"""Аналитик v25, часть 3: permutation-null, события-граф, toward/away, tz,
ARI меток, Z-калибровка на контролях, Dt-страты. Только старые данные + калибровка.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

WORK = Path(os.environ.get("FAC_WORK", "/Users/victorkhudyakov/work"))
AN = WORK / "analyst_v25"
CALIB = Path(os.environ.get("FAC_CALIB", "/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
NOISE = pd.read_csv(WORK / "alpha_calib_v25" / "table5_noise_floor.csv")


def yaw_bin(dy):
    a = abs(float(dy))
    return "0-3" if a <= 3 else ("3-8" if a <= 8 else ("8-15" if a <= 15 else ">15"))


def noise_p95(dyaw):
    hit = NOISE[(NOISE.yaw_gap == yaw_bin(dyaw)) & (NOISE.same_bin == "yes")]
    return float(hit["p95"].iloc[0])


def procrustes(a, b):
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


SIDE = {"eyeL": -1, "eyeR": 1, "jawL": -1, "jawR": 1, "cheekL": -1, "cheekR": 1,
        "browL": -1, "browR": 1, "mouth": 0, "nose": 0, "nose_up": 0}


def main():
    rng = np.random.default_rng(7)
    zt = pd.read_csv(AN / "top_pairs_zones.csv")
    pa = pd.read_csv(AN / "matched_pairs.csv")
    ph = pd.read_csv(AN / "photos.csv")
    ev = pd.read_csv(AN / "events.csv")

    # ---- 1. события-граф R2-пар ----
    r2 = zt[~zt.worst_zone.isin(["browL", "browR"]) & (zt.z_raw > 3)].copy()
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for _, r in r2.iterrows():
        parent.setdefault(r["a"], r["a"])
        parent.setdefault(r["b"], r["b"])
        union(r["a"], r["b"])
    comp = {}
    for k in parent:
        comp.setdefault(find(k), []).append(k)
    dev = []
    for members in comp.values():
        dates = sorted(ph.set_index("photo_id").loc[members, "date"].unique())
        dev.append(dict(n_photos=len(members), n_events=len(dates),
                        span_days=(pd.to_datetime(dates[-1]) - pd.to_datetime(dates[0])).days if len(dates) > 1 else 0))
    ce = pd.DataFrame(dev)
    print(f"R2 graph: {len(r2)} пар -> {len(ce)} компонент; "
          f"событий всего: {ce.n_events.sum()}, max photos={ce.n_photos.max()}", flush=True)
    ce.to_csv(AN / "r2_event_components.csv", index=False)

    # ---- 2. toward/away ----
    yawmap = ph.set_index("photo_id")["yaw"].to_dict()
    tw = []
    for _, r in r2.iterrows():
        ym = (yawmap[r["a"]] + yawmap[r["b"]]) / 2
        s = SIDE.get(r["worst_zone"], 0)
        side = "center" if s == 0 else ("toward" if np.sign(s) == np.sign(ym) and ym != 0 else "away")
        tw.append(side)
    r2["side"] = tw
    print("R2 toward/away/center:", r2["side"].value_counts().to_dict(), flush=True)

    # ---- 3. tz-диагностика: лоб vs челюсть ----
    zc = [c for c in zt.columns if c.startswith("z_") and c != "z_corr" and c != "z_raw"]
    brow_c = [c for c in zc if "brow" in c]
    jaw_c = [c for c in zc if "jaw" in c]
    zt["brow_med"] = zt[brow_c].median(axis=1)
    zt["jaw_med"] = zt[jaw_c].median(axis=1)
    zt["tz_ratio"] = zt["brow_med"] / zt["jaw_med"].replace(0, np.nan)
    print("tz_ratio (brow/jaw): median=%.2f p10=%.2f p90=%.2f" % (
        zt.tz_ratio.median(), zt.tz_ratio.quantile(0.1), zt.tz_ratio.quantile(0.9)), flush=True)

    # ---- 4. ARI меток кластера к ковариатам ----
    evl = ev.set_index("date")["cluster2"].to_dict() if "cluster2" in ev.columns else {}
    if evl:
        lab = ph["date"].map(evl).to_numpy()
        ok = ~pd.isna(lab)
        print("ARI(label, pose_bin)=%.3f ARI(label, smile)=%.3f ARI(label, jaw)=%.3f ARI(label, year)=%.3f" % (
            adjusted_rand_score(lab[ok], ph.loc[ok, "pose_bin"]),
            adjusted_rand_score(lab[ok], ph.loc[ok, "smile"].astype(str)),
            adjusted_rand_score(lab[ok], ph.loc[ok, "jaw"].astype(str)),
            adjusted_rand_score(lab[ok], ph.loc[ok, "date"].str[:4]),
        ), flush=True)

    # ---- 5. Z-калибровка: FPR на контрольных парах калибровки ----
    rows = list(csv.DictReader(open(CALIB / "all_calibration_index.csv")))
    m = np.load(WORK / "assets" / "face_model.npy", allow_pickle=True).item()
    bu, bid = np.asarray(m["u"], float).reshape(-1), np.asarray(m["id"], float)
    FPR = []
    for pid in sorted({r["dataset_id"] for r in rows}):
        sub = [r for r in rows if r["dataset_id"] == pid]
        V, Y = [], []
        for r in sub:
            z = np.load(CALIB / r["npz_file"], allow_pickle=False)
            aid = np.asarray(z["alpha_id"], float).reshape(-1)
            i134 = np.asarray(z["ldm134_vertex_indices"], np.int64).reshape(-1)
            V.append((bu + bid @ aid).reshape(35709, 3)[i134])
            Y.append((float(r["yaw"]), r["pose_bin"]))
        V = np.stack(V)
        n = len(V)
        idx = rng.choice(n * (n - 1) // 2, min(4000, n * (n - 1) // 2), replace=False)
        pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
        zs = []
        for k in idx:
            i, j = pairs[k]
            if Y[i][1] != Y[j][1] or abs(Y[i][0] - Y[j][0]) > 15:
                continue
            d = procrustes(V[i], V[j])
            zs.append(d / noise_p95(Y[i][0] - Y[j][0]))
        zs = np.array(zs)
        if len(zs):
            FPR.append((pid, len(zs), float(np.mean(zs > 4)), float(np.mean(zs > 3))))
    fpr = pd.DataFrame(FPR, columns=["person", "n_pairs", "fpr_Z4", "fpr_Z3"])
    fpr.to_csv(AN / "z_calibration_fpr.csv", index=False)
    print(fpr.to_string(), flush=True)
    print("mean control FPR Z>4: %.4f" % fpr.fpr_Z4.mean(), flush=True)

    # ---- 6. permutation-null связок зона×годы ----
    r2["ya"] = r2.date_a.str[:4]
    r2["yb"] = r2.date_b.str[:4]
    obs = r2.groupby(["worst_zone", "ya", "yb"]).size()
    obs_max, obs_eye = int(obs.max()), int(obs.loc["eyeR", "2008", "2025"]) if ("eyeR", "2008", "2025") in obs.index else 0
    # пул фото со стратами
    phx = ph.set_index("photo_id")
    strata = (phx["pose_bin"].astype(str) + "|" + phx["smile"].astype(str) + "|" + phx["jaw"].astype(str)).to_dict()
    members = list(r2[["a", "b", "worst_zone"]].itertuples(index=False))
    bystrat = {}
    for pid, s in strata.items():
        bystrat.setdefault(s, []).append(pid)
    null_max = []
    for _ in range(200):
        perm = {}
        for s, pool in bystrat.items():
            sh = list(pool)
            rng.shuffle(sh)
            perm.update(dict(zip(pool, sh)))
        cnt = {}
        for a, b, wz in members:
            pa2, pb2 = perm[a], perm[b]
            da, db = phx.loc[pa2, "date"][:4], phx.loc[pb2, "date"][:4]
            ya2, yb2 = (da, db) if da <= db else (db, da)
            k = (wz, ya2, yb2)
            cnt[k] = cnt.get(k, 0) + 1
        null_max.append(max(cnt.values()))
    null_max = np.array(null_max)
    print(f"permutation-null links: obs_max={obs_max} (eyeR08-25={obs_eye}); "
          f"null max: median={np.median(null_max):.1f} p95={np.quantile(null_max, .95):.1f} max={null_max.max()} "
          f"p(obs_max)={(null_max >= obs_max).mean():.3f}", flush=True)

    # ---- 7. Δt-страты Z ----
    pa["dt_days"] = (pd.to_datetime(pa.date_b) - pd.to_datetime(pa.date_a)).dt.days.abs()
    pa["dt_bin"] = pd.cut(pa["dt_days"], [0, 1, 365, 1825, 99999], labels=["same-event", "<1y", "1-5y", ">5y"])
    dt = pa.groupby("dt_bin", observed=True)["z_corrected"].agg(n="size", median="median",
        p95=lambda s: float(s.quantile(0.95))).reset_index()
    dt.to_csv(AN / "z_by_dt.csv", index=False)
    print(dt.to_string(), flush=True)


if __name__ == "__main__":
    sys.exit(main())
