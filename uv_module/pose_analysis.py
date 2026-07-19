"""Pose-aware wrinkle zone analysis for forensic skin consistency."""
from __future__ import annotations
import json
import numpy as np
import cv2
from pathlib import Path
from typing import Any
from .zones import ZONE_SPECS, policy_weight
from .metrics import wrinkle_graph_features

def analyze_pose_zones(
    texture_bgr: np.ndarray,
    observed_mask: np.ndarray,
    pose_bin: str,
    vertices_canonical: np.ndarray,
    vertices_2d: np.ndarray,
    uv_coords: np.ndarray,
    triangles: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    """Analyze wrinkle patterns in anatomical zones based on pose policy."""
    
    # 1. Map vertices to zones
    u = uv_coords[:, 0]
    v = uv_coords[:, 1]
    
    zone_results = {}
    usable_zone_count = 0
    
    # We'll also produce a combined skeleton image for preview
    h, w = texture_bgr.shape[:2]
    skeleton_preview = np.zeros((h, w, 3), dtype=np.uint8)
    skeleton_preview[observed_mask] = (texture_bgr[observed_mask] * 0.3).astype(np.uint8) # Dim background
    
    for spec in ZONE_SPECS:
        weight = policy_weight(pose_bin, spec.name)
        if weight <= 0:
            continue
            
        # Extract zone mask in UV space
        umin, vmin, umax, vmax = spec.uv_box
        # Map [0,1] to pixel coords. 
        # Note: rasterizer.py uses xy[:, 1] = (1.0 - uv[:, 1]) * (size - 1)
        # So we follow that convention.
        py1, py2 = int((1.0 - vmax) * h), int((1.0 - vmin) * h)
        px1, px2 = int(umin * w), int(umax * w)
        
        # Clamp
        py1, py2 = max(0, py1), min(h, py2)
        px1, px2 = max(0, px1), min(w, px2)
        
        if py2 <= py1 or px2 <= px1:
            continue
            
        zone_tex = texture_bgr[py1:py2, px1:px2]
        zone_mask = observed_mask[py1:py2, px1:px2]
        
        if zone_mask.sum() < 400: # Min pixels for analysis
            continue
            
        # Gray version for metrics
        zone_gray = cv2.cvtColor(zone_tex, cv2.COLOR_BGR2GRAY)
        
        # Run wrinkle analysis
        features = wrinkle_graph_features(zone_gray, zone_mask)
        
        if features.get("available") and features.get("n_branches", 0) > 0:
            zone_results[spec.name] = {
                "weight": weight,
                "features": features
            }
            usable_zone_count += 1
            
            # TODO: Add to skeleton_preview if we had the raw skeleton here.
            # Since wrinkle_graph_features doesn't return the skeleton image, 
            # we'll just mark the zone for now.
            cv2.rectangle(skeleton_preview, (px1, py1), (px2, py2), (0, 255, 0), 1)

    report = {
        "schema": "wrinkle_v2",
        "pose_bin": pose_bin,
        "usable_zone_count": usable_zone_count,
        "zones": zone_results
    }
    
    # Save reports
    (output_dir / "wrinkle_zones.json").write_text(json.dumps(report, indent=2))
    cv2.imwrite(str(output_dir / "uv_wrinkle_skeletons.png"), skeleton_preview)
    
    # Save a dummy NPZ for compliance with assets.py
    np.savez_compressed(output_dir / "wrinkle_zones.npz", report=np.array([json.dumps(report)]))
    
    return report
