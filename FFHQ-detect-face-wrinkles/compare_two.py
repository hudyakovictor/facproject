#!/usr/bin/env python3
"""Process two photo folders → UV wrinkle maps → compare → same-person probability."""
import os, sys, torch, numpy as np, json
from glob import glob
from PIL import Image
from types import SimpleNamespace
import torch.nn.functional as F

PYTHON = "/Users/victorkhudyakov/work/.venv/bin/python"
TDDFA = "/Users/victorkhudyakov/work/3ddfa_v3"
FFHQ  = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles"
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"

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

# ── Load zones ──
with np.load(f"{TDDFA}/atlas/texture_zones_bfm35709_v3.npz") as data:
    tri_main_label = data["triangle_main_label"]
    tri_focus = data["triangle_focus_mask"]

meta = json.load(open(f"{TDDFA}/atlas/texture_zones_v3_metadata.json"))

# nose filter: A08(7), A11(10), A12(11)
nose_tri = np.isin(tri_main_label, [7, 10, 11])

# W-zone focus triangles
focus_tri = tri_focus  # (14, 70789) bool

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

def compute_face_normals(v3d, tri_t):
    v0 = v3d[0, tri_t[:, 0]]
    v1 = v3d[0, tri_t[:, 1]]
    v2 = v3d[0, tri_t[:, 2]]
    fn = F.normalize(torch.cross(v1 - v0, v2 - v0, dim=1), dim=1)
    vn = torch.zeros(v3d.shape[1], 3, device=v3d.device)
    vn.index_add_(0, tri_t[:, 0], fn)
    vn.index_add_(0, tri_t[:, 1], fn)
    vn.index_add_(0, tri_t[:, 2], fn)
    return F.normalize(vn, dim=1)

# ── State ──
tri = None; uv_coords = None; nose_vert_mask = None; focus_vert_masks = None

def process_folder(photo_dir, out_dir, label):
    """Process all photos in folder → compute frac_vert + vis_count."""
    global tri, uv_coords, nose_vert_mask, focus_vert_masks
    os.makedirs(out_dir, exist_ok=True)

    photos = sorted(glob(f"{photo_dir}/*.jpg"))
    print(f"\n{'='*60}")
    print(f"[{label}] Photos: {len(photos)} → {out_dir}")
    print(f"{'='*60}")

    all_vert = []; all_vis = []
    names = []
    for p in photos:
        name = os.path.splitext(os.path.basename(p))[0]
        f_vert = f"{out_dir}/{name}_vert_prob.npy"
        f_vis  = f"{out_dir}/{name}_vis.npy"
        if os.path.exists(f_vert) and os.path.exists(f_vis):
            print(f"  LOAD {name}")
            all_vert.append(np.load(f_vert)); all_vis.append(np.load(f_vis))
            names.append(name)
            continue
        vp, vm = _process_one(p, out_dir, name)
        if vp is not None:
            all_vert.append(vp); all_vis.append(vm); names.append(name)

    N = len(all_vert)
    print(f"[{label}] Done: {N}/{len(photos)}")
    if N < 3:
        print(f"[{label}] Too few photos ({N}), skipping comparison.")
        return None, None

    # Ensure mesh data loaded (needed for rendering)
    _ensure_mesh(photo_dir)

    stack = np.stack(all_vert)
    vis_stack = np.stack(all_vis)
    V = stack.shape[1]

    vis_count = vis_stack.sum(axis=0)
    frac = np.divide((stack > 0.5).sum(axis=0), vis_count, where=vis_count > 2, out=np.zeros_like(stack[0]))

    np.save(f"{out_dir}/frac_vert.npy", frac)
    np.save(f"{out_dir}/vis_count.npy", vis_count)

    # Render frac map
    _render_frac(frac, vis_count, N, f"{out_dir}/frac_map.png")
    print(f"[{label}] Mean frac: {frac[frac>0].mean():.3f}, vis verts: {(vis_count>2).sum()}/{V}")

    return frac, vis_count

