#!/usr/bin/env python3
"""Зоны по разметке модели (annotation из face_model.npy) на канонической сетке бина."""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.face_model_io import load_face_model  # noqa: E402
from src.zones import canonical_mesh, check_disjoint, save_zones  # noqa: E402
from src.zones_annotation import zones_from_annotation  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Зоны лица по annotation из face_model.npy")
    p.add_argument("--meshes", required=True)
    p.add_argument("--face-model", required=True, help="3ddfa_v3/assets/face_model.npy")
    p.add_argument("--bin", default="frontal")
    p.add_argument("--min-frames", type=int, default=5)
    p.add_argument("--out-json", default="app10/configs/zones_annotation.json")
    p.add_argument("--out-png", default="app10/reports/zones_annotation_check.png")
    args = p.parse_args()

    fm = load_face_model(args.face_model)
    if "annotation" not in fm:
        sys.exit("в face_model.npy нет ключа annotation")

    frames = []
    for npz in sorted(Path(args.meshes).glob("*.npz")):
        try:
            d = np.load(npz, allow_pickle=True)
            if str(d["pose_bin"]) == args.bin:
                frames.append(d["v_aligned"].astype(np.float64))
        except Exception as e:  # noqa: BLE001
            print(f"SKIP {npz.name}: {e}")
    if len(frames) < args.min_frames:
        sys.exit(f"мало кадров бина {args.bin}: {len(frames)} < {args.min_frames}")

    canon = canonical_mesh(frames)
    if "ldm106" not in fm:
        sys.exit("в face_model.npy нет ключа ldm106 (нужен для границ от ориентов)")
    zones = zones_from_annotation(fm["annotation"], canon, fm["ldm106"], tri=fm["tri"])
    assert check_disjoint(zones)
    covered = sum(len(v) for v in zones.values())
    if covered != len(canon):
        sys.exit(f"зоны покрывают {covered} из {len(canon)} вершин")
    save_zones(args.out_json, zones, len(canon), rules={"method": "landmark+contour+normals"},
               source={"bin": args.bin, "n_frames": len(frames), "face_model": str(args.face_model)})
    counts = {k: len(v) for k, v in zones.items()}
    print("WROTE", args.out_json, counts)
    for z in ("cheek_r", "cheek_l", "side"):
        if z in counts:
            print(f"  доля {z}: {100.0 * counts[z] / len(canon):.1f}%")

    def sym(a, b):
        if counts.get(a) and counts.get(b):
            d = abs(counts[a] - counts[b]) / min(counts[a], counts[b]) * 100
            print(f"  симметрия {a}/{b}: {d:.1f}%")
    sym("cheek_r", "cheek_l")
    sym("jaw_r", "jaw_l")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 8))
        ax.scatter(canon[:, 0], canon[:, 1], s=1, c="lightgray")
        for name, idx in zones.items():
            ax.scatter(canon[idx, 0], canon[idx, 1], s=3, label=f"{name} ({len(idx)})")
        ax.set_aspect("equal")
        ax.legend(markerscale=4, fontsize=6)
        Path(args.out_png).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.out_png, dpi=130)
        print("WROTE", args.out_png, "- ПРОВЕРЬ ЗОНЫ ГЛАЗАМИ")
    except ImportError:
        print("matplotlib не найден: картинку проверки не построили")


if __name__ == "__main__":
    main()
