"""📊 METRIC → Здоровье калибровочной базы для `/api/v1/calibration/health`.

Использует реальный `calibration_dataset/all_calibration_index.csv` (943
записи, 7 персон × 9 ракурсов — см. `calibration_dataset/calibration_manifest.json`)
и переиспользует ту же проверку целостности, что и `app6/run_preflight.py`,
чтобы у API и у release-preflight не было двух расходящихся источников
истины о состоянии калибровки.

Категории уверенности корзины (invalid/low/medium/high) описаны в
`docs/техническое задание проекта/aboutplatform.txt` ("Система здоровья
калибровки"): здесь они выводятся из фактического количества независимых
персон и кадров в каждом (pose_bin) бакете — не выдумываются.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

CALIBRATION_HEALTH_SCHEMA = "deeputin-api-calibration-health-v1.0"

POSE_BINS: tuple[str, ...] = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)

#: Пороги уверенности корзины по количеству независимых людей и кадров.
#: Согласованы с `app6.stage2.robustness.MIN_REFERENCE_PERSONS` (нужно >=3
#: человек, иначе `balanced_reference` возвращает `insufficient_persons`).
MIN_PERSONS_FOR_ANY_CONFIDENCE = 3
MIN_PERSONS_FOR_MEDIUM = 5
MIN_PERSONS_FOR_HIGH = 7
MIN_FRAMES_FOR_MEDIUM = 15
MIN_FRAMES_FOR_HIGH = 40


def _bucket_confidence(person_count: int, frame_count: int) -> str:
    if person_count < MIN_PERSONS_FOR_ANY_CONFIDENCE or frame_count < 4:
        return "invalid"
    if person_count < MIN_PERSONS_FOR_MEDIUM or frame_count < MIN_FRAMES_FOR_MEDIUM:
        return "low"
    if person_count < MIN_PERSONS_FOR_HIGH or frame_count < MIN_FRAMES_FOR_HIGH:
        return "medium"
    return "high"


def load_calibration_health(calibration_root: Path) -> dict[str, Any]:
    """🚪 ENTRY POINT (программный) → Построить отчёт о здоровье калибровки.

    Raises:
        FileNotFoundError: если индекс калибровки недоступен в этом окружении.
    """
    index_path = calibration_root / "all_calibration_index.csv"
    if not index_path.is_file():
        raise FileNotFoundError(f"calibration index not found: {index_path}")

    with index_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    buckets: dict[str, dict[str, Any]] = {}
    for pose in POSE_BINS:
        pose_rows = [r for r in rows if r.get("pose_bin") == pose]
        persons = sorted({r.get("dataset_id") for r in pose_rows if r.get("dataset_id")})
        confidence = _bucket_confidence(len(persons), len(pose_rows))
        buckets[pose] = {
            "pose_bin": pose,
            "frame_count": len(pose_rows),
            "person_count": len(persons),
            "persons": persons,
            "confidence": confidence,
            "runtime_usable": confidence in ("medium", "high"),
        }

    confidence_counts = {"invalid": 0, "low": 0, "medium": 0, "high": 0}
    for bucket in buckets.values():
        confidence_counts[bucket["confidence"]] += 1

    unreliable = [b["pose_bin"] for b in buckets.values() if b["confidence"] in ("invalid", "low")]
    recommendations = []
    for pose_bin in unreliable:
        bucket = buckets[pose_bin]
        needed_persons = max(0, MIN_PERSONS_FOR_MEDIUM - bucket["person_count"])
        needed_frames = max(0, MIN_FRAMES_FOR_MEDIUM - bucket["frame_count"])
        recommendations.append({
            "pose_bin": pose_bin,
            "reason": f"confidence={bucket['confidence']}",
            "action": (
                f"добавить съёмку в ракурсе {pose_bin}: "
                f"+{needed_persons} независимых людей и/или +{needed_frames} кадров"
            ),
        })

    return {
        "schema": CALIBRATION_HEALTH_SCHEMA,
        "not_a_verdict": True,
        "total_records": len(rows),
        "total_persons": len(sorted({r.get("dataset_id") for r in rows if r.get("dataset_id")})),
        "confidence_counts": confidence_counts,
        "buckets": buckets,
        "unreliable_buckets": unreliable,
        "recommendations": recommendations,
        "source": str(index_path),
    }


CALIBRATION_MATCH_SCHEMA = "deeputin-api-calibration-match-v1.0"


def find_matching_calibration_frames(
    calibration_root: Path,
    *,
    yaw: float,
    pitch: float,
    roll: float,
    pose_bin: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """🔍 QUERY → Подобрать калибровочные кадры, ближайшие по углам к анализируемому фото.

    Реализует раздел ТЗ "к парам основного анализа подбирается пара из
    калибровочного датасета... по данным калибровочной пары различия будут
    указывать на шум из-за разницы в углах наклона головы": возвращает
    ранжированный список кандидатов по евклидову расстоянию в пространстве
    (yaw, pitch, roll), с обязательным фильтром по pose_bin, если он задан
    (сравнение поперёк ракурсов запрещено политикой проекта — см.
    `app6/AGENTS.md`, "Девять ракурсов").

    Использует ТОЛЬКО метаданные `all_calibration_index.csv` (углы, ракурс,
    идентификатор персоны) — не landmark-координаты, которые признаны
    невыровненными в `calibration_dataset/person_*/frame_*/` (см.
    `app6/stage2/loaders.load_calibration`). Список кандидатов — это только
    указание, ГДЕ искать; реальное сравнение всё равно требует Stage 1
    переизвлечения из `calibration_dataset/photos/`.

    Raises:
        FileNotFoundError: если индекс калибровки недоступен.
    """
    index_path = calibration_root / "all_calibration_index.csv"
    if not index_path.is_file():
        raise FileNotFoundError(f"calibration index not found: {index_path}")
    with index_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    candidates = [r for r in rows if pose_bin is None or r.get("pose_bin") == pose_bin]

    def _distance(row: dict[str, str]) -> float:
        try:
            dy = float(row["yaw"]) - yaw
            dp = float(row["pitch"]) - pitch
            dr = float(row["roll"]) - roll
        except (KeyError, ValueError):
            return float("inf")
        return (dy * dy + dp * dp + dr * dr) ** 0.5

    ranked = sorted(candidates, key=_distance)
    top = ranked[:limit]

    return {
        "schema": CALIBRATION_MATCH_SCHEMA,
        "not_a_verdict": True,
        "query": {"yaw": yaw, "pitch": pitch, "roll": roll, "pose_bin": pose_bin},
        "candidate_count": len(candidates),
        "candidates": [
            {
                "dataset_id": r.get("dataset_id"),
                "record_id": r.get("record_id"),
                "pose_bin": r.get("pose_bin"),
                "yaw": float(r["yaw"]), "pitch": float(r["pitch"]), "roll": float(r["roll"]),
                "angle_distance": round(_distance(r), 4),
                "source_filename": r.get("source_filename"),
            }
            for r in top
        ],
        "note": (
            "Кандидаты ранжированы только по углам позы из метаданных калибровки. "
            "Реальное численное сравнение требует переизвлечения через Stage 1 из "
            "calibration_dataset/photos/ — см. app6/stage2/loaders.load_calibration."
        ),
    }

