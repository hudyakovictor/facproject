"""🚧 GATE → Достаточность общих видимых точек в паре.

Замер на калибровочном наборе (943 кадра):
  глобальное пересечение по бину — left_profile 19, right_profile 19,
  frontal 34, остальные 32–37 (порог LDM134 = 30 → профили не проходят);
  попарное пересечение — медиана 63, p05 48, минимум 40, ниже 30: 0 пар.

Вывод: гейт должен быть попарным. Глобальное пересечение отбраковывает
профили целиком без статистической на то причины.
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np

VISIBILITY_GATE_SCHEMA: Final[str] = "deeputin-visibility-gate-v1.0"

MIN_COMMON_134: Final[int] = 30
MIN_COMMON_106: Final[int] = 24

#: Доля кадров бина, в которых точка должна быть видима, чтобы войти в prior.
PRIOR_MIN_FRACTION: Final[float] = 0.60


def pair_visibility(visible_a, visible_b, *, contract: str = "ldm134") -> dict[str, Any]:
    va = np.asarray(visible_a, dtype=bool).reshape(-1)
    vb = np.asarray(visible_b, dtype=bool).reshape(-1)
    if va.shape != vb.shape:
        raise ValueError("visibility shape mismatch")
    minimum = MIN_COMMON_134 if contract == "ldm134" else MIN_COMMON_106
    mask = va & vb
    common = int(mask.sum())
    return {"schema": VISIBILITY_GATE_SCHEMA,
            "common": common, "required": minimum,
            "accepted": bool(common >= minimum),
            "reason": "" if common >= minimum else "insufficient_common_visibility",
            "mask": mask, "contract": contract}


def bin_visibility_prior(visibility_matrix) -> np.ndarray:
    """Доля кадров бина, где точка видима. Основа per-bin subset (патч 6)."""
    m = np.asarray(visibility_matrix, dtype=bool)
    if m.ndim != 2:
        raise ValueError("visibility_matrix must be 2-D (frames, points)")
    return m.mean(axis=0)


def global_intersection_is_deprecated() -> str:
    return ("глобальное пересечение видимости по бину устарело: "
            "оно даёт 19 точек в профилях против попарного минимума 40")
