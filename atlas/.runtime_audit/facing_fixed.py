"""Signed-area consistency of the fixed projection and culling variants."""

import glob, json, sys

import numpy as np
from PIL import Image

ROOT = "/Users/victorkhudyakov/work/atlas"
sys.path.insert(0, ROOT)

import server.models.tddfa as tddfa
from pathlib import Path

tddfa.ASSETS = Path("/Users/victorkhudyakov/work/3ddfa_v3/assets")
basis = tddfa.basis_arrays()
pid = "2a29f955863593e6"
meta = json.load(open(f"{ROOT}/cache/{pid}/meta.json"))
feature = glob.glob(f"{ROOT}/cache/{pid}/features-*.npz")
key = meta.get("feature_key")
feature = [f for f in feature if key and key in f] or feature
alpha = np.load(feature[0], allow_pickle=True)["alpha"]
from PIL import ImageOps

record = next(p for p in json.load(open(f"{ROOT}/data/library.json"))["photos"] if p["id"] == pid)
photo = ImageOps.exif_transpose(Image.open(f"{ROOT}/{record['path']}")).convert("RGB")
W, H = photo.size

uv = tddfa.project_to_photo(basis, alpha, W, H, meta["alignment"])
src = np.stack([uv[:, 0] * (W - 1), (1 - uv[:, 1]) * (H - 1)], 1)
tri = np.asarray(basis["tri"], np.int32)


def signed(a):
    return 0.5 * (
        (a[:, 1, 0] - a[:, 0, 0]) * (a[:, 2, 1] - a[:, 0, 1])
        - (a[:, 2, 0] - a[:, 0, 0]) * (a[:, 1, 1] - a[:, 0, 1])
    )


src_area = signed(src[tri])
tpl_area = signed(np.asarray(basis["uv_coords"], np.float32)[:, :2][tri])
print("source area sign  +:", int((src_area > 0).sum()), " -:", int((src_area < 0).sum()))
print("template area sign +:", int((tpl_area > 0).sum()), " -:", int((tpl_area < 0).sum()))
agree = np.sign(src_area) == np.sign(tpl_area)
print("sign agreement", round(float(agree.mean()), 4))
print("abs source area percentiles", np.percentile(np.abs(src_area), [1, 5, 25, 50, 95]))
print("abs template area percentiles", np.percentile(np.abs(tpl_area), [1, 5, 25, 50, 95]))
ratio = np.abs(src_area) / np.maximum(np.abs(tpl_area), 1e-12)
print("src/tpl area ratio percentiles", np.percentile(ratio, [0.5, 1, 5, 25, 50, 95]))

# Does the disagreeing set look like the far side? Check vertex normals of those triangles.
shape = (
    basis["u"].reshape(-1) + basis["id"] @ alpha[:80] + basis["exp"] @ alpha[80:144]
).reshape(-1, 3)
cam = shape @ tddfa.pose_rotation(alpha[224:227]) + alpha[254:257]
n = np.cross(
    cam[tri[:, 1]] - cam[tri[:, 0]], cam[tri[:, 2]] - cam[tri[:, 0]]
)
nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
print("normal z of agreeing triangles  ", np.round(np.percentile(nz[agree], [5, 50, 95]), 3))
print("normal z of disagreeing triangles", np.round(np.percentile(nz[~agree], [5, 50, 95]), 3))

np.save(f"{ROOT}/.runtime_audit/facing_src_area.npy", src_area.astype(np.float32))
np.save(f"{ROOT}/.runtime_audit/facing_tpl_area.npy", tpl_area.astype(np.float32))
