"""Configuration for the high-detail UV texture generator (uv_module v3).

Designed for forensic use on MacBook M1 (pure numpy + OpenCV, no GPU renderer).
Source photos are expected to be <= ~800x800 px, so the UV atlas is capped at
1000x1000 -- larger sizes would only interpolate, not add real detail.

v3 changes vs v1/v2:
- The ANALYSIS texture is *never* enhanced (no CLAHE, no unsharp). v1/v2
  applied `_enhance_texture_details` to the analytic texture, which
  contaminates LBP/GLCM/skan metrics and creates a measurable dark halo at the
  observed-mask border (blur mixes black texels into the skin). Enhancement is
  now morph-only, and an optional enhanced *view* copy is exposed in `aux`.
- Sampling uses BORDER_REPLICATE (no Lanczos ringing against a black border);
  out-of-frame texels are removed by the in_frame mask instead.
- Occlusion uses per-pixel barycentric-interpolated depth instead of a
  constant-depth painter's algorithm (fewer ragged false-occlusion holes
  around the nose / brow ridge).
- `observed_erode_px` erodes the observed mask so mixed boundary texels
  (background/hair bleed averaged into edge pixels) never enter analytics.
- Optional `skin_mask` in the recon dict (HxW, from the 3DDFA_V3 segmentation
  head) removes background/hair/eye/mouth pixels at the source.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

MAX_UV_SIZE = 1000


@dataclass
class HDUVConfig:
    # --- contract fields used by app/stage1/assets.py ---
    uv_size: int = 1000                     # final atlas size, hard-capped at 1000
    super_sample: int = 2                   # sampling grid = uv_size * super_sample, then INTER_AREA
    enable_delighting: bool = False         # experimental SH de-lighting (OFF for evidence textures)
    force_all_triangles_visible: bool = False
    device: str = "cpu"                     # kept for interface compatibility; module is CPU-only

    # --- sampling ---
    interpolation: str = "lanczos4"         # lanczos4 | cubic | linear
    # --- visibility ---
    zbuffer_size: int = 768                 # raster size for self-occlusion depth test
    depth_tolerance: float = 0.015          # fraction of face depth range
    angle_soft_lo: float = 0.05             # n_z where angle weight starts rising from 0
    angle_soft_hi: float = 0.35             # n_z where angle weight saturates to 1
    observed_threshold: float = 0.5         # texel counts as "observed" above this visibility
    observed_erode_px: int = 2              # erode observed mask: drop mixed boundary texels
    # --- optional source-space skin mask (recon["skin_mask"]) ---
    use_skin_mask: bool = True              # if recon provides it, gate visibility with it
    skin_mask_threshold: float = 0.5
    # --- morph texture (symmetric synthesis) ---
    mirror_fill: bool = True
    mirror_color_match: bool = True         # LAB median/std match of mirrored half in the bilateral overlap
    seam_feather_px: int = 24               # feather band around observed/mirrored seam
    inpaint_remaining: bool = True          # TELEA for texels not covered by either side
    inpaint_radius: int = 6
    detail_enhance: bool = True             # morph-only mild sharpening + CLAHE (NEVER applied to analysis)
    detail_blend: float = 0.35              # blend weight of enhanced detail pass
    detail_clahe_clip: float = 2.2          # CLAHE clip limit
    detail_sigma: float = 1.2               # Gaussian sigma for unsharp masking
    background: str = "median_skin"         # median_skin | black
    # --- optional human-inspection copy of the analysis texture ---
    analysis_view: bool = True              # put an enhanced VIEW copy in aux["analysis_view"] (never for metrics)
    # --- confidence ---
    footprint_target_px: float = 1.0        # source image px per texel for confidence=1
    # --- cache ---
    cache_dir: str | None = None            # default: <this package>/_cache

    def __post_init__(self) -> None:
        requested = int(self.uv_size)
        if requested > MAX_UV_SIZE:
            raise ValueError(f"uv_size={requested} exceeds forensic limit {MAX_UV_SIZE}")
        if requested < 64:
            raise ValueError("uv_size must be >= 64")
        self.uv_size = requested
        self.super_sample = int(min(max(int(self.super_sample), 1), 4))

    @property
    def grid_size(self) -> int:
        return self.uv_size * self.super_sample

    def resolved_cache_dir(self) -> Path:
        if self.cache_dir:
            return Path(self.cache_dir)
        return Path(__file__).resolve().parent / "_cache"

    def public_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: (str(v) if isinstance(v, Path) else v) for k, v in d.items()}
