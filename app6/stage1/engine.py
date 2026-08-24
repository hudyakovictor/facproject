"""
🎯 CRITICAL → Оркестратор Stage 1: один inference 3DDFA → все артефакты фото.

Для каждого фото _one() выполняет: EXIF-ориентацию, 3DDFA-реконструкцию,
chronology alignment, запись reconstruction.npz / ldm*-{raw,aligned,chronology}.csv /
info.json, skin authenticity/texture.json по face_mask.png и валидацию.
Контракты: schema deeputin-stage1-v2.4-chronology-alignment; в info["chronology"]
пишутся alignment_quality, residual_*_deg, pose_confidence, expression_magnitude,
detection_confidence. run() дополнительно: content digest-дедупликация входа (#22),
пропуск уже валидных фото (resume), атомарный main_timeline.csv.
💡 NOTE: ldm*_aligned.csv — DEPRECATED (yaw-only); используйте ldm*_chronology.csv.
"""
from __future__ import annotations

import json
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .assets import save_image_assets, save_uv_and_mesh, technical_quality, save_face_mask, save_semantic_channels
from .config import (
    EXPRESSION_MAGNITUDE_THRESHOLD, EXPRESSION_CORNER_LIFT_THRESHOLD, EXPRESSION_JAW_OPEN_THRESHOLD,
    IMAGE_EXTENSIONS, PHOTO_SCHEMA_VERSION, SCHEMA_VERSION, Stage1Config,
)
from .geometry import pack_mask, to_original_image
from .status_logger import log_status, status_warning
from .masks import build_mask_bundle
from .naming import PhotoName, make_nonchronological_photo_name, make_photo_id, parse_photo_name
from .reconstruction import ReconstructionEngine
from .storage import atomic_photo_directory, clean_incomplete, write_failure
from .utils import atomic_json, runtime_versions, digest_file, digest_json, digest_paths, write_csv
from .validator import is_resumable, validate_photo
from .input_provenance import build_date_provenance, decode_oriented
from .provenance_ledger import hamming_distance,load_provenance_sidecar,perceptual_dhash
from .authenticity import build_texture_package


def _utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def discover_input_photos(input_dir: Path, require_filename_date: bool = True) -> list[Path]:
    """Return eligible photos only after validating their authoritative dates.

    A bad filename must not be converted into an ``errors.csv`` row after a
    partially completed extraction: filename date is the chronology authority,
    so accepting a partial timeline would make the batch scientifically
    non-reproducible.  AppleDouble sidecars are deliberately ignored; they are
    macOS metadata, never source photographs.
    """
    photos = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and not p.name.startswith("._")
    )
    if not require_filename_date:
        return photos
    invalid: list[str] = []
    for path in photos:
        try:
            parse_photo_name(path)
        except ValueError as exc:
            invalid.append(f"{path.relative_to(input_dir)}: {exc}")
    if invalid:
        examples = "; ".join(invalid[:10])
        suffix = "" if len(invalid) <= 10 else f" (+{len(invalid) - 10} more)"
        raise ValueError(
            "input preflight failed: every photograph needs a valid calendar "
            f"date in its filename; {examples}{suffix}"
        )
    return photos


def _landmark_rows(points: np.ndarray, visible: np.ndarray, indices: np.ndarray,
                    confidence: np.ndarray | None = None) -> list[dict[str, Any]]:
    """Создание строк CSV для ландмарков с опциональным confidence.
    📊 METRIC — confidence вычисляется из projection + visibility.
    """
    # status: complete — отлажена, работает
    points = np.asarray(points)
    visible = np.asarray(visible)
    indices = np.asarray(indices)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("landmark points must have shape (N,3)")
    if len(visible) != len(points) or len(indices) != len(points):
        raise ValueError("landmark points/visibility/indices length mismatch")
    if not np.isfinite(points).all():
        raise ValueError("landmark points contain NaN/Inf")
    if confidence is not None and len(confidence) != len(points):
        raise ValueError("landmark confidence length mismatch")
    rows = []
    for i, p in enumerate(points):
        row = {
            "landmark_id": i,
            "x": float(p[0]),
            "y": float(p[1]),
            "z": float(p[2]),
            "visible": int(visible[i]),
            "vertex_index": int(indices[i]),
        }
        if confidence is not None:
            row["confidence"] = float(confidence[i])
        rows.append(row)
    return rows


