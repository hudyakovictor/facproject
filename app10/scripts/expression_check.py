#!/usr/bin/env python3
"""Проверка мимики по зонам: сдвиг формы и сдвиг alpha_id относительно нейтральных кадров.

Нейтральные кадры: бин --neutral-bin, имя файла не совпадает ни с одним --expr.
Базис шума: расстояние каждого нейтрального кадра до медианы остальных (leave-one-out).
"""
import argparse
import json
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.zones import load_zones  # noqa: E402


def norm(s):
    return unicodedata.normalize("NFC", s).lower()


def load_one(npz):
    d = np.load(npz, allow_pickle=True)
    a = d["alpha_id"] if "alpha_id" in d.files else None
    if a is not None and a.dtype == object:
        a = None
    return {
        "name": Path(npz).stem,
        "v": d["v_aligned"].astype(np.float64),
        "bin": str(d["pose_bin"]),
        "yaw": float(d["yaw"]),
        "alpha": None if a is None else np.asarray(a, dtype=np.float64).ravel(),
    }


def zone_dist(a, b, idx):
    diff = a[idx] - b[idx]
    return float(np.mean(np.sqrt(np.sum(diff * diff, axis=1))))


def main():
    p = argparse.ArgumentParser(description="Проверка мимики по зонам")
    p.add_argument("--meshes", required=True)
    p.add_argument("--zones", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--neutral-bin", default="frontal")
    p.add_argument("--expr", action="append", required=True,
                   help="метка=подстрока_в_имени, например улыбка=улыбка (можно несколько раз)")
    args = p.parse_args()

    labels = {}
    for item in args.expr:
        label, _, sub = item.partition("=")
        labels[label] = norm(sub or label)

    frames = []
    for npz in sorted(Path(args.meshes).glob("*.npz")):
        try:
            frames.append(load_one(npz))
        except Exception as e:  # noqa: BLE001
            print(f"SKIP {npz.name}: {e}")
    if not frames:
        sys.exit("NO MESHES")
    zones, _ = load_zones(args.zones, n_vertices=frames[0]["v"].shape[0])

    def label_of(f):
        for lab, sub in labels.items():
            if sub in norm(f["name"]):
                return lab
        return None

    neutral = [f for f in frames if f["bin"] == args.neutral_bin and label_of(f) is None]
    if len(neutral) < 3:
        sys.exit(f"нейтральных кадров {len(neutral)} < 3")
    neut_med = np.median(np.stack([f["v"] for f in neutral]), axis=0)

    base = {z: [] for z in zones}
    base_alpha = []
    for i, f in enumerate(neutral):
        rest = np.median(np.stack([g["v"] for j, g in enumerate(neutral) if j != i]), axis=0)
        for z, idx in zones.items():
            base[z].append(zone_dist(f["v"], rest, idx))
        if f["alpha"] is not None and all(g["alpha"] is not None for g in neutral):
            ra = np.median(np.stack([g["alpha"] for j, g in enumerate(neutral) if j != i]), axis=0)
            base_alpha.append(float(np.linalg.norm(f["alpha"] - ra)))
    base_med = {z: float(np.median(v)) for z, v in base.items()}
    alpha_all = all(g["alpha"] is not None for g in neutral)
    neut_alpha = np.median(np.stack([g["alpha"] for g in neutral]), axis=0) if alpha_all else None

    report = {
        "n_neutral": len(neutral),
        "neutral_bin": args.neutral_bin,
        "baseline_zone_median": base_med,
        "baseline_alpha_id_median": float(np.median(base_alpha)) if base_alpha else None,
        "expressions": {},
    }
    for lab in labels:
        rows = []
        for f in frames:
            if label_of(f) != lab:
                continue
            zrow = {}
            for z, idx in zones.items():
                d = zone_dist(f["v"], neut_med, idx)
                b = base_med[z]
                zrow[z] = {"dist": d, "ratio_to_baseline": (d / b) if b > 0 else None}
            row = {"frame": f["name"], "pose_bin": f["bin"], "yaw": f["yaw"], "zones": zrow}
            if f["alpha"] is not None and neut_alpha is not None:
                da = float(np.linalg.norm(f["alpha"] - neut_alpha))
                bm = report["baseline_alpha_id_median"]
                row["alpha_id_shift"] = {"l2": da, "ratio_to_baseline": (da / bm) if bm else None}
            rows.append(row)
        report["expressions"][lab] = rows

    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "expression_check_zonal.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("WROTE", Path(args.out) / "expression_check_zonal.json")


if __name__ == "__main__":
    main()
