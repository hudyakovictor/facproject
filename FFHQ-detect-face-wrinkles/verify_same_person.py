import os
import sys
import torch
import numpy as np
from PIL import Image
from torchvision import transforms
from glob import glob

sys.path.insert(0, os.path.dirname(__file__))
face_parsing_dir = os.path.join(os.path.dirname(__file__), "face-parsing.PyTorch")
sys.path.append(face_parsing_dir)
from unet import UNet
from model import BiSeNet

# DEV_FIX_TZ B4/P1.14: fallback-пути к машине разработчика удалены.
from pathlib import Path  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import FFHQ_ROOT, optional_out_dir, require_arg  # noqa: E402

input_dir = require_arg(sys.argv, 1, "входной каталог с фото",
                        "python verify_same_person.py <input_dir> [output_dir]")
output_dir = optional_out_dir(sys.argv, 2, FFHQ_ROOT / "output_result")

device = "cuda" if torch.cuda.is_available() else "cpu"

checkpoint = torch.load(FFHQ_ROOT / "res" / "cp" / "wrinkle_model.pth", map_location=device)
unet = UNet(n_channels=3, n_classes=1, bilinear=False, pretrained=True, freeze_encoder=True).to(device).eval()
unet.load_state_dict(checkpoint["model_state_dict"])

net = BiSeNet(n_classes=19).to(device)
net.load_state_dict(torch.load(FFHQ_ROOT / "res" / "cp" / "face_segmentation.pth", map_location=device))
net.eval()

transform = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])
to_tensor = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
])

image_files = sorted([
    f for f in os.listdir(input_dir)
    if f.lower().endswith((".jpg", ".jpeg", ".png")) and not f.endswith("_overlay.png") and not f.endswith("_mask.png")
])

all_skin_pcts = []

for img_name in image_files:
    img_path = os.path.join(input_dir, img_name)
    img = Image.open(img_path).convert("RGB")
    img_512 = img.resize((512, 512), Image.Resampling.BILINEAR)

    img_t = to_tensor(img_512).unsqueeze(0).to(device)
    with torch.no_grad():
        out = net(img_t)[0]
        parsing = out.squeeze(0).cpu().numpy().argmax(0)

    face_t = transform(img_512).unsqueeze(0).to(device)
    with torch.no_grad():
        wr_out = unet(face_t)
        wr_pred = torch.sigmoid(wr_out).cpu().numpy()
    wr_mask = (wr_pred > 0.5).astype(np.uint8).squeeze()

    skin_mask = (parsing == 1)
    skin_pixels = skin_mask.sum()
    wrinkle_on_skin = (wr_mask * skin_mask).sum()
    skin_wrinkle_pct = float((wrinkle_on_skin / skin_pixels) * 100) if skin_pixels > 0 else 0.0

    total_pct = float((wr_mask.sum() / wr_mask.size) * 100)

    name = os.path.splitext(img_name)[0]
    all_skin_pcts.append(skin_wrinkle_pct)
    print(f"{name:<30} skin_wrinkle={skin_wrinkle_pct:.2f}%  total_wrinkle={total_pct:.2f}%")

all_skin_pcts = np.array(all_skin_pcts)
print(f"\n--- Skin wrinkle statistics across all {len(all_skin_pcts)} photos ---")
print(f"Mean:     {all_skin_pcts.mean():.2f}%")
print(f"Std:      {all_skin_pcts.std():.2f}%")
print(f"Min:      {all_skin_pcts.min():.2f}%")
print(f"Max:      {all_skin_pcts.max():.2f}%")
print(f"Median:   {np.median(all_skin_pcts):.2f}%")
print(f"CV (std/mean): {all_skin_pcts.std() / all_skin_pcts.mean():.2f}")

z_scores = np.abs(all_skin_pcts - all_skin_pcts.mean()) / all_skin_pcts.std()
outliers = [(image_files[i], all_skin_pcts[i]) for i in range(len(all_skin_pcts)) if z_scores[i] > 2]
if outliers:
    print(f"\nPotential outliers (|z| > 2):")
    for name, pct in outliers:
        print(f"  {name}: {pct:.2f}%")
else:
    print(f"\nNo outliers - all photos within 2 std of mean (consistent wrinkle density)")
