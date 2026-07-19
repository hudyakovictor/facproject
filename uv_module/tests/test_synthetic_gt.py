"""Synthetic ground-truth validation: v2 baseline vs v3.

Builds a procedural 'face' (hemisphere + nose bump), textures it with a known
ground-truth UV texture containing skin-like micro detail, renders an 800x800
photo at a 3/4 pose (real self-occlusion from the nose), then reconstructs the
UV texture with both modules and measures:
  - PSNR of the analysis texture vs ground truth (observed texels only)
  - forensic purity: analysis must be identical with detail_enhance on/off
  - dark-halo: border-vs-interior luma gap inside the observed mask
  - observed coverage (false occlusion holes reduce it)
"""
import sys, time
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "uv_module" / "tests" / "_bench_out"
OUT.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(7)

# ---------------- ground-truth texture (1000x1000, skin-like micro detail) ---
TS = 1000
yy, xx = np.mgrid[0:TS, 0:TS].astype(np.float32) / TS
base = np.stack([
    150 + 20 * np.sin(xx * 9),          # B
    170 + 15 * np.cos(yy * 7),          # G
    215 + 12 * np.sin((xx + yy) * 5),   # R
], axis=-1).astype(np.float32)
pores = cv2.GaussianBlur(rng.normal(0, 22, (TS, TS)).astype(np.float32), (0, 0), 1.0)
wrinkles = 10 * np.sin(yy * 220 + 3 * np.sin(xx * 30)) * (np.sin(xx * 40) > 0.6)
spots = np.zeros((TS, TS), np.float32)
for _ in range(60):
    cx_, cy_, r_ = rng.integers(50, TS - 50), rng.integers(50, TS - 50), rng.integers(3, 9)
    cv2.circle(spots, (int(cx_), int(cy_)), int(r_), float(rng.normal(-25, 6)), -1)
spots = cv2.GaussianBlur(spots, (0, 0), 1.2)
detail = (pores + wrinkles + spots)[..., None]
GT = np.clip(base + detail, 0, 255).astype(np.uint8)

# ---------------- procedural mesh ------------------------------------------
G = 140                      # grid resolution -> ~38k triangles
R = 1.0
u = np.linspace(0, 1, G, dtype=np.float64)
v = np.linspace(0, 1, G, dtype=np.float64)
UU, VV = np.meshgrid(u, v)                     # VV row 0 = v=0
X = (UU - 0.5) * 2 * R * 0.98
Y = (VV - 0.5) * 2 * R * 0.98
rr2 = np.clip(R * R - X ** 2 - Y ** 2, 0, None)
Z = np.sqrt(rr2)
# nose bump slightly below center
Z = Z + 0.5 * R * np.exp(-(((X) ** 2 + (Y + 0.1) ** 2) / (0.16 * R) ** 2))

# numeric normals of height field z(x, y): n ~ (-dz/dx, -dz/dy, 1)
dzdx = np.gradient(Z, X[0, :], axis=1)
dzdy = np.gradient(Z, Y[:, 0], axis=0)
N = np.stack([-dzdx, -dzdy, np.ones_like(Z)], axis=-1)
N /= np.linalg.norm(N, axis=-1, keepdims=True)

verts = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
normals = N.reshape(-1, 3)
uvs = np.stack([UU, 1.0 - VV], axis=-1).reshape(-1, 2)  # v=1 at top of face (row 0)

idx = np.arange(G * G).reshape(G, G)
t1 = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[:-1, 1:]], axis=-1).reshape(-1, 3)
t2 = np.stack([idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], axis=-1).reshape(-1, 3)
tris = np.concatenate([t1, t2], axis=0).astype(np.int64)

# ---------------- pose: 28 deg yaw ------------------------------------------
theta = np.deg2rad(28)
Ry = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])
vp = verts @ Ry.T
np_ = normals @ Ry.T

# ---------------- orthographic projection to 800x800 photo ------------------
H = W = 800
scale = 300.0
cx, cy = W / 2, H / 2
px = cx + vp[:, 0] * scale
py_top = cy - vp[:, 1] * scale            # top-origin rows
depth = vp[:, 2]                           # larger = closer

# render photo: image-space triangle-id raster, far-to-near
id_buf = np.full((H, W), -1, np.int32)
tri_depth = depth[tris].mean(axis=1)
front_tri = (np_[:, 2][tris].mean(axis=1) > 0)
order = np.argsort(tri_depth)
pts2 = np.stack([px, py_top], axis=1)
pts_all = np.round(pts2[tris]).astype(np.int32)
for i in order:
    if front_tri[i]:
        cv2.fillConvexPoly(id_buf, pts_all[i], int(i))
