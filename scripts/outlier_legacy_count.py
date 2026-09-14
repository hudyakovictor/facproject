"""Подсчёт смены outlier-статусов legacy vs новый гейт на 1909 (без инференса).

Новый displacement = ||chrono - identity_normalized||, где identity_normalized
= chrono @ R_corr.T (точный replay). Legacy = ||chrono - object_normalized||.
Оба терма есть в старых NPZ. Порог отбора: >100 вершин.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import numpy as np

OLD = Path(os.environ.get("FAC_STAGE1", "/Volumes/SDCARD/storage/stage1"))
OUT = Path(os.environ.get("FAC_ANALYST", "/Users/victorkhudyakov/work/analyst_v25"))


def main():
    tl = list(csv.DictReader(open(OLD / "main_timeline.csv")))
    chg, tot = [], 0
    no, nn = [], []
    for r in tl:
        d = OLD / r["photo_id"]
        try:
            z = np.load(d / "reconstruction.npz", allow_pickle=False)
            ch = z["vertices_chronology_aligned"].astype(np.float64)
            ob = z["ldm134_object_normalized"]  # noqa: ensure key exists
            ob = z["vertices_object_normalized"].astype(np.float64)
            R = np.asarray(z["chronology_correction_matrix"], np.float64).reshape(3, 3)
        except Exception as e:
            print("skip", r["photo_id"], e, flush=True)
            continue
        idn = ch @ R.T
        disp_new = np.linalg.norm(ch - idn, axis=1)
        disp_old = np.linalg.norm(ch - ob, axis=1)
        o = int((disp_old > np.percentile(disp_old, 99) * 3).sum())
        n = int((disp_new > np.percentile(disp_new, 99) * 3).sum())
        no.append(o)
        nn.append(n)
        tot += 1
        if (o > 100) != (n > 100):
            chg.append((r["photo_id"], o, n))
    import statistics as st
    print(f"total={tot} status_changes={len(chg)}", flush=True)
    print(f"legacy: max={max(no)} mean={st.mean(no):.1f} | new: max={max(nn)} mean={st.mean(nn):.1f}", flush=True)
    for c in chg[:20]:
        print(c, flush=True)


if __name__ == "__main__":
    sys.exit(main())
