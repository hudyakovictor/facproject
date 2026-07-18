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

from typing import Any

import cv2
import numpy as np

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


def enhance_texture_details(texture_u8: np.ndarray, mask: np.ndarray | None, cfg: HDUVConfig) -> np.ndarray:
    """Mild unsharp + CLAHE for HUMAN VIEWING / morph texture only.

    v3 fixes vs v1/v2:
    - correct color space: input is BGR, so BGR2LAB (v1/v2 used RGB2LAB);
    - mask-aware blur: unobserved (black) texels are excluded from the blur
      support via normalized convolution, so no dark halo creeps into the
      observed region near mask borders.
    """
    if texture_u8.ndim != 3 or not cfg.detail_enhance:
        return texture_u8
    tex = texture_u8.astype(np.float32) / 255.0

    if mask is not None:
        m = mask.astype(np.float32)
        blur_num = cv2.GaussianBlur(tex * m[..., None], (0, 0), cfg.detail_sigma)
        blur_den = cv2.GaussianBlur(m, (0, 0), cfg.detail_sigma)
        blur = blur_num / np.clip(blur_den[..., None], 1e-4, None)
    else:
        blur = cv2.GaussianBlur(tex, (0, 0), cfg.detail_sigma)
    sharpened = np.clip(tex * 1.35 - blur * 0.35, 0.0, 1.0)

    bgr_u8 = (sharpened * 255.0).astype(np.uint8)
    lab = cv2.cvtColor(bgr_u8, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=float(cfg.detail_clahe_clip), tileGridSize=(8, 8))
    lab_enh = cv2.merge([clahe.apply(l), a, b])
    enhanced = cv2.cvtColor(lab_enh, cv2.COLOR_LAB2BGR).astype(np.float32) / 255.0

    blended = tex * (1.0 - cfg.detail_blend) + enhanced * cfg.detail_blend
    out = np.clip(blended * 255.0, 0, 255).astype(np.uint8)
    if mask is not None:
        out[~mask] = texture_u8[~mask]
    return out


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
        skin_src = recon.get("skin_mask") if cfg.use_skin_mask else None
        if skin_src is not None:
            sm = np.asarray(skin_src)
            sm = sm.astype(np.float32)
            if sm.max() > 1.0:
                sm = sm / 255.0
            skin_ss = cv2.remap(sm, map_x, map_y, cv2.INTER_LINEAR,
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
        }
        if cfg.analysis_view:
            # enhanced HUMAN-INSPECTION copy; never feed to metrics
            view = enhance_texture_details(analysis_u8, observed, cfg)
            view[~observed] = 0
            aux["analysis_view"] = view
        return analysis_u8, beauty_u8, observed, confidence, aux
