"""Аналитик v25, часть 1: загрузка 1909, event-датасет, matching, метрики, Z_noise.

Читает ТОЛЬКО старый storage (read-only). Пишет в analyst_v25/.
Каналы: PRIMARY target-only (T134_targetonly.npy; canonical, без инверсии позы),
raw object, original 2D. Legacy R_corr (chrono@R.T) — только sensitivity
(флаг --channel legacy). Пути через env/argv (портативность для форка).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path(os.environ.get("FAC_WORK", "/Users/victorkhudyakov/work"))
OLD = Path(os.environ.get("FAC_STAGE1", "/Volumes/SDCARD/storage/stage1"))

EYE_L, EYE_R = 74, 77


def read_csv3(p, n):
    a = np.full((n, 3), np.nan)
    with open(p, newline="") as f:
        for row in csv.DictReader(f):
            a[int(float(row["landmark_id"]))] = [float(row["x"]), float(row["y"]), float(row["z"])]
    return a.astype(np.float32)


def read_csv2(p, n):
    a = np.full((n, 2), np.nan)
    with open(p, newline="") as f:
        for row in csv.DictReader(f):
            x = row.get("x_px", row.get("x"))
            y = row.get("y_px", row.get("y"))
            a[int(float(row["landmark_id"]))] = [float(x), float(y)]
    return a.astype(np.float32)


def procrustes(a, b):
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    m = np.isfinite(a).all(1) & np.isfinite(b).all(1)
    a, b = a[m], b[m]
    ca, cb = a.mean(0), b.mean(0)
    x, y = b - cb, a - ca
    U, _, Vt = np.linalg.svd(x.T @ y)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = U @ Vt
    d = np.sqrt(np.mean(np.sum((x @ R - y) ** 2, 1)))
    return d, int(m.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", choices=["targetonly", "legacy"], default="targetonly",
                    help="targetonly=canonical (default); legacy=R_corr sensitivity")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    OUT = args.out or (WORK / "analyst_v25")
    OUT.mkdir(exist_ok=True)
    NOISE = pd.read_csv(WORK / "alpha_calib_v25" / "table5_noise_floor.csv")

    def noise_p95(dyaw, same_bin):
        a = abs(float(dyaw))
        gap = "0-3" if a <= 3 else ("3-8" if a <= 8 else ("8-15" if a <= 15 else ">15"))
        sb = "yes" if same_bin else "no"
        hit = NOISE[(NOISE.yaw_gap == gap) & (NOISE.same_bin == sb)]
        return float(hit["p95"].iloc[0]) if len(hit) else 0.05

    tl = list(csv.DictReader(open(OLD / "main_timeline.csv")))
    recs, F106, F134, Fraw106, Fraw134, F2d = [], [], [], [], [], []
    use_legacy = args.channel == "legacy"
    if use_legacy:
        print("WARNING: legacy R_corr channel (deprecated sensitivity)", flush=True)
    T106 = T134 = None
    if not use_legacy:
        T106 = np.load(OUT / "T106_targetonly.npy")
        T134 = np.load(OUT / "T134_targetonly.npy")
        tpids = json.load(open(OUT / "T_targetonly_pids.json"))
    for k, r in enumerate(tl):
        d = OLD / r["photo_id"]
        try:
            info = json.load(open(d / "info.json"))
            raw106 = read_csv3(d / "ldm106_raw.csv", 106)
            raw134 = read_csv3(d / "ldm134_raw.csv", 134)
            o2d = read_csv2(d / "ldm106_original.csv", 106)
            if use_legacy:
                ch106 = read_csv3(d / "ldm106_chronology.csv", 106)
                ch134 = read_csv3(d / "ldm134_chronology.csv", 134)
        except Exception:
            continue
        ch = info.get("chronology", {})
        img = info.get("image", {})
        W, H = float(img.get("width") or 1), float(img.get("height") or 1)
        o2dn = o2d / np.array([[W, H]], np.float32)
        if use_legacy:
            R = np.asarray(ch["applied_rotation"], np.float64).reshape(3, 3)
            RT = R.T
            F106.append(ch106.astype(np.float64) @ RT)
            F134.append(ch134.astype(np.float64) @ RT)
        else:
            assert tpids[k] == r["photo_id"], "targetonly order mismatch"
            F106.append(T106[k].astype(np.float64))
            F134.append(T134[k].astype(np.float64))
        Fraw106.append(raw106.astype(np.float64))
        Fraw134.append(raw134.astype(np.float64))
        F2d.append(o2dn.astype(np.float64))
        recs.append(dict(
            photo_id=r["photo_id"], date=r["date"], seq=int(r["same_date_sequence"] or 0),
            yaw=float(r["yaw"]), pitch=float(r["pitch"]), roll=float(r["roll"]),
            pose_bin=r["pose_bin"], smile=bool(ch.get("smile_detected")),
            jaw=bool(ch.get("jaw_open_detected")),
            jaw_ratio=float(ch.get("jaw_open_ratio") or 0),
            corner=float(ch.get("corner_lift_ioc") or 0),
            vis106=int(ch.get("visible_landmarks_106") or 0),
            vis134=int(ch.get("visible_landmarks_134") or 0),
            reproj=float(ch.get("reprojection_p95") or 9),
            corr_mag=float(ch.get("correction_magnitude_deg") or 0),
        ))
    ph = pd.DataFrame(recs)
    A106 = np.stack(F106)
    A134 = np.stack(F134)
    R106 = np.stack(Fraw106)
    R134 = np.stack(Fraw134)
    D2 = np.stack(F2d)
    np.save(OUT / "A106_corrected.npy", A106)
    np.save(OUT / "A134_corrected.npy", A134)
    np.save(OUT / "R106_raw.npy", R106)
    np.save(OUT / "R134_raw.npy", R134)
    np.save(OUT / "D2_original_norm.npy", D2)

    # ---- event-level: медиана corrected-identity по дате ----
    ph["date"] = ph["date"].astype(str)
    events = sorted(ph["date"].unique())
    erows = []
    for ev in events:
        ix = ph.index[ph["date"] == ev].to_numpy()
        med134 = np.nanmedian(A134[ix], axis=0)
        # репрезентант: max vis134, min reproj
        sub = ph.loc[ix].sort_values(["vis134", "reproj"], ascending=[False, True])
        rep = sub.iloc[0]
        erows.append(dict(date=ev, n=len(ix), rep_photo=rep["photo_id"],
                          pose_bin=rep["pose_bin"], yaw=float(rep["yaw"]),
                          pitch=float(rep["pitch"]), roll=float(rep["roll"])))
    ev = pd.DataFrame(erows)
    np.save(OUT / "events_median134.npy",
            np.stack([np.nanmedian(A134[ph.index[ph["date"] == e].to_numpy()], axis=0) for e in ev["date"]]))
    ph.to_csv(OUT / "photos.csv", index=False)
    ev.to_csv(OUT / "events.csv", index=False)
    json.dump({"primary_channel": args.channel,
               "note": "targetonly=canonical (v2.7); legacy=R_corr deprecated sensitivity"},
              open(OUT / "channel.json", "w"))
    print(f"photos={len(ph)} events={len(ev)} channel={args.channel}", flush=True)

    # ---- matching: пары same-bin, малые Δуглы, same smile/jaw ----
    idx = ph.index.to_numpy()
    pairs = []
    for b, grp in ph.groupby("pose_bin"):
        gi = grp.index.to_numpy()
        yaw = grp["yaw"].to_numpy(float)
        pit = grp["pitch"].to_numpy(float)
        rol = grp["roll"].to_numpy(float)
        for ii in range(len(gi)):
            for jj in range(ii + 1, len(gi)):
                dy, dp, dr = abs(yaw[ii] - yaw[jj]), abs(pit[ii] - pit[jj]), abs(rol[ii] - rol[jj])
                if dy > 15 or dp > 10 or dr > 10:
                    continue
                a, c = ph.loc[gi[ii]], ph.loc[gi[jj]]
                if a["smile"] != c["smile"] or a["jaw"] != c["jaw"]:
                    continue
                if min(a["vis134"], c["vis134"]) < 60:
                    continue
                d134, n134 = procrustes(A134[gi[ii]], A134[gi[jj]])
                draw, _ = procrustes(R134[gi[ii]], R134[gi[jj]])
                # 2D-канал: нормированные original, Procrustes 2D
                x, y = D2[gi[ii]][:, :2], D2[gi[jj]][:, :2]
                m = np.isfinite(x).all(1) & np.isfinite(y).all(1)
                d2d = float(np.sqrt(np.mean(np.sum((x[m] - y[m]) ** 2, 1)))) if m.sum() >= 8 else float("nan")
                p95 = noise_p95(dy, True)
                pairs.append(dict(a=a["photo_id"], b=c["photo_id"], date_a=a["date"], date_b=c["date"],
                                  pose_bin=b, dyaw=round(dy, 2), dpitch=round(dp, 2), droll=round(dr, 2),
                                  d_corrected=round(d134, 5), d_raw=round(draw, 5), d_2d=round(d2d, 6),
                                  noise_p95=round(p95, 5),
                                  z_corrected=round(d134 / p95, 2),
                                  cross_period="yes" if a["date"][:4] != c["date"][:4] else "no"))
    pa = pd.DataFrame(pairs)
    pa.to_csv(OUT / "matched_pairs.csv", index=False)
    print(f"matched pairs={len(pa)} cross-period={int((pa.cross_period=='yes').sum())}", flush=True)
    print("z_corrected: median=%.2f p95=%.2f max=%.2f" % (
        pa.z_corrected.median(), pa.z_corrected.quantile(0.95), pa.z_corrected.max()), flush=True)


if __name__ == "__main__":
    sys.exit(main())
