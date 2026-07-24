#!/usr/bin/env python3
"""UV wrinkle atlas preview for ONE photo."""
import os, sys, torch, numpy as np
from PIL import Image
from types import SimpleNamespace

TDDFA_ROOT = "/Users/victorkhudyakov/work/3ddfa_v3"
FFHQ_ROOT  = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles"
PHOTO      = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles/е1/2000_06_14.jpg"
MASK       = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles/e1_result/2000_06_14_mask.png"
OUT_DIR    = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles/uv_wrinkle_test"
os.makedirs(OUT_DIR, exist_ok=True)

device = "cuda" if torch.cuda.is_available() else "cpu"

# ── 1. Init 3DDFA ──────────────────────────────────────────────────
os.chdir(TDDFA_ROOT)
sys.path.insert(0, TDDFA_ROOT)
from face_box import face_box
from model.recon import face_model
from util.cpu_renderer import MeshRenderer_UV_cpu, MeshRenderer_cpu

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

# ── 3. Init renderers ─────────────────────────────────────────────
# UV renderer renders per-vertex attributes onto UV atlas
uv_renderer = MeshRenderer_UV_cpu(rasterize_size=1000)
# 2D renderer renders mesh onto a 2D image (to get face texture on the image plane)
img_renderer = MeshRenderer_cpu(rasterize_fov=12, rasterize_size=224)

# ── 4. Load photo + run 3DDFA ─────────────────────────────────────
print("Running 3DDFA...")
img_pil = Image.open(PHOTO).convert("RGB")
trans_params, img_tensor = facebox_detector(img_pil)
os.chdir(TDDFA_ROOT)
recon_model.input_img = img_tensor.to(device)
results = recon_model.forward()

v2d     = torch.from_numpy(results["v2d"][0]).float()
uv_raw  = torch.from_numpy(results["uv_coords"]).float()
tri     = torch.from_numpy(results["tri"]).long()
if tri.dim() == 3:
    tri = tri[0]
v3d     = torch.from_numpy(results["v3d"][0]).float()
face_tex = torch.from_numpy(results["face_texture"][0]).float()  # per-vertex RGB (0-1)
render_face = results.get("render_face")
if render_face is not None:
    render_face = torch.from_numpy(render_face[0]).float() if isinstance(render_face, np.ndarray) else render_face[0].float()

# ── 5. Run wrinkle model ──────────────────────────────────────────
print("Running wrinkle model...")
img_for_wrinkle = img_pil.resize((512, 512), Image.Resampling.LANCZOS)
face_tensor = wrinkle_tfm(img_for_wrinkle).unsqueeze(0).to(device)
with torch.no_grad():
    wr_out = wrinkle_net(face_tensor)
    wr_pred = torch.sigmoid(wr_out).cpu().numpy()
wr_mask = (wr_pred > 0.5).astype(np.float32).squeeze()  # (512, 512)

# Also load the existing mask
existing_mask = np.array(Image.open(MASK).convert("L"), dtype=np.float32) / 255.0

# ── 6. Map wrinkle mask to vertices ───────────────────────────────
# v2d is in 224x224 cropped face space. Wrinkle mask is 512x512 in the
# FFHQ crop. We use the 3DDFA's rendered face to find the correspondence.
# Better: render the 3D mesh with face_texture onto a 224x224 image,
# then compare with the actual 224x224 crop to find alignment offset.

# Simple approach: just use scale factor
scale = 512.0 / 224.0
v2d_512 = v2d * scale
v2d_int = v2d_512.long()
v2d_int[:, 0] = v2d_int[:, 0].clamp(0, 511)
v2d_int[:, 1] = v2d_int[:, 1].clamp(0, 511)

vert_wrinkle = torch.from_numpy(existing_mask[v2d_int[:, 1].numpy(), v2d_int[:, 0].numpy()]).float()

# ── 7. Render wrinkle + texture onto UV atlas ─────────────────────

def render_to_uv(per_vertex_attr, uv_coords, tri, size=1000):
    """Render per-vertex attribute onto UV atlas."""
    uv = uv_coords.float() * 2.0 - 1.0
    if uv.shape[1] == 2:
        uv = torch.cat([uv, torch.zeros(uv.shape[0], 1)], dim=1)
    if per_vertex_attr.dim() == 1:
        attr_3ch = per_vertex_attr.unsqueeze(-1).repeat(1, 3)
    else:
        attr_3ch = per_vertex_attr
    renderer = MeshRenderer_UV_cpu(rasterize_size=size)
    with torch.no_grad():
        _, _, rendered, _ = renderer(
            uv.unsqueeze(0), tri, attr_3ch.unsqueeze(0), visible_vertice=False)
    return rendered[0].cpu().numpy()  # (3, H, W)

print("Rendering UV atlas...")

# UV texture atlas (face albedo with lighting)
uv_tex = render_to_uv(face_tex, uv_raw, tri, 1000)
uv_tex_img = uv_tex.transpose(1, 2, 0)  # (H, W, 3)
uv_tex_img = np.clip(uv_tex_img, 0, 1)

# UV wrinkle atlas
uv_wr = render_to_uv(vert_wrinkle, uv_raw, tri, 1000)
uv_wr_map = uv_wr[0]  # first channel

# ── 8. Create composite visualization ─────────────────────────────
import cv2

# 8a. Original photo
orig_display = np.array(img_pil.resize((512, 512), Image.Resampling.LANCZOS))

# 8b. UV texture atlas (dimmed) + wrinkle overlay
uv_bg = (uv_tex_img * 0.4 * 255).astype(np.uint8)  # dimmed
uv_overlay = np.zeros((1000, 1000, 3), dtype=np.uint8)
uv_overlay[uv_wr_map > 0.5] = [255, 0, 0]  # red for wrinkles
composite = cv2.addWeighted(uv_bg, 1.0, uv_overlay, 0.7, 0)

# ── 9. Save ───────────────────────────────────────────────────────
Image.fromarray(orig_display).save(os.path.join(OUT_DIR, "1_original.png"))
Image.fromarray((uv_tex_img * 255).astype(np.uint8)).save(os.path.join(OUT_DIR, "2_uv_texture.png"))
Image.fromarray(composite).save(os.path.join(OUT_DIR, "3_uv_wrinkle_overlay.png"))
Image.fromarray((uv_wr_map * 255).astype(np.uint8)).save(os.path.join(OUT_DIR, "4_uv_wrinkle_mask.png"))

print(f"\nSaved to {OUT_DIR}/:")
for f in ["1_original.png", "2_uv_texture.png", "3_uv_wrinkle_overlay.png", "4_uv_wrinkle_mask.png"]:
    print(f"  {f}")
