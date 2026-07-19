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

v3.2 changes vs v3 (seam + border fixes):
- Mirror fill uses **multi-band Laplacian pyramid blending** instead of a single
  distance-transform feather, so the symmetry seam becomes invisible on side-lit
  poses (the v3 box feather produced a "cord" along the central nasal ridge).
- LAB color match of the mirrored side is computed in **per-strip** bands along
  the seam instead of globally across the bilateral overlap, so directional
  lighting gradients (one half in shadow, one in light) don't average out.
- Residual holes use **Navier-Stokes inpainting** instead of TELEA (TELEA smears
  along isophote direction and amplifies the seam on profile shots).
- Enhancement is computed on the **super-sampled** buffer and downsampled with
  INTER_AREA, so micro-wrinkles / pores survive the SS→final collapse (v3 did
  detail injection on the already-downsampled atlas).
- `observed_erode_px` is now applied in **super-sample space** (consistent
  footprint across super_sample settings) and is wider by default.
- View-aware downsample: invalid/out-of-frame texels are masked **before**
  INTER_AREA so Lanczos ringing at the atlas border never bleeds into skin.
- `observed_threshold` is tighter (0.55) to drop the half-coverage texels that
  produced the ragged fringe on frontal poses.
- `analyze_skin_wrinkles` runs Frangi on a normalised-but-not-quotient image
  (the v3 Retinex-style `gray / blur_large` collapsed pore-scale contrast), and
  uses a per-region percentile-based threshold (frontal vs profile).
- Visibility: depth tolerance is scaled by texel coverage fraction, so
  sliver-thin near-side triangles no longer occlude legitimate far-side
  vertices on profile shots.
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
    super_sample: int = 3                   # UPGRADED: higher sampling grid for better detail
    enable_delighting: bool = False         # experimental SH de-lighting (OFF for evidence textures)
    force_all_triangles_visible: bool = False
    device: str = "cpu"                     # kept for interface compatibility; module is CPU-only

    # --- sampling ---
    interpolation: str = "lanczos4"         # lanczos4 | cubic | linear
    # --- visibility ---
    zbuffer_size: int = 1024                # UPGRADED: higher resolution for cleaner masks
    depth_tolerance: float = 0.015          # fraction of face depth range
    angle_soft_lo: float = 0.05             # n_z where angle weight starts rising from 0
    angle_soft_hi: float = 0.45             # UPGRADED: more generous angle for profile shots
    observed_threshold: float = 0.55         # v3.2: tighter (was 0.4) -- drop half-coverage fringe texels
    observed_erode_px: int = 2               # in SUPER-SAMPLE space (3x3 kernel at S_ss); applied before downsample
    # --- optional source-space skin mask (recon["skin_mask"]) ---
    use_skin_mask: bool = True              # if recon provides it, gate visibility with it
    skin_mask_threshold: float = 0.3        # UPGRADED: more inclusive skin mask
    # --- morph texture (symmetric synthesis) ---
    mirror_fill: bool = True
    mirror_color_match: bool = True         # LAB median/std match of mirrored half in the bilateral overlap
    mirror_strip_count: int = 5             # v3.2: per-seam-strip LAB match bins (parallel to u=0.5)
    seam_feather_px: int = 24               # legacy single-feather fallback (ignored when mb_blend_levels>=2)
    mb_blend_levels: int = 5                # v3.2: Laplacian pyramid levels for multi-band mirror blend
    mb_blend_sigma: float = 0.36            # v3.2: spatial band sigma for pyramid alpha masks (0..1 of half-width)
    inpaint_remaining: bool = True          # NS for texels not covered by either side
    inpaint_radius: int = 6
    inpaint_method: str = "ns"              # "ns" | "telea" -- v3.2 default Navier-Stokes
    detail_enhance: bool = True             # morph-only mild sharpening + CLAHE (NEVER applied to analysis)
    detail_blend: float = 0.65              # UPGRADED: stronger enhancement for visual clarity
    detail_clahe_clip: float = 3.5          # UPGRADED: higher contrast for micro-wrinkles
    detail_sigma: float = 1.0               # UPGRADED: tighter focus for sharpening
    detail_apply_on_super_sample: bool = True  # v3.2: enhance at SS grid then downsample with INTER_AREA
    detail_paid_only_synthetic: bool = True # v3.2: don't boost across the observed/synthetic seam (would amplify it)
    detail_seam_band_px: int = 28           # v3.2: bandwidth (final-uv-space) suppressed around the seam
    background: str = "median_skin"         # median_skin | black
    # --- optional human-inspection copy of the analysis texture ---
    analysis_view: bool = True              # put an enhanced VIEW copy in aux["analysis_view"] (never for metrics)
    # --- confidence ---
    footprint_target_px: float = 0.8        # UPGRADED: more sensitive to low-res photos
    # --- forensic wrinkle analysis ---
    wrinkle_sigmas: tuple = (0.4, 0.8, 1.2, 1.6)
    wrinkle_threshold_percentile: float = 82.0   # lower than v3's 85 to keep more pore-scale ridges
    wrinkle_per_region_percentile: bool = True   # split observed into seam-half strips, threshold each
    wrinkle_strip_count: int = 4                 # for per-region thresholding
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
