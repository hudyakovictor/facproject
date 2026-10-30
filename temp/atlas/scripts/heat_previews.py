"""PNG-примеры карты из настоящего preview-эндпоинта.

Рендер идёт через `GET /api/photos/{id}/preview` — тот же код, который
вызывает интерфейс, поэтому картинки показывают именно то, что увидит
пользователь. Для каждой пары кадров сохраняются четыре режима и общая
панель.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 python scripts/heat_previews.py
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import ingest_and_process, select_frames  # noqa: E402

MODES = [
    ("euclid", "distance", "none"),
    ("normal", "normal", "none"),
    ("weighted_euclid", "distance", "calibrated"),
    ("weighted_normal", "normal", "calibrated"),
]
CAPTION = 34
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


def tile(image, text):
    """Кадр с подписью снизу, чтобы панель читалась без отчёта."""
    from PIL import Image, ImageDraw, ImageFont

    out = Image.new("RGB", (image.width, image.height + CAPTION), (255, 255, 255))
    out.paste(image, (0, 0))
    font = None
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            font = ImageFont.truetype(path, 20)
            break
    draw = ImageDraw.Draw(out)
    draw.text((8, image.height + 7), text, fill=(20, 20, 20), font=font)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--person", default=None, help="по умолчанию первый по алфавиту")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "reports/calibration")
    args = ap.parse_args()

    from fastapi.testclient import TestClient
    from PIL import Image

    from server.app import app

    index_path = args.calibration_root / "all_calibration_index.csv"
    selected = select_frames(index_path, args.photos_root, args.per_person)
    if not selected:
        raise SystemExit("корпус не выбран")
    ingest_and_process(selected, False)
    person = args.person or sorted(selected)[0]
    rows = sorted(selected[person], key=lambda r: int(r["frame"]))
    if len(rows) < 2:
        raise SystemExit("нужно хотя бы два кадра")
    reference, target = rows[0], rows[-1]

    client = TestClient(app)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tiles, saved = [], []
    for name, metric, weighting in MODES:
        params = {
            "other": target["id"],
            "reference": reference["id"],
            "morphing": "false",
            "t": 0.0,
            "size": args.size,
            "heatmap": "true",
            "normalizeScale": "true",
            "metric": metric,
            "weighting": weighting,
            "palette": "turbo",
            "opacity": 1.0,
        }
        response = client.get(f"/api/photos/{target['id']}/preview", params=params)
        if response.status_code != 200:
            raise SystemExit(f"{name}: preview {response.status_code} {response.text[:200]}")
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        path = args.out_dir / f"v3-preview-{name}.png"
        image.save(path)
        saved.append(str(path.relative_to(ROOT)))
        tiles.append(tile(image, f"{name}"))
        print(f"{name:16s} -> {path.relative_to(ROOT)}")

    width = sum(t.width for t in tiles)
    height = max(t.height for t in tiles)
    panel = Image.new("RGB", (width, height), (255, 255, 255))
    x = 0
    for t in tiles:
        panel.paste(t, (x, 0))
        x += t.width
    panel_path = args.out_dir / "v3-preview-modes.png"
    panel.save(panel_path)
    print("panel ->", panel_path.relative_to(ROOT))

    manifest = {
        "person": person,
        "reference_frame": int(reference["frame"]),
        "target_frame": int(target["frame"]),
        "bins": [reference["bin"], target["bin"]],
        "size": args.size,
        "endpoint": "GET /api/photos/{id}/preview",
        "normalizeScale": True,
        "files": saved + [str(panel_path.relative_to(ROOT))],
    }
    (args.out_dir / "v3-preview.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1))
    print("frames", manifest["reference_frame"], "->", manifest["target_frame"],
          "bins", manifest["bins"])


if __name__ == "__main__":
    main()
