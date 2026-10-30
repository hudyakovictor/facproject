"""Software UV-textured mesh renderer for offline texture checks."""

import numpy as np
from PIL import Image


def render(verts, tri, uv, atlas, out, yaw_deg=0, size=560):
    arr = np.asarray(atlas)
    S = arr.shape[0]
    canvas = np.zeros((size, size, 3), np.uint8)
    zbuf = np.full((size, size), 1e9, np.float32)
    yaw = np.radians(yaw_deg)
    cy, sy = np.cos(yaw), np.sin(yaw)
    x = verts[:, 0] * cy + verts[:, 2] * sy
    z = -verts[:, 0] * sy + verts[:, 2] * cy
    px = (x * 0.34 + 0.5) * size
    py = (0.5 - (verts[:, 1] + 0.41) * 0.34) * size
    depth = -z
    for t in tri:
        i0, i1, i2 = t
        x0, y0, x1, y1, x2, y2 = px[i0], py[i0], px[i1], py[i1], px[i2], py[i2]
        minx = max(int(np.floor(min(x0, x1, x2))), 0)
        maxx = min(int(np.ceil(max(x0, x1, x2))), size - 1)
        miny = max(int(np.floor(min(y0, y1, y2))), 0)
        maxy = min(int(np.ceil(max(y0, y1, y2))), size - 1)
        if maxx < minx or maxy < miny:
            continue
        det2 = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(det2) < 1e-12:
            continue
        xs = np.arange(minx, maxx + 1) + 0.5
        ys = np.arange(miny, maxy + 1)[:, None] + 0.5
        w0 = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / det2
        w1 = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / det2
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        z = w0 * depth[i0] + w1 * depth[i1] + w2 * depth[i2]
        yy, xx = np.where(inside)
        zz = z[yy, xx]
        sub = zbuf[miny : miny + len(ys), minx : minx + len(xs)]
        better = zz < sub[yy, xx]
        if not better.any():
            continue
        yy, xx, zz = yy[better], xx[better], zz[better]
        u = w0[yy, xx] * uv[i0, 0] + w1[yy, xx] * uv[i1, 0] + w2[yy, xx] * uv[i2, 0]
        vv = w0[yy, xx] * uv[i0, 1] + w1[yy, xx] * uv[i1, 1] + w2[yy, xx] * uv[i2, 1]
        ax = np.clip((u * (S - 1)).astype(int), 0, S - 1)
        ay = np.clip(((1 - vv) * (S - 1)).astype(int), 0, S - 1)
        gy, gx = yy + miny, xx + minx
        canvas[gy, gx] = arr[ay, ax]
        zbuf[gy, gx] = zz
    Image.fromarray(canvas).save(out)
    return canvas


def masked_share(atlas, uv, tri, mask):
    """Fraction of *kept* atlas coverage that ends up black on the mesh."""
    return float((atlas.sum(-1) == 0).mean())
