"""
Drop-in replacement for app6/stage1/skin/projection.py (actually app6/stage1/skin/projection wrapper around uv module? 
Original file at app6/stage1/skin/projection.py wraps rasterize_surface.

We patch the underlying rasterizer to compute projected_density_map physics.

This file replaces app6/stage1/skin/projection.py AND adds compatibility for new quality_maps signature.

Original functions to keep same names:
- rasterize_surface(...)
- project_atlas(...)

Enhancements:
- rasterize_surface returns RasterResult with additional projected_density_map (screen pixels per surface area)
- Need triangle surface areas: compute from surface_vertices if provided? We add optional param surface_vertices + triangles to rasterize for density.

For drop-in, we keep original signature but add **kwargs to accept surface_vertices, triangles, triangle_surface_areas.
If not provided, fallback to heuristic _scale.

Also project_atlas now also returns projected_density_map for quality.

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
    # new v4 field with default for backward compat
    projected_density_map: np.ndarray = None
    triangle_surface_area: np.ndarray = None

def rasterize_surface(vertices_xy, vertices_z, normals, triangles, image_shape, vertex_visibility=None, near='min', surface_vertices=None, triangle_surface_areas=None):
    """
    Drop-in: original args + optional surface_vertices, triangle_surface_areas for physics fix
    vertices_xy: Vx2 image coords (original image)
    vertices_z: V depth
    normals: Vx3
    triangles: Fx3 indices
    image_shape: (H,W)
    vertex_visibility: V float 0..1

    Returns RasterResult with projected_density_map
    """
    xy = np.asarray(vertices_xy, np.float32)[:, :2]
    z = np.asarray(vertices_z, np.float32).reshape(-1)
    n = np.asarray(normals, np.float32)
    f = np.asarray(triangles, np.int64)
    H,W = map(int, image_shape[:2])
    if xy.shape != (len(z),2) or n.shape != (len(z),3):
        raise ValueError('vertex array shape mismatch')
    tid = np.full((H,W), BACKGROUND_TRIANGLE, np.int32)
    depth = np.full((H,W), np.inf if near=='min' else -np.inf, np.float32)
    bar = np.zeros((H,W,3), np.float32)
    normal = np.zeros((H,W,3), np.float32)
    vv = np.ones(len(z), np.float32) if vertex_visibility is None else np.asarray(vertex_visibility, np.float32)
    # for density: count pixels per triangle
    # We'll also need surface areas
    if triangle_surface_areas is None and surface_vertices is not None:
        try:
            sv = np.asarray(surface_vertices, np.float64)
            # compute area per triangle: 0.5*|cross(v1-v0, v2-v0)|
            v0 = sv[f[:,0]]; v1 = sv[f[:,1]]; v2 = sv[f[:,2]]
            cross = np.cross(v1-v0, v2-v0)
            area = 0.5*np.linalg.norm(cross, axis=1).astype(np.float32)
            triangle_surface_areas = area
        except Exception:
            triangle_surface_areas = None

    for fi,t in enumerate(f):
        p = xy[t]
        xmin = max(0, int(np.floor(p[:,0].min())))
        xmax = min(W-1, int(np.ceil(p[:,0].max())))
        ymin = max(0, int(np.floor(p[:,1].min())))
        ymax = min(H-1, int(np.ceil(p[:,1].max())))
        if xmax<xmin or ymax<ymin:
            continue
        den = (p[1,1]-p[2,1])*(p[0,0]-p[2,0]) + (p[2,0]-p[1,0])*(p[0,1]-p[2,1])
        if abs(float(den)) < 1e-10:
            continue
        yy,xx = np.mgrid[ymin:ymax+1, xmin:xmax+1]
        px = xx + 0.5
        py = yy + 0.5
        b0 = ((p[1,1]-p[2,1])*(px-p[2,0]) + (p[2,0]-p[1,0])*(py-p[2,1]))/den
        b1 = ((p[2,1]-p[0,1])*(px-p[2,0]) + (p[0,0]-p[2,0])*(py-p[2,1]))/den
        b2 = 1 - b0 - b1
        inside = (b0 >= -1e-5) & (b1 >= -1e-5) & (b2 >= -1e-5)
        if not inside.any():
            continue
        dz = b0*z[t[0]] + b1*z[t[1]] + b2*z[t[2]]
        old = depth[ymin:ymax+1, xmin:xmax+1]
        take = inside & ((dz < old) if near=='min' else (dz > old))
        if not take.any():
            continue
        old[take] = dz[take]
        T = tid[ymin:ymax+1, xmin:xmax+1]
        T[take] = fi
        B = bar[ymin:ymax+1, xmin:xmax+1]
        B[take] = np.stack((b0,b1,b2), -1)[take]
        N = normal[ymin:ymax+1, xmin:xmax+1]
        ni = b0[...,None]*n[t[0]] + b1[...,None]*n[t[1]] + b2[...,None]*n[t[2]]
        N[take] = ni[take]

    bg = tid < 0
    depth[bg] = np.nan
    norm = np.linalg.norm(normal, axis=2, keepdims=True)
    normal = np.divide(normal, norm, out=np.zeros_like(normal), where=norm>1e-8)
    signed = normal[...,2]
    # polarity: determine front facing via median
    try:
        median_signed = np.nanmedian(signed[~bg]) if np.any(~bg) else 1.0
    except:
        median_signed = 1.0
    pol = -1 if median_signed < 0 else 1
    inc = np.clip(pol*signed, 0, 1).astype(np.float32)
    inc[bg] = 0
    vis = np.zeros((H,W), np.float32)
    valid = ~bg
    ft = f[np.clip(tid,0,len(f)-1)]
    vis[valid] = np.min(vv[ft[valid]], axis=1)
    edge = np.clip(3.0 * np.min(bar, axis=2), 0.0, 1.0).astype(np.float32)
    # NOTE: do NOT multiply conf by barycentric edge — it imprints triangle mesh onto quality renders.
    conf = (vis * np.sqrt(np.clip(inc, 0.0, 1.0))).astype(np.float32)
    conf[bg] = 0
    
    try:
        import cv2 as _cv2
        _m = ~bg
        if np.any(_m):
            _cs = _cv2.GaussianBlur(conf, (0, 0), 1.2)
            conf = np.where(_m, _cs, 0.0).astype(np.float32)
    except Exception:
        pass
    yy,xx = np.mgrid[:H,:W]
    source = np.stack((xx,yy), axis=2).astype(np.int32)
    source[bg] = -1

    # projected density map: pixels per surface area
    projected_density = np.zeros((H,W), dtype=np.float32)
    if triangle_surface_areas is not None and len(triangle_surface_areas)==len(f):
        # count pixels per triangle id
        unique, counts = np.unique(tid[valid], return_counts=True)
        for t_id, cnt in zip(unique, counts):
            sa = float(triangle_surface_areas[int(t_id)]) if int(t_id)<len(triangle_surface_areas) else 1.0
            if sa < 1e-9:
                sa = 1e-9
            # density = screen pixel count / surface area
            # but need per pixel, so assign count/sa to each pixel of that triangle (approx)
            # For better accuracy, distribute uniformly
            projected_density[tid==t_id] = cnt / sa
    else:
        # fallback heuristic: sqrt(count) as before but as density proxy
        # compute sqrt(count) map
        unique, counts = np.unique(tid[valid], return_counts=True)
        q = np.zeros(int(unique.max())+1 if len(unique) else 1, dtype=np.float32)
        q[unique] = np.sqrt(counts.astype(np.float32))
        # assign
        # we need map same shape
        for t_id, cnt in zip(unique, counts):
            # heuristic density = sqrt(cnt) (old) but we treat as density already
            projected_density[tid==t_id] = np.sqrt(float(cnt))

    return RasterResult(tid, bar, depth, normal, inc, vis, conf, source, projected_density_map=projected_density, triangle_surface_area=np.asarray(triangle_surface_areas) if triangle_surface_areas is not None else None)

def project_atlas(raster, atlas, skin_segmentation=None):
    """
    Same signature as original, returns dict with zone_id_a20 etc + projected_density_map
    """
    tid = raster.triangle_id
    valid = tid >= 0
    # atlas may have different attribute names? Original code uses atlas.A, atlas.S, atlas.skin, atlas.W, atlas.boundary
    # Keep compat
    try:
        A_atlas = atlas.A
        S_atlas = atlas.S
        skin_atlas = atlas.skin
        W_atlas = atlas.W
        boundary_atlas = atlas.boundary
    except AttributeError:
        # fallback for different registry
        A_atlas = getattr(atlas, 'A', np.zeros(len(atlas.skin) if hasattr(atlas,'skin') else 1))
        S_atlas = getattr(atlas, 'S', A_atlas)
        skin_atlas = getattr(atlas, 'skin', np.ones(1000, bool))
        W_atlas = getattr(atlas, 'W', np.zeros((14, 1000), bool))
        boundary_atlas = getattr(atlas, 'boundary', np.zeros(1000, np.uint8))

    safe = np.clip(tid, 0, len(A_atlas)-1) if hasattr(A_atlas,'__len__') else tid
    seg = np.ones(tid.shape, bool) if skin_segmentation is None else np.asarray(skin_segmentation, bool)
    try:
        skin_mask = skin_atlas[safe]
    except:
        skin_mask = np.ones(tid.shape, bool)
    domain = valid & seg & skin_mask
    A = np.full(tid.shape, -1, np.int8)
    S = np.full(tid.shape, -1, np.int8)
    A[domain] = A_atlas[safe[domain]] if A_atlas is not None else -1
    S[domain] = S_atlas[safe[domain]] if S_atlas is not None else -1
    W = np.zeros((14, *tid.shape), bool)
    for k in range(14):
        try:
            W[k] = domain & W_atlas[k, safe]
        except:
            W[k] = False
    bd = np.zeros(tid.shape, np.uint8)
    try:
        bd[domain] = boundary_atlas[safe[domain]]
    except:
        pass

    # projected density for quality
    proj_density = getattr(raster, 'projected_density_map', None)
    if proj_density is None:
        proj_density = np.zeros(tid.shape, np.float32)

    return {
        'zone_id_a20': A,
        'zone_id_s40': S,
        'wrinkle_bits_w14': np.packbits(W, axis=0, bitorder='little'),
        'wrinkle_membership_w14': W,
        'boundary_distance': bd,
        'domain_mask': domain,
        'projected_density_map': proj_density,  # new for v4 physics
    }