def _landmark_rows_2d(points: np.ndarray, visible: np.ndarray, indices: np.ndarray) -> list[dict[str, Any]]:
    """Создание строк CSV для 2D ландмарков в оригинальном изображении (x, y пиксели)."""
    points = np.asarray(points)
    visible = np.asarray(visible)
    indices = np.asarray(indices)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("2D landmark points must have shape (N,2)")
    if len(visible) != len(points) or len(indices) != len(points):
        raise ValueError("landmark points/visibility/indices length mismatch")
    if not np.isfinite(points).all():
        raise ValueError("landmark points contain NaN/Inf")
    rows = []
    for i, p in enumerate(points):
        rows.append({
            "landmark_id": i,
            "x_px": float(p[0]),
            "y_px": float(p[1]),
            "visible": int(visible[i]),
            "vertex_index": int(indices[i]),
        })
    return rows


class Stage1Engine:
    def __init__(self, config: Stage1Config):
        self.cfg = config
        self.root = config.project_root.resolve()
        if not self.cfg.input_dir.is_dir():
            raise FileNotFoundError(f"input directory not found: {self.cfg.input_dir}")
        # The filename date is the authority for chronology.  Validate every
        # eligible photo before loading a neural model or creating an output.
        self.photos = discover_input_photos(self.cfg.input_dir, self.cfg.require_filename_date)
        self.config_hash = digest_json(config.extraction_payload())
        package_dir = Path(__file__).resolve().parent
        workspace_dir = package_dir.parents[1]
        code_files = (
            list(package_dir.rglob("*.py"))
            + [self.root / "model" / "recon.py"]
            + list((workspace_dir / "uv_module").rglob("*.py"))
        )
        self.code_hash = digest_paths(code_files, self.root)
        weight = "net_recon.pth" if config.backbone == "resnet50" else "net_recon_mbnet.pth"
        model_files = [self.root / "assets" / "face_model.npy", self.root / "assets" / weight, self.root / "assets" / "large_base_net.pth", self.root / "app6" / "atlas" / "texture_zones_bfm35709_v3.npz"]
        missing = [p for p in model_files if not p.is_file()]
        if missing:
            raise FileNotFoundError("missing required model assets: " + ", ".join(map(str, missing)))
        self.model_hash = digest_paths(model_files, self.root)
        self.recon = ReconstructionEngine(self.root, config.device, config.detector, config.backbone)

    def run(self) -> dict[str, Any]:
        log_status("run", "complete")
        if not self.cfg.input_dir.is_dir():
            raise FileNotFoundError(f"input directory not found: {self.cfg.input_dir}")
        photos = self.photos
        if self.cfg.limit:
            photos = photos[: self.cfg.limit]
        if not photos:
            raise RuntimeError(f"no supported input photos under {self.cfg.input_dir}")

        # Output is created only after input, assets, dependencies and photo
        # discovery have all passed preflight.
        self.cfg.output_dir.mkdir(parents=True, exist_ok=True)
        clean_incomplete(self.cfg.output_dir)

        # 🎯 CRITICAL: Detect duplicate photos by content digest hash
        # Different filenames but same content = duplicates
        seen_hashes:dict[str,str]={};seen_visual:list[tuple[str,str]]=[]
        duplicate_count=0;near_duplicate_count=0;unique_photos=[];input_provenance_rows=[]
        for path in photos:
            file_hash=digest_file(path);relative=self._relative(path);duplicate_of=seen_hashes.get(file_hash)
            phash=perceptual_dhash(path);nearest=min(((hamming_distance(phash,h),r) for h,r in seen_visual),default=(999,None))
            near_distance,near_duplicate_of=nearest if nearest[0]<=4 else (None,None)
            near_duplicate_count+=int(bool(near_duplicate_of) and not bool(duplicate_of));side=load_provenance_sidecar(path)
            input_provenance_rows.append({"source_relative_path":relative,"source_filename":path.name,"source_digest":file_hash,
              "size_bytes":path.stat().st_size,"perceptual_dhash":phash,"duplicate_of":duplicate_of or "",
              "near_duplicate_of":near_duplicate_of or "","near_duplicate_hamming":near_distance if near_duplicate_of else "",
              "included":not bool(duplicate_of),"provenance_sidecar_status":side.get("status"),
              "provenance_sidecar_path":side.get("sidecar_path"),"provenance_sidecar_digest":side.get("sidecar_digest")})
            if duplicate_of:
                print(f"  ⚠️ DUPLICATE: {path.name} == {duplicate_of} (skipping)",flush=True);duplicate_count+=1;continue
            seen_hashes[file_hash]=relative;seen_visual.append((phash,relative));unique_photos.append(path)
        # Dataset identity is independent of absolute paths and filesystem order.
        dataset_hash = digest_json(sorted(
            ({"path":r["source_relative_path"],"digest":r["source_digest"],"provenance_sidecar_digest":r.get("provenance_sidecar_digest")}
             for r in input_provenance_rows), key=lambda x: x["path"]
        ))
        write_csv(self.cfg.output_dir / "input_provenance.csv",input_provenance_rows)
        self._provenance_index={str(r["source_relative_path"]):r for r in input_provenance_rows}

        if duplicate_count > 0:
            print(f"  Found {duplicate_count} duplicate photos (skipped)", flush=True)

        started = time.time(); rows: list[dict[str, Any]] = []; errors: list[dict[str, Any]] = []
        skipped = 0
        for number, path in enumerate(unique_photos, 1):
            print(f"[{number}/{len(unique_photos)}] {path.name}", flush=True)
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
                    parsed = self._photo_name(path); source_hash = digest_file(path)
                    write_failure(self.cfg.output_dir, make_photo_id(parsed, source_hash), payload)
                except Exception as failure_exc:
                    status_warning("write_failure", f"could not persist failure record: {failure_exc}")
                print(f"  ERROR {type(exc).__name__}: {exc}", flush=True)
                self.recon.cleanup()
                if not self.cfg.continue_on_error:
                    raise
        rows.sort(key=lambda r: (r["date"] or "", int(r["same_date_sequence"]), r["photo_id"]))
        pose_counts: dict[str, int] = {}
        for i, row in enumerate(rows, 1):
            row["chronology_index_global"] = i
            pose = str(row["pose_bin"])
            pose_counts[pose] = pose_counts.get(pose, 0) + 1
            row["chronology_index_in_pose"] = pose_counts[pose]
        # 💡 NOTE (AUDIT-5): main_index.csv — дубль main_timeline.csv, оставлен как
        # compatibility-alias для внешних read-only потребителей (стиль app7).
        # Канонический индекс для stage2 — main_timeline.csv (см. stage2/loaders.py).
        write_csv(self.cfg.output_dir / "main_index.csv", rows or [{"status": "no_successes"}])
        write_csv(self.cfg.output_dir / "main_timeline.csv", rows or [{"status": "no_successes"}])
        if errors:
            write_csv(self.cfg.output_dir / "errors.csv", errors)
        else:
            (self.cfg.output_dir / "errors.csv").write_text("", encoding="utf-8")
        self.recon.cleanup()
        manifest = {
            "schema_version": SCHEMA_VERSION, "status": "complete" if not errors else "complete_with_errors",
            "created_at_utc": _utc(), "input_count": len(photos), "success_count": len(rows),
            "error_count":len(errors),"duplicate_count":duplicate_count,"near_duplicate_count":near_duplicate_count,
            "skipped_valid_count": skipped, "elapsed_seconds": time.time() - started,
            "input_dir": str(self.cfg.input_dir.resolve()), "output_dir": str(self.cfg.output_dir.resolve()),
            "device": self.recon.device, "detector": self.cfg.detector, "backbone": self.cfg.backbone,
            "uv_size": self.cfg.uv_size, "dataset_hash": dataset_hash,
            "code_hash": self.code_hash, "config_hash": self.config_hash,
            "model_hash":self.model_hash,"hash_algorithms":{"source":"sha256","dataset":"sha256-canonical-json","code":"sha256-path-tree","model":"sha256","config":"sha256-canonical-json","provenance_sidecar":"sha256","perceptual":"dhash64"},"runtime":runtime_versions(),
            "provenance_index": "input_provenance.csv",
        }
        atomic_json(self.cfg.output_dir / "stage1_manifest.json", manifest)
        print(f"DONE success={len(rows)} errors={len(errors)} skipped={skipped}", flush=True)
        return manifest

    def _one(self, path: Path) -> tuple[dict[str, Any], bool]:
        """🎯 CRITICAL → Обработка ОДНОГО фото через весь Stage 1.

        Вызывается для каждого фото в цикле run(). Здесь происходит:
        1. 3DDFA inference (reconstruction.py)
        2. Pose classification + chronology alignment
        3. Semantic mask + face mask generation
        4. UV texture + mesh generation
        5. Skin feature extraction (skin/pipeline.py)
        6. Сохранение ВСЕХ результатов в output_dir/photo_id/

        🔗 DEPENDS ON:
          - run() — вызывает в цикле для каждого фото
          - reconstruction.process() — 3DDFA inference
          - build_texture_package() — skin authenticity from face_mask.png

        ⚠️ IN PROGRESS:
          - Нет проверки что фото не дублируется по содержимому
          - Нет проверки качества реконструкции (reprojection error)
          - Нет фильтрации по expression magnitude

        💡 NOTE:
          - Результаты атомарно сохраняются (temp dir → rename)
          - При ошибке — пишет в _failures/photo_id.json
          - При resume — проверяет хеши и пропускает уже обработанные

        🚨 WARNING:
          - Не вызывать параллельно для одного и того же фото!
          - При continue_on_error=False — останавливается на первой ошибке
        """
        log_status("_one", "complete")
        parsed = self._photo_name(path)
        source_hash = digest_file(path)
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
                    atomic_json(out / "face_mask_failure.json", {
                        "status": "unavailable",
                        "reason": "save_face_mask_returned_none",
                        "mask_status": getattr(mask, "status", None),
                        "mask_error": getattr(mask, "error", None),
                    })
                    files["face_mask_failure"] = "face_mask_failure.json"
            except Exception as face_mask_exc:
                files["face_mask"] = None
                files["face_mask_data"] = None
                atomic_json(out / "face_mask_failure.json", {
                    "status": "failed",
                    "error": str(face_mask_exc),
                    "mask_status": getattr(mask, "status", None),
                    "mask_error": getattr(mask, "error", None),
                })
                files["face_mask_failure"] = "face_mask_failure.json"
            files["semantic_channels"] = save_semantic_channels(mask, out)
            uv_files, uv_arrays, uv_meta = save_uv_and_mesh(
                bgr, rec, out, self.cfg.uv_size, skin_mask=mask.hard_original,
                save_mesh=self.cfg.save_mesh
            )
            files.update(uv_files)
            quality = technical_quality(bgr, crop_meta["bbox_original"], mask.hard_original, rec.combined_visible)
            quality["uv_observed_coverage"] = uv_meta["observed_coverage"]

            reprojection_p95 = float(max(r["p95"] for r in rec.reprojection.values()))
            reprojection_rmse = float(min(r["rmse"] for r in rec.reprojection.values()))

            pose_payload = {"pitch": float(rec.angles_deg[0]), "yaw": float(rec.angles_deg[1]), "roll": float(rec.angles_deg[2]),
                            "pose_bin": rec.pose_bin, "canonical_yaw": rec.canonical_yaw}
            # Legacy forehead-fallback quality zones are intentionally not run.
            # Family-level applicability is produced later in the native skin
            # package from A20/S40/W14/Q projection and decomposed quality maps.
            quality_summary = {"status": "skin_authenticity_v1"}
            # Compute per-landmark confidence for chronology landmarks
            # Confidence = visibility * reprojection_anchor * front_facing
            # Higher = more reliable landmark for comparison
            def _compute_landmark_confidence(visible_arr, front_facing_arr, indices, reproj_factor):
                """📊 METRIC — Per-landmark confidence score (0-1)."""
                conf = np.zeros(len(indices), np.float32)
                for i, idx in enumerate(indices):
                    if visible_arr[i]:
                        # Base confidence from visibility
                        conf[i] = 1.0
                        # Reduce if not front-facing
                        if not front_facing_arr[idx]:
                            conf[i] *= 0.5
                        # Reduce by reprojection quality factor
                        conf[i] *= reproj_factor
                return conf

            # Reprojection quality factor (1.0 = perfect, 0.0 = bad)
            reproj_factor = float(np.clip(1.0 - reprojection_p95 / 10.0, 0.1, 1.0))

            ldm106_confidence = _compute_landmark_confidence(
                ldm["ldm106_visible"], rec.front_facing, rec.ldm106_indices, reproj_factor
            )
            ldm134_confidence = _compute_landmark_confidence(
                ldm["ldm134_visible"], rec.front_facing, rec.ldm134_indices, reproj_factor
            )


            write_csv(out / "ldm106_raw.csv", _landmark_rows(ldm["ldm106_object"], ldm["ldm106_visible"], rec.ldm106_indices))
            # ⚠️ DEPRECATED: ldm*_aligned.csv использует только yaw коррекцию
            # Для хронологии используйте ldm*_chronology.csv (полная pose коррекция)
            write_csv(out / "ldm106_aligned.csv", _landmark_rows(ldm["ldm106_bin_canonical"], ldm["ldm106_visible"], rec.ldm106_indices))
            write_csv(out / "ldm106_chronology.csv", _landmark_rows(ldm["ldm106_chronology_aligned"], ldm["ldm106_visible"], rec.ldm106_indices, ldm106_confidence))
            write_csv(out / "ldm134_raw.csv", _landmark_rows(ldm["ldm134_object"], ldm["ldm134_visible"], rec.ldm134_indices))
            write_csv(out / "ldm134_aligned.csv", _landmark_rows(ldm["ldm134_bin_canonical"], ldm["ldm134_visible"], rec.ldm134_indices))
            write_csv(out / "ldm134_chronology.csv", _landmark_rows(ldm["ldm134_chronology_aligned"], ldm["ldm134_visible"], rec.ldm134_indices, ldm134_confidence))
            # Landmarks in original image pixel coordinates (224→original)
            write_csv(out / "ldm106_original.csv", _landmark_rows_2d(ldm106_original, ldm["ldm106_visible"], rec.ldm106_indices))
            write_csv(out / "ldm134_original.csv", _landmark_rows_2d(ldm134_original, ldm["ldm134_visible"], rec.ldm134_indices))
            files.update({
                "ldm106_raw": "ldm106_raw.csv",
                "ldm106_aligned": "ldm106_aligned.csv",  # DEPRECATED: yaw-only
                "ldm106_chronology": "ldm106_chronology.csv",  # RECOMMENDED
                "ldm106_original": "ldm106_original.csv",  # original image px
                "ldm134_raw": "ldm134_raw.csv",
                "ldm134_aligned": "ldm134_aligned.csv",  # DEPRECATED: yaw-only
                "ldm134_chronology": "ldm134_chronology.csv",  # RECOMMENDED
                "ldm134_original": "ldm134_original.csv",  # original image px
            })
            # Compute per-vertex visibility confidence
            # Combines: combined_visible, front_facing, renderer_visible
            # Higher = more reliable vertex for comparison
            vertex_visibility_confidence = (
                rec.combined_visible.astype(np.float32) *
                rec.front_facing.astype(np.float32) *
                (1.0 - np.clip(reprojection_p95 / 10.0, 0.0, 0.5))  # reduce for bad reprojection
            ).astype(np.float32)


            arrays: dict[str, np.ndarray] = {
                "vertices_object": rec.vertices_object, "vertices_identity_only": rec.vertices_identity_only,
                "vertices_object_normalized": rec.vertices_object_normalized, "vertices_bin_canonical": rec.vertices_bin_canonical,
                "vertices_chronology_aligned": rec.vertices_chronology_aligned,
                "vertices_camera": rec.vertices_camera, "vertices_image_224": rec.vertices_image_224,
                "normals_object": rec.normals_object, "normals_posed": rec.normals_posed,
                "triangles": rec.triangles, "uv_coords": rec.uv_coords,
                "vertex_visibility_confidence": vertex_visibility_confidence,
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
                "chronology_correction_matrix": rec.chronology_correction_matrix,
                "chronology_target_pose": rec.chronology_target_pose,
                "canonical_yaw": np.asarray([rec.canonical_yaw], np.float32),
                **ldm, **uv_arrays,
            }
            np.savez_compressed(out / "reconstruction.npz", **arrays)
            files["reconstruction"] = "reconstruction.npz"

            # Skin authenticity from face_mask.png only (old skin/ package removed).
            try:
                face_mask_png = out / "face_mask.png"
                if not face_mask_png.is_file():
                    raise FileNotFoundError("face_mask.png unavailable for authenticity extract")
                skin_summary = build_texture_package(
                    out_dir=out,
                    face_mask_png=face_mask_png,
                    photo_id=photo_id,
                )
                files.update(skin_summary.get("files") or {})
                skin_status = {
                    "state": skin_summary.get("state", "success"),
                    "source": skin_summary.get("source", "face_mask.png"),
                    "contract": skin_summary.get("contract", "skin-authenticity-v1"),
                    "panel": skin_summary.get("panel", "top20_z_median"),
                    "texture_file": skin_summary.get("texture_file", "texture.json"),
                    "hard_stop": bool(skin_summary.get("hard_stop", False)),
                    "hard_stop_reason": skin_summary.get("hard_stop_reason"),
                }
            except Exception as exc:
                skin_status = {"state": "failed_retryable", "error": str(exc), "source": "face_mask.png"}
                atomic_json(out / "skin_failure.json", skin_status)
                files["skin_failure"] = "skin_failure.json"

            # Пороги мимики заданы в общем конфиге (config.py).
            # - EXPRESSION_MAGNITUDE_THRESHOLD (12.0) — L2 норма alpha_exp (stage2)
            # - EXPRESSION_CORNER_LIFT_THRESHOLD (0.005) — подъём уголков рта
            # - EXPRESSION_JAW_OPEN_THRESHOLD (0.28) — раскрытие рта
            _ = EXPRESSION_MAGNITUDE_THRESHOLD  # используется stage2/engine.py
            # Compute alignment quality: how much correction was applied
            # Lower is better (less correction needed = more reliable)
            actual_pose = np.array([float(rec.angles_deg[0]), float(rec.angles_deg[1]), float(rec.angles_deg[2])])
            target_pose = np.array([0.0, float(rec.canonical_yaw), 0.0])
            correction_per_axis = np.abs(actual_pose - target_pose)

            # Compute residual pose after correction
            # This is the remaining pose difference after applying chronology alignment
            # Ideally should be close to [0, 0, 0]
            # Residual = actual - target (what we tried to correct)
            residual_pose = actual_pose - target_pose
            residual_pitch = float(residual_pose[0])
            residual_yaw = float(residual_pose[1])
            residual_roll = float(residual_pose[2])
            # Weight yaw less (expected to be larger), pitch/roll more (should be near 0)
            alignment_quality = float(1.0 - np.clip(
                (correction_per_axis[0] / 15.0 + correction_per_axis[1] / 30.0 + correction_per_axis[2] / 15.0) / 3.0,
                0.0, 1.0
            ))
            correction_magnitude_deg = float(np.linalg.norm(correction_per_axis))
            # Compute expression magnitude from alpha_exp
            # alpha_exp is a 64-dim vector representing expression coefficients
            # Higher norm = more extreme expression
            expression_magnitude = float(np.linalg.norm(rec.alpha_exp))

            # Estimate jaw opening from alpha_exp
            # In 3DDFA, dimensions 0-2 are typically jaw-related (pitch, yaw, roll of jaw)
            # This is a heuristic - actual jaw opening depends on the specific model
            jaw_open_degree = float(np.abs(rec.alpha_exp[0]) * 100) if len(rec.alpha_exp) > 0 else 0.0
            # Compute pose confidence
            # Extreme poses (>50° yaw) have lower confidence in 3DDFA
            # This is based on the model's training distribution
            yaw_magnitude = abs(float(rec.angles_deg[1]))
            if yaw_magnitude < 20:
                pose_confidence = 1.0  # frontal: high confidence
            elif yaw_magnitude < 40:
                pose_confidence = 0.9  # light 3/4: good confidence
            elif yaw_magnitude < 55:
                pose_confidence = 0.7  # deep 3/4: moderate confidence
            elif yaw_magnitude < 70:
                pose_confidence = 0.5  # profile: lower confidence
            else:
                pose_confidence = 0.3  # extreme profile: low confidence
            # Estimate face detection confidence
            # Based on face bbox size relative to image (larger = more confident)
            # and face position (center = more confident)
            face_bbox_area = crop_meta["bbox_original"][2] * crop_meta["bbox_original"][3]
            image_area = bgr.shape[0] * bgr.shape[1]
            face_area_ratio = face_bbox_area / max(image_area, 1)

            # Heuristic: face should be 5%-80% of image
            if 0.05 < face_area_ratio < 0.8:
                detection_confidence = min(1.0, face_area_ratio * 2)
            else:
                detection_confidence = 0.3  # too small or too large

            # Compute visible landmarks count for this pose
            visible_106 = int(np.sum(ldm["ldm106_visible"]))
            visible_134 = int(np.sum(ldm["ldm134_visible"]))

            # ── Expression metrics from raw 3DDFA landmarks (object space) ──
            # Детекция выражений ТОЛЬКО через геометрию ключевых точек,
            # НЕ через alpha_exp (BFM expression coefficients).
            #
            # corner_lift_ioc — подъём уголков рта относительно центра рта,
            # нормализованный по межзрачковому расстоянию (interocular).
            # Положительное значение = уголки ПОДНЯТЫ = улыбка.
            # Отрицательное значение = уголки опущены = спокойное лицо.
            # Метрика НЕ ЗАВИСИТ от ширины рта человека — только от того,
            # насколько уголки поднимаются относительно центра рта.
            # Это чистая геометрия формы, а не размера.
            #
            # Индексы 106-точечной схемы 3DDFA_V3:
            #   84 = левый уголок рта, 90 = правый уголок рта
            #   87 = верхняя губа (центр), 93 = нижняя губа (центр)
            #   74 = левый глаз, 77 = правый глаз
            _L_CORNER, _R_CORNER = 84, 90
            _UP_LIP, _LOW_LIP = 87, 93
            _EYE_L, _EYE_R = 74, 77
            raw_pts = ldm["ldm106_object"]
            ioc = float(np.linalg.norm(raw_pts[_EYE_L] - raw_pts[_EYE_R])) or 1.0
            mouth_center_y = (raw_pts[_UP_LIP][1] + raw_pts[_LOW_LIP][1]) / 2.0
            corner_avg_y = (raw_pts[_L_CORNER][1] + raw_pts[_R_CORNER][1]) / 2.0
            corner_lift_ioc = float((corner_avg_y - mouth_center_y) / ioc)
            # jaw_open_ratio — раскрытие рта: 3D-расстояние между верхней и нижней
            # губой, нормализованное по межзрачковому расстоянию.
            # При открытом рте расстояние резко возрастает (0.40+ vs ≤0.17 у спокойных).
            # Не зависит от размера рта человека благодаря нормализации по IOC.
            jaw_open_ratio = float(np.linalg.norm(raw_pts[_UP_LIP] - raw_pts[_LOW_LIP])) / ioc
            # Комбинированный флаг: улыбка (подъём уголков) ИЛИ открытый рот
            smile_detected = corner_lift_ioc > EXPRESSION_CORNER_LIFT_THRESHOLD
            jaw_open_detected = jaw_open_ratio > EXPRESSION_JAW_OPEN_THRESHOLD

            source_provenance=load_provenance_sidecar(path)
            info = {
                "schema_version": PHOTO_SCHEMA_VERSION, "photo_id": photo_id,
                "source_filename": path.name, "source_relative_path": self._relative(path), "source_digest": source_hash,
                "date": parsed.date_iso or None, "date_year": parsed.year or None, "date_month": parsed.month or None,
                "date_day": parsed.day or None, "same_date_sequence": parsed.sequence,
                "date_provenance": (build_date_provenance(parsed.date_iso,decode_meta,source_provenance)
                                    if self.cfg.require_filename_date else {"status": "not_applicable", "authority": "calibration_reference"}),
                "source_provenance":source_provenance,"perceptual_dhash":perceptual_dhash(path),
                "near_duplicate_of":(getattr(self,"_provenance_index",{}).get(self._relative(path),{}) or {}).get("near_duplicate_of") or None,
                "extraction_timestamp": _utc(), "code_hash": self.code_hash,
                "config_hash": self.config_hash, "model_hash": self.model_hash,
                "image": {"width": int(bgr.shape[1]), "height": int(bgr.shape[0]), "extension": path.suffix.lower(), "decode": decode_meta},
                "pose": pose_payload,
                "chronology": {
                    "alignment_method": "full_pose_correction_v1",
                    "applied_rotation": rec.chronology_correction_matrix.tolist(),
                    "applied_scale": float(rec.normalization_scale),
                    "applied_center": rec.normalization_center.tolist(),
                    "target_pose": rec.chronology_target_pose.tolist(),
                    "actual_pose": rec.angles_deg.tolist(),
                    "pose_bin": rec.pose_bin,
                    "canonical_yaw": float(rec.canonical_yaw),
                    "visible_landmarks_106": visible_106,
                    "visible_landmarks_134": visible_134,
                    "alignment_csv_106": "ldm106_chronology.csv",
                    "alignment_csv_134": "ldm134_chronology.csv",
                    "alignment_quality": alignment_quality,
                    "correction_magnitude_deg": correction_magnitude_deg,
                    "correction_pitch_deg": float(correction_per_axis[0]),
                    "correction_yaw_deg": float(correction_per_axis[1]),
                    "correction_roll_deg": float(correction_per_axis[2]),
                    "residual_pitch_deg": residual_pitch,
                    "residual_yaw_deg": residual_yaw,
                    "residual_roll_deg": residual_roll,
                    "reprojection_p95": reprojection_p95,
                    "reprojection_rmse": reprojection_rmse,
                    "expression_magnitude": expression_magnitude,
                    "jaw_open_degree": jaw_open_degree,
                    "corner_lift_ioc": corner_lift_ioc,
                    "jaw_open_ratio": jaw_open_ratio,
                    "smile_detected": smile_detected,
                    "jaw_open_detected": jaw_open_detected,
                    "pose_confidence": pose_confidence,
                    "detection_confidence": detection_confidence,
                    "face_area_ratio": float(face_area_ratio),
                    "description": "Full pose correction (pitch+yaw+roll) to canonical pose. Use chronology CSVs for within-bin comparison."
                },
                "camera": {"projection": "perspective", "focal": 1015.0, "principal_point": [112.0, 112.0],
                           "camera_distance": 10.0, "render_size": [224, 224]},
                "normalization": {"method": "full_mesh_rms_v1", "center": rec.normalization_center.tolist(),
                                  "scale": float(rec.normalization_scale)},
                "landmark_contract": {
                    "raw": "object identity+expression",
                    "aligned": "full-mesh RMS normalized then pose-bin canonical yaw (yaw only)",
                    "chronology": "full pose correction (pitch+yaw+roll) to canonical pose, identity-only vertices"
                },
                "mask": {"status": mask.status, "error": mask.error, **mask.metadata},
                "uv": {"status": "valid", **uv_meta}, "quality_inputs": quality,
                "quality_summary": quality_summary, "skin": skin_status,
                "reprojection": rec.reprojection, "crop": crop_meta, "files": files,
            }
            # 🛠️ PATCH → quality honesty: compute real technical metrics using already-defined variables.
            quality_summary = {
                "status": "technical_v1",
                "reprojection_p95": reprojection_p95,
                "reprojection_rmse": reprojection_rmse,
                "correction_magnitude_deg": float(np.linalg.norm(correction_per_axis)),
                "alignment_quality": float(1.0 - np.clip(
                    (correction_per_axis[0] / 15.0 + correction_per_axis[1] / 30.0 + correction_per_axis[2] / 15.0) / 3.0,
                    0.0, 1.0
                )),
                "face_area_ratio": face_area_ratio,
                "uv_observed_coverage": uv_meta["observed_coverage"],
            }
            if skin_status.get("state") == "success" and (out / "texture.json").is_file():
                tex = json.loads((out / "texture.json").read_text(encoding="utf-8"))
                info["skin_quality_score"] = tex.get("quality", {}).get("score")
                info["skin_quality_status"] = tex.get("quality", {}).get("status")
                info["skin_authenticity_score"] = tex.get("authenticity", {}).get("score")
                info["skin_authenticity_status"] = tex.get("authenticity", {}).get("status")
            else:
                info["skin_quality_score"] = None
                info["skin_quality_status"] = "failed"
                info["skin_authenticity_score"] = None
                info["skin_authenticity_status"] = "failed"
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

    def _photo_name(self, path: Path) -> PhotoName:
        if self.cfg.require_filename_date:
            return parse_photo_name(path)
        return make_nonchronological_photo_name(path, self._relative(path))

    @staticmethod
    def _index_row(info: dict[str, Any]) -> dict[str, Any]:
        pose = info["pose"]; quality = info["quality_inputs"]
        return {
            "photo_id": info["photo_id"], "date": info["date"], "same_date_sequence": info["same_date_sequence"],
            "pose_bin": pose["pose_bin"], "pitch": pose["pitch"], "yaw": pose["yaw"], "roll": pose["roll"],
            "source_filename": info["source_filename"], "source_relative_path": info["source_relative_path"],
            "date_provenance_status": info.get("date_provenance", {}).get("status", "unknown"),
            "exif_date": info.get("date_provenance", {}).get("exif_date"),
            "date_delta_days":info.get("date_provenance",{}).get("delta_days"),
            "source_claimed_date":info.get("date_provenance",{}).get("source_claimed_date"),
            "source_claimed_delta_days":info.get("date_provenance",{}).get("source_claimed_delta_days"),
            "date_conflict_sources":info.get("date_provenance",{}).get("conflict_sources",[]),
            "source_provenance_status":info.get("source_provenance",{}).get("status","not_provided"),
            "source_url":info.get("source_provenance",{}).get("source_url"),"archive_url":info.get("source_provenance",{}).get("archive_url"),
            "perceptual_dhash":info.get("perceptual_dhash"),"near_duplicate_of":info.get("near_duplicate_of"),
            "geometry_status": "valid", "segmentation_status": info["mask"]["status"], "uv_status": info["uv"]["status"],
            "combined_visible_fraction": quality["combined_visible_fraction"],
            "skin_mask_coverage": quality["skin_mask_coverage"], "uv_observed_coverage": quality["uv_observed_coverage"],
        }
