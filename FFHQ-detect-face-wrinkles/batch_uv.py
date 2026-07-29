#!/usr/bin/env python3
"""Batch: all photos → UV wrinkle atlas → compare."""
import os, sys, torch, numpy as np, json
from glob import glob
from PIL import Image
from types import SimpleNamespace
import torch.nn.functional as F

# DEV_FIX_TZ B4/P1.14: абсолютные пути к машине разработчика заменены на
# расчёт от расположения файла (+ env TDDFA_ROOT). Инициализация моделей
# 3DDFA выполняется в `pushd`, т.к. апстрим грузит веса по относительным
# путям "assets/..."; парные os.chdir внутри функций сохранены — они
# симметричны и теперь оперируют портируемыми абсолютными путями.
from pathlib import Path  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import FFHQ_ROOT, pushd, tddfa_root  # noqa: E402

TDDFA = str(tddfa_root())
FFHQ = str(FFHQ_ROOT)
PHOTO_DIR = sys.argv[1] if len(sys.argv) > 1 else f"{FFHQ}/е1"
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{FFHQ}/uv_atlas"
os.makedirs(OUT, exist_ok=True)
device = "cuda" if torch.cuda.is_available() else "cpu"

# ── Init 3DDFA ──
sys.path.insert(0, TDDFA)
from face_box import face_box
from model.recon import face_model
from util.cpu_renderer import MeshRenderer_UV_cpu

args = SimpleNamespace(device=device, iscrop=True, detector="retinaface",
    backbone="resnet50", ldm68=False, ldm106=False, ldm106_2d=False, ldm134=False,
    seg=False, seg_visible=False, useTex=False, extractTex=False)
with pushd(TDDFA):
    recon_model = face_model(args)
    facebox_detector = face_box(args).detector

# Will be set after first photo
tri = None
uv_coords = None

# ── Init wrinkle UNet ──
sys.path.insert(0, FFHQ)
from torchvision import transforms
from unet import UNet
ckpt = torch.load(f"{FFHQ}/res/cp/wrinkle_model.pth", map_location=device)
wr = UNet(n_channels=3, n_classes=1, bilinear=False, pretrained=True, freeze_encoder=True).to(device).eval()
wr.load_state_dict(ckpt["model_state_dict"])
tfm = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])

# ── Render UV (reuse renderer) ──
_rend = None
def render_uv_attr(attr, size=1000):
    global _rend
    if _rend is None:
        _rend = MeshRenderer_UV_cpu(size)
    uv_ = uv_coords.float() * 2 - 1
    uv_ = torch.cat([uv_, torch.zeros(uv_.shape[0], 1)], dim=1)
    rendered = []
    for a in attr:
        if a.dim() == 1:
            a_rgb = a.unsqueeze(-1).repeat(1,3)
        else:
            a_rgb = a
        with torch.no_grad():
            _,_,img,_ = _rend(uv_.unsqueeze(0), tri, a_rgb.unsqueeze(0))
        # img is (1,3,H,W). Take first channel (all 3 are same for 1D attr).
        rendered.append(img[0, 0].cpu().numpy())
    return np.stack(rendered)

# ── Process one photo ──
def process_photo(path, out_dir):
    global tri, uv_coords
    name = os.path.splitext(os.path.basename(path))[0]
    os.chdir(TDDFA)
    try:
        img_pil = Image.open(path).convert("RGB")
        _, img_tensor = facebox_detector(img_pil)
        recon_model.input_img = img_tensor.to(device)
        res = recon_model.forward()
    except Exception as e:
        print(f"  SKIP {name}: {e}")
        return None

    if tri is None:
        tri = torch.from_numpy(res["tri"]).long()
        if tri.dim() == 3: tri = tri[0]
    if uv_coords is None:
        uv_coords = torch.from_numpy(res["uv_coords"]).float()

    v2d = torch.from_numpy(res["v2d"][0]).float()

    os.chdir(FFHQ)
    aligned_np = (img_tensor[0].permute(1,2,0).cpu().numpy() * 255).astype(np.uint8)
    aligned_pil = Image.fromarray(aligned_np)
    inp = tfm(aligned_pil).unsqueeze(0).to(device)
    with torch.no_grad():
        out = wr(inp)
        prob = torch.sigmoid(out).squeeze().cpu()

    # Bilinear sample at v2d
    v2d_norm = v2d.clone()
    v2d_norm[:, 0] = v2d[:, 0] / 223.5 * 2 - 1
    v2d_norm[:, 1] = (223 - v2d[:, 1]) / 223.5 * 2 - 1
    grid = v2d_norm.view(1, -1, 1, 2)
    prob_4d = prob.view(1, 1, 512, 512)
    with torch.no_grad():
        sampled = F.grid_sample(prob_4d, grid, mode='bilinear', align_corners=False)
    vert_prob = sampled[0, 0, :, 0]

    np.save(f"{out_dir}/{name}_vert_prob.npy", vert_prob.numpy())

    uv_prob = render_uv_attr([vert_prob], 1000)[0]
    np.save(f"{out_dir}/{name}_uv_prob.npy", uv_prob)

    uv_bin = (uv_prob > 0.5).astype(np.uint8) * 255
    Image.fromarray(uv_bin).save(f"{out_dir}/{name}_uv_binary.png")
    Image.fromarray((uv_prob.clip(0,1)*255).astype(np.uint8)).save(f"{out_dir}/{name}_uv_prob.png")
    img_pil.resize((128,128)).save(f"{out_dir}/{name}_thumb.jpg")

    print(f"  OK {name}")
    return vert_prob.cpu().numpy()

