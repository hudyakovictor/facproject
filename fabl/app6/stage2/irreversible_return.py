"""📊 METRIC → Детекция хронологической аномалии возврата A→B→A (ТЗ п.4).

Костная геометрия черепа взрослого человека меняется медленно и монотонно.
Последовательность «форма A → форма B → снова форма A» через годы биологически
не ожидаема: кость не возвращается к прежнему состоянию. Такая картина —
основание для проверки (смена носителя, ошибка датировки, дефект реконструкции),
но не доказательство подмены личности.

🚨 WARNING: результат — флаг для ручной проверки. Модуль не утверждает, что на
кадрах разные люди (см. AGENTS.md). Возврат может объясняться освещением,
качеством съёмки или сбоем реконструкции — эти причины перечисляются в выводе.
"""
from __future__ import annotations

from datetime import date
from collections.abc import Sequence
from typing import Any, Final

import calendar

import numpy as np

IRREVERSIBLE_RETURN_SCHEMA: Final[str] = "deeputin-irreversible-return-v1.0"

#: Порог сходства НЕ откалиброван на наборе — калибровка отложена (патч 7).
SIMILARITY_CALIBRATED: Final[bool] = False

#: Минимальный разрыв между возвращающимися состояниями (ТЗ: N > 5 лет).
DEFAULT_MIN_YEARS: Final[float] = 5.0

#: Порог сходства форм, при котором состояния считаются совпадающими.
DEFAULT_SIMILARITY: Final[float] = 0.95

#: Во сколько раз промежуточное состояние должно отличаться от возвращающихся.
DEFAULT_DIVERGENCE_RATIO: Final[float] = 2.0
DEFAULT_MIN_MID_DIVERGENCE: Final[float] = 0.03

#: Максимальное окно в точках шкалы между возвращающимися состояниями.
DEFAULT_MAX_WINDOW: Final[int] = 240

#: Предварительный отсев несходных пар по кэшированной матрице сходств.
DEFAULT_PREFILTER: Final[bool] = True


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _date_bounds(point: dict[str, Any]) -> tuple[date, date] | None:
    """Ранняя и поздняя границы даты с учётом точности day/month/year.

    Консервативный разрыв считается по (ранняя граница k − поздняя граница i):
    если точность годовая, разрыв не может быть подтверждён меньше чем годом.
    """
    parsed = _parse_date(point.get("date"))
    if parsed is None:
        return None
    precision = str(point.get("date_precision") or "day").lower()
    if precision == "year":
        return date(parsed.year, 1, 1), date(parsed.year, 12, 31)
    if precision == "month":
        last = calendar.monthrange(parsed.year, parsed.month)[1]
        return date(parsed.year, parsed.month, 1), date(parsed.year, parsed.month, last)
    return parsed, parsed


