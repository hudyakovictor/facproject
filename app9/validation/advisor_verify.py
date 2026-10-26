#!/usr/bin/env python
"""Проверка тезисов советника на моих кэше (pts106 pose-free + углы из CSV).

A) Конфаунд: читает ли классификатор сам yaw? (корреляция yaw↔класс, acc по одному yaw)
B) Утечка vs межклассовый разброс по каждой из 17 метрик (после съёма эффекта персоны).
C) Симметризация лендмарок (гасит нечётный по x сигнал) против доворота P1: accuracy/хрупкость.
"""
from __future__ import annotations
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
IDS = ("put", "vas", "udmurt")
HYP = ROOT / ".runtime" / "hyp_cache"
SCAL = ROOT / ".runtime" / "rob_cache" / "scalars.jsonl"

spec = importlib.util.spec_from_file_location("r", HERE / "robustness_check.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
from morphing.backend import identity as I
from morphing.backend.aligner import normalize_ldm106

# билатеральная карта 106 (из symmetry_pairs_3d второго разработчика; layout совпадает)
PAIRS = [(0, 31), (1, 29), (3, 27), (5, 25), (7, 23), (9, 21), (11, 19), (13, 17),
         (33, 46), (34, 45), (35, 44), (36, 43), (37, 42), (57, 63), (59, 61),
         (66, 79), (67, 78), (69, 76), (70, 75), (71, 82), (73, 80),
         (84, 90), (85, 89), (86, 88), (91, 95), (92, 94), (96, 100), (97, 99), (101, 103)]
MIDLINE = [15, 51, 52, 53, 54, 60, 87, 93]  # self (середина)


def angles_from_csv():
    out = {}
    for ident in IDS:
        with (ROOT / f"{ident}_angles.csv").open(newline="", encoding="utf-8-sig") as fh:
            for rec in csv.DictReader(fh):
                name = (rec.get("filename") or "").strip()
                try:
                    out[f"{ident}/{name}"] = (float(rec["pitch_deg"]), float(rec["yaw_deg"]), float(rec["roll_deg"]))
                except (KeyError, ValueError):
                    pass
    return out


def center_scale(v):
    """Нормировка одна с продом: aligner.normalize_ldm106 (центр и RMS по 106 точкам)."""
    return normalize_ldm106(np.asarray(v, float))[0]


def symmetrize(p):
    cx = float(p[:, 0].mean())
    refl = lambda q: np.array([2 * cx - q[0], q[1], q[2]])
    out = p.copy()
    for i, j in PAIRS:
        mi = (p[i] + refl(p[j])) / 2.0
        out[i] = mi
        out[j] = refl(mi)
    for k in MIDLINE:
        out[k] = (p[k] + refl(p[k])) / 2.0  # на серединную плоскость
    return out


def main():
    ang = angles_from_csv()
    rows = []
    for line in SCAL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        npy = HYP / (rec["key"].replace("/", "__") + ".npy")
        if not npy.exists() or rec["key"] not in ang:
            continue
        p = np.load(npy)[:318].reshape(106, 3)
        pitch, yaw, roll = ang[rec["key"]]
        rows.append({"ident": rec["key"].split("/")[0], "p": p, "yaw": yaw})
    label = np.array([{"put": 0, "vas": 1, "udmurt": 2}[x["ident"]] for x in rows])
    yaw = np.array([x["yaw"] for x in rows])
    pts = np.array([x["p"] for x in rows])
    print(f"N={len(rows)}")

    # A) конфаунд: предсказывает ли yaw класс?
    print("\n--- A) mean |yaw| по классам:", [round(float(np.abs(yaw[label == k]).mean()), 1) for k in range(3)])
    acc_yaw_only = r.lda_acc(yaw[:, None], label)
    acc_absyaw_only = r.lda_acc(np.abs(yaw)[:, None], label)
    print(f"CV-LDA acc по ОДНОМУ (сырому) yaw = {acc_yaw_only:.3f}, по |yaw| = {acc_absyaw_only:.3f} (случайно=0.33)")

    X0 = np.array([I.form_vector(center_scale(p)) for p in pts])
    Xsym = np.array([I.form_vector(symmetrize(center_scale(p))) for p in pts])

    # B) утечка vs межклассовый разброс (для 17 метрик, эффект персоны снимаем внутри-классовой регрессией на yaw)
    print("\n--- B) по каждой из 17 метрик: leak(|slope|*std_yaw внутри персоны) / between(разброс средних по классам)")
    names = I.FEATURE_ORDER
    big_leak = 0
    for m in range(X0.shape[1]):
        v = X0[:, m]
        within = []
        for k in range(3):
            mk = label == k
            vv, yy = v[mk], yaw[mk]
            if np.std(yy) > 1e-6 and len(vv) > 5:
                slope = np.cov(vv, yy)[0, 1] / np.var(yy)
                within.append(abs(slope) * np.std(yy))
        leak = float(np.mean(within))
        between = float(np.std([v[label == k].mean() for k in range(3)]))
        ratio = leak / (between + 1e-12)
        if ratio > 0.2:
            big_leak += 1
        print(f"   {names[m]:22s} leak={leak:.4f} between={between:.4f} ratio={ratio:.2f}" + ("  <<>" if ratio > 0.5 else ""))
    print(f"метрик с leak/between>0.2: {big_leak}/17")

    # C) accuracy/хрупкость: P0 vs симметризация (и сверка с прошлым P1-доворотом)
    masks = {"strict": np.abs(yaw) <= 7, "light": (np.abs(yaw) > 7) & (np.abs(yaw) <= 15),
             "off": np.abs(yaw) > 15, "full": np.ones(len(label), bool)}
    print("\n--- C) 17 метрик: P0 ( pose-free ) vs P0+симметризация")
    print(f"{'stratum':8s} {'P0':>7s} {'P0+sym':>8s}")
    p0s, ps = [], []
    for s, mk in masks.items():
        a = r.lda_acc(X0[mk], label[mk]); b = r.lda_acc(Xsym[mk], label[mk])
        p0s.append(a); ps.append(b)
        print(f"{s:8s} {round(a,3) if a==a else None:>7} {round(b,3) if b==b else None:>8}")
    fA = [x for x in p0s if x == x]; fB = [x for x in ps if x == x]
    print(f"хрупкость:  P0={max(fA)-min(fA):.3f}   P0+sym={max(fB)-min(fB):.3f}")

    nx0 = np.array([p[54, 0] for p in map(center_scale, pts)])
    nxs = np.array([p[54, 0] for p in map(symmetrize, map(center_scale, pts))])
    print(f"corr(нос-x↔yaw): P0={np.corrcoef(nx0, yaw)[0,1]:+.2f}  P0+sym={np.corrcoef(nxs, yaw)[0,1]:+.2f}  "
          f"std: P0={nx0.std():.4f} sym={nxs.std():.4f}")


if __name__ == "__main__":
    main()
