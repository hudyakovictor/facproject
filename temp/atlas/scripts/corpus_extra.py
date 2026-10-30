"""Пилот расширения корпуса: person_9/10/11 (wild Wikimedia).

Разметки поз для этих людей нет: all_calibration_index.csv содержит только
person_01..07. Скрипт честно помечает позы предсказанным yaw (`label_source:
predicted`), чтобы отчёты не выдавали псевдо-метку за ручную. Контроль
invalid_pose по расхождению метки и предсказания для них не работает — это
зафиксировано в reports/calibration-v4.md.

    python scripts/corpus_extra.py --per-person 20

Пишет reports/calibration/corpus-extra.json и не трогает production-профиль.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import _Job  # noqa: E402
from server import storage  # noqa: E402
from server.models.tddfa import classify_pose_bin  # noqa: E402

WILD = {
    "person_9": "trump",
    "person_10": "tom_cruise",
    "person_11": "george_w._bush",
}


def photo_files(root: Path):
    return sorted(p for p in root.glob("*.jpg")
                  if not p.name.startswith("._") and p.stat().st_size > 20_000)


def frame_number(path: Path) -> int:
    """Номер кадра в исходной серии (trump_0123.jpg -> 123)."""
    digits = re.findall(r"(\d+)", path.stem)
    return int(digits[-1]) if digits else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=20)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "reports/calibration/corpus-extra.json")
    args = ap.parse_args()

    known = {(p["group"], p["name"]): p
             for p in storage.read_db()["photos"] if not p.get("deleted_at")}
    plan = {}
    for person in WILD:
        files = photo_files(args.photos_root / person)
        if not files:
            raise SystemExit(f"нет фото: {person}")
        if 0 < args.per_person < len(files):
            index = np.linspace(0, len(files) - 1, args.per_person).round().astype(int)
            picked = [files[i] for i in sorted(set(index.tolist()))]
        else:
            picked = files
        plan[person] = picked
        print(person, "photos", len(files), "picked", len(picked))

    items = [(f"{person}/{path.name}", path.read_bytes())
             for person, files in plan.items() for path in files]
    storage.ingest(items, group="__wild__")
    known = {(p["group"], p["name"]): p
             for p in storage.read_db()["photos"] if not p.get("deleted_at")}
    ids = []
    for person, files in plan.items():
        for path in files:
            record = known.get((person, path.name))
            if record is None:
                raise SystemExit(f"не проиндексирован {person}/{path.name}")
            ids.append(record["id"])
    info = storage.process(_Job(), ids)
    print("process", {k: info[k] for k in ("photos", "cache_hits", "errors")})

    rows = []
    for person, files in plan.items():
        for order, path in enumerate(files):
            record = known.get((person, path.name))
            feature = storage.feature_path(record) if record else None
            if record is None or not feature.exists():
                rows.append({"person": person, "filename": path.name,
                             "frame": frame_number(path),
                             "status": "missing", "label_source": "predicted"})
                continue
            with np.load(feature) as handle:
                angles = np.ravel(handle["alpha"])
                yaw = float(np.degrees(angles[225]))
                current = float(np.degrees(angles[224]))
                roll = float(np.degrees(angles[226]))
            bin_name, _ = classify_pose_bin(yaw)
            rows.append({
                "person": person,
                "id": record["id"],
                "filename": path.name,
                "frame": frame_number(path),
                "yaw": round(yaw, 2),
                "pitch": round(current, 2),
                "roll": round(roll, 2),
                "bin": bin_name,
                "label_source": "predicted",
                "status": "ready",
            })
    payload = {
        "source": "Wikimedia Commons, no manual pose labels",
        "note": "Позы предсказаны моделью; invalid_pose по метке для этих людей не проверяется.",
        "people": {person: len(files) for person, files in plan.items()},
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    from collections import Counter

    print("bins", {p: dict(Counter(r.get("bin", "missing") for r in rows
                                     if r["person"] == p)) for p in WILD})
    print("frontal", {p: sum(1 for r in rows
                             if r["person"] == p and r.get("bin") == "frontal")
                       for p in WILD})
    print("report", args.out)


if __name__ == "__main__":
    main()
