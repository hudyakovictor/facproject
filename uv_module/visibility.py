"""Utilities for estimating visibility weights for 3DDFA_V3 triangles."""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

__all__ = ["compute_triangle_visibility", "compute_vertex_visibility"]

logger = logging.getLogger(__name__)


def rasterize_depth(vertices_2d, depths, triangles, image_size, front_mask=None, max_side=1024):
    h, w = image_size
    ratio = min(1.0, max_side / max(h, w))
    bh, bw = max(2, int(round(h * ratio))), max(2, int(round(w * ratio)))
    scale = np.array([(bw - 1) / max(w - 1, 1), (bh - 1) / max(h - 1, 1)])
    points = np.asarray(vertices_2d, dtype=float) * scale
    z = np.asarray(depths, dtype=float)
    faces = np.asarray(triangles, dtype=int)
    depth = np.full((bh, bw), np.inf, dtype=np.float32)
    owners = np.full((bh, bw), -1, dtype=np.int32)
    mask = np.ones(len(faces), dtype=bool) if front_mask is None else front_mask
    for index in np.flatnonzero(mask):
        indices = faces[index]
        p, tz = points[indices], z[indices]
        if not np.isfinite(p).all() or not np.isfinite(tz).all() or np.any(tz <= 0):
            continue
        edges = np.column_stack((p[1] - p[0], p[2] - p[0]))
        if abs(np.linalg.det(edges)) < 1e-10:
            continue
        low = np.maximum(np.floor(p.min(axis=0)).astype(int), 0)
        high = np.minimum(np.ceil(p.max(axis=0)).astype(int), [bw - 1, bh - 1])
        if np.any(low > high):
            continue
        gx, gy = np.meshgrid(np.arange(low[0], high[0] + 1), np.arange(low[1], high[1] + 1))
        coordinates = np.column_stack((gx.ravel(), gy.ravel()))
        tail = (coordinates - p[0]) @ np.linalg.inv(edges).T
        bary = np.column_stack((1 - tail.sum(axis=1), tail))
        inside = (bary >= -1e-6).all(axis=1)
        coordinates, bary = coordinates[inside].astype(int), bary[inside]
        predicted = 1 / np.sum(bary / tz, axis=1)
        x, y = coordinates[:, 0], coordinates[:, 1]
        closer = predicted < depth[y, x]
        depth[y[closer], x[closer]] = predicted[closer]
        owners[y[closer], x[closer]] = index
    return {"depth": depth, "triangle_id": owners, "scale": scale, "image_size": tuple(image_size)}


def query_visibility(source_xy, expected_depth, triangle_id, buffers):
    xy = np.asarray(source_xy)
    h, w = buffers["image_size"]
    in_bounds = np.isfinite(xy).all(axis=1) & (xy[:, 0] >= 0) & (xy[:, 0] <= w - 1) & (xy[:, 1] >= 0) & (xy[:, 1] <= h - 1)
    scaled = np.rint(np.nan_to_num(xy) * buffers["scale"]).astype(int)
    bh, bw = buffers["depth"].shape
    x, y = np.clip(scaled[:, 0], 0, bw - 1), np.clip(scaled[:, 1], 0, bh - 1)
    depth, owner = buffers["depth"][y, x], buffers["triangle_id"][y, x]
    return in_bounds & np.isfinite(depth) & ((owner == triangle_id) | (expected_depth <= depth + buffers["z_tolerance"]))


