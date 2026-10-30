"""Шаг 5 итерации 5: фронтальный гейт при зазоре 30.

Гейт требует минимум 20 within-пар между фронтальными кадрами одного человека
при зазоре по номеру кадра >= 30 и минимум на 6 людях. В v4 при зазоре 30 была
1 пара (гейт не измерялся): дикие люди шли с предсказанными позами, а корпус
субсэмплирован до 30 кадров на человека.

Здесь:
  * позы person_9/10/11 берутся из ручной разметки шага 3 (manual+yaw),
    кадры шага 3 с invalid_pose исключаются;
  * считаются фронтальные within-пары при зазоре 30 и 10;
  * если пар >= 20 на >= 6 людях — считается гейт (среднее within-значение
    baseline euclid против кандидата euclid + calibrated);
  * иначе пишется «не измеряется» с фактическими числами.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python scripts/frontal_gate_v5.py

Артефакт: reports/calibration/frontal-gate-v5.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import v5_corpus as corpus  # noqa: E402


def apply_manual_labels(frames, labels_path, invalid_path):
    """Ставит manual yaw/bin диким людям и снимает кадры invalid_pose."""
    labels = json.loads(labels_path.read_text())["frames"]
    by = {(x["person"], x["frame"]): x for x in labels}
    invalid = {(x["person"], x["frame"]) for x in
               json.loads(invalid_path.read_text())["frames"]}
    for f in frames:
        key = (f["person"], f["frame"])
        cell = by.get(key)
        if cell is None:
            continue
        if key in invalid or cell["invalid"]:
            f["valid"] = False
            f["invalid_reason"] = cell["reason"] or "invalid_pose"
            continue
        if cell["manual_yaw"] is not None:
            f["yaw"] = float(cell["manual_yaw"])
            f["csv_yaw"] = float(cell["manual_yaw"])
            f["bin"] = cell["manual_bin"]
            f["label_source"] = "manual+yaw"
    return frames


def frontal_pairs(frames, gap):
    """Within-пары фронтальных нечётных кадров одного человека с зазором >= gap."""
    by_person = {}
    for i, f in enumerate(frames):
        if f["valid"] and f["order"] % 2 == 1 and f["bin"] == "frontal":
            by_person.setdefault(f["person"], []).append((f["frame"], i))
    pairs = []
    for person, items in by_person.items():
        items.sort()
        for (fa, ia), (fb, ib) in itertools.combinations(items, 2):
            if fb - fa >= gap:
                pairs.append((ia, ib))
    return pairs, {p: len(v) for p, v in by_person.items()}


def eval_pairs(frames, pairs, tri, cal):
    from calibration_v3 import scalar, values_all

    e, w = [], []
    for i, j in pairs:
        values = values_all(frames, i, j, tri, cal)
        e.append(scalar(values["euclid"], "euclid", cal))
        w.append(scalar(values["weighted_euclid"], "weighted_euclid", cal))
    return (round(float(np.mean(e)), 5), round(float(np.mean(w)), 5),
            round(100 * (float(np.mean(w)) / float(np.mean(e)) - 1), 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gap", type=int, default=30)
    ap.add_argument("--labels", type=Path,
                    default=ROOT / "reports/calibration/pose-labels-v5.json")
    ap.add_argument("--invalid", type=Path,
                    default=ROOT / "reports/calibration/invalid-frames-v5.json")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration/frontal-gate-v5.json")
    args = ap.parse_args()

    t0 = time.time()
    frames, within, between = corpus.load_corpus({"gap": args.gap})
    frames = apply_manual_labels(frames, args.labels, args.invalid)
    tri, _lm = _topology()
    cal = corpus.calibration_from_profile()

    need_pairs, need_people = 20, 6
    result = {"iteration": 5, "step": 5,
              "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "runtime_sec": round(time.time() - t0, 1),
              "requirement": {"min_pairs": need_pairs, "min_people": need_people,
                              "gap": args.gap},
              "pose_source_wild": "manual+yaw (шаг 3); invalid_pose кадры исключены"}

    for gap in (30, 10):
        pairs, per_person = frontal_pairs(frames, gap)
        people_with = sum(1 for v in per_person.values() if v >= 2)
        row = {"gap": gap, "n_pairs": len(pairs), "n_people_with_pairs": people_with,
               "frontal_frames_per_person": per_person}
        measurable = len(pairs) >= need_pairs and people_with >= need_people
        row["measurable"] = measurable
        if measurable:
            eu, we, delta = eval_pairs(frames, pairs, tri, cal)
            row.update({"euclid_within_mean": eu, "weighted_euclid_within_mean": we,
                        "delta_pct": delta})
            row["verdict"] = ("calibrated снижает within-разброс на фронтальных парах"
                              if delta < 0 else "calibrated не снижает within-разброс")
        else:
            row["verdict"] = "не измеряется"
            row["reason"] = (f"пар {len(pairs)} (<{need_pairs}) или людей {people_with} "
                             f"(<{need_people})")
        result[f"gate_gap{gap}"] = row
        print(f"gap {gap}: pairs {len(pairs)}, people_with_pairs {people_with}, "
              f"measurable {measurable}", {k: v for k, v in per_person.items()})

    g30 = result["gate_gap30"]
    result["gate"] = {
        "frontal_gate_measurable_at_gap30": bool(g30["measurable"]),
        "pairs_at_gap30": g30["n_pairs"],
        "people_at_gap30": g30["n_people_with_pairs"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    print("artifact", args.out)
    print("gate", json.dumps(result["gate"]))


def _topology():
    from calibration_v3 import topology

    return topology()


if __name__ == "__main__":
    main()
