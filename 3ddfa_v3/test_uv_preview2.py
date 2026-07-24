#!/usr/bin/env python3
"""UV wrinkle atlas — правильное совмещение через render_face из 3DDFA."""
import os, sys, torch, numpy as np
from PIL import Image
from types import SimpleNamespace

TDDFA_ROOT = "/Users/victorkhudyakov/work/3ddfa_v3"
FFHQ_ROOT  = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles"
PHOTO      = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles/е1/2000_06_14.jpg"
OUT_DIR    = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles/uv_wrinkle_test"
os.makedirs(OUT_DIR, exist_ok=True)

device = "cuda" if torch.cuda.is_available() else "cpu"

# ── 1. Init 3DDFA ──────────────────────────────────────────────────
os.chdir(TDDFA_ROOT)
sys.path.insert(0, TDDFA_ROOT)
from face_box import face_box
from model.recon import face_model
from util.cpu_renderer import MeshRenderer_UV_cpu

args = SimpleNamespace(
    device=device, iscrop=True, detector="retinaface", backbone="resnet50",
    ldm68=False, ldm106=False, ldm106_2d=False, ldm134=False,
    seg=False, seg_visible=False, useTex=False, extractTex=False,
)
recon_model = face_model(args)
facebox_detector = face_box(args).detector

# ── 2. Init Wrinkle model ─────────────────────────────────────────
os.chdir(FFHQ_ROOT)
sys.path.insert(0, FFHQ_ROOT)
from torchvision import transforms
from unet import UNet

ckpt = torch.load(f"{FFHQ_ROOT}/res/cp/wrinkle_model.pth", map_location=device)
wrinkle_net = UNet(n_channels=3, n_classes=1, bilinear=False, pretrained=True, freeze_encoder=True).to(device).eval()
wrinkle_net.load_state_dict(ckpt["model_state_dict"])

wrinkle_tfm = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])

inv_normalize = transforms.Normalize(
    mean=[-0.485/0.229, -0.456/0.224, -0.406/0.225],
    std=[1/0.229, 1/0.224, 1/0.225]
)

# ── 3. Init UV renderer ───────────────────────────────────────────
uv_renderer = MeshRenderer_UV_cpu(rasterize_size=1000)

# ── 4. Load photo + run 3DDFA ─────────────────────────────────────
print("1. Running 3DDFA...")
img_pil = Image.open(PHOTO).convert("RGB")
trans_params, img_tensor = facebox_detector(img_pil)
os.chdir(TDDFA_ROOT)
recon_model.input_img = img_tensor.to(device)
results = recon_model.forward()

# Extract data
v2d     = torch.from_numpy(results["v2d"][0]).float()     # (35709, 2) in 224x224
uv_raw  = torch.from_numpy(results["uv_coords"]).float()
tri     = torch.from_numpy(results["tri"]).long()
if tri.dim() == 3: tri = tri[0]
face_tex = torch.from_numpy(results["face_texture"][0]).float()  # per-vertex

# Get the rendered face from 3DDFA (224x224, same coordinate space as v2d)
render_face_t = results.get("render_face")
if render_face_t is None:
    print("ERROR: render_face not found!")
    sys.exit(1)
render_face_t = torch.from_numpy(render_face_t[0]) if isinstance(render_face_t, np.ndarray) else render_face_t[0]
# render_face_t is (224, 224, 3) in 0-1 range, BGR from OpenCV

# Convert to RGB PIL
render_face_np = render_face_t.cpu().numpy()
render_face_rgb = render_face_np[..., ::-1]  # BGR -> RGB
render_face_rgb = np.clip(render_face_rgb, 0, 1)
render_face_pil = Image.fromarray((render_face_rgb * 255).astype(np.uint8))

# ── 5. Run wrinkle model on 3DDFA's rendered face ─────────────────
print("2. Running wrinkle model on 3DDFA crop...")
# The rendered face is already aligned with v2d coordinates
# But it's BGR, we need RGB. wrinkle_tfm expects RGB.
face_tensor = wrinkle_tfm(render_face_pil).unsqueeze(0).to(device)
with torch.no_grad():
    wr_out = wrinkle_net(face_tensor)
    wr_pred = torch.sigmoid(wr_out).cpu().numpy()
