"""Stage 1 engine — deterministic extraction from photos.

Key differences from app6:
- No SHA-256 on source photos (photo_id = canonical stem only)
- No original file copy (path recorded in info.json)
- Skin pipeline integrated (no separate scripts needed)
- FFHQ receives original crop (not masked)
- Preview level control: --preview-level none|minimal|full
- Photometric normalization before texture extraction
- Reduced output: no redundant JSON summaries
"""

from __future__ import annotations

import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .assets import save_face_mask, save_image_assets, save_uv_and_mesh, technical_quality
from .config import SCHEMA_VERSION, PHOTO_SCHEMA_VERSION
from .expression import classify_expression
from .geodesic import compute_landmark_geodesic_matrix, geodesic_distance_vector
from .geometry import pack_mask, to_original_image
from .input_provenance import decode_oriented
from .landmark_zones import compute_landmark_zones, landmark_zone_weights
from .masks import build_mask_bundle
from .naming import make_photo_id, parse_photo_name
from .reconstruction import ReconstructionEngine
from .skin.pipeline import build_skin_package
from .skin.spatial_signatures import compute_zone_spatial_signatures
from .storage import atomic_photo_directory, clean_incomplete, write_failure
from .utils import atomic_json, runtime_versions, sha256_json, sha256_paths, write_csv
from .validator import is_resumable, validate_photo


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _landmark_rows(points, visible, indices):
    return [
        {"landmark_id": i, "x": float(p[0]), "y": float(p[1]), "z": float(p[2]),
         "visible": int(visible[i]), "vertex_index": int(indices[i])}
        for i, p in enumerate(points)
    ]


