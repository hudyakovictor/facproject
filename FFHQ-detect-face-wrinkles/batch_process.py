import os
import sys
import shutil
import torch
import cv2
import numpy as np
from torchvision import transforms
from PIL import Image
from unet import UNet
from face_parsing_extraction import parse_face
from face_detection import detect_face, calculate_wrinkle_metrics

# DEV_FIX_TZ B4/P1.14: fallback-путь к каталогу на машине разработчика удалён —
# входной каталог обязан быть указан явно (см. _paths.require_arg).
from pathlib import Path  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import FFHQ_ROOT, optional_out_dir, require_arg  # noqa: E402

input_dir = require_arg(sys.argv, 1, "входной каталог с фото",
                        "python batch_process.py <input_dir> [output_dir]")
output_dir = optional_out_dir(sys.argv, 2, FFHQ_ROOT / "output_batch")

device = "cuda" if torch.cuda.is_available() else "cpu"

checkpoint = torch.load(FFHQ_ROOT / "res" / "cp" / "wrinkle_model.pth", map_location=device)
model = (
    UNet(n_channels=3, n_classes=1, bilinear=False, pretrained=True, freeze_encoder=True)
    .to(device)
    .eval()
)
model.load_state_dict(checkpoint["model_state_dict"])

wrinkle_transform = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])

os.makedirs(output_dir, exist_ok=True)
temp_dir = os.path.join(output_dir, "temp")
os.makedirs(temp_dir, exist_ok=True)

image_exts = (".jpg", ".jpeg", ".png", ".bmp", ".tiff")
image_files = [f for f in os.listdir(input_dir) if f.lower().endswith(image_exts) and not f.endswith("_overlay.png") and not f.endswith("_mask.png")]
image_files.sort()

for img_name in image_files:
    img_path = os.path.join(input_dir, img_name)
    img = Image.open(img_path).convert("RGB")
    resized = img.resize((512, 512), Image.Resampling.LANCZOS)

    face_detected = detect_face(resized)
    if face_detected is None:
        print(f"{img_name}: No face detected")
        continue

    temp_img_path = os.path.join(temp_dir, img_name)
    resized.save(temp_img_path)

    processed_face = parse_face(dspth=temp_dir, cp="face_segmentation.pth")

    face_tensor = wrinkle_transform(processed_face).unsqueeze(0).to(device)
    with torch.no_grad():
        wrinkle_output = model(face_tensor)
        wrinkle_prediction = torch.sigmoid(wrinkle_output).cpu().numpy()

    wrinkle_mask = (wrinkle_prediction > 0.5).astype(np.uint8)
    wrinkle_pct = calculate_wrinkle_metrics(wrinkle_mask)

    resized_np = np.array(resized)
    mask_3ch = np.squeeze(wrinkle_mask) * 255
    mask_3ch = np.stack([mask_3ch] * 3, axis=-1).astype(np.uint8)
    overlay = cv2.addWeighted(resized_np, 0.7, mask_3ch, 0.3, 0)

    base_name = os.path.splitext(img_name)[0]
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_overlay.png"), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_mask.png"), np.squeeze(wrinkle_mask) * 255)

    print(f"{img_name}: Wrinkle percentage = {wrinkle_pct}%")

    for f in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, f))

shutil.rmtree(temp_dir)
print(f"\nDone. Results saved in '{output_dir}/'")
