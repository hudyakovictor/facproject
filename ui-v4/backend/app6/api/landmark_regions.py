"""Landmark region definitions for the Landmark Comparison widget.

Regions map landmark indices (0-based, 3DDFA_V3 schemes: 106 and 134 points)
to anatomical zones. The index ranges are the same ones used by the atlas
grouping in Stage 2 (`stage2/core.py` coordinate zones) and are kept here as a
single source of truth for UI region filters.

⚠️ These ranges describe *display grouping* for the expert widget. They do not
change any measurement or threshold in Stage 2.
"""
from __future__ import annotations

LANDMARK_REGIONS_106: dict[str, list[int]] = {
    "contour": list(range(0, 33)),
    "brows": list(range(33, 43)),
    "eyes": list(range(43, 59)),
    "nose": list(range(59, 68)),
    "mouth": list(range(68, 88)),
    "cheeks": list(range(88, 106)),
}

LANDMARK_REGIONS_134: dict[str, list[int]] = {
    "contour": list(range(0, 33)),
    "brows": list(range(33, 43)),
    "eyes": list(range(43, 59)),
    "nose": list(range(59, 68)),
    "mouth": list(range(68, 92)),
    "cheeks": list(range(92, 118)),
    "inner_contour": list(range(118, 134)),
}

REGION_LABELS: dict[str, str] = {
    "contour": "Контур лица",
    "brows": "Брови",
    "eyes": "Глаза",
    "nose": "Нос",
    "mouth": "Рот",
    "cheeks": "Щёки",
    "inner_contour": "Внутренний контур",
}


def regions_for(count: int) -> dict[str, list[int]]:
    """Region index map for the requested landmark count (106 or 134)."""
    if count == 106:
        return {name: list(indices) for name, indices in LANDMARK_REGIONS_106.items()}
    if count == 134:
        return {name: list(indices) for name, indices in LANDMARK_REGIONS_134.items()}
    raise ValueError("supported landmark counts: 106, 134")


def region_of(count: int, landmark_index: int) -> str:
    """Region name for a single landmark index."""
    for name, indices in regions_for(count).items():
        if landmark_index in indices:
            return name
    return "other"
