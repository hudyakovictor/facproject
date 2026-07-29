"""📊 METRIC → Публичный контроль множественных сравнений (Benjamini-Hochberg).

ТЗ п.9 требует публичную процедуру BH с уровнем FDR ≤ 0.05. Внутри
`multiple_testing.py` уже была корректная, но приватная реализация `_bh_qvalues`
с порогом 0.10 (дефект D7). Этот модуль даёт стабильный публичный API и
нормативный уровень 0.05, не ломая существующих вызовов.

🚨 WARNING: результат BH — диагностический фильтр, а не вердикт о личности.
Значимая по FDR пара означает «расхождение не объясняется случайностью при
данных допущениях», а не «другой человек» (см. AGENTS.md).
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np

FDR_SCHEMA: Final[str] = "deeputin-fdr-control-v1.0"

#: Нормативный уровень ложных обнаружений по ТЗ п.9.
DEFAULT_FDR_LEVEL: Final[float] = 0.05


def benjamini_hochberg(
    p_values: np.ndarray | list[float],
    fdr_level: float = DEFAULT_FDR_LEVEL,
) -> tuple[np.ndarray, np.ndarray]:
    """📊 METRIC → Поправка Benjamini-Hochberg на множественные сравнения.

    Реализует восходящую процедуру BH: p-значения сортируются, каждое умножается
    на `m/rank`, затем применяется обратная кумулятивная минимизация, чтобы
    итоговые q-значения были монотонны по p.

    Args:
        p_values: массив p-значений в [0, 1]. Нефинитные значения не допускаются.
        fdr_level: целевой уровень FDR, по умолчанию 0.05.

    Returns:
        `(adjusted, significant)` — q-значения в исходном порядке и булев массив
        `q <= fdr_level`.

    Raises:
        ValueError: p-значения вне [0, 1], нефинитные, либо недопустимый уровень.

    Examples:
        >>> q, sig = benjamini_hochberg([0.001, 0.001, 0.9])
        >>> bool(sig[0]), bool(sig[2])
        (True, False)
    """
    arr = np.asarray(p_values, dtype=np.float64).reshape(-1)
    if not 0.0 < float(fdr_level) <= 1.0:
        raise ValueError(f"fdr_level должен быть в (0,1], получено {fdr_level}")
    if arr.size == 0:
        return np.empty(0, np.float64), np.empty(0, bool)
    if not np.isfinite(arr).all():
        raise ValueError("p-значения содержат NaN/Inf; отсутствие теста не равно p=1")
    if (arr < 0.0).any() or (arr > 1.0).any():
        raise ValueError("p-значения должны лежать в [0, 1]")

    m = arr.size
    order = np.argsort(arr, kind="stable")
    ranked = arr[order]
    scaled = ranked * m / np.arange(1, m + 1, dtype=np.float64)
    # Обратная кумулятивная минимизация обеспечивает монотонность q по p.
    monotone = np.minimum.accumulate(scaled[::-1])[::-1]
    adjusted = np.empty(m, np.float64)
    adjusted[order] = np.clip(monotone, 0.0, 1.0)
    return adjusted, adjusted <= float(fdr_level)


def apply_fdr(
    rows: list[dict[str, Any]],
    *,
    p_key: str = "mt_p_approx",
    q_key: str = "fdr_adjusted_p",
    flag_key: str = "fdr_significant",
    fdr_level: float = DEFAULT_FDR_LEVEL,
) -> dict[str, Any]:
    """📊 METRIC → Применить BH к строкам с p-значениями, записав результат на месте.

    Строки без пригодного p-значения не участвуют в процедуре и получают статус
    `not_tested`: подстановка p=1 исказила бы знаменатель m.
    """
    indexed: list[tuple[int, float]] = []
    for i, row in enumerate(rows):
        raw = row.get(p_key)
        if raw is None:
            row[flag_key] = False
            row["fdr_status"] = "not_tested"
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            row[flag_key] = False
            row["fdr_status"] = "not_tested"
            continue
        if not np.isfinite(value) or not 0.0 <= value <= 1.0:
            row[flag_key] = False
            row["fdr_status"] = "not_tested"
            continue
        indexed.append((i, value))

    if not indexed:
        return {"schema": FDR_SCHEMA, "fdr_level": float(fdr_level), "test_count": 0,
                "significant_count": 0, "diagnostic_only": True,
                "method": "Benjamini-Hochberg", "note": "нет пригодных p-значений"}

    positions = [i for i, _ in indexed]
    adjusted, significant = benjamini_hochberg([p for _, p in indexed], fdr_level)
    for slot, position in enumerate(positions):
        rows[position][q_key] = float(adjusted[slot])
        rows[position][flag_key] = bool(significant[slot])
        rows[position]["fdr_status"] = "tested"

    return {"schema": FDR_SCHEMA, "fdr_level": float(fdr_level), "test_count": len(positions),
            "significant_count": int(significant.sum()), "diagnostic_only": True,
            "not_a_verdict": True, "method": "Benjamini-Hochberg step-up",
            "note": "значимость по FDR — основание для проверки, не вывод о личности"}
