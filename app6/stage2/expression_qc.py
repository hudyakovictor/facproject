"""🚧 GATE → Динамическое исключение мимических зон (ТЗ п.2).

При улыбке или открытом рте мягкие ткани деформируются на величину, сравнимую
с межличностными различиями. Такие зоны нельзя взвешивать наравне с костными:
их изменение говорит о выражении лица, а не о геометрии черепа.

Модуль обнуляет вес мимических зон, когда выражение превышает порог, и никогда
не трогает костные структуры (глазницы, переносица, скулы, подбородок, виски).

🚨 WARNING: детекция ведётся по 106 ландмаркам в нормализованном object-space.
Пороги подобраны как безразмерные отношения к межзрачковому расстоянию, что
делает их устойчивыми к масштабу, но они остаются эвристикой и требуют
пересчёта на калибровке перед сильными утверждениями.
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np

EXPRESSION_QC_SCHEMA: Final[str] = "deeputin-expression-qc-v1.0"

#: Пороги в долях межзрачкового расстояния.
DEFAULT_THRESHOLDS: Final[dict[str, float]] = {
    "smile": 0.92,      # ширина рта / межзрачковое расстояние
    "jaw_open": 0.28,   # раскрытие рта / межзрачковое расстояние
}

#: Мимические зоны mesh-атласа: деформируются выражением.
MIMIC_ZONES: Final[frozenset[str]] = frozenset({
    "cheek_soft_L", "cheek_soft_R",
    "nose_wing_L", "nose_wing_R",
    "jaw_L", "jaw_R",
})

#: Костные зоны: не зависят от выражения, вес сохраняется всегда.
BONE_ZONES: Final[frozenset[str]] = frozenset({
    "orbit_L", "orbit_R", "nose_bridge_tip", "brow_ridge_L", "brow_ridge_R",
    "cheekbone_L", "cheekbone_R", "chin", "forehead", "temporal_L", "temporal_R",
    "jaw_angle_L", "jaw_angle_R",
    "ligament_orbital_L", "ligament_orbital_R",
    "ligament_zygomatic_L", "ligament_zygomatic_R",
})

# Индексы 106-точечной схемы 3DDFA_V3.
_EYE_LEFT: Final[int] = 74
_EYE_RIGHT: Final[int] = 77
_MOUTH_LEFT: Final[int] = 84
_MOUTH_RIGHT: Final[int] = 90
_MOUTH_UPPER: Final[int] = 87
_MOUTH_LOWER: Final[int] = 93


def _interocular(landmarks: np.ndarray) -> float:
    """Межзрачковое расстояние как масштабный инвариант кадра."""
    distance = float(np.linalg.norm(landmarks[_EYE_LEFT] - landmarks[_EYE_RIGHT]))
    if not np.isfinite(distance) or distance < 1e-9:
        raise ValueError("вырожденное межзрачковое расстояние: масштаб не определён")
    return distance


def expression_magnitude(landmarks: np.ndarray) -> dict[str, float]:
    """📊 METRIC → Безразмерные показатели улыбки и раскрытия рта.

    Args:
        landmarks: массив (106, 3) в согласованном пространстве.

    Returns:
        `smile`, `jaw_open` и `magnitude` — максимум относительного превышения.

    Raises:
        ValueError: неверная форма массива, нефинитные точки или нулевой масштаб.
    """
    pts = np.asarray(landmarks, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[0] < 106 or pts.shape[1] != 3:
        raise ValueError(f"ожидается массив (106,3), получено {pts.shape}")
    if not np.isfinite(pts[[_EYE_LEFT, _EYE_RIGHT, _MOUTH_LEFT, _MOUTH_RIGHT,
                            _MOUTH_UPPER, _MOUTH_LOWER]]).all():
        raise ValueError("ключевые точки выражения содержат NaN/Inf")

    scale = _interocular(pts)
    smile = float(np.linalg.norm(pts[_MOUTH_LEFT] - pts[_MOUTH_RIGHT])) / scale
    jaw_open = float(np.linalg.norm(pts[_MOUTH_UPPER] - pts[_MOUTH_LOWER])) / scale
    return {"smile": smile, "jaw_open": jaw_open,
            "magnitude": max(smile / DEFAULT_THRESHOLDS["smile"],
                             jaw_open / DEFAULT_THRESHOLDS["jaw_open"])}


def detect_expression(landmarks: np.ndarray,
                      thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    """🚧 GATE → Определить, превышает ли выражение допустимые пороги."""
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    measures = expression_magnitude(landmarks)
    smiling = measures["smile"] > limits["smile"]
    jaw_open = measures["jaw_open"] > limits["jaw_open"]
    return {"schema": EXPRESSION_QC_SCHEMA, **measures,
            "smile_detected": bool(smiling), "jaw_open_detected": bool(jaw_open),
            "expression_active": bool(smiling or jaw_open),
            "thresholds": limits}


def exclude_mimic_zones(
    landmarks: np.ndarray,
    zone_weights: dict[str, float],
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """🚧 GATE → Обнулить веса мимических зон при выраженной мимике (ТЗ п.2).

    Костные зоны не затрагиваются никогда: при активной мимике вес анализа
    полностью переносится на структуры, не зависящие от выражения.

    Args:
        landmarks: (106, 3) ландмарки кадра.
        zone_weights: исходные веса зон mesh-атласа.
        thresholds: пороги детекции; по умолчанию `DEFAULT_THRESHOLDS`.

    Returns:
        `{"zone_weights": ..., "expression": ..., "excluded_zones": [...]}`.

    Raises:
        ValueError: некорректные ландмарки или отрицательные веса.
    """
    if any(float(w) < 0 for w in zone_weights.values()):
        raise ValueError("веса зон не могут быть отрицательными")

    expression = detect_expression(landmarks, thresholds)
    adjusted = dict(zone_weights)
    excluded: list[str] = []

    if expression["expression_active"]:
        for zone in list(adjusted):
            if zone in MIMIC_ZONES:
                adjusted[zone] = 0.0
                excluded.append(zone)

    return {"schema": EXPRESSION_QC_SCHEMA,
            "zone_weights": adjusted,
            "expression": expression,
            "excluded_zones": sorted(excluded),
            "bone_zones_preserved": sorted(z for z in adjusted if z in BONE_ZONES),
            "policy": "mimic zones zeroed; bone zones never modified"}
