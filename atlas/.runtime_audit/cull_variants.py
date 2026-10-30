"""Bake culling variants for a yawed and a frontal cached photo."""

import glob, json, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = "/Users/victorkhudyakov/work/atlas"
sys.path.insert(0, ROOT)
sys.path.insert(0, f"{ROOT}/.runtime_audit")

import server.models.tddfa as tddfa
from server.uv_texture import bake_photo_to_uv, facing_mask
from meshview import render

tddfa.ASSETS = Path("/Users/victorkhudyakov/work/3ddfa_v3/assets")
basis = tddfa.basis_arrays()
tri = np.asarray(basis["tri"], np.int32)
uv = np.asarray(basis["uv_coords"], np.float32)[:, :2]
library = {p["id"]: p for p in json.load(open(f"{ROOT}/data/library.json"))["photos"]}


def load(pid):
    meta = json.load(open(f"{ROOT}/cache/{pid}/meta.json"))
    files = glob.glob(f"{ROOT}/cache/{pid}/features-*.npz")
    key = meta.get("feature_key")
    files = [f for f in files if key and key in f] or files
    feats = np.load(files[0], allow_pickle=True)
    photo = ImageOps.exif_transpose(
        Image.open(f"{ROOT}/{library[pid]['path']}")
    ).convert("RGB")
    return meta, feats, np.asarray(photo)


for pid, yaws in (("2a29f955863593e6", (0, 35)), ("dfcbf5e52d181c22", (0,))):
    meta, feats, rgb = load(pid)
    alpha = feats["alpha"]
    H, W = rgb.shape[:2]
    src = tddfa.project_to_photo(basis, alpha, W, H, meta["alignment"])
    print(f"\n{pid} yaw={meta['angles']['yaw']:.1f} photo={W}x{H}")
    variants = {
        "nocus": None,
        "cull_only": facing_mask(src, uv, tri, W, H, min_area=0.0),
        "cull_a05": facing_mask(src, uv, tri, W, H, min_area=0.5),
        "cull_a15": facing_mask(src, uv, tri, W, H, min_area=1.5),
    }
    for name, mask in variants.items():
        atlas, cov = bake_photo_to_uv(
            rgb, src, uv, tri, 1024, faces=mask
        )
        Image.fromarray(atlas).save(f"{ROOT}/.runtime_audit/v_{name}.png")
        kept = "all" if mask is None else f"{int(mask.sum())}/{len(mask)}"
        print(f"  {name:<9} kept={kept:<14} atlas coverage={float((cov>0).mean()):.3f}")
        for yaw in yaws:
            out = f"{ROOT}/.runtime_audit/v_{name}_yaw{yaw}.png"
            render(feats["vertices"], tri, uv, atlas, out, yaw)
            print("   ", out)
