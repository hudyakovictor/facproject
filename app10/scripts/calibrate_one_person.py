#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np


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
    return float(np.mean(d)), float(np.median(d)), float(np.max(d))


def main():
    p = argparse.ArgumentParser(description="Калибровка шума на одном человеке по бин-позам (только внутри бина)")
    p.add_argument("--meshes", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    mesh_dir = Path(args.meshes)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    meshes = load_meshes(mesh_dir)
    if not meshes:
        print("NO MESHES"); return
    # группировка по поз-бину
    by_bin = {}
    for m in meshes:
        by_bin.setdefault(m["pose_bin"], []).append(m)

    report = {"n": len(meshes), "by_bin": {}, "pairs_in_bin": []}
    # внутри бина ТОЛЬКО
    for bname, items in by_bin.items():
        if len(items) < 2:
            report["by_bin"][bname] = {"count": len(items), "mean_within_bin": None, "median_within_bin": None, "mad_within_bin": None, "p95_within_bin": None, "std_within_bin": None}
            continue
        vals_m = []
        for i in range(len(items)):
            for j in range(i+1, len(items)):
                mmean, mmed, mmax = pairwise_dists(items[i]["v_aligned"], items[j]["v_aligned"])
                vals_m.append(mmean)
                report["pairs_in_bin"].append({"bin": bname, "a": items[i]["path"], "b": items[j]["path"], "mean_euclid": mmean, "median_euclid": mmed})
        vals_m = np.array(vals_m)
        med = float(np.median(vals_m))
        mad = float(np.median(np.abs(vals_m - med)))
        p95 = float(np.percentile(vals_m, 95))
        report["by_bin"][bname] = {"count": len(items), "mean_within_bin": float(np.mean(vals_m)), "median_within_bin": med, "mad_within_bin": mad, "p95_within_bin": p95, "std_within_bin": float(np.std(vals_m))}
    # НЕ считаем межгрупповые пары

    (out / "calibration_one_person.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["by_bin"], indent=2))
    print("WROTE", out / "calibration_one_person.json")
    print("NOTE: межгрупповые пары не считаются - сравнения только внутри бина")


if __name__ == "__main__":
    main()
