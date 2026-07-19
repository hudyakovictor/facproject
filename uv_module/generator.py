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

try:
    from skimage import filters, feature, morphology, restoration
    _HAS_SKIMAGE = True
except ImportError:
    filters = feature = morphology = restoration = None
    _HAS_SKIMAGE = False

try:
    from skan import Skeleton, summarize
    _HAS_SKAN = True
except ImportError:
    Skeleton = summarize = None
    _HAS_SKAN = False

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

    Complies with WRINKLE_PIPELINE_SPEC.md.
    v3.3 fixes vs v3.2:
    - skan and scikit-image are optional (graceful degradation with cv2 fallback).
    - skan summarize() called with separator='_' to suppress deprecation warning.
    - Column name access is robust (tries 'branch-distance', 'main-path-distance', etc.).
    - Fallback skeleton via cv2 morphology when skan is unavailable.
    """
    if not mask.any():
        return {"wrinkle_map": np.zeros(mask.shape, np.uint8), "stats": {}}

    gray = cv2.cvtColor(texture_u8, cv2.COLOR_BGR2GRAY)
    gray_f = gray.astype(np.float32) / 255.0

    # 1. Subtle high-frequency emphasis only (DoG) -- pore scale kept,
    #    lighting gradient suppressed.
    blur_coarse = cv2.GaussianBlur(gray_f, (0, 0), 8.0)
    high = gray_f - blur_coarse
    # Standardise the high-pass component so illumination differences between
    # photos don't bias the threshold.
    base = cv2.GaussianBlur(gray_f, (0, 0), 32.0)
    std_base = cv2.GaussianBlur(((gray_f - base) ** 2), (0, 0), 32.0) ** 0.5 + 1e-3
    normalized = (high - high.mean()) / std_base
    normalized = (normalized - normalized.min()) / (normalized.max() - normalized.min() + 1e-8)

    # 2. Multiscale Hessian ridge detector
    sigmas = list(cfg.wrinkle_sigmas) or [0.4, 0.8, 1.2, 1.6]
    if _HAS_SKIMAGE and filters is not None:
        ridges = filters.frangi(normalized, sigmas=sigmas, black_ridges=True)
    else:
        # Fallback: pure cv2 Hessian ridge detection
        ridges = _cv2_ridge_fallback(normalized, sigmas)
    ridges = (ridges - ridges.min()) / (ridges.max() - ridges.min() + 1e-8)

    # 3. Adaptive threshold: per-strip (along v) if enabled, else global.
    wrinkle_bin = np.zeros_like(mask)
    if cfg.wrinkle_per_region_percentile:
        S = gray.shape[0]
        bounds = np.linspace(0, S, cfg.wrinkle_strip_count + 1, dtype=np.int64)
        for k in range(cfg.wrinkle_strip_count):
            r0, r1 = int(bounds[k]), int(bounds[k + 1])
            strip_mask = mask[r0:r1, :]
            if strip_mask.any():
                strip_ridges = ridges[r0:r1, :]
                t = np.percentile(strip_ridges[strip_mask], cfg.wrinkle_threshold_percentile)
                wrinkle_bin[r0:r1, :] = (strip_ridges > t) & strip_mask
    else:
        observed_ridges = ridges[mask]
        if len(observed_ridges) > 0:
            t = np.percentile(observed_ridges, cfg.wrinkle_threshold_percentile)
            wrinkle_bin = (ridges > t) & mask

    # 4. Cleanup and Skeletonization
    min_px = int(6 * max(cfg.super_sample, 1))
    if _HAS_SKIMAGE and morphology is not None:
        wrinkle_bin = morphology.remove_small_objects(wrinkle_bin, min_size=min_px)
        skeleton_img = morphology.skeletonize(wrinkle_bin)
    else:
        # Fallback: cv2-based cleanup and skeletonization
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        # Remove small objects via opening
        opened = cv2.morphologyEx(wrinkle_bin.astype(np.uint8), cv2.MORPH_OPEN, kernel, iterations=max(1, min_px // 3))
        wrinkle_bin = opened.astype(bool)
        skeleton_img = _cv2_skeleton(wrinkle_bin)

    # 5. Graph Analysis via Skan (optional) or cv2 fallback
    stats: dict[str, Any] = {}
    if skeleton_img.any():
        if _HAS_SKAN and Skeleton is not None and summarize is not None:
            try:
                sk = Skeleton(skeleton_img)
                summary = summarize(sk, separator='_')
                stats['branch_count'] = int(len(summary))
                # Robust column access: try multiple possible column names
                dist_col = None
                for candidate in ('branch_distance', 'main-path-distance', 'mean-pixel-diff'):
                    if candidate in summary.columns:
                        dist_col = candidate
                        break
                if dist_col is None:
                    # Last resort: first column containing 'distance' or 'length'
                    for c in summary.columns:
                        if 'distance' in c.lower() or 'length' in c.lower():
                            dist_col = c
                            break
                if dist_col is not None:
                    stats['total_geodesic_length'] = float(summary[dist_col].sum())
                stats['mean_ridge_strength'] = float(np.mean(ridges[skeleton_img]))
                stats['junctions'] = int(np.sum(sk.degrees > 2))
                stats['endpoints'] = int(np.sum(sk.degrees == 1))
                stats['skan_available'] = True
            except Exception as e:
                stats['skan_error'] = f"Skan analysis bypassed: {str(e)}"
                _cv2_skeleton_stats(skeleton_img, ridges, stats)
        else:
            _cv2_skeleton_stats(skeleton_img, ridges, stats)
    stats['skimage_available'] = _HAS_SKIMAGE
    stats['skan_available'] = _HAS_SKAN

    return {
        "wrinkle_map": (ridges * 255).astype(np.uint8),
        "wrinkle_binary": wrinkle_bin,
        "skeleton": skeleton_img,
        "stats": stats
    }


def _cv2_ridge_fallback(gray_f: np.ndarray, sigmas: list[float]) -> np.ndarray:
    """Pure cv2 Hessian-based ridge detection when scikit-image is unavailable."""
    responses = []
    for sigma in sigmas:
        smooth = cv2.GaussianBlur(gray_f, (0, 0), sigma)
        dxx = cv2.Sobel(smooth, cv2.CV_32F, 2, 0, ksize=3)
        dyy = cv2.Sobel(smooth, cv2.CV_32F, 0, 2, ksize=3)
        dxy = cv2.Sobel(smooth, cv2.CV_32F, 1, 1, ksize=3)
        trace = dxx + dyy
        disc = np.sqrt(np.maximum((dxx - dyy) ** 2 + 4 * dxy ** 2, 0.0))
        l1 = 0.5 * (trace - disc)
        l2 = 0.5 * (trace + disc)
        # Frangi-like: respond to elongated structures (|l1| >> |l2|)
        ridge = np.abs(l1) * np.exp(-(l2 ** 2) / (np.maximum(np.abs(l1), 1e-6) ** 2 + 1e-6))
        responses.append(ridge)
    return np.max(np.stack(responses), axis=0)


def _cv2_skeleton(binary: np.ndarray) -> np.ndarray:
    """Morphological thinning (cv2 fallback for skimage.skeletonize)."""
    img = binary.astype(np.uint8) * 255
    skeleton = np.zeros_like(img)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    for _ in range(256):
        opened = cv2.morphologyEx(img, cv2.MORPH_OPEN, element)
        skeleton = cv2.bitwise_or(skeleton, cv2.subtract(img, opened))
        img = cv2.erode(img, element)
        if cv2.countNonZero(img) == 0:
            break
    return skeleton > 0


def _cv2_skeleton_stats(skeleton_img: np.ndarray, ridges: np.ndarray, stats: dict) -> None:
    """Compute basic skeleton statistics using cv2 when skan is unavailable."""
    skel_u8 = skeleton_img.astype(np.uint8)
    # Count components, endpoints, branch points
    neighbors = cv2.filter2D(skel_u8, cv2.CV_16S, np.ones((3, 3), np.int16)) - skel_u8.astype(np.int16)
    count, labels, _, _ = cv2.connectedComponentsWithStats(skel_u8, 8)
    stats['skeleton_pixels'] = int(skeleton_img.sum())
    stats['skeleton_components'] = max(0, count - 1)  # exclude background
    stats['endpoints'] = int(np.sum(skeleton_img & (neighbors == 1)))
    stats['junctions'] = int(np.sum(skeleton_img & (neighbors >= 3)))
    if skeleton_img.any():
        stats['mean_ridge_strength'] = float(np.mean(ridges[skeleton_img]))
    stats['skan_available'] = False


def enhance_texture_details(texture_u8: np.ndarray, mask: np.ndarray | None, cfg: HDUVConfig) -> np.ndarray:
    """Gentle detail enhancement for the morph texture synthetic region.

    v3.2: modest guided-filter + CLAHE; no aggressive multi-scale DoG injection
    which oversharpens the synthetic-filled areas. Enhancement is limited to the
    synthetic region (where mask=True) and suppressed near the observed/synthetic
    seam to avoid amplifying the blend boundary.
    """
    if texture_u8.ndim != 3 or not cfg.detail_enhance:
        return texture_u8

    lab = cv2.cvtColor(texture_u8, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=float(cfg.detail_clahe_clip), tileGridSize=(8, 8))
    l_clahe = clahe.apply(l)

    radius = max(1, int(cfg.detail_sigma * 2))
    l_f = l_clahe.astype(np.float32)
    l_guide = guided_filter(l_clahe, l_clahe, radius=radius, eps=0.005)
    l_detail = l_f - l_guide.astype(np.float32)
    l_sharpened = np.clip(l_f + 1.2 * l_detail, 0, 255).astype(np.uint8)

    enhanced_lab = cv2.merge([l_sharpened, a, b])
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    if cfg.detail_blend > 0:
        res = cv2.addWeighted(texture_u8, 1.0 - cfg.detail_blend, enhanced_bgr, cfg.detail_blend, 0)
    else:
        res = enhanced_bgr

    if mask is not None:
        # Suppress enhancement in a band around the seam so the observed↔
        # synthetic transition stays smooth (no sharp edge enhancement).
        if cfg.detail_paid_only_synthetic:
            band = _seam_band(mask, cfg.detail_seam_band_px)
            res[band] = texture_u8[band]
        res[~mask] = texture_u8[~mask]

    return res


def _seam_band(mask: np.ndarray, band_px: int) -> np.ndarray:
    """Boolean mask of `band_px` around the transition of `mask`."""
    if band_px <= 0:
        return np.zeros_like(mask)
    k = 2 * int(band_px) + 1
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    dil = cv2.dilate(mask.astype(np.uint8), se).astype(bool)
    ero = cv2.erode(mask.astype(np.uint8), se).astype(bool)
    return dil ^ ero


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
        # v3.2: mask-aware resize. INTER_AREA averages all neighbouring texels
        # regardless of valid/invalid, which makes the atlas border fringe
        # (background/hair mixed into skin). We zero the image where not
        # in_frame/valid at SS-resolution and rebuild observed from a
        # correspondingly masked area accumulator. Per-texel coverage is
        # preserved by separately averaging the 0/1 valid mask.
        def down(a: np.ndarray) -> np.ndarray:
            if cfg.super_sample == 1:
                return a
            return cv2.resize(a, (S, S), interpolation=cv2.INTER_AREA)

        def down_mask(a: np.ndarray) -> np.ndarray:
            # boolean mask -> fraction of valid SS texels per final texel
            if cfg.super_sample == 1:
                return a.astype(np.float32)
            return cv2.resize(a.astype(np.float32), (S, S), interpolation=cv2.INTER_AREA)

        # Zero out texels that are out-of-frame at the SS grid BEFORE INTER_AREA,
        # so Lanczos replicate edge color doesn't leak into the accurate texels.
        clean_ss = sampled_ss.copy()
        clean_ss[~raster.valid] = 0.0
        clean_ss[~in_frame_ss] = 0.0
        # image accumulation for masked mean
        valid_ss = (raster.valid & in_frame_ss).astype(np.float32)

        img_sum = down(clean_ss)
        valid_sum = down_mask(valid_ss)
        safe = np.where(valid_sum > 1e-3, valid_sum, 1.0)
        texture = (img_sum / safe[..., None]).astype(np.float32)
        unknown_final = valid_sum <= 1e-3
        texture[unknown_final] = 0.0

        atlas_valid = down_mask(raster.valid.astype(np.float32)) > 0.5
        in_frame = down_mask(in_frame_ss.astype(np.float32))
        angle_w = down(angle_ss)
        occ_w = down(occ_ss)
        footprint = down(foot_ss)

        visibility = angle_w * occ_w * in_frame
        if skin_ss is not None:
            skin_w = down(skin_ss)
            visibility = visibility * (skin_w >= cfg.skin_mask_threshold).astype(np.float32)
        observed = atlas_valid & (visibility >= cfg.observed_threshold)

        # v3.2: erode in SS space *before* downsample so the kernel size is
        # consistent across super_sample settings and tight enough to keep
        # boundary detail (we recompute observed from eroded masks).
        if cfg.observed_erode_px > 0 and cfg.super_sample > 1:
            k_ss = 2 * int(cfg.observed_erode_px) + 1
            se_ss = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_ss, k_ss))
            obs_ss = (raster.valid & in_frame_ss & (
                (interpolate_vertex_attribute(raster, triangles, vis.combined.astype(np.float32)) > 0)
            ))
            ang_ss = interpolate_vertex_attribute(raster, triangles, vis.angle_weight)
            occ_ss_full = interpolate_vertex_attribute(raster, triangles, vis.combined.astype(np.float32))
            skin_ss_full = None
            if skin_ss is not None:
                skin_ss_full = skin_ss
            vis_ss = (ang_ss * occ_ss_full * (
                (raster.valid & in_frame_ss).astype(np.float32)
            ))
            if skin_ss_full is not None:
                vis_ss = vis_ss * (skin_ss_full >= cfg.skin_mask_threshold).astype(np.float32)
            obs_ss_pre = (vis_ss >= cfg.observed_threshold)
            obs_ss_pre = cv2.erode(obs_ss_pre.astype(np.uint8), se_ss).astype(bool)
            observed = down_mask(obs_ss_pre.astype(np.float32)) > 0.5
        elif cfg.observed_erode_px > 0:
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
            skin_mask_final = down(skin_ss) > cfg.skin_mask_threshold
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
                mb_blend_levels=cfg.mb_blend_levels,
                mb_blend_sigma=cfg.mb_blend_sigma,
                mirror_strip_count=cfg.mirror_strip_count,
                inpaint_method=cfg.inpaint_method,
            )
            # v3.2: gentle enhancement limited to synthetic region only,
            # with seam-band suppression so the blend boundary isn't amplified.
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
