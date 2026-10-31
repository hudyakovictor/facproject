#!/usr/bin/env python3
"""Зональная калибровка ТОЛЬКО внутри бина по фиксированным зонам (индексы вершин)."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.zones import load_zones, zones_sha256  # noqa: E402

MIN_FRAMES = 3


def load_meshes(mesh_dir):
    meshes, skipped = [], []
    for npz in sorted(Path(mesh_dir).glob("*.npz")):
        try:
            d = np.load(npz, allow_pickle=True)
            meshes.append({
                "path": str(npz),
                "v_aligned": d["v_aligned"].astype(np.float32),
                "pose_bin": str(d["pose_bin"]),
                "yaw": float(d["yaw"]),
            })
        except Exception as e:  # noqa: BLE001
            skipped.append({"path": str(npz), "reason": str(e)})
    return meshes, skipped


def zone_pair_values(items, idx):
    vals = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            diff = items[i]["v_aligned"][idx] - items[j]["v_aligned"][idx]
            vals.append(float(np.mean(np.sqrt(np.sum(diff * diff, axis=1)))))
    return np.array(vals)


def main():
    p = argparse.ArgumentParser(description="Зональная калибровка внутри бина")
    p.add_argument("--meshes", required=True)
    p.add_argument("--zones", required=True, help="JSON из build_zones.py или build_zones_annotation.py")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    meshes, skipped = load_meshes(args.meshes)
    if not meshes:
        sys.exit("NO MESHES")
    zones, zmeta = load_zones(args.zones, n_vertices=meshes[0]["v_aligned"].shape[0])
    cur_sha = zones_sha256(zones)
    validated = bool(zmeta.get("validated", False)) and zmeta.get("zones_sha256") == cur_sha

    by_bin = {}
    for m in meshes:
        by_bin.setdefault(m["pose_bin"], []).append(m)

    report = {
        "n": len(meshes),
        "skipped": skipped,
        "zones_file": str(args.zones),
        "zones_sha256": cur_sha,
        "zones_validated": validated,
        "note": "пары кадров зависимы: цифры описывают повторяемость, не независимую выборку",
        "by_bin_zones": {},
    }
    for bname, items in by_bin.items():
        if len(items) < MIN_FRAMES:
            report["by_bin_zones"][bname] = {"status": "insufficient_frames", "n_frames": len(items)}
            continue
        zrep = {}
        for zname, idx in zones.items():
            vals = zone_pair_values(items, idx)
            med = float(np.median(vals))
            zrep[zname] = {
                "n_verts": int(len(idx)),
                "n_frames": len(items),
                "n_pairs": int(len(vals)),
                "mean": float(np.mean(vals)),
                "median": med,
                "mad": float(np.median(np.abs(vals - med))),
                "p95": float(np.percentile(vals, 95)),
            }
        report["by_bin_zones"][bname] = zrep

    (out / "zonal_calibration.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("WROTE", out / "zonal_calibration.json")


if __name__ == "__main__":
    main()
