"""Smile/jaw-буфер: пересчёт R2 без фото в буферной зоне порогов (в ветке).

Границы буфера: corner_lift_ioc ±0.004 от 0.005; jaw_open_ratio ±0.03 от 0.28.
Вход: analyst_v25/top_pairs_zones.csv + старый storage (read-only, corner/jaw).
Выход: analyst_v25/r2_buffer_report.json + печать честного R2.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

WORK = Path(os.environ.get("FAC_WORK", "/Users/victorkhudyakov/work"))
OLD = Path(os.environ.get("FAC_STAGE1", "/Volumes/SDCARD/storage/stage1"))
AN = WORK / "analyst_v25"

CORNER_THR = 0.005
CORNER_BUF = 0.004
JAW_THR = 0.28
JAW_BUF = 0.03


def buffered(corner, jaw):
    return ((corner is not None and abs(corner - CORNER_THR) < CORNER_BUF)
            or (jaw is not None and abs(jaw - JAW_THR) < JAW_BUF))


def main():
    zt = pd.read_csv(AN / "top_pairs_zones.csv")
    cache: dict[str, tuple] = {}
    need = set(zt["a"]) | set(zt["b"])
    for pid in need:
        ch = json.load(open(OLD / pid / "info.json"))["chronology"]
        cache[pid] = (ch.get("corner_lift_ioc"), ch.get("jaw_open_ratio"))
    out = {"thresholds": {"corner": [CORNER_THR, CORNER_BUF], "jaw": [JAW_THR, JAW_BUF]}, "sets": {}}
    for name, sub in (("all_Zgt4", zt),
                      ("R2_nonbrow_raw", zt[~zt.worst_zone.isin(["browL", "browR"]) & (zt.z_raw > 3)])):
        buf = [buffered(*cache[a]) or buffered(*cache[b]) for a, b in zip(sub["a"], sub["b"])]
        clean = sub[[not b for b in buf]]
        out["sets"][name] = {
            "n": int(len(sub)), "clean": int(len(clean)),
            "zones": clean["worst_zone"].value_counts().to_dict(),
        }
        print(f"{name}: n={len(sub)} clean={len(clean)}", flush=True)
    json.dump(out, open(AN / "r2_buffer_report.json", "w"), indent=1)
    print("wrote r2_buffer_report.json", flush=True)


if __name__ == "__main__":
    sys.exit(main())
