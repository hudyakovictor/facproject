"""High-detail UV texture generator v3 (drop-in `uv_module` for DEEPUTIN stage1).

Contract (used by app/stage1/assets.py):

    cfg = HDUVConfig(uv_size=1000, super_sample=2, ...)
    analysis, beauty, observed, confidence, aux = HDUVTextureGenerator(cfg).generate(bgr, recon)

- `analysis` : ANALYTIC texture (uint8 BGR). Only real pixels sampled from the
  original photo. Hidden texels are black. No synthesis, no inpainting, no
  mirroring, **no enhancement of any kind** -> safe for LBP/GLCM/skan skin
  analytics. (v1/v2 bug: CLAHE+unsharp was applied to this texture.)
- `beauty`   : MORPH texture (uint8 BGR). Analytic + symmetric completion of the
  hidden half + inpainted holes. For 3D-model morph/visual comparison ONLY.
- `observed` : (S,S) bool -- texels backed by real photo pixels (eroded by
  cfg.observed_erode_px to exclude mixed boundary texels).
- `confidence`: (S,S) float32 0..1 = angle x occlusion x in-frame x footprint
  (x skin-mask when provided).
- `aux`      : dict with `uv_is_original`, `tri_visibility`, `synthetic_mask`,
  `angle_weight`, `footprint`, `atlas_valid`, and optionally `analysis_view`
  (enhanced copy for human inspection only -- never for metrics).

recon dict keys (as produced by app/stage1/assets.py):
    vertices_2d (N,2|3) original-image coords, top-left origin, y measured
        bottom-up (3DDFA_V3 projection convention -- inverted before remap)
    vertices / vertices_3d (N,3) camera-space (used only for depth ordering)
    triangles (M,3) int, uv_coords (N,2|3) in [0,1], normals_3d (N,3) posed
    alpha_sh (27,) optional, used only when enable_delighting=True
    skin_mask (H,W) optional uint8/bool/float -- 1 where facial skin. Comes
        from the 3DDFA_V3 segmentation head; gates visibility so background,
        hair, glasses and mouth interior never enter the texture.
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Any

from skimage import filters, feature, morphology, restoration
from skan import Skeleton, summarize

try:
    from .config import HDUVConfig
    from .rasterizer import UVRaster, interpolate_vertex_attribute, load_or_build_uv_raster
    from .symmetry import symmetric_fill
    from .visibility import compute_visibility
except ImportError:
    from uv_module_v3.config import HDUVConfig
    from uv_module_v3.rasterizer import UVRaster, interpolate_vertex_attribute, load_or_build_uv_raster
    from uv_module_v3.symmetry import symmetric_fill
    from uv_module_v3.visibility import compute_visibility

_INTERP = {
    "lanczos4": cv2.INTER_LANCZOS4,
    "cubic": cv2.INTER_CUBIC,
    "linear": cv2.INTER_LINEAR,
}

# Deep3DFace / 3DDFA SH illumination constants (order-2, 9 bands).
_SH_A = np.array([np.pi, 2 * np.pi / np.sqrt(3.0), 2 * np.pi / np.sqrt(8.0)])
_SH_C = np.array([1 / np.sqrt(4 * np.pi), np.sqrt(3.0) / np.sqrt(4 * np.pi), 3 * np.sqrt(5.0) / np.sqrt(12 * np.pi)])


def _sh_basis(n: np.ndarray) -> np.ndarray:
    x, y, z = n[:, 0], n[:, 1], n[:, 2]
    a, c = _SH_A, _SH_C
    return np.stack([
        a[0] * c[0] * np.ones_like(x),
        -a[1] * c[1] * y,
        a[1] * c[1] * z,
        -a[1] * c[1] * x,
        a[2] * c[2] * x * y,
        -a[2] * c[2] * y * z,
        0.5 * a[2] * c[2] / np.sqrt(3.0) * (3 * z ** 2 - 1),
        -a[2] * c[2] * x * z,
        0.5 * a[2] * c[2] * (x ** 2 - y ** 2),
    ], axis=1)  # (N, 9)


def guided_filter(guide: np.ndarray, src: np.ndarray, radius: int, eps: float) -> np.ndarray:
    """Fast guided filter for edge-preserving smoothing/sharpening."""
    guide_f = guide.astype(np.float32) / 255.0
    src_f = src.astype(np.float32) / 255.0

    mean_I = cv2.boxFilter(guide_f, -1, (radius, radius))
    mean_p = cv2.boxFilter(src_f, -1, (radius, radius))
    mean_Ip = cv2.boxFilter(guide_f * src_f, -1, (radius, radius))
    cov_Ip = mean_Ip - mean_I * mean_p

    mean_II = cv2.boxFilter(guide_f * guide_f, -1, (radius, radius))
    var_I = mean_II - mean_I * mean_I

    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I

    mean_a = cv2.boxFilter(a, -1, (radius, radius))
    mean_b = cv2.boxFilter(b, -1, (radius, radius))

    q = mean_a * guide_f + mean_b
    return np.clip(q * 255.0, 0, 255).astype(np.uint8)


def analyze_skin_wrinkles(texture_u8: np.ndarray, mask: np.ndarray, cfg: HDUVConfig) -> dict[str, Any]:
    """Expert-level forensic wrinkle analysis using Multiscale Hessian + Skan.
    
    Complies with WRINKLE_PIPELINE_SPEC.md:
    - Multiscale analysis (sigmas)
    - Thresholding based on robust local statistics
    - Skeletonization and graph characterization via Skan
    """
    if not mask.any():
        return {"wrinkle_map": np.zeros_like(mask), "stats": {}}

    # 1. Prepare grayscale and normalize
    gray = cv2.cvtColor(texture_u8, cv2.COLOR_BGR2GRAY)
    gray_f = gray.astype(np.float32) / 255.0
    
    # Advanced local contrast normalization (Retinex-inspired)
    # This helps to equalize different lighting conditions across the chronological dataset
    blur_large = cv2.GaussianBlur(gray_f, (0, 0), 15.0)
    normalized = np.clip(gray_f / (blur_large + 1e-2), 0.5, 1.5)
    normalized = (normalized - normalized.min()) / (normalized.max() - normalized.min() + 1e-8)

    # 2. Multiscale Hessian (Frangi) for ridge detection
    # SIGMAS calibrated for 800-1000px images to detect micro-relief
    sigmas = [0.4, 0.8, 1.2, 1.6]
    ridges = filters.frangi(normalized, sigmas=sigmas, black_ridges=True)
    ridges = (ridges - ridges.min()) / (ridges.max() - ridges.min() + 1e-8)
    
    # 3. Robust adaptive thresholding
    observed_ridges = ridges[mask]
    if len(observed_ridges) > 0:
        # Use high-percentile threshold to focus on actual structural lines
        thresh = np.percentile(observed_ridges, 85)
        wrinkle_bin = (ridges > thresh) & mask
    else:
        wrinkle_bin = np.zeros_like(mask)
    
    # 4. Cleanup and Skeletonization
    # min_size depends on super_sample to maintain consistency across resolutions
    min_px = int(8 * cfg.super_sample)
    wrinkle_bin = morphology.remove_small_objects(wrinkle_bin, min_size=min_px)
    skeleton_img = morphology.skeletonize(wrinkle_bin)
    
    # 5. Graph Analysis via Skan
    stats = {}
    if skeleton_img.any():
        try:
            sk = Skeleton(skeleton_img)
            summary = summarize(sk)
            stats['branch_count'] = len(summary)
            stats['total_geodesic_length'] = float(summary['main-path-distance'].sum())
            stats['mean_ridge_strength'] = float(np.mean(ridges[skeleton_img]))
            stats['junctions'] = int(np.sum(sk.degrees > 2))
            stats['endpoints'] = int(np.sum(sk.degrees == 1))
        except Exception as e:
            stats['error'] = f"Skan analysis bypassed: {str(e)}"
    
    return {
        "wrinkle_map": (ridges * 255).astype(np.uint8),
        "wrinkle_binary": wrinkle_bin,
        "skeleton": skeleton_img,
        "stats": stats
    }


def enhance_texture_details(texture_u8: np.ndarray, mask: np.ndarray | None, cfg: HDUVConfig) -> np.ndarray:
    """Expert-level detail enhancement: High-Pass Guided Filter + Advanced CLAHE.

    v3.2 (Expert Ultra):
    - Multi-scale detail injection.
    - Guided Filter with tighter EPS for micro-detail preservation.
    - Optimized for 800-1000px source resolution.
    """
    if texture_u8.ndim != 3 or not cfg.detail_enhance:
        return texture_u8

    # Convert to LAB for luminance-only processing (preserves skin tone)
    lab = cv2.cvtColor(texture_u8, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # 1. Micro-contrast enhancement via CLAHE
    clahe = cv2.createCLAHE(clipLimit=float(cfg.detail_clahe_clip), tileGridSize=(8, 8))
    l_clahe = clahe.apply(l)

    # 2. Edge-preserving sharpening via Guided Filter on the L channel
    # Radius is tight to catch pores, EPS is small to protect edges
    radius = max(1, int(cfg.detail_sigma * 2))
    l_f = l_clahe.astype(np.float32)
    l_guide = guided_filter(l_clahe, l_clahe, radius=radius, eps=0.005)
    
    # Detail boosting
    l_detail = l_f - l_guide.astype(np.float32)
    l_sharpened = l_f + 2.0 * l_detail # Aggressive boost for visibility
    l_final = np.clip(l_sharpened, 0, 255).astype(np.uint8)

    # Reconstruct
    enhanced_lab = cv2.merge([l_final, a, b])
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # 3. Micro-texture blend back
    if cfg.detail_blend > 0:
        # We blend the L channel specifically or the whole image
        # Using whole image for softer color integration
        res = cv2.addWeighted(texture_u8, 1.0 - cfg.detail_blend, enhanced_bgr, cfg.detail_blend, 0)
    else:
        res = enhanced_bgr

    if mask is not None:
        # Seamlessly restore unobserved areas
        res[~mask] = texture_u8[~mask]
    
    return res


class HDUVTextureGenerator:
    def __init__(self, cfg: HDUVConfig | None = None):
        self.cfg = cfg or HDUVConfig()
        self._raster: UVRaster | None = None
        self._raster_key: tuple[int, int, int] | None = None

    # ------------------------------------------------------------------
    def _get_raster(self, uv_coords: np.ndarray, triangles: np.ndarray) -> UVRaster:
        key = (int(self.cfg.grid_size), int(uv_coords.shape[0]), int(triangles.shape[0]))
        if self._raster is None or self._raster_key != key:
            self._raster = load_or_build_uv_raster(
                uv_coords, triangles, self.cfg.grid_size, self.cfg.resolved_cache_dir(),
            )
            self._raster_key = key
        return self._raster

    # ------------------------------------------------------------------
    def _invert_y_for_remap(self, map_y: np.ndarray, height: int) -> np.ndarray:
        return (height - 1) - map_y

    # ------------------------------------------------------------------
    def generate(self, bgr: np.ndarray, recon: dict[str, Any]):
        cfg = self.cfg
        img = np.asarray(bgr)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        h, w = img.shape[:2]

        uv_coords = np.asarray(recon["uv_coords"], np.float32)
        triangles = np.asarray(recon["triangles"], np.int64)
        v2d = np.asarray(recon["vertices_2d"], np.float32)[:, :2]
        normals = np.asarray(recon["normals_3d"], np.float32)
        v3d = np.asarray(recon.get("vertices_3d", recon.get("vertices")), np.float32)

        raster = self._get_raster(uv_coords, triangles)
        S_ss, S = cfg.grid_size, cfg.uv_size

        vis = compute_visibility(
            vertices_2d=v2d, depth=v3d[:, 2], normals_posed=normals, triangles=triangles,
            zbuffer_size=cfg.zbuffer_size, depth_tolerance=cfg.depth_tolerance,
            angle_soft_lo=cfg.angle_soft_lo, angle_soft_hi=cfg.angle_soft_hi,
            force_all_visible=cfg.force_all_triangles_visible,
        )

        # --- per-texel inverse mapping: UV texel -> position in ORIGINAL photo ---
        pos = interpolate_vertex_attribute(raster, triangles, v2d)  # (S_ss, S_ss, 2)
        map_x = pos[..., 0].astype(np.float32)
        map_y = pos[..., 1].astype(np.float32)
        # 3DDFA projected coordinates follow a bottom-origin convention, while
        # OpenCV remap uses image rows with origin at the top. Invert Y before sampling.
        map_y = self._invert_y_for_remap(map_y, h)
        # v3: REPLICATE border -- Lanczos support never touches synthetic black
        # pixels, so no ringing/dark fringe at the frame boundary. Out-of-frame
        # texels are excluded by in_frame below instead.
        sampled_ss = cv2.remap(
            img.astype(np.float32), map_x, map_y,
            _INTERP.get(cfg.interpolation, cv2.INTER_LANCZOS4),
            borderMode=cv2.BORDER_REPLICATE,
        )

        in_frame_ss = (
            raster.valid
            & (map_x >= 0) & (map_x <= w - 1)
            & (map_y >= 0) & (map_y <= h - 1)
        )

        # --- per-texel weights ---
        angle_ss = interpolate_vertex_attribute(raster, triangles, vis.angle_weight)
        occ_ss = interpolate_vertex_attribute(raster, triangles, vis.combined.astype(np.float32))

        # --- optional source-space skin mask (background / hair / eye / mouth gate) ---
        skin_ss = None
        # Priority 1: Semantic segmentation mask from 3DDFA_V3 head
        # Priority 2: Generic skin_mask from recon dict
        skin_src = recon.get("seg_mask") if recon.get("seg_mask") is not None else recon.get("skin_mask")
        
        if cfg.use_skin_mask and skin_src is not None:
            sm = np.asarray(skin_src)
            # 3DDFA_V3 semantic classes: usually 0:bg, 1:skin, 2:eyebrow, 3:eye, 4:nose, 5:lip, 6:inner_mouth
            # For skin consistency, we strictly need class 1 (skin).
            if sm.dtype != np.float32:
                # If it's a multi-class segmentation, create a binary skin mask
                # Class 1 is typically 'skin' in 3DDFA_V3
                skin_binary = (sm == 1).astype(np.float32)
            else:
                skin_binary = sm
                
            skin_ss = cv2.remap(skin_binary, map_x, map_y, cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)

        # footprint: source-image pixels per texel (Jacobian area of the map)
        gxu = cv2.Sobel(map_x, cv2.CV_32F, 1, 0, ksize=3) / 8.0
        gxv = cv2.Sobel(map_x, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        gyu = cv2.Sobel(map_y, cv2.CV_32F, 1, 0, ksize=3) / 8.0
        gyv = cv2.Sobel(map_y, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        jac_ss = np.abs(gxu * gyv - gxv * gyu) * (cfg.super_sample ** 2)  # px per FINAL texel
        jac_ss[~raster.valid] = 0.0
        jac_ss = cv2.medianBlur(jac_ss.astype(np.float32), 3)  # kill Sobel spikes at atlas borders
        foot_ss = np.clip(jac_ss / max(cfg.footprint_target_px, 1e-6), 0.0, 1.0) ** 0.5

        # --- optional experimental SH de-lighting (never for evidence output) ---
        if cfg.enable_delighting and recon.get("alpha_sh") is not None:
            sh = np.asarray(recon["alpha_sh"], np.float32).reshape(-1)
            if sh.size >= 27:
                gamma = sh[:27].reshape(3, 9) if sh.size == 27 else sh.reshape(-1, 9)[:3]
                basis = _sh_basis(normals / (np.linalg.norm(normals, axis=1, keepdims=True) + 1e-9))
                shading_v = basis @ gamma.T  # (N, 3) RGB
                shading_v = np.clip(shading_v, 0.25, 4.0)
                shading_ss = interpolate_vertex_attribute(raster, triangles, shading_v.astype(np.float32))
                mean_sh = float(np.mean(shading_ss[raster.valid])) or 1.0
                # recon SH is RGB; image is BGR -> flip channel order
                sampled_ss = sampled_ss / np.clip(shading_ss[..., ::-1] / mean_sh, 0.25, 4.0)

        # --- downsample supersampled buffers to the final atlas size ---
        def down(a: np.ndarray) -> np.ndarray:
            if cfg.super_sample == 1:
                return a
            return cv2.resize(a, (S, S), interpolation=cv2.INTER_AREA)

        texture = np.clip(down(sampled_ss), 0, 255).astype(np.float32)
        atlas_valid = down(raster.valid.astype(np.float32)) > 0.5
        in_frame = down(in_frame_ss.astype(np.float32))
        angle_w = down(angle_ss)
        occ_w = down(occ_ss)
        footprint = down(foot_ss)

        visibility = angle_w * occ_w * in_frame
        if skin_ss is not None:
            skin_w = down(skin_ss)
            visibility = visibility * (skin_w >= cfg.skin_mask_threshold).astype(np.float32)
        observed = atlas_valid & (visibility >= cfg.observed_threshold)

        # v3: drop mixed boundary texels (background/hair averaged into edge
        # pixels by Lanczos + INTER_AREA) from the evidence mask.
        if cfg.observed_erode_px > 0:
            k = 2 * int(cfg.observed_erode_px) + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
            observed = cv2.erode(observed.astype(np.uint8), kernel).astype(bool)

        confidence = np.clip(visibility * footprint, 0.0, 1.0).astype(np.float32)
        confidence[~atlas_valid] = 0.0
        confidence[~observed] *= 0.0  # evidence confidence only where observed

        # --- ANALYTIC: real pixels only, mathematically untouched ---
        analysis_u8 = np.clip(texture, 0, 255).astype(np.uint8)
        
        # Apply strict segmentation mask filter if available
        if skin_ss is not None:
            # Downsample skin mask to match final UV size
            skin_mask_final = down(skin_ss) > cfg.skin_mask_threshold
            # Kill everything that is not skin (eyes, hair, mouth, background)
            observed = observed & skin_mask_final
            
        analysis_u8[~observed] = 0

        # --- MORPH: symmetric completion (clearly synthetic, mask returned) ---
        if cfg.mirror_fill:
            beauty_base = np.clip(texture, 0, 255).astype(np.uint8)
            beauty_u8, synthetic_mask = symmetric_fill(
                beauty_base.astype(np.float32), observed, atlas_valid,
                seam_feather_px=cfg.seam_feather_px,
                inpaint_remaining=cfg.inpaint_remaining,
                inpaint_radius=cfg.inpaint_radius,
                background=cfg.background,
                color_match=cfg.mirror_color_match,
            )
            # Enhancement is allowed only in the synthetic region.
            enhanced = enhance_texture_details(beauty_u8, synthetic_mask, cfg)
            beauty_u8[synthetic_mask] = enhanced[synthetic_mask]
        else:
            beauty_u8 = analysis_u8.copy()
            synthetic_mask = np.zeros_like(observed)

        # Key invariant: observed texels remain bitwise-identical to the analysis texture.
        beauty_u8[observed] = analysis_u8[observed]

        # --- FORENSIC SKIN ANALYSIS (v3.1 Expert) ---
        skin_analysis = analyze_skin_wrinkles(analysis_u8, observed, cfg)

        aux = {
            "uv_is_original": observed.copy(),
            "tri_visibility": vis.tri_visibility,
            "uv_synthetic_mask": synthetic_mask,
            "uv_synthetic_valid": atlas_valid & ~observed,
            "uv_synthetic_confidence": np.where(synthetic_mask, 0.25, 0.0).astype(np.float16),
            "synthetic_mask": synthetic_mask,
            "angle_weight": angle_w.astype(np.float16),
            "footprint": footprint.astype(np.float16),
            "atlas_valid": atlas_valid,
            "config": self.cfg.public_dict(),
            "wrinkle_map": skin_analysis.get("wrinkle_map"),
            "wrinkle_stats": skin_analysis.get("stats"),
            "skeleton": skin_analysis.get("skeleton"),
        }
        if cfg.analysis_view:
            # Enhanced HUMAN-INSPECTION copy: 
            # uses Guided Filter and micro-texture boost for better visibility
            view = enhance_texture_details(analysis_u8, observed, cfg)
            view[~observed] = 0
            
            # Highlight wrinkles in the view if desired (forensic overlay)
            if skin_analysis.get("wrinkle_binary") is not None:
                view_with_wrinkles = view.copy()
                view_with_wrinkles[skin_analysis["wrinkle_binary"]] = [0, 255, 0] # Green wrinkles
                aux["analysis_view_wrinkles"] = view_with_wrinkles
            
            aux["analysis_view"] = view
            
        return analysis_u8, beauty_u8, observed, confidence, aux