ys, xs = np.nonzero(id_buf >= 0)
t = id_buf[ys, xs].astype(np.int64)
a2, b2, c2 = pts2[tris[t, 0]], pts2[tris[t, 1]], pts2[tris[t, 2]]
p = np.stack([xs, ys], 1).astype(np.float64)
v0, v1, v2_ = b2 - a2, c2 - a2, p - a2
d00 = np.einsum("ij,ij->i", v0, v0); d01 = np.einsum("ij,ij->i", v0, v1)
d11 = np.einsum("ij,ij->i", v1, v1); d20 = np.einsum("ij,ij->i", v2_, v0)
d21 = np.einsum("ij,ij->i", v2_, v1)
den = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-12, 1e-12, d00 * d11 - d01 * d01)
w1 = (d11 * d20 - d01 * d21) / den; w2 = (d00 * d21 - d01 * d20) / den
w0 = 1 - w1 - w2
Wt = np.clip(np.stack([w0, w1, w2], 1), 0, 1); Wt /= Wt.sum(1, keepdims=True)
uv_pix = (uvs[tris[t, 0]] * Wt[:, :1] + uvs[tris[t, 1]] * Wt[:, 1:2] + uvs[tris[t, 2]] * Wt[:, 2:3])
mx = (uv_pix[:, 0] * (TS - 1)).astype(np.float32)
my = ((1.0 - uv_pix[:, 1]) * (TS - 1)).astype(np.float32)
photo = np.zeros((H, W, 3), np.uint8)
map_x = np.full((H, W), -1, np.float32); map_y = np.full((H, W), -1, np.float32)
map_x[ys, xs] = mx; map_y[ys, xs] = my
sampled = cv2.remap(GT, map_x, map_y, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
photo[ys, xs] = sampled[ys, xs]
photo[id_buf < 0] = (40, 160, 60)  # green background -> bleed detector
cv2.imwrite(str(OUT / "synth_photo.png"), photo)

# ---------------- recon dict (module contract) -------------------------------
recon = {
    "uv_coords": uvs.astype(np.float32),
    "triangles": tris,
    "vertices_2d": np.stack([px, (H - 1) - py_top], axis=1).astype(np.float32),  # bottom-origin
    "vertices_3d": np.stack([vp[:, 0], vp[:, 1], depth], axis=1).astype(np.float32),
    "normals_3d": np_.astype(np.float32),
}

# GT in atlas space at 1000: row 0 = v=1 (v2/v3 flipped convention)
GT_atlas = GT  # by construction row0 <-> v=1

def evaluate(name, mod_cfg, mod_gen, extra_recon=None):
    cfg = mod_cfg(uv_size=1000, super_sample=2, cache_dir="/tmp/uvcache_" + name)
    gen = mod_gen(cfg)
    rc = dict(recon)
    if extra_recon:
        rc.update(extra_recon)
    t0 = time.time()
    analysis, beauty, observed, conf, aux = gen.generate(photo, rc)
    dt = time.time() - t0
    # purity: rerun with enhancement off -> analysis must be identical
    cfg2 = mod_cfg(uv_size=1000, super_sample=2, detail_enhance=False, cache_dir="/tmp/uvcache_" + name)
    analysis2 = mod_gen(cfg2).generate(photo, rc)[0]
    pure = bool(np.array_equal(analysis, analysis2))
    m = observed & (GT_atlas.sum(-1) > 0)
    diff = analysis.astype(np.float32) - GT_atlas.astype(np.float32)
    mse = float(np.mean(diff[m] ** 2)) if m.any() else float("nan")
    psnr = 10 * np.log10(255 ** 2 / mse) if mse > 0 else float("inf")
    g = cv2.cvtColor(analysis, cv2.COLOR_BGR2GRAY).astype(np.float32)
    k = np.ones((7, 7), np.uint8)
    inner = cv2.erode(observed.astype(np.uint8), k) > 0
    border = observed & ~inner
    halo = float(g[inner].mean() - g[border].mean()) if border.any() and inner.any() else 0.0
    # green-background bleed inside observed texels
    bgr = analysis.astype(np.int32)
    greenish = (bgr[..., 1] > bgr[..., 2] + 30) & (bgr[..., 1] > bgr[..., 0] + 30) & observed
    print(f"{name:6s} obs={100*observed.mean():5.1f}%  PSNR={psnr:6.2f} dB  pure={pure}  "
          f"halo={halo:5.2f}  green_bleed={int(greenish.sum())} px  conf={conf[observed].mean():.2f}  t={dt:.1f}s")
    return analysis, beauty, observed

print("=== synthetic ground-truth benchmark (28 deg yaw, nose occlusion) ===")
from uv_module.config import HDUVConfig as C3
from uv_module.generator import HDUVTextureGenerator as G3
# skin mask: everything that is not green background
skin = ~((photo[..., 1].astype(np.int32) > photo[..., 2] + 30) & (photo[..., 1].astype(np.int32) > photo[..., 0] + 30))
a3_, b3_, o3_ = evaluate("v3", C3, G3, extra_recon={"skin_mask": skin.astype(np.uint8) * 255})

cv2.imwrite(str(OUT / "bench_v3_analysis.png"), a3_)
cv2.imwrite(str(OUT / "bench_v3_synth.png"), b3_)
print("done")
