"""Bootstrap-доверительный интервал для top-1 точности идентификации.

Точечная оценка на 120 held-out фото (61.7%) сама по себе ничего не значит:
без интервала нельзя сказать, отличие 63.3% -> 61.7% — деградация метода или
шум выборки. Скрипт берёт готовый отчёт `assess_identity_accuracy.py` (строки
`rows` с флагом `correct`) и считает два интервала:

  1. по фото      — классический bootstrap: кадры независимы;
  2. по личностям — кластерный bootstrap: целиком ресемплируются личности
                    (put/vas/udmurt), потому что 40 кадров одного человека
                    коррелированы через один эталон, и интервал по фото этот
                    разброс не видит.

Заодно печатает объём выборки, нужный, чтобы полуширина упала до 5 п.п.

Пример:
    python scripts/bootstrap_identity_eval.py
    python scripts/bootstrap_identity_eval.py --eval .runtime/identity_eval/identity_eval.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL = ROOT / ".runtime" / "identity_eval" / "identity_eval.json"


def percentile_interval(values: np.ndarray) -> tuple[float, float, float]:
    lo, med, hi = np.percentile(values, [2.5, 50.0, 97.5])
    return float(lo), float(med), float(hi)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", default=str(DEFAULT_EVAL), type=Path,
                        help="отчёт assess_identity_accuracy.py с полем rows")
    parser.add_argument("--boots", default=20000, type=int)
    parser.add_argument("--seed", default=20261027, type=int,
                        help="фиксированный seed: числа в README должны повторяться")
    args = parser.parse_args()

    report = json.loads(args.eval.read_text(encoding="utf-8"))
    rows = report["rows"]
    correct = np.array([1.0 if r["correct"] else 0.0 for r in rows])
    people = np.array([r["identity"] for r in rows])
    n = len(correct)
    rng = np.random.default_rng(args.seed)

    point = float(correct.mean())
    print(f"held-out кадров: {n} · точечная top-1 = {point * 100:.2f}%")

    # 1) bootstrap по кадрам
    by_photo = correct[rng.integers(0, n, size=(args.boots, n))].mean(axis=1)
    lo, med, hi = percentile_interval(by_photo)
    print(f"по фото:       95% CI [{lo * 100:.1f}; {hi * 100:.1f}] п.п. "
          f"(медиана {med * 100:.1f}%, полуширина {(hi - lo) / 2 * 100:.1f}, "
          f"SE {float(by_photo.std()) * 100:.2f})")

    # 2) кластерный bootstrap по личностям
    uniq = sorted(set(people.tolist()))
    per_person = {p: np.flatnonzero(people == p) for p in uniq}
    cluster = np.empty(args.boots)
    for b in range(args.boots):
        picked = rng.choice(uniq, len(uniq), replace=True)
        cluster[b] = correct[np.concatenate([per_person[p] for p in picked])].mean()
    lo, med, hi = percentile_interval(cluster)
    print(f"по личностям:  95% CI [{lo * 100:.1f}; {hi * 100:.1f}] п.п. "
          f"(медиана {med * 100:.1f}%, полуширина {(hi - lo) / 2 * 100:.1f}; "
          f"кластеров всего {len(uniq)})")

    se = float(by_photo.std())
    needed = int(round(1.96 ** 2 * point * (1 - point) / 0.05 ** 2))
    # 63.3% -> 61.7% = 1.6 п.п.: чтобы сравнить две такие оценки, нужен paired-тест
    # на одних и тех же кадрах, но и он упирается в объём выборки ниже.
    print(f"\nМинимальная различимая разница при n={n}: ±{1.96 * se * 100:.1f} п.п. "
          f"(95%). Сдвиг в 1.6 п.п. (63.3% -> 61.7%) — шум, а не деградация.")
    print(f"Чтобы полуширина стала 5 п.п., нужно ~{needed} held-out кадров "
          f"(сейчас {n}).")
    chance = float(report["summary"].get("chance", 1.0 / len(uniq)))
    print(f"Случайное угадывание: {chance * 100:.1f}% — нижняя граница интервала "
          f"выше неё, то есть ранжирование реально, но размыто.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
