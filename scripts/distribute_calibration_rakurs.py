#!/usr/bin/env python3
"""Раскладка фото калибровки по ракурсам (POSE_BINS) для каждого человека.

Источник фото: /Volumes/SDCARD/photo/calibration_dataset/photos/{person}/{file}
Индекс углов:  /Volumes/SDCARD/calibration/all_calibration_index.csv
Результат:     /Volumes/SDCARD/calibration_rakurs/{person}/{pose_bin}/{file}

Бин определяется по yaw через диапазоны POSE_BINS (app6/stage1/config.py:17-25).
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

PHOTOS_DIR = Path("/Volumes/SDCARD/photo/calibration_dataset/photos")
INDEX_CSV = Path("/Volumes/SDCARD/calibration/all_calibration_index.csv")
OUT_DIR = Path("/Volumes/SDCARD/calibration_rakurs")

# (name, lo, hi, canonical) — lo включительно, hi исключительно
POSE_BINS = (
    ("left_profile", -95.0, -50.0, -70.0),
    ("left_deep", -50.0, -40.0, -45.0),
    ("left_mid", -40.0, -25.0, -32.5),
    ("left_light", -25.0, -10.0, -17.5),
    ("frontal", -10.0, 10.0, 0.0),
    ("right_light", 10.0, 25.0, 17.5),
    ("right_mid", 25.0, 40.0, 32.5),
    ("right_deep", 40.0, 50.0, 45.0),
    ("right_profile", 50.0, 95.000001, 70.0),
)


def classify_yaw(yaw: float) -> str | None:
    for name, lo, hi, _ in POSE_BINS:
        if lo <= yaw < hi:
            return name
    return None


def main() -> int:
    copied = 0
    missing_src = 0
    bad_yaw = 0
    per_person: dict[str, dict[str, int]] = {}

    with INDEX_CSV.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            person = row["dataset_id"].strip()
            fname = row["source_filename"].strip()
            if not person or not fname:
                continue
            try:
                yaw = float(row["yaw"])
            except (TypeError, ValueError):
                bad_yaw += 1
                continue
            bin_name = classify_yaw(yaw)
            if bin_name is None:
                bad_yaw += 1
                continue

            src = PHOTOS_DIR / person / fname
            if not src.is_file():
                missing_src += 1
                print(f"[MISS] {src}")
                continue

            dst_dir = OUT_DIR / person / bin_name
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst_dir / fname)
            copied += 1
            per_person.setdefault(person, {}).setdefault(bin_name, 0)
            per_person[person][bin_name] += 1

    print("\n=== ИТОГО ===")
    for person in sorted(per_person):
        total = sum(per_person[person].values())
        print(f"\n{person}  (всего {total})")
        for name, _, _, _ in POSE_BINS:
            c = per_person[person].get(name, 0)
            print(f"  {name:14s} {c}")
    print(f"\nСкопировано: {copied}")
    print(f"Не найдено исходников: {missing_src}")
    print(f"Записей с некорректным yaw: {bad_yaw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
