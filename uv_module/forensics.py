"""Compatibility export boundary.

Skin/chronology analytics are intentionally not part of the replacement UV
module. This writer keeps the existing Stage-1 call site operational and makes
the absence explicit instead of returning fabricated wrinkle measurements.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np


def extract_texture_forensics(analysis_bgr: np.ndarray, observed_mask: np.ndarray,
                               output_dir: Path, **kwargs: Any):
    report = {
        "schema": "uv-core-only",
        "observed_pixels": int(np.asarray(observed_mask, bool).sum()),
        "uv_geometry": {"available": False, "reason": "skin analysis moved outside uv_module", "zones": {}},
        "image_texture": {"available": False, "reason": "skin analysis moved outside uv_module", "zones": {}},
        "two_space_available": False,
    }
    path = Path(output_dir) / "texture_forensics.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, path
