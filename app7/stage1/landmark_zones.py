"""Landmark → zone mapping with bone/skin stability classification.

Maps each of 106 and 134 landmarks to its anatomical A20 zone and
stability class (bone/skin/mixed). This is needed for Stage 2 weighted
comparison — bone-adjacent landmarks are far more stable for identity.

The mapping is computed from the atlas (per-triangle zone assignment)
and the landmark vertex indices in the BFM mesh.
"""

from __future__ import annotations

import numpy as np
from pathlib import Path

# 21 face zone stability: bone (stable) vs skin (mobile) vs mixed
ZONE_STABILITY = (
    "bone",   # A01 forehead_upper
    "bone",   # A02 forehead_lower
    "bone",   # A03 glabella
    "bone",   # A04 nose_bridge
    "mixed",  # A05 nose_tip (cartilage)
    "skin",   # A06 nose_ala_left
    "skin",   # A07 nose_ala_right
    "bone",   # A08 orbit_left
    "bone",   # A09 orbit_right
    "bone",   # A10 zygomatic_left
    "bone",   # A11 zygomatic_right
    "skin",   # A12 cheek_left
    "skin",   # A13 cheek_right
    "skin",   # A14 mouth_upper
    "skin",   # A15 mouth_lower
    "bone",   # A16 chin
    "bone",   # A17 jaw_left
    "bone",   # A18 jaw_right
    "bone",   # A19 temple_left
    "bone",   # A20 temple_right
)

ZONE_NAMES = (
    "forehead_upper", "forehead_lower", "glabella", "nose_bridge",
    "nose_tip", "nose_ala_left", "nose_ala_right",
    "orbit_left", "orbit_right", "zygomatic_left", "zygomatic_right",
    "cheek_left", "cheek_right", "mouth_upper", "mouth_lower",
    "chin", "jaw_left", "jaw_right", "temple_left", "temple_right",
)

BONE_ZONE_IDS = [i for i, s in enumerate(ZONE_STABILITY) if s == "bone"]
SKIN_ZONE_IDS = [i for i, s in enumerate(ZONE_STABILITY) if s == "skin"]
MIXED_ZONE_IDS = [i for i, s in enumerate(ZONE_STABILITY) if s == "mixed"]

# Expression-sensitive zones that should be excluded/downweighted
# when expression is non-neutral
EXPRESSION_SENSITIVE_ZONES = {5, 6, 13, 14, 11, 12}  # nose ala, mouth, cheeks


def compute_landmark_zones(
    ldm_vertex_indices: np.ndarray,
    triangles: np.ndarray,
    atlas_zone_a20: np.ndarray,
) -> dict:
    """Map each landmark to its A20 zone via the atlas.

    Args:
        ldm_vertex_indices: (L,) landmark vertex indices in BFM mesh
        triangles: (F, 3) triangle vertex indices
        atlas_zone_a20: (F,) zone id per triangle from atlas

    Returns:
        dict with per-landmark zone assignment and stability class
    """
    ldm_indices = np.asarray(ldm_vertex_indices, np.int64)
    tri = np.asarray(triangles, np.int64)
    zones_tri = np.asarray(atlas_zone_a20, np.int64)

    # Build vertex → triangles mapping
    n_verts = int(tri.max()) + 1
    vert_to_tris = [[] for _ in range(n_verts)]
    for ti in range(len(tri)):
        for vi in tri[ti]:
            vert_to_tris[int(vi)].append(ti)

    landmark_zones = []
    for li, vi in enumerate(ldm_indices):
        vi = int(vi)
        if vi < 0 or vi >= n_verts or not vert_to_tris[vi]:
            landmark_zones.append({
                "landmark_id": li,
                "zone_id": -1,
                "zone_name": "unknown",
                "stability": "unknown",
            })
            continue

        # Majority zone among adjacent triangles
        tri_zones = [int(zones_tri[ti]) for ti in vert_to_tris[vi] if ti < len(zones_tri)]
        if not tri_zones:
            landmark_zones.append({
                "landmark_id": li,
                "zone_id": -1,
                "zone_name": "unknown",
                "stability": "unknown",
            })
            continue

        zone_id = int(max(set(tri_zones), key=tri_zones.count))
        zone_id = min(zone_id, 19)  # clamp to valid range
        stability = ZONE_STABILITY[zone_id] if zone_id < 20 else "unknown"
        name = ZONE_NAMES[zone_id] if zone_id < 20 else "unknown"

        landmark_zones.append({
            "landmark_id": li,
            "zone_id": zone_id,
            "zone_name": name,
            "stability": stability,
        })

    return {
        "landmarks": landmark_zones,
        "n_bone": sum(1 for lz in landmark_zones if lz["stability"] == "bone"),
        "n_skin": sum(1 for lz in landmark_zones if lz["stability"] == "skin"),
        "n_mixed": sum(1 for lz in landmark_zones if lz["stability"] == "mixed"),
        "bone_landmark_ids": [lz["landmark_id"] for lz in landmark_zones if lz["stability"] == "bone"],
        "skin_landmark_ids": [lz["landmark_id"] for lz in landmark_zones if lz["stability"] == "skin"],
    }


def landmark_zone_weights(zones: dict, expression_label: str = "neutral") -> np.ndarray:
    """Compute per-landmark weight based on zone stability and expression.

    Bone landmarks: weight 1.0
    Mixed landmarks: weight 0.7
    Skin landmarks: weight 0.4
    Expression-sensitive zones: weight 0.1 if expression != neutral
    """
    weights = np.ones(len(zones["landmarks"]), np.float32)
    for lz in zones["landmarks"]:
        li = lz["landmark_id"]
        if lz["stability"] == "bone":
            weights[li] = 1.0
        elif lz["stability"] == "mixed":
            weights[li] = 0.7
        elif lz["stability"] == "skin":
            weights[li] = 0.4
        else:
            weights[li] = 0.2

        # Down-weight expression-sensitive zones
        if expression_label != "neutral" and lz["zone_id"] in EXPRESSION_SENSITIVE_ZONES:
            weights[li] *= 0.15

    return weights
