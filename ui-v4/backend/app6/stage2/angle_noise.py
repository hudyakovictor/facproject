"""📊 METRIC → Дифференциальное вычитание углового шума калибровки (ТЗ п.1).

Аудит измерил утечку позы на 3789 парах одного человека: корреляция между
`pose_distance` и `ldm134_rmse` равна 0.463, а медианный RMSE растёт с 0.0046
до 0.0122 (в 2.6 раза) при увеличении разницы углов. То есть часть расхождения
в анализируемой паре объясняется не различием лиц, а различием ракурсов.

Идея: для пары (A, B) найти в калибровочном наборе пару кадров **одного и того
же** человека с близкой разницей углов. Расхождение такой пары — это чистый
угловой шум при заданной геометрии съёмки. Вычитаем его из наблюдаемого.

🚨 WARNING: компенсация не может сделать несопоставимые позы сопоставимыми.
Если подходящей калибровочной пары нет, выставляется `angle_noise_uncompensated`
и метрика остаётся сырой — молчаливая подстановка нуля запрещена (AGENTS.md).
"""
from __future__ import annotations

from typing import Any, Final, Sequence

import numpy as np

ANGLE_NOISE_SCHEMA: Final[str] = "deeputin-angle-noise-subtraction-v1.0"

#: Допуски подбора калибровочной пары по ТЗ: ±2° yaw, ±1° pitch/roll.
DEFAULT_TOLERANCE: Final[dict[str, float]] = {"yaw": 2.0, "pitch": 1.0, "roll": 1.0}

#: Метрики, для которых вычитание углового шума осмысленно (расстояния, не углы).
COMPENSABLE_METRICS: Final[tuple[str, ...]] = (
    "ldm106_rmse", "ldm106_median", "ldm106_p95",
    "ldm134_rmse", "ldm134_median", "ldm134_p95",
    "identity_only_ldm134_rmse",
)


def angle_delta(angles_a: Sequence[float], angles_b: Sequence[float]) -> dict[str, float]:
    """🔢 Абсолютная разница углов пары в порядке (pitch, yaw, roll).

    Raises:
        ValueError: если вектор углов не содержит ровно три компоненты.
    """
    a = np.asarray(angles_a, dtype=np.float64).reshape(-1)
    b = np.asarray(angles_b, dtype=np.float64).reshape(-1)
    if a.size != 3 or b.size != 3:
        raise ValueError("ожидается три угла (pitch, yaw, roll)")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("углы содержат NaN/Inf")
    return {"pitch": abs(float(a[0] - b[0])),
            "yaw": abs(float(a[1] - b[1])),
            "roll": abs(float(a[2] - b[2]))}


def find_matching_calibration_pair(
    target_delta: dict[str, float],
    calibration_pairs: Sequence[dict[str, Any]],
    tolerance: dict[str, float] | None = None,
    pose_bin: str | None = None,
) -> dict[str, Any] | None:
    """🔍 QUERY → Калибровочная пара того же человека с близкой разницей углов.

    Кандидаты фильтруются по допускам и, при указании, по совпадению ракурса;
    среди прошедших выбирается ближайший по евклидову расстоянию в пространстве
    (Δyaw, Δpitch, Δroll).

    Returns:
        Ближайшая пара или None, если ни одна не укладывается в допуски.
    """
    tol = {**DEFAULT_TOLERANCE, **(tolerance or {})}
    best: dict[str, Any] | None = None
    best_distance = float("inf")

    for pair in calibration_pairs:
        if pose_bin is not None and pair.get("pose_bin") != pose_bin:
            continue
        delta = pair.get("delta") or {}
        if any(abs(float(delta.get(axis, 1e9)) - float(target_delta.get(axis, 0.0))) > tol[axis]
               for axis in ("yaw", "pitch", "roll")):
            continue
        distance = float(np.sqrt(sum(
            (float(delta.get(axis, 0.0)) - float(target_delta.get(axis, 0.0))) ** 2
            for axis in ("yaw", "pitch", "roll"))))
        if distance < best_distance:
            best_distance, best = distance, {**pair, "match_distance": distance}
    return best


