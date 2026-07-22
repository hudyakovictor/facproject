from __future__ import annotations
from app6.stage1.status_logger import log_status, log_blocker, log_warning

import csv
import json
from pathlib import Path

import numpy as np

from .core import Record
from .quality_integration import load_quality_zone_summary


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_main(stage1_root: Path) -> list[Record]:
    log_status("load_main", "complete")
    """🎯 CRITICAL → Загрузка записей Stage 1 для анализа Stage 2.

    Читает main_timeline.csv, затем для каждого фото:
    - info.json (метаданные, pose, alignment quality)
    - reconstruction.npz (вершины, ландмарки, видимость)

    🔗 DEPENDS ON:
      - engine.run() — вызывается в начале Stage 2
      - stage1 output — структура папок photo_id/

    ⚠️ IN PROGRESS:
      - Использует chronology-aligned landmarks (ldm134_chronology_aligned)
      - Fallback к object_normalized если chronology отсутствует (legacy)
      - Нет проверки что все записи из одного источника

    💡 NOTE:
      - Фильтрует по validation.status == "complete"
      - Сортирует по (date, sequence, record_id)
      - Загружает alignment quality для фильтрации пар

    🚨 WARNING:
      - Если reconstruction.npz не содержит chronology arrays — fallback к старым данным!
      - При отсутствии info.json — запись пропускается
    """
    index = stage1_root / "main_timeline.csv"
    if not index.is_file():
        raise FileNotFoundError(index)
    out: list[Record] = []
    for row in _rows(index):
        if not row.get("photo_id"):
            continue
        directory = stage1_root / row["photo_id"]
        validation = json.loads((directory / "validation.json").read_text(encoding="utf-8"))
        if validation.get("status") != "complete":
            continue
        info = json.loads((directory / "info.json").read_text(encoding="utf-8"))
        relative_source = str(info.get("source_relative_path") or "")
        source_parts = Path(relative_source).parts
        source_group = source_parts[0] if len(source_parts) > 1 else "unknown"
        qsum = info.get("quality_summary") or {}
        gtq = qsum.get("global_texture_quality") or {}
        qzones = load_quality_zone_summary(directory)
        with np.load(directory / "reconstruction.npz", allow_pickle=False) as z:
            idx106 = z["ldm106_vertex_indices"].astype(np.int64); idx134 = z["ldm134_vertex_indices"].astype(np.int64)
            # CRITICAL: Use chronology-aligned landmarks (full pitch+yaw+roll correction)
            # NOT object_normalized (which has no pose correction)
            ldm106_chrono = z.get("ldm106_chronology_aligned")
            ldm134_chrono = z.get("ldm134_chronology_aligned")
            ldm106_obj = z.get("ldm106_object_normalized", z.get("ldm106_object_norm"))
            ldm134_obj = z.get("ldm134_object_normalized", z.get("ldm134_object_norm"))
            # Validate chronology data is present and finite
            use_chronology = (
                ldm106_chrono is not None and ldm134_chrono is not None
                and np.isfinite(ldm106_chrono).all() and np.isfinite(ldm134_chrono).all()
            )
            if use_chronology:
                ldm106_data = ldm106_chrono.astype(np.float32)
                ldm134_data = ldm134_chrono.astype(np.float32)
            else:
                # Fallback to object_normalized if chronology not available (legacy data)
                ldm106_data = ldm106_obj.astype(np.float32)
                ldm134_data = ldm134_obj.astype(np.float32)
            out.append(Record(
                record_id=row["photo_id"], dataset_id="main", date=row["date"], sequence=int(row["same_date_sequence"]),
                pose_bin=row["pose_bin"], angles=z["angle_deg_pitch_yaw_roll"].astype(np.float32),
                ldm106=ldm106_data,
                ldm134=ldm134_data,
                visible106=z["ldm106_visible"].astype(bool), visible134=z["ldm134_visible"].astype(bool),
                alpha_id=z["alpha_id"].astype(np.float32), alpha_exp=z["alpha_exp"].astype(np.float32),
                identity_only106=(z["ldm106_identity_only"] if "ldm106_identity_only" in z else z["vertices_identity_only"][idx106]).astype(np.float32),
                identity_only134=(z["ldm134_identity_only"] if "ldm134_identity_only" in z else z["vertices_identity_only"][idx134]).astype(np.float32),
                quality_status=str(gtq.get("status", qsum.get("status", "unknown"))),
                quality_texture_score=float(gtq.get("texture_score_0_1", 0.0) or 0.0),
                forehead_wrinkle_supported=bool(qsum.get("supported_forehead_wrinkle_pose_v1", False)),
                quality_zones=qzones,
                record_dir=str(directory),
                source_group=source_group,
                source_sha256=info.get("source_sha256"),
            ))
    return sorted(out, key=lambda r: (r.date or "9999", r.sequence, r.record_id))


def _read_landmark_csv(path: Path, count: int) -> np.ndarray:
    """Load landmark_id,x,y,z CSV into (count,3) float32 ordered by landmark_id."""
    rows = _rows(path)
    if not rows:
        raise ValueError(f"empty landmark CSV: {path}")
    by_id: dict[int, list[float]] = {}
    for row in rows:
        lid = int(float(row["landmark_id"]))
        by_id[lid] = [float(row["x"]), float(row["y"]), float(row["z"])]
    out = np.full((count, 3), np.nan, np.float32)
    for lid, xyz in by_id.items():
        if 0 <= lid < count:
            out[lid] = np.asarray(xyz, np.float32)
    return out


