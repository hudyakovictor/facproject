#!/usr/bin/env python3
"""Test: project wrinkle masks onto UV atlas via 3DDFA-V3, then compare.

DEV_FIX_TZ B3/P1.13/P2.14: абсолютные пути к машине разработчика заменены на
расчёт от расположения файла + CLI/переменные окружения, а глобальный
`os.chdir()` — на локальный контекстный менеджер `pushd` (см. `_paths.py`).
"""
import argparse
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (  # noqa: E402
    TDDFA_ROOT, add_common_arguments, ffhq_root, pushd, require, resolve_device, wrinkle_checkpoint,
)

parser = add_common_arguments(argparse.ArgumentParser(description=__doc__))
parser.add_argument("--photo-dir", type=Path, default=None,
                    help="каталог фото (по умолчанию: <ffhq-root>/е1)")
parser.add_argument("--mask-dir", type=Path, default=None,
                    help="каталог масок (по умолчанию: <ffhq-root>/e1_result)")
args_cli = parser.parse_args()

FFHQ_ROOT = (args_cli.ffhq_root or ffhq_root()).resolve()
PHOTO_DIR = require(args_cli.photo_dir or (FFHQ_ROOT / "е1"), "каталог фото")
MASK_DIR = require(args_cli.mask_dir or (FFHQ_ROOT / "e1_result"), "каталог масок")
OUT_DIR = (args_cli.out_dir or (FFHQ_ROOT / "uv_wrinkle_test")).resolve()
os.makedirs(OUT_DIR, exist_ok=True)

device = resolve_device(args_cli.device)

# ── 1. Init 3DDFA ──────────────────────────────────────────────────
sys.path.insert(0, str(TDDFA_ROOT))

from face_box import face_box
from model.recon import face_model
from util.cpu_renderer import MeshRenderer_UV_cpu

args = SimpleNamespace(
    device=device, iscrop=True, detector="retinaface", backbone="resnet50",
    ldm68=False, ldm106=False, ldm106_2d=False, ldm134=False,
    seg=False, seg_visible=False, useTex=False, extractTex=False,
)
# Апстрим 3DDFA_V3 читает веса по относительным путям "assets/...", поэтому
# CWD переключается ровно на время конструирования моделей и возвращается.
with pushd(TDDFA_ROOT):
    recon_model = face_model(args)
    facebox_detector = face_box(args).detector

# ── 2. Init Wrinkle model ─────────────────────────────────────────
sys.path.insert(0, str(FFHQ_ROOT))
from torchvision import transforms
from unet import UNet

ckpt = torch.load(require(wrinkle_checkpoint(FFHQ_ROOT), "веса модели морщин"), map_location=device)
wrinkle_net = UNet(n_channels=3, n_classes=1, bilinear=False, pretrained=True, freeze_encoder=True).to(device).eval()
wrinkle_net.load_state_dict(ckpt["model_state_dict"])

wrinkle_tfm = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])

# ── 3. Init CPU UV renderer ───────────────────────────────────────
uv_renderer = MeshRenderer_UV_cpu(rasterize_size=1000)

# ── 4. Load photo list ────────────────────────────────────────────
photo_names = sorted([
    f for f in os.listdir(PHOTO_DIR)
    if f.lower().endswith((".jpg", ".jpeg", ".png"))
    and not f.endswith("_overlay.png") and not f.endswith("_mask.png") and f != ".DS_Store"
])

print(f"Found {len(photo_names)} photos\n")

# ── 5. Process each photo ─────────────────────────────────────────
uv_wrinkle_maps = {}

