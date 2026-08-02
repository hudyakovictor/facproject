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
from typing import Any, Final, Sequence

import numpy as np

IRREVERSIBLE_RETURN_SCHEMA: Final[str] = "deeputin-irreversible-return-v1.0"

#: Минимальный разрыв между возвращающимися состояниями (ТЗ: N > 5 лет).
DEFAULT_MIN_YEARS: Final[float] = 5.0

#: Порог сходства форм, при котором состояния считаются совпадающими.
DEFAULT_SIMILARITY: Final[float] = 0.95

#: Во сколько раз промежуточное состояние должно отличаться от возвращающихся.
DEFAULT_DIVERGENCE_RATIO: Final[float] = 2.0
DEFAULT_MIN_MID_DIVERGENCE: Final[float] = 0.03


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


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
) -> list[dict[str, Any]]:
    """📊 METRIC → Найти возвраты формы A→B→A во временной шкале (ТЗ п.4).

    Точка временной шкалы: `{"date": "YYYY-MM-DD", "shape": [...], "photo_id": ...}`.
    Тройка (i, j, k) считается аномалией, когда:
      1. состояния i и k сходны выше `similarity_threshold`;
      2. промежуточное j отличается от обоих минимум в `divergence_ratio` раз
         (в терминах расхождения 1 - similarity);
      3. между i и k прошло не менее `min_years` лет.

    Args:
        timeline: точки шкалы,必 содержащие `date` и `shape`.
        similarity_threshold: порог совпадения форм.
        min_years: минимальный разрыв в годах между i и k.
        divergence_ratio: во сколько раз B должно отличаться от A.

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

    points: list[dict[str, Any]] = []
    for item in timeline:
        parsed = _parse_date(item.get("date"))
        shape = item.get("shape")
        if parsed is None or shape is None:
            continue
        vector = np.asarray(shape, dtype=np.float64).reshape(-1)
        if vector.size == 0 or not np.isfinite(vector).all():
            continue
        points.append({**item, "_date": parsed, "_shape": vector})

    if len(points) < 3:
        return []
    points.sort(key=lambda p: p["_date"])

    anomalies: list[dict[str, Any]] = []
    for i in range(len(points)):
        for k in range(i + 2, len(points)):
            gap_years = (points[k]["_date"] - points[i]["_date"]).days / 365.25
            if gap_years < min_years:
                continue
            sim_ik = _similarity(points[i]["_shape"], points[k]["_shape"])
            if sim_ik < similarity_threshold:
                continue
            divergence_ik = 1.0 - sim_ik
            for j in range(i + 1, k):
                sim_ij = _similarity(points[i]["_shape"], points[j]["_shape"])
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
                    "date_a": points[i]["_date"].isoformat(),
                    "date_b": points[j]["_date"].isoformat(),
                    "date_a_return": points[k]["_date"].isoformat(),
                    "year_a": points[i]["_date"].year,
                    "year_b": points[j]["_date"].year,
                    "year_a_return": points[k]["_date"].year,
                    "gap_years": round(gap_years, 2),
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
