from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .visibility import compute_triangle_visibility
from .uv_baker import UVBaker
from .detail import UVDetailEnhancer
from .inpaint_blend import UVBeautyPostprocessor
from .delight import compute_shading_uv, albedo_from_texture
from .provenance import apply_beauty_provenance, measurement_mask
from .warp_metrics import triangle_warp_metrics

logger = logging.getLogger(__name__)


@dataclass
class HDUVConfig:
    uv_size: int = 1024  # Changed from 2048 to 1024 for smaller file size
    super_sample: int = 2
    enable_delighting: bool = False
    enable_symmetry_fill: bool = True
    enable_detail_boost: bool = True
    detail_strength: float = 1.05
    unsharp_amount: float = 0.2
    detail_base_sigma_s_ratio: float = 0.02
    detail_base_sigma_r: float = 0.15
    use_barycentric_bake: bool = True
    force_all_triangles_visible: bool = False  # Changed to False for production
    device: str = "mps"
    use_fast_path: bool = True
    verbose: bool = False
    collect_provenance: bool = False
    visibility_depth_tolerance_fraction: float = 0.01


class HDUVTextureGenerator:
    """
    Генератор HD UV-текстур для 3DDFA_V3.

    Пайплайн:
      1. Visibility weights (нормали, угол к камере)
      2. UV baking (affine warp / barycentric, supersampled)
      3. De-lighting (опц., SH + нормали → albedo)
      4. Detail enhancement (base/detail split, selective gain)
      5. Beauty postprocessing (symmetry fill, inpaint, seam blend)

    Возвращает:
      - uv_tex_analysis  (uint8) — legacy derived observed texture (may be detail enhanced)
      - uv_tex_beauty    (uint8) — для рендера (+ symmetry/inpaint)
      - uv_mask_visible  (uint8) — маска видимых texel'ов
      - uv_confidence    (float32) — карта доверия
      - aux_data         (dict) — вспомогательные карты
    """

    def __init__(self, config: Optional[HDUVConfig] = None):
        self.config = config or HDUVConfig()
        self.baker = UVBaker(
            uv_size=self.config.uv_size,
            super_sample=self.config.super_sample,
        )
        self.detail = UVDetailEnhancer(
            detail_strength=self.config.detail_strength,
            unsharp_amount=self.config.unsharp_amount,
            base_sigma_s_ratio=self.config.detail_base_sigma_s_ratio,
            base_sigma_r=self.config.detail_base_sigma_r,
        )
        self.beauty_post = UVBeautyPostprocessor()

    def generate(
        self,
        image: np.ndarray,
        recon_dict: Dict[str, Any],
        debug_output_dir: Optional[str] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:

        cfg = self.config

        # --- 1. Подготовка геометрии (ТЗ 5.1–5.2) ---
        vertices = np.asarray(recon_dict["vertices"], dtype=np.float32)
        tris_key = "triangles" if "triangles" in recon_dict else "tri"
        triangles = np.asarray(recon_dict[tris_key], dtype=np.int64)
        uv_coords = np.asarray(recon_dict["uv_coords"], dtype=np.float32)

        # 2D-координаты в пикселях изображения
        if "vertices_2d" in recon_dict:
            vertices_2d = np.asarray(recon_dict["vertices_2d"], dtype=np.float32)
        else:
            raise ValueError("vertices_2d is mandatory but not found in recon_dict")

        # 3D для расчёта нормалей / видимости
        vertices_3d = np.asarray(
            recon_dict.get("vertices_3d", vertices), dtype=np.float32
        )
        if vertices_3d.ndim == 3:
            vertices_3d = vertices_3d[0]
        if cfg.collect_provenance and recon_dict.get("projection_space") != "original":
            raise ValueError("diagnostics require explicitly declared original-pixel projections")

        # --- 2. Видимость и веса (ТЗ 5.3) ---
        if cfg.force_all_triangles_visible:
            tri_weights = np.ones(triangles.shape[0], dtype=np.float32)
            visibility_buffers = None
        else:
            depth_span = float(np.ptp(vertices_3d[:, 2]))
            tri_weights, visibility_buffers = compute_triangle_visibility(
                vertices_3d=vertices_3d,
                triangles=triangles,
                use_zbuffer=True,
                vertices_2d=vertices_2d,
                image_size=(image.shape[0], image.shape[1]),
                z_tolerance=max(1e-6, cfg.visibility_depth_tolerance_fraction * depth_span),
                angle_threshold_deg=75.0, # Reduced from 89.0 to fix side smearing
                gamma=4.0, # Increased from 1.5 to fix edge smearing
                occlusion_falloff=0.001,
                return_buffers=True,
            )

        if cfg.verbose:
            logger.info("[VIS] total triangles:   %d", triangles.shape[0])
            logger.info("[VIS] tri_weights > 0:   %d", (tri_weights > 0).sum())
            logger.info("[VIS] tri_weights > 0.5: %d", (tri_weights > 0.5).sum())
            logger.info("[VIS] tri_weights max:   %.4f", float(tri_weights.max()))
            logger.info("[VIS] tri_weights mean:  %.6f", float(tri_weights.mean()))

        # --- 3. UV Baking (ТЗ 5.4) ---
        if cfg.use_barycentric_bake:
            uv_texture_raw, uv_mask_visible, uv_confidence, uv_is_original = (
                self.baker.bake_via_barycentric(
                    image=image,
                    vertices_2d=vertices_2d,
                    uv_coords=uv_coords,
                    triangles=triangles,
                    tri_visibility_weights=tri_weights,
                    collect_provenance=cfg.collect_provenance,
                    visibility_buffers=visibility_buffers,
                )
            )
        else:
            uv_texture_raw, uv_mask_visible, uv_confidence, uv_is_original = (
                self.baker.bake(
                    image=image,
                    vertices_2d=vertices_2d,
                    uv_coords=uv_coords,
                    triangles=triangles,
                    tri_visibility_weights=tri_weights,
                    debug_output_dir=debug_output_dir,
                    collect_provenance=cfg.collect_provenance,
                    visibility_buffers=visibility_buffers,
                )
            )

        aux: Dict[str, Any] = {
            "uv_is_original": uv_is_original,
            "tri_visibility": tri_weights,
            "uv_texture_raw": uv_texture_raw.copy(),
            "projection_space": recon_dict.get("projection_space", "undeclared_legacy"),
            "geometry_visibility_verified": visibility_buffers is not None,
        }

        # --- 4. De-lighting (ТЗ 5.6, опционально) ---
        did_delight = False
        if (
            cfg.enable_delighting
            and "normals_3d" in recon_dict
            and "alpha_sh" in recon_dict
        ):
            work_size = self.baker.uv_size
            normals_3d = np.asarray(recon_dict["normals_3d"], dtype=np.float32)
            normals_01 = np.clip((normals_3d + 1.0) * 0.5, 0.0, 1.0)
            normals_uv_01 = self.baker.bake_vertex_colors(
                uv_coords, triangles, normals_01, size=work_size
            )
            normals_uv = 2.0 * normals_uv_01 - 1.0
            nnorm = np.linalg.norm(normals_uv, axis=-1, keepdims=True)
            normals_uv = np.where(nnorm > 1e-8, normals_uv / nnorm, 0.0)

            shading_uv = compute_shading_uv(normals_uv, recon_dict["alpha_sh"])
            uv_texture_raw = albedo_from_texture(
                uv_texture_raw, shading_uv, eps=1e-4, clamp_max=255.0
            )
            aux["shading_uv"] = shading_uv
            aux["albedo_uv"] = uv_texture_raw.copy()
            did_delight = True

        # --- 5. Detail enhancement (ТЗ 5.5) ---
        detail_strength_map = None
        if cfg.enable_detail_boost:
            uv_tex_analysis, detail_strength_map = self.detail.enhance(
                uv_texture_raw=uv_texture_raw,
                uv_mask_visible=uv_mask_visible,
                uv_confidence=uv_confidence,
            )
        else:
            uv_tex_analysis = uv_texture_raw.copy()
            detail_strength_map = np.zeros_like(uv_confidence, dtype=np.float32)

        # --- 6. Beauty: symmetry + inpaint + seam blend (ТЗ 5.7–5.9) ---
        uv_tex_analysis = np.clip(uv_tex_analysis, 0, 255).astype(np.uint8)

        beauty_result = self.beauty_post.process(
            uv_tex_analysis=uv_tex_analysis,
            uv_mask_visible=uv_mask_visible,
            uv_confidence=uv_confidence,
            enable_symmetry=cfg.enable_symmetry_fill,
            return_masks=cfg.collect_provenance,
        )
        if cfg.collect_provenance:
            uv_tex_beauty, beauty_masks = beauty_result
        else:
            uv_tex_beauty, beauty_masks = beauty_result, {}

        uv_tex_beauty = np.clip(uv_tex_beauty, 0, 255).astype(np.uint8)

        if detail_strength_map is not None:
            aux["uv_detail_strength_map"] = detail_strength_map
        if cfg.collect_provenance:
            provenance = self.baker.last_provenance
            apply_beauty_provenance(provenance, beauty_masks)
            provenance["beauty_modified"] |= uv_mask_visible & (cfg.enable_detail_boost or did_delight)
            external_mask = recon_dict.get("external_occlusion_uv")
            if external_mask is not None:
                external_mask = np.asarray(external_mask, dtype=np.int8)
                if external_mask.shape != uv_mask_visible.shape or not np.isin(external_mask, [-1, 0, 1]).all():
                    raise ValueError("external occlusion map must contain unknown=-1,clear=0,occluded=1 on the UV grid")
                provenance["external_occlusion"] = external_mask
            radius = {0: 0.5, 1: 1.0, 2: 2.0, 4: 4.0}.get(self.baker.config.interpolation, 4.0)
            provenance["source_bounds"][..., :2] -= radius
            provenance["source_bounds"][..., 2:] += radius
            bounds = provenance["source_bounds"]
            provenance["sampling_kernel_in_image"] = np.isfinite(bounds).all(axis=2) & (bounds[..., 0] >= 0) & (bounds[..., 1] >= 0) \
                & (bounds[..., 2] <= image.shape[1] - 1) & (bounds[..., 3] <= image.shape[0] - 1)
            provenance["measurement_suitable"] = measurement_mask(provenance)
            if visibility_buffers is None:
                provenance["measurement_suitable"][:] = False
            metrics = triangle_warp_metrics(np.asarray(recon_dict.get("vertices_object", vertices_3d)), triangles,
                                            uv_coords, vertices_2d, cfg.uv_size)
            metrics["triangle_visible"] = tri_weights > 0
            ids = provenance["triangle_id"]
            mapped = ids >= 0
            density = np.full(ids.shape, np.nan, dtype=np.float32)
            detail = np.full(ids.shape, np.nan, dtype=np.float32)
            density[mapped] = metrics["density_uv_photo"][ids[mapped]]
            detail[mapped] = metrics["scales_uv_photo"][ids[mapped], 1]
            provenance["source_density"] = density
            provenance["source_detail_px"] = detail
            aux.update({"provenance": provenance, "triangle_warp_metrics": metrics, "beauty_masks": beauty_masks,
                        "raw_sampling_interpolation": self.baker.config.interpolation,
                        "visibility_buffers": visibility_buffers})

        return uv_tex_analysis, uv_tex_beauty, uv_mask_visible, uv_confidence, aux