def _ensure_mesh(fallback_dir):
    """Ensure tri and uv_coords are loaded (e.g. when all photos cached)."""
    global tri, uv_coords, nose_vert_mask, focus_vert_masks
    if uv_coords is not None:
        return
    os.chdir(TDDFA)
    try:
        photos_here = sorted(glob(f"{fallback_dir}/*.jpg"))
        if not photos_here:
            print("  _ensure_mesh: no photos found")
            return
        p = photos_here[0]
        img_pil = Image.open(p).convert("RGB")
        _, img_tensor = facebox_detector(img_pil)
        recon_model.input_img = img_tensor.to(device)
        res = recon_model.forward()
        tri = torch.from_numpy(res["tri"]).long()
        if tri.dim() == 3: tri = tri[0]
        uv_coords = torch.from_numpy(res["uv_coords"]).float()
        # build vertex masks
        nose_v = np.unique(recon_model.tri.cpu().numpy()[nose_tri])
        nose_vert_mask = np.zeros(35709, dtype=bool)
        nose_vert_mask[nose_v] = True
        focus_vert_masks = []
        for w in range(14):
            fv = np.unique(recon_model.tri.cpu().numpy()[focus_tri[w]])
            fm = np.zeros(35709, dtype=bool); fm[fv] = True
            focus_vert_masks.append(fm)
        print(f"  Mesh loaded, nose_vert_mask sum: {nose_vert_mask.sum()}")
    except Exception as e:
        print(f"  _ensure_mesh FAILED: {e}")
        raise

def _process_one(path, out_dir, name):
    global tri, uv_coords, nose_vert_mask, focus_vert_masks
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
    if nose_vert_mask is None:
        nose_v = np.unique(recon_model.tri.cpu().numpy()[nose_tri])
        nose_vert_mask = np.zeros(35709, dtype=bool)
        nose_vert_mask[nose_v] = True
    if focus_vert_masks is None:
        focus_vert_masks = []
        for w in range(14):
            fv = np.unique(recon_model.tri.cpu().numpy()[focus_tri[w]])
            fm = np.zeros(35709, dtype=bool); fm[fv] = True
            focus_vert_masks.append(fm)

    v3d = torch.from_numpy(res["v3d"]).float()
    v2d = torch.from_numpy(res["v2d"][0]).float()

    # Z-buffer visibility
    with torch.no_grad():
        _, _, _, visible_verts = recon_model.renderer(
            v3d.clone(), recon_model.tri.clone(), visible_vertice=True)
    vis = torch.zeros(v3d.shape[1], dtype=torch.bool)
    vis[visible_verts] = True
    vn = compute_face_normals(v3d, recon_model.tri)
    vis = vis & (vn[:, 2] > 0)

    # Wrinkle UNet
    os.chdir(FFHQ)
    aligned_np = (img_tensor[0].permute(1,2,0).cpu().numpy() * 255).astype(np.uint8)
    inp = tfm(Image.fromarray(aligned_np)).unsqueeze(0).to(device)
    with torch.no_grad():
        prob = torch.sigmoid(wr(inp)).squeeze().cpu()

    v2d_norm = v2d.clone()
    v2d_norm[:, 0] = v2d[:, 0] / 223.5 * 2 - 1
    v2d_norm[:, 1] = (223 - v2d[:, 1]) / 223.5 * 2 - 1
    grid = v2d_norm.view(1, -1, 1, 2)
    with torch.no_grad():
        vert_prob = F.grid_sample(
            prob.view(1, 1, 512, 512), grid, mode='bilinear', align_corners=False
        )[0, 0, :, 0]

    vert_prob[~vis] = 0.0
    vert_prob[nose_vert_mask] = 0.0

    np.save(f"{out_dir}/{name}_vert_prob.npy", vert_prob.cpu().numpy())
    np.save(f"{out_dir}/{name}_vis.npy", vis.cpu().numpy())
    print(f"  OK {name} (vis={vis.sum()})")
    return vert_prob.cpu().numpy(), vis.cpu().numpy()

