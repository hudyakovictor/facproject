"""🎯 CRITICAL → Загрузка записей Stage 1 (npz+csv+sidecar) в Record-структуры.
🚪 API: load_main(), load_calibration(), load_calibration_from_sidecar()
🔗 DEPENDS ON: stage1.validator контракты (6 CSV + npz keys)
🚨 WARNING: _missing_alpha() мягко помечает записи без α-каналов.
"""
from __future__ import annotations
from app6.stage1.status_logger import log_status

import csv
import json
from pathlib import Path

import numpy as np

from .core import Record
from .quality_integration import load_quality_zone_summary
from .robustness import validate_landmarks, validate_serialized_record


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _required_npz_array(z: np.lib.npyio.NpzFile, key: str, shape: tuple[int, ...]) -> np.ndarray:
    """Load a required finite array without legacy-space substitution."""
    if key not in z.files:
        raise ValueError(f"required NPZ array missing: {key}")
    arr = np.asarray(z[key])
    if arr.shape != shape:
        raise ValueError(f"NPZ {key} shape {arr.shape}, expected {shape}")
    if np.issubdtype(arr.dtype, np.number) and not np.isfinite(arr).all():
        raise ValueError(f"NPZ {key} contains NaN/Inf")
    return arr


def load_main(stage1_root: Path) -> list[Record]:
    """🎯 CRITICAL → Загрузка записей Stage 1 для анализа Stage 2.

    Читает main_timeline.csv, затем для каждого фото:
    - info.json (метаданные, pose, alignment quality)
    - reconstruction.npz (вершины, ландмарки, видимость)

    🔗 DEPENDS ON:
      - engine.run() — вызывается в начале Stage 2
      - stage1 output — структура папок photo_id/

    APPLICABILITY:
      - Требует chronology-aligned landmarks; legacy-space fallback запрещён.
      - Source group сохраняется для диагностики и corroboration.

    💡 NOTE:
      - Фильтрует по validation.status == "complete"
      - Сортирует по (date, sequence, record_id)
      - Загружает alignment quality для фильтрации пар

    🚨 WARNING:
      - Если reconstruction.npz не содержит chronology arrays — fallback к старым данным!
      - При отсутствии info.json — запись пропускается
    """
    log_status("load_main", "complete")
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
        chronology_info = info.get("chronology") or {}
        gtq = qsum.get("global_texture_quality") or {}
        qzones = load_quality_zone_summary(directory)
        with np.load(directory / "reconstruction.npz", allow_pickle=False) as z:
            idx106 = z["ldm106_vertex_indices"].astype(np.int64); idx134 = z["ldm134_vertex_indices"].astype(np.int64)
            # CRITICAL: never substitute a different coordinate space.
            ldm106_data = _required_npz_array(z, "ldm106_chronology_aligned", (106, 3)).astype(np.float32)
            ldm134_data = _required_npz_array(z, "ldm134_chronology_aligned", (134, 3)).astype(np.float32)
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
                coordinate_noise_sigma=float(chronology_info.get("coordinate_noise_sigma", 0.0) or 0.0),
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
        if lid in by_id:
            raise ValueError(f"duplicate landmark_id {lid} in {path}")
        if not 0 <= lid < count:
            raise ValueError(f"landmark_id {lid} outside 0..{count - 1} in {path}")
        xyz = [float(row["x"]), float(row["y"]), float(row["z"])]
        if not np.isfinite(xyz).all():
            raise ValueError(f"nonfinite landmark {lid} in {path}")
        by_id[lid] = xyz
    missing = sorted(set(range(count)) - set(by_id))
    if missing:
        raise ValueError(f"missing landmark ids in {path}: {missing[:10]}")
    out = np.full((count, 3), np.nan, np.float32)
    for lid, xyz in by_id.items():
        out[lid] = np.asarray(xyz, np.float32)
    validate_landmarks(out, ids=np.arange(count), expected_count=count)
    return out


