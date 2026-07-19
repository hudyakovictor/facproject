from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

SURFACE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SURFACE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from surface_lab.backends import FFHQWrinkleBackend
from surface_lab.graphs import skeletonize_probability, graph_summary


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def parse_csv_floats(s: str) -> list[float]:
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def parse_csv_strings(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def list_images(folder: Path) -> list[Path]:
    return sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS])


def safe_name(p: Path) -> str:
    stem = p.stem.replace(" ", "_")
    keep = []
    for ch in stem:
        keep.append(ch if ch.isalnum() or ch in "._-" else "_")
    return "".join(keep)[:120] or "image"


def fit_square_bgr(img: np.ndarray, size: int = 320) -> np.ndarray:
    h, w = img.shape[:2]
    scale = min(size / max(1, w), size / max(1, h))
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((size, size, 3), np.uint8)
    y = (size - nh) // 2
    x = (size - nw) // 2
    canvas[y:y+nh, x:x+nw] = small
    return canvas


def overlay_bgr(base: np.ndarray, prob: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    mask = np.ones(prob.shape, bool)
    binary, skel = skeletonize_probability(prob, mask, threshold, min_px=8)
    out = base.copy()
    # faint probability heat; white skeleton on top
    heat = cv2.applyColorMap(np.round(np.clip(prob, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    alpha = (np.clip(prob, 0, 1) * 0.45)[..., None]
    out = np.clip(out * (1 - alpha) + heat * alpha, 0, 255).astype(np.uint8)
    out[skel] = (255, 255, 255)
    info = graph_summary(skel)
    info.update({"threshold": float(threshold), "binary_pixels": int(binary.sum())})
    return out, binary, skel, info


def add_label(tile: np.ndarray, text: str) -> np.ndarray:
    out = tile.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(out, text[:42], (7, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def make_contact_sheet(items: list[tuple[str, Path]], out_path: Path, cols: int = 4, tile: int = 320) -> None:
    if not items:
        return
    imgs = []
    for label, p in items:
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        imgs.append(add_label(fit_square_bgr(img, tile), label))
    if not imgs:
        return
    rows = int(np.ceil(len(imgs) / cols))
    sheet = np.zeros((rows * tile, cols * tile, 3), np.uint8)
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        sheet[r*tile:(r+1)*tile, c*tile:(c+1)*tile] = img
    cv2.imwrite(str(out_path), sheet)


def main() -> int:
    ap = argparse.ArgumentParser(description="FFHQ wrinkle survey on plain photo folders. No 3DDFA, no UV, no Stage1.")
    ap.add_argument("--input", required=True, help="Folder with ordinary photos")
    ap.add_argument("--output", required=True, help="Output folder")
    ap.add_argument("--ffhq-repo", required=True, help="Path to FFHQ-detect-face-wrinkles repo")
    ap.add_argument("--checkpoint", required=True, help="Path to wrinkle_model.pth")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--detail-modes", default="none,gentle", help="CSV: none,gentle,strong,clahe")
    ap.add_argument("--thresholds", default="0.25,0.35,0.50", help="CSV probability thresholds")
    ap.add_argument("--copy-originals", action="store_true")
    args = ap.parse_args()

    in_dir = Path(args.input).expanduser().resolve()
    out_dir = Path(args.output).expanduser().resolve()
    if not in_dir.exists():
        raise FileNotFoundError(in_dir)
    photos = list_images(in_dir)
    if args.limit:
        photos = photos[:args.limit]
    if not photos:
        raise SystemExit(f"No images found in {in_dir}")

    thresholds = parse_csv_floats(args.thresholds)
    detail_modes = parse_csv_strings(args.detail_modes)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "schema": "ffhq-wrinkle-photo-survey-1",
        "input": str(in_dir),
        "photo_count": len(photos),
        "detail_modes": detail_modes,
        "thresholds": thresholds,
        "note": "Plain photo survey only: no 3DDFA, no UV, no identity comparison.",
        "records": [],
    }

    for mode in detail_modes:
        print(f"[mode] {mode}")
        backend = FFHQWrinkleBackend(args.ffhq_repo, args.checkpoint, args.device, input_size=512, detail_mode=mode)
        mode_dir = out_dir / mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        contacts: dict[float, list[tuple[str, Path]]] = {t: [] for t in thresholds}
        for i, photo in enumerate(photos, 1):
            print(f"  [{i}/{len(photos)}] {photo.name}")
            bgr = cv2.imread(str(photo), cv2.IMREAD_COLOR)
            if bgr is None:
                print(f"    skip unreadable: {photo}")
                continue
            name = f"{i:04d}_{safe_name(photo)}"
            rec_dir = mode_dir / name
            rec_dir.mkdir(parents=True, exist_ok=True)
            if args.copy_originals:
                shutil.copy2(photo, rec_dir / f"original{photo.suffix.lower()}")
            prob = backend.predict(bgr, None)
            model_input = backend.last_input_bgr if backend.last_input_bgr is not None else bgr
            cv2.imwrite(str(rec_dir / "model_input.jpg"), model_input)
            cv2.imwrite(str(rec_dir / "probability.png"), np.round(np.clip(prob, 0, 1) * 255).astype(np.uint8))
            rec = {"file": str(photo), "name": name, "detail_mode": mode, "thresholds": {}}
            for t in thresholds:
                overlay, binary, skel, info = overlay_bgr(bgr, prob, t)
                model_overlay, _, _, _ = overlay_bgr(model_input, prob, t)
                tag = f"t{int(round(t*100)):03d}"
                overlay_path = rec_dir / f"overlay_{tag}.jpg"
                cv2.imwrite(str(overlay_path), overlay)
                cv2.imwrite(str(rec_dir / f"model_input_overlay_{tag}.jpg"), model_overlay)
                cv2.imwrite(str(rec_dir / f"skeleton_{tag}.png"), skel.astype(np.uint8) * 255)
                cv2.imwrite(str(rec_dir / f"binary_{tag}.png"), binary.astype(np.uint8) * 255)
                rec["thresholds"][str(t)] = info
                contacts[t].append((photo.name, overlay_path))
            (rec_dir / "report.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            summary["records"].append(rec)
        for t, items in contacts.items():
            tag = f"t{int(round(t*100)):03d}"
            make_contact_sheet(items, mode_dir / f"contact_sheet_{mode}_{tag}.jpg", cols=4, tile=320)

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE photos={len(photos)} modes={','.join(detail_modes)} output={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
