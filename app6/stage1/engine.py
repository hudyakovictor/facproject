from __future__ import annotations

import json
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .assets import save_image_assets, save_uv_and_mesh, technical_quality, save_face_mask, save_semantic_channels
from .config import IMAGE_EXTENSIONS, PHOTO_SCHEMA_VERSION, SCHEMA_VERSION, Stage1Config
from .geometry import pack_mask, to_original_image
from .masks import build_mask_bundle
from .naming import make_photo_id, parse_photo_name
from .reconstruction import ReconstructionBundle, ReconstructionEngine
from .storage import atomic_photo_directory, clean_incomplete, write_failure
from .utils import atomic_json, runtime_versions, sha256_file, sha256_json, sha256_paths, write_csv
from .validator import is_resumable, validate_photo
from .skin.pipeline import build_skin_package
from .skin.input_provenance import decode_oriented


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _landmark_rows(points: np.ndarray, visible: np.ndarray, indices: np.ndarray) -> list[dict[str, Any]]:
    return [
        {"landmark_id": i, "x": float(p[0]), "y": float(p[1]), "z": float(p[2]),
         "visible": int(visible[i]), "vertex_index": int(indices[i])}
        for i, p in enumerate(points)
    ]


class Stage1Engine:
    def __init__(self, config: Stage1Config):
        self.cfg = config
        self.root = config.project_root.resolve()
        self.cfg.output_dir.mkdir(parents=True, exist_ok=True)
        clean_incomplete(self.cfg.output_dir)
        self.config_hash = sha256_json(config.extraction_payload())
        package_dir = Path(__file__).resolve().parent
        workspace_dir = package_dir.parents[1]
        code_files = (
            list(package_dir.rglob("*.py"))
            + [self.root / "model" / "recon.py"]
            + list((workspace_dir / "uv_module").rglob("*.py"))
        )
        self.code_hash = sha256_paths(code_files, self.root)
        weight = "net_recon.pth" if config.backbone == "resnet50" else "net_recon_mbnet.pth"
        model_files = [self.root / "assets" / "face_model.npy", self.root / "assets" / weight, self.root / "assets" / "large_base_net.pth", self.root / "app6" / "atlas" / "texture_zones_bfm35709_v3.npz"]
        missing = [p for p in model_files if not p.is_file()]
        if missing:
            raise FileNotFoundError("missing required model assets: " + ", ".join(map(str, missing)))
        self.model_hash = sha256_paths(model_files, self.root)
        self.recon = ReconstructionEngine(self.root, config.device, config.detector, config.backbone)

    def run(self) -> dict[str, Any]:
        photos = sorted(
            p for p in self.cfg.input_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and not p.name.startswith("._")
        )
        if self.cfg.limit:
            photos = photos[: self.cfg.limit]
        started = time.time(); rows: list[dict[str, Any]] = []; errors: list[dict[str, Any]] = []
        skipped = 0
        for number, path in enumerate(photos, 1):
            print(f"[{number}/{len(photos)}] {path.name}", flush=True)
            try:
                info, was_skipped = self._one(path)
                rows.append(self._index_row(info)); skipped += int(was_skipped)
            except Exception as exc:
                payload = {
                    "source_relative_path": self._relative(path), "source_filename": path.name,
                    "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(), "timestamp": _utc(),
                }
                errors.append(payload)
                try:
                    parsed = parse_photo_name(path); source_hash = sha256_file(path)
                    write_failure(self.cfg.output_dir, make_photo_id(parsed, source_hash), payload)
                except Exception:
                    pass
                print(f"  ERROR {type(exc).__name__}: {exc}", flush=True)
                self.recon.cleanup()
                if not self.cfg.continue_on_error:
                    raise
        rows.sort(key=lambda r: (r["date"], int(r["same_date_sequence"]), r["photo_id"]))
        pose_counts: dict[str, int] = {}
        for i, row in enumerate(rows, 1):
            row["chronology_index_global"] = i
            pose = str(row["pose_bin"])
            pose_counts[pose] = pose_counts.get(pose, 0) + 1
            row["chronology_index_in_pose"] = pose_counts[pose]
        write_csv(self.cfg.output_dir / "main_index.csv", rows or [{"status": "no_successes"}])
        write_csv(self.cfg.output_dir / "main_timeline.csv", rows or [{"status": "no_successes"}])
        if errors:
            write_csv(self.cfg.output_dir / "errors.csv", errors)
        else:
            (self.cfg.output_dir / "errors.csv").write_text("", encoding="utf-8")
        manifest = {
            "schema_version": SCHEMA_VERSION, "status": "complete" if not errors else "complete_with_errors",
            "created_at_utc": _utc(), "input_count": len(photos), "success_count": len(rows),
            "error_count": len(errors), "skipped_valid_count": skipped, "elapsed_seconds": time.time() - started,
            "input_dir": str(self.cfg.input_dir.resolve()), "output_dir": str(self.cfg.output_dir.resolve()),
            "device": self.recon.device, "detector": self.cfg.detector, "backbone": self.cfg.backbone,
            "uv_size": self.cfg.uv_size, "code_hash": self.code_hash, "config_hash": self.config_hash,
            "model_hash": self.model_hash, "runtime": runtime_versions(),
        }
        atomic_json(self.cfg.output_dir / "stage1_manifest.json", manifest)
        print(f"DONE success={len(rows)} errors={len(errors)} skipped={skipped}", flush=True)
        return manifest

    def _one(self, path: Path) -> tuple[dict[str, Any], bool]:
        parsed = parse_photo_name(path)
        source_hash = sha256_file(path)
        photo_id = make_photo_id(parsed, source_hash)
        final = self.cfg.output_dir / photo_id
        if not self.cfg.overwrite:
            okay, info = is_resumable(final, source_hash, self.code_hash, self.config_hash, self.model_hash)
            if okay and info is not None:
                return info, True
        try:
            bgr, decode_meta = decode_oriented(path)
        except Exception as exc:
            raise RuntimeError(f"cannot decode/orient image: {exc}") from exc
        rec = self.recon.process(path, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        ldm = rec.landmark_arrays()
        ldm106_original = to_original_image(ldm["ldm106_image_224"], rec.trans_params)
        ldm134_original = to_original_image(ldm["ldm134_image_224"], rec.trans_params)
        mask = build_mask_bundle(rec.semantic_channels_224, rec.trans_params, bgr.shape)

        with atomic_photo_directory(self.cfg.output_dir, photo_id, overwrite=final.exists()) as out:
            files, crop_meta = save_image_assets(path, bgr, ldm106_original, out, self.cfg.save_original)
            try:
                face_mask_files = save_face_mask(bgr, mask.hard_original, crop_meta["bbox_original"], out)
                if face_mask_files:
                    files.update(face_mask_files)
                else:
                    files["face_mask"] = None
                    files["face_mask_data"] = None
            except Exception:
                files["face_mask"] = None
                files["face_mask_data"] = None
            files["semantic_channels"] = save_semantic_channels(mask, out)
            uv_files, uv_arrays, uv_meta = save_uv_and_mesh(
                bgr, rec, out, self.cfg.uv_size, skin_mask=mask.hard_original
            )
            files.update(uv_files)
            quality = technical_quality(bgr, crop_meta["bbox_original"], mask.hard_original, rec.combined_visible)
            quality["uv_observed_coverage"] = uv_meta["observed_coverage"]

            pose_payload = {"pitch": float(rec.angles_deg[0]), "yaw": float(rec.angles_deg[1]), "roll": float(rec.angles_deg[2]),
                            "pose_bin": rec.pose_bin, "canonical_yaw": rec.canonical_yaw}
            # Legacy forehead-fallback quality zones are intentionally not run.
            # Family-level applicability is produced later in the native skin
            # package from A20/S40/W14/Q projection and decomposed quality maps.
            quality_summary = {"status": "migrated_to_skin_quality_v1"}

            write_csv(out / "ldm106_raw.csv", _landmark_rows(ldm["ldm106_object"], ldm["ldm106_visible"], rec.ldm106_indices))
            write_csv(out / "ldm106_aligned.csv", _landmark_rows(ldm["ldm106_bin_canonical"], ldm["ldm106_visible"], rec.ldm106_indices))
            write_csv(out / "ldm134_raw.csv", _landmark_rows(ldm["ldm134_object"], ldm["ldm134_visible"], rec.ldm134_indices))
            write_csv(out / "ldm134_aligned.csv", _landmark_rows(ldm["ldm134_bin_canonical"], ldm["ldm134_visible"], rec.ldm134_indices))
            files.update({
                "ldm106_raw": "ldm106_raw.csv", "ldm106_aligned": "ldm106_aligned.csv",
                "ldm134_raw": "ldm134_raw.csv", "ldm134_aligned": "ldm134_aligned.csv",
            })

            arrays: dict[str, np.ndarray] = {
                "vertices_object": rec.vertices_object, "vertices_identity_only": rec.vertices_identity_only,
                "vertices_object_normalized": rec.vertices_object_normalized, "vertices_bin_canonical": rec.vertices_bin_canonical,
                "vertices_camera": rec.vertices_camera, "vertices_image_224": rec.vertices_image_224,
                "normals_object": rec.normals_object, "normals_posed": rec.normals_posed,
                "triangles": rec.triangles, "uv_coords": rec.uv_coords,
                "ldm106_vertex_indices": rec.ldm106_indices, "ldm134_vertex_indices": rec.ldm134_indices,
                "ldm106_identity_only": rec.vertices_identity_only[rec.ldm106_indices].astype(np.float32),
                "ldm134_identity_only": rec.vertices_identity_only[rec.ldm134_indices].astype(np.float32),
                "full_mesh_front_facing_packbits": pack_mask(rec.front_facing),
                "full_mesh_renderer_visible_packbits": pack_mask(rec.renderer_visible),
                "full_mesh_visible_packbits": pack_mask(rec.combined_visible),
                "alpha_full": rec.alpha_full, "alpha_id": rec.alpha_id, "alpha_exp": rec.alpha_exp,
                "alpha_alb": rec.alpha_alb, "alpha_sh": rec.alpha_sh,
                "angle_rad": rec.angles_rad, "angle_deg_pitch_yaw_roll": rec.angles_deg,
                "rotation_matrix": rec.rotation, "translation": rec.translation, "trans_params": rec.trans_params,
                "normalization_center": rec.normalization_center,
                "normalization_scale": np.asarray([rec.normalization_scale], np.float32),
                "canonical_rotation_row_matrix": rec.canonical_rotation,
                "canonical_yaw": np.asarray([rec.canonical_yaw], np.float32),
                **ldm, **uv_arrays,
            }
            np.savez_compressed(out / "reconstruction.npz", **arrays)
            files["reconstruction"] = "reconstruction.npz"

            # Native-photo skin evidence package. This consumes the already computed
            # reconstruction and therefore never performs a second 3DDFA inference.
            vertices_original_xy = to_original_image(rec.vertices_image_224, rec.trans_params)
            try:
                build_skin_package(
                    photo_id=photo_id, input_path=path, bgr=bgr, out_dir=out,
                    triangles=rec.triangles, vertices_original_xy=vertices_original_xy,
                    vertices_depth=rec.vertices_camera[:, 2], normals=rec.normals_posed,
                    surface_vertices=rec.vertices_object_normalized,
                    vertex_visibility=rec.combined_visible,
                    face_mask_data_path=out / "face_mask.npz",
                    atlas_path=self.root / "app6" / "atlas" / "texture_zones_bfm35709_v3.npz",
                    coordinate_chain={"encoded_to_oriented":decode_meta,"original_to_model_224":"3ddfa_trans_params_v1","model_224_to_original":"app6.geometry.to_original_image","trans_params":np.asarray(rec.trans_params).tolist(),"display_crop":crop_meta,"source_xy":"explicit_original_oriented_pixels"},
                    models={"3ddfa_model_hash":self.model_hash},
                    config={**self.cfg.extraction_payload(),"skin_contract":"A20-S40-W14-Q-v3"}, pose=pose_payload,
                )
                files["skin_manifest"] = "skin/manifest.json"; skin_status={"state":"success"}
            except Exception as exc:
                # Preserve expensive reconstruction. run_skin_stage1.py retries this
                # package without a second 3DDFA call.
                skin_status={"state":"failed_retryable","error":str(exc)}
                atomic_json(out / "skin_failure.json", skin_status);files["skin_failure"]="skin_failure.json"

            info = {
                "schema_version": PHOTO_SCHEMA_VERSION, "photo_id": photo_id,
                "source_filename": path.name, "source_relative_path": self._relative(path), "source_sha256": source_hash,
                "date": parsed.date_iso, "date_year": parsed.year, "date_month": parsed.month,
                "date_day": parsed.day, "same_date_sequence": parsed.sequence,
                "extraction_timestamp": _utc(), "code_hash": self.code_hash,
                "config_hash": self.config_hash, "model_hash": self.model_hash,
                "image": {"width": int(bgr.shape[1]), "height": int(bgr.shape[0]), "extension": path.suffix.lower(), "decode": decode_meta},
                "pose": pose_payload,
                "camera": {"projection": "perspective", "focal": 1015.0, "principal_point": [112.0, 112.0],
                           "camera_distance": 10.0, "render_size": [224, 224]},
                "normalization": {"method": "full_mesh_rms_v1", "center": rec.normalization_center,
                                  "scale": rec.normalization_scale},
                "landmark_contract": {"raw": "object identity+expression", "aligned": "full-mesh RMS normalized then pose-bin canonical yaw"},
                "mask": {"status": mask.status, "error": mask.error, **mask.metadata},
                "uv": {"status": "valid", **uv_meta}, "quality_inputs": quality,
                "quality_summary": quality_summary, "skin": skin_status,
                "reprojection": rec.reprojection, "crop": crop_meta, "files": files,
            }
            atomic_json(out / "info.json", info)
            result = validate_photo(out, write_result=True)
            if result["status"] != "complete":
                raise RuntimeError("validation failed: " + "; ".join(result["errors"]))
        return info, False

    def _relative(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.cfg.input_dir.resolve()))
        except ValueError:
            return path.name

    @staticmethod
    def _index_row(info: dict[str, Any]) -> dict[str, Any]:
        pose = info["pose"]; quality = info["quality_inputs"]
        return {
            "photo_id": info["photo_id"], "date": info["date"], "same_date_sequence": info["same_date_sequence"],
            "pose_bin": pose["pose_bin"], "pitch": pose["pitch"], "yaw": pose["yaw"], "roll": pose["roll"],
            "source_filename": info["source_filename"], "source_relative_path": info["source_relative_path"],
            "geometry_status": "valid", "segmentation_status": info["mask"]["status"], "uv_status": info["uv"]["status"],
            "combined_visible_fraction": quality["combined_visible_fraction"],
            "skin_mask_coverage": quality["skin_mask_coverage"], "uv_observed_coverage": quality["uv_observed_coverage"],
        }