wr_mask = (wr_pred > 0.5).astype(np.float32).squeeze()  # (512, 512)

# ── 6. Map wrinkle mask to vertices (perfect alignment!) ──────────
# v2d is in 224x224, wr_mask is 512x512 (resized from 224x224 by wrinkle_tfm)
scale = 512.0 / 224.0
v2d_512 = v2d * scale
v2d_int = v2d_512.long()
v2d_int[:, 0] = v2d_int[:, 0].clamp(0, 511)
v2d_int[:, 1] = v2d_int[:, 1].clamp(0, 511)

vert_wrinkle = torch.from_numpy(wr_mask[v2d_int[:, 1].numpy(), v2d_int[:, 0].numpy()]).float()

# ── 7. Render onto UV atlas ───────────────────────────────────────
print("3. Rendering UV atlas...")

def render_to_uv(attr, uv_coords, tri, size=1000):
    uv = uv_coords.float() * 2.0 - 1.0
    if uv.shape[1] == 2:
        uv = torch.cat([uv, torch.zeros(uv.shape[0], 1)], dim=1)
    if attr.dim() == 1:
        attr = attr.unsqueeze(-1).repeat(1, 3)
    rend = MeshRenderer_UV_cpu(rasterize_size=size)
    with torch.no_grad():
        _, _, img, _ = rend(uv.unsqueeze(0), tri, attr.unsqueeze(0))
    return img[0].cpu().numpy()

# 7a. UV face texture (BFM albedo + lighting, dimmed background)
uv_tex = render_to_uv(face_tex, uv_raw, tri, 1000)
uv_tex_img = uv_tex.transpose(1, 2, 0)  # (H, W, 3)
uv_tex_img = np.clip(uv_tex_img, 0, 1)

# 7b. UV wrinkle atlas
uv_wr = render_to_uv(vert_wrinkle, uv_raw, tri, 1000)
uv_wr_map = uv_wr[0]

# ── 8. Create visualization ───────────────────────────────────────
import cv2

# 8a. Original photo
orig_display = np.array(img_pil.resize((512, 512), Image.Resampling.LANCZOS))

# 8b. 3DDFA rendered face (224x224 -> 512x512)
rend_display = np.array(render_face_pil.resize((512, 512), Image.Resampling.NEAREST))

# 8c. Wrinkle mask on the rendered face (512x512)
wr_display = (wr_mask * 255).astype(np.uint8)
wr_overlay = np.zeros((512, 512, 3), dtype=np.uint8)
wr_overlay[wr_mask > 0.5] = [0, 0, 255]
rend_overlay = cv2.addWeighted(rend_display, 0.6, wr_overlay, 0.4, 0)

# 8d. UV texture (dimmed) + wrinkle overlay
uv_bg = (uv_tex_img * 0.35 * 255).astype(np.uint8)
uv_over = np.zeros((1000, 1000, 3), dtype=np.uint8)
uv_over[uv_wr_map > 0.5] = [255, 0, 0]
uv_composite = cv2.addWeighted(uv_bg, 1.0, uv_over, 0.7, 0)

# 8e. UV texture full brightness for reference
uv_full = (uv_tex_img * 255).astype(np.uint8)

# 8f. Combined overview: place images side by side
h1, w1 = 512, 512
h2, w2 = 1000, 1000
# Scale UV to fit
uv_small = cv2.resize(uv_composite, (512, 512))
uv_full_small = cv2.resize(uv_full, (512, 512))
uv_wr_small = cv2.resize((uv_wr_map * 255).astype(np.uint8), (512, 512))
uv_wr_small_3ch = cv2.cvtColor(uv_wr_small, cv2.COLOR_GRAY2RGB)

# Layout: top row = original, rendered, wr_overlay
#         bottom row = UV_tex, UV_wr, UV_composite
top = np.hstack([orig_display, rend_display, rend_overlay])
bot = np.hstack([uv_full_small, uv_wr_small_3ch, uv_small])
overview = np.vstack([top, bot])

