"""Per-vertex visibility for texture extraction (CPU only, no renderer).

Two independent signals, both required:
1. front-facing test from posed normals (camera-space n_z), used as a SOFT
   angle weight so grazing texels get low confidence instead of a hard cut;
2. self-occlusion test via a triangle-id z-buffer rasterized with OpenCV in
   image space.

v3 upgrade vs v1/v2: instead of painting a *constant* depth per triangle
(painter's algorithm), we paint triangle IDs back-to-front and then evaluate
the *barycentric-interpolated* depth of the covering triangle at every vertex
pixel. Constant-depth painting misclassifies vertices on steep geometry (nose
flanks, brow ridge, eye sockets) and produced the ragged false-occlusion holes
seen in v1/v2 analysis textures. A vertex is also trivially visible when the
covering triangle contains that vertex itself.

v3.2 upgrade vs v3: depth tolerance is scaled per-vertex by the cover triangle
footprint (fraction of the cover pixel actually covered by the triangle). On
profile shots the far-side forehead vertex sits behind a sliver-thin near-side
cheek triangle whose zbuffer pixel is only ~10% covered; the v3 constant
tolerance falsely occluded those vertices. Scaling tol by coverage fraction
makes occlusion tighter only when the cover is truly solid.

The camera-space depth sign convention of 3DDFA_V3 is auto-detected: whichever
direction makes front-facing vertices closer to the camera is used.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class VisibilityBundle:
    front_facing: np.ndarray       # (N,) bool
    occlusion_visible: np.ndarray  # (N,) bool (True = not occluded)
    combined: np.ndarray           # (N,) bool
    angle_weight: np.ndarray       # (N,) float32 in [0,1], soft grazing-angle weight
    tri_visibility: np.ndarray     # (M,) float32 fraction of visible corners


def _soft_step(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip((x - lo) / max(hi - lo, 1e-6), 0.0, 1.0).astype(np.float32)


def _auto_depth_sign(depth: np.ndarray, front: np.ndarray) -> np.ndarray:
    """Return depth remapped so that LARGER value == closer to camera."""
    if front.any() and (~front).any():
        if float(np.mean(depth[front])) >= float(np.mean(depth[~front])):
            return depth
        return -depth
    return depth


def compute_visibility(
    vertices_2d: np.ndarray,
    depth: np.ndarray,
    normals_posed: np.ndarray,
    triangles: np.ndarray,
    zbuffer_size: int = 768,
    depth_tolerance: float = 0.015,
    angle_soft_lo: float = 0.05,
    angle_soft_hi: float = 0.35,
    force_all_visible: bool = False,
) -> VisibilityBundle:
    v2d = np.asarray(vertices_2d, np.float64)[:, :2]
    tri = np.asarray(triangles, np.int64)
    n = np.asarray(normals_posed, np.float32)
    nz = n[:, 2]
    front = nz >= 0.0
    angle_w = _soft_step(nz, angle_soft_lo, angle_soft_hi)

    if force_all_visible:
        ones = np.ones(v2d.shape[0], bool)
        return VisibilityBundle(
            front_facing=ones, occlusion_visible=ones, combined=ones,
            angle_weight=np.ones(v2d.shape[0], np.float32),
            tri_visibility=np.ones(tri.shape[0], np.float32),
        )

    z = _auto_depth_sign(np.asarray(depth, np.float64).reshape(-1), front)

    # --- rasterize triangle-id buffer in a face-tight frame ---
    lo = v2d.min(axis=0)
    hi = v2d.max(axis=0)
    span = max(float((hi - lo).max()), 1e-6)
    scale = (zbuffer_size - 1) / span
    pix = (v2d - lo) * scale
    W = int(np.ceil((hi[0] - lo[0]) * scale)) + 2
    H = int(np.ceil((hi[1] - lo[1]) * scale)) + 2
    W, H = max(W, 4), max(H, 4)

    tri_depth = z[tri].mean(axis=1)
    order = np.argsort(tri_depth)  # far first, near last (near overwrites)
    id_buf = np.full((H, W), -1, np.int32)
    pts_all = np.round(pix[tri]).astype(np.int32)
    for i in order:
        cv2.fillConvexPoly(id_buf, pts_all[i], int(i))

    px = np.clip(np.round(pix[:, 0]).astype(np.int64), 0, W - 1)
    py = np.clip(np.round(pix[:, 1]).astype(np.int64), 0, H - 1)
    cover = id_buf[py, px].astype(np.int64)          # covering (nearest) triangle per vertex pixel

    zrange = max(float(z.max() - z.min()), 1e-6)
    base_tol = depth_tolerance * zrange

    N = v2d.shape[0]
    occ_visible = np.ones(N, bool)
    has_cover = cover >= 0
    if np.any(has_cover):
        c = cover[has_cover]
        vidx = np.nonzero(has_cover)[0]
        # trivially visible when the covering triangle contains the vertex itself
        own = (tri[c] == vidx[:, None]).any(axis=1)
        # barycentric-interpolated depth of covering triangle at the vertex pixel
        a2, b2, c2 = pix[tri[c, 0]], pix[tri[c, 1]], pix[tri[c, 2]]
        p = pix[vidx]
        v0 = b2 - a2
        v1 = c2 - a2
        v2 = p - a2
        d00 = np.einsum("ij,ij->i", v0, v0)
        d01 = np.einsum("ij,ij->i", v0, v1)
        d11 = np.einsum("ij,ij->i", v1, v1)
        d20 = np.einsum("ij,ij->i", v2, v0)
        d21 = np.einsum("ij,ij->i", v2, v1)
        denom = d00 * d11 - d01 * d01
        denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
        w1 = (d11 * d20 - d01 * d21) / denom
        w2 = (d00 * d21 - d01 * d20) / denom
        w0 = 1.0 - w1 - w2
        w = np.clip(np.stack([w0, w1, w2], axis=1), 0.0, 1.0)
        s = np.sum(w, axis=1, keepdims=True)
        w = w / np.where(s < 1e-12, 1.0, s)
        z_cover = (
            z[tri[c, 0]] * w[:, 0] + z[tri[c, 1]] * w[:, 1] + z[tri[c, 2]] * w[:, 2]
        )
        # v3.2: scale tolerance by barycentric footprint of the cover pixel
        # inside the cover triangle. min(w) tells how close the vertex pixel is
        # to the triangle edge; near 1 means the cover pixel lies fully inside
        # the triangle (solid cover), near 0 means just an edge sliver.
        coverage = np.clip(np.minimum(np.minimum(w[:, 0], w[:, 1]), w[:, 2]) * 3.0, 0.0, 1.0)
        tol = base_tol * (0.25 + 0.75 * coverage)
        occ_visible[vidx] = own | (z[vidx] >= (z_cover - tol))

    combined = front & occ_visible
    tri_vis = combined[tri].mean(axis=1).astype(np.float32)
    return VisibilityBundle(
        front_facing=front,
        occlusion_visible=occ_visible,
        combined=combined,
        angle_weight=angle_w * occ_visible.astype(np.float32),
        tri_visibility=tri_vis,
    )
