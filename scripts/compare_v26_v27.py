"""Приёмочный compare v26(R_corr) → v27(target-only) на 53 фото.

Ожидание рецензента: флаги corrected сходятся к raw (~6.5k→), пересечение
48%→85-90%, доля brow/all-zones падает; set-diff R2 показывает выбывшую позу.
Плюс within-bin residual как вес пары (тонкость target-only).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path("/Users/victorkhudyakov/work")
V26 = WORK / "stage1_v26_det_output"
V27 = WORK / "stage1_v27_det_output"
NOISE = pd.read_csv(WORK / "alpha_calib_v25" / "table5_noise_floor.csv")
OUT = WORK / "analyst_v25"


def ZoneOf(p):
    x, y = p[0], p[1]
    if y > 0.55:
        return "browL" if x < 0 else "browR"
    if 0.15 < y <= 0.55:
        return "eyeL" if x < -0.25 else ("eyeR" if x > 0.25 else "nose_up")
    if -0.35 < y <= 0.15:
        return "nose" if abs(x) < 0.3 else ("cheekL" if x < 0 else "cheekR")
    if -0.75 < y <= -0.35:
        return "mouth" if abs(x) < 0.45 else ("jawL" if x < 0 else "jawR")
    return "jawL" if x < 0 else "jawR"


def read3(p, n):
    a = np.full((n, 3), np.nan)
    with open(p, newline="") as f:
        for row in csv.DictReader(f):
            a[int(float(row["landmark_id"]))] = [float(row["x"]), float(row["y"]), float(row["z"])]
    return a.astype(np.float64)


def procrustes(a, b):
    ca, cb = a.mean(0), b.mean(0)
    x, y = b - cb, a - ca
    U, _, Vt = np.linalg.svd(x.T @ y)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = U @ Vt
    d = x @ R - y
    return float(np.sqrt(np.mean(np.sum(d * d, 1)))), d


def p95(dyaw):
    a = abs(float(dyaw))
    gap = "0-3" if a <= 3 else ("3-8" if a <= 8 else ("8-15" if a <= 15 else ">15"))
    return float(NOISE[(NOISE.yaw_gap == gap) & (NOISE.same_bin == "yes")]["p95"].iloc[0])


def main():
    dirs = sorted([d for d in V27.iterdir() if (d / "info.json").exists()])
    print(f"v27 photo dirs: {len(dirs)}", flush=True)
    ph, LEG, TGT, RAW = [], [], [], []
    for d in dirs:
        info = json.load(open(d / "info.json"))
        ch = info["chronology"]
        ph.append(dict(pid=d.name, yaw=ch["actual_pose"][1], pitch=ch["actual_pose"][0],
                       roll=ch["actual_pose"][2], yaw_canon=float(ch["canonical_yaw"]),
                       bin=ch["pose_bin"]))
        LEG.append(read3(d / "ldm134_chronology.csv", 134))
        TGT.append(read3(d / "ldm134_chronology_targetonly.csv", 134))
        RAW.append(read3(d / "ldm134_raw.csv", 134))
    ph = pd.DataFrame(ph)
    mu = np.nanmean(np.stack(TGT), axis=0)
    mu = (mu - mu.mean(0)) / np.sqrt(np.mean(np.sum((mu - mu.mean(0)) ** 2, 1)))
    zones = np.array([ZoneOf(p) for p in mu])
    znames = sorted(set(zones))

    rows = []
    for i in range(len(ph)):
        for j in range(i + 1, len(ph)):
            a, b = ph.iloc[i], ph.iloc[j]
            if a["bin"] != b["bin"]:
                continue
            dy = abs(a["yaw"] - b["yaw"])
            if dy > 15:
                continue
            dl, rl = procrustes(LEG[i], LEG[j])
            dt, rt = procrustes(TGT[i], TGT[j])
            dw, _ = procrustes(RAW[i], RAW[j])
            p = p95(dy)
            # within-bin residual: |yaw - canon| пары (вес target-only слепоты)
            wbr = abs(a["yaw"] - a["yaw_canon"]) + abs(b["yaw"] - b["yaw_canon"])
            zrow = {"dy": round(dy, 2), "wbr": round(wbr, 2), "p95": round(p, 5),
                    "zl": round(dl / p, 2), "zt": round(dt / p, 2), "zw": round(dw / p, 2)}
            # зональный worst для legacy и targetonly
            for tag, res in (("l", rl), ("t", rt)):
                per = {}
                for z in znames:
                    sel = np.flatnonzero(zones == z)
                    per[z] = float(np.sqrt(np.mean(np.sum(res[sel] ** 2, 1))))
                zrow[f"worst_{tag}"] = max(per, key=per.get)
                zrow[f"nzhi_{tag}"] = sum(1 for v in per.values() if v > p)
            rows.append(zrow)
    c = pd.DataFrame(rows)
    print(f"pairs: {len(c)}", flush=True)
    for tag, col in (("legacy", "zl"), ("targetonly", "zt"), ("raw", "zw")):
        hi = c[c[col] > 4]
        print(f"{tag}: Z>4 n={len(hi)}", flush=True)
    cl = c[c.zl > 4]
    ct = c[c.zt > 4]
    cw = c[c.zw > 4]
    print("overlap legacy∩raw: %d (%.0f%% legacy)" % (len(c[(c.zl > 4) & (c.zw > 4)]), 100 * len(c[(c.zl > 4) & (c.zw > 4)]) / max(len(cl), 1)), flush=True)
    print("overlap target∩raw: %d (%.0f%% target)" % (len(c[(c.zt > 4) & (c.zw > 4)]), 100 * len(c[(c.zt > 4) & (c.zw > 4)]) / max(len(ct), 1)), flush=True)
    for tag in ("l", "t"):
        hi = c[c[f"z{tag}"] > 4] if f"z{tag}" in c else (cl if tag == "l" else ct)
        col = f"worst_{tag}"
        brow = hi[col].isin(["browL", "browR"]).mean() if len(hi) else float("nan")
        allz = (hi[f"nzhi_{tag}"] == len(znames)).mean() if len(hi) else float("nan")
        print(f"{tag}: brow share={brow:.2f} all-zones share={allz:.2f}", flush=True)
    # set-diff R2-подобных: пары Z>4 legacy, упавшие в targetonly, и наоборот
    dropped = c[(c.zl > 4) & (c.zt <= 3)]
    kept = c[(c.zl > 4) & (c.zt > 4)]
    print(f"legacy-hi: dropped in targetonly={len(dropped)} kept={len(kept)}; "
          f"dropped median dy={dropped.dy.median() if len(dropped) else float('nan'):.1f} "
          f"kept median dy={kept.dy.median() if len(kept) else float('nan'):.1f}", flush=True)
    c.to_csv(OUT / "v26_v27_compare.csv", index=False)
    print("DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