def _similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Косинусная близость двух дескрипторов формы в [0, 1]."""
    x = np.asarray(a, dtype=np.float64).reshape(-1)
    y = np.asarray(b, dtype=np.float64).reshape(-1)
    if x.size != y.size or x.size == 0:
        raise ValueError("дескрипторы формы должны иметь одинаковую ненулевую длину")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("дескриптор содержит NaN/Inf")
    nx, ny = float(np.linalg.norm(x)), float(np.linalg.norm(y))
    if nx < 1e-12 or ny < 1e-12:
        raise ValueError("вырожденный дескриптор формы")
    return float(np.clip(float(x @ y) / (nx * ny), -1.0, 1.0))


def detect_irreversible_return(
    timeline: Sequence[dict[str, Any]],
    similarity_threshold: float = DEFAULT_SIMILARITY,
    *,
    min_years: float = DEFAULT_MIN_YEARS,
    divergence_ratio: float = DEFAULT_DIVERGENCE_RATIO,
    min_mid_divergence: float = DEFAULT_MIN_MID_DIVERGENCE,
    max_window: int = DEFAULT_MAX_WINDOW,
    prefilter: bool = DEFAULT_PREFILTER,
    conservative_dates: bool = True,
) -> list[dict[str, Any]]:
    """📊 METRIC → Найти возвраты формы A→B→A во временной шкале (ТЗ п.4).

    Точка временной шкалы:
    `{"date": "YYYY-MM-DD", "date_precision": "day|month|year",
      "shape": [...], "photo_id": ...}`.

    Тройка (i, j, k) считается аномалией, когда:
      1. состояния i и k сходны выше `similarity_threshold`;
      2. промежуточное j отличается от обоих минимум в `divergence_ratio` раз
         (в терминах расхождения 1 - similarity);
      3. между i и k прошло не менее `min_years` лет.

    Оптимизация (патч 7): вместо O(n³) перебора сравниваются только пары
    (i, k) в окне `max_window` точек; матрица сходств кэшируется и при
    `prefilter=True` несходные пары отсекаются без вложенного цикла по j.
    Разрыв считается консервативно: `(ранняя граница k − поздняя граница i)`,
    поэтому годовая/месячная точность не порождает ложных «длинных» разрывов.

    Args:
        timeline: точки шкалы с `date` и `shape`.
        similarity_threshold: порог совпадения форм.
        min_years: минимальный разрыв в годах между i и k.
        divergence_ratio: во сколько раз B должно отличаться от A.
        min_mid_divergence: минимальное абсолютное расхождение B.
        max_window: максимальное число точек между i и k.
        prefilter: кэшировать матрицу сходств и отсекать несходные пары.
        conservative_dates: использовать границы дат по точности.

    Returns:
        Список аномалий с годами, метриками сходства и альтернативными
        объяснениями. Пустой список при менее чем трёх пригодных точках.

    Raises:
        ValueError: недопустимые пороги.
    """
    if not 0.0 < similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold должен быть в (0, 1]")
    if min_years < 0 or divergence_ratio < 1.0 or not 0.0 < min_mid_divergence < 1.0:
        raise ValueError("недопустимые параметры возврата")
    if int(max_window) < 2:
        raise ValueError("max_window должен быть >= 2")

    points: list[dict[str, Any]] = []
    for item in timeline:
        shape = item.get("shape")
        if shape is None:
            continue
        vector = np.asarray(shape, dtype=np.float64).reshape(-1)
        if vector.size == 0 or not np.isfinite(vector).all():
            continue
        if conservative_dates:
            bounds = _date_bounds(item)
            if bounds is None:
                continue
            early, late = bounds
        else:
            parsed = _parse_date(item.get("date"))
            if parsed is None:
                continue
            early = late = parsed
        points.append({**item, "_early": early, "_late": late, "_shape": vector})

    if len(points) < 3:
        return []
    points.sort(key=lambda p: p["_late"])
    n = len(points)

    # Кэшированная матрица сходств только внутри окна max_window.
    sim = np.full((n, n), np.nan, dtype=np.float64)
    if prefilter:
        for i in range(n):
            for k in range(i + 1, min(n, i + int(max_window) + 1)):
                sim[i, k] = _similarity(points[i]["_shape"], points[k]["_shape"])

    anomalies: list[dict[str, Any]] = []
    for i in range(n):
        for k in range(i + 2, min(n, i + int(max_window) + 1)):
            gap_years = (points[k]["_early"] - points[i]["_late"]).days / 365.25
            if gap_years < min_years:
                continue
            sim_ik = float(sim[i, k])
            if np.isnan(sim_ik):
                sim_ik = _similarity(points[i]["_shape"], points[k]["_shape"])
            if sim_ik < similarity_threshold:
                continue
            divergence_ik = 1.0 - sim_ik
            for j in range(i + 1, k):
                sim_ij = float(sim[i, j])
                if np.isnan(sim_ij):
                    sim_ij = _similarity(points[i]["_shape"], points[j]["_shape"])
                sim_jk = float(sim[j, k])
                if np.isnan(sim_jk):
                    sim_jk = _similarity(points[j]["_shape"], points[k]["_shape"])
                divergence_mid = min(1.0 - sim_ij, 1.0 - sim_jk)
                # Промежуточное состояние обязано быть заметно другим, иначе это
                # просто стабильная серия, а не возврат.
                if divergence_mid < max(float(min_mid_divergence), divergence_ratio * max(divergence_ik, 1e-6)):
                    continue
                anomalies.append({
                    "schema": IRREVERSIBLE_RETURN_SCHEMA,
                    "status": "irreversible_return_anomaly",
                    "photo_a": points[i].get("photo_id"),
                    "photo_b": points[j].get("photo_id"),
                    "photo_a_return": points[k].get("photo_id"),
                    "date_a": points[i]["_late"].isoformat(),
                    "date_b": points[j]["_late"].isoformat(),
                    "date_a_return": points[k]["_late"].isoformat(),
                    "date_precision_a": str(points[i].get("date_precision") or "day"),
                    "date_precision_b": str(points[j].get("date_precision") or "day"),
                    "date_precision_a_return": str(points[k].get("date_precision") or "day"),
                    "year_a": points[i]["_late"].year,
                    "year_b": points[j]["_late"].year,
                    "year_a_return": points[k]["_late"].year,
                    "gap_years": round(gap_years, 2),
                    "conservative_dates": conservative_dates,
                    "similarity_calibrated": SIMILARITY_CALIBRATED,
                    "similarity_a_to_return": round(sim_ik, 5),
                    "similarity_a_to_b": round(sim_ij, 5),
                    "similarity_b_to_return": round(sim_jk, 5),
                    "divergence_ratio": round(divergence_mid / max(divergence_ik, 1e-6), 2),
                    "interpretation": "форма вернулась к прежнему состоянию после промежуточного",
                    "not_a_verdict": True,
                    "alternative_explanations": [
                        "различие условий съёмки или освещения",
                        "ошибка датировки одного из кадров",
                        "нестабильность реконструкции на кадре B",
                        "различие качества источников (архив vs цифра)",
                    ],
                })
                break  # одна аномалия на пару (i, k) достаточна
    return anomalies


def summarize_returns(anomalies: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """📤 Сводка найденных возвратов для манифеста прогона."""
    if not anomalies:
        return {"schema": IRREVERSIBLE_RETURN_SCHEMA, "event_count": 0,
                "years": [], "max_gap_years": 0.0, "not_a_verdict": True}
    gaps = [float(a["gap_years"]) for a in anomalies]
    return {"schema": IRREVERSIBLE_RETURN_SCHEMA, "event_count": len(anomalies),
            "years": sorted({int(a["year_b"]) for a in anomalies}),
            "max_gap_years": max(gaps), "median_gap_years": float(np.median(gaps)),
            "not_a_verdict": True,
            "note": "флаги требуют независимой проверки; это не вывод о личности"}