# ── Main ──
photos = sorted(glob(f"{PHOTO_DIR}/*.jpg"))
print(f"Total photos: {len(photos)}")
print(f"Output: {OUT}")
print(f"Device: {device}")

all_vert_probs = []
names = []
for p in photos:
    name = os.path.splitext(os.path.basename(p))[0]
    f_vert = f"{OUT}/{name}_vert_prob.npy"
    if os.path.exists(f_vert):
        print(f"  LOAD {name}")
        all_vert_probs.append(np.load(f_vert))
        names.append(name)
        continue
    vp = process_photo(p, OUT)
    if vp is not None:
        all_vert_probs.append(vp)
        names.append(name)

N = len(all_vert_probs)
print(f"\nProcessed/loaded: {N}/{len(photos)}")

if N == 0:
    print("No photos processed."); sys.exit(1)

# Ensure mesh topology is loaded (needed for render_uv_attr)
if uv_coords is None:
    # Process the first photo just to get mesh data
    for p in photos:
        name = os.path.splitext(os.path.basename(p))[0]
        os.chdir(TDDFA)
        try:
            img_pil = Image.open(p).convert("RGB")
            _, img_tensor = facebox_detector(img_pil)
            recon_model.input_img = img_tensor.to(device)
            res = recon_model.forward()
            tri = torch.from_numpy(res["tri"]).long()
            if tri.dim() == 3: tri = tri[0]
            uv_coords = torch.from_numpy(res["uv_coords"]).float()
            print(f"  Mesh loaded from {name}")
        except Exception as e:
            print(f"  SKIP {name} for mesh: {e}")
            continue
        break

vert_stack = np.stack(all_vert_probs)
V = vert_stack.shape[1]
print(f"Vertices: {V}")

# ── Stats ──
mean_vert = vert_stack.mean(axis=0)
std_vert = vert_stack.std(axis=0)
np.save(f"{OUT}/mean_vert.npy", mean_vert)
np.save(f"{OUT}/std_vert.npy", std_vert)

mean_uv = render_uv_attr([torch.from_numpy(mean_vert)], 1000)[0]
std_uv = render_uv_attr([torch.from_numpy(std_vert)], 1000)[0]
np.save(f"{OUT}/mean_uv.npy", mean_uv)
np.save(f"{OUT}/std_uv.npy", std_uv)
Image.fromarray((mean_uv.clip(0,1)*255).astype(np.uint8)).save(f"{OUT}/mean_uv.png")
Image.fromarray((std_uv.clip(0,1)*255).astype(np.uint8)).save(f"{OUT}/std_uv.png")

