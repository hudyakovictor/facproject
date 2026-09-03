"""🚧 GATE → Динамическое исключение мимических зон (ТЗ п.2).

При улыбке или открытом рте мягкие ткани деформируются на величину, сравнимую
с межличностными различиями. Такие зоны нельзя взвешивать наравне с костными:
их изменение говорит о выражении лица, а не о геометрии черепа.

ДЕТЕКЦИЯ ВЫРАЖЕНИЙ — ТОЛЬКО ГЕОМЕТРИЯ ЛАНДМАРОК (не alpha_exp).
────────────────────────────────────────────────────────────
Используются две метрики по 106-точечной схеме 3DDFA_V3:

  1. corner_lift = (avg_y(уголки_рта) - avg_y(центр_рта)) / interocular
     Положительное = уголки подняты = улыбка.
     Не зависит от ширины рта человека — измеряет ФОРМУ, а не размер.
     Порог: 0.005 (калиброван на smiletest, 100% separation).

  2. jaw_open = ||upper_lip - lower_lip|| / interocular
     Раскрытие рта. Порог: 0.28.

  alpha_exp (BFM coefficients) НЕ ИСПОЛЬЗУЕТСЯ для детекции выражений,
  так как L2-норма alpha_exp не разделяет спокойные лица и улыбки
  (см. audit: calibration_dataset/test_calibration_landmarks.py).

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

EXPRESSION_QC_SCHEMA: Final[str] = "deeputin-expression-qc-v2.0"

#: Пороги для геометрической детекции выражений по ландмаркам.
#: corner_lift = подъём уголков рта относительно центра рта / IOC.
#: jaw_open = высота рта / IOC.
#: Пороги синхронизированы с stage1/config.py и stage2/engine.py.
DEFAULT_THRESHOLDS: Final[dict[str, float]] = {
    "corner_lift": 0.005,   # подъём уголков рта / межзрачковое расстояние
    "jaw_open": 0.28,       # раскрытие рта / межзрачковое расстояние
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
        `corner_lift`, `jaw_open` и `magnitude` — макс. превышение порога.
        corner_lift > 0 = уголки подняты (улыбка).

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
    # Подъём уголков рта относительно центра рта
    mouth_center_y = (pts[_MOUTH_UPPER][1] + pts[_MOUTH_LOWER][1]) / 2.0
    corner_avg_y = (pts[_MOUTH_LEFT][1] + pts[_MOUTH_RIGHT][1]) / 2.0
    corner_lift = float((corner_avg_y - mouth_center_y) / scale)
    # Раскрытие рта
    jaw_open = float(np.linalg.norm(pts[_MOUTH_UPPER] - pts[_MOUTH_LOWER])) / scale
    return {"corner_lift": corner_lift, "jaw_open": jaw_open,
            "magnitude": max(corner_lift / DEFAULT_THRESHOLDS["corner_lift"], 0.0,
                             jaw_open / DEFAULT_THRESHOLDS["jaw_open"])}


def detect_expression(landmarks: np.ndarray,
                      thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    """🚧 GATE → Определить, превышает ли выражение допустимые пороги."""
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    measures = expression_magnitude(landmarks)
    corner_lift_active = measures["corner_lift"] > limits["corner_lift"]
    jaw_open = measures["jaw_open"] > limits["jaw_open"]
    return {"schema": EXPRESSION_QC_SCHEMA, **measures,
            "smile_detected": bool(corner_lift_active),
            "jaw_open_detected": bool(jaw_open),
            "expression_active": bool(corner_lift_active or jaw_open),
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
