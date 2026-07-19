"""uv_module v3 -- high-detail forensic UV texture generation for 3DDFA_V3.

Drop-in module expected by DEEPUTIN app/stage1/assets.py:

    from uv_module import HDUVConfig, HDUVTextureGenerator

Outputs two textures per photo:
- analytic (`analysis`): real photo pixels only, mathematically untouched,
  for skin analytics (LBP/GLCM/skan);
- morph (`beauty`): symmetric completion of hidden areas, for 3D morphing.

Skin analysis architecture (v3.3):
- UV-SPACE: Frangi ridges + skan skeleton graph (geometry, pose-invariant)
- IMAGE-SPACE: LBP/GLCM/Gabor on original photo (texture, sensor-accurate)
- Combined via SkinAnalyzer.analyze_full()
"""
from .calibration import calibrate, load_profile, load_records
from .chronology import analyze_records, load_stage1_records, match_branches
from .config import HDUVConfig, MAX_UV_SIZE
from .generator import HDUVTextureGenerator, enhance_texture_details
from .metrics import texture_detail_report, wrinkle_graph_features
from .rasterizer import UVRaster, build_uv_raster, interpolate_vertex_attribute, load_or_build_uv_raster
from .skin_analysis import SkinAnalyzer, SkinAnalysisResult
from .symmetry import symmetric_fill
from .visibility import VisibilityBundle, compute_visibility
from .zones import POSE_POLICY, ZONE_SPECS, policy_weight, zone_vertex_masks

__all__ = [
    "HDUVConfig",
    "HDUVTextureGenerator",
    "MAX_UV_SIZE",
    "SkinAnalyzer",
    "SkinAnalysisResult",
    "UVRaster",
    "VisibilityBundle",
    "build_uv_raster",
    "calibrate",
    "compute_visibility",
    "enhance_texture_details",
    "interpolate_vertex_attribute",
    "load_or_build_uv_raster",
    "load_profile",
    "load_records",
    "load_stage1_records",
    "analyze_records",
    "match_branches",
    "POSE_POLICY",
    "ZONE_SPECS",
    "policy_weight",
    "symmetric_fill",
    "texture_detail_report",
    "wrinkle_graph_features",
    "zone_vertex_masks",
]

__version__ = "3.3.0"