for idx, img_name in enumerate(photo_names):
    stem = os.path.splitext(img_name)[0]
    img_path = os.path.join(PHOTO_DIR, img_name)
    mask_path = os.path.join(MASK_DIR, f"{stem}_mask.png")
    if not os.path.exists(mask_path):
        print(f"  SKIP {img_name}: no mask found")
        continue

    # ── 5a. Load original photo, run 3DDFA ────────────────────────
    img_pil = Image.open(img_path).convert("RGB")
    trans_params, img_tensor = facebox_detector(img_pil)  # returns 224x224 tensor

    recon_model.input_img = img_tensor.to(device)
    with pushd(TDDFA_ROOT):
        results = recon_model.forward()

    v2d_np = results["v2d"][0] if isinstance(results["v2d"], np.ndarray) else results["v2d"][0].cpu().numpy()
    v2d = torch.from_numpy(v2d_np).float()
    uv_arr = results["uv_coords"]
    uv_cpu = torch.from_numpy(uv_arr).float() if isinstance(uv_arr, np.ndarray) else uv_arr.float().cpu()
    tri_arr = results["tri"]
    tri_cpu = torch.from_numpy(tri_arr).long() if isinstance(tri_arr, np.ndarray) else tri_arr.long().cpu()
    if tri_cpu.dim() == 3:
        tri_cpu = tri_cpu[0]
    tri_cpu = tri_cpu.long()

    visible_idx = None

    # ── 5b. Build per-vertex wrinkle value ────────────────────────
    # Map v2d (224x224) -> wrinkle mask (512x512)
    wrinkle_mask_pil = Image.open(mask_path).convert("L")
    wrinkle_mask_np = np.array(wrinkle_mask_pil, dtype=np.float32) / 255.0

    scale = 512.0 / 224.0
    v2d_512 = v2d * scale
    v2d_int = v2d_512.long()
    v2d_int[:, 0] = v2d_int[:, 0].clamp(0, 511)
    v2d_int[:, 1] = v2d_int[:, 1].clamp(0, 511)

    vert_wrinkle = wrinkle_mask_np[v2d_int[:, 1].numpy(), v2d_int[:, 0].numpy()]  # (35709,)
    vert_wrinkle = torch.from_numpy(vert_wrinkle).float()

    if visible_idx is not None:
        vert_wrinkle[visible_idx == 0] = 0.0

    # ── 5c. Render wrinkle onto UV atlas ──────────────────────────
    # uv_coords in [0,1] -> map to [-1,1] for renderer
    uv_verts = uv_cpu.float() * 2.0 - 1.0                             # (35709, 2)
    uv_verts_3d = torch.cat([uv_verts, torch.zeros(35709, 1)], dim=1) # (35709, 3)

    feat_3ch = vert_wrinkle.unsqueeze(-1).repeat(1, 3)                # (35709, 3)

    with torch.no_grad():
        uv_mask_t, _, uv_wrink_t, _ = uv_renderer(
            uv_verts_3d.unsqueeze(0),   # (1, 35709, 3)
            tri_cpu,                    # (70789, 3)
            feat_3ch.unsqueeze(0),      # (1, 35709, 3)
            visible_vertice=False,
        )

    uv_wrinkle_map = uv_wrink_t[0, 0].cpu().numpy()  # first channel

    # ── 5d. Apply observed mask ────────────────────────────────────
    _, _, uv_obs_t, _ = uv_renderer(
        uv_verts_3d.unsqueeze(0), tri_cpu,
        visible_idx.float().unsqueeze(-1).repeat(1, 3).unsqueeze(0) if visible_idx is not None else torch.ones(1, 35709, 3),
        visible_vertice=False,
    )
    obs_mask = uv_obs_t[0, 0].cpu().numpy() > 0.5

    uv_wrinkle_clean = np.where(obs_mask, uv_wrinkle_map, 0.0)

    # ── 6. Save ───────────────────────────────────────────────────
    np.savez(os.path.join(OUT_DIR, f"{stem}_uv_wrinkle.npz"),
             uv_wrinkle=uv_wrinkle_clean, observed=obs_mask)
    Image.fromarray((uv_wrinkle_clean * 255).astype(np.uint8)).save(
        os.path.join(OUT_DIR, f"{stem}_uv_wrinkle.png"))

    uv_wrinkle_maps[stem] = uv_wrinkle_clean

    total_wr = float(wrinkle_mask_np.sum() / wrinkle_mask_np.size * 100)
    uv_wr = float(uv_wrinkle_clean[obs_mask].mean() * 100) if obs_mask.any() else 0
    print(f"  [{idx+1}/{len(photo_names)}] {stem:<30} 2D={total_wr:.2f}%  UV={uv_wr:.2f}%")

print(f"\nUV wrinkle maps saved to {OUT_DIR}/")

# ── 7. Pairwise comparison in UV space ─────────────────────────────
print(f"\n--- UV wrinkle similarity (top-20) ---\n")

def cosine_sim_uv(uv_a, uv_b, mask_a, mask_b):
    common = mask_a & mask_b
    if common.sum() < 100:
        return 0.0
    a = uv_a[common].ravel()
    b = uv_b[common].ravel()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

names = sorted(uv_wrinkle_maps.keys())
results = []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        n1, n2 = names[i], names[j]
        d1 = np.load(os.path.join(OUT_DIR, f"{n1}_uv_wrinkle.npz"))
        d2 = np.load(os.path.join(OUT_DIR, f"{n2}_uv_wrinkle.npz"))
        sim = cosine_sim_uv(d1["uv_wrinkle"], d2["uv_wrinkle"], d1["observed"], d2["observed"])
        results.append((sim, n1, n2))

results.sort(key=lambda x: -x[0])
print(f"{'Rank':<5} {'Similarity':<12} {'Photo 1':<30} {'Photo 2':<30}")
print("-" * 77)
for i, (sim, n1, n2) in enumerate(results[:20]):
    print(f"{i+1:<5} {sim:<12.4f} {n1:<30} {n2:<30}")

all_sims = [r[0] for r in results]
print(f"\nStats: mean={np.mean(all_sims):.4f} min={np.min(all_sims):.4f} max={np.max(all_sims):.4f}")
