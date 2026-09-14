"""Событийный permutation-null + Δt-стратифицированный знаменатель (R3).

1. Зональный worst пересчитывается на TARGET-канале для hi-пар.
2. Δt-страты: p95 RMSE по (yaw-gap × Δt-bin) из всех matched-пар -> Z_dt.
3. Null: перестановка ДАТ (событий) внутри страт pose/smile/jaw, 10k;
   статистика = max связок зона×год-пара (контроль look-elsewhere).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path(os.environ.get("FAC_WORK", "/Users/victorkhudyakov/work"))
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


def main():
    rng = np.random.default_rng(21)
    pa = pd.read_csv(AN / "matched_pairs_acceptance.csv")
    ph = pd.read_csv(AN / "photos.csv")
    T134 = np.load(AN / "T134_targetonly.npy")
    id_of = {p: i for i, p in enumerate(ph["photo_id"])}
    mu = np.nanmean(T134, axis=0)
    mu = (mu - mu.mean(0)) / np.sqrt(np.mean(np.sum((mu - mu.mean(0)) ** 2, 1)))
    zones = np.array([ZoneOf(p) for p in mu])
    znames = sorted(set(zones))

    # ---- Δt-страты знаменателя ----
    pa["dt_days"] = (pd.to_datetime(pa.date_b) - pd.to_datetime(pa.date_a)).dt.days.abs()

    def yb(dy):
        a = abs(float(dy))
        return "0-3" if a <= 3 else ("3-8" if a <= 8 else ("8-15" if a <= 15 else ">15"))

    def tb(dt):
        return "same" if dt == 0 else ("<1y" if dt < 365 else ("1-5y" if dt < 1825 else ">5y"))

    pa["yg"] = pa["dyaw"].map(yb)
    pa["dtb"] = pa["dt_days"].map(tb)
    # NOTE: d_corrected в acceptance — legacy-Proc; для знаменателя нужен RMSE.
    # Пересчитываем target-Proc RMSE один раз для всех пар.
    ia = pa["a"].map(id_of).to_numpy()
    ib = pa["b"].map(id_of).to_numpy()
    dt_rmse = np.zeros(len(pa))
    for k in range(len(pa)):
        dt_rmse[k], _ = procrustes(T134[ia[k]], T134[ib[k]])
        if (k + 1) % 20000 == 0:
            print(k + 1, flush=True)
    pa["d_tgt"] = dt_rmse
    denom = pa.groupby(["yg", "dtb"])["d_tgt"].quantile(0.95).reset_index()
    denom.to_csv(AN / "dt_noise_floor.csv", index=False)
    print(denom.to_string(), flush=True)
    key2p95 = {(r["yg"], r["dtb"]): r["d_tgt"] for _, r in denom.iterrows()}
    pa["z_dt"] = pa.apply(lambda r: r["d_tgt"] / key2p95[(r["yg"], r["dtb"])], axis=1)

    # ---- зональный worst на target для hi-пар ----
    hi = pa[pa.z_dt > 4].copy()
    print(f"target Z_dt>4: {len(hi)}", flush=True)
    wz, zr = [], []
    for _, r in hi.iterrows():
        i, j = id_of[r["a"]], id_of[r["b"]]
        _, d = procrustes(T134[i], T134[j])
        p = r["noise_p95"]
        per = {z: float(np.sqrt(np.mean(np.sum(d[zones == z] ** 2, 1)))) for z in znames}
        w = max(per, key=per.get)
        wz.append(w)
        # raw-согласие: d_raw из acceptance
        zr.append(r["d_raw"] / p)
    hi["worst_zone"] = wz
    hi["z_raw"] = zr
    print("worst_zone Z_dt>4:", hi["worst_zone"].value_counts().to_dict(), flush=True)
    r2t = hi[~hi.worst_zone.isin(["browL", "browR"]) & (hi.z_raw > 3)].copy()
    print(f"R2-target (nonbrow+raw): {len(r2t)}", flush=True)
    r2t["ya"] = r2t.date_a.str[:4]
    r2t["yb"] = r2t.date_b.str[:4]
    obs = r2t.groupby(["worst_zone", "ya", "yb"]).size()
    print("top links:", obs.sort_values(ascending=False).head(6).to_dict(), flush=True)
    obs_max = int(obs.max()) if len(obs) else 0

    # ---- событийный null: перестановка дат внутри страт ----
    phx = ph.set_index("photo_id")
    strata = (phx["pose_bin"].astype(str) + "|" + phx["smile"].astype(str)
              + "|" + phx["jaw"].astype(str)).to_dict()
    members = list(r2t[["a", "b", "worst_zone"]].itertuples(index=False))
    bystrat: dict[str, list] = {}
    for pid, s in strata.items():
        bystrat.setdefault(s, []).append(pid)
    null_max = []
    for _ in range(1000):
        perm = {}
        for s, pool in bystrat.items():
            sh = list(pool)
            rng.shuffle(sh)
            perm.update(dict(zip(pool, sh)))
        cnt: dict = {}
        for a, b, wzone in members:
            da, db = phx.loc[perm[a], "date"][:4], phx.loc[perm[b], "date"][:4]
            y1, y2 = (da, db) if da <= db else (db, da)
            k = (wzone, y1, y2)
            cnt[k] = cnt.get(k, 0) + 1
        null_max.append(max(cnt.values()) if cnt else 0)
    null_max = np.array(null_max)
    print(f"event-null links: obs_max={obs_max} null med={np.median(null_max):.1f} "
          f"p95={np.quantile(null_max, .95):.1f} max={null_max.max()} "
          f"p={(null_max >= obs_max).mean():.3f}", flush=True)
    hi.to_csv(AN / "target_hi_dt.csv", index=False)
    print("DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
