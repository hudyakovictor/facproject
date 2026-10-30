#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np

from src.pose_bins import classify_pose


def load_meshes(mesh_dir: Path):
    meshes = []
    for npz in sorted(mesh_dir.glob("*.npz")):
        d = np.load(npz, allow_pickle=True)
        meshes.append({
            "path": str(npz),
            "v_aligned": d["v_aligned"].astype(np.float32),
            "ldm106_aligned": d["ldm106_aligned"].astype(np.float32),
            "pose_bin": str(d["pose_bin"]),
            "yaw": float(d["yaw"]),
        })
    return meshes


def pairwise_dists(a: np.ndarray, b: np.ndarray):
    diff = a - b
    d = np.sqrt(np.sum(diff*diff, axis=1))
    return float(np.mean(d)), float(np.median(d))


def main():
    p = argparse.ArgumentParser(description="Диагностика внутри бина: сравнение с медианным представителем")
    p.add_argument("--meshes", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    mesh_dir = Path(args.meshes)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    meshes = load_meshes(mesh_dir)
    if not meshes:
        print("NO MESHES"); return

    report = {"n": len(meshes), "bins": {}, "notes": []}
    by_bin = {}
    for m in meshes:
        by_bin.setdefault(m["pose_bin"], []).append(m)

    for bname, items in by_bin.items():
        if len(items) < 2:
            continue
        # медианный представитель по среднему расстоянию к остальным
        best_idx = 0
        best_score = 1e18
        for i in range(len(items)):
            score = 0.0
            for j in range(len(items)):
                if i == j: continue
                mmean, _ = pairwise_dists(items[i]["v_aligned"], items[j]["v_aligned"])
                score += mmean
            if score < best_score:
                best_score = score
                best_idx = i
        ref = items[best_idx]["v_aligned"]
        vals = []
        for k,m in enumerate(items):
            if k == best_idx: continue
            mmean, mmed = pairwise_dists(ref, m["v_aligned"])
            vals.append(mmean)
        report["bins"][bname] = {"ref": items[best_idx]["path"], "count_vs_ref": len(vals), "mean_vs_ref": float(np.mean(vals)), "median_vs_ref": float(np.median(vals))}

    report["notes"].append("Только внутри бина. Эталон - медианный представитель (не первый по алфавиту). Межгрупповые сравнения исключены.")
    (out / "diagnose_norm_rotation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print("WROTE", out / "diagnose_norm_rotation.json")


if __name__ == "__main__":
    main()
