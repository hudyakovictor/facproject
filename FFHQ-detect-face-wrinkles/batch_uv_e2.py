#!/usr/bin/env python3
"""Batch UV atlas with z-buffer visibility masking."""
import os, sys, torch, numpy as np, json
from glob import glob
from PIL import Image
from types import SimpleNamespace
import torch.nn.functional as F

TDDFA = "/Users/victorkhudyakov/work/3ddfa_v3"
FFHQ  = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles"
PHOTO_DIR = sys.argv[1] if len(sys.argv) > 1 else f"{FFHQ}/е1"
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{FFHQ}/uv_atlas"
os.makedirs(OUT, exist_ok=True)
device = "cuda" if torch.cuda.is_available() else "cpu"

# ── Init 3DDFA ──
os.chdir(TDDFA); sys.path.insert(0, TDDFA)
from face_box import face_box
from model.recon import face_model
from util.cpu_renderer import MeshRenderer_UV_cpu

args = SimpleNamespace(device=device, iscrop=True, detector="retinaface",
    backbone="resnet50", ldm68=False, ldm106=False, ldm106_2d=False, ldm134=False,
    seg=False, seg_visible=False, useTex=False, extractTex=False)
recon_model = face_model(args)
facebox_detector = face_box(args).detector

tri = None; uv_coords = None

# ── Load focus zones + nose zone filter ──
zp = f"{TDDFA}/atlas/texture_zones_bfm35709_v3.npz"
with np.load(zp) as data:
    tri_main_label = data["triangle_main_label"]  # (70789,) triangle → A-label 0-19
    tri_focus = data["triangle_focus_mask"]        # (14, 70789) W-zone masks

meta = json.load(open(f"{TDDFA}/atlas/texture_zones_v3_metadata.json"))

# nose A-zones (0-indexed): A08→7, A11→10, A12→11
nose_A = {7, 10, 11}
nose_tri_mask = np.isin(tri_main_label, list(nose_A))
nose_vert_mask = np.zeros(35709, dtype=bool)

# ── Init wrinkle UNet ──
os.chdir(FFHQ); sys.path.insert(0, FFHQ)
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

# ── UV renderer ──
_rend = None
def render_uv_attr(attr, size=1000):
    global _rend
    if _rend is None:
        _rend = MeshRenderer_UV_cpu(size)
    uv_ = uv_coords.float() * 2 - 1
    uv_ = torch.cat([uv_, torch.zeros(uv_.shape[0], 1)], dim=1)
    if attr.dim() == 1:
        attr_rgb = attr.unsqueeze(-1).repeat(1,3)
    else:
        attr_rgb = attr
    with torch.no_grad():
        _,_,img,_ = _rend(uv_.unsqueeze(0), tri, attr_rgb.unsqueeze(0))
    return img[0, 0].cpu().numpy()

def compute_face_normals(v3d, tri):
    """Compute vertex normals from v3d. Returns normalized (V,3)."""
    v0 = v3d[0, tri[:, 0]]
    v1 = v3d[0, tri[:, 1]]
    v2 = v3d[0, tri[:, 2]]
    fn = torch.cross(v1 - v0, v2 - v0)
    fn = F.normalize(fn, dim=1)
    vn = torch.zeros(v3d.shape[1], 3, device=v3d.device)
    vn.index_add_(0, tri[:, 0], fn)
    vn.index_add_(0, tri[:, 1], fn)
    vn.index_add_(0, tri[:, 2], fn)
    return F.normalize(vn, dim=1)

# ── Process one photo ──
def process_photo(path, out_dir):
    global tri, uv_coords, nose_vert_mask
    name = os.path.splitext(os.path.basename(path))[0]
    os.chdir(TDDFA)
    try:
        img_pil = Image.open(path).convert("RGB")
        _, img_tensor = facebox_detector(img_pil)
        recon_model.input_img = img_tensor.to(device)
        res = recon_model.forward()
    except Exception as e:
        print(f"  SKIP {name}: {e}")
        return None, None

    if tri is None:
        tri = torch.from_numpy(res["tri"]).long()
        if tri.dim() == 3: tri = tri[0]
    if uv_coords is None:
        uv_coords = torch.from_numpy(res["uv_coords"]).float()

    v3d = torch.from_numpy(res["v3d"]).float()
    v2d = torch.from_numpy(res["v2d"][0]).float()

    # ── Z-buffer visibility ──
    with torch.no_grad():
        _, _, _, visible_verts = recon_model.renderer(
            v3d.clone(), recon_model.tri.clone(),
            visible_vertice=True
        )
    vis = torch.zeros(v3d.shape[1], dtype=torch.bool)
    vis[visible_verts] = True

    # also backface-cull via normals
    vn = compute_face_normals(v3d, recon_model.tri)
    vis = vis & (vn[:, 2] > 0)

    # ── Build nose vertex mask (from tri labels, computed once) ──
    if not nose_vert_mask.any():
        nose_v = np.unique(recon_model.tri.cpu().numpy()[nose_tri_mask])
        nose_vert_mask[nose_v] = True
        np.save(f"{OUT}/nose_vert_mask.npy", nose_vert_mask)

    os.chdir(FFHQ)
    aligned_np = (img_tensor[0].permute(1,2,0).cpu().numpy() * 255).astype(np.uint8)
    aligned_pil = Image.fromarray(aligned_np)
    inp = tfm(aligned_pil).unsqueeze(0).to(device)
    with torch.no_grad():
        out = wr(inp); prob = torch.sigmoid(out).squeeze().cpu()

    # sample wrinkle at v2d
    v2d_norm = v2d.clone()
    v2d_norm[:, 0] = v2d[:, 0] / 223.5 * 2 - 1
    v2d_norm[:, 1] = (223 - v2d[:, 1]) / 223.5 * 2 - 1
    grid = v2d_norm.view(1, -1, 1, 2)
    prob_4d = prob.view(1, 1, 512, 512)
    with torch.no_grad():
        sampled = F.grid_sample(prob_4d, grid, mode='bilinear', align_corners=False)
    vert_prob = sampled[0, 0, :, 0]

    # apply visibility mask: zero out wrinkle for invisible vertices
    vert_prob[~vis] = 0.0

    # apply nose filter: zero out wrinkle on nose vertices
    vert_prob[nose_vert_mask] = 0.0

    np.save(f"{out_dir}/{name}_vert_prob.npy", vert_prob.cpu().numpy())
    np.save(f"{out_dir}/{name}_vis.npy", vis.cpu().numpy())
    print(f"  OK {name} (vis={vis.sum()}/{len(vis)})")
    return vert_prob.cpu().numpy(), vis.cpu().numpy()

