import os
import sys
import torch
import numpy as np
import cv2
from PIL import Image
from torchvision import transforms
from glob import glob

sys.path.insert(0, os.path.dirname(__file__))
face_parsing_dir = os.path.join(os.path.dirname(__file__), "face-parsing.PyTorch")
sys.path.append(face_parsing_dir)
from unet import UNet
from face_parsing_extraction import parse_face
from model import BiSeNet

# DEV_FIX_TZ B4/P1.14: fallback-пути к машине разработчика удалены.
from pathlib import Path  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import FFHQ_ROOT, optional_out_dir, require_arg  # noqa: E402

input_dir = require_arg(sys.argv, 1, "входной каталог с фото",
                        "python compare_regions.py <input_dir> [output_dir]")
output_dir = optional_out_dir(sys.argv, 2, FFHQ_ROOT / "output_result")

device = "cuda" if torch.cuda.is_available() else "cpu"

checkpoint = torch.load(FFHQ_ROOT / "res" / "cp" / "wrinkle_model.pth", map_location=device)
model = UNet(n_channels=3, n_classes=1, bilinear=False, pretrained=True, freeze_encoder=True).to(device).eval()
model.load_state_dict(checkpoint["model_state_dict"])

net = BiSeNet(n_classes=19).to(device)
net.load_state_dict(torch.load(FFHQ_ROOT / "res" / "cp" / "face_segmentation.pth", map_location=device))
net.eval()

wrinkle_transform = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])

to_tensor = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
])

image_exts = (".jpg", ".jpeg", ".png", ".bmp", ".tiff")
image_files = sorted([
    f for f in os.listdir(input_dir)
    if f.lower().endswith(image_exts) and not f.endswith("_overlay.png") and not f.endswith("_mask.png") and not f == ".DS_Store"
])

FACIAL_REGIONS = {
    0: "background",
    1: "skin",
    2: "left_eyebrow",
    3: "right_eyebrow",
    4: "left_eye",
    5: "right_eye",
    6: "nose",
    7: "upper_lip",
    8: "lower_lip",
    9: "mouth",
    10: "hair",
    11: "left_ear",
    12: "right_ear",
    13: "neck",
}

wrinkle_regions = {}
face_info = {}

for img_name in image_files:
    img_path = os.path.join(input_dir, img_name)
    img = Image.open(img_path).convert("RGB")
    img_resized = img.resize((512, 512), Image.Resampling.BILINEAR)

    img_tensor = to_tensor(img_resized).unsqueeze(0).to(device)
    with torch.no_grad():
        out = net(img_tensor)[0]
        parsing = out.squeeze(0).cpu().numpy().argmax(0)

    face_tensor = wrinkle_transform(img_resized).unsqueeze(0).to(device)
    with torch.no_grad():
        wrinkle_output = model(face_tensor)
        wrinkle_pred = torch.sigmoid(wrinkle_output).cpu().numpy()
    wrinkle_mask = (wrinkle_pred > 0.5).astype(np.uint8).squeeze()

    name = os.path.splitext(img_name)[0]
    region_data = {"total_wrinkle_pct": float((wrinkle_mask.sum() / wrinkle_mask.size) * 100)}

    for label_id, label_name in FACIAL_REGIONS.items():
        region_mask = (parsing == label_id)
        region_pixels = region_mask.sum()
        if region_pixels > 50:
            wrinkle_in_region = (wrinkle_mask * region_mask).sum()
            region_pct = float((wrinkle_in_region / region_pixels) * 100)
            region_data[label_name] = round(region_pct, 2)
        else:
            region_data[label_name] = None

    wrinkle_regions[name] = region_data
    face_info[name] = {"parsing": parsing, "wrinkle_mask": wrinkle_mask}

    print(f"{name}: total {region_data['total_wrinkle_pct']:.2f}%", end="")
    active = [(k, v) for k, v in region_data.items() if k != "total_wrinkle_pct" and v is not None and v > 0.1]
    if active:
        print(f", regions: {dict(active[:3])}", end="")
    print()

REGION_KEYS = [k for k in next(iter(wrinkle_regions.values())).keys() if k != "total_wrinkle_pct"]

print(f"\n{'Photo':<30} {'Total%':<8}", end="")
for rk in REGION_KEYS:
    print(f"{rk:<14}", end="")
print()
print("-" * (30 + 8 + 14 * len(REGION_KEYS)))

for name in sorted(wrinkle_regions.keys()):
    rd = wrinkle_regions[name]
    print(f"{name:<30} {rd['total_wrinkle_pct']:<8.2f}", end="")
    for rk in REGION_KEYS:
        v = rd.get(rk)
        if v is not None:
            print(f"{v:<14.2f}", end="")
        else:
            print(f"{'':<14}", end="")
    print()

print(f"\n--- Regional wrinkle signature similarity (top-20 pairs) ---\n")

def region_vector(rd):
    vec = []
    for rk in REGION_KEYS:
        v = rd.get(rk)
        if v is None:
            vec.append(0.0)
        else:
            vec.append(v)
    return np.array(vec, dtype=np.float64)

def cosine_sim(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

names_list = sorted(wrinkle_regions.keys())
results = []
for i in range(len(names_list)):
    for j in range(i + 1, len(names_list)):
        n1, n2 = names_list[i], names_list[j]
        v1 = region_vector(wrinkle_regions[n1])
        v2 = region_vector(wrinkle_regions[n2])
        sim = cosine_sim(v1, v2)
        diff_pct = abs(wrinkle_regions[n1]["total_wrinkle_pct"] - wrinkle_regions[n2]["total_wrinkle_pct"])
        results.append((sim, n1, n2, diff_pct))

results.sort(key=lambda x: -x[0])

print(f"{'Rank':<5} {'Similarity':<12} {'Photo 1':<30} {'Photo 2':<30} {'%Diff':<8}")
print("-" * 85)
for i, (sim, n1, n2, dp) in enumerate(results[:20]):
    print(f"{i+1:<5} {sim:<12.4f} {n1:<30} {n2:<30} {dp:<8.2f}")

all_sims = [r[0] for r in results]
print(f"\nSimilarity stats: mean={np.mean(all_sims):.4f}, min={np.min(all_sims):.4f}, max={np.max(all_sims):.4f}, std={np.std(all_sims):.4f}")
print(f"All {len(results)} pairs have similarity >= {min(all_sims):.4f}")
