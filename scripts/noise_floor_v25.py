"""Эмпирический noise floor: same-person попарные различия identity-геометрии.

Страты по угловому расхождению (протокол: верхняя граница ошибки одного
человека при заданном Δpose). Метрика — Procrustes-RMSE 134 identity-точек
(без масштаба: только форма; масштаб отдельно через |ΔS_id|/mean).
Выход: alpha_calib_v25/table5_noise_floor.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path("/Users/victorkhudyakov/work")
CALIB = Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets")
OUT = WORK / "alpha_calib_v25"


def load_bfm():
    m = np.load(WORK / "assets" / "face_model.npy", allow_pickle=True).item()
    return (np.asarray(m["u"], np.float64).reshape(-1),
            np.asarray(m["id"], np.float64), np.asarray(m["exp"], np.float64))


def procrustes_rmse(a, b):
    """Kabsch b->a без масштаба, RMSE по всем точкам."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    ca, cb = a.mean(0), b.mean(0)
    x, y = b - cb, a - ca
    U, _, Vt = np.linalg.svd(x.T @ y)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = U @ Vt
    return float(np.sqrt(np.mean(np.sum((x @ R - y) ** 2, 1))))


def yaw_bin(dy):
    a = abs(float(dy))
    if a <= 3:
        return "0-3"
    if a <= 8:
        return "3-8"
    if a <= 15:
        return "8-15"
    return ">15"


def main():
    u, BID, BEXP = load_bfm()
    rows = list(csv.DictReader(open(CALIB / "all_calibration_index.csv")))
    # identity-landmarks 134 + S_id + углы, по персонам
    per = {}
    for r in rows:
        z = np.load(CALIB / r["npz_file"], allow_pickle=False)
        aid = np.asarray(z["alpha_id"], np.float64).reshape(-1)
        aexp = np.asarray(z["alpha_exp"], np.float64).reshape(-1)
        i134 = np.asarray(z["ldm134_vertex_indices"], np.int64).reshape(-1)
        V = (u + BID @ aid).reshape(35709, 3)[i134]
        c = V.mean(0)
        S = float(np.sqrt(np.mean(np.sum((V - c) ** 2, 1))))
        per.setdefault(r["dataset_id"], []).append(
            (V, S, float(r["yaw"]), float(r["pitch"]), float(r["roll"]), r["pose_bin"]))
    out = []
    rng = np.random.default_rng(0)
    for pid, items in per.items():
        n = len(items)
        # все пары при n<=200, иначе стратифицированная подвыборка 20000
        pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
        if len(pairs) > 20000:
            idx = rng.choice(len(pairs), 20000, replace=False)
            pairs = [pairs[k] for k in idx]
        for i, j in pairs:
            Vi, Si, yi, pi, ri, bi = items[i]
            Vj, Sj, yj, pj, rj, bj = items[j]
            out.append(dict(
                yaw_gap=yaw_bin(yi - yj),
                same_bin="yes" if bi == bj else "no",
                rmse=procrustes_rmse(Vi, Vj),
                scale_rel=abs(Si - Sj) / max((Si + Sj) / 2, 1e-12),
            ))
    df = pd.DataFrame(out)
    g = df.groupby(["yaw_gap", "same_bin"])
    tab = g["rmse"].agg(n="size", median="median",
                        p95=lambda s: float(np.quantile(s, 0.95)),
                        p99=lambda s: float(np.quantile(s, 0.99))).reset_index()
    sc = g["scale_rel"].agg(median="median",
                            p95=lambda s: float(np.quantile(s, 0.95)),
                            p99=lambda s: float(np.quantile(s, 0.99))).reset_index()
    tab = tab.merge(sc, on=["yaw_gap", "same_bin"], suffixes=("", "_scale"))
    tab = tab.sort_values(["yaw_gap", "same_bin"])
    tab.to_csv(OUT / "table5_noise_floor.csv", index=False)
    print(tab.to_string(), flush=True)
    print("pairs:", len(df), flush=True)


if __name__ == "__main__":
    sys.exit(main())
