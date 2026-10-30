"""Общая инфраструктура итерации 5: кадры корпуса, значения пар, кластерный bootstrap.

Кадры и пары считаются один раз и кэшируются в .runtime/v5 — шаги 1, 2, 5, 6
должны видеть ровно тот же корпус, что и шаг 1, без повторного переизвлечения.
Профиль весов для `euclid + calibrated` читается из production-файла
reports/calibration/weights.json — того же, который читает приложение
(configs/runtime.yaml не трогается).

    cd /Users/victorkhudyakov/work/temp/atlas
    python scripts/v5_corpus.py --check
"""
from __future__ import annotations

import itertools
import json
import pickle
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

RUNTIME = ROOT / ".runtime"
CACHE = RUNTIME / "v5_frames.pkl"
PAIR_CACHE = RUNTIME / "v5_pairs.pkl"

LABELED = [f"person_{i:02d}" for i in range(1, 8)]
WILD = ["person_9", "person_10", "person_11"]
DEFAULT_GAP = 30

# Сравнение итерации 5: кандидат против baseline, обе метрики — euclid.
CANDIDATE = ("euclid", "calibrated")
BASELINE = ("euclid", "none")


def default_paths():
    sdcard = Path("/Volumes/SDCARD/photo/calibration_dataset")
    return {
        "calibration_root": sdcard / "calibration_datasets",
        "photos_root": sdcard / "photos",
        "per_person": 30,
        "gap": DEFAULT_GAP,
        "extra": ROOT / "reports/calibration/corpus-extra.json",
        "weights": ROOT / "reports/calibration/weights.json",
    }


def _signature(paths):
    """Отпечаток корпуса: любые правки в таблицах или кэше меняют его."""
    from server import storage

    db = storage.read_db()
    files = sorted(
        (p["id"], p["hash"]) for p in db["photos"] if not p.get("deleted_at")
    )
    return {
        "db": files,
        "extra_mtime": int(paths["extra"].stat().st_mtime_ns),
        "extra_rows": len(json.loads(paths["extra"].read_text())["rows"]),
        "index_mtime": int(paths["calibration_root"].joinpath(
            "all_calibration_index.csv").stat().st_mtime_ns),
        "per_person": paths["per_person"],
        "cache_model": storage.VERSION,
    }


def load_corpus(paths=None, *, refresh=False):
    """Кадры корпуса v4/v5 (10 человек) + пары within/between при зазоре gap.

    Кэш .runtime/v5_frames.pkl — локальный артефакт этого проекта, со своим
    отпечатком корпуса; при несовпадении отпечатка пересчитывается.
    """
    from calibration_check import ingest_and_process, select_frames
    from calibration_v3 import index_rows, load_frames, topology

    paths = {**default_paths(), **(paths or {})}
    sig = _signature(paths)
    if CACHE.exists() and not refresh:
        payload = pickle.loads(CACHE.read_bytes())
        if payload.get("signature") == sig:
            return payload["frames"], payload["within"], payload["between"]

    selected = select_frames(paths["calibration_root"] / "all_calibration_index.csv",
                            paths["photos_root"], paths["per_person"])
    index = index_rows(paths["calibration_root"] / "all_calibration_index.csv")
    extra = json.loads(paths["extra"].read_text())
    for row in extra["rows"]:
        if row.get("status") != "ready":
            continue
        selected.setdefault(row["person"], []).append({
            "frame": int(row["frame"]),
            "bin": row["bin"],
            "path": paths["photos_root"] / row["person"] / row["filename"],
            "id": row["id"],
            "label_source": "predicted",
        })
    for person in selected:
        selected[person].sort(key=lambda r: r["frame"])
    from corpus_v4 import load_extra

    _extra, extra_index, _skipped = load_extra(paths["extra"], paths["photos_root"])
    index.update(extra_index)

    targets, _proc = ingest_and_process(selected, False)
    tri, lm = topology()
    frames = load_frames(selected, index, tri, lm, {})
    from calibration_v3 import build_pairs

    within, between = build_pairs(frames, paths["gap"])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps(
        {"signature": sig, "frames": frames, "within": within, "between": between},
        protocol=4))
    return frames, within, between


def calibration_from_profile(path=None):
    """Профиль весов приложения (weights.json) как объект Calibration."""
    from server.heat import Calibration

    path = Path(path or default_paths()["weights"])
    return Calibration(json.loads(path.read_text()))


def person_subset(frames, within, between, people):
    """Те же пары, но только those людей; индексы в frames не меняются."""
    keep = set(people)
    sub = [(i, j) for i, j in within
           if frames[i]["person"] in keep and frames[j]["person"] in keep]
    others = [(i, j) for i, j in between
              if frames[i]["person"] in keep and frames[j]["person"] in keep]
    return sub, others


