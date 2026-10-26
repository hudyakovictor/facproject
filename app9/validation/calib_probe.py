#!/usr/bin/env python
"""Разведка /Volumes/SDCARD/calibration (deeputin-calibration-seven-datasets-v7).

Хотим понять, можно ли на нём независимо проверить P0 (raw object-space) против
P1 (aligned to pose-bin canonical yaw) и шум по бинам БЕЗ реконструкции:
 - есть ли 3D-координаты (x,y,z) в ldm106_raw / ldm106_aligned;
 - покрыты ли все 9 бинов на каждую персону и сколько записей;
 - что лежит в record.npz (альфа? confidence? полный mesh?);
 - это те же люди/кадры, что и в calibration_rakurs (пересечение по frame_index)?
 - один ли это непрерывный видео-сессион на персону (по frame_index / mtime).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

CAL = Path("/Volumes/SDCARD/calibration")
RAK = Path("/Volumes/SDCARD/calibration_rakurs")
BINS = ("frontal", "left_light", "right_light", "left_mid", "right_mid",
        "left_deep", "right_deep", "left_profile", "right_profile")


def load_pts(csv_path: Path) -> np.ndarray:
    a = np.loadtxt(csv_path, delimiter=",", skiprows=1)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    return a[:, 1:4] if a.shape[1] >= 4 else a


def main() -> None:
    persons = sorted(p.name for p in CAL.glob("person_*") if p.is_dir())
    print("person_* :", persons)

    npz_keys: list[str] = []
    bins_per_person: dict[str, Counter] = defaultdict(Counter)
    shapes = {}
    frame_index: dict[str, list[int]] = defaultdict(list)
    n_rec = 0
    for p in persons:
        for rec in sorted((CAL / p).glob("frame_*")):
            meta = rec / "metadata.json"
            if not meta.exists():
                continue
            m = json.loads(meta.read_text(encoding="utf-8"))
            n_rec += 1
            bins_per_person[p][m.get("pose_bin", "?")] += 1
            frame_index[p].append(int(m.get("frame_index", -1)))
            if (rec / "ldm106_raw.csv").exists() and (rec / "ldm106_aligned.csv").exists():
                raw = load_pts(rec / "ldm106_raw.csv")
                al = load_pts(rec / "ldm106_aligned.csv")
                shapes.setdefault("raw", raw.shape)
                shapes.setdefault("aligned", al.shape)
                shapes.setdefault("raw_fin", (bool(np.isfinite(raw).all()), float(np.nanmax(np.abs(raw)))))
                shapes.setdefault("al_fin", (bool(np.isfinite(al).all()), float(np.nanmax(np.abs(al)))))
            z = rec / "record.npz"
            if z.exists() and not npz_keys:
                with np.load(z, allow_pickle=False) as f:
                    npz_keys = [f"{k}:{f[k].shape}:{f[k].dtype}" for k in f.files]
    print("записей всего:", n_rec)
    print("формы ldm106:", shapes)
    print("record.npz поля:", npz_keys)

    print("\n=== бины по персонам ===")
    print("person".ljust(11) + "".join(b[:6].rjust(7) for b in BINS) + "   всего")
    for p in persons:
        c = bins_per_person[p]
        print(p.ljust(11) + "".join(str(c.get(b, 0)).rjust(7) for b in BINS) + str(sum(c.values())).rjust(8))
    cov = [b for b in BINS if all(bins_per_person[p].get(b, 0) >= 3 for p in persons)]
    print("бины, где >=3 кадров У КАЖДОЙ из", len(persons), "персон:", cov)

    print("\n=== continuity: один ли это видео-сессион на персону ===")
    for p in persons:
        idx = np.array(sorted(frame_index[p]))
        d = np.diff(idx)
        print(f"{p}: n={len(idx)} min={idx.min()} max={idx.max()} "
              f"median_gap={float(np.median(d)) if len(d) else 0:.0f} max_gap={int(d.max()) if len(d) else 0} "
              f"плотность={len(idx)/(idx.max()-idx.min()+1):.3f}")

    print("\n=== пересечение с calibration_rakurs (по frame_index) ===")
    for p in persons:
        rak = RAK / p
        if not rak.is_dir():
            print(f"{p}: нет папки в calibration_rakurs")
            continue
        rfi = set()
        for f in rak.glob("*/*.jpg"):
            if f.name.startswith("._"):
                continue
            core = f.stem.replace("frame_", "")
            try:
                rfi.add(int(core))
            except ValueError:
                pass
        cfi = set(frame_index[p])
        print(f"{p}: calibration={len(cfi)} rakurs={len(rfi)} пересечение={len(cfi & rfi)}")


if __name__ == "__main__":
    main()
