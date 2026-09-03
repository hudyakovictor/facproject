"""Обогащение строки пары полями патча primary-зон.

Вызывать из Stage2Engine.run() сразу перед rows.append(row).
Не зависит от _persistence.
"""
from __future__ import annotations

from typing import Any

from .primary_zones import (
    PRIMARY_HYPOTHESIS_ZONES,
    expression_zone_policy,
    pair_expression_active,
    primary_zone_aggregate,
)
from .quality_gate import compensate_quality_disparity
from .evidence import evidence_state


def enrich_pair_row(
    row: dict[str, Any],
    *,
    zones: list[dict[str, Any]],
    record_a: Any,
    record_b: Any,
    qc_a: dict[str, Any] | None = None,
    qc_b: dict[str, Any] | None = None,
    smile_a: bool = False,
    smile_b: bool = False,
    jaw_a: bool = False,
    jaw_b: bool = False,
) -> dict[str, Any]:
    """Добавить primary_zone_* / expression_* / quality_disparity в row."""
    qc_a = qc_a or {}
    qc_b = qc_b or {}
    landmarks = getattr(record_a, "ldm106", None)
    policy = expression_zone_policy(
        landmarks if landmarks is not None else None,
        smile_detected=bool(smile_a or smile_b),
        jaw_open_detected=bool(jaw_a or jaw_b),
    )
    agg = primary_zone_aggregate(zones, policy.get("zone_weights"))
    active = bool(
        (policy.get("expression") or {}).get("expression_active")
        or pair_expression_active(
            {"smile_detected": smile_a, "jaw_open_detected": jaw_a},
            {"smile_detected": smile_b, "jaw_open_detected": jaw_b},
        )
    )
    out = dict(row)
    out.update({
        "primary_zone_status": agg.get("status"),
        "primary_zone_rmse": agg.get("primary_zone_rmse"),
        "primary_zone_count": agg.get("primary_zone_count"),
        "primary_zone_names": ",".join(PRIMARY_HYPOTHESIS_ZONES),
        "expression_active": active,
        "expression_excluded_zones": ",".join(policy.get("excluded_zones") or []),
        "expression_policy": "mimic_zeroed_primary_preserved",
    })
    photo_a = str(out.get("photo_a") or getattr(record_a, "record_id", "a"))
    photo_b = str(out.get("photo_b") or getattr(record_b, "record_id", "b"))
    qlimited = bool(out.get("quality_limited") or qc_a.get("quality_limited") or qc_b.get("quality_limited"))
    out["texture_score_0_1"] = min(
        float(getattr(record_a, "quality_texture_score", 0.0) or 0.0),
        float(getattr(record_b, "quality_texture_score", 0.0) or 0.0),
    )
    out = compensate_quality_disparity(
        {**out, "photo_a": photo_a, "photo_b": photo_b},
        {
            photo_a: {
                "pixels": qc_a.get("pixels"),
                "texture_score_0_1": getattr(record_a, "quality_texture_score", 0.0),
                "quality_limited": qlimited,
            },
            photo_b: {
                "pixels": qc_b.get("pixels"),
                "texture_score_0_1": getattr(record_b, "quality_texture_score", 0.0),
                "quality_limited": qlimited,
            },
        },
    )
    if out.get("texture_conclusions_allowed") is False:
        out["quality_limited"] = True
        out["evidence_state"] = evidence_state(str(out.get("status", "")), quality_limited=True)
    return out
