"""🚧 GATE → Контроль конфликтов одной даты (ТЗ п.10).

Два кадра, снятые в один день, не могут показывать разную костную структуру.
Если показывают — это сильный сигнал: либо кадры принадлежат разным людям,
либо одна из дат неверна, либо реконструкция на одном из кадров дефектна.

В отличие от эвристики в `chronology.py` (фиксированные пороги `p95>=4.5`),
здесь порог выводится из данных: расхождение сравнивается с медианой
внутридневных расхождений того же субъекта, нормированной на MAD (3σ по ТЗ).

🚨 WARNING: флаг не утверждает подмену личности. Кадры одного дня из разных
источников часто различаются оптикой, сжатием и ракурсом.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Final, Sequence

import numpy as np

SAME_DAY_SCHEMA: Final[str] = "deeputin-same-day-gate-v1.0"

#: Порог в робастных сигмах (ТЗ: > 3σ от медианы внутридневных расхождений).
DEFAULT_SIGMA_THRESHOLD: Final[float] = 3.0

#: Минимум внутридневных пар для оценки распределения.
MIN_BASELINE_PAIRS: Final[int] = 5


def _robust_scale(values: np.ndarray) -> tuple[float, float]:
    """Медиана и робастная сигма (MAD → σ) распределения."""
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, max(1.4826 * mad, 1e-9)


def check_same_day_conflict(
    daily_pairs: Sequence[dict[str, Any]],
    within_day_threshold: float = DEFAULT_SIGMA_THRESHOLD,
    *,
    metric_key: str = "ldm134_rmse",
) -> list[dict[str, Any]]:
    """🚧 GATE → Найти конфликты структуры внутри одной даты (ТЗ п.10).

    Args:
        daily_pairs: пары с полями `date_a`, `date_b`, `photo_a`, `photo_b`
            и метрикой `metric_key`. Учитываются только пары с `date_a == date_b`.
        within_day_threshold: порог в робастных сигмах.
        metric_key: имя сравниваемой метрики расхождения.

    Returns:
        Список конфликтов с `photo_id`, значением метрики и z-оценкой. Пустой
        список, если внутридневных пар меньше `MIN_BASELINE_PAIRS`: без базового
        распределения порог был бы произвольным.

    Raises:
        ValueError: недопустимый порог.
    """
    if within_day_threshold <= 0:
        raise ValueError("within_day_threshold должен быть положительным")

    same_day: list[dict[str, Any]] = []
    for pair in daily_pairs:
        date_a, date_b = pair.get("date_a"), pair.get("date_b")
        if not date_a or not date_b or str(date_a)[:10] != str(date_b)[:10]:
            continue
        try:
            value = float(pair.get(metric_key))
        except (TypeError, ValueError):
            continue
        if np.isfinite(value):
            same_day.append({**pair, "_value": value})

    if len(same_day) < MIN_BASELINE_PAIRS:
        return []

    values = np.asarray([p["_value"] for p in same_day], dtype=np.float64)
    median, sigma = _robust_scale(values)

    conflicts: list[dict[str, Any]] = []
    for pair in same_day:
        z = (pair["_value"] - median) / sigma
        if z <= float(within_day_threshold):
            continue
        conflicts.append({
            "schema": SAME_DAY_SCHEMA,
            "status": "SAME_DAY_IDENTITY_CONFLICT",
            "pair_id": pair.get("pair_id"),
            "photo_a": pair.get("photo_a"),
            "photo_b": pair.get("photo_b"),
            "date": str(pair.get("date_a"))[:10],
            "pose_bin": pair.get("pose_bin"),
            "metric": metric_key,
            "value": float(pair["_value"]),
            "within_day_median": median,
            "within_day_sigma": sigma,
            "robust_z": float(z),
            "threshold_sigma": float(within_day_threshold),
            "not_a_verdict": True,
            "alternative_explanations": [
                "неверная дата у одного из кадров",
                "разные источники: оптика, сжатие, кадрирование",
                "дефект реконструкции на одном кадре",
            ],
        })
    return conflicts


def same_day_summary(rows: Sequence[dict[str, Any]],
                     conflicts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """📤 Сводка проверки одной даты для манифеста."""
    by_date: dict[str, int] = defaultdict(int)
    for row in rows:
        a, b = row.get("date_a"), row.get("date_b")
        if a and b and str(a)[:10] == str(b)[:10]:
            by_date[str(a)[:10]] += 1
    return {"schema": SAME_DAY_SCHEMA,
            "same_day_pair_count": int(sum(by_date.values())),
            "distinct_dates": len(by_date),
            "conflict_count": len(conflicts),
            "conflict_dates": sorted({c["date"] for c in conflicts}),
            "min_baseline_pairs": MIN_BASELINE_PAIRS,
            "not_a_verdict": True}
