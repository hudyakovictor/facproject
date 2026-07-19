"""Static UV-space rasterization cache.

Key idea of the quality upgrade: the stock 3DDFA_V3 texture path first collapses
the photo to *per-vertex* colors (35,709 samples) and then rasterizes those into
UV space. All skin micro-detail between vertices is destroyed before it ever
reaches the texture.

Here we invert the mapping at *texel* level: for every texel of the UV atlas we
precompute (triangle id, barycentric coords) once -- the UV layout of the face
model never changes -- and per photo we only evaluate the barycentric mix of the
triangle's 2D image positions and sample the ORIGINAL photo directly with
Lanczos interpolation (cv2.remap). Detail is then limited only by the photo
itself, which is exactly what a forensic texture needs.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class UVRaster:
    """Per-texel triangle assignment for a fixed UV layout at a fixed grid size."""
    size: int                 # grid size (possibly supersampled)
    tri_map: np.ndarray       # (S, S) int32, -1 where no triangle covers the texel
    bary: np.ndarray          # (S, S, 3) float32 barycentric coords (0 outside)
    valid: np.ndarray         # (S, S) bool == tri_map >= 0


def uv_to_grid(uv_coords: np.ndarray, size: int) -> np.ndarray:
    """Map uv in [0,1]^2 to grid pixel coords. Row 0 of the atlas is v=1 (top),
    matching the standard OBJ convention and the flipped-y sampling used by
    3DDFA_V3's get_colors_from_uv."""
    uv = np.asarray(uv_coords, np.float64)[:, :2]
    xy = np.empty_like(uv)
    xy[:, 0] = uv[:, 0] * (size - 1)
    xy[:, 1] = (1.0 - uv[:, 1]) * (size - 1)
    return xy.astype(np.float64)


def _layout_hash(uv_coords: np.ndarray, triangles: np.ndarray, size: int) -> str:
    h = hashlib.sha1()
    h.update(np.ascontiguousarray(uv_coords[:, :2], np.float32).tobytes())
    h.update(np.ascontiguousarray(triangles, np.int64).tobytes())
    h.update(str(int(size)).encode())
    return h.hexdigest()[:16]


def build_uv_raster(uv_coords: np.ndarray, triangles: np.ndarray, size: int) -> UVRaster:
    """Rasterize the UV triangulation into a texel->triangle map with barycentrics.

    O(#triangles) fillConvexPoly passes (one-off; result is cached on disk).
    """
    tri = np.asarray(triangles, np.int64)
    xy = uv_to_grid(uv_coords, size)

    tri_map = np.full((size, size), -1, np.int32)
    # Paint triangle indices. Overlaps in a proper UV atlas are negligible;
    # later triangles win deterministically.
    pts_all = xy[tri]  # (M, 3, 2)
    for i in range(tri.shape[0]):
        p = np.round(pts_all[i]).astype(np.int32)
        cv2.fillConvexPoly(tri_map, p, int(i))
    # Also paint exact vertex texels to reduce pinholes on thin triangles.
    vx = np.clip(np.round(xy[:, 0]).astype(np.int64), 0, size - 1)
    vy = np.clip(np.round(xy[:, 1]).astype(np.int64), 0, size - 1)
    empty = tri_map[vy, vx] < 0
    if np.any(empty):
        first_tri = np.full(uv_coords.shape[0], -1, np.int64)
        for c in range(3):
            col = tri[:, c]
            unset = first_tri[col] < 0
            first_tri[col[unset]] = np.nonzero(unset)[0] if False else np.arange(tri.shape[0])[unset]
        first_tri = np.maximum(first_tri, 0)
        tri_map[vy[empty], vx[empty]] = first_tri[empty].astype(np.int32)

    valid = tri_map >= 0
    ys, xs = np.nonzero(valid)
    t = tri_map[ys, xs].astype(np.int64)
    a = xy[tri[t, 0]]
    b = xy[tri[t, 1]]
    c = xy[tri[t, 2]]
    p = np.stack([xs, ys], axis=1).astype(np.float64)

    v0 = b - a
    v1 = c - a
    v2 = p - a
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
    w = np.stack([w0, w1, w2], axis=1)
    # Rounding can push edge texels slightly outside: clamp and renormalize.
    w = np.clip(w, 0.0, 1.0)
    s = np.sum(w, axis=1, keepdims=True)
    s = np.where(s < 1e-12, 1.0, s)
    w = w / s

    bary = np.zeros((size, size, 3), np.float32)
    bary[ys, xs] = w.astype(np.float32)
    return UVRaster(size=size, tri_map=tri_map, bary=bary, valid=valid)


def load_or_build_uv_raster(
    uv_coords: np.ndarray,
    triangles: np.ndarray,
    size: int,
    cache_dir: Path | None = None,
) -> UVRaster:
    key = _layout_hash(np.asarray(uv_coords), np.asarray(triangles), size)
    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        f = cache_dir / f"uv_raster_{size}_{key}.npz"
        if f.is_file():
            try:
                z = np.load(f)
                return UVRaster(size=size, tri_map=z["tri_map"], bary=z["bary"], valid=z["tri_map"] >= 0)
            except Exception:
                f.unlink(missing_ok=True)
    raster = build_uv_raster(uv_coords, triangles, size)
    if cache_dir is not None:
        tmp = cache_dir / f".tmp_uv_raster_{size}_{key}.npz"
        np.savez_compressed(tmp, tri_map=raster.tri_map, bary=raster.bary)
        tmp.replace(cache_dir / f"uv_raster_{size}_{key}.npz")
    return raster


def interpolate_vertex_attribute(raster: UVRaster, triangles: np.ndarray, attr: np.ndarray) -> np.ndarray:
    """Barycentric interpolation of a per-vertex attribute onto the UV grid.

    attr: (N,) or (N, C). Returns (S, S) or (S, S, C) float32, zeros outside atlas.
    """
    tri = np.asarray(triangles, np.int64)
    a = np.asarray(attr, np.float32)
    squeeze = a.ndim == 1
    if squeeze:
        a = a[:, None]
    S = raster.size
    out = np.zeros((S, S, a.shape[1]), np.float32)
    ys, xs = np.nonzero(raster.valid)
    t = raster.tri_map[ys, xs].astype(np.int64)
    w = raster.bary[ys, xs]  # (K, 3)
    vals = (
        a[tri[t, 0]] * w[:, 0:1]
        + a[tri[t, 1]] * w[:, 1:2]
        + a[tri[t, 2]] * w[:, 2:3]
    )
    out[ys, xs] = vals
    return out[..., 0] if squeeze else out
