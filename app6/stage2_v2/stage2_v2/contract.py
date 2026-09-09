"""Stage 1 -> Stage 2 data contract (single source of truth).

This module is DECLARATIVE ONLY. It describes exactly what Stage 1 writes and
what Stage 2 is allowed to read. Nothing here imports Stage 2 logic, so the
contract can be validated standalone (CI, admin panel, preflight).

The contract is intentionally identical to the legacy Stage 1 output so that
Stage 1 does NOT have to be re-run after the Stage 2 rewrite.
"""
from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Topology (BFM / 3DDFA_V3)
# --------------------------------------------------------------------------
MESH_COUNT: Final[int] = 35709
TRIANGLE_COUNT: Final[int] = 70789
LDM106: Final[int] = 106
LDM134: Final[int] = 134
PACKBITS_LEN: Final[int] = (MESH_COUNT + 7) // 8  # 4464

# --------------------------------------------------------------------------
# Pose bins - MUST stay in sync with app6/stage1/config.py POSE_BINS
# (name, yaw_min, yaw_max, canonical_yaw)
# --------------------------------------------------------------------------
POSE_BINS: Final[tuple[tuple[str, float, float, float], ...]] = (
    ("left_profile", -95.0, -50.0, -70.0),
    ("left_deep", -50.0, -40.0, -45.0),
    ("left_mid", -40.0, -25.0, -32.5),
    ("left_light", -25.0, -10.0, -17.5),
    ("frontal", -10.0, 10.0, 0.0),
    ("right_light", 10.0, 25.0, 17.5),
    ("right_mid", 25.0, 40.0, 32.5),
    ("right_deep", 40.0, 50.0, 45.0),
    ("right_profile", 50.0, 95.000001, 70.0),
)
BIN_NAMES: Final[tuple[str, ...]] = tuple(name for name, *_ in POSE_BINS)
BIN_CANONICAL_YAW: Final[dict[str, float]] = {n: y for n, _lo, _hi, y in POSE_BINS}
PROFILE_BINS: Final[frozenset[str]] = frozenset({"left_profile", "right_profile"})

# --------------------------------------------------------------------------
# reconstruction.npz - arrays Stage 2 is allowed to consume.
# `-1` in a shape means "any length" (resolved at runtime from the file).
# --------------------------------------------------------------------------
NPZ_REQUIRED: Final[dict[str, tuple[int, ...]]] = {
    # coefficient vectors
    "alpha_id": (80,),
    "alpha_exp": (64,),
    # pose
    "angle_deg_pitch_yaw_roll": (3,),
    "rotation_matrix": (3, 3),
    "normalization_center": (3,),
    "normalization_scale": (1,),
    # landmark index maps
    "ldm106_vertex_indices": (LDM106,),
    "ldm134_vertex_indices": (LDM134,),
    # PRIMARY analysis space (see params.analysis_space)
    "ldm106_object_normalized": (LDM106, 3),
    "ldm134_object_normalized": (LDM134, 3),
    # identity-only channel (expression removed)
    "ldm106_identity_only": (LDM106, 3),
    "ldm134_identity_only": (LDM134, 3),
    # visibility
    "ldm106_visible": (LDM106,),
    "ldm134_visible": (LDM134,),
}

#: Arrays that are read only when a diagnostic channel is enabled.
NPZ_OPTIONAL: Final[dict[str, tuple[int, ...]]] = {
    "ldm106_chronology_aligned": (LDM106, 3),
    "ldm134_chronology_aligned": (LDM134, 3),
    "ldm106_bin_canonical": (LDM106, 3),
    "ldm134_bin_canonical": (LDM134, 3),
    "ldm106_front_facing": (LDM106,),
    "ldm134_front_facing": (LDM134,),
    "ldm106_renderer_visible": (LDM106,),
    "ldm134_renderer_visible": (LDM134,),
    "vertices_object_normalized": (MESH_COUNT, 3),
    "vertices_identity_only": (MESH_COUNT, 3),
    "triangles": (TRIANGLE_COUNT, 3),
    "full_mesh_visible_packbits": (PACKBITS_LEN,),
    "uv_coords": (MESH_COUNT, 2),
}