def _render_frac(frac, vis_count, N, save_path):
    frac_t = torch.from_numpy(frac)
    uv_ = uv_coords.float() * 2 - 1
    uv_ = torch.cat([uv_, torch.zeros(uv_.shape[0], 1)], dim=1)
    rend = MeshRenderer_UV_cpu(4000)
    with torch.no_grad():
        _,_,img,_ = rend(uv_.unsqueeze(0), tri,
                         frac_t.unsqueeze(-1).repeat(1,3).unsqueeze(0))
    raw = img[0,0].cpu().numpy()
    small = np.array(Image.fromarray((raw*255).astype(np.uint8)
        ).resize((1000,1000), Image.BILINEAR)) / 255.0
    mask = (small > 3/N) & (small > 0)
    boosted = small ** 0.7
    def hot(x):
        r = (x*3).clip(0,1); r[x>1/3]=1
        g = (x*3-1).clip(0,1); g[x>2/3]=1
        b = (x*3-2).clip(0,1)
        return np.stack([r,g,b], axis=-1)
    rgb = hot(boosted) * mask[:,:,None]
    Image.fromarray((rgb*255).astype(np.uint8)).save(save_path)
    print(f"  Rendered {save_path}")

def compare_sets(frac1, frac2, vis1, vis2, label1, label2, out_dir):
    """Compare two wrinkle fraction maps and compute same-person probability."""
    print(f"\n{'='*60}")
    print(f"COMPARISON: {label1} vs {label2}")
    print(f"{'='*60}")

    # Only consider vertices visible in ≥3 photos in BOTH sets
    valid = (vis1 > 2) & (vis2 > 2)
    Vv = valid.sum()
    print(f"Valid vertices (vis≥3 both): {Vv}/{len(valid)}")

    if Vv < 100:
        print("Too few valid vertices for comparison.")
        return

    f1, f2 = frac1[valid], frac2[valid]

    # 1. Overall per-vertex Pearson
    mu1, mu2 = f1.mean(), f2.mean()
    s1, s2 = f1.std(), f2.std()
    if s1 > 1e-6 and s2 > 1e-6:
        pearson = ((f1 - mu1) * (f2 - mu2)).sum() / (s1 * s2 * (Vv - 1))
    else:
        pearson = 0.0
    print(f"Per-vertex Pearson (all valid): {pearson:.4f}")

    # 2. Within-zone Pearson (discounts generic wrinkle locations)
    zone_corrs = []
    for w, meta_w in enumerate(meta.get("focus", [])):
        zm = focus_vert_masks[w]
        zv = zm & valid
        if zv.sum() < 10:
            continue
        z1, z2 = frac1[zv], frac2[zv]
        # remove zone-level mean → keep spatial pattern only
        z1r, z2r = z1 - z1.mean(), z2 - z2.mean()
        sz1, sz2 = z1r.std(), z2r.std()
        if sz1 > 1e-6 and sz2 > 1e-6:
            zc = (z1r * z2r).sum() / (sz1 * sz2 * (len(z1) - 1))
        else:
            zc = 0.0
        zone_corrs.append(zc)

    within_zone_r = np.mean(zone_corrs) if zone_corrs else 0.0
    print(f"Within-zone mean Pearson ({len(zone_corrs)} zones): {within_zone_r:.4f}")

    # 3. Cosine similarity per zone
    zone_cos = []
    zone_frac1 = []; zone_frac2 = []
    for w in range(14):
        zm = focus_vert_masks[w]
        zv = zm & valid
        if zv.sum() < 10:
            continue
        z1, z2 = frac1[zv], frac2[zv]
        n1, n2 = np.linalg.norm(z1), np.linalg.norm(z2)
        if n1 > 1e-6 and n2 > 1e-6:
            zc = float(z1 @ z2 / (n1 * n2))
        else:
            zc = 0.0
        zone_cos.append(zc)
        zone_frac1.append(z1.mean())
        zone_frac2.append(z2.mean())

    mean_zone_cos = np.mean(zone_cos) if zone_cos else 0.0
    print(f"Within-zone mean cosine ({len(zone_cos)} zones): {mean_zone_cos:.4f}")

    # 4. Zone-level severity correlation
    zf1 = np.array([zone_frac1[i] for i in range(len(zone_frac1))])
    zf2 = np.array([zone_frac2[i] for i in range(len(zone_frac2))])
    if len(zf1) > 3:
        zr = np.corrcoef(zf1, zf2)[0, 1]
    else:
        zr = 0.0
    print(f"Zone-level severity Pearson ({len(zf1)} zones): {zr:.4f}")

    # 5. Same-person probability
    # Core insight: within-zone cosine similarity captures INDIVIDUAL-SPECIFIC
    # wrinkle patterns. Generic age-related wrinkles contribute only to the
    # zone-level mean, which we subtract in the within-zone analysis.
    # Higher within-zone similarity → more likely same person.
    #
    # Scale: 
    #   r ≈ 0.2-0.3 → different people (generic wrinkle locations)
    #   r ≈ 0.5-0.7 → same person (individual-specific patterns)
    #   r > 0.8 → identical or near-identical photos
    #
    # Convert to probability using sigmoid mapping:
    #   P = 1 / (1 + exp(-k * (r - r0)))
    # where r0 = 0.35 (threshold) and k = 8 (steepness)

    r0 = 0.35
    k = 8.0
    prob_same = 1.0 / (1.0 + np.exp(-k * (within_zone_r - r0)))

    # Also combine with overall Pearson for robustness
    combined_r = 0.4 * pearson + 0.6 * within_zone_r
    prob_combined = 1.0 / (1.0 + np.exp(-k * (combined_r - r0)))

    result = {
        "set1": label1,
        "set2": label2,
        "N1": int(vis1.shape[0]), "N2": int(vis2.shape[0]),
        "valid_vertices": int(Vv),
        "pearson_all_vertices": float(f"{pearson:.4f}"),
        "within_zone_pearson": float(f"{within_zone_r:.4f}"),
        "within_zone_cosine": float(f"{mean_zone_cos:.4f}"),
        "zone_severity_pearson": float(f"{zr:.4f}"),
        "within_zone_pearson_list": [float(f"{c:.4f}") for c in zone_corrs],
        "within_zone_cosine_list": [float(f"{c:.4f}") for c in zone_cos],
        "zone_severity_1": [float(f"{z:.4f}") for z in zf1],
        "zone_severity_2": [float(f"{z:.4f}") for z in zf2],
        "same_person_prob_spatial": float(f"{prob_same:.4f}"),
        "same_person_prob_combined": float(f"{prob_combined:.4f}"),
    }

    with open(f"{out_dir}/comparison.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n─── RESULTS ───")
    print(f"  Valid vertices:        {Vv:>6}")
    print(f"  Pearson (all valid):   {pearson:.4f}")
    print(f"  Within-zone Pearson:   {within_zone_r:.4f}")
    print(f"  Within-zone cosine:    {mean_zone_cos:.4f}")
    print(f"  Zone severity Pearson: {zr:.4f}")
    print(f"  ──────────────────────────────")
    print(f"  SAME-PERSON PROB (spatial):   {prob_same*100:.1f}%")
    print(f"  SAME-PERSON PROB (combined):  {prob_combined*100:.1f}%")
    print(f"  Saved to {out_dir}/comparison.json")

    return result


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════
if __name__ == "__main__":
    PHOTO1 = sys.argv[1] if len(sys.argv) > 1 else f"{FFHQ}/е1"
    PHOTO2 = sys.argv[2] if len(sys.argv) > 2 else f"{FFHQ}/e2"
    OUT = sys.argv[3] if len(sys.argv) > 3 else f"{FFHQ}/compare_result"
    os.makedirs(OUT, exist_ok=True)

    label1 = os.path.basename(PHOTO1.rstrip("/"))
    label2 = os.path.basename(PHOTO2.rstrip("/"))

    frac1, vis1 = process_folder(PHOTO1, f"{OUT}/{label1}", label1)
    frac2, vis2 = process_folder(PHOTO2, f"{OUT}/{label2}", label2)

    if frac1 is not None and frac2 is not None:
        vis_vec1 = np.load(f"{OUT}/{label1}/vis_count.npy")
        vis_vec2 = np.load(f"{OUT}/{label2}/vis_count.npy")
        compare_sets(frac1, frac2, vis_vec1, vis_vec2, label1, label2, OUT)

    print(f"\nDone. Results in {OUT}/")
