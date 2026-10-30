#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np

from morphing.backend.aligner import normalize_ldm106, align_identity_mesh


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
    p = argparse.ArgumentParser(description="Диагностика нормировки/канонического поворота на одном человеке")
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
        # берём первый как эталон внутри бина
        ref = items[0]["v_aligned"]
        vals = []
        for m in items[1:]:
            mmean, mmed = pairwise_dists(ref, m["v_aligned"])
            vals.append(mmean)
        report["bins"][bname] = {"ref": items[0]["path"], "count_vs_ref": len(vals), "mean_vs_ref": float(np.mean(vals)), "median_vs_ref": float(np.median(vals))}

    # сравнение между бинами vs фронтал/близкий
    # ищем фронтальный бином
    front_keys = [k for k in by_bin if "front" in k.lower()]
    if front_keys:
        ref_bin = front_keys[0]
        ref_items = by_bin[ref_bin]
        if ref_items:
            ref = ref_items[0]["v_aligned"]
            for bname, items in by_bin.items():
                if bname == ref_bin: continue
                vals = []
                for m in items:
                    mmean, mmed = pairwise_dists(ref, m["v_aligned"])
                    vals.append(mmean)
                if vals:
                    report["bins"][f"{ref_bin}_vs_{bname}"] = {"ref": ref_items[0]["path"], "count": len(vals), "mean_vs_ref": float(np.mean(vals)), "median_vs_ref": float(np.median(vals))}

    report["notes"].append("Единицы - доли RMS106 (normalize_ldm106). identity_only без двойного поворота.")
    (out / "diagnose_norm_rotation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print("WROTE", out / "diagnose_norm_rotation.json")


if __name__ == "__main__":
    main()
