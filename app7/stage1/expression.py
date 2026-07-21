"""Expression detection from alpha_exp coefficients.

Classifies expression as neutral/smile/open_mouth/frown/etc. and
identifies which zones should be excluded or downweighted for
non-neutral expressions.

Uses alpha_exp (64-dim expression vector from 3DDFA_V3) which
decomposes face expression into independent components.
"""

from __future__ import annotations

import numpy as np

# Zones to exclude/downweight for each expression type
# Based on anatomical knowledge of which face regions move
EXPRESSION_ZONE_EXCLUSIONS = {
    "neutral": set(),
    "smile_closed": {5, 6, 13, 14, 11, 12},        # nose ala, mouth, cheeks
    "smile_open": {5, 6, 13, 14, 11, 12, 15},        # + chin
    "open_mouth": {5, 6, 13, 14, 15, 11, 12},         # nose ala, mouth, chin, cheeks
    "frown": {2, 0, 1},                                 # glabella, forehead
    "squint": {7, 8, 0, 1},                            # orbits, forehead
    "unknown": set(),
}


def classify_expression(alpha_exp: np.ndarray) -> dict:
    """Classify facial expression from alpha_exp vector.

    Args:
        alpha_exp: (64,) expression coefficient vector from 3DDFA_V3

    Returns:
        dict with label, confidence, magnitude, excluded_zones
    """
    alpha = np.asarray(alpha_exp, np.float64).ravel()
    if len(alpha) < 10:
        return {
            "label": "unknown",
            "confidence": 0.0,
            "magnitude": 0.0,
            "excluded_zones": list(EXPRESSION_ZONE_EXCLUSIONS["unknown"]),
        }

    magnitude = float(np.linalg.norm(alpha))

    # First 10 components capture most expression variance
    # In BFM, early components roughly correspond to:
    # 0: jaw open/close
    # 1: smile (lip corners)
    # 2: brow raise
    # 3: lip pucker
    # 4-9: finer expressions
    c = alpha[:10]

    # Detect specific expressions by component magnitudes
    jaw_open = abs(c[0]) if len(c) > 0 else 0
    smile = abs(c[1]) if len(c) > 1 else 0
    brow = abs(c[2]) if len(c) > 2 else 0

    # Thresholds (empirical, may need calibration)
    JAW_THRESH = 0.5
    SMILE_THRESH = 0.3
    BROW_THRESH = 0.4
    NEUTRAL_THRESH = 0.15

    if magnitude < NEUTRAL_THRESH:
        label = "neutral"
    elif jaw_open > JAW_THRESH and smile > SMILE_THRESH:
        label = "smile_open"
    elif smile > SMILE_THRESH:
        label = "smile_closed"
    elif jaw_open > JAW_THRESH:
        label = "open_mouth"
    elif brow > BROW_THRESH:
        label = "frown"
    else:
        label = "neutral" if magnitude < NEUTRAL_THRESH * 2 else "unknown"

    excluded = EXPRESSION_ZONE_EXCLUSIONS.get(label, set())

    # Confidence: how far from neutral
    confidence = min(1.0, magnitude / (NEUTRAL_THRESH * 5))

    return {
        "label": label,
        "confidence": confidence,
        "magnitude": magnitude,
        "jaw_component": float(c[0]) if len(c) > 0 else 0.0,
        "smile_component": float(c[1]) if len(c) > 1 else 0.0,
        "brow_component": float(c[2]) if len(c) > 2 else 0.0,
        "excluded_zones": sorted(excluded),
        "is_neutral": label == "neutral",
    }
