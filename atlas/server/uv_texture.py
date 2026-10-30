"""Barycentric-style per-triangle photo-to-template UV texture baking.

Keeps the 3DDFA template UV topology unchanged. Source image coordinates are
projected model vertices; pixels are sampled into the model's canonical UV atlas.
"""
from __future__ import annotations
import cv2
import numpy as np


def facing_mask(source_uv: np.ndarray, template_uv: np.ndarray,
                triangles: np.ndarray, width: int, height: int,
                min_area: float = 0.5) -> np.ndarray:
    """Select triangles that actually face the camera in the source photo.

    A triangle whose projection mirrors the template winding shows the far side
    of the head through the face; baking it paints a ghost eye on the near
    cheek. Nearly edge-on triangles cover a sub-pixel sliver of the photo, which
    smears into long streaks, so they need at least ``min_area`` source pixels.
    """
    src = np.asarray(source_uv, np.float64)
    tpl = np.asarray(template_uv, np.float64)
    tri = np.asarray(triangles, np.int32)
    if src.shape != tpl.shape or src.ndim != 2 or src.shape[1] != 2:
        raise ValueError("source_uv and template_uv must share the same (N, 2) shape")
    if tri.ndim != 2 or tri.shape[1] != 3:
        raise ValueError("triangles must have shape (T, 3)")

    def signed(points):
        a, b, c = points[tri[:, 0]], points[tri[:, 1]], points[tri[:, 2]]
        return 0.5 * (
            (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
            - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
        )

    # Both areas are measured with y pointing down, as in the atlas and the
    # source image, so a correctly oriented triangle keeps the same sign.
    src_px = np.column_stack((src[:, 0] * (width - 1), (1 - src[:, 1]) * (height - 1)))
    tpl_px = np.column_stack((tpl[:, 0], 1 - tpl[:, 1]))
    source_area = signed(src_px)
    template_area = signed(tpl_px)
    oriented = np.sign(source_area) == np.sign(template_area)
    return oriented & (np.abs(source_area) >= min_area)


def bake_photo_to_uv(image_rgb: np.ndarray, source_uv: np.ndarray,
                     template_uv: np.ndarray, triangles: np.ndarray,
                     size: int = 1024, faces: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(image_rgb)
    if image.ndim != 3 or image.shape[2] != 3 or image.shape[0] < 2 or image.shape[1] < 2:
        raise ValueError("image_rgb must be a non-empty HxWx3 image")
    size = int(size)
    if size < 2:
        raise ValueError("UV atlas size must be at least 2 pixels")
    if not np.isfinite(image).all():
        raise ValueError("image pixels must be finite")
    if image.dtype != np.uint8:
        scale = 255.0 if np.issubdtype(image.dtype, np.floating) and image.max(initial=0) <= 1.0 else 1.0
        image = np.clip(image.astype(np.float32) * scale, 0, 255).astype(np.uint8)
    h, w = image.shape[:2]
    src = np.asarray(source_uv, np.float32)
    uv = np.asarray(template_uv, np.float32)
    tri_raw = np.asarray(triangles)
    if src.ndim != 2 or src.shape[1] != 2 or uv.ndim != 2 or uv.shape[1] != 2:
        raise ValueError("source_uv and template_uv must have shape (N, 2)")
    if tri_raw.ndim != 2 or tri_raw.shape[1] != 3 or tri_raw.size == 0:
        raise ValueError("triangles must have shape (T, 3) and contain at least one face")
    if len(src) != len(uv) or not np.isfinite(src).all() or not np.isfinite(uv).all():
        raise ValueError("UV coordinates must be finite and share the same topology")
    if not np.issubdtype(tri_raw.dtype, np.integer):
        if not np.isfinite(tri_raw).all() or not np.equal(tri_raw, np.floor(tri_raw)).all():
            raise ValueError("triangle indices must be integers")
    tri = tri_raw.astype(np.int32, copy=False)
    if tri.min() < 0 or tri.max() >= len(src):
        raise ValueError("triangle index is outside the UV vertex array")
    if faces is not None:
        keep = np.asarray(faces, dtype=bool).reshape(-1)
        if len(keep) != len(tri):
            raise ValueError("faces must have one entry per triangle")
        tri = tri[keep]
    # Atlas row zero corresponds to v=1. Three.js TextureLoader's flipY=true
    # then presents this convention with the unmodified template UVs.
    dst_all = np.column_stack((uv[:, 0] * (size - 1), (1.0 - uv[:, 1]) * (size - 1)))
    src_all = np.column_stack((src[:, 0] * (w - 1), (1.0 - src[:, 1]) * (h - 1)))
    accum = np.zeros((size, size, 3), np.float32)
    weights = np.zeros((size, size), np.float32)
    for ids in tri:
        dst = dst_all[ids]
        image_pts = src_all[ids]
        if abs(cv2.contourArea(dst.astype(np.float32))) < .15:
            continue
        x0, y0 = np.floor(dst.min(0)).astype(int)
        x1, y1 = np.ceil(dst.max(0)).astype(int)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(size - 1, x1), min(size - 1, y1)
        if x1 <= x0 or y1 <= y0:
            continue
        local = dst - np.array([x0, y0], np.float32)
        mask = np.zeros((y1-y0+1, x1-x0+1), np.uint8)
        cv2.fillConvexPoly(mask, np.round(local).astype(np.int32), 1)
        yy, xx = np.where(mask != 0)
        if not len(xx):
            continue
        # Exact affine UV->source-image mapping for this mesh triangle.
        mat = cv2.getAffineTransform(dst.astype(np.float32), image_pts.astype(np.float32))
        xy = mat @ np.vstack((xx + x0, yy + y0, np.ones(len(xx), np.float32)))
        inside = (xy[0] >= 0) & (xy[0] <= w-1) & (xy[1] >= 0) & (xy[1] <= h-1)
        if not np.any(inside):
            continue
        valid = np.flatnonzero(inside)
        X, Y = xx[valid] + x0, yy[valid] + y0
        # OpenCV remap has a signed-short limit on each map dimension. Chunk
        # broad triangles instead of passing a huge 1xN map (e.g. 4K atlas).
        for start in range(0, len(valid), 30000):
            ix = valid[start:start + 30000]
            sampled = cv2.remap(
                image,
                xy[0, ix].astype(np.float32).reshape(1, -1),
                xy[1, ix].astype(np.float32).reshape(1, -1),
                cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            ).reshape(-1, 3)
            stop = start + len(ix)
            accum[Y[start:stop], X[start:stop]] += sampled.astype(np.float32)
            weights[Y[start:stop], X[start:stop]] += 1
    visible = weights > 0
    atlas = np.zeros_like(accum, dtype=np.uint8)
    atlas[visible] = np.clip(accum[visible] / weights[visible, None], 0, 255).astype(np.uint8)
    # Fill only 1-pixel rasterization cracks immediately adjacent to observed
    # texels. Do not inpaint the entire unseen UV island or invent a back face.
    if visible.any():
        near = cv2.dilate(visible.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1) > 0
        cracks = near & ~visible
        if cracks.any():
            nearest = cv2.inpaint(atlas, cracks.astype(np.uint8), 2, cv2.INPAINT_TELEA)
            atlas[cracks] = nearest[cracks]
    return atlas, visible.astype(np.uint8) * 255