# Labels
overview_rgb = cv2.cvtColor(overview.astype(np.uint8), cv2.COLOR_RGB2BGR)
for i, label in enumerate(["Original", "3DDFA render", "Wrinkles overlay"]):
    cv2.putText(overview_rgb, label, (i*512 + 10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
for i, label in enumerate(["UV texture", "UV wrinkles", "UV composite"]):
    cv2.putText(overview_rgb, label, (i*512 + 10, 512 + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
overview_final = cv2.cvtColor(overview_rgb, cv2.COLOR_BGR2RGB)

# ── 9. Save ───────────────────────────────────────────────────────
Image.fromarray(overview_final).save(os.path.join(OUT_DIR, "overview.png"))
Image.fromarray(uv_full).save(os.path.join(OUT_DIR, "uv_texture.png"))
Image.fromarray(uv_composite).save(os.path.join(OUT_DIR, "uv_wrinkle_overlay.png"))
Image.fromarray((uv_wr_map * 255).astype(np.uint8)).save(os.path.join(OUT_DIR, "uv_wrinkle_mask.png"))
Image.fromarray(rend_display).save(os.path.join(OUT_DIR, "render_face.png"))
Image.fromarray(rend_overlay).save(os.path.join(OUT_DIR, "render_wrinkles.png"))

# Also save with zone outlines for context
zone_data = np.load(f"{TDDFA_ROOT}/atlas/texture_zones_bfm35709_v3.npz", allow_pickle=True)
tri_zones = zone_data["triangle_subzone_label"]  # (70789,) 0-39
# Render zone boundaries by finding edges
tri_np = tri.numpy()
uv_v = (uv_raw.numpy() * 1000).astype(int)
uv_v[:, 1] = 1000 - uv_v[:, 1]  # flip Y

zone_borders = np.zeros((1000, 1000, 3), dtype=np.uint8)
for t_idx in range(tri_np.shape[0]):
    z = tri_zones[t_idx]
    if z < 0: continue
    v0, v1, v2 = tri_np[t_idx]
    pts = np.array([uv_v[v0][:2], uv_v[v1][:2], uv_v[v2][:2]], dtype=np.int32)
    cv2.polylines(zone_borders, [pts], True, (100, 100, 100), 1)

# Add wrinkle zone labels from metadata
import json
with open(f"{TDDFA_ROOT}/atlas/texture_zones_v3_metadata.json") as f:
    meta = json.load(f)
zone_names = {z["code"]: z["name_ru"] for z in meta["focus"]}
focus_codes = zone_data["focus_codes"]

# Color each wrinkle focus zone differently
focus_colors = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 255, 0), (255, 128, 0),
    (0, 128, 255), (128, 0, 255), (255, 0, 128), (0, 255, 128),
    (200, 200, 0), (0, 200, 200),
]
focus_mask = zone_data["triangle_focus_mask"]  # (14, 70789)
zone_img = np.zeros((1000, 1000, 3), dtype=np.uint8)
for f_idx in range(14):
    tri_in_zone = np.where(focus_mask[f_idx])[0]
    for t_idx in tri_in_zone:
        v0, v1, v2 = tri_np[t_idx]
        pts = np.array([uv_v[v0][:2], uv_v[v1][:2], uv_v[v2][:2]], dtype=np.int32)
        cv2.fillPoly(zone_img, [pts], focus_colors[f_idx])
        cv2.polylines(zone_img, [pts], True, (50, 50, 50), 1)

# Blend zone overlay with texture
zone_overlay_final = cv2.addWeighted(uv_full, 0.5, zone_img, 0.5, 0)
Image.fromarray(zone_overlay_final).save(os.path.join(OUT_DIR, "uv_zones.png"))

wp = float(wr_mask.sum() / wr_mask.size * 100)
print(f"\nWrinkle on render: {wp:.2f}%")
print(f"UV wrinkle pixels: {int((uv_wr_map > 0.5).sum())} / 1,000,000")
print(f"\nSaved:")
for f in os.listdir(OUT_DIR):
    if f in ["overview.png", "uv_texture.png", "uv_wrinkle_overlay.png", 
             "uv_wrinkle_mask.png", "uv_zones.png", "render_face.png", "render_wrinkles.png"]:
        print(f"  {OUT_DIR}/{f}")
