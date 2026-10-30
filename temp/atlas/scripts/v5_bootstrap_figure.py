"""Рисунок шага 1: bootstrap CI для ΔAUC (euclid+calibrated против euclid+none).

Читает reports/calibration/bootstrap-v5.json и рисует точечную ΔAUC с 95% CI
для двух срезов (10 людей, 7 размеченных) и четырёх LOTRO-семейств. Порог
гейта — нижняя граница CI больше 0 на 10 людях. Ничего не пересчитывает.

    cd /Users/victorkhudyakov/work/temp/atlas
    python scripts/v5_bootstrap_figure.py

Артефакт: reports/figures/v5-bootstrap-auc.png
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports/calibration/bootstrap-v5.json"
OUT = ROOT / "reports/figures/v5-bootstrap-auc.png"


def main():
    d = json.loads(SRC.read_text())
    rows = []
    s = d["slices"]["all_10"]
    rows.append(("10 людей", s["delta_auc"], s["bootstrap"]["ci95_delta_auc"],
                 s["gate_ci_lo_positive"]))
    s = d["slices"]["labeled_7"]
    rows.append(("7 размеченных", s["delta_auc"], s["bootstrap"]["ci95_delta_auc"],
                 s["gate_ci_lo_positive"]))
    for fam in ("frontal_light", "light_mid", "mid_deep", "deep_profile"):
        f = d["lotro_families"][fam]
        ci = f.get("bootstrap", {}).get("ci95_delta_auc")
        rows.append((f"LOTRO {fam}", f["delta_auc"], ci,
                     f.get("gate_ci_lo_positive", False)))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [r[0] for r in rows]
    pts = [r[1] for r in rows]
    lo = [r[1] - r[2][0] if r[2] else 0 for r in rows]
    hi = [r[2][1] - r[1] if r[2] else 0 for r in rows]
    colors = ["#5bd7bb" if r[3] else ("#e05c5c" if r[1] < -0.005 else "#e8b76d")
              for r in rows]
    y = range(len(rows))
    fig, ax = plt.subplots(figsize=(8.2, 4.4), dpi=130)
    ax.errorbar(pts, y, xerr=[lo, hi], fmt="none", ecolor="#8a97a3", capsize=4, lw=1.4)
    ax.scatter(pts, y, c=colors, s=60, zorder=3)
    ax.axvline(0, color="black", lw=0.8)
    ax.axvline(-0.005, color="#e05c5c", lw=0.8, ls=":", label="порог mid_deep −0.005")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("ΔAUC (euclid + calibrated − euclid + none) с 95% CI, ресемплинг по людям")
    ax.set_title("Итерация 5, шаг 1: bootstrap ΔAUC (seed=42, ≥2000 повторов)", fontsize=11)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    plt.close(fig)
    print("figure", OUT)


if __name__ == "__main__":
    main()
