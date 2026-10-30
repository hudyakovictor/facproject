"""Шаг 6 итерации 5: устойчивость весов на независимых половинах людей.

В v4 веса между корпусами менялись на 27% по медиане |Δw|, у 5% вершин значения
лежали на границах clip. Здесь веса считаются на двух независимых половинах
людей корпуса; делается 5 случайных разбиений (seed фиксирован). Для каждого
разбиения пишутся:

  * медиана |Δw| между весами двух половин (относительно, как в v4);
  * доля вершин на границах clip (нижней/верхней) в каждой половине;
  * ΔAUC на отложенной половине: профиль с обучением на половине A, оценка на
    половине B (within-пары B против between B↔A), кандидат euclid+calibrated
    против baseline euclid.

Гейт для weights-v4.json: медиана |Δw| <= 10%, доля на границах clip <= 1%,
ΔAUC > 0 в 5 из 5 разбиений. Иначе файл остаётся неподключённым.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python scripts/weights_stability_v5.py

Артефакты: reports/calibration/weights-stability-v5.json,
           reports/figures/v5-weights-stability.png
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

GATE_MEDIAN = 0.10
GATE_CLIP_PCT = 1.0


def weights_from_sigma(sigma, clip):
    s = np.clip(np.asarray(sigma, np.float64), clip[0], clip[1])
    return 1.0 / np.maximum(s, 1e-12), s


def half_metrics(frames, within, between, tri, gap, train, holdout):
    """Профиль на train, ΔAUC на holdout; веса и доли на границах clip для train."""
    from calibration_sweep import auc
    from calibration_v3 import calibration, calibration_payload, collect, fit_noise

    sigma_e, sigma_n, n_pairs = fit_noise(frames, train, gap)
    cal = calibration(sigma_e, sigma_n)
    payload = calibration_payload(sigma_e, sigma_n)
    w, s = weights_from_sigma(payload["sigma"], payload["clip"])
    lo, hi = payload["clip"]
    at_lower = 100 * float((s <= lo + 1e-12).mean())
    at_upper = 100 * float((s >= hi - 1e-12).mean())

    hold = set(holdout)
    train_set = set(train)
    odd_in = lambda p: [i for i, f in enumerate(frames)
                        if f["person"] == p and f["order"] % 2 == 1 and f["valid"]]
    hold_idx = {i for p in holdout for i in odd_in(p)}
    other_idx = {i for p in train for i in odd_in(p)}
    within_h = [(i, j) for i, j in within if i in hold_idx and j in hold_idx]
    between_h = [(i, j) for i, j in between
                 if (i in hold_idx and j in other_idx) or (j in hold_idx and i in other_idx)]
    acc, _ = collect(frames, within_h + between_h, tri, cal, None)
    e_w = np.asarray(acc["euclid"]["scalar"][: len(within_h)])
    e_b = np.asarray(acc["euclid"]["scalar"][len(within_h):])
    w_w = np.asarray(acc["weighted_euclid"]["scalar"][: len(within_h)])
    w_b = np.asarray(acc["weighted_euclid"]["scalar"][len(within_h):])
    auc_base = auc(e_w, e_b)
    auc_cand = auc(w_w, w_b)
    _ = train_set
    return {
        "train": sorted(train), "holdout": sorted(holdout), "sigma_pairs": n_pairs,
        "n_within_hold": len(within_h), "n_between_hold": len(between_h),
        "clip": [round(lo, 6), round(hi, 6)],
        "at_lower_pct": round(at_lower, 2), "at_upper_pct": round(at_upper, 2),
        "at_bounds_pct": round(at_lower + at_upper, 2),
        "auc_euclid": auc_base, "auc_weighted_euclid": auc_cand,
        "delta_auc": round(auc_cand - auc_base, 4),
        "_weights": w, "_sigma": s,
    }


def relative_median(wa, wb):
    rel = np.abs(wb - wa) / np.maximum(wa, 1e-12)
    return round(float(np.median(rel)), 4)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gap", type=int, default=corpus.DEFAULT_GAP)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "reports/calibration/weights-stability-v5.json")
    ap.add_argument("--figure", type=Path, default=ROOT / "reports/figures/v5-weights-stability.png")
    args = ap.parse_args()

    t0 = time.time()
    frames, within, between = corpus.load_corpus({"gap": args.gap})
    tri, _lm = _topology()
    people = sorted({f["person"] for f in frames})
    half = len(people) // 2
    rng = random.Random(args.seed)

    runs = []
    medians = []
    for k in range(args.splits):
        perm = people[:]
        rng.shuffle(perm)
        train, holdout = perm[:half], perm[half:]
        a = half_metrics(frames, within, between, tri, args.gap, train, holdout)
        b = half_metrics(frames, within, between, tri, args.gap, holdout, train)
        median_dw = relative_median(a["_weights"], b["_weights"])
        at_bounds = max(a["at_bounds_pct"], b["at_bounds_pct"])
        run = {
            "split": k, "seed": args.seed,
            "half_A": sorted(train), "half_B": sorted(holdout),
            "median_abs_dw_rel": median_dw,
            "at_bounds_pct_A": a["at_bounds_pct"], "at_bounds_pct_B": b["at_bounds_pct"],
            "at_bounds_pct_max": round(at_bounds, 2),
            "delta_auc_B_on_A_profile": a["delta_auc"],
            "delta_auc_A_on_B_profile": b["delta_auc"],
            "auc_base_B": a["auc_euclid"], "auc_cand_B": a["auc_weighted_euclid"],
            "auc_base_A": b["auc_euclid"], "auc_cand_A": b["auc_weighted_euclid"],
        }
        runs.append(run)
        medians.append(median_dw)
        print(f"split {k}: median|dw| {median_dw:.3f}, at_bounds {at_bounds:.1f}%, "
              f"ΔAUC B|A {a['delta_auc']:+.4f}, A|B {b['delta_auc']:+.4f}", flush=True)

    pos = sum(1 for r in runs
              if r["delta_auc_B_on_A_profile"] > 0 and r["delta_auc_A_on_B_profile"] > 0)
    median_of_medians = round(float(np.median(medians)), 4)
    max_bounds = round(max(r["at_bounds_pct_max"] for r in runs), 2)
    gate = {
        "median_abs_dw_le_10pct": bool(median_of_medians <= GATE_MEDIAN),
        "at_bounds_le_1pct": bool(max_bounds <= GATE_CLIP_PCT),
        "delta_auc_positive_5_of_5": bool(pos >= args.splits),
        "median_of_medians": median_of_medians,
        "max_at_bounds_pct": max_bounds,
        "splits_with_both_delta_auc_positive": f"{pos}/{args.splits}",
    }
    gate["weights_v4_connect_allowed"] = bool(
        gate["median_abs_dw_le_10pct"] and gate["at_bounds_le_1pct"]
        and gate["delta_auc_positive_5_of_5"])
    payload = {
        "iteration": 5, "step": 6,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runtime_sec": round(time.time() - t0, 1),
        "gap": args.gap, "seed": args.seed, "n_splits": args.splits,
        "people": people,
        "method": "веса 1/clip(sigma) на двух независимых половинах людей; "
                  "медиана |Δw| относительно; ΔAUC на отложенной половине",
        "runs": runs,
        "gates": gate,
        "decision": ("weights-v4.json можно подключать"
                     if gate["weights_v4_connect_allowed"]
                     else "weights-v4.json остаётся неподключённым"),
    }
    figure(runs, args.figure, median_of_medians, max_bounds)
    payload["figure"] = str(args.figure.relative_to(ROOT))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    print("gates", json.dumps(gate))
    print("artifact", args.out)


def figure(runs, out_path, median_of_medians, max_bounds):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    idx = [r["split"] for r in runs]
    med = [r["median_abs_dw_rel"] for r in runs]
    bounds = [r["at_bounds_pct_max"] for r in runs]
    dauc = [r["delta_auc_B_on_A_profile"] for r in runs]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8), dpi=130)
    axes[0].bar(idx, med, color="#e8b76d")
    axes[0].axhline(GATE_MEDIAN, color="#e05c5c", ls="--", label="порог 10%")
    axes[0].set_title(f"медиана |Δw| (медиана {median_of_medians:.1%})", fontsize=10)
    axes[0].set_xlabel("разбиение")
    axes[0].legend(fontsize=8)
    axes[1].bar(idx, bounds, color="#7dbff0")
    axes[1].axhline(GATE_CLIP_PCT, color="#e05c5c", ls="--", label="порог 1%")
    axes[1].set_title(f"вершины на границах clip (max {max_bounds:.1f}%)", fontsize=10)
    axes[1].set_xlabel("разбиение")
    axes[1].legend(fontsize=8)
    axes[2].bar(idx, dauc, color=["#5bd7bb" if d > 0 else "#e05c5c" for d in dauc])
    axes[2].axhline(0, color="black", lw=0.8)
    axes[2].set_title("ΔAUC на отложенной половине (B|A)", fontsize=10)
    axes[2].set_xlabel("разбиение")
    for ax in axes:
        ax.tick_params(labelsize=8)
    fig.suptitle("Устойчивость весов: 5 разбиений пополам", fontsize=11)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def _topology():
    from calibration_v3 import topology

    return topology()


if __name__ == "__main__":
    main()