def subtract_angle_noise(
    pair_metrics: dict[str, Any],
    calibration_pairs: Sequence[dict[str, Any]],
    tolerance: dict[str, float] | None = None,
) -> dict[str, Any]:
    """📊 METRIC → Вычесть угловой шум калибровки из метрик пары (ТЗ п.1).

    Args:
        pair_metrics: должен содержать `angles_a`, `angles_b` и измеренные метрики.
        calibration_pairs: пары одного человека с полями `delta`, `metrics`, `pose_bin`.
        tolerance: допуски подбора; по умолчанию ±2° yaw, ±1° pitch/roll.

    Returns:
        Копия `pair_metrics` с полями `*_angle_compensated`, `angle_delta`,
        флагом `angle_noise_uncompensated` и описанием подобранной пары.

    Raises:
        KeyError: отсутствуют углы пары.
    """
    if "angles_a" not in pair_metrics or "angles_b" not in pair_metrics:
        raise KeyError("pair_metrics должен содержать angles_a и angles_b")

    out = dict(pair_metrics)
    delta = angle_delta(pair_metrics["angles_a"], pair_metrics["angles_b"])
    out["angle_delta"] = delta
    out["angle_noise_schema"] = ANGLE_NOISE_SCHEMA

    match = find_matching_calibration_pair(
        delta, calibration_pairs, tolerance, pose_bin=pair_metrics.get("pose_bin"))

    if match is None:
        out["angle_noise_uncompensated"] = True
        out["angle_noise_reason"] = "нет калибровочной пары в допусках по углам"
        out["angle_noise_match"] = None
        return out

    reference = match.get("metrics") or {}
    out["angle_noise_uncompensated"] = False
    out["angle_noise_reason"] = ""
    out["angle_noise_match"] = {
        "dataset_id": match.get("dataset_id"),
        "record_a": match.get("record_a"),
        "record_b": match.get("record_b"),
        "delta": match.get("delta"),
        "match_distance": match.get("match_distance"),
    }

    for metric in COMPENSABLE_METRICS:
        observed = pair_metrics.get(metric)
        noise = reference.get(metric)
        if observed is None or noise is None:
            continue
        try:
            observed_f, noise_f = float(observed), float(noise)
        except (TypeError, ValueError):
            continue
        if not (np.isfinite(observed_f) and np.isfinite(noise_f)):
            continue
        # Расхождение не может стать отрицательным: угловой шум объясняет
        # часть наблюдаемого, но не более чем всё наблюдаемое.
        out[f"{metric}_angle_compensated"] = float(max(0.0, observed_f - noise_f))
        out[f"{metric}_angle_noise"] = noise_f
    return out


def build_calibration_pair_index(
    records: Sequence[Any],
    compare_fn: Any,
    zone106: np.ndarray,
    zone134: np.ndarray,
    *,
    max_pairs_per_group: int = 40,
) -> list[dict[str, Any]]:
    """🏭 FACTORY → Индекс калибровочных пар одного человека с их угловым шумом.

    Для каждой персоны и ракурса берутся пары кадров; их расхождение и есть
    оценка шума при данной разнице углов, поскольку человек тот же.
    """
    from collections import defaultdict

    grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for record in records:
        grouped[(record.dataset_id, record.pose_bin)].append(record)

    index: list[dict[str, Any]] = []
    for (dataset_id, pose_bin), group in grouped.items():
        group = sorted(group, key=lambda r: (r.sequence, r.record_id))
        emitted = 0
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if emitted >= max_pairs_per_group:
                    break
                a, b = group[i], group[j]
                comparison = compare_fn(a, b, zone106, zone134)
                if comparison.status != "measured":
                    continue
                index.append({
                    "dataset_id": dataset_id, "pose_bin": pose_bin,
                    "record_a": a.record_id, "record_b": b.record_id,
                    "delta": angle_delta(a.angles, b.angles),
                    "metrics": dict(comparison.metrics),
                })
                emitted += 1
            if emitted >= max_pairs_per_group:
                break
    return index