def pair_values(frames, pairs, tri, cal, *, cache_path=None, modes=("euclid", "weighted_euclid"),
                refresh=False):
    """Скалярные значения пары через единый helper server.heat.compute_heat_values.

    modes — имена из calibration_v3.MODES; cache_path даёт отдельные кэши для
    per-family профилей (шаг 1 LOTRO), чтобы не затирать глобальный.
    """
    from calibration_v3 import scalar, values_all

    modes = list(modes)
    path = Path(cache_path) if cache_path else PAIR_CACHE
    if path.exists() and not refresh:
        payload = pickle.loads(path.read_bytes())
        if (payload.get("modes") == modes and payload.get("n_pairs") == len(pairs)
                and payload.get("clip") == list(cal.payload.get("clip", []))):
            return payload["map"]
    acc = {m: [] for m in modes}
    for i, j in pairs:
        values = values_all(frames, i, j, tri, cal)
        for m in modes:
            acc[m].append(scalar(values[m], m, cal))
    out = {}
    keys = list(acc)
    for idx, (i, j) in enumerate(pairs):
        hit = tuple(float(acc[m][idx]) for m in keys)
        out[(i, j)] = out[(j, i)] = hit
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(
        {"map": out, "modes": keys, "n_pairs": len(pairs),
         "clip": list(cal.payload.get("clip", []))}, protocol=4))
    return out


def bootstrap_delta(frames, within, between, vmap, people, *, rounds=2000, seed=42):
    """Кластерный bootstrap ΔAUC(candidate) − ΔAUC(baseline): ресемплинг по людям.

    Кадры ресемплируются с возвращением внутри человека, пары строятся заново,
    поэтому зависимость пар одного человека попадает в разброс. Дельта считается
    на одних и тех же ресемплированных парах (парный bootstrap).
    """
    from calibration_sweep import auc

    by_person = {}
    for person in sorted(people):
        ids = [i for i, f in enumerate(frames)
               if f["person"] == person and f["order"] % 2 == 1 and f["valid"]]
        if len(ids) >= 2:
            by_person[person] = ids
    if len(by_person) < 2:
        return None
    rng = random.Random(seed)
    names = sorted(by_person)
    deltas = []
    for _ in range(rounds):
        chosen = [rng.choices(by_person[p], k=len(by_person[p])) for p in names]
        wv, bv = [], []
        for ch in chosen:
            for a, b in itertools.combinations(ch, 2):
                hit = vmap.get((a, b))
                if hit:
                    wv.append(hit)
        for p, q in itertools.combinations(range(len(chosen)), 2):
            for a in chosen[p]:
                for b in chosen[q]:
                    hit = vmap.get((a, b))
                    if hit:
                        bv.append(hit)
        if len(wv) < 10 or len(bv) < 10:
            continue
        base = auc([x for x, _ in wv], [x for x, _ in bv])
        cand = auc([y for _, y in wv], [y for _, y in bv])
        deltas.append(cand - base)
    if not deltas:
        return None
    arr = np.sort(np.asarray(deltas, np.float64))
    return {
        "n_people": len(names),
        "people": names,
        "rounds_requested": rounds,
        "rounds_used": int(arr.size),
        "seed": seed,
        "mean_delta_auc": round(float(arr.mean()), 4),
        "ci95": [round(float(arr[int(0.025 * arr.size)]), 4),
                 round(float(arr[int(0.975 * arr.size) - 1]), 4)],
        "p_positive": round(float((arr > 0).mean()), 4),
    }


def point_auc(frames, within, between, vmap, people):
    """Точечные AUC baseline и кандидата на парах выбранных людей (нечётные кадры)."""
    from calibration_sweep import auc

    keep = set(people)
    w = [vmap[(i, j)] for i, j in within
         if frames[i]["person"] in keep and frames[j]["person"] in keep and (i, j) in vmap]
    b = [vmap[(i, j)] for i, j in between
         if frames[i]["person"] in keep and frames[j]["person"] in keep and (i, j) in vmap]
    if len(w) < 10 or len(b) < 10:
        return None
    return {
        "n_within": len(w), "n_between": len(b),
        "auc_euclid": auc([x for x, _ in w], [x for x, _ in b]),
        "auc_weighted_euclid": auc([y for _, y in w], [y for _, y in b]),
        "delta_auc": round(auc([y for _, y in w], [y for _, y in b])
                           - auc([x for x, _ in w], [x for x, _ in b]), 4),
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    frames, within, between = load_corpus(refresh=args.refresh)
    tri, lm = None, None
    from calibration_v3 import topology

    tri, lm = topology()
    cal = calibration_from_profile()
    vmap = pair_values(frames, within + between, tri, cal, refresh=args.refresh)
    people = sorted({f["person"] for f in frames})
    print("frames", len(frames), "valid", sum(1 for f in frames if f["valid"]),
          "people", len(people))
    print("within", len(within), "between", len(between), "vmap", len(vmap) // 2)
    if args.check:
        print("point 10:", point_auc(frames, within, between, vmap, people))
        print("point 7:", point_auc(frames, within, between, vmap, LABELED))