def _missing_alpha(count: int) -> np.ndarray:
    """Explicit NaN vector for unavailable alpha channels (never fabricated zeros)."""
    return np.full((count,), np.nan, np.float32)


def load_calibration_from_sidecar(root: Path) -> list[Record]:
    """Recover Records from metadata.json + ldm*_raw.csv when record.npz is absent.

    Space contract:
      object_normalized = (raw_object - center) / scale
    Never treat aligned/bin_canonical CSV as object_normalized.
    Alpha is unavailable in the published sidecar layout → NaN vectors.
    """
    log_status("load_calibration_from_sidecar", "complete")
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
    """Загрузка калибровочных записей через Stage 1 из сырых фото.

    🔥 ВАЖНО: данные в calibration_dataset/person_*/frame_*/ признаны
    неактуальными (извлечены неверно). Используются ТОЛЬКО сырые фото
    из calibration_dataset/photos/ с переизвлечением через Stage 1.

    Порядок работы:
    1. Если calibration_root содержит main_timeline.csv — читает свежий
       результат Stage 1 (формат run_calibration.py).
    2. Иначе запускает Stage 1 pipeline на calibration_dataset/photos/
       и возвращает результат.

    🚨 Если веса моделей (net_recon.pth, retinaface_*.pth) отсутствуют —
    вызывает FileNotFoundError с инструкцией по установке.
    """
    log_status("load_calibration", "complete")
    root = calibration_root

    # ✅ Свежий результат Stage 1 (предварительный прогон run_calibration.py)
    if (root / "main_timeline.csv").is_file():
        records = load_main(root)
        for record in records:
            record.dataset_id = "same_day_calibration"
            record.date = None
        if not records:
            raise FileNotFoundError(f"no valid Stage-1 calibration records under {root}")
        return records

    # 🔥 Запуск Stage 1 на сырых фото из calibration_dataset/photos/
    photos_dir = root / "photos"
    if not photos_dir.is_dir():
        raise FileNotFoundError(
            f"каталог сырых фото не найден: {photos_dir}. "
            "Ожидается структура: calibration_dataset/photos/person_*/frame_*.jpg"
        )

    # Проверка наличия весов моделей
    assets_dir = root.parent / "assets"
    required_weights = [
        "net_recon.pth", "large_base_net.pth",
        "retinaface_resnet50_2020-07-20_old_torch.pth",
        "similarity_Lm3D_all.mat",
    ]
    missing_weights = [w for w in required_weights if not (assets_dir / w).is_file()]
    if missing_weights:
        raise FileNotFoundError(
            f"отсутствуют веса моделей Stage 1: {missing_weights}. "
            f"Скопируйте их в {assets_dir} или выполните:\n"
            f"  python app6/scripts/fetch_external_assets.py\n"
            f"После установки весов запустите калибровку:\n"
            f"  python app6/run_calibration.py --input {photos_dir} --output runs/calibration_stage1"
        )

    # Запуск Stage 1 pipeline
    from app6.stage1.config import Stage1Config
    from app6.stage1.engine import Stage1Engine

    output_dir = root / "runs" / "calibration_stage1"
    cfg = Stage1Config(
        project_root=root.parent,
        input_dir=photos_dir,
        output_dir=output_dir,
        device="auto",
        overwrite=True,
    )
    engine = Stage1Engine(cfg)

    photos = sorted(
        p for p in photos_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")
        and not p.name.startswith("._")
    )
    if not photos:
        raise FileNotFoundError(f"нет фото в {photos_dir}")

    for path in photos:
        try:
            engine._one(path)
        except Exception as e:
            log_status("load_calibration", f"warn: {path.name}: {e}")

    # Чтение свежего результата
    if not (output_dir / "main_timeline.csv").is_file():
        raise FileNotFoundError(
            f"Stage 1 не создал main_timeline.csv в {output_dir}. "
            f"Проверьте логи выше."
        )
    records = load_main(output_dir)
    for record in records:
        record.dataset_id = "same_day_calibration"
        record.date = None
    return records
