#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np


# Простая зональная разметка по координатам в нормированном пространстве (ориентирная)
# Основано на общих зонах лица; требует валидации
def get_zones(v):
    # v: (N,3)
    x = v[:,0]; y = v[:,1]; z = v[:,2]
    zones = {}
    # лоб
    zones['forehead'] = np.where((y > 0.15))[0]
    # брови
    zones['eyebrows'] = np.where((y > -0.05) & (y < 0.15) & (np.abs(x)>0.15) & (np.abs(x)<0.4))[0]
    # глаза
    zones['eyes'] = np.where((y > -0.25) & (y < 0.0) & (np.abs(x)>0.1) & (np.abs(x)<0.35))[0]
    # нос
    zones['nose'] = np.where((np.abs(x)<0.15) & (y > -0.45) & (y < 0.05))[0]
    # скулы
    zones['cheeks'] = np.where((np.abs(x)>0.2) & (np.abs(x)<0.5) & (y > -0.5) & (y < 0.1))[0]
    # губы
    zones['lips'] = np.where((np.abs(x)<0.2) & (y > -0.65) & (y < -0.25))[0]
    # подбородок
    zones['chin'] = np.where((np.abs(x)<0.25) & (y < -0.55))[0]
    # челюсть
    zones['jaw'] = np.where((np.abs(x)>0.25) & (np.abs(x)<0.5) & (y < -0.3) & (y > -0.7))[0]
    return zones


def main():
    p = argparse.ArgumentParser(description="Зональная калибровка внутри бина")
    p.add_argument("--meshes", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    mesh_dir = Path(args.meshes)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    meshes = []
    for npz in sorted(mesh_dir.glob("*.npz")):
        try:
            d = np.load(npz, allow_pickle=True)
            meshes.append({
                "path": str(npz),
                "v_aligned": d["v_aligned"].astype(np.float32),
                "pose_bin": str(d["pose_bin"]),
                "yaw": float(d["yaw"]),
            })
        except Exception:
            continue

    by_bin = {}
    for m in meshes:
        by_bin.setdefault(m["pose_bin"], []).append(m)

    report = {"n": len(meshes), "by_bin_zones": {}}
    for bname, items in by_bin.items():
        if len(items) < 2:
            continue
        zones = get_zones(items[0]["v_aligned"])
        zrep = {}
        for zname, idx in zones.items():
            if len(idx) < 10: 
                continue
            vals = []
            for i in range(len(items)):
                for j in range(i+1, len(items)):
                    v1 = items[i]["v_aligned"][idx]
                    v2 = items[j]["v_aligned"][idx]
                    diff = v1-v2
                    d = np.sqrt(np.sum(diff*diff, axis=1))
                    vals.append(float(np.mean(d)))
            if not vals: continue
            vals = np.array(vals)
            med = float(np.median(vals))
            mad = float(np.median(np.abs(vals-med)))
            zrep[zname] = {"n_verts": int(len(idx)), "mean": float(np.mean(vals)), "median": med, "mad": mad, "p95": float(np.percentile(vals,95))}
        report["by_bin_zones"][bname] = zrep

    (out / "zonal_calibration.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["by_bin_zones"].get("frontal",{}), indent=2))
    print("WROTE", out / "zonal_calibration.json")


if __name__ == "__main__":
    main()
