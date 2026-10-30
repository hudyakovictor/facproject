#!/usr/bin/env python3
"""Строит фиксированные зоны на канонической сетке (медиана кадров одного бина)."""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.zones import DEFAULT_RULES, build_zones, canonical_mesh, check_disjoint, save_zones  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Фиксированные зоны лица по канонической сетке")
    p.add_argument("--meshes", required=True)
    p.add_argument("--bin", default="frontal")
    p.add_argument("--min-frames", type=int, default=5)
    p.add_argument("--out-json", default="app10/configs/zones_canonical.json")
    p.add_argument("--out-png", default="app10/reports/zones_check.png")
    args = p.parse_args()

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
    zones = build_zones(canon)
    assert check_disjoint(zones)
    save_zones(args.out_json, zones, len(canon), DEFAULT_RULES,
               source={"bin": args.bin, "n_frames": len(frames)})
    print("WROTE", args.out_json, {k: len(v) for k, v in zones.items()})

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 8))
        ax.scatter(canon[:, 0], canon[:, 1], s=1, c="lightgray")
        for name, idx in zones.items():
            ax.scatter(canon[idx, 0], canon[idx, 1], s=3, label=f"{name} ({len(idx)})")
        ax.set_aspect("equal")
        ax.legend(markerscale=4, fontsize=7)
        Path(args.out_png).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.out_png, dpi=130)
        print("WROTE", args.out_png, "- ПРОВЕРЬ ЗОНЫ ГЛАЗАМИ")
    except ImportError:
        print("matplotlib не найден: картинку проверки не построили")


if __name__ == "__main__":
    main()