#: Coordinate spaces Stage 2 may select as the PRIMARY comparison space.
#: chronology-aligned is diagnostic only: it amplifies pose residuals.
ALLOWED_ANALYSIS_SPACES: Final[tuple[str, ...]] = (
    "raw_object_normalized",
    "bin_canonical",
)
DIAGNOSTIC_ONLY_SPACES: Final[frozenset[str]] = frozenset(
    {"chronology", "chronology_aligned"}
)

# --------------------------------------------------------------------------
# Per-photo sidecar files
# --------------------------------------------------------------------------
REQUIRED_PHOTO_FILES: Final[tuple[str, ...]] = (
    "info.json",
    "validation.json",
    "reconstruction.npz",
)
OPTIONAL_PHOTO_FILES: Final[tuple[str, ...]] = (
    "texture.json",
    "quality_zones.npz",
    "face_mask.npz",
    "uv.npz",
    "ldm106_raw.csv",
    "ldm134_raw.csv",
)

#: Root-level index written by Stage 1.
MAIN_INDEX: Final[str] = "main_timeline.csv"
MAIN_INDEX_COLUMNS: Final[tuple[str, ...]] = (
    "photo_id",
    "date",
    "same_date_sequence",
    "pose_bin",
)

#: info.json paths Stage 2 reads, as dotted lookups. Missing -> None, never 0.
INFO_FIELDS: Final[dict[str, str]] = {
    "source_relative_path": "source_relative_path",
    "source_digest": "source_digest",
    "perceptual_dhash": "perceptual_dhash",
    "near_duplicate_of": "near_duplicate_of",
    "pixels": "image.pixels",
    "alignment_quality": "chronology.alignment_quality",
    "corner_lift_ioc": "chronology.corner_lift_ioc",
    "jaw_open_ratio": "chronology.jaw_open_ratio",
    "jaw_open_degree": "chronology.jaw_open_degree",
    "smile_detected": "chronology.smile_detected",
    "jaw_open_detected": "chronology.jaw_open_detected",
    "detection_confidence": "chronology.detection_confidence",
    "face_area_ratio": "chronology.face_area_ratio",
    "coordinate_noise_sigma": "chronology.coordinate_noise_sigma",
    "reprojection_rmse": "chronology.reprojection_rmse",
    "exif_date": "date_provenance.exif_date",
    "source_claimed_date": "date_provenance.source_claimed_date",
    "date_delta_days": "date_provenance.delta_days",
    "forehead_wrinkle_supported": "quality_summary.supported_forehead_wrinkle_pose_v1",
    # Provenance conflict trail. `conflict_sources` lists which date sources
    # disagreed, which is what turns a bare delta into an explainable one.
    "conflict_sources": "date_provenance.conflict_sources",
    "source_claimed_delta_days": "date_provenance.source_claimed_delta_days",
    "source_provenance_status": "source_provenance.status",
    "source_url": "source_provenance.source_url",
    "archive_url": "source_provenance.archive_url",
    # Skin quality is a top-level field, NOT under quality_summary. This is a
    # separate channel from texture.json quality: skin scores the surface,
    # texture scores the reconstructed map. Conflating them was one of the
    # legacy gate bugs, where _record_qc read this key while the loader read
    # the other, so one gate was fed by two different sources.
    "skin_quality_score": "skin_quality_score",
    "skin_quality_status": "skin_quality_status",
}

#: texture.json -> global texture quality. Legacy Stage 2 looked for
#: `quality_summary.global_texture_quality`, which never existed, and silently
#: substituted 0.0 -> every pair became `quality_limited`. Fixed here.
TEXTURE_QUALITY_PATH: Final[str] = "quality"


def dotted(payload: dict, path: str, default=None):
    """Safe dotted lookup that never fabricates a numeric default."""
    node = payload
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def classify_pose(yaw_deg: float) -> str:
    """Return the pose bin for a yaw angle, or `out_of_supported_range`."""
    for name, lo, hi, _canon in POSE_BINS:
        if lo <= yaw_deg < hi:
            return name
    return "out_of_supported_range"
