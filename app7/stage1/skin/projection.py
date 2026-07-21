"""Surface rasterization + atlas projection.

Projects 3D mesh onto original-image crop, assigns atlas zone IDs,
computes incidence, visibility, projection confidence, and projected density.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BACKGROUND_TRIANGLE = -1


@dataclass
class RasterResult:
    triangle_id: np.ndarray
    barycentric: np.ndarray
    depth: np.ndarray
    normal: np.ndarray
    incidence: np.ndarray
    visibility: np.ndarray
    projection_confidence: np.ndarray
    source_xy: np.ndarray
    projected_density_map: np.ndarray


def rasterize_surface(
    vertices_xy, vertices_z, normals, triangles, image_shape,
    vertex_visibility=None, near="min",
    surface_vertices=None, triangle_surface_areas=None,
):
    """Z-buffer rasterization of mesh onto image plane.

    Args:
        vertices_xy: Vx2 image-space coordinates (original image pixels)
        vertices_z: V depth values
        normals: Vx3 normals (posed)
        triangles: Fx3 triangle indices
        image_shape: (H, W)
        vertex_visibility: V float 0..1 (combined visibility)
        surface_vertices: Vx3 for surface area computation
        triangle_surface_areas: F precomputed triangle areas

    Returns:
        RasterResult with per-pixel triangle assignments and geometry
    """
    xy = np.asarray(vertices_xy, np.float32)[:, :2]
    z = np.asarray(vertices_z, np.float32).reshape(-1)
    n = np.asarray(normals, np.float32)
    f = np.asarray(triangles, np.int64)
    H, W = map(int, image_shape[:2])

    tid = np.full((H, W), BACKGROUND_TRIANGLE, np.int32)
    depth = np.full((H, W), np.inf if near == "min" else -np.inf, np.float32)
    bar = np.zeros((H, W, 3), np.float32)
    normal = np.zeros((H, W, 3), np.float32)
    vv = np.ones(len(z), np.float32) if vertex_visibility is None else np.asarray(vertex_visibility, np.float32)

    # Compute triangle surface areas if not provided
    if triangle_surface_areas is None and surface_vertices is not None:
        try:
            sv = np.asarray(surface_vertices, np.float64)
            v0 = sv[f[:, 0]]; v1 = sv[f[:, 1]]; v2 = sv[f[:, 2]]
            triangle_surface_areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1).astype(np.float32)
        except Exception:
            triangle_surface_areas = None

    # Per-triangle rasterization
    for fi, t in enumerate(f):
        p = xy[t]
        xmin = max(0, int(np.floor(p[:, 0].min())))
        xmax = min(W - 1, int(np.ceil(p[:, 0].max())))
        ymin = max(0, int(np.floor(p[:, 1].min())))
        ymax = min(H - 1, int(np.ceil(p[:, 1].max())))
        if xmax < xmin or ymax < ymin:
            continue
        den = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(float(den)) < 1e-10:
            continue
        yy, xx = np.mgrid[ymin:ymax + 1, xmin:xmax + 1]
        px = xx + 0.5
        py = yy + 0.5
        b0 = ((p[1, 1] - p[2, 1]) * (px - p[2, 0]) + (p[2, 0] - p[1, 0]) * (py - p[2, 1])) / den
        b1 = ((p[2, 1] - p[0, 1]) * (px - p[2, 0]) + (p[0, 0] - p[2, 0]) * (py - p[2, 1])) / den
        b2 = 1 - b0 - b1
        inside = (b0 >= -1e-5) & (b1 >= -1e-5) & (b2 >= -1e-5)
        if not inside.any():
            continue
        dz = b0 * z[t[0]] + b1 * z[t[1]] + b2 * z[t[2]]
        old = depth[ymin:ymax + 1, xmin:xmax + 1]
        take = inside & ((dz < old) if near == "min" else (dz > old))
        if not take.any():
            continue
        old[take] = dz[take]
        tid[ymin:ymax + 1, xmin:xmax + 1][take] = fi
        bar[ymin:ymax + 1, xmin:xmax + 1][take] = np.stack((b0, b1, b2), -1)[take]
        ni = b0[..., None] * n[t[0]] + b1[..., None] * n[t[1]] + b2[..., None] * n[t[2]]
        normal[ymin:ymax + 1, xmin:xmax + 1][take] = ni[take]

    # Post-process
    bg = tid < 0
    depth[bg] = np.nan
    norm = np.linalg.norm(normal, axis=2, keepdims=True)
    normal = np.divide(normal, norm, out=np.zeros_like(normal), where=norm > 1e-8)
    signed = normal[..., 2]
    median_signed = float(np.nanmedian(signed[~bg])) if np.any(~bg) else 1.0
    pol = -1 if median_signed < 0 else 1
    inc = np.clip(pol * signed, 0, 1).astype(np.float32)
    inc[bg] = 0

    vis = np.zeros((H, W), np.float32)
    valid = ~bg
    ft = f[np.clip(tid, 0, len(f) - 1)]
    vis[valid] = np.min(vv[ft[valid]], axis=1)

    # Confidence: visibility * sqrt(incidence), smoothed to remove mesh grid
    conf = (vis * np.sqrt(np.clip(inc, 0.0, 1.0))).astype(np.float32)
    conf[bg] = 0
    try:
        import cv2 as _cv2
        m = ~bg
        if np.any(m):
            cs = _cv2.GaussianBlur(conf, (0, 0), 1.2)
            conf = np.where(m, cs, 0.0).astype(np.float32)
    except Exception:
        pass

    # Source pixel coordinates
    yy2, xx2 = np.mgrid[:H, :W]
    source = np.stack((xx2, yy2), axis=2).astype(np.int32)
    source[bg] = -1

    # Projected density: screen pixels per surface area
    projected_density = np.zeros((H, W), dtype=np.float32)
    if triangle_surface_areas is not None and len(triangle_surface_areas) == len(f):
        unique, counts = np.unique(tid[valid], return_counts=True)
        for t_id, cnt in zip(unique, counts):
            sa = float(triangle_surface_areas[int(t_id)]) if int(t_id) < len(triangle_surface_areas) else 1.0
            projected_density[tid == t_id] = cnt / max(sa, 1e-9)
    else:
        unique, counts = np.unique(tid[valid], return_counts=True)
        for t_id, cnt in zip(unique, counts):
            projected_density[tid == t_id] = np.sqrt(float(cnt))

    return RasterResult(tid, bar, depth, normal, inc, vis, conf, source, projected_density)


def project_atlas(raster: RasterResult, atlas, skin_segmentation=None) -> dict:
    """Project atlas zone memberships onto rasterized pixels."""
    tid = raster.triangle_id
    valid = tid >= 0
    A_atlas = atlas.A
    S_atlas = atlas.S
    skin_atlas = atlas.skin
    W_atlas = atlas.W
    boundary_atlas = atlas.boundary

    safe = np.clip(tid, 0, len(A_atlas) - 1)
    seg = np.ones(tid.shape, bool) if skin_segmentation is None else np.asarray(skin_segmentation, bool)
    try:
        skin_mask = skin_atlas[safe]
    except Exception:
        skin_mask = np.ones(tid.shape, bool)
    domain = valid & seg & skin_mask

    A = np.full(tid.shape, -1, np.int8)
    S = np.full(tid.shape, -1, np.int8)
    A[domain] = A_atlas[safe[domain]]
    S[domain] = S_atlas[safe[domain]]

    W = np.zeros((14, *tid.shape), bool)
    for k in range(14):
        try:
            W[k] = domain & W_atlas[k, safe]
        except Exception:
            W[k] = False

    bd = np.zeros(tid.shape, np.uint8)
    try:
        bd[domain] = boundary_atlas[safe[domain]]
    except Exception:
        pass

    return {
        "zone_id_a20": A,
        "zone_id_s40": S,
        "wrinkle_membership_w14": W,
        "boundary_distance": bd,
        "domain_mask": domain,
        "projected_density_map": raster.projected_density_map,
    }
