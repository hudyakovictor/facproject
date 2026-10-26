#!/usr/bin/env python
"""Решающий тест: поворачивать ли v_id в (0,0,0) обратной матрицей ОЦЕНЁННОЙ позы
(идея пользователя == full_pose_correction_matrix с target=0), перед замером метрик.

P0 = как сейчас (center+scale, без доворота)
P1 = center -> v_id @ R(angles)^T  (снять оценённый yaw/pitch/roll) -> scale
Сравниваем CV-LDA по 17 геометр. метрикам по стратам + остаётся ли corr(нос-x↔yaw).
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
from app8 import geometry as g
from morphing.backend import identity as I


def angles_from_csv():
    out = {}
    for ident in IDS:
        with (ROOT / f"{ident}_angles.csv").open(newline="", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                name = (rec.get("filename") or "").strip()
                try:
                    out[f"{ident}/{name}"] = (float(rec["pitch_deg"]), float(rec["yaw_deg"]), float(rec["roll_deg"]))
                except (KeyError, ValueError):
                    pass
    return out


def center_scale(v):
    v = v - v.mean(0)
    s = float(np.linalg.norm(v, axis=1).max())
    return v / s if s > 1e-4 else v


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
        rows.append((rec["key"].split("/")[0], p, pitch, yaw, roll))

    label = np.array([{"put": 0, "vas": 1, "udmurt": 2}[x[0]] for x in rows])
    yaw = np.array([x[3] for x in rows])

    P0, P1 = [], []
    for _, p, pitch, y, roll in rows:
        c = center_scale(p)
        P0.append(c)
        R = g.row_rotation_matrix(pitch, y, roll)   # (rz@ry@rx)^T
        P1.append(center_scale(c @ R.T))            # снять оценённую позу
    P0 = np.array(P0); P1 = np.array(P1)

    X0 = np.array([I.form_vector(p) for p in P0])
    X1 = np.array([I.form_vector(p) for p in P1])

    masks = {
        "strict": np.abs(yaw) <= 7,
        "light": (np.abs(yaw) > 7) & (np.abs(yaw) <= 15),
        "off": np.abs(yaw) > 15,
        "full": np.ones(len(label), bool),
    }
    print("=== 17 геометр. метрик: доворота нет (P0) vs доворот в (0,0,0) по оценке (P1) ===")
    print(f"{'stratum':8s} {'n':>4s} {'P0':>7s} {'P1':>7s} {'Δ(P1-P0)':>10s}")
    for s, mk in masks.items():
        a = r.lda_acc(X0[mk], label[mk]); b = r.lda_acc(X1[mk], label[mk])
        d = None if (a != a or b != b) else round(b - a, 3)
        print(f"{s:8s} {int(mk.sum()):>4d} {round(a,3) if a==a else None:>7} {round(b,3) if b==b else None:>7} {str(d):>10s}")
    fA = [r.lda_acc(X0[masks[s]], label[masks[s]]) for s in masks]; fA = [x for x in fA if x == x]
    fB = [r.lda_acc(X1[masks[s]], label[masks[s]]) for s in masks]; fB = [x for x in fB if x == x]
    print(f"хрупкость:  P0={max(fA)-min(fA):.3f}   P1={max(fB)-min(fB):.3f}")

    # осталась ли утечка yaw в координаты (нос-x относительно серединной плоскости)
    nx0 = P0[:, 54, 0]; nx1 = P1[:, 54, 0]
    print(f"\ncorr(нос-x ↔ CSV yaw):  P0={np.corrcoef(nx0, yaw)[0,1]:+.2f}   P1={np.corrcoef(nx1, yaw)[0,1]:+.2f}")
    print(f"std(нос-x):             P0={nx0.std():.4f}   P1={nx1.std():.4f}")


if __name__ == "__main__":
    main()