# ── Pairwise correlation (wrinkle-zone only) ──
zone_mask = (vert_stack > 0.1).sum(axis=0) > max(5, N // 4)
Z = zone_mask.sum()
print(f"Wrinkle-zone vertices: {Z}/{V}")

corr = np.zeros((N, N))
for i in range(N):
    for j in range(i, N):
        vi = all_vert_probs[i][zone_mask]
        vj = all_vert_probs[j][zone_mask]
        svi, svj = vi.std(), vj.std()
        if svi < 0.01 or svj < 0.01:
            c = 0.0
        else:
            c = ((vi - vi.mean()) * (vj - vj.mean())).sum() / (svi * svj * (len(vi) - 1))
        corr[i,j] = corr[j,i] = c

np.save(f"{OUT}/pairwise_corr.npy", corr)

# ── Cosine similarity on ALL vertices ──
cos = np.zeros((N, N))
for i in range(N):
    vi = all_vert_probs[i]
    for j in range(i, N):
        vj = all_vert_probs[j]
        ni, nj = np.linalg.norm(vi), np.linalg.norm(vj)
        c = float(vi @ vj / (ni * nj + 1e-8)) if ni > 1e-8 and nj > 1e-8 else 0.0
        cos[i,j] = cos[j,i] = c
np.save(f"{OUT}/pairwise_cosine.npy", cos)

# ── Pearson on ALL vertices ──
corr_all = np.zeros((N, N))
for i in range(N):
    vi = all_vert_probs[i]
    for j in range(i, N):
        vj = all_vert_probs[j]
        svi, svj = vi.std(), vj.std()
        if svi < 1e-6 or svj < 1e-6:
            c = 0.0
        else:
            c = float(((vi - vi.mean()) * (vj - vj.mean())).sum() / (svi * svj * (V - 1)))
        corr_all[i,j] = corr_all[j,i] = c
np.save(f"{OUT}/pairwise_corr_all.npy", corr_all)

mean_corr = corr.mean(axis=1)
print("\nPer-photo mean pairwise correlation (sorted):")
for idx in np.argsort(-mean_corr):
    print(f"  {names[idx]:30s}: {mean_corr[idx]:.4f}")

upper_idx = np.triu_indices(N, k=1)
summary = {
    "N": N, "total_photos": len(photos), "V": int(V),
    "wrinkle_zone_vertices": int(Z),
    "overall_mean_corr_wrinkle_zone": float(np.mean(corr[upper_idx])),
    "overall_std_corr_wrinkle_zone": float(np.std(corr[upper_idx])),
    "overall_mean_corr_all_vertices": float(np.mean(corr_all[upper_idx])),
    "overall_mean_cosine_all_vertices": float(np.mean(cos[upper_idx])),
    "per_photo_mean_corr_wrinkle_zone": {names[i]: float(mean_corr[i]) for i in range(N)},
    "per_photo_mean_corr_all": {names[i]: float(corr_all[i].mean()) for i in range(N)},
    "per_photo_mean_cosine": {names[i]: float(cos[i].mean()) for i in range(N)},
    "photo_order": names,
}
with open(f"{OUT}/summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"Overall mean pairwise corr (wrinkle-zone, {Z} verts): {summary['overall_mean_corr_wrinkle_zone']:.4f}")
print(f"Overall mean pairwise corr (all {V} verts): {summary['overall_mean_corr_all_vertices']:.4f}")
print(f"Overall mean cosine similarity (all {V} verts): {summary['overall_mean_cosine_all_vertices']:.4f}")

# ── Visual ──
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    im = axes[0,0].imshow(corr, vmin=0, vmax=1, cmap="viridis")
    axes[0,0].set_title(f"Pairwise corr wrinkle-zone ({Z}v)")
    plt.colorbar(im, ax=axes[0,0])

    im = axes[0,1].imshow(corr_all, vmin=0, vmax=1, cmap="viridis")
    axes[0,1].set_title(f"Pairwise corr all verts")
    plt.colorbar(im, ax=axes[0,1])

    im = axes[0,2].imshow(cos, vmin=0, vmax=1, cmap="viridis")
    axes[0,2].set_title(f"Pairwise cosine all verts")
    plt.colorbar(im, ax=axes[0,2])

    axes[1,0].imshow(mean_uv, cmap="gray")
    axes[1,0].set_title(f"Mean wrinkle prob ({summary['overall_mean_cosine_all_vertices']:.3f})")

    axes[1,1].imshow(std_uv, cmap="hot")
    axes[1,1].set_title("Std dev")

    zone_uv = render_uv_attr([torch.from_numpy(zone_mask.astype(np.float32))], 1000)[0]
    axes[1,2].imshow(zone_uv, cmap="gray")
    axes[1,2].set_title(f"Wrinkle-zone mask ({Z} verts)")

    plt.tight_layout()
    plt.savefig(f"{OUT}/analysis.png", dpi=150)
    print("Saved analysis.png")
except Exception as e:
    print(f"Viz skipped: {e}")

print(f"\nDone. Results in {OUT}/")
