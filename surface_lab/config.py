from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class LabConfig:
    uv_size: int = 1000
    super_sample: int = 2
    probability_threshold: float = 0.50
    min_component_px: int = 18
    min_patch_coverage: float = 0.45
    confidence_threshold: float = 0.40
    patch_radius: float = 0.34
    ffhq_input_size: int = 512
    # First-pass FFHQ should see the whole visible face, not the forensic skin-only mask.
    # skin_only can be re-enabled later for texture metrics, not for initial wrinkle QA.
    analysis_region: str = "full_face"  # full_face | skin_only
    # Optional pre-processing before FFHQ inference.  This is experimental and
    # is saved separately for visual QA; it does not modify original images.
    detail_mode: str = "none"  # none | gentle | strong | clahe

# Anchor targets are expressed in normalized canonical mesh coordinates.
PATCH_TARGETS = {
    "forehead_center": (0.00, 0.63, 0.38),
    "forehead_left": (-0.38, 0.58, 0.34),
    "forehead_right": (0.38, 0.58, 0.34),
    "crow_feet_left": (-0.58, 0.14, 0.28),
    "crow_feet_right": (0.58, 0.14, 0.28),
    "under_eye_left": (-0.34, 0.02, 0.42),
    "under_eye_right": (0.34, 0.02, 0.42),
    "nasolabial_left": (-0.29, -0.25, 0.48),
    "nasolabial_right": (0.29, -0.25, 0.48),
}
