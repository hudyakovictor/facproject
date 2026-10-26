#!/usr/bin/env python
"""Сидит ли фото-поза (yaw/pitch/roll) в vertices_identity_only?

Если бы v_id содержал вращение головы, то «перекос» лендмарк-конфигурации
(напр. roll линии глаз, латеральное смещение кончика носа) коррелировал бы с
углами из CSV. Если v_id — уже канон (поза вынесена), корреляции не будет.
"""
from __future__ import annotations
import csv
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
IDS = ("put", "vas", "udmurt")

spec = importlib.util.spec_from_file_location("r", HERE / "robustness_check.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

EYE_L = [67, 74, 104, 66, 68, 69]
EYE_R = [76, 78, 81, 83, 105, 79, 77]


def angles_from_csv() -> dict[str, tuple[float, float, float]]:
    out: dict[str, tuple[float, float, float]] = {}
    for ident in IDS:
        with (ROOT / f"{ident}_angles.csv").open(newline="", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                name = (rec.get("filename") or "").strip()
                try:
                    p, y, ro = float(rec["pitch_deg"]), float(rec["yaw_deg"]), float(rec["roll_deg"])
                except (KeyError, TypeError, ValueError):
                    continue
                out[f"{ident}/{name}"] = (p, y, ro)
    return out


def proxies(pts: np.ndarray) -> tuple[float, float]:
    el, er = pts[EYE_L].mean(0), pts[EYE_R].mean(0)
    roll_proxy = np.degrees(np.arctan2(el[1] - er[1], el[0] - er[0]))  # наклон линии глаз в xy
    zyg_mid = (pts[3] + pts[29]) / 2.0
    yaw_proxy = pts[54, 0] - zyg_mid[0]  # латеральное смещение кончика носа от средней линии
    return float(roll_proxy), float(yaw_proxy)


prox = proxies  # alias


def main() -> None:
    ang = angles_from_csv()
    # пересобираем pts + углы напрямую по scalars (тот же порядок, что и load_all)
    HYP = ROOT / ".runtime" / "hyp_cache"
    recs = []
    for line in (ROOT / ".runtime" / "rob_cache" / "scalars.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = __import__("json").loads(line)
        npy = HYP / (row["key"].replace("/", "__") + ".npy")
        if not npy.exists() or row["key"] not in ang:
            continue
        pts = np.load(npy)[:318].reshape(106, 3)
        p, y, ro = ang[row["key"]]
        recs.append((row["key"].split("/")[0], p, y, ro, pts))
    for ident in IDS:
        sel = [x for x in recs if x[0] == ident]
        if not sel:
            continue
        rp = np.array([prox(s[4])[0] for s in sel])
        yp = np.array([prox(s[4])[1] for s in sel])
        roll = np.array([s[3] for s in sel])
        yaw = np.array([s[2] for s in sel])
        c_roll = np.corrcoef(rp, roll)[0, 1]
        c_yaw = np.corrcoef(yp, yaw)[0, 1]
        print(f"[{ident:7s}] n={len(sel):3d}  "
              f"corr(roll-глаз↔CSV roll)={c_roll:+.2f}  corr(нос-x↔CSV yaw)={c_yaw:+.2f}  "
              f"std(roll-глаз)={rp.std():.2f}°  std(нос-x)={yp.std():.3f}")
    allrp = np.array([prox(x[4])[0] for x in recs])
    allyaw = np.array([x[2] for x in recs])
    allroll = np.array([x[3] for x in recs])
    allyp = np.array([prox(x[4])[1] for x in recs])
    print("\n=== все кадры |yaw|<=32 ===")
    print(f"corr(roll-глаз ↔ CSV roll) = {np.corrcoef(allrp, allroll)[0,1]:+.2f}")
    print(f"corr(нос-x ↔ CSV yaw)      = {np.corrcoef(allyp, allyaw)[0,1]:+.2f}")
    print(f"разброс roll-глаз по всем: min={allrp.min():.1f}° max={allrp.max():.1f}° (CSV roll разброс {allroll.min():.0f}..{allroll.max():.0f}°)")


if __name__ == "__main__":
    main()
