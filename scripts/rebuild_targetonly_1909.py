"""Перестройка target-only канала для всех 1909 из сохранённых alpha (без inference).

V_id = BFM(alpha_id, 0); targetonly = normalize(V_id)[ldm] @ R_target(0, canon, 0).
canon/углы — из info.json (read-only старый storage).
Выход: analyst_v25/T134_targetonly.npy, T106_targetonly.npy
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

WORK = Path("/Users/victorkhudyakov/work")
OLD = Path("/Volumes/SDCARD/storage/stage1")
OUT = WORK / "analyst_v25"


def row_rot(p, y, r):
    p, y, r = np.radians([p, y, r])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1]])
    return ((rz @ ry @ rx).T).astype(np.float64)


def main():
    m = np.load(WORK / "assets" / "face_model.npy", allow_pickle=True).item()
    u = np.asarray(m["u"], np.float64).reshape(-1)
    BID = np.asarray(m["id"], np.float64)
    T6, T4, PIDS = [], [], []
    tl = list(csv.DictReader(open(OLD / "main_timeline.csv")))
    for n, r in enumerate(tl):
        d = OLD / r["photo_id"]
        try:
            z = np.load(d / "reconstruction.npz", allow_pickle=False)
            info = json.load(open(d / "info.json"))
        except Exception as e:
            print("skip", r["photo_id"], e, flush=True)
            continue
        aid = np.asarray(z["alpha_id"], np.float64).reshape(-1)
        V = (u + BID @ aid).reshape(35709, 3)
        c = V.mean(0)
        S = float(np.sqrt(np.mean(np.sum((V - c) ** 2, 1))))
        nrm = (V - c) / S
        canon = float(info["chronology"]["canonical_yaw"])
        Rt = row_rot(0.0, canon, 0.0)
        T = nrm @ Rt
        i106 = np.asarray(z["ldm106_vertex_indices"], np.int64).reshape(-1)
        i134 = np.asarray(z["ldm134_vertex_indices"], np.int64).reshape(-1)
        T6.append(T[i106].astype(np.float32))
        T4.append(T[i134].astype(np.float32))
        PIDS.append(r["photo_id"])
        if (n + 1) % 300 == 0:
            print(n + 1, flush=True)
    np.save(OUT / "T106_targetonly.npy", np.stack(T6))
    np.save(OUT / "T134_targetonly.npy", np.stack(T4))
    json.dump(PIDS, open(OUT / "T_targetonly_pids.json", "w"))
    print(f"DONE n={len(PIDS)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
