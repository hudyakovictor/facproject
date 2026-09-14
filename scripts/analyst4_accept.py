"""Приёмка П1 на полном архиве: legacy vs target-only, Procrustes + centered-only,
флаги, brow-доли, кластеризация ARI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

WORK = Path("/Users/victorkhudyakov/work")
AN = WORK / "analyst_v25"


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


def proc(a, b):
    ca, cb = a.mean(0), b.mean(0)
    x, y = b - cb, a - ca
    U, _, Vt = np.linalg.svd(x.T @ y)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = U @ Vt
    d = x @ R - y
    return float(np.sqrt(np.mean(np.sum(d * d, 1)))), d


def centered(a, b):
    d = (b - b.mean(0)) - (a - a.mean(0))
    return float(np.sqrt(np.mean(np.sum(d * d, 1)))), d


def main():
    pa = pd.read_csv(AN / "matched_pairs.csv")
    ph = pd.read_csv(AN / "photos.csv")
    A134 = np.load(AN / "A134_corrected.npy")
    R134 = np.load(AN / "R134_raw.npy")
    T134 = np.load(AN / "T134_targetonly.npy")
    pids = json.load(open(AN / "T_targetonly_pids.json"))
    assert list(ph["photo_id"]) == pids, "order mismatch"
    id_of = {p: i for i, p in enumerate(pids)}
    mu = np.nanmean(T134, axis=0)
    mu = (mu - mu.mean(0)) / np.sqrt(np.mean(np.sum((mu - mu.mean(0)) ** 2, 1)))
    zones = np.array([ZoneOf(p) for p in mu])
    znames = sorted(set(zones))

    ia = pa["a"].map(id_of).to_numpy()
    ib = pa["b"].map(id_of).to_numpy()
    p95 = pa["noise_p95"].to_numpy(float)
    n = len(pa)
    out = np.zeros((n, 4))  # legacy_proc, target_proc, legacy_cen, target_cen
    for k in range(n):
        i, j = ia[k], ib[k]
        out[k, 0], _ = proc(A134[i], A134[j])
        out[k, 1], _ = proc(T134[i], T134[j])
        out[k, 2], _ = centered(A134[i], A134[j])
        out[k, 3], _ = centered(T134[i], T134[j])
        if (k + 1) % 15000 == 0:
            print(k + 1, flush=True)
    Z = out / p95[:, None]
    pa["z_leg_proc"] = Z[:, 0]
    pa["z_tgt_proc"] = Z[:, 1]
    pa["z_leg_cen"] = Z[:, 2]
    pa["z_tgt_cen"] = Z[:, 3]
    for col in ["z_leg_proc", "z_tgt_proc", "z_leg_cen", "z_tgt_cen"]:
        hi = pa[pa[col] > 4]
        print(f"{col}: Z>4 n={len(hi)}", flush=True)
    lp = set(pa.index[pa.z_leg_proc > 4])
    tp = set(pa.index[pa.z_tgt_proc > 4])
    lc = set(pa.index[pa.z_leg_cen > 4])
    tc = set(pa.index[pa.z_tgt_cen > 4])
    print(f"proc: legacy∩target={len(lp & tp)} legacy-only={len(lp - tp)} target-only={len(tp - lp)}", flush=True)
    print(f"centered: legacy={len(lc)} target={len(tc)} overlap={len(lc & tc)}", flush=True)
    # brow-доли на centered-флагах
    for tag, idx in (("leg_cen", lc), ("tgt_cen", tc)):
        if not idx:
            continue
        sub = pa.loc[list(sorted(idx))]
        bw = 0
        allz = 0
        for _, r in sub.iterrows():
            i, j = id_of[r["a"]], id_of[r["b"]]
            arr = A134 if tag.startswith("leg") else T134
            _, d = centered(arr[i], arr[j])
            per = {z: float(np.sqrt(np.mean(np.sum(d[zones == z] ** 2, 1)))) for z in znames}
            w = max(per, key=per.get)
            bw += w in ("browL", "browR")
            allz += sum(1 for v in per.values() if v > r["noise_p95"]) == len(znames)
        print(f"{tag}: brow share={bw / len(sub):.2f} all-zones share={allz / len(sub):.2f}", flush=True)
    # кластеризация target-медиан событий
    ev = pd.read_csv(AN / "events.csv")
    E = np.stack([np.nanmedian(T134[ph.index[ph["date"] == e].to_numpy()], axis=0) for e in ev["date"]])
    X = np.nan_to_num((E.reshape(len(E), -1) - E.reshape(len(E), -1).mean(0)) / (E.reshape(len(E), -1).std(0) + 1e-12))
    lab_t = KMeans(n_clusters=2, n_init=20, random_state=0).fit_predict(X)
    print("ARI(legacy_labels, target_labels)=%.3f" % adjusted_rand_score(ev["cluster2"].to_numpy(), lab_t), flush=True)
    # где каналы расходятся: стратификация по величине коррекции пары
    phx = ph.set_index("photo_id")
    import csv as _csv
    corr = {}
    for _, r in pa.iterrows():
        pass
    # величина rotation-различия пары через сами каналы (centered diff / p95)
    chdiff = np.zeros(n)
    for k in range(n):
        i, j = ia[k], ib[k]
        da, _ = centered(A134[i], T134[i])
        db, _ = centered(A134[j], T134[j])
        chdiff[k] = (da + db) / 2 / p95[k]
    pa["channel_diff_z"] = chdiff
    print("channel_diff_z: median=%.3f p95=%.3f max=%.3f frac>1: %.3f" % (
        float(np.median(chdiff)), float(np.quantile(chdiff, .95)), float(chdiff.max()),
        float(np.mean(chdiff > 1))), flush=True)
    pa.to_csv(AN / "matched_pairs_acceptance.csv", index=False)
    print("DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