def _missing_alpha(count: int) -> np.ndarray:
    """Explicit NaN vector for unavailable alpha channels (never fabricated zeros)."""
    return np.full((count,), np.nan, np.float32)


def load_calibration_from_sidecar(root: Path) -> list[Record]:
    log_status("load_calibration_from_sidecar", "complete")
    """Recover Records from metadata.json + ldm*_raw.csv when record.npz is absent.

    Space contract:
      object_normalized = (raw_object - center) / scale
    Never treat aligned/bin_canonical CSV as object_normalized.
    Alpha is unavailable in the published sidecar layout → NaN vectors.
    """
    out: list[Record] = []
    for meta_path in sorted(root.glob("*/frame_*/metadata.json")):
        directory = meta_path.parent
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        arrays = meta.get("arrays") or {}
        raw106_path = directory / "ldm106_raw.csv"
        raw134_path = directory / "ldm134_raw.csv"
        if not raw106_path.is_file() or not raw134_path.is_file():
            continue
        center = np.asarray(arrays.get("object_normalization_center"), np.float64).reshape(-1)
        scale_arr = np.asarray(arrays.get("object_normalization_scale"), np.float64).reshape(-1)
        if center.size != 3 or scale_arr.size < 1:
            raise ValueError(f"sidecar missing object_normalization center/scale: {directory}")
        scale = float(scale_arr[0])
        if not np.isfinite(scale) or abs(scale) < 1e-12:
            raise ValueError(f"invalid object_normalization_scale in {directory}")
        raw106 = _read_landmark_csv(raw106_path, 106)
        raw134 = _read_landmark_csv(raw134_path, 134)
        ldm106 = ((raw106.astype(np.float64) - center.reshape(1, 3)) / scale).astype(np.float32)
        ldm134 = ((raw134.astype(np.float64) - center.reshape(1, 3)) / scale).astype(np.float32)
        vis106 = np.asarray(arrays.get("ldm106_visible_original"), bool).reshape(-1)
        vis134 = np.asarray(arrays.get("ldm134_visible_original"), bool).reshape(-1)
        if vis106.size != 106 or vis134.size != 134:
            raise ValueError(f"sidecar visibility length mismatch: {directory}")
        angles = np.asarray(arrays.get("angle_deg_pitch_yaw_roll"), np.float32).reshape(3)
        out.append(Record(
            record_id=str(meta.get("record_id") or directory.name),
            dataset_id=str(meta.get("dataset_id") or directory.parent.name),
            date=None,
            sequence=int(meta.get("frame_index", 0)),
            pose_bin=str(meta.get("pose_bin") or "unknown"),
            angles=angles,
            ldm106=ldm106,
            ldm134=ldm134,
            visible106=vis106,
            visible134=vis134,
            alpha_id=_missing_alpha(80),
            alpha_exp=_missing_alpha(64),
            record_dir=str(directory),
            source_group=str(meta.get("dataset_id") or directory.parent.name),
            source_sha256=meta.get("source_sha256"),
        ))
    if not out:
        raise FileNotFoundError(f"no sidecar calibration frames under {root}")
    return out


def load_calibration(calibration_root: Path) -> list[Record]:
    log_status("load_calibration", "complete")
    root = calibration_root
    # Native app6 Stage-1 same-day calibration output. This is the format
    # produced by the top-level run_calibration.py workflow.
    if (root / "main_timeline.csv").is_file():
        records = load_main(root)
        for record in records:
            record.dataset_id = "same_day_calibration"
            record.date = None
        if not records:
            raise FileNotFoundError(f"no valid Stage-1 calibration records under {root}")
        return records
    if (root / "calibration_datasets").is_dir():
        root = root / "calibration_datasets"
    out: list[Record] = []
    for npz_path in sorted(root.glob("*/*/record.npz")):
        directory = npz_path.parent
        meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        with np.load(npz_path, allow_pickle=False) as z:
            alpha_id = z["alpha_id"].astype(np.float32) if "alpha_id" in z.files else _missing_alpha(80)
            alpha_exp = z["alpha_exp"].astype(np.float32) if "alpha_exp" in z.files else _missing_alpha(64)
            out.append(Record(
                record_id=meta["record_id"], dataset_id=meta["dataset_id"], date=None, sequence=int(meta.get("frame_index", 0)),
                pose_bin=meta["pose_bin"], angles=z["angle_deg_pitch_yaw_roll"].astype(np.float32),
                ldm106=z.get("ldm106_object_norm", z.get("ldm106_object_normalized")).astype(np.float32),
                ldm134=z.get("ldm134_object_norm", z.get("ldm134_object_normalized")).astype(np.float32),
                visible106=z["ldm106_visible_original"].astype(bool), visible134=z["ldm134_visible_original"].astype(bool),
                alpha_id=alpha_id, alpha_exp=alpha_exp,
                record_dir=str(directory),
            ))
    if out:
        for rec in out:
            if rec.ldm106 is None or rec.ldm134 is None:
                raise ValueError(
                    f"Calibration record {rec.record_id} has no landmark data. "
                    "Expected 'ldm106_object_norm' or 'ldm106_object_normalized' in record.npz"
                )
        return out
    # Published archive often ships metadata+CSV sidecars only.
    return load_calibration_from_sidecar(root)
