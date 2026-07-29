"""🏭 FACTORY → Загрузка опубликованного архива ландмарок в записи Stage 2.

Архив `selected_photos_7x9x3_data.tar.gz` содержит 188 записей (7 персон × 9
ракурсов × ~3 кадра) в плоской раскладке `person_XX__frame_YYYYYY/`. Это
единственные реальные данные в репозитории, пригодные для сценарных тестов
геометрии: фотографий и текстур в архиве нет.

Адаптер намеренно **не** изобретает недостающие данные:
  - `alpha_*` берётся из `record.npz`, если он есть, иначе остаётся NaN-вектором;
  - `date` назначается сценарием, а не выдумывается из имени кадра;
  - текстурные поля не заполняются — текстурные каналы на этих данных неприменимы.

🚨 WARNING: даты, назначаемые сценариями, синтетические. Они задают порядок
хронологии для проверки алгоритмов, но не являются датировкой съёмки.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from app6.stage2.core import Record

ARCHIVE_SCHEMA = "deeputin-test-archive-adapter-v1.0"

#: Девять нормативных ракурсов проекта.
POSE_BINS: tuple[str, ...] = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)


def _missing_alpha(count: int) -> np.ndarray:
    """NaN-вектор для недоступного alpha-канала (никогда не нули)."""
    return np.full((count,), np.nan, np.float32)


def _read_landmarks(path: Path, count: int) -> np.ndarray:
    """Прочитать `landmark_id,x,y,z` CSV в массив (count, 3)."""
    import csv

    out = np.full((count, 3), np.nan, np.float32)
    seen: set[int] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            lid = int(float(row["landmark_id"]))
            if not 0 <= lid < count:
                raise ValueError(f"landmark_id {lid} вне диапазона 0..{count - 1}: {path}")
            if lid in seen:
                raise ValueError(f"дубликат landmark_id {lid}: {path}")
            seen.add(lid)
            out[lid] = (float(row["x"]), float(row["y"]), float(row["z"]))
    missing = sorted(set(range(count)) - seen)
    if missing:
        raise ValueError(f"пропущены landmark id в {path}: {missing[:8]}")
    if not np.isfinite(out).all():
        raise ValueError(f"нефинитные координаты в {path}")
    return out


def load_archive_records(archive_root: Path) -> list[Record]:
    """🏭 FACTORY → Собрать Record-структуры из распакованного архива.

    Предпочитает `record.npz` (там есть alpha и нормализованные ландмарки);
    при его отсутствии восстанавливает геометрию из `ldm*_raw.csv` по формуле
    `object_normalized = (raw - center) / scale`, как в основном загрузчике.

    Raises:
        FileNotFoundError: если под корнем нет ни одной пригодной записи.
    """
    root = Path(archive_root)
    records: list[Record] = []
    for meta_path in sorted(root.glob("*/metadata.json")):
        directory = meta_path.parent
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        arrays = meta.get("arrays") or {}
        pose = meta.get("pose") or {}
        npz_path = directory / "record.npz"

        if npz_path.is_file():
            with np.load(npz_path, allow_pickle=False) as z:
                ldm106 = np.asarray(z["ldm106_object_norm"], np.float32)
                ldm134 = np.asarray(z["ldm134_object_norm"], np.float32)
                angles = np.asarray(z["angle_deg_pitch_yaw_roll"], np.float32).reshape(3)
                vis106 = np.asarray(z["ldm106_visible_original"], bool).reshape(-1)
                vis134 = np.asarray(z["ldm134_visible_original"], bool).reshape(-1)
                alpha_id = (np.asarray(z["alpha_id"], np.float32)
                            if "alpha_id" in z.files else _missing_alpha(80))
                alpha_exp = (np.asarray(z["alpha_exp"], np.float32)
                             if "alpha_exp" in z.files else _missing_alpha(64))
        else:
            center = np.asarray(arrays.get("object_normalization_center"), np.float64).reshape(1, 3)
            scale = float(np.asarray(arrays.get("object_normalization_scale")).reshape(-1)[0])
            if not np.isfinite(scale) or abs(scale) < 1e-12:
                raise ValueError(f"недопустимый object_normalization_scale: {directory}")
            ldm106 = ((_read_landmarks(directory / "ldm106_raw.csv", 106) - center) / scale).astype(np.float32)
            ldm134 = ((_read_landmarks(directory / "ldm134_raw.csv", 134) - center) / scale).astype(np.float32)
            angles = np.asarray(arrays.get("angle_deg_pitch_yaw_roll"), np.float32).reshape(3)
            vis106 = np.asarray(arrays.get("ldm106_visible_original"), bool).reshape(-1)
            vis134 = np.asarray(arrays.get("ldm134_visible_original"), bool).reshape(-1)
            alpha_id, alpha_exp = _missing_alpha(80), _missing_alpha(64)

        records.append(Record(
            record_id=str(meta.get("record_id") or directory.name),
            dataset_id=str(meta.get("dataset_id") or directory.name.split("__")[0]),
            date=None,
            sequence=int(meta.get("frame_index", 0)),
            pose_bin=str(meta.get("pose_bin") or "unknown"),
            angles=angles,
            ldm106=ldm106,
            ldm134=ldm134,
            visible106=vis106,
            visible134=vis134,
            alpha_id=alpha_id,
            alpha_exp=alpha_exp,
            record_dir=str(directory),
            source_group=str(meta.get("dataset_id") or "archive"),
            source_sha256=meta.get("source_sha256"),
        ))

    if not records:
        raise FileNotFoundError(f"нет пригодных записей архива под {root}")
    return records


def group_by_person_pose(records: Iterable[Record]) -> dict[tuple[str, str], list[Record]]:
    """🔍 QUERY → Сгруппировать записи по (персона, ракурс) с устойчивым порядком."""
    grouped: dict[tuple[str, str], list[Record]] = {}
    for record in records:
        grouped.setdefault((record.dataset_id, record.pose_bin), []).append(record)
    for key in grouped:
        grouped[key].sort(key=lambda r: (r.sequence, r.record_id))
    return grouped


def with_synthetic_dates(records: list[Record], start_year: int = 1999,
                         step_days: int = 400) -> list[Record]:
    """🔄 Присвоить последовательные синтетические даты для проверки хронологии.

    Даты нужны только чтобы задать порядок и интервалы: реальная датировка
    архивных кадров неизвестна. Формат ISO, совместим с `chronology._days`.
    """
    from datetime import date, timedelta

    base = date(start_year, 1, 11)
    return [replace(record, date=(base + timedelta(days=index * step_days)).isoformat())
            for index, record in enumerate(records)]


def archive_summary(records: list[Record]) -> dict[str, Any]:
    """📤 Компактная сводка состава архива для отчётов и тестов."""
    grouped = group_by_person_pose(records)
    persons = sorted({r.dataset_id for r in records})
    bins = sorted({r.pose_bin for r in records})
    return {
        "schema": ARCHIVE_SCHEMA,
        "record_count": len(records),
        "person_count": len(persons),
        "persons": persons,
        "pose_bins": bins,
        "pose_bin_count": len(bins),
        "covers_nine_bins": set(bins) == set(POSE_BINS),
        "cells": {f"{p}|{b}": len(v) for (p, b), v in sorted(grouped.items())},
        "has_alpha": bool(records and np.isfinite(records[0].alpha_id).any()),
    }
