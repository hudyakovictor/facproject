"""Texture forensics for skin consistency analysis."""
from __future__ import annotations
import json
import numpy as np
import cv2
from pathlib import Path
from .metrics import texture_detail_report

def extract_texture_forensics(analysis_bgr: np.ndarray, observed_mask: np.ndarray, output_dir: Path) -> tuple[dict, Path]:
    """Extract forensic quality metrics from the analytic UV texture."""
    gray = cv2.cvtColor(analysis_bgr, cv2.COLOR_BGR2GRAY)
    metrics = texture_detail_report(gray, observed_mask)
    
    report = {
        "schema": "forensic_v1",
        "metrics": metrics,
        "observed_pixels": int(np.sum(observed_mask)),
    }
    
    report_path = output_dir / "texture_forensics.json"
    report_path.write_text(json.dumps(report, indent=2))
    
    return report, report_path
