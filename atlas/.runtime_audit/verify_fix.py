"""End-to-end check of the shipped projection and baker on a cached photo."""

import glob, json, os, sys

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = "/Users/victorkhudyakov/work/atlas"
sys.path.insert(0, ROOT)

import server.models.tddfa as tddfa
from server.uv_texture import bake_photo_to_uv

tddfa.ASSETS = __import__("pathlib").Path("/Users/victorkhudyakov/work/3ddfa_v3/assets")
basis = tddfa.basis_arrays()
print("basis loaded, vertices:", len(basis["u"]) // 3)

pid = "2a29f955863593e6"
meta = json.load(open(f"{ROOT}/cache/{pid}/meta.json"))
record = next(p for p in json.load(open(f"{ROOT}/data/library.json"))["photos"] if p["id"] == pid)
feature = glob.glob(f"{ROOT}/cache/{pid}/features-*.npz")
key = meta.get("feature_key")
feature = [f for f in feature if key and key in f] or feature
alpha = np.load(feature[0], allow_pickle=True)["alpha"]
img = ImageOps.exif_transpose(Image.open(f"{ROOT}/{record['path']}")).convert("RGB")
W, H = img.size
alignment = meta["alignment"]
print("photo", img.size, "angles", {k: round(v, 1) for k, v in meta["angles"].items()})


def legacy_project(alpha, transpose):
    """Old in-place formula, kept only to report the regression delta."""
    a = np.asarray(alpha, np.float64)
    x, y, z = a[224:227]
    Rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    Ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    Rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    shape = (
        basis["u"].reshape(-1) + basis["id"] @ a[:80] + basis["exp"] @ a[80:144]
    ).reshape(-1, 3)
    R = Rz @ Ry @ Rx
    cam = shape @ (R.T if transpose else R) + a[254:257]
    depth = 10.0 - cam[:, 2]
    px = 1015.0 * cam[:, 0] / depth + 112.0
    py = 1015.0 * cam[:, 1] / depth + 112.0
    left, top, scale = alignment["crop"]
    nw = max(1, int(round(W * scale)))
    nh = max(1, int(round(H * scale)))
    ox = (px + left) * (W / nw)
    oy = (223.0 - py + top) * (H / nh)
    return np.stack([ox, oy], -1)


def pixels(uv):
    return np.stack([uv[:, 0] * (W - 1), (1 - uv[:, 1]) * (H - 1)], -1)


shipped = pixels(tddfa.project_to_photo(basis, alpha, W, H, alignment))
old = legacy_project(alpha, False)
ldm68 = np.asarray(basis["ldm68"], np.int32).reshape(-1)

det = json.load(open(f"{ROOT}/cache/{pid}/ocular-detection.json"))
mp = np.asarray(det["points"], np.float64)
mp[:, 0] *= W / det["width"]
mp[:, 1] *= H / det["height"]

pairs = [(30, 1), (36, 33), (45, 263), (48, 61), (54, 291), (8, 199)]
print(f"{'3ddfa':>6} {'mp':>4} {'old px':>8} {'fixed px':>9}")
for i, j in pairs:
    d_old = np.linalg.norm(old[ldm68][i] - mp[j])
    d_new = np.linalg.norm(shipped[ldm68][i] - mp[j])
    print(f"{i:>6} {j:>4} {d_old:>8.1f} {d_new:>9.1f}")

buf = img.copy()
d = ImageDraw.Draw(buf)
for i, j in pairs:
    x, y = old[ldm68][i]
    d.line([x - 7, y, x + 7, y], fill=(255, 60, 60), width=2)
    d.line([x, y - 7, x, y + 7], fill=(255, 60, 60), width=2)
    x, y = shipped[ldm68][i]
    d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(60, 255, 120), width=3)
for x, y in mp[[1, 33, 263, 61, 291, 199]]:
    d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(80, 160, 255))
buf.save(f"{ROOT}/.runtime_audit/verify_fix_overlay.png")

atlas, mask = bake_photo_to_uv(
    np.asarray(img), tddfa.project_to_photo(basis, alpha, W, H, alignment),
    basis["uv_coords"], basis["tri"], 1024,
)
Image.fromarray(atlas).save(f"{ROOT}/.runtime_audit/atlas_shipped.png")
print("atlas coverage", round(float((mask > 0).mean()), 3))

# Software z-buffer render of the canonical atlas on the fitted mesh.
topo = json.load(open(f"{ROOT}/data/topology.json"))
tri = np.asarray(topo["triangles"], np.int32)
uv = np.asarray(topo["uv"], np.float32)
verts = np.load(feature[0], allow_pickle=True)["vertices"].astype(np.float32)


def render(atlas_img, out, yaw_deg=0, size=560):
    arr = np.asarray(atlas_img)
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
    print("saved", out)


render(atlas, f"{ROOT}/.runtime_audit/mesh_shipped.png", 0)
render(atlas, f"{ROOT}/.runtime_audit/mesh_shipped_yaw35.png", 35)
