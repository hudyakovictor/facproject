"""Облегчённый detector-only проход: только face_box (без net_recon).

Выход: stage1_det_only/<photo_stem>/ldm106_detector2d.csv + detector_info.json.
Пиксели ориентированного входа, top-left origin. Дешёвая доля Stage 1.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from argparse import Namespace
from pathlib import Path

import numpy as np

WORK = Path("/Users/victorkhudyakov/work")
sys.path.insert(0, str(WORK / "3ddfa_v3"))


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--limit", type=int, default=0)
    a = p.parse_args()
    os.chdir(WORK)
    # Совместимость вендорного 3DDFA с torch<2.0 (weights_only добавлен в torch 2.x).
    import torch as _torch
    import inspect as _inspect
    try:
        if "weights_only" not in _inspect.signature(_torch.load).parameters:
            _orig = _torch.load

            def _compat(*a, **k):
                k.pop("weights_only", None)
                return _orig(*a, **k)

            _torch.load = _compat
    except Exception:
        pass
    from face_box import face_box
    from PIL import Image, ImageOps

    fb = face_box(Namespace(device="cpu", detector="retinaface", iscrop=True))
    photos = sorted([p for p in a.input.iterdir()
                     if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
    if a.limit:
        photos = photos[:a.limit]
    ok = err = 0
    t0 = time.time()
    for n, path in enumerate(photos, 1):
        out = a.output / path.stem
        done = out / "detector_info.json"
        if done.is_file():
            ok += 1
            continue
        try:
            with Image.open(path) as src:
                image = ImageOps.exif_transpose(src).convert("RGB")
            trans, tensor = fb.detector(image)
            lmks = getattr(getattr(fb, "impl", None), "last_lmks_106", None)
            info = {"source_filename": path.name,
                    "face_count": int(getattr(getattr(fb, 'impl', None), 'last_face_count', 0) or 0),
                    "has_landmarks": bool(lmks is not None),
                    "trans_params": np.asarray(trans, float).reshape(-1).tolist() if trans is not None else None}
            out.mkdir(parents=True, exist_ok=True)
            if lmks is not None:
                lmks = np.asarray(lmks, np.float32).reshape(106, 2)
                with open(out / "ldm106_detector2d.csv", "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["landmark_id", "x_px", "y_px"])
                    for i, (x, y) in enumerate(lmks):
                        w.writerow([i, f"{x:.4f}", f"{y:.4f}"])
            (out / "detector_info.json").write_text(json.dumps(info, ensure_ascii=False))
            ok += 1
        except Exception as exc:
            err += 1
            print(f"ERROR {path.name}: {exc}", flush=True)
        if n % 50 == 0:
            print(f"[{n}/{len(photos)}] ok={ok} err={err} elapsed={time.time()-t0:.0f}s", flush=True)
    print(f"DONE ok={ok} err={err} elapsed={time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
