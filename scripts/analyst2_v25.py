"""Аналитик v25, часть 2: зоны, A-B-A, кластеризация + negative control,
leave-year-out, чувствительность, шкала R0-R6.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

WORK = Path("/Users/victorkhudyakov/work")
AN = WORK / "analyst_v25"
CALIB = Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets")


def ZoneOf(p):
    """Геометрические зоны по нормированным (x right+, y up+) координатам."""
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


def main():
    ph = pd.read_csv(AN / "photos.csv")
    ev = pd.read_csv(AN / "events.csv")
    pa = pd.read_csv(AN / "matched_pairs.csv")
    A134 = np.load(AN / "A134_corrected.npy")
    R134 = np.load(AN / "R134_raw.npy")
    D2 = np.load(AN / "D2_original_norm.npy")
    EV134 = np.load(AN / "events_median134.npy")

    # ---- зоны по среднему shape ----
    mu = np.nanmean(A134, axis=0)
    mu = mu - mu.mean(0)
    sc = np.sqrt(np.mean(np.sum(mu ** 2, 1)))
    mun = mu / sc
    zones = np.array([ZoneOf(p) for p in mun])
    znames = sorted(set(zones))
    print("zones:", {z: int((zones == z).sum()) for z in znames}, flush=True)
    zid = {z: np.flatnonzero(zones == z) for z in znames}

    # ---- топ-пары Z>4: зональная декомпозиция + каналы ----
    top = pa[pa.z_corrected > 4].copy()
    id_of = {pid: i for i, pid in enumerate(ph["photo_id"])}
    zrows = []
    for _, r in top.iterrows():
        i, j = id_of[r["a"]], id_of[r["b"]]
        a, b = A134[i], A134[j]
        m = np.isfinite(a).all(1) & np.isfinite(b).all(1)
        ca, cb = a[m].mean(0), b[m].mean(0)
        x, y = b[m] - cb, a[m] - ca
        U, _, Vt = np.linalg.svd(x.T @ y)
        Rm = U @ Vt
        if np.linalg.det(Rm) < 0:
            Vt[-1] *= -1
            Rm = U @ Vt
        res = np.linalg.norm(x @ Rm - y, axis=1)
        per_zone = {}
        for z in znames:
            sel = np.flatnonzero(m)[np.isin(np.flatnonzero(m), zid[z])]
            per_zone[z] = float(np.sqrt(np.mean(res[np.isin(np.flatnonzero(m), zid[z])] ** 2))) if (np.isin(np.flatnonzero(m), zid[z]).sum() >= 3) else float("nan")
        # raw-канал Z (тот же noise p95 как чувствительность)
        xa, xb = R134[i], R134[j]
        mm = np.isfinite(xa).all(1) & np.isfinite(xb).all(1)
        ca2, cb2 = xa[mm].mean(0), xb[mm].mean(0)
        x2, y2 = xb[mm] - cb2, xa[mm] - ca2
        U2, _, V2 = np.linalg.svd(x2.T @ y2)
        R2m = U2 @ V2
        if np.linalg.det(R2m) < 0:
            V2[-1] *= -1
            R2m = U2 @ V2
        draw = float(np.sqrt(np.mean(np.sum((x2 @ R2m - y2) ** 2, 1))))
        zrows.append(dict(a=r["a"], b=r["b"], date_a=r["date_a"], date_b=r["date_b"],
                           z_corr=r["z_corrected"], z_raw=round(draw / r["noise_p95"], 2),
                           d_2d=r["d_2d"], n_zones_hi=sum(1 for v in per_zone.values() if v > r["noise_p95"]),
                           worst_zone=max(per_zone, key=lambda k: per_zone[k] if np.isfinite(per_zone[k]) else -1),
                           **{f"z_{k}": round(v / r["noise_p95"], 2) if np.isfinite(v) else None for k, v in per_zone.items()}))
    zt = pd.DataFrame(zrows)
    zt.to_csv(AN / "top_pairs_zones.csv", index=False)
    print(f"top pairs Z>4: {len(zt)}", flush=True)
    if len(zt):
        print("multichannel agree: z_raw>3 in %d/%d, median z_raw=%.2f" % (
            int((zt.z_raw > 3).sum()), len(zt), zt.z_raw.median()), flush=True)

    # ---- event-медоиды: признаки для кластеризации ----
    X = EV134.reshape(len(EV134), -1)
    X = (X - X.mean(0)) / (X.std(0) + 1e-12)
    X = np.nan_to_num(X)
    km = KMeans(n_clusters=2, n_init=20, random_state=0).fit(X)
    lab = km.labels_
    sil = silhouette_score(X, lab)
    ev["cluster2"] = lab
    print(f"k=2 silhouette={sil:.3f} sizes={np.bincount(lab)}", flush=True)
    # стабильность: 106-канал
    A106 = np.load(AN / "A106_corrected.npy")
    E106 = np.stack([np.nanmedian(A106[ph.index[ph["date"] == e].to_numpy()], axis=0) for e in ev["date"]])
    X6 = np.nan_to_num((E106.reshape(len(E106), -1) - E106.reshape(len(E106), -1).mean(0)) / (E106.reshape(len(E106), -1).std(0) + 1e-12))
    lab6 = KMeans(n_clusters=2, n_init=20, random_state=0).fit_predict(X6)
    print("ARI(134 vs 106)=%.3f" % adjusted_rand_score(lab, lab6), flush=True)
    # один бин (frontal события по репрезентанту)
    fr = ev.index[ev.pose_bin == "frontal"].to_numpy()
    if len(fr) > 20:
        labf = KMeans(n_clusters=2, n_init=20, random_state=1).fit_predict(X[fr])
        print("frontal-only k=2 sizes=%s sil=%.3f" % (np.bincount(labf), silhouette_score(X[fr], labf)), flush=True)
    # балансировка годов
    ev["year"] = ev["date"].str[:4]
    yrs = sorted(ev["year"].unique())
    rng = np.random.default_rng(0)
    per_yr = min((ev["year"] == y).sum() for y in yrs)
    bal = np.concatenate([rng.choice(ev.index[ev["year"] == y].to_numpy(), per_yr, replace=False) for y in yrs])
    labb = KMeans(n_clusters=2, n_init=20, random_state=2).fit_predict(X[bal])
    print("year-balanced ARI vs full=%.3f" % adjusted_rand_score(lab[bal], labb), flush=True)

    # ---- negative control: тот же пайплайн на калибровочных персонах ----
    import csv as _csv
    rows = list(_csv.DictReader(open(CALIB / "all_calibration_index.csv")))
    m = np.load(WORK / "assets" / "face_model.npy", allow_pickle=True).item()
    bu, bid, bexp = (np.asarray(m["u"], float).reshape(-1), np.asarray(m["id"], float), np.asarray(m["exp"], float))
    ncout = []
    for pid in sorted({r["dataset_id"] for r in rows}):
        sub = [r for r in rows if r["dataset_id"] == pid]
        if len(sub) < 30:
            continue
        F = []
        for r in sub:
            z = np.load(CALIB / r["npz_file"], allow_pickle=False)
            aid = np.asarray(z["alpha_id"], float).reshape(-1)
            i134 = np.asarray(z["ldm134_vertex_indices"], np.int64).reshape(-1)
            V = (bu + bid @ aid).reshape(35709, 3)[i134]
            F.append(V.reshape(-1))
        F = np.stack(F)
        Fs = (F - F.mean(0)) / (F.std(0) + 1e-12)
        l2 = KMeans(n_clusters=2, n_init=20, random_state=0).fit_predict(Fs)
        ncout.append(dict(person=pid, n=len(sub), sil=round(silhouette_score(Fs, l2), 3),
                          sizes=str(np.bincount(l2).tolist())))
    nc = pd.DataFrame(ncout)
    nc.to_csv(AN / "negative_control.csv", index=False)
    print(nc.to_string(), flush=True)

    # ---- A-B-A по последовательности событий ----
    seq = ev.sort_values("date")
    labs = seq["cluster2"].to_numpy()
    aba = 0
    abab = 0
    runs = []
    for i in range(len(labs) - 2):
        if labs[i] != labs[i + 1] and labs[i + 1] != labs[i + 2] and labs[i] == labs[i + 2]:
            aba += 1
            runs.append((seq.iloc[i]["date"], seq.iloc[i + 1]["date"], seq.iloc[i + 2]["date"]))
            if i + 3 < len(labs) and labs[i + 3] == labs[i + 1]:
                abab += 1
    pd.DataFrame(runs, columns=["A1", "B", "A2"]).to_csv(AN / "aba_patterns.csv", index=False)
    print(f"A-B-A patterns={aba} A-B-A-B={abab}", flush=True)

    # ---- leave-year-out: стабильность меток ----
    aris = {}
    for y in yrs:
        tr = ev.index[ev["year"] != y].to_numpy()
        if len(tr) < 20:
            continue
        l = KMeans(n_clusters=2, n_init=20, random_state=0).fit_predict(X[tr])
        aris[y] = round(adjusted_rand_score(lab[tr], l), 3)
    pd.DataFrame([dict(year=k, ARI=v) for k, v in aris.items()]).to_csv(AN / "leave_year_out.csv", index=False)
    print("leave-year-out min ARI=%.3f" % min(aris.values()), flush=True)
    ev.to_csv(AN / "events.csv", index=False)

    # ---- чувствительность: нормировки ----
    pa_all = pa.copy()
    pa_all["hi_corr"] = pa_all.z_corrected > 3
    pa_all["hi_raw"] = pa_all.d_raw / pa_all.noise_p95 > 3
    print("pairs Z>3: corrected=%d raw=%d both=%d" % (
        int(pa_all.hi_corr.sum()), int(pa_all.hi_raw.sum()), int((pa_all.hi_corr & pa_all.hi_raw).sum())), flush=True)


if __name__ == "__main__":
    sys.exit(main())
