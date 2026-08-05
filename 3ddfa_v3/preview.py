#!/usr/bin/env python3
"""Одно фото → 4 файла с билинейной интерполяцией.

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
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (  # noqa: E402
    TDDFA_ROOT, add_common_arguments, ffhq_root, pushd, require, resolve_device, wrinkle_checkpoint,
)

parser = add_common_arguments(argparse.ArgumentParser(description=__doc__))
parser.add_argument("--photo", type=Path, default=None, help="входное фото (по умолчанию: <ffhq-root>/е1/2000_06_14.jpg)")
args_cli = parser.parse_args()

FFHQ = (args_cli.ffhq_root or ffhq_root()).resolve()
TDDFA = TDDFA_ROOT
PHOTO = require(args_cli.photo or (FFHQ / "е1" / "2000_06_14.jpg"), "входное фото")
OUT = (args_cli.out_dir or (FFHQ / "uv_wrinkle_test")).resolve()
os.makedirs(OUT, exist_ok=True)
device = resolve_device(args_cli.device)

sys.path.insert(0, str(TDDFA))
from face_box import face_box  # noqa: E402
from model.recon import face_model  # noqa: E402
from util.cpu_renderer import MeshRenderer_UV_cpu  # noqa: E402

args = SimpleNamespace(device=device, iscrop=True, detector="retinaface", backbone="resnet50",
    ldm68=False, ldm106=False, ldm106_2d=False, ldm134=False,
    seg=False, seg_visible=False, useTex=False, extractTex=False)
# Апстрим 3DDFA_V3 читает веса по относительным путям "assets/...", поэтому
# CWD переключается ровно на время конструирования моделей и возвращается назад.
with pushd(TDDFA):
    recon_model = face_model(args)
    facebox_detector = face_box(args).detector

sys.path.insert(0, str(FFHQ))
from torchvision import transforms  # noqa: E402
from unet import UNet  # noqa: E402
ckpt = torch.load(require(wrinkle_checkpoint(FFHQ), "веса модели морщин"), map_location=device)
wr = UNet(n_channels=3, n_classes=1, bilinear=False, pretrained=True, freeze_encoder=True).to(device).eval()
wr.load_state_dict(ckpt["model_state_dict"])
tfm = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])

# ── Run 3DDFA ──
img_pil = Image.open(PHOTO).convert("RGB")
trans_params, img_tensor = facebox_detector(img_pil)
recon_model.input_img = img_tensor.to(device)
with pushd(TDDFA):
    res = recon_model.forward()

v2d = torch.from_numpy(res["v2d"][0]).float()
uv  = torch.from_numpy(res["uv_coords"]).float()
tri = torch.from_numpy(res["tri"]).long()
if tri.dim() == 3: tri = tri[0]
face_tex = torch.from_numpy(res["face_texture"][0]).float()

# ── Wrinkle on same crop (bilinear sampling) ──
aligned_np = (img_tensor[0].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
aligned_pil = Image.fromarray(aligned_np)
inp = tfm(aligned_pil).unsqueeze(0).to(device)
with torch.no_grad():
    out = wr(inp)
    # Get probability (not binary) for smoother interpolation
    prob = torch.sigmoid(out).squeeze().cpu()  # (512, 512)

# Sample mask at v2d using bilinear interpolation
# v2d in [0,223], map to [-1,1] for grid_sample
v2d_norm = v2d.clone()
v2d_norm[:, 0] = v2d_norm[:, 0] / 223.5 * 2 - 1  # x: 0→-1, 223→1
v2d_norm[:, 1] = (223 - v2d[:, 1]) / 223.5 * 2 - 1  # flip Y: 0→1, 223→-1
grid = v2d_norm.view(1, -1, 1, 2)  # (1, 35709, 1, 2)
prob_4d = prob.view(1, 1, 512, 512)  # (1, 1, H, W)
sampled = F.grid_sample(prob_4d, grid, mode='bilinear', align_corners=False)
vert_prob = sampled[0, 0, :, 0]  # (35709,)

# Binary: threshold > 0.5
vert_w = (vert_prob > 0.5).float()

# ── Render UV (original uv_coords, no flip) ──
def rnd(attr, size=1000):
    uv_ = uv.float() * 2 - 1
    uv_ = torch.cat([uv_, torch.zeros(uv_.shape[0], 1)], dim=1)
    if attr.dim() == 1: attr = attr.unsqueeze(-1).repeat(1,3)
    rend = MeshRenderer_UV_cpu(size)
    with torch.no_grad():
        _,_,img,_ = rend(uv_.unsqueeze(0), tri, attr.unsqueeze(0))
    return img[0].cpu().numpy()

uv_tex = rnd(face_tex, 1000).transpose(1,2,0).clip(0,1)
uv_w   = rnd(vert_w, 1000)[0]

# ── Also render probability (0-1) for smoother UV map ──
uv_prob = rnd(vert_prob, 1000)[0]

# ── Save ──
import cv2

big = np.array(aligned_pil.resize((512,512), Image.NEAREST))
m = (prob > 0.5).numpy()
over = np.zeros_like(big); over[m] = [255,0,0]
ov = cv2.addWeighted(big, 0.6, over, 0.4, 0)
Image.fromarray(ov).save(f"{OUT}/1_wrinkles_on_photo.png")

Image.fromarray((m*255).astype(np.uint8)).save(f"{OUT}/2_wrinkle_mask_black.png")

bg = (uv_tex * 0.3 * 255).astype(np.uint8)
uv_over = bg.copy()
uv_over[uv_w > 0.5] = [255, 50, 50]
Image.fromarray(uv_over).save(f"{OUT}/3_uv_texture_wrinkles.png")

Image.fromarray((uv_w*255).astype(np.uint8)).save(f"{OUT}/4_uv_wrinkle_solo.png")

# UV probability map (smooth, 0-1)
Image.fromarray((uv_prob.clip(0,1)*255).astype(np.uint8)).save(f"{OUT}/5_uv_probability.png")

# UV probability over texture
uv_prob_over = bg.copy()
uv_prob_rgb = np.zeros((1000,1000,3), dtype=np.uint8)
uv_prob_rgb[:,:,0] = (uv_prob.clip(0,1)*255).astype(np.uint8)
uv_prob_over = cv2.addWeighted(bg, 0.6, uv_prob_rgb, 0.4, 0)
Image.fromarray(uv_prob_over).save(f"{OUT}/6_uv_probability_overlay.png")

print("Saved:")
for f in sorted(os.listdir(OUT)):
    print(f"  {OUT}/{f}")
