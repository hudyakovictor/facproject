"""Шаг 3 итерации 5: ручная yaw-разметка кадров person_9/10/11.

Дикие Wikimedia-люди были без ручной метки: их позы предсказаны моделью
(`label_source: predicted`), поэтому контроль `invalid_pose` по расхождению
метки и yaw для них не работал. Здесь по каждому из 56 готовых кадров
(20 + 18 + 18) проставлена ручная оценка yaw (глазом по контакт-листам),
для каждого кадра записаны метка и предсказание модели, посчитано расхождение.

Порог `invalid_pose` — LABEL_MISMATCH из текущего харнесс-конфига
(calibration_v3.LABEL_MISMATCH = 90°): кадр помечается invalid_pose, если
|manual_yaw − predicted_yaw| > порога либо лицо в кадре отсутствует/не является
лицом субъекта (постер, статуя, обложка книги, съёмка со спины).

Источник поз переключается с `predicted` на `manual+yaw`. Артефакты:
  reports/calibration/pose-labels-v5.json      — по каждому кадру метка/предсказание/расхождение
  reports/calibration/invalid-frames-v5.json   — список невалидных кадров
  reports/calibration/corpus-extra-v5.json     — обновлённая таблица корпуса (manual+yaw)

    cd /Users/victorkhudyakov/work/temp/atlas
    python scripts/pose_labels_v5.py
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_v3 import LABEL_MISMATCH, YAW_LIMIT  # noqa: E402
from server.models.tddfa import classify_pose_bin  # noqa: E402

# Ручная оценка yaw (градусы, нос вправо — плюс). None — лицо субъекта
# отсутствует или кадр не является лицом (постер/статуя/обложка/со спины).
MANUAL_YAW = {
    "person_9": {
        126: -63, 83: -55, 94: -47, 190: -40, 105: -30, 73: -20, 136: -15,
        179: -12, 146: -13, 167: -12, 33: -4, 49: -3, 157: -4, 62: -2,
        115: 2, 19: -28, 230: 5, 200: 15, 2: 35, 256: 45,
    },
    "person_10": {
        116: 35, 520: -40, 809: -25, 463: -8, 1100: -5, 752: -5, 867: 0,
        1: -3, 694: 0, 1041: 0, 579: 1, 983: 5, 174: 5, 925: 20, 59: -30,
        405: 5, 347: None, 636: None,
    },
    "person_11": {
        757: -40, 648: -30, 865: -20, 702: None, 592: 0, 919: None, 1: 0,
        1026: 0, 483: 0, 973: 5, 539: 0, 270: 5, 377: 30, 55: None, 163: 40,
        430: 10, 109: None, 811: -55,
    },
}
# Кадры без лица субъекта (ручной визуальный контроль): invalid_pose по причине non_face.
NON_FACE = {
    ("person_10", 347): "съёмка со спины, лица нет",
    ("person_10", 636): "субъект отвернут, фронтальной составляющей лица нет",
    ("person_11", 702): "обложка книги с миниатюрным фото",
    ("person_11", 919): "кинопостер, на постере другие актёры",
    ("person_11", 55): "бронзовая статуя, не живое лицо",
    ("person_11", 109): "в кадре только другие люди, субъекта нет",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--extra", type=Path,
                    default=ROOT / "reports/calibration/corpus-extra.json")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "reports/calibration")
    args = ap.parse_args()

    payload = json.loads(args.extra.read_text())
    rows = [r for r in payload["rows"] if r.get("status") == "ready"]
    labeled = []
    for r in rows:
        person, frame = r["person"], int(r["frame"])
        manual = MANUAL_YAW[person][frame]
        pred = float(r["yaw"])
        reason = None
        if (person, frame) in NON_FACE:
            reason = f"non_face: {NON_FACE[(person, frame)]}"
        elif manual is None:
            reason = "non_face"
        elif abs(pred) > YAW_LIMIT:
            reason = f"|pred_yaw|={pred:.1f}>{YAW_LIMIT:.0f}"
        elif abs(manual - pred) > LABEL_MISMATCH:
            reason = f"label_mismatch: |{manual:.0f} - {pred:.0f}| = " \
                     f"{abs(manual - pred):.0f} > {LABEL_MISMATCH:.0f}"
        discrepancy = None if manual is None else round(abs(manual - pred), 1)
        manual_bin = None if manual is None else classify_pose_bin(manual)[0]
        labeled.append({
            "person": person, "frame": frame, "id": r["id"], "filename": r["filename"],
            "pred_yaw": round(pred, 1), "pred_bin": r["bin"],
            "manual_yaw": manual, "manual_bin": manual_bin,
            "discrepancy": discrepancy, "invalid": reason is not None,
            "reason": reason or "",
        })

    valid = [x for x in labeled if not x["invalid"]]
    invalid = [x for x in labeled if x["invalid"]]
    disc = [x["discrepancy"] for x in valid if x["discrepancy"] is not None]
    per_person = {}
    for person in MANUAL_YAW:
        own = [x for x in labeled if x["person"] == person]
        ok = [x for x in own if not x["invalid"]]
        per_person[person] = {
            "frames": len(own), "valid": len(ok),
            "invalid": len(own) - len(ok),
            "frontal": sum(1 for x in ok if x["manual_bin"] == "frontal"),
            "label_source": "manual+yaw",
        }

    meta = {
        "iteration": 5, "step": 3,
        "invalid_pose_threshold": {
            "label_mismatch_deg": LABEL_MISMATCH, "yaw_limit_deg": YAW_LIMIT,
            "source": "calibration_v3.LABEL_MISMATCH / YAW_LIMIT (текущий конфиг харнесса)",
        },
        "n_frames": len(labeled), "n_valid": len(valid), "n_invalid": len(invalid),
        "discrepancy_valid": {
            "median": round(statistics.median(disc), 1),
            "mean": round(statistics.mean(disc), 1),
            "p90": round(sorted(disc)[int(0.9 * len(disc)) - 1], 1),
            "max": round(max(disc), 1),
        },
        "per_person": per_person,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "pose-labels-v5.json").write_text(json.dumps(
        {**meta, "frames": labeled}, ensure_ascii=False, indent=1))
    (args.out_dir / "invalid-frames-v5.json").write_text(json.dumps(
        {"n_invalid": len(invalid), "frames": invalid}, ensure_ascii=False, indent=1))

    # Обновлённая таблица корпуса: источник поз manual+yaw, yaw=ручная метка,
    # невалидные кадры остаются в списке с флагом invalid_pose.
    updated = []
    by = {(x["person"], x["frame"]): x for x in labeled}
    for r in payload["rows"]:
        key = (r["person"], int(r["frame"]))
        cell = by.get(key)
        row = dict(r)
        if cell is not None and r.get("status") == "ready":
            row["label_source"] = "manual+yaw"
            if cell["manual_yaw"] is not None:
                row["yaw"] = cell["manual_yaw"]
                row["bin"] = cell["manual_bin"]
            if cell["invalid"]:
                row["invalid_pose"] = True
                row["invalid_reason"] = cell["reason"]
        updated.append(row)
    (args.out_dir / "corpus-extra-v5.json").write_text(json.dumps(
        {"source": "Wikimedia Commons + ручная yaw-разметка (итерация 5)",
         "note": "Источник поз person_9/10/11: manual+yaw; кадры выше порога "
                 "invalid_pose помечены.", "people": payload["people"], "rows": updated},
        ensure_ascii=False, indent=1))

    print("frames", len(labeled), "valid", len(valid), "invalid", len(invalid))
    print("discrepancy(valid)", meta["discrepancy_valid"])
    for person, row in per_person.items():
        print(person, row)
    print("invalid:", [(x["person"], x["frame"], x["reason"].split(":")[0]) for x in invalid])
    print("artifacts in", args.out_dir)


if __name__ == "__main__":
    main()
