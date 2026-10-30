"""Шаг 1 итерации 5: кластерный bootstrap CI для ΔAUC `euclid + calibrated`.

Сравнивает кандидат (`euclid + calibrated`) с baseline (`euclid + none`) на одних
и тех же парах. Ресемплинг по людям (не по кадрам): кадры одного человека зависимы,
поэтому внутри человека кадры берутся с возвращением, а пары строятся заново.
Значения пары считает `server.heat.compute_heat_values` — тот же helper, что и
в приложении; в браузере второй формулы нет.

Проверяются два среза: 10 человек корпуса и 7 размеченных, плюс те же ΔAUC
по LOTRO-семействам (frontal_light, light_mid, mid_deep, deep_profile) — для
семейств профиль пересобирается без этого семейства (leave-one-transition-out).

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python scripts/bootstrap_auc.py --rounds 2000

Артефакт: reports/calibration/bootstrap-v5.json
Гейт: нижняя граница CI ΔAUC больше 0 на 10 людях.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import v5_corpus as corpus  # noqa: E402

FAMILIES = ["frontal_light", "light_mid", "mid_deep", "deep_profile"]


def fast_auc(neg, pos):
    """AUC через Mann-Whitney со средними рангами по связям = sklearn roc_auc_score."""
    a = np.asarray(neg, np.float64)
    b = np.asarray(pos, np.float64)
    if a.size == 0 or b.size == 0:
        return None
    values = np.concatenate([a, b])
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, np.float64)
    ranks[order] = np.arange(1, values.size + 1, dtype=np.float64)
    _, inv, counts = np.unique(values, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=ranks)
    ranks = (sums / counts)[inv]
    return float((ranks[a.size:].sum() - b.size * (b.size + 1) / 2) / (a.size * b.size))


def bootstrap(frames, within, between, vmap, people, *, rounds, seed, min_pairs=10):
    """Кластерный bootstrap ΔAUC(candidate) − AUC(baseline) по людям."""
    by_person = {}
    for person in sorted(people):
        ids = [i for i, f in enumerate(frames)
               if f["person"] == person and f["order"] % 2 == 1 and f["valid"]]
        if len(ids) >= 2:
            by_person[person] = ids
    if len(by_person) < 2:
        return {"measurable": False,
                "reason": f"людей с ≥2 нечётными кадрами: {len(by_person)}"}
    names = sorted(by_person)
    rng = random.Random(seed)
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
        if len(wv) < min_pairs or len(bv) < min_pairs:
            continue
        base = fast_auc([x[0] for x in wv], [x[0] for x in bv])
        cand = fast_auc([x[1] for x in wv], [x[1] for x in bv])
        deltas.append(cand - base)
    if not deltas:
        return {"measurable": False, "reason": "ни одного ресемпла с достаточным числом пар"}
    arr = np.sort(np.asarray(deltas, np.float64))
    lo = float(arr[int(0.025 * arr.size)])
    hi = float(arr[int(0.975 * arr.size) - 1])
    return {
        "measurable": True,
        "n_people": len(names),
        "people": names,
        "rounds_requested": int(rounds),
        "rounds_used": int(arr.size),
        "seed": int(seed),
        "delta_auc_mean": round(float(arr.mean()), 4),
        "ci95_delta_auc": [round(lo, 4), round(hi, 4)],
        "p_positive": round(float((arr > 0).mean()), 4),
    }


def point_row(frames, within, between, vmap, people):
    """Точечные AUC на нечётных кадрах выбранных людей (то же определение, что в v4)."""
    keep = set(people)
    w = [vmap[(i, j)] for i, j in within if (i, j) in vmap
         and frames[i]["person"] in keep and frames[j]["person"] in keep]
    b = [vmap[(i, j)] for i, j in between if (i, j) in vmap
         and frames[i]["person"] in keep and frames[j]["person"] in keep]
    if len(w) < 10 or len(b) < 10:
        return {"measurable": False, "n_within": len(w), "n_between": len(b)}
    base = fast_auc([x[0] for x in w], [x[0] for x in b])
    cand = fast_auc([x[1] for x in w], [x[1] for x in b])
    return {
        "measurable": True,
        "n_within": len(w), "n_between": len(b),
        "auc_euclid_none": round(base, 4),
        "auc_euclid_calibrated": round(cand, 4),
        "delta_auc": round(cand - base, 4),
    }


def family_splits(frames, within, between):
    """within/between пары по LOTRO-семействам (без пропущенных переходов)."""
    from calibration_v3 import family_of

    out = {}
    for family in FAMILIES:
        wfam = [(i, j) for i, j in within
                if family_of(frames[i]["bin"], frames[j]["bin"]) == family]
        bfam = [(i, j) for i, j in between
                if family_of(frames[i]["bin"], frames[j]["bin"]) == family]
        out[family] = (wfam, bfam)
    return out


def run_families(frames, within, between, tri, cal, people, args, splits_tag):
    """Для каждого семейства: свой LOTRO-профиль, значения пар, bootstrap по людям."""
    from calibration_v3 import fit_noise

    out = {}
    for family, (wfam, bfam) in family_splits(frames, within, between).items():
        fam_people = sorted({frames[i]["person"] for i, _ in wfam}
                            & {frames[i]["person"] for i, _ in bfam})
        keep = [(i, j) for i, j in wfam if frames[i]["person"] in fam_people]
        entry = {"family": family, "n_within": len(keep), "n_between": len(bfam),
                 "n_people": len(fam_people)}
        if len(keep) < 10 or len(bfam) < 10 or len(fam_people) < 2:
            entry["measurable"] = False
            entry["reason"] = (f"пар within {len(keep)}, between {len(bfam)}, "
                               f"людей {len(fam_people)}")
            out[family] = entry
            print(f"{family}: не измеряется ({entry['reason']})", flush=True)
            continue
        sigma_e, sigma_n, n_pairs = fit_noise(frames, people, args.gap, exclude_family=family)
        fam_cal = _calibration(sigma_e, sigma_n)
        fam_map = corpus.pair_values(frames, keep + bfam, tri, fam_cal,
                                     cache_path=ROOT / f".runtime/v5_pairs_{family}.pkl",
                                     modes=("euclid", "weighted_euclid"),
                                     refresh=args.refresh)
        entry["sigma_pairs"] = n_pairs
        # Точечная ΔAUC: family within против family between (суженная выборка).
        entry["family_only"] = point_row(frames, keep, bfam, fam_map, fam_people)
        # Точечная ΔAUC в определении v4: family within против всего between на 10 людях.
        entry.update(point_row(frames, keep, between, fam_map, people))
        entry["bootstrap"] = bootstrap(frames, keep, bfam, fam_map, fam_people,
                                       rounds=args.rounds, seed=args.seed)
        boot = entry["bootstrap"]
        entry["delta_auc_lo"] = boot["ci95_delta_auc"][0] if boot.get("measurable") else None
        entry["gate_ci_lo_positive"] = bool(boot.get("measurable")
                                            and boot["ci95_delta_auc"][0] > 0)
        entry["gate_point_not_below_-0.005"] = bool(
            (entry.get("delta_auc") or -1) >= -0.005)
        out[family] = entry
        print(f"{family}: delta {entry.get('delta_auc')} "
              f"ci {boot.get('ci95_delta_auc')} people {len(fam_people)} "
              f"used {boot.get('rounds_used')}", flush=True)
    _ = splits_tag
    return out


def run_slices(frames, within, between, vmap, people, args):
    labeled = [p for p in corpus.LABELED if p in people]
    out = {}
    for name, cohort in (("all_10", people), ("labeled_7", labeled)):
        row = point_row(frames, within, between, vmap, cohort)
        boot = bootstrap(frames, within, between, vmap, cohort,
                         rounds=args.rounds, seed=args.seed)
        row.update({"bootstrap": boot,
                    "gate_ci_lo_positive": bool(boot.get("measurable")
                                                and boot["ci95_delta_auc"][0] > 0)})
        out[name] = row
        print(f"{name}: delta {row.get('delta_auc')} ci {boot.get('ci95_delta_auc')} "
              f"used {boot.get('rounds_used')}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--gap", type=int, default=corpus.DEFAULT_GAP)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--splits", default="slices,families",
                    help="прогоны: slices (10 и 7 людей), families (LOTRO)")
    ap.add_argument("--partial-dir", type=Path, default=ROOT / ".runtime/v5_bootstrap")
    ap.add_argument("--merge", action="store_true",
                    help="собрать итоговый JSON из partial-файлов и посчитать гейты")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "reports/calibration/bootstrap-v5.json")
    args = ap.parse_args()
    if args.rounds < 2000:
        print(f"warning: rounds={args.rounds} < 2000, результат не для гейта", flush=True)
    if args.merge:
        merge(args.out, args.partial_dir, args)
        return

    splits = {s.strip() for s in args.splits.split(",") if s.strip()}
    t0 = time.time()
    frames, within, between = corpus.load_corpus({"gap": args.gap}, refresh=args.refresh)
    tri, _lm = _topology()
    people = sorted({f["person"] for f in frames})
    cal = corpus.calibration_from_profile()
    vmap = corpus.pair_values(frames, within + between, tri, cal,
                              cache_path=corpus.PAIR_CACHE, refresh=args.refresh)
    print(f"corpus: frames {len(frames)}, within {len(within)}, between {len(between)}, "
          f"{len(people)} people, {time.time() - t0:.0f}s", flush=True)

    partial = {}
    if "slices" in splits:
        partial["slices"] = run_slices(frames, within, between, vmap, people, args)
    if "families" in splits:
        partial["lotro_families"] = run_families(frames, within, between, tri, cal,
                                                 people, args, splits)
    if not partial:
        return
    partial["meta"] = {"rounds": args.rounds, "seed": args.seed, "gap": args.gap,
                       "splits": sorted(splits),
                       "corpus": {"people": people, "frames": len(frames),
                                  "within": len(within), "between": len(between)}}
    args.partial_dir.mkdir(parents=True, exist_ok=True)
    tag = "_".join(sorted(splits))
    path = args.partial_dir / f"partial_{tag}.json"
    path.write_text(json.dumps(partial, ensure_ascii=False, indent=1, default=str))
    print("partial", path, f"{time.time() - t0:.0f}s", flush=True)
    merge(args.out, args.partial_dir, args)


def merge(out_path: Path, partial_dir: Path, args):
    """Собирает итоговый JSON из partial-файлов, пересчитывает точки по полному vmap."""
    partial_dir = Path(partial_dir)
    try:
        shown = str(partial_dir.resolve().relative_to(ROOT))
    except ValueError:
        shown = str(partial_dir)
    t0 = time.time()
    frames, within, between = corpus.load_corpus({"gap": args.gap})
    tri, _lm = _topology()
    people = sorted({f["person"] for f in frames})
    cal = corpus.calibration_from_profile()
    vmap = corpus.pair_values(frames, within + between, tri, cal)
    slices, families, rounds, seed = {}, {}, None, None
    for path in sorted(partial_dir.glob("partial_*.json")):
        payload = json.loads(path.read_text())
        rounds = rounds or payload["meta"]["rounds"]
        seed = seed or payload["meta"]["seed"]
        for name, value in payload.get("slices", {}).items():
            cohort = people if name == "all_10" else [p for p in corpus.LABELED if p in people]
            row = point_row(frames, within, between, vmap, cohort)
            row["bootstrap"] = value["bootstrap"]
            row["gate_ci_lo_positive"] = bool(
                value["bootstrap"].get("measurable")
                and value["bootstrap"]["ci95_delta_auc"][0] > 0)
            slices[name] = row
        for fam, value in payload.get("lotro_families", {}).items():
            families[fam] = value
    for fam in FAMILIES:
        families.setdefault(fam, {"family": fam, "measurable": False,
                                  "reason": "прогон не запускался"})
    measured = [v for v in families.values() if v.get("measurable")]
    mid_deep = families.get("mid_deep") or {}
    payload = {
        "iteration": 5,
        "step": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "partial_dir": shown,
        "runtime_sec": round(time.time() - t0, 1),
        "comparison": {"candidate": "euclid + calibrated", "baseline": "euclid + none"},
        "weighting_profile": str(corpus.default_paths()["weights"].relative_to(ROOT)),
        "resampling": "person-cluster bootstrap: кадры с возвращением внутри человека, "
                      "пары строятся заново, ΔAUC парный на одних ресемплированных парах",
        "seed": seed,
        "rounds_requested": rounds,
        "gap": args.gap,
        "space": "center + IOD (eye-contour means ldm68 36:42/42:48)",
        "auc_impl": "Mann-Whitney со средними рангами (равно sklearn roc_auc_score)",
        "corpus": {"people": people, "frames": len(frames),
                   "valid": sum(1 for f in frames if f["valid"]),
                   "within": len(within), "between": len(between)},
        "slices": slices,
        "lotro_families": families,
        "gates": {
            "ci_lo_positive_on_10": bool(slices.get("all_10", {}).get("gate_ci_lo_positive")),
            "lotro_families_ci_positive":
                f"{sum(1 for v in measured if v.get('gate_ci_lo_positive'))}/{len(measured)}",
            "lotro_families_point_positive":
                f"{sum(1 for v in measured if (v.get('delta_auc') or 0) > 0)}/{len(measured)}",
            "mid_deep_point_delta_not_below_-0.005":
                bool(mid_deep.get("gate_point_not_below_-0.005")),
            "mid_deep_ci_lo_above_-0.005": bool(
                mid_deep.get("measurable") and (mid_deep.get("delta_auc_lo") or -1) > -0.005),
            "rounds_at_least_2000": bool((rounds or 0) >= 2000),
        },
    }
    crosscheck(frames, within, between, vmap, payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    print("artifact", out_path, f"{time.time() - t0:.0f}s", flush=True)
    print("gates", json.dumps(payload["gates"]), flush=True)


def crosscheck(frames, within, between, vmap, payload):
    """Разовая сверка fast_auc со sklearn на полном корпусе."""
    from calibration_sweep import auc

    people = sorted({f["person"] for f in frames})
    row = point_row(frames, within, between, vmap, people)
    keep = set(people)
    w = [vmap[(i, j)] for i, j in within if (i, j) in vmap
         and frames[i]["person"] in keep and frames[j]["person"] in keep]
    b = [vmap[(i, j)] for i, j in between if (i, j) in vmap
         and frames[i]["person"] in keep and frames[j]["person"] in keep]
    sk_base = auc([x[0] for x in w], [x[0] for x in b])
    sk_cand = auc([x[1] for x in w], [x[1] for x in b])
    payload["auc_crosscheck"] = {
        "fast_auc": [row["auc_euclid_none"], row["auc_euclid_calibrated"]],
        "sklearn_auc": [sk_base, sk_cand],
        "max_abs_diff": round(max(abs(row["auc_euclid_none"] - sk_base),
                                  abs(row["auc_euclid_calibrated"] - sk_cand)), 6),
    }


def _topology():
    from calibration_v3 import topology

    return topology()


def _calibration(sigma_e, sigma_n):
    from calibration_v3 import calibration

    return calibration(sigma_e, sigma_n)


if __name__ == "__main__":
    main()
