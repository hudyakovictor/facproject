"""🎚 Вычитание углового шума из метрик пары по калибровочному набору.

Подключает к API уже реализованный, но НИКЕМ не вызываемый механизм
`app6/stage2/angle_noise.py`. До этого `subtract_angle_noise` и
`build_calibration_pair_index` использовались только в тестах: ключевая идея
ТЗ — «по данным калибровочной пары шум можно вычесть из данных сравнения
основной пары» — не влияла ни на API, ни на графики.

Принцип: калибровочный набор содержит кадры ОДНОГО человека. Расхождение
между двумя его кадрами при известной разнице углов и есть оценка шума,
вызванного разницей ракурса. Для пары основного анализа подбирается
калибровочная пара с близкой Δуглов, и её расхождение вычитается.

🚨 WARNING: компенсация УМЕНЬШАЕТ наблюдаемое расхождение. Поэтому модуль
всегда возвращает и сырое, и компенсированное значение вместе с признаком
`uncompensated` и описанием подобранной пары. Тихая подмена числа
недопустима: «после компенсации расхождение упало» может означать не
отсутствие аномалии, а неудачный подбор калибровочной пары.

📤 API: build_noise_index(), apply_noise_subtraction(), noise_coverage_report()
"""
from __future__ import annotations

import threading
from typing import Any

from app6.stage2.angle_noise import (
    ANGLE_NOISE_SCHEMA,
    COMPENSABLE_METRICS,
    DEFAULT_TOLERANCE,
    angle_delta,
    build_calibration_pair_index,
    subtract_angle_noise,
)

NOISE_CALIBRATION_SCHEMA = "deeputin-api-noise-calibration-v1.0"

#: Построение индекса перебирает пары кадров и вызывает compare_landmarks —
#: это дорого, поэтому результат кэшируется на процесс.
_lock = threading.Lock()
_index_cache: dict[str, list[dict[str, Any]]] = {}


def build_noise_index(cache_key: str = "demo") -> list[dict[str, Any]]:
    """🏭 FACTORY → Индекс калибровочных пар (кэшируется на процесс).

    В demo-режиме источником «одного и того же человека» служат кадры одного
    carrier: `build_demo_records` порождает их из одного alpha_id, поэтому
    расхождение внутри carrier — это в точности шум метода, а не различие
    личностей.
    """
    with _lock:
        cached = _index_cache.get(cache_key)
        if cached is not None:
            return cached

        from app6.stage2.core import compare_landmarks

        from .demo_data import build_demo_records, build_demo_zone_maps

        photos = build_demo_records()
        zone106, zone134 = build_demo_zone_maps(photos)

        # 🎯 КРИТИЧНО: `build_calibration_pair_index` группирует кадры по
        # `record.dataset_id`, считая их одним человеком. В демо-наборе ВСЕ
        # записи имеют dataset_id="demo_subject", хотя порождены тремя разными
        # carrier'ами (разные alpha_id = разные «лица»). Без подмены
        # идентификатора в «шум одного человека» попали бы пары разных людей:
        # оценка шума оказалась бы завышенной, а вычитание замаскировало бы
        # настоящие расхождения — прямо противоположно цели калибровки.
        from dataclasses import replace as _replace

        records = [
            _replace(photo.record, dataset_id=f"carrier_{photo.carrier}")
            for photo in photos
        ]
        index = build_calibration_pair_index(
            records, compare_landmarks, zone106, zone134, max_pairs_per_group=40)
        _index_cache[cache_key] = index
        return index


def resolve_tolerance(raw: dict[str, Any] | None) -> dict[str, float]:
    """🚧 GATE → Допуски подбора с валидацией.

    Отрицательный или нечисловой допуск молча заменяется значением по
    умолчанию: подбор с отрицательным допуском не нашёл бы ни одной пары и
    выглядел бы как «калибровки нет».
    """
    tolerance = dict(DEFAULT_TOLERANCE)
    for axis in ("yaw", "pitch", "roll"):
        value = (raw or {}).get(axis)
        try:
            parsed = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if parsed >= 0 and parsed == parsed:
            tolerance[axis] = parsed
    return tolerance


