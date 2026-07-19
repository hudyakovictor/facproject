"""uv_module.zones - pose-aware wrinkle zone specifications.

Defines the canonical set of facial wrinkle zones (ZONE_SPECS), the per-pose
policy weights (POSE_POLICY), and helpers to build per-zone vertex masks and to
query a single pose/zone weight.

Contract used by app6/tests/test_wrinkle_zones.py:
- ZONE_SPECS is a list of zone specs, each with a `.name` attribute.
- POSE_POLICY maps pose_bin -> {zone_name: weight in [0, 1]}.
- zone_vertex_masks(uv_coords, triangles) -> dict[zone_name, (N,) bool].
- policy_weight(pose_bin, zone_name) -> float in [0, 1].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

# Canonical pose bins (must match app6/stage1/config.py POSE_BINS).
_POSE_BINS = (
    "left_profile",
    "left_deep",
    "left_mid",
    "left_light",
    "frontal",
    "right_light",
    "right_mid",
    "right_deep",
    "right_profile",
)


@dataclass(frozen=True)
class ZoneSpec:
    name: str
    description: str
    # UV-space bounding box in [0, 1]^2 (u_min, v_min, u_max, v_max).
    uv_box: tuple[float, float, float, float]
    # Whether this zone is symmetric (present on both sides of the face).
    symmetric: bool = True


# 13 canonical wrinkle zones.
ZONE_SPECS: List[ZoneSpec] = [
    ZoneSpec("forehead_horizontal_center", "Horizontal forehead lines, central band", (0.30, 0.05, 0.70, 0.25), symmetric=False),
    ZoneSpec("forehead_horizontal_left", "Horizontal forehead lines, left band", (0.05, 0.05, 0.35, 0.25)),
    ZoneSpec("forehead_horizontal_right", "Horizontal forehead lines, right band", (0.65, 0.05, 0.95, 0.25)),
    ZoneSpec("glabella_vertical", "Vertical glabellar (frown) lines", (0.42, 0.18, 0.58, 0.40), symmetric=False),
    ZoneSpec("glabella_horizontal", "Horizontal glabellar lines", (0.38, 0.22, 0.62, 0.34), symmetric=False),
    ZoneSpec("crow_feet_left", "Left crow's feet", (0.02, 0.35, 0.22, 0.60)),
    ZoneSpec("crow_feet_right", "Right crow's feet", (0.78, 0.35, 0.98, 0.60)),
    ZoneSpec("nasolabial_left", "Left nasolabial fold", (0.30, 0.45, 0.46, 0.72)),
    ZoneSpec("nasolabial_right", "Right nasolabial fold", (0.54, 0.45, 0.70, 0.72)),
    ZoneSpec("marionette_left", "Left marionette lines", (0.34, 0.72, 0.48, 0.92)),
    ZoneSpec("marionette_right", "Right marionette lines", (0.52, 0.72, 0.66, 0.92)),
    ZoneSpec("perioral_upper", "Upper lip / smoker's lines", (0.40, 0.62, 0.60, 0.74), symmetric=False),
    ZoneSpec("perioral_lower", "Lower lip / mental crease", (0.40, 0.78, 0.60, 0.90), symmetric=False),
]

_ZONE_NAMES = [z.name for z in ZONE_SPECS]


def _policy_row(active: Iterable[str]) -> Dict[str, float]:
    """Build a full policy row: 1.0 for active zones, 0.0 otherwise."""
    active_set = set(active)
    return {name: (1.0 if name in active_set else 0.0) for name in _ZONE_NAMES}


# Per-pose policy: which zones are reliably observable / targeted per pose.
# Frontal sees central/frontal zones; profiles see the contralateral (far)
# side's crow's feet and nasolabial/marionette lines, never the near side.
POSE_POLICY: Dict[str, Dict[str, float]] = {
    "left_profile": _policy_row([
        "forehead_horizontal_center", "forehead_horizontal_left",
        "crow_feet_left", "nasolabial_left", "marionette_left",
        "perioral_upper", "perioral_lower",
    ]),
    "left_deep": _policy_row([
        "forehead_horizontal_center", "forehead_horizontal_left",
        "crow_feet_left", "nasolabial_left", "marionette_left",
        "perioral_upper", "perioral_lower",
    ]),
    "left_mid": _policy_row([
        "forehead_horizontal_center", "forehead_horizontal_left",
        "crow_feet_left", "nasolabial_left", "marionette_left",
        "perioral_upper", "perioral_lower",
    ]),
    "left_light": _policy_row([
        "forehead_horizontal_center", "forehead_horizontal_left",
        "crow_feet_left", "nasolabial_left", "marionette_left",
        "perioral_upper", "perioral_lower",
    ]),
    "frontal": _policy_row([
        "forehead_horizontal_center", "glabella_vertical", "glabella_horizontal",
        "crow_feet_left", "crow_feet_right",
        "nasolabial_left", "nasolabial_right",
        "marionette_left", "marionette_right",
        "perioral_upper", "perioral_lower",
    ]),
    "right_light": _policy_row([
        "forehead_horizontal_center", "forehead_horizontal_right",
        "crow_feet_right", "nasolabial_right", "marionette_right",
        "perioral_upper", "perioral_lower",
    ]),
    "right_mid": _policy_row([
        "forehead_horizontal_center", "forehead_horizontal_right",
        "crow_feet_right", "nasolabial_right", "marionette_right",
        "perioral_upper", "perioral_lower",
    ]),
    "right_deep": _policy_row([
        "forehead_horizontal_center", "forehead_horizontal_right",
        "crow_feet_right", "nasolabial_right", "marionette_right",
        "perioral_upper", "perioral_lower",
    ]),
    "right_profile": _policy_row([
        "forehead_horizontal_center", "forehead_horizontal_right",
        "crow_feet_right", "nasolabial_right", "marionette_right",
        "perioral_upper", "perioral_lower",
    ]),
}


def policy_weight(pose_bin: str, zone_name: str) -> float:
    """Return the policy weight for (pose_bin, zone_name); 0.0 if unknown."""
    row = POSE_POLICY.get(pose_bin)
    if row is None:
        return 0.0
    return float(row.get(zone_name, 0.0))


def zone_vertex_masks(
    uv_coords: "np.ndarray",
    triangles: "np.ndarray | None" = None,
) -> Dict[str, "np.ndarray"]:
    """Return a boolean mask per zone over the UV vertex set.

    A vertex belongs to a zone when its UV coordinate falls inside that zone's
    UV bounding box. `triangles` is accepted for interface compatibility but is
    not required for the box test.
    """
    import numpy as np

    uv = np.asarray(uv_coords, dtype=np.float32)
    if uv.ndim != 2 or uv.shape[1] < 2:
        raise ValueError("uv_coords must have shape (N, 2|3)")
    u = uv[:, 0]
    v = uv[:, 1]
    masks: Dict[str, "np.ndarray"] = {}
    for spec in ZONE_SPECS:
        umin, vmin, umax, vmax = spec.uv_box
        mask = (u >= umin) & (u <= umax) & (v >= vmin) & (v <= vmax)
        masks[spec.name] = mask
    return masks
