"""Предварительная оценка профиля перед запуском Stage 2 + Stage 3 (Iteration 06).

Не запускает тяжёлый расчёт. Считает по уже замороженному манифесту:

- разбивку пар внутри каждого pose bin (adjacent + baseline);
- оценку общего числа пар и времени прогона (эмпирически, по числу пар);
- список блокирующих проблем (нет frozen manifest, нет Stage 1, нет калибровки);
- список предупреждений (мало фото, маленький pose bin, нулевой calibration для каких-то ракурсов);
- критерии фильтрации, которые сейчас применены.

Используется UI, чтобы пользователь увидел реалистичный масштаб работы
**до** нажатия «Рассчитать». Сама оценка дешевле оценочной секунды и не
трогает калибровку и Stage 1.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .runtime_config import RuntimePaths, load_runtime_paths

PREVIEW_SCHEMA = "deeputin-profile-preview-v1.0"

#: Порог, ниже которого выборка помечается предупреждением (слишком мало фото).
MIN_INCLUDED_WARN = 50
#: Порог для предупреждения, что в pose bin всего одна запись и сравнений не будет.
MIN_BIN_RECORDS_WARN = 3

#: Эмпирическая стоимость одной пары (секунды работы Stage 2 на типичном CPU).
#: Используется только для оценки; реальная производительность зависит от
#: железа и числа пропусков калибровки. Stage 1 manifest показал ~21 387 секунд
#: на полный датасет 1909 фото и ~525k пар — это ~0.04 сек/пара.
#: Мы закладываем 0.05 сек/пара (overhead reserve) и 30 секунд базового старта.
SECONDS_PER_PAIR = 0.05
STAGE2_STARTUP_SECONDS = 30.0
STAGE3_STARTUP_SECONDS = 20.0
STAGE3_SECONDS_PER_PAIR = 0.005


def _pairs_for_bin(count: int) -> dict[str, int]:
    """Пары внутри pose bin по политике `adjacent + baseline`.

    Бины меньше двух фото не дают ни adjacent, ни baseline пар.
    """
    adjacent = max(count - 1, 0)
    baseline = max(count - 2, 0) if count >= 3 else 0
    return {"adjacent": adjacent, "baseline": baseline, "total": adjacent + baseline}


def _photos_by_pose_bin(included_ids: list[str], photos: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    included = set(included_ids)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for photo in photos:
        photo_id = str(photo.get("id") or "")
        if photo_id in included:
            bucket = str(photo.get("bucket") or photo.get("pose_bin") or "unknown")
            buckets[bucket].append(photo)
    return buckets


def _format_human_seconds(value: float) -> str:
    """Человекочитаемая оценка времени.

    До 60 сек — секунды, до часа — минуты, до суток — часы, иначе — сутки.
    """
    if value < 0:
        return "—"
    if value < 60:
        return f"{int(round(value))} сек"
    if value < 3600:
        return f"{value / 60:.1f} мин"
    if value < 86400:
        return f"{value / 3600:.1f} ч"
    return f"{value / 86400:.1f} сут"


def _calibration_coverage_per_bin(calibration_root: Path | None) -> dict[str, int]:
    """Число калибровочных пар в каждом pose bin (для предупреждений)."""
    if calibration_root is None or not calibration_root.is_dir():
        return {}
    index_path = calibration_root / "all_calibration_index.csv"
    if not index_path.is_file():
        return {}
    counts: Counter[str] = Counter()
    try:
        with index_path.open(encoding="utf-8-sig", newline="") as handle:
            header = handle.readline().strip().lstrip("\ufeff").split(",")
            pose_idx = None
            for i, name in enumerate(header):
                if name.strip().lower() in ("pose_bin", "bucket"):
                    pose_idx = i
                    break
            if pose_idx is None:
                return {}
            for line in handle:
                parts = line.rstrip("\n").split(",")
                if pose_idx >= len(parts):
                    continue
                counts[parts[pose_idx].strip()] += 1
    except OSError:
        return {}
    return dict(counts)


def _selection_manifest_payload(profile_id: str, paths: RuntimePaths | None = None) -> tuple[Path, dict[str, Any]] | None:
    current = paths or load_runtime_paths()
    profiles_root = current.storage_root / "profiles"
    candidate = profiles_root / profile_id / "selection_manifest.json"
    if not candidate.is_file():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return candidate, payload


def _stage1_ready(paths: RuntimePaths) -> bool:
    return (paths.stage1_root / "main_timeline.csv").is_file()


def _stage1_pose_index(paths: RuntimePaths) -> list[dict[str, Any]]:
    stage1_root = paths.stage1_root
    index_path = stage1_root / "main_timeline.csv"
    if not index_path.is_file():
        return []
    photos: list[dict[str, Any]] = []
    try:
        from .stage1_timeline import build_stage1_inventory  # local import: avoids heavy boot
        inventory = build_stage1_inventory(stage1_root)
        for item in inventory.get("photos") or []:
            photos.append(item)
    except Exception:  # noqa: BLE001 - preview is best-effort, must never crash
        photos = []
    return photos


def _filter_summary(filter_state: dict[str, Any] | None) -> dict[str, Any]:
    """Краткое описание применённых фильтров в JSON для UI."""
    state = filter_state or {}
    enabled = state.get("enabled") or {}
    ranges = state.get("ranges") or {}
    booleans = state.get("booleans") or {}
    pose = state.get("poseOutlier") or {}
    keys_active = sorted([k for k, v in enabled.items() if v])
    range_active = []
    for key in keys_active:
        bounds = ranges.get(key) or {}
        lo = bounds.get("min")
        hi = bounds.get("max")
        if lo is not None or hi is not None:
            range_active.append({"metric": key, "min": lo, "max": hi})
    boolean_active = sorted([k for k, v in booleans.items() if v])
    manual_include = list(state.get("manualInclude") or [])
    manual_exclude = list(state.get("manualExclude") or [])
    return {
        "active_metrics": keys_active,
        "active_ranges": range_active,
        "active_booleans": boolean_active,
        "pose_outlier": {
            "enabled": bool(pose.get("enabled")),
            "method": pose.get("method"),
            "master_percentile": pose.get("masterPercentile"),
            "mad_multiplier": pose.get("madMultiplier"),
        },
        "manual_include_count": len(manual_include),
        "manual_exclude_count": len(manual_exclude),
    }


def build_profile_preview(
    profile_id: str,
    photos: list[dict[str, Any]] | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    """🧮 Собрать preview для профиля по frozen манифесту.

    :param profile_id: идентификатор профиля (slug).
    :param photos: уже построенный Stage 1 timeline (опционально — иначе читаем сами).
    :param paths: заменитель runtime paths (для тестов).
    """
    current = paths or load_runtime_paths()
    blockers: list[str] = []
    warnings: list[str] = []

    if not _stage1_ready(current):
        blockers.append("Stage 1 не настроен (нет main_timeline.csv) — расчёт невозможен")

    manifest_pair = _selection_manifest_payload(profile_id, current)
    if manifest_pair is None:
        blockers.append("Профиль не имеет замороженной выборки (вызовите freeze)")
    else:
        manifest_path, manifest = manifest_pair
        if manifest.get("immutable_stage1") is not True:
            blockers.append("Манифест профиля не помечен immutable_stage1")
    calibration_root = current.calibration_root if (current.calibration_root / "all_calibration_index.csv").is_file() else None
    if calibration_root is None:
        blockers.append("Калибровочный датасет недоступен (нет all_calibration_index.csv)")

    included_ids: list[str] = []
    excluded_ids: list[str] = []
    status_counts: dict[str, int] = {}
    filter_state: dict[str, Any] = {}
    selection_manifest_path: str | None = None
    if manifest_pair is not None:
        manifest_path, manifest = manifest_pair
        selection_manifest_path = str(manifest_path)
        included_ids = [str(x) for x in (manifest.get("included_ids") or []) if isinstance(x, str)]
        excluded_ids = [str(x) for x in (manifest.get("excluded_ids") or []) if isinstance(x, str)]
        status_counts = dict(manifest.get("status_counts") or {})
        filter_state = dict(manifest.get("filter_state") or {})

    if photos is None:
        photos = _stage1_pose_index(current)
    by_bin = _photos_by_pose_bin(included_ids, photos)

    pair_breakdown: list[dict[str, Any]] = []
    total_pairs = 0
    total_records = 0
    for pose_bin in sorted(by_bin.keys()):
        records = by_bin[pose_bin]
        count = len(records)
        total_records += count
        pair_counts = _pairs_for_bin(count)
        total_pairs += pair_counts["total"]
        pair_breakdown.append({
            "pose_bin": pose_bin,
            "included_count": count,
            "adjacent_pairs": pair_counts["adjacent"],
            "baseline_pairs": pair_counts["baseline"],
            "total_pairs": pair_counts["total"],
        })

    # Calibration coverage: помогает понять, какие bin получат полную компенсацию шума.
    cal_coverage = _calibration_coverage_per_bin(calibration_root)
    if cal_coverage:
        for entry in pair_breakdown:
            entry["calibration_pairs"] = int(cal_coverage.get(entry["pose_bin"], 0))

    estimated_stage2 = STAGE2_STARTUP_SECONDS + total_pairs * SECONDS_PER_PAIR
    estimated_stage3 = STAGE3_STARTUP_SECONDS + total_pairs * STAGE3_SECONDS_PER_PAIR
    estimated_total = estimated_stage2 + estimated_stage3
    estimate_notes = [
        "Оценка линейна: пары считаются по политике adjacent + baseline внутри pose bin.",
        f"Stage 2 ≈ {SECONDS_PER_PAIR:.3f} сек/пара + {STAGE2_STARTUP_SECONDS:.0f} сек старт.",
        f"Stage 3 ≈ {STAGE3_SECONDS_PER_PAIR:.4f} сек/пара + {STAGE3_STARTUP_SECONDS:.0f} сек старт.",
    ]

    # Warnings
    if total_records < MIN_INCLUDED_WARN:
        warnings.append(
            f"В выборке {total_records} фото — это меньше порога {MIN_INCLUDED_WARN} "
            "для надёжной статистики; результаты будут неустойчивыми."
        )
    sparse_bins = [entry for entry in pair_breakdown if entry["included_count"] < MIN_BIN_RECORDS_WARN]
    if sparse_bins:
        names = ", ".join(f"{e['pose_bin']} ({e['included_count']})" for e in sparse_bins)
        warnings.append(f"Разреженные bin без пар: {names}")
    if total_pairs == 0 and not blockers:
        warnings.append("Текущая выборка не образует ни одной пары для сравнения.")
    if manifest_pair is not None:
        manifest_path, manifest = manifest_pair
        locked_after_freeze = manifest.get("locked_after_freeze")
        if locked_after_freeze is True:
            warnings.append("Профиль уже заблокирован после заморозки — изменить выборку нельзя.")

    return {
        "schema": PREVIEW_SCHEMA,
        "not_a_verdict": True,
        "profile_id": profile_id,
        "selection_manifest_path": selection_manifest_path,
        "selected_at": (manifest_pair[1].get("frozen_at") if manifest_pair else None),
        "included_count": total_records,
        "excluded_count": len(excluded_ids),
        "status_counts": status_counts,
        "total_pairs": total_pairs,
        "pair_breakdown": pair_breakdown,
        "estimated_runtime": {
            "stage2_seconds": estimated_stage2,
            "stage3_seconds": estimated_stage3,
            "total_seconds": estimated_total,
            "stage2_human": _format_human_seconds(estimated_stage2),
            "stage3_human": _format_human_seconds(estimated_stage3),
            "total_human": _format_human_seconds(estimated_total),
            "notes": estimate_notes,
        },
        "filter_summary": _filter_summary(filter_state),
        "blockers": blockers,
        "warnings": warnings,
        "is_runnable": len(blockers) == 0 and total_pairs > 0,
        "calibration_root": str(calibration_root) if calibration_root else None,
        "stage1_root": str(current.stage1_root),
    }


__all__ = [
    "PREVIEW_SCHEMA",
    "build_profile_preview",
]