def apply_noise_subtraction(
    metrics: dict[str, float],
    angles_a: Any,
    angles_b: Any,
    pose_bin: str | None,
    *,
    tolerance: dict[str, float] | None = None,
    cache_key: str = "demo",
    exclude_records: tuple[str | None, str | None] = (None, None),
) -> dict[str, Any]:
    """📊 METRIC → Вычесть угловой шум из метрик одной пары.

    Returns:
        Блок с сырыми и компенсированными значениями, оценкой шума и
        описанием подобранной калибровочной пары. При отсутствии подходящей
        пары `uncompensated=True` и указана причина — компенсация НЕ
        применяется, а не подменяется нулём.
    """
    tol = resolve_tolerance(tolerance)
    index = build_noise_index(cache_key)

    # 🚧 GATE → Исключение самоподбора (leakage). Если анализируемая пара сама
    # присутствует в калибровочном индексе, из наблюдаемого вычтется оно же и
    # компенсированное значение окажется ровно 0 — круговая логика, выдающая
    # «идеальное совпадение». В штатной конфигурации калибровочный и основной
    # наборы физически разделены (`app6/AGENTS.md`), но в demo-режиме индекс
    # строится из тех же кадров, поэтому защита обязательна.
    excluded = {r for r in exclude_records if r}
    if excluded:
        index = [
            pair for pair in index
            if not ({pair.get("record_a"), pair.get("record_b")} & excluded)
        ]

    payload: dict[str, Any] = {
        **{k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))},
        "angles_a": list(angles_a),
        "angles_b": list(angles_b),
        "pose_bin": pose_bin,
    }
    result = subtract_angle_noise(payload, index, tol)

    compensated: dict[str, dict[str, float | None]] = {}
    for metric in COMPENSABLE_METRICS:
        if metric not in metrics:
            continue
        raw_value = float(metrics[metric])
        compensated[metric] = {
            "raw": raw_value,
            "noise": result.get(f"{metric}_angle_noise"),
            "compensated": result.get(f"{metric}_angle_compensated"),
        }

    # Полная компенсация (расхождение схлопнулось в ноль) почти всегда
    # означает не отсутствие различий, а вырожденный подбор. Помечаем явно.
    suspicious = any(
        entry["compensated"] is not None and entry["raw"] > 0
        and float(entry["compensated"]) <= 1e-9
        for entry in compensated.values()
    )

    return {
        "schema": NOISE_CALIBRATION_SCHEMA,
        "angle_noise_schema": ANGLE_NOISE_SCHEMA,
        "degenerate_match": suspicious,
        "tolerance": tol,
        "angle_delta": result.get("angle_delta"),
        "uncompensated": bool(result.get("angle_noise_uncompensated", True)),
        "reason": result.get("angle_noise_reason") or "",
        "match": result.get("angle_noise_match"),
        "metrics": compensated,
        "index_size": len(index),
        "not_a_verdict": True,
        "note": (
            "Компенсация уменьшает наблюдаемое расхождение. Сырое значение "
            "сохраняется рядом: падение после компенсации не является "
            "доказательством отсутствия аномалии."
        ),
    }


def noise_coverage_report(
    pairs: list[tuple[dict[str, float], Any, Any, str | None]],
    *,
    tolerance: dict[str, float] | None = None,
    cache_key: str = "demo",
) -> dict[str, Any]:
    """📤 Покрытие компенсации по набору пар: для скольких шум удалось вычесть.

    Без этого показателя переключатель «сырые/компенсированные» вводит в
    заблуждение: пользователь не знает, к какой доле данных компенсация
    вообще применилась.
    """
    tol = resolve_tolerance(tolerance)
    total = len(pairs)
    covered = 0
    reasons: dict[str, int] = {}
    deltas: list[float] = []

    for metrics, angles_a, angles_b, pose_bin in pairs:
        outcome = apply_noise_subtraction(
            metrics, angles_a, angles_b, pose_bin, tolerance=tol, cache_key=cache_key)
        if outcome["uncompensated"]:
            reason = outcome["reason"] or "неизвестная причина"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        covered += 1
        entry = outcome["metrics"].get("ldm134_rmse")
        if entry and entry.get("raw") is not None and entry.get("compensated") is not None:
            deltas.append(float(entry["raw"]) - float(entry["compensated"]))

    return {
        "schema": NOISE_CALIBRATION_SCHEMA,
        "tolerance": tol,
        "pair_count": total,
        "compensated_count": covered,
        "coverage": (covered / total) if total else None,
        "uncompensated_reasons": reasons,
        "median_noise_removed": (
            sorted(deltas)[len(deltas) // 2] if deltas else None
        ),
        "not_a_verdict": True,
    }


def angle_delta_for(angles_a: Any, angles_b: Any) -> dict[str, float]:
    """🔍 QUERY → Разница углов пары (обёртка для API)."""
    return angle_delta(angles_a, angles_b)
