"""🚧 GATE → Контроль мимики в паре.

Выражение больше не исключает пары. Все пары принимаются;
рассогласование jaw_open_detected и smile_detected записывается
в диагностические поля, но не влияет на применимость пары.

Пары выбираются по близости углов головы (pitch/yaw/roll),
а не по наличию выражения.
"""
from __future__ import annotations

from typing import Any, Final

EXPRESSION_PAIR_GATE_SCHEMA: Final[str] = "deeputin-expression-pair-gate-v2.0"

MAX_JAW_DEGREE_GAP: Final[float] = 8.0


def expression_gate(meta_a: dict[str, Any], meta_b: dict[str, Any],
                    *, era_a: str | None = None, era_b: str | None = None,
                    strict: bool = False) -> dict[str, Any]:
    """Принимает все пары; фиксирует рассогласование мимики диагностически."""
    jaw_a = bool(meta_a.get("jaw_open_detected"))
    jaw_b = bool(meta_b.get("jaw_open_detected"))
    deg_a = float(meta_a.get("jaw_open_degree") or 0.0)
    deg_b = float(meta_b.get("jaw_open_degree") or 0.0)
    smile_a = bool(meta_a.get("smile_detected"))
    smile_b = bool(meta_b.get("smile_detected"))

    gap = abs(deg_a - deg_b)
    jaw_mismatch = jaw_a != jaw_b
    smile_mismatch = smile_a != smile_b
    gap_exceeded = gap > MAX_JAW_DEGREE_GAP

    return {"schema": EXPRESSION_PAIR_GATE_SCHEMA, "accepted": True,
            "reason": "", "threshold_multiplier": 1.0,
            "jaw_mismatch": jaw_mismatch, "smile_mismatch": smile_mismatch,
            "jaw_degree_gap": gap, "jaw_degree_gap_exceeded": gap_exceeded,
            "confidence": "normal"}