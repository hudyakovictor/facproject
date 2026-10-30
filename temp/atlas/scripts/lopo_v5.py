"""Шаг 2 итерации 5: LOPO без предсказанных поз (7 размеченных против 10).

Повторяет leave-one-person-out на двух когортах с одинаковыми параметрами:
7 размеченных (person_01..07, `manual+yaw`) и все 10 (добавляются wild
person_9/10/11 с `predicted` позами). Профиль на каждом фолде пересобирается
по чётным кадрам остальных людей когорты, оценка — на нечётных кадрах
held-out человека. Сравнивает режимы `normal`, `weighted_euclid`,
`weighted_normal` против baseline `euclid`.

Значения пары считает `server.heat.compute_heat_values` (calibration_v3.collect).

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python scripts/lopo_v5.py

Артефакты: reports/calibration/lopo-v5.json, reports/figures/v5-lopo-7vs10.png
Гейт: weighted_euclid выигрывает не меньше 5 из 7; минимум ΔAUC не хуже −0.02.
"""
from __future__ import annotations

import argparse
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

MODE_NAMES = ["euclid", "normal", "weighted_euclid", "weighted_normal"]
CANDIDATES = ["normal", "weighted_euclid", "weighted_normal"]


def lopo_cohort(frames, within, between, tri, lm, gap, cohort):
    """LOPO по людям когорты: sigma по чётным кадрам остальных, оценка на held-out."""
    from calibration_v3 import MODES, calibration, collect, fit_noise
    from calibration_sweep import auc

    rows = []
    for person in cohort:
        others = [p for p in cohort if p != person]
        sigma_e, sigma_n, pairs = fit_noise(frames, others, gap)
        cal = calibration(sigma_e, sigma_n)
        mine = {i for i, f in enumerate(frames)
                if f["person"] == person and f["order"] % 2 == 1 and f["valid"]}
        others_idx = {i for i, f in enumerate(frames)
                      if f["person"] in others and f["order"] % 2 == 1 and f["valid"]}
        within_mine = [(i, j) for i, j in within if i in mine and j in mine]
        between_mine = [(i, j) for i, j in between
                        if (i in mine and j in others_idx) or (j in mine and i in others_idx)]
        if len(within_mine) < 10 or len(between_mine) < 10:
            rows.append({"person": person, "skipped": True,
                         "n_within": len(within_mine), "n_between": len(between_mine)})
            continue
        acc, _ = collect(frames, within_mine + between_mine, tri, cal, lm)
        row = {"person": person, "sigma_pairs": pairs,
               "n_within": len(within_mine), "n_between": len(between_mine)}
        for name, _metric, _weighting in MODES:
            wv = np.asarray(acc[name]["scalar"][: len(within_mine)])
            bv = np.asarray(acc[name]["scalar"][len(within_mine):])
            row[f"auc_{name}"] = auc(wv, bv)
        for name in CANDIDATES:
            row[f"delta_{name}"] = round(row[f"auc_{name}"] - row["auc_euclid"], 4)
        rows.append(row)
    scored = [r for r in rows if not r.get("skipped")]
    out = {"rows": rows, "n": len(scored)}
    for name in CANDIDATES:
        deltas = [r[f"delta_{name}"] for r in scored]
        out[name] = {
            "wins": int(sum(d > 0 for d in deltas)),
            "n": len(deltas),
            "mean_delta_auc": round(float(np.mean(deltas)), 4),
            "min_delta_auc": round(float(np.min(deltas)), 4),
        }
    return out


def figure(cohort7, cohort10, out_path: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    people = sorted({r["person"] for r in cohort10["rows"] if not r.get("skipped")})
    a7 = {r["person"]: r for r in cohort7["rows"]}
    a10 = {r["person"]: r for r in cohort10["rows"]}
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.2), dpi=130)
    for ax, tag, data in ((axes[0], "7 размеченных (manual+yaw)", a7),
                          (axes[1], "10 людей (+3 predicted)", a10)):
        x = np.arange(len(people))
        e = [data.get(p, {}).get("auc_euclid", np.nan) for p in people]
        w = [data.get(p, {}).get("auc_weighted_euclid", np.nan) for p in people]
        ax.bar(x - 0.2, e, 0.4, label="euclid", color="#7dbff0")
        ax.bar(x + 0.2, w, 0.4, label="euclid + calibrated", color="#5bd7bb")
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace("person_", "p") for p in people],
                           rotation=45, ha="right", fontsize=8)
        ax.set_ylim(0.4, 1.0)
        ax.set_title(tag, fontsize=10)
        ax.set_ylabel("AUC (held-out person)", fontsize=9)
        ax.legend(fontsize=8)
    fig.suptitle("LOPO: euclid против euclid + calibrated", fontsize=11)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gap", type=int, default=corpus.DEFAULT_GAP)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration/lopo-v5.json")
    ap.add_argument("--figure", type=Path, default=ROOT / "reports/figures/v5-lopo-7vs10.png")
    args = ap.parse_args()

    t0 = time.time()
    frames, within, between = corpus.load_corpus({"gap": args.gap})
    tri, lm = _topology()
    people = sorted({f["person"] for f in frames})
    labeled = [p for p in corpus.LABELED if p in people]
    cohort7 = lopo_cohort(frames, within, between, tri, lm, args.gap, labeled)
    cohort10 = lopo_cohort(frames, within, between, tri, lm, args.gap, people)
    print(f"cohort7 weighted_euclid: {cohort7['weighted_euclid']}")
    print(f"cohort10 weighted_euclid: {cohort10['weighted_euclid']}")

    we7 = cohort7["weighted_euclid"]
    we10 = cohort10["weighted_euclid"]
    wn7 = cohort7["weighted_normal"]
    wn10 = cohort10["weighted_normal"]
    payload = {
        "iteration": 5, "step": 2,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runtime_sec": round(time.time() - t0, 1),
        "gap": args.gap, "seed": args.seed,
        "note": "LOPO профиль пересобирается на остальных людях когорты; "
                "в когорте из 7 дикие predicted-люди не участвуют ни в обучении, ни в оценке.",
        "modes_compared": ["normal", "weighted_euclid", "weighted_normal"],
        "labeled_source": "manual+yaw (person_01..07)",
        "predicted_source": "predicted (person_9/10/11)",
        "cohort_7_labeled": cohort7,
        "cohort_10_all": cohort10,
        "comparison": {
            "weighted_euclid": {
                "wins_7": we7["wins"], "wins_10": we10["wins"],
                "min_delta_7": we7["min_delta_auc"], "min_delta_10": we10["min_delta_auc"],
                "mean_delta_7": we7["mean_delta_auc"], "mean_delta_10": we10["mean_delta_auc"],
            },
            "weighted_normal": {
                "wins_7": wn7["wins"], "wins_10": wn10["wins"],
                "min_delta_7": wn7["min_delta_auc"], "min_delta_10": wn10["min_delta_auc"],
            },
        },
        "gates": {
            "weighted_euclid_wins_at_least_5_of_7": bool(we7["wins"] >= 5),
            "weighted_euclid_min_delta_not_worse_than_-0.02": bool(we7["min_delta_auc"] >= -0.02),
        },
        "interpretation": _interpret(we7, we10),
    }
    figure(cohort7, cohort10, args.figure)
    payload["figure"] = str(args.figure.relative_to(ROOT))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    print("gates", json.dumps(payload["gates"]))
    print("artifact", args.out)


def _interpret(we7, we10):
    better7 = we7["min_delta_auc"] > we10["min_delta_auc"] + 0.005
    if better7 and we7["wins"] >= 5:
        return ("На 7 размеченных weighted_euclid заметно стабильнее, чем на 10 "
                f"(мин ΔAUC {we7['min_delta_auc']:+.4f} против {we10['min_delta_auc']:+.4f}): "
                "просадка на 10 людях объясняется шумом предсказанных поз wild-людей. "
                "Шаг 3 (разметка person_9/10/11) релевантен.")
    return (f"На 7 размеченных результат сопоставим с 10 людьми "
            f"(мин ΔAUC {we7['min_delta_auc']:+.4f} против {we10['min_delta_auc']:+.4f}): "
            "дело в методе, а не в шуме поз. Шаг 3 не блокирует вывод.")


def _topology():
    from calibration_v3 import topology

    return topology()


if __name__ == "__main__":
    main()
