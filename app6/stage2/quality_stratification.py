"""🚧 GATE → Стратификация по качеству съёмки и уверенности детектора.

Замеры на 943 кадрах:
  low-quality (laplacian/skin) медиана residual 0.00476 против 0.00232 (2.05×);
  detection_confidence < 0.70 → 0.00631 против ≥0.85 → 0.00403 (1.57×).
Единая null-модель на смешанном качестве завышает порог для чистых кадров и
занижает для грязных. Поэтому страта — часть ключа калибровки.

⚠️ ИМЯ ФАЙЛА: в репозитории уже есть `quality_gate.py` (v1.0, компенсация
дисбаланса качества источников). Этот модуль — стратификация пары, не заменяет
его.
"""
from __future__ import annotations

from typing import Any, Final

QUALITY_STRATIFICATION_SCHEMA: Final[str] = "deeputin-quality-stratification-v1.0"

DETECTION_CONFIDENCE_LOW: Final[float] = 0.50
DETECTION_CONFIDENCE_HIGH: Final[float] = 0.70
#: Минимальная доля кадра, занятая лицом. Ниже — реконструкция ненадёжна.
MIN_FACE_AREA_RATIO: Final[float] = 0.01

QUALITY_INFLATION: Final[dict[str, float]] = {"high": 1.00, "mixed": 1.45, "low": 2.05}


def _stratum(meta: dict[str, Any]) -> str:
    conf = float(meta.get("detection_confidence") or 0.0)
    skin = float(meta.get("skin_quality_score") or 0.0)
    if conf >= DETECTION_CONFIDENCE_HIGH and skin >= 0.6:
        return "high"
    if conf < DETECTION_CONFIDENCE_LOW or skin < 0.35:
        return "low"
    return "mixed"


def quality_gate(meta_a: dict[str, Any], meta_b: dict[str, Any]) -> dict[str, Any]:
    for meta in (meta_a, meta_b):
        area = float(meta.get("face_area_ratio") or 0.0)
        if area and area < MIN_FACE_AREA_RATIO:
            return {"schema": QUALITY_STRATIFICATION_SCHEMA, "accepted": False,
                    "reason": "face_too_small", "face_area_ratio": area}

    sa, sb = _stratum(meta_a), _stratum(meta_b)
    # Пара наследует худшую страту: слабое звено определяет шум.
    order = {"high": 0, "mixed": 1, "low": 2}
    stratum = sa if order[sa] >= order[sb] else sb
    return {"schema": QUALITY_STRATIFICATION_SCHEMA, "accepted": True,
            "stratum": stratum,
            "stratum_a": sa, "stratum_b": sb,
            #: Ключ калибровки: null-модель выбирается по (pose_bin, stratum).
            "calibration_key_suffix": f"::q_{stratum}",
            "threshold_multiplier": QUALITY_INFLATION[stratum],
            "confidence": "normal" if stratum == "high" else "reduced"}
