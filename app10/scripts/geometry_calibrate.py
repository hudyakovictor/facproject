#!/usr/bin/env python3
"""Калибровка геометрических признаков зон ТОЛЬКО внутри бина.

Признаки по зонам (вес по площади): площадь, доля площади, средняя и гауссова кривизна,
угол между нормалями (для пар кадров). Работает на уже извлечённых NPZ (нужен только v_aligned и pose_bin).
Статистика по кадрам: медиана и MAD. Статистика по парам |a-b|: p80 и p97.5 (как k_same/k_differ в файле метрик);
пары зависимы, поэтому это описание повторяемости, а не независимая выборка.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.face_model_io import load_face_model  # noqa: E402
from src.mesh_geometry import normal_angle_deg, vertex_areas, vertex_normals, weighted_mean, zone_features  # noqa: E402
from src.zones import load_zones  # noqa: E402

MIN_FRAMES = 3
FEATURES = ["area", "area_frac", "mean_curvature", "gauss_curvature"]


def robust(values):
    x = np.asarray(values, dtype=np.float64)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return None
    med = float(np.median(x))
    return {"n": int(len(x)), "median": med, "mad": float(np.median(np.abs(x - med))),
            "min": float(x.min()), "max": float(x.max())}


def pair_stats(values):
    x = np.asarray(values, dtype=np.float64)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return None
    return {"n_pairs": int(len(x)), "median": float(np.median(x)),
            "k_same_p80": float(np.percentile(x, 80)), "k_differ_p97_5": float(np.percentile(x, 97.5))}


def main():
    p = argparse.ArgumentParser(description="Калибровка геометрии зон внутри бина")
    p.add_argument("--meshes", required=True)
    p.add_argument("--face-model", required=True)
    p.add_argument("--zones", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    tri = load_face_model(args.face_model)["tri"]
    frames, skipped = [], []
    for npz in sorted(Path(args.meshes).glob("*.npz")):
        try:
            d = np.load(npz, allow_pickle=True)
            frames.append({"name": npz.stem, "v": d["v_aligned"].astype(np.float64), "bin": str(d["pose_bin"])})
        except Exception as e:  # noqa: BLE001
            skipped.append({"path": str(npz), "reason": str(e)})
    if not frames:
        sys.exit("NO MESHES")
    n_vert = frames[0]["v"].shape[0]
    if tri.max() >= n_vert:
        sys.exit(f"tri ссылается на вершину {tri.max()}, а в сетке {n_vert} вершин")
    zones, zmeta = load_zones(args.zones, n_vertices=n_vert)

    by_bin = {}
    for f in frames:
        by_bin.setdefault(f["bin"], []).append(f)

    report = {
        "n": len(frames), "skipped": skipped, "zones_file": str(args.zones),
        "zones_validated": bool(zmeta.get("validated", False)),
        "note": "пары кадров зависимы; цифры описывают повторяемость, не независимую выборку",
        "by_bin": {},
    }
    for bname, items in by_bin.items():
        if len(items) < MIN_FRAMES:
            report["by_bin"][bname] = {"status": "insufficient_frames", "n_frames": len(items)}
            continue
        feats = [zone_features(f["v"], tri, zones) for f in items]
        normals = [vertex_normals(f["v"], tri) for f in items]
        areas = [vertex_areas(f["v"], tri) for f in items]
        brep = {}
        for z in zones:
            zr = {"n_verts": int(len(zones[z])), "n_frames": len(items), "features": {}}
            for name in FEATURES:
                vals = [ft[z][name] for ft in feats]
                zr["features"][name] = {
                    "per_frame": robust(vals),
                    "pairs_abs_diff": pair_stats([abs(vals[i] - vals[j])
                                                  for i in range(len(vals)) for j in range(i + 1, len(vals))]),
                }
            ang = []
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    a = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", normals[i], normals[j]), -1, 1)))
                    ang.append(weighted_mean(a, zones[z], 0.5 * (areas[i] + areas[j])))
            zr["normal_angle_deg_pairs"] = pair_stats(ang)
            brep[z] = zr
        report["by_bin"][bname] = brep

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "geometry_calibration.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("WROTE", out / "geometry_calibration.json")


if __name__ == "__main__":
    main()
