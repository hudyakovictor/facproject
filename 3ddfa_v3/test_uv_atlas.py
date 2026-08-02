#!/usr/bin/env python3
"""UV wrinkle atlas — через общий crop.

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
parser.add_argument("--photo", type=Path, default=None,
                    help="входное фото (по умолчанию: <ffhq-root>/е1/2000_06_14.jpg)")
args_cli = parser.parse_args()

FFHQ_ROOT = (args_cli.ffhq_root or ffhq_root()).resolve()
PHOTO = require(args_cli.photo or (FFHQ_ROOT / "е1" / "2000_06_14.jpg"), "входное фото")
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

# ── 3. Init UV renderer ───────────────────────────────────────────
uv_renderer = MeshRenderer_UV_cpu(rasterize_size=1000)

# ── 4. Load photo + run 3DDFA ─────────────────────────────────────
print("1. Running 3DDFA...")
img_pil = Image.open(PHOTO).convert("RGB")
trans_params, img_tensor = facebox_detector(img_pil)
# img_tensor: (1, 3, 224, 224) in [0,1] range (just /255, no imagenet norm)

recon_model.input_img = img_tensor.to(device)
with pushd(TDDFA_ROOT):
    results = recon_model.forward()

v2d    = torch.from_numpy(results["v2d"][0]).float()   # (35709, 2) в 224x224
uv_raw = torch.from_numpy(results["uv_coords"]).float()
tri    = torch.from_numpy(results["tri"]).long()
if tri.dim() == 3: tri = tri[0]
face_tex = torch.from_numpy(results["face_texture"][0]).float()

# ── 5. Wrinkle model на том же crop'е ─────────────────────────────
print("2. Running wrinkle model on aligned crop...")

# Восстанавливаем PIL из img_tensor (просто /255, без imagenet norm)
aligned_np = (img_tensor[0].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
aligned_pil = Image.fromarray(aligned_np)  # 224x224, RGB

# Wrinkle model
face_tensor = wrinkle_tfm(aligned_pil).unsqueeze(0).to(device)
with torch.no_grad():
    wr_out = wrinkle_net(face_tensor)
    wr_pred = torch.sigmoid(wr_out).cpu().numpy()
wr_mask = (wr_pred > 0.5).astype(np.float32).squeeze()  # (512, 512)

# ── 6. Сопоставление v2d -> wrinkle mask ─────────────────────────
# v2d в 224x224, wr_mask в 512x512 (resize в wrinkle_tfm)
scale = 512.0 / 224.0
v2d_512 = v2d * scale
v2d_int = v2d_512.long()
v2d_int[:, 0] = v2d_int[:, 0].clamp(0, 511)
v2d_int[:, 1] = v2d_int[:, 1].clamp(0, 511)

vert_wr = torch.from_numpy(wr_mask[v2d_int[:, 1].numpy(), v2d_int[:, 0].numpy()]).float()

# ── 7. Рендер на UV-атлас ────────────────────────────────────────
print("3. Rendering UV atlas...")

def render_uv(attr, uv_coords, tri, size=1000):
    uv = uv_coords.float() * 2.0 - 1.0
    if uv.shape[1] == 2:
        uv = torch.cat([uv, torch.zeros(uv.shape[0], 1)], dim=1)
    if attr.dim() == 1:
        attr = attr.unsqueeze(-1).repeat(1, 3)
    rend = MeshRenderer_UV_cpu(rasterize_size=size)
    with torch.no_grad():
        _, _, img, _ = rend(uv.unsqueeze(0), tri, attr.unsqueeze(0))
    return img[0].cpu().numpy()

uv_tex = render_uv(face_tex, uv_raw, tri, 1000).transpose(1, 2, 0)
uv_tex = np.clip(uv_tex, 0, 1)

uv_wr = render_uv(vert_wr, uv_raw, tri, 1000)
uv_wr_map = uv_wr[0]

# ── 8. Зоны атласа ───────────────────────────────────────────────
print("4. Drawing zone overlay...")
import json, cv2

zone_data = np.load(f"{TDDFA_ROOT}/atlas/texture_zones_bfm35709_v3.npz", allow_pickle=True)
focus_mask = zone_data["triangle_focus_mask"]  # (14, 70789)
tri_zones = zone_data["triangle_subzone_label"]

with open(f"{TDDFA_ROOT}/atlas/texture_zones_v3_metadata.json") as f:
    meta = json.load(f)
focus_meta = meta["focus"]

tri_np = tri.numpy()
uv_v = (uv_raw.numpy() * 1000).astype(int)
uv_v[:, 1] = 1000 - uv_v[:, 1]

focus_colors = [
    (200, 50, 50), (50, 200, 50), (50, 50, 200),
    (200, 200, 50), (200, 50, 200), (50, 200, 200),
    (180, 120, 50), (120, 180, 50), (50, 180, 120),
    (120, 50, 180), (180, 50, 120), (50, 120, 180),
    (180, 180, 50), (50, 180, 180),
]

zone_img = np.zeros((1000, 1000, 3), dtype=np.uint8)
for f_idx in range(14):
    tris = np.where(focus_mask[f_idx])[0]
    for t_idx in tris:
        v0, v1, v2 = tri_np[t_idx]
        pts = np.array([uv_v[v0][:2], uv_v[v1][:2], uv_v[v2][:2]], dtype=np.int32)
        cv2.fillPoly(zone_img, [pts], focus_colors[f_idx])
        cv2.polylines(zone_img, [pts], True, (40, 40, 40), 1)

# ── 9. Композит ───────────────────────────────────────────────────
# 9a. UV текстура (фон)
uv_bg = (uv_tex * 0.3 * 255).astype(np.uint8)

# 9b. Wrinkle overlay (red) поверх затемнённой текстуры
wr_overlay = np.zeros((1000, 1000, 3), dtype=np.uint8)
wr_overlay[uv_wr_map > 0.5] = [255, 50, 50]
uv_wr_comp = uv_bg.copy()
mask_3ch = (uv_wr_map > 0.5).astype(np.float32)[:, :, np.newaxis].repeat(3, axis=2)
uv_wr_comp = ((1 - mask_3ch) * uv_bg + mask_3ch * np.array([255, 50, 50])).astype(np.uint8)

# 9c. Зоны на UV текстуре
zone_blend = cv2.addWeighted((uv_tex * 255).astype(np.uint8), 0.4, zone_img, 0.6, 0)

# 9d. Wrinkle + зоны
zone_wr = zone_blend.copy()
zone_wr = ((1 - mask_3ch) * zone_wr.astype(float) + mask_3ch * np.array([255, 50, 50])).astype(np.uint8)

# ── 10. Сохранение ────────────────────────────────────────────────
# Оригинал + aligned crop
Image.fromarray(np.array(img_pil.resize((512, 512)))).save(f"{OUT_DIR}/01_original.png")
aligned_pil.resize((512, 512), Image.NEAREST).save(f"{OUT_DIR}/02_aligned.png")

# Wrinkle на aligned
wr_rgb = np.zeros((512, 512, 3), dtype=np.uint8)
wr_rgb[wr_mask > 0.5] = [255, 0, 0]
aligned_big = np.array(aligned_pil.resize((512, 512), Image.NEAREST))
aligned_wr = cv2.addWeighted(aligned_big, 0.6, wr_rgb, 0.4, 0)
Image.fromarray(aligned_wr).save(f"{OUT_DIR}/03_aligned_wrinkles.png")

# Атласы
Image.fromarray((uv_tex * 255).astype(np.uint8)).save(f"{OUT_DIR}/04_uv_texture.png")
Image.fromarray(uv_wr_comp).save(f"{OUT_DIR}/05_uv_wrinkles.png")
Image.fromarray((uv_wr_map * 255).astype(np.uint8)).save(f"{OUT_DIR}/06_uv_wrinkle_mask.png")
Image.fromarray(zone_blend).save(f"{OUT_DIR}/07_uv_zones.png")
Image.fromarray(zone_wr).save(f"{OUT_DIR}/08_uv_zones_wrinkles.png")

# ── 11. Инфо ──────────────────────────────────────────────────────
wp = float(wr_mask.sum() / wr_mask.size * 100)
uv_px = int((uv_wr_map > 0.5).sum())
print(f"\nAlign crop wrinkle: {wp:.2f}%")
print(f"UV wrinkle pixels:  {uv_px} / 1,000,000 ({uv_px/10000:.2f}%)")
print(f"\nФайлы:")
for f in sorted(os.listdir(OUT_DIR)):
    fp = os.path.join(OUT_DIR, f)
    if os.path.isfile(fp) and f[0].isdigit():
        print(f"  {fp}")