# ── Main ──
photos = sorted(glob(f"{PHOTO_DIR}/*.jpg"))
print(f"Photos: {len(photos)} → {OUT}")

all_vert = []; all_vis = []
names = []
for p in photos:
    name = os.path.splitext(os.path.basename(p))[0]
    f_vert = f"{OUT}/{name}_vert_prob.npy"
    f_vis  = f"{OUT}/{name}_vis.npy"
    if os.path.exists(f_vert) and os.path.exists(f_vis):
        print(f"  LOAD {name}")
        all_vert.append(np.load(f_vert)); all_vis.append(np.load(f_vis))
        names.append(name)
        continue
    vp, vm = process_photo(p, OUT)
    if vp is not None:
        all_vert.append(vp); all_vis.append(vm); names.append(name)

N = len(all_vert)
print(f"Done: {N}/{len(photos)}")
if N == 0: sys.exit(1)

# ensure tri/uv_coords loaded
if tri is None:
    for p in photos:
        name = os.path.splitext(os.path.basename(p))[0]
        os.chdir(TDDFA)
        try:
            img_pil = Image.open(p).convert("RGB")
            _, img_tensor = facebox_detector(img_pil); recon_model.input_img = img_tensor.to(device)
            res = recon_model.forward()
            tri = torch.from_numpy(res["tri"]).long()
            if tri.dim() == 3: tri = tri[0]
            uv_coords = torch.from_numpy(res["uv_coords"]).float()
        except: continue
        break

stack = np.stack(all_vert)
vis_stack = np.stack(all_vis)
V = stack.shape[1]

# visibility count per vertex
vis_count = vis_stack.sum(axis=0)
# fraction: wrinkle-positive / visible-photos
frac_vert = np.where(vis_count > 0, (stack > 0.5).sum(axis=0) / vis_count, 0.0)

np.save(f"{OUT}/frac_vert.npy", frac_vert)
np.save(f"{OUT}/vis_count.npy", vis_count)

print(f"Vertices: {V}, Mean visibility: {vis_count.mean():.1f}/{N}")

# ── Render ──
print("Rendering frac at 4000...")
frac_vert_t = torch.from_numpy(frac_vert)
uv_ = uv_coords.float() * 2 - 1
uv_ = torch.cat([uv_, torch.zeros(uv_.shape[0], 1)], dim=1)
rend = MeshRenderer_UV_cpu(4000)
attr_rgb = frac_vert_t.unsqueeze(-1).repeat(1,3)
with torch.no_grad():
    _,_,img,_ = rend(uv_.unsqueeze(0), tri, attr_rgb.unsqueeze(0))
raw = img[0,0].cpu().numpy()
small = np.array(Image.fromarray((raw*255).astype(np.uint8)).resize((1000,1000), Image.BILINEAR)) / 255.0

# threshold: >=3 visible photos
min_vis = 3
show = vis_count.max() > 0
vis_uv = render_uv_attr(torch.from_numpy(vis_count.astype(np.float32)), 1000)

# mask: visible in >=3 photos AND wrinkle fraction > 0
mask = (small > 3/N) & (small > 0)
boosted = small ** 0.7

def hot(x):
    r = np.clip(x*3,0,1); r[x>1/3]=1
    g = np.clip(x*3-1,0,1); g[x>2/3]=1
    b = np.clip(x*3-2,0,1)
    return np.stack([r,g,b],axis=-1)

rgb = hot(boosted) * mask[:,:,None]
out_img = (rgb * 255).astype(np.uint8)
Image.fromarray(out_img).save(f"{OUT}/frac_intersect_3plus.png")

print(f"Saved {OUT}/frac_intersect_3plus.png (N={N}, vis≥3 px: {mask.sum():,})")

# also save visibility count UV
vis_norm = vis_uv / N
Image.fromarray((vis_norm.clip(0,1)*255).astype(np.uint8)).save(f"{OUT}/vis_count_uv.png")

raw_small = np.array(Image.fromarray((raw*255).astype(np.uint8)).resize((1000,1000), Image.BILINEAR)) / 255.0
np.save(f"{OUT}/frac_map.npy", raw_small)

summary = {"N": N, "photos": names}
with open(f"{OUT}/summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# compute nose filter stats
print(f"Nose verts in mask: {nose_vert_mask.sum()}")
print(f"Done.")
