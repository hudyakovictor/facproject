"""Texture forensics for skin consistency analysis (v3.3).

Unified entry point that combines UV-geometry and image-texture analysis.
The old version only called texture_detail_report(); this version uses
SkinAnalyzer for comprehensive two-space forensic analysis.
"""
from __future__ import annotations
import json
import numpy as np
import cv2
from pathlib import Path
from typing import Any

from .metrics import texture_detail_report
from .skin_analysis import SkinAnalyzer


def extract_texture_forensics(
    analysis_bgr: np.ndarray,
    observed_mask: np.ndarray,
    output_dir: Path,
    original_bgr: np.ndarray | None = None,
    skin_mask: np.ndarray | None = None,
    pose_bin: str = "frontal",
    cfg: Any = None,
) -> tuple[dict, Path]:
    """Extract forensic quality metrics from the analytic UV texture.

    When original_bgr and skin_mask are provided, also runs image-space
    texture analysis for a comprehensive two-space forensic report.
    """
    gray = cv2.cvtColor(analysis_bgr, cv2.COLOR_BGR2GRAY)
    metrics = texture_detail_report(gray, observed_mask)

    report: dict[str, Any] = {
        "schema": "forensic_v2",
        "uv_metrics": metrics,
        "observed_pixels": int(np.sum(observed_mask)),
    }

    # Extended: two-space analysis if original image is provided
    if original_bgr is not None and skin_mask is not None:
        analyzer = SkinAnalyzer(cfg)
        uv_result = analyzer.analyze_uv_geometry(analysis_bgr, observed_mask, pose_bin)
        img_result = analyzer.analyze_image_texture(original_bgr, skin_mask, pose_bin)
        report["uv_geometry"] = uv_result
        report["image_texture"] = img_result
        report["two_space_available"] = True
    else:
        report["two_space_available"] = False

    report_path = output_dir / "texture_forensics.json"
    # Sanitize numpy types for JSON
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [sanitize(x) for x in obj]
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return sanitize(obj.tolist())
        return obj

    report_path.write_text(json.dumps(sanitize(report), indent=2, ensure_ascii=False))

    return report, report_path
