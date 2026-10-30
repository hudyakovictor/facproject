from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from .provenance import DIRECT, TexelProvenance
from .visibility import query_visibility


@dataclass
class UVBakerConfig:
    interpolation: int = cv2.INTER_LANCZOS4
    border_mode: int = cv2.BORDER_REPLICATE


logger = logging.getLogger(__name__)


class UVBaker:
    """
    High-res UV baker: per-triangle affine warp image->UV.
    На выходе даёт:
        - uv_texture_raw      (work_size x work_size x 3, float32)
        - uv_mask_visible     (work_size x work_size, bool)
        - uv_confidence_map   (work_size x work_size, float32)
        - uv_is_original      (work_size x work_size, bool)
    """

    def __init__(
        self,
        uv_size: int = 2048,
        super_sample: int = 2,
        config: Optional[UVBakerConfig] = None,
    ) -> None:
        self.uv_size = int(uv_size)
        self.super_sample = int(super_sample)
        self.work_size = self.uv_size * self.super_sample
        self.config = config or UVBakerConfig()
        self.last_provenance = None

    def bake(
        self,
        image: np.ndarray,
        vertices_2d: np.ndarray,
        uv_coords: np.ndarray,
        triangles: np.ndarray,
        tri_visibility_weights: np.ndarray,
        debug_output_dir: Optional[str] = None,
        collect_provenance: bool = False,
        visibility_buffers: Optional[dict] = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        h, w = image.shape[:2]
        work = self.work_size

        uv_px = self._prepare_uv_px(uv_coords, work)
        tris = np.asarray(triangles, dtype=np.int64)
        verts2d = np.asarray(vertices_2d, dtype=np.float32)
        w_tri = np.asarray(tri_visibility_weights, dtype=np.float32).reshape(-1)

        if debug_output_dir:
            os.makedirs(debug_output_dir, exist_ok=True)
            debug_uv_mesh = np.zeros((work, work, 3), dtype=np.uint8)
            for i in range(tris.shape[0]):
                idx0, idx1, idx2 = tris[i]
                pts = uv_px[[idx0, idx1, idx2]].astype(np.int32).reshape(-1, 1, 2)
                cv2.fillConvexPoly(debug_uv_mesh, pts, (0, 100, 0))
                cv2.polylines(debug_uv_mesh, [pts], isClosed=True, color=(0, 255, 0), thickness=1)
            mesh_path = os.path.join(debug_output_dir, "debug_uv_mesh.png")
            cv2.imwrite(mesh_path, debug_uv_mesh)
            filled_mesh = int((debug_uv_mesh[:, :, 1] > 0).sum())
            logger.debug(
                "[BAKER] debug_uv_mesh saved -> %s  (filled %d / %d = %.1f%%)",
                mesh_path,
                filled_mesh,
                work * work,
                100.0 * filled_mesh / (work * work),
            )

        texture = np.zeros((work, work, 3), dtype=np.float32)
        weight_accum = np.zeros((work, work), dtype=np.float32)
        tracker = TexelProvenance(work) if collect_provenance else None
        self.last_provenance = None

        for i in range(tris.shape[0]):
            w_i = float(w_tri[i])
            if w_i <= 0.0 and tracker is None:
                continue

            idx0, idx1, idx2 = tris[i]
            src_pts = verts2d[[idx0, idx1, idx2]]  # image space
            dst_pts = uv_px[[idx0, idx1, idx2]]  # UV pixel space

            if self._tri_area(dst_pts) < 0.01 or self._tri_area(src_pts) < 0.01:
                continue

            M = np.asarray(
                cv2.getAffineTransform(dst_pts.astype(np.float32), src_pts.astype(np.float32)),
                dtype=np.float64,
            )

            bb_min = np.floor(dst_pts.min(axis=0)).astype(int)
            bb_max = np.ceil(dst_pts.max(axis=0)).astype(int)
            bb_min = np.clip(bb_min, 0, work - 1)
            bb_max = np.clip(bb_max, 0, work - 1)
            if bb_min[0] >= bb_max[0] or bb_min[1] >= bb_max[1]:
                continue

            bw = bb_max[0] - bb_min[0] + 1
            bh = bb_max[1] - bb_min[1] + 1
            local_pts = dst_pts - bb_min.astype(np.float32)

            mask = np.zeros((bh, bw), dtype=np.uint8)
            pts_fixed = np.round(local_pts * 16).astype(np.int32).reshape(-1, 1, 2)
            cv2.fillConvexPoly(mask, pts_fixed, (1,), lineType=cv2.LINE_8, shift=4)

            ys, xs = np.where(mask > 0)
            if xs.size == 0:
                continue

            uv_pixels = np.stack(
                [
                    xs + bb_min[0],
                    ys + bb_min[1],
                    np.ones_like(xs, dtype=np.float64),
                ],
                axis=0,
            )
            img_coords = M @ uv_pixels
            ix = img_coords[0]
            iy = img_coords[1]
            uv_points = uv_pixels[:2].T
            edge_matrix = np.column_stack((dst_pts[1] - dst_pts[0], dst_pts[2] - dst_pts[0]))
            tail = (uv_points - dst_pts[0]) @ np.linalg.inv(edge_matrix).T
            barycentric = np.column_stack((1 - tail.sum(axis=1), tail))

            sample_x = ix.astype(np.float32).reshape(1, -1)
            sample_y = iy.astype(np.float32).reshape(1, -1)
            sampled = cv2.remap(
                image,
                sample_x,
                sample_y,
                self.config.interpolation,
                borderMode=self.config.border_mode,
            )
            colors = sampled.reshape(-1, 3).astype(np.float64)

            write_y = ys + bb_min[1]
            write_x = xs + bb_min[0]

            in_bounds = (ix >= 0.0) & (ix <= w - 1) & (iy >= 0.0) & (iy <= h - 1) & (barycentric >= -1e-6).all(axis=1)
            geometry_visible = self._sample_visibility(i, np.column_stack((ix, iy)), barycentric, tris, visibility_buffers)
            observed = in_bounds & geometry_visible & (w_i > 0)
            if tracker is not None:
                tracker.record(i, write_y, write_x, barycentric, np.column_stack((ix, iy)), w_i, in_bounds, geometry_visible)
            update = observed & (w_i > weight_accum[write_y, write_x])
            texture[write_y[update], write_x[update]] = colors[update]
            weight_accum[write_y[update], write_x[update]] = w_i

        mask_visible = weight_accum > 0.0
        uv_texture_raw = texture
        uv_confidence = np.clip(weight_accum, 0, 1)

        uv_is_original = mask_visible.copy()

        if self.super_sample > 1:
            uv_texture_raw, mask_visible, uv_confidence, uv_is_original = self._downsample_results(
                uv_texture_raw, mask_visible, uv_confidence, uv_is_original
            )
        if tracker is not None:
            self.last_provenance = tracker.finish(self.super_sample)
            if self.config.interpolation == cv2.INTER_NEAREST:
                self.last_provenance["raw_method"][mask_visible] = DIRECT

        total_uv_pixels = work * work
        filled_pixels = int(mask_visible.sum())
        logger.debug("[BAKER] work_size=%d", work)
        logger.debug("[BAKER] total triangles:     %d", tris.shape[0])
        logger.debug("[BAKER] triangles with w>0:  %d", int((w_tri > 0).sum()))
        logger.debug(
            "[BAKER] UV pixels filled:    %d / %d  (%.1f%%)",
            filled_pixels,
            total_uv_pixels,
            100.0 * filled_pixels / max(total_uv_pixels, 1),
        )
        logger.debug("[BAKER] weight_accum max:    %.4f", float(weight_accum.max()))
        logger.debug("[BAKER] texture max:         %.1f", float(texture.max()))

        return uv_texture_raw, mask_visible, uv_confidence, uv_is_original

    def bake_via_barycentric(
        self,
        image: np.ndarray,
        vertices_2d: np.ndarray,
        uv_coords: np.ndarray,
        triangles: np.ndarray,
        tri_visibility_weights: np.ndarray,
        collect_provenance: bool = False,
        visibility_buffers: Optional[dict] = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Бейкинг через растеризацию fillConvexPoly + барицентрическая интерполяция.
        Надёжнее per-triangle affine: без щелей между треугольниками, один remap в конце.
        Возвращает (uv_texture_raw, mask_visible, uv_confidence, uv_is_original) как bake().
        """
        h, w = image.shape[:2]
        work = self.work_size
        uv_px = self._prepare_uv_px(uv_coords, work)
        tris = np.asarray(triangles, dtype=np.int64)
        verts2d = np.asarray(vertices_2d, dtype=np.float32)
        w_tri = np.asarray(tri_visibility_weights, dtype=np.float32).reshape(-1)

        map_x_accum = np.zeros((work, work), dtype=np.float32)
        map_y_accum = np.zeros((work, work), dtype=np.float32)
        weight_accum = np.zeros((work, work), dtype=np.float32)
        tracker = TexelProvenance(work) if collect_provenance else None
        self.last_provenance = None

        for i in range(tris.shape[0]):
            w_i = float(w_tri[i])
            if w_i <= 0.0 and tracker is None:
                continue

            idx0, idx1, idx2 = tris[i]
            uv_tri = uv_px[[idx0, idx1, idx2]].astype(np.float64)
            img_tri = verts2d[[idx0, idx1, idx2]].astype(np.float64)

            bb_min = np.floor(uv_tri.min(axis=0)).astype(int)
            bb_max = np.ceil(uv_tri.max(axis=0)).astype(int)
            bb_min = np.clip(bb_min, 0, work - 1)
            bb_max = np.clip(bb_max, 0, work - 1)
            if bb_min[0] > bb_max[0] or bb_min[1] > bb_max[1]:
                continue

            bw = bb_max[0] - bb_min[0] + 1
            bh = bb_max[1] - bb_min[1] + 1
            
            v0 = uv_tri[2] - uv_tri[0]
            v1 = uv_tri[1] - uv_tri[0]
            d00 = float(v0 @ v0)
            d01 = float(v0 @ v1)
            d11 = float(v1 @ v1)
            denom = d00 * d11 - d01 * d01
            if abs(denom) < 1e-10:
                continue

            px_local = np.arange(bb_min[0], bb_max[0] + 1, dtype=np.float64)
            py_local = np.arange(bb_min[1], bb_max[1] + 1, dtype=np.float64)
            gx, gy = np.meshgrid(px_local, py_local)
            xs_all = gx.ravel()
            ys_all = gy.ravel()

            v2_x = xs_all - uv_tri[0, 0]
            v2_y = ys_all - uv_tri[0, 1]
            
            d20 = v2_x * v0[0] + v2_y * v0[1]
            d21 = v2_x * v1[0] + v2_y * v1[1]
            
            bary_v = (d11 * d20 - d01 * d21) / denom
            bary_w = (d00 * d21 - d01 * d20) / denom
            bary_u = 1.0 - bary_v - bary_w

            # Eps buffer avoids seam gaps
            eps = 1e-6
            inside = (bary_u >= -eps) & (bary_v >= -eps) & (bary_w >= -eps)
            if not inside.any():
                continue
                
            xs = xs_all[inside].astype(np.int32)
            ys = ys_all[inside].astype(np.int32)
            bary_u = bary_u[inside]
            bary_v = bary_v[inside]
            bary_w = bary_w[inside]

            img_x = bary_u * img_tri[0, 0] + bary_w * img_tri[1, 0] + bary_v * img_tri[2, 0]
            img_y = bary_u * img_tri[0, 1] + bary_w * img_tri[1, 1] + bary_v * img_tri[2, 1]

            in_bounds = (img_x >= 0.0) & (img_x <= w - 1) & (img_y >= 0.0) & (img_y <= h - 1)
            barycentric = np.column_stack((bary_u, bary_w, bary_v))
            source_xy = np.column_stack((img_x, img_y))
            geometry_visible = self._sample_visibility(i, source_xy, barycentric, tris, visibility_buffers)
            observed = in_bounds & geometry_visible & (w_i > 0)
            if tracker is not None:
                tracker.record(i, ys, xs, barycentric, source_xy, w_i, in_bounds, geometry_visible)
            # Averaging coordinates of overlapping charts samples an unrelated image location.
            # Keep the strongest actual contributor; equal-weight ties keep the first triangle.
            update = observed & (w_i > weight_accum[ys, xs])
            y, x = ys[update], xs[update]
            map_x_accum[y, x] = img_x[update]
            map_y_accum[y, x] = img_y[update]
            weight_accum[y, x] = w_i

        valid = weight_accum > 0.0
        filled = int(valid.sum())
        total = work * work
        logger.debug(
            "[BAKER] bake_via_barycentric: filled %d / %d (%.1f%%)",
            filled,
            total,
            100.0 * filled / max(total, 1),
        )

        map_x_final = np.zeros((work, work), dtype=np.float32)
        map_y_final = np.zeros((work, work), dtype=np.float32)
        if filled > 0:
            map_x_final[valid] = np.clip(
                map_x_accum[valid],
                0.0,
                float(w - 1),
            )
            map_y_final[valid] = np.clip(
                map_y_accum[valid],
                0.0,
                float(h - 1),
            )

        uv_texture_raw = cv2.remap(
            image,
            map_x_final,
            map_y_final,
            self.config.interpolation,
            borderMode=self.config.border_mode,
        ).astype(np.float32)
        uv_texture_raw[~valid] = 0.0

        uv_confidence = np.clip(weight_accum, 0, 1)

        uv_is_original = valid.copy()

        if self.super_sample > 1:
            uv_texture_raw, valid, uv_confidence, uv_is_original = self._downsample_results(
                uv_texture_raw, valid, uv_confidence, uv_is_original
            )
        if tracker is not None:
            self.last_provenance = tracker.finish(self.super_sample)
            if self.config.interpolation == cv2.INTER_NEAREST:
                self.last_provenance["raw_method"][valid] = DIRECT

        return uv_texture_raw, valid, uv_confidence, uv_is_original

    @staticmethod
    def _sample_visibility(triangle_id, source_xy, barycentric, triangles, buffers):
        if buffers is None:
            return np.ones(len(source_xy), dtype=bool)
        if not buffers["front_facing"][triangle_id]:
            return np.zeros(len(source_xy), dtype=bool)
        depths = buffers["vertex_depth"][triangles[triangle_id]]
        if np.any(depths <= 0):
            return np.zeros(len(source_xy), dtype=bool)
        expected = 1 / np.sum(barycentric / depths, axis=1)
        return query_visibility(source_xy, expected, triangle_id, buffers)

    def bake_vertex_colors(
        self,
        uv_coords: np.ndarray,
        triangles: np.ndarray,
        vertex_colors: np.ndarray,
        size: Optional[int] = None,
    ) -> np.ndarray:
        """
        Растеризация вершинных цветов в UV без сэмплинга из изображения.
        Возвращает стандартную UV-карту (H, W, 3) в [0, 1], float32.
        size: разрешение карты (по умолчанию uv_size, без super_sample).
        """
        work = int(size) if size is not None else self.uv_size
        uv_px = self._prepare_uv_px(uv_coords, work)

        color_accum = np.zeros((work, work, 3), dtype=np.float64)
        weight_accum = np.zeros((work, work), dtype=np.float64)
        tris = np.asarray(triangles, dtype=np.int64)
        vcolors = np.asarray(vertex_colors, dtype=np.float64)
        if vcolors.ndim == 3:
            vcolors = vcolors[0]
        vcolors = np.clip(vcolors, 0.0, 1.0)

        for i in range(tris.shape[0]):
            idx0, idx1, idx2 = tris[i]
            dst_pts = uv_px[[idx0, idx1, idx2]].astype(np.float64)
            if self._tri_area(dst_pts) < 0.01:
                continue

            bb_min = np.floor(dst_pts.min(axis=0)).astype(int)
            bb_max = np.ceil(dst_pts.max(axis=0)).astype(int)
            bb_min = np.clip(bb_min, 0, work - 1)
            bb_max = np.clip(bb_max, 0, work - 1)
            if bb_min[0] > bb_max[0] or bb_min[1] > bb_max[1]:
                continue

            v0 = dst_pts[2] - dst_pts[0]
            v1 = dst_pts[1] - dst_pts[0]
            d00 = float(v0 @ v0)
            d01 = float(v0 @ v1)
            d11 = float(v1 @ v1)
            denom = d00 * d11 - d01 * d01
            if abs(denom) < 1e-10:
                continue

            px_local = np.arange(bb_min[0], bb_max[0] + 1, dtype=np.float64)
            py_local = np.arange(bb_min[1], bb_max[1] + 1, dtype=np.float64)
            gx, gy = np.meshgrid(px_local, py_local)
            xs_all = gx.ravel()
            ys_all = gy.ravel()

            v2_x = xs_all - dst_pts[0, 0]
            v2_y = ys_all - dst_pts[0, 1]
            
            d20 = v2_x * v0[0] + v2_y * v0[1]
            d21 = v2_x * v1[0] + v2_y * v1[1]
            
            bary_v = (d11 * d20 - d01 * d21) / denom
            bary_w = (d00 * d21 - d01 * d20) / denom
            bary_u = 1.0 - bary_v - bary_w

            # Eps buffer avoids seam gaps
            eps = 1e-4
            inside = (bary_u >= -eps) & (bary_v >= -eps) & (bary_w >= -eps)
            if not inside.any():
                continue
                
            xs = xs_all[inside].astype(np.int32)
            ys = ys_all[inside].astype(np.int32)
            bary_u = bary_u[inside]
            bary_v = bary_v[inside]
            bary_w = bary_w[inside]

            c0, c1, c2 = vcolors[idx0], vcolors[idx1], vcolors[idx2]
            colors = (
                bary_u[:, None] * c0[None, :]
                + bary_w[:, None] * c1[None, :]
                + bary_v[:, None] * c2[None, :]
            )

            wy = ys
            wx = xs
            color_accum[wy, wx] += colors
            weight_accum[wy, wx] += 1.0

        out = np.zeros((work, work, 3), dtype=np.float32)
        mask_visible = weight_accum > 0.0
        out[mask_visible] = (
            color_accum[mask_visible] / weight_accum[mask_visible, None]
        ).astype(np.float32)
        return np.clip(out, 0.0, 1.0)

    @staticmethod
    def _tri_area(pts: np.ndarray) -> float:
        d1 = pts[1] - pts[0]
        d2 = pts[2] - pts[0]
        return float(abs(d1[0] * d2[1] - d1[1] * d2[0]) * 0.5)

    @staticmethod
    def _tri_areas_batch(pts: np.ndarray) -> np.ndarray:
        d1 = pts[:, 1] - pts[:, 0]
        d2 = pts[:, 2] - pts[:, 0]
        return np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) * 0.5

    def _prepare_uv_px(self, uv_coords: np.ndarray, size: int) -> np.ndarray:
        uv = np.asarray(uv_coords, dtype=np.float32)
        if uv.ndim != 2 or uv.shape[1] < 2:
            raise ValueError("uv_coords must be (N, 2+) array")
        if uv.shape[1] > 2:
            uv = uv[:, :2]
        else:
            uv = uv.copy()

        uv_max = float(uv.max(initial=0.0))
        if uv_max > 1.5:
            denom = max(uv_max, 1e-6)
            uv = uv / denom

        uv_px = np.empty((uv.shape[0], 2), dtype=np.float32)
        uv_px[:, 0] = uv[:, 0] * (size - 1)
        uv_px[:, 1] = (1.0 - uv[:, 1]) * (size - 1)
        return uv_px

    def _downsample_results(
        self,
        uv_texture_raw: np.ndarray,
        mask_visible: np.ndarray,
        uv_confidence: np.ndarray,
        uv_is_original: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        target = self.uv_size
        support = cv2.resize(mask_visible.astype(np.float32), (target, target), interpolation=cv2.INTER_AREA)
        mask = support > 0
        texture = cv2.resize(uv_texture_raw * mask_visible[..., None], (target, target), interpolation=cv2.INTER_AREA)
        texture = np.divide(texture, support[..., None], out=np.zeros_like(texture), where=support[..., None] > 0)
        confidence = cv2.resize(uv_confidence * mask_visible, (target, target), interpolation=cv2.INTER_AREA)
        confidence = np.divide(confidence, support, out=np.zeros_like(confidence), where=support > 0)
        original_support = cv2.resize((uv_is_original & mask_visible).astype(np.float32), (target, target), interpolation=cv2.INTER_AREA)
        is_original = mask & (original_support >= support - 1e-6)
        return texture, mask, confidence, is_original
