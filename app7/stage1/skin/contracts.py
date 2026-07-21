"""Schemas, evidence states, and constants for the skin sub-package."""

from __future__ import annotations

from enum import Enum


# Schema version strings embedded into every output artifact
SCHEMAS = {
    "surface": "skin-surface-v1",
    "atlas": "skin-atlas-v1",
    "quality": "skin-quality-v1",
    "features": "skin-features-v1",
    "wrinkles": "skin-wrinkles-v1",
    "pair": "skin-pair-v1",
}


class EvidenceState(str, Enum):
    USABLE = "usable"
    COARSE_ONLY = "coarse_only"
    NOT_MEASURABLE = "not_measurable"
    NOT_OBSERVED = "not_observed"


class ReasonCode(str, Enum):
    SELF_OCCLUDED = "self_occluded"
    PROJECTION_UNSTABLE = "projection_unstable"
    HIGH_INCIDENCE_ANGLE = "high_incidence_angle"
    EXCESSIVE_BLUR = "excessive_blur"
    EXCESSIVE_NOISE = "excessive_noise"
    JPEG_DAMAGE = "jpeg_damage"
    SPECULAR_CONTAMINATION = "specular_contamination"
    DEEP_SHADOW = "deep_shadow"
    LOW_EFFECTIVE_RESOLUTION = "low_effective_resolution"


class PairStatus(str, Enum):
    PARTIAL_MATCH = "partial_match"
    COARSE_DIRECTION_MATCH = "coarse_direction_match"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_COMPARABLE = "not_comparable"


class Applicability:
    """Structured applicability record for one evidence family."""

    def __init__(self, family: str, state: EvidenceState, support: float,
                 reasons: tuple[str, ...], base: dict):
        self.family = family
        self.state = state
        self.support = support
        self.reasons = reasons
        self.base = base

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "state": self.state.value,
            "effective_support": self.support,
            "reasons": list(self.reasons),
            **self.base,
        }


FAMILIES = (
    "geometry", "macro_texture", "meso_texture", "micro_texture",
    "wrinkles", "pigmentation", "material_optics", "local_feature_matching",
)
