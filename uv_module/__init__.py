"""Forensic UV Core v4: projection, visibility, provenance and morph completion only."""
from .config import MAX_UV_SIZE, UVExtractionConfig, MorphCompletionConfig
from .generator import UVGenerator, UVResult, HDUVTextureGenerator, normalize_skin_mask
from .preview import provenance_preview, save_uv_result

# Compatibility alias. New code should use UVExtractionConfig.
HDUVConfig = UVExtractionConfig

class SkinAnalyzer:
    """Compatibility boundary: skin analytics were intentionally removed."""
    def __init__(self, cfg=None): self.cfg = cfg
    def analyze_uv_geometry(self, *args, **kwargs):
        return {"available": False, "reason": "skin analysis moved outside uv_module", "zones": {}}

__all__=["MAX_UV_SIZE","UVExtractionConfig","MorphCompletionConfig","UVGenerator","UVResult","HDUVConfig","HDUVTextureGenerator","SkinAnalyzer","normalize_skin_mask","provenance_preview","save_uv_result"]