class Stage1Engine:
    """Process all photos in input_dir: reconstruct → extract → save."""

    def __init__(self, config):
        self.cfg = config
        self.root = config.project_root.resolve()
        self.cfg.output_dir.mkdir(parents=True, exist_ok=True)
        clean_incomplete(self.cfg.output_dir)

        # Compute code/config hashes for cache invalidation
        self.config_hash = sha256_json(config.extraction_payload())
        package_dir = Path(__file__).resolve().parent
        workspace_dir = package_dir.parents[1]
        code_files = list(package_dir.rglob("*.py"))
        self.code_hash = sha256_paths(code_files, self.root)

        # Check required model assets
        weight = "net_recon.pth" if config.backbone == "resnet50" else "net_recon_mbnet.pth"
        model_files = [
            self.root / "assets" / "face_model.npy",
            self.root / "assets" / weight,
            self.root / "assets" / "large_base_net.pth",
            self.root / "app7" / "atlas" / "texture_zones_bfm35709_v3.npz",
        ]
        missing = [p for p in model_files if not p.is_file()]
        if missing:
            raise FileNotFoundError("missing required model assets: " + ", ".join(map(str, missing)))

        self.recon = ReconstructionEngine(self.root, config.device, config.detector, config.backbone)

    def run(self) -> dict[str, Any]:
        photos = sorted(
            p for p in self.cfg.input_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
            and not p.name.startswith("._")
        )
        if self.cfg.limit:
            photos = photos[:self.cfg.limit]

        started = time.time()
        rows, errors = [], []
        skipped = 0

        for number, path in enumerate(photos, 1):
            print(f"[{number}/{len(photos)}] {path.name}", flush=True)
            try:
                info, was_skipped = self._one(path)
                rows.append(self._index_row(info))
                skipped += int(was_skipped)
            except Exception as exc:
                payload = {
                    "source_filename": path.name,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "timestamp": _utc(),
                }
                errors.append(payload)
                try:
                    parsed = parse_photo_name(path)
                    write_failure(self.cfg.output_dir, make_photo_id(parsed), payload)
                except Exception:
                    pass
                print(f"  ERROR {type(exc).__name__}: {exc}", flush=True)
                self.recon.cleanup()
                if not self.cfg.continue_on_error:
                    raise

        # Sort and add chronology indices
        rows.sort(key=lambda r: (r["date"], int(r["same_date_sequence"]), r["photo_id"]))
        pose_counts: dict[str, int] = {}
        for i, row in enumerate(rows, 1):
            row["chronology_index_global"] = i
            pose = str(row["pose_bin"])
            pose_counts[pose] = pose_counts.get(pose, 0) + 1
            row["chronology_index_in_pose"] = pose_counts[pose]

        write_csv(self.cfg.output_dir / "main_index.csv", rows or [{"status": "no_successes"}])
        if errors:
            write_csv(self.cfg.output_dir / "errors.csv", errors)

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete" if not errors else "complete_with_errors",
            "created_at_utc": _utc(),
            "input_count": len(photos),
            "success_count": len(rows),
            "error_count": len(errors),
            "skipped_valid_count": skipped,
            "elapsed_seconds": time.time() - started,
            "device": self.recon.device,
            "detector": self.cfg.detector,
            "backbone": self.cfg.backbone,
            "uv_size": self.cfg.uv_size,
            "code_hash": self.code_hash,
            "config_hash": self.config_hash,
            "runtime": runtime_versions(),
            "pose_bins": {k: v for k, v in pose_counts.items()},
        }
        atomic_json(self.cfg.output_dir / "stage1_manifest.json", manifest)
        print(f"DONE success={len(rows)} errors={len(errors)} skipped={skipped}", flush=True)
        return manifest

    def _one(self, path: Path) -> tuple[dict[str, Any], bool]:
        parsed = parse_photo_name(path)
        photo_id = make_photo_id(parsed)

        # Check if already processed (same code + config)
        final = self.cfg.output_dir / photo_id
        if not self.cfg.overwrite:
            okay, info = is_resumable(final, self.code_hash, self.config_hash)
            if okay and info is not None:
                return info, True

        # Decode image
        bgr, decode_meta = decode_oriented(path)

        # 3DDFA reconstruction (single inference)
        rec = self.recon.process(path, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        ldm = rec.landmark_arrays()
        ldm106_original = to_original_image(ldm["ldm106_image_224"], rec.trans_params)
        ldm134_original = to_original_image(ldm["ldm134_image_224"], rec.trans_params)

        # Build mask
        mask = build_mask_bundle(rec.semantic_channels_224, rec.trans_params, bgr.shape)

        with atomic_photo_directory(self.cfg.output_dir, photo_id, overwrite=final.exists()) as out:
            # Image assets (face crop + thumbnail, NO original copy)
            files, crop_meta = save_image_assets(path, bgr, ldm106_original, out)

            # Face mask
            bbox = crop_meta["bbox"]
            try:
                face_mask_files = save_face_mask(bgr, mask.hard_original, bbox, out)
                if face_mask_files:
                    files.update(face_mask_files)
            except Exception:
                files["face_mask"] = None
                files["face_mask_data"] = None

            # UV + mesh
            uv_files, uv_meta = save_uv_and_mesh(
                bgr, rec, out, self.cfg.uv_size, skin_mask=mask.hard_original)
            files.update(uv_files)

            # Quality metrics
            quality = technical_quality(bgr, bbox, mask.hard_original, rec.combined_visible)
            quality["uv_observed_coverage"] = uv_meta.get("observed_coverage", 0.0)

            # Pose
            pose_payload = {
                "pitch": float(rec.angles_deg[0]),
                "yaw": float(rec.angles_deg[1]),
                "roll": float(rec.angles_deg[2]),
                "pose_bin": rec.pose_bin,
                "canonical_yaw": rec.canonical_yaw,
            }

            # Landmarks (raw + aligned)
            write_csv(out / "ldm106_raw.csv",
                       _landmark_rows(ldm["ldm106_object"], ldm["ldm106_visible"], rec.ldm106_indices))
            write_csv(out / "ldm106_aligned.csv",
                       _landmark_rows(ldm["ldm106_bin_canonical"], ldm["ldm106_visible"], rec.ldm106_indices))
            write_csv(out / "ldm134_raw.csv",
                       _landmark_rows(ldm["ldm134_object"], ldm["ldm134_visible"], rec.ldm134_indices))
            write_csv(out / "ldm134_aligned.csv",
                       _landmark_rows(ldm["ldm134_bin_canonical"], ldm["ldm134_visible"], rec.ldm134_indices))
            files.update({
                "ldm106_raw": "ldm106_raw.csv", "ldm106_aligned": "ldm106_aligned.csv",
                "ldm134_raw": "ldm134_raw.csv", "ldm134_aligned": "ldm134_aligned.csv",
            })

            # Reconstruction data
            arrays = {
                "vertices_object": rec.vertices_object,
                "vertices_identity_only": rec.vertices_identity_only,
                "vertices_object_normalized": rec.vertices_object_normalized,
                "vertices_bin_canonical": rec.vertices_bin_canonical,
                "vertices_camera": rec.vertices_camera,
                "vertices_image_224": rec.vertices_image_224,
                "normals_object": rec.normals_object,
                "normals_posed": rec.normals_posed,
                "triangles": rec.triangles,
                "uv_coords": rec.uv_coords,
                "ldm106_vertex_indices": rec.ldm106_indices,
                "ldm134_vertex_indices": rec.ldm134_indices,
                "full_mesh_front_facing_packbits": pack_mask(rec.front_facing),
                "full_mesh_renderer_visible_packbits": pack_mask(rec.renderer_visible),
                "full_mesh_visible_packbits": pack_mask(rec.combined_visible),
                "alpha_id": rec.alpha_id,
                "alpha_exp": rec.alpha_exp,
                "angle_deg_pitch_yaw_roll": rec.angles_deg,
                "rotation_matrix": rec.rotation,
                "translation": rec.translation,
                "trans_params": rec.trans_params,
                "normalization_center": rec.normalization_center,
                "normalization_scale": np.asarray([rec.normalization_scale], np.float32),
                "canonical_rotation_row_matrix": rec.canonical_rotation,
                "canonical_yaw": np.asarray([rec.canonical_yaw], np.float32),
                **ldm,
            }
            np.savez_compressed(out / "reconstruction.npz", **arrays)
            files["reconstruction"] = "reconstruction.npz"

            # ── Expression classification ──
            expression = classify_expression(rec.alpha_exp)
            atomic_json(out / "expression.json", expression)

            # ── Landmark zone mapping ──
            atlas_path = self.root / "app7" / "atlas" / "texture_zones_bfm35709_v3.npz"
            ldm106_zones = None
            ldm134_zones = None
            if atlas_path.is_file():
                with np.load(atlas_path, allow_pickle=False) as az:
                    atlas_a20 = az.get("zone_id_a20", az.get("A"))
                if atlas_a20 is not None:
                    ldm106_zones = compute_landmark_zones(rec.ldm106_indices, rec.triangles, atlas_a20)
                    ldm134_zones = compute_landmark_zones(rec.ldm134_indices, rec.triangles, atlas_a20)
                    atomic_json(out / "ldm106_zones.json", ldm106_zones)
                    atomic_json(out / "ldm134_zones.json", ldm134_zones)
                    files["ldm106_zones"] = "ldm106_zones.json"
                    files["ldm134_zones"] = "ldm134_zones.json"

            # ── Geodesic landmark distance matrix ──
            try:
                geo_106 = compute_landmark_geodesic_matrix(
                    rec.vertices_object_normalized, rec.triangles, rec.ldm106_indices)
                np.savez_compressed(out / "geodesic_ldm106.npz",
                                    geodesic_matrix=geo_106.astype(np.float32),
                                    landmark_indices=rec.ldm106_indices)
                files["geodesic_ldm106"] = "geodesic_ldm106.npz"
            except Exception:
                pass

            # ── Skin evidence package ──
            vertices_original_xy = to_original_image(rec.vertices_image_224, rec.trans_params)
            try:
                build_skin_package(
                    photo_id=photo_id, input_path=path, bgr=bgr, out_dir=out,
                    triangles=rec.triangles,
                    vertices_original_xy=vertices_original_xy,
                    vertices_depth=rec.vertices_camera[:, 2],
                    normals=rec.normals_posed,
                    surface_vertices=rec.vertices_object_normalized,
                    vertex_visibility=rec.combined_visible,
                    face_mask_data_path=out / "face_mask.npz",
                    atlas_path=self.root / "app7" / "atlas" / "texture_zones_bfm35709_v3.npz",
                    coordinate_chain={
                        "encoded_to_oriented": decode_meta,
                        "original_to_model_224": "3ddfa_trans_params_v1",
                        "model_224_to_original": "geometry.to_original_image",
                        "trans_params": np.asarray(rec.trans_params).tolist(),
                        "source_xy": "explicit_original_oriented_pixels",
                    },
                    models={"3ddfa_backbone": self.cfg.backbone},
                    config={**self.cfg.extraction_payload(), "skin_contract": "A20-S40-W14-Q-v3"},
                    pose=pose_payload,
                    preview_level=self.cfg.preview_level,
                )
                files["skin_manifest"] = "skin/manifest.json"
                skin_status = {"state": "success"}
            except Exception as exc:
                skin_status = {"state": "failed_retryable", "error": str(exc)}
                atomic_json(out / "skin_failure.json", skin_status)
                files["skin_failure"] = "skin_failure.json"

            # ── info.json ──
            info = {
                "schema_version": PHOTO_SCHEMA_VERSION,
                "photo_id": photo_id,
                "source_filename": path.name,
                "source_relative_path": str(path.resolve().relative_to(self.cfg.input_dir.resolve()))
                    if path.is_relative_to(self.cfg.input_dir.resolve()) else path.name,
                "date": parsed.date_iso,
                "date_year": parsed.year, "date_month": parsed.month, "date_day": parsed.day,
                "same_date_sequence": parsed.sequence,
                "extraction_timestamp": _utc(),
                "code_hash": self.code_hash,
                "config_hash": self.config_hash,
                "image": {"width": int(bgr.shape[1]), "height": int(bgr.shape[0]),
                          "extension": path.suffix.lower(), "decode": decode_meta},
                "pose": pose_payload,
                "normalization": {"method": "full_mesh_rms_v1",
                                  "center": rec.normalization_center,
                                  "scale": rec.normalization_scale},
                "landmark_contract": {
                    "raw": "object identity+expression",
                    "aligned": "full-mesh RMS normalized then pose-bin canonical yaw",
                },
                "mask": {"status": mask.status, "error": mask.error, **mask.metadata},
                "uv": {"status": "valid", **uv_meta},
                "quality_inputs": quality,
                "skin": skin_status,
                "reprojection": rec.reprojection,
                "crop": crop_meta,
                "files": files,
            }
            atomic_json(out / "info.json", info)

            result = validate_photo(out, write_result=True)
            if result["status"] != "complete":
                raise RuntimeError("validation failed: " + "; ".join(result["errors"]))

        return info, False

    @staticmethod
    def _index_row(info: dict) -> dict[str, Any]:
        pose = info["pose"]
        quality = info["quality_inputs"]
        return {
            "photo_id": info["photo_id"],
            "date": info["date"],
            "same_date_sequence": info["same_date_sequence"],
            "pose_bin": pose["pose_bin"],
            "pitch": pose["pitch"], "yaw": pose["yaw"], "roll": pose["roll"],
            "source_filename": info["source_filename"],
            "combined_visible_fraction": quality["combined_visible_fraction"],
            "skin_mask_coverage": quality["skin_mask_coverage"],
            "uv_observed_coverage": quality["uv_observed_coverage"],
        }
