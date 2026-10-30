#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np

from morphing.backend.aligner import normalize_ldm106


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
    # средняя евклидова разница между сетками в RMS106 единицах
    diff = a - b
    d = np.sqrt(np.sum(diff*diff, axis=1))
    return float(np.mean(d)), float(np.median(d)), float(np.max(d))


def main():
    p = argparse.ArgumentParser(description="Калибровка шума на одном человеке по бин-позам")
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

    report = {"n": len(meshes), "by_bin": {}, "pairs": []}
    # внутри бина
    for bname, items in by_bin.items():
        if len(items) < 2:
            report["by_bin"][bname] = {"count": len(items), "mean": None, "median": None}
            continue
        vals_m = []
        for i in range(len(items)):
            for j in range(i+1, len(items)):
                mmean, mmed, mmax = pairwise_dists(items[i]["v_aligned"], items[j]["v_aligned"])
                vals_m.append(mmean)
                report["pairs"].append({"bin": bname, "a": items[i]["path"], "b": items[j]["path"], "mean_euclid": mmean, "median_euclid": mmed})
        report["by_bin"][bname] = {"count": len(items), "mean_within_bin": float(np.mean(vals_m)), "median_within_bin": float(np.median(vals_m)), "std_within_bin": float(np.std(vals_m))}
    # между бинами (доп смещение от ракурса)
    bins = list(by_bin.keys())
    for bi in range(len(bins)):
        for bj in range(bi+1, len(bins)):
            b1, b2 = bins[bi], bins[bj]
            vals_m = []
            for m1 in by_bin[b1]:
                for m2 in by_bin[b2]:
                    mmean, mmed, mmax = pairwise_dists(m1["v_aligned"], m2["v_aligned"])
                    vals_m.append(mmean)
                    report["pairs"].append({"bin": f"{b1}__{b2}", "a": m1["path"], "b": m2["path"], "mean_euclid": mmean, "median_euclid": mmed})
            if vals_m:
                report["by_bin"][f"between_{b1}_{b2}"] = {"count": f"{len(by_bin[b1])}x{len(by_bin[b2])}", "mean_between": float(np.mean(vals_m)), "median_between": float(np.median(vals_m))}

    (out / "calibration_one_person.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["by_bin"], indent=2))
    print("WROTE", out / "calibration_one_person.json")


if __name__ == "__main__":
    main()