def compute_triangle_visibility(
    vertices_3d: np.ndarray,
    triangles: np.ndarray,
    view_dir: Optional[np.ndarray] = None,
    angle_threshold_deg: float = 85.0,
    gamma: float = 1.5,
    use_zbuffer: bool = False,
    vertices_2d: Optional[np.ndarray] = None,
    image_size: Optional[tuple[int, int]] = None,
    z_tolerance: float = 1e-3,
    occlusion_falloff: float = 0.1,
    return_buffers: bool = False,
) -> np.ndarray | tuple[np.ndarray, dict]:
    """Return per-triangle visibility weights in the [0, 1] range.

    Args:
        vertices_3d: (N, 3) vertex positions in camera space.
        triangles: (T, 3) triangle indices.
        view_dir: Optional (3,) view direction. Defaults to +Z.
        angle_threshold_deg: Maximum allowed angle between normal and view dir.
        gamma: Falloff exponent applied to cos(angle).
        use_zbuffer: Enable full triangle-rasterized depth visibility.
        vertices_2d: (N, 2) projected vertices (required for z-buffer mode).
        image_size: (H, W) image resolution for z-buffer grid.
        z_tolerance: Allowed depth slack before marking as occluded.
        occlusion_falloff: Legacy argument; occluded triangles now receive zero analytical weight.

    Returns:
        (T,) float32 weights.
    """

    verts = np.asarray(vertices_3d, dtype=np.float32)
    tris = np.asarray(triangles, dtype=np.int64)
    if tris.ndim != 2 or tris.shape[1] != 3:
        raise ValueError("triangles must have shape (T, 3)")

    if view_dir is None:
        view_dir = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    else:
        view_dir = np.asarray(view_dir, dtype=np.float32)

    view_norm = np.linalg.norm(view_dir)
    if view_norm < 1e-8:
        raise ValueError("view_dir magnitude is too small")
    view = view_dir / view_norm

    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]

    normals = np.cross(v1 - v0, v2 - v0)
    norm_len = np.linalg.norm(normals, axis=1, keepdims=True)
    valid_normals = norm_len.squeeze(-1) > 1e-8
    normals = np.divide(
        normals,
        np.maximum(norm_len, 1e-8),
        out=np.zeros_like(normals),
        where=norm_len > 1e-8,
    )

    cos_angle = np.clip((normals @ view).astype(np.float32), -1.0, 1.0)
    front = valid_normals & (cos_angle > 0)
    mask = front & (cos_angle >= np.cos(np.deg2rad(angle_threshold_deg)))

    weights = np.zeros(tris.shape[0], dtype=np.float32)
    weights[mask] = np.power(cos_angle[mask], gamma).astype(np.float32)
    buffers = None

    if use_zbuffer:
        if vertices_2d is None or image_size is None:
            raise ValueError("z-buffer requires original-pixel projections and image size")
        else:
            buffers = rasterize_depth(vertices_2d, verts[:, 2], tris, image_size, front)
            buffers.update({"z_tolerance": float(z_tolerance), "vertex_depth": verts[:, 2], "front_facing": front})
            projected = np.asarray(vertices_2d)[tris]
            centres = projected.mean(axis=1)
            expected = 1 / np.mean(1 / verts[tris, 2], axis=1)
            visible = query_visibility(centres, expected, np.arange(len(tris)), buffers)
            for corner in range(3):
                visible |= query_visibility(projected[:, corner], verts[tris[:, corner], 2], np.arange(len(tris)), buffers)
            weights[~visible] = 0

    logger.debug(
        "Visibility: %d/%d total valid normal tris processed for occlusion",
        int(mask.sum()),
        tris.shape[0],
    )

    return (weights, buffers) if return_buffers else weights


def compute_vertex_visibility(
    triangles: np.ndarray,
    tri_weights: np.ndarray,
    num_vertices: Optional[int] = None,
) -> np.ndarray:
    """Map per-triangle weights to per-vertex visibility via averaging."""

    tris = np.asarray(triangles, dtype=np.int64)
    weights = np.asarray(tri_weights, dtype=np.float32).reshape(-1)
    if tris.shape[0] != weights.shape[0]:
        raise ValueError("triangles and tri_weights must have the same length")

    if num_vertices is None:
        num_vertices = int(tris.max()) + 1 if tris.size > 0 else 0

    vert_sum = np.zeros(num_vertices, dtype=np.float64)
    vert_count = np.zeros(num_vertices, dtype=np.float64)

    for j in range(3):
        np.add.at(vert_sum, tris[:, j], weights)
        np.add.at(vert_count, tris[:, j], 1.0)

    vert_count = np.maximum(vert_count, 1e-6)
    return (vert_sum / vert_count).astype(np.float32)
