"""ABA-null: сырой (364) и high-Z гейтированный (воспроизводимо, в ветке).

H0: метки кластеров случайно фликкерят -> число A-B-A не выше permutation.
high-Z версия: переход засчитывается, только если через границу есть
matched-пара Z>4 (иначе это шум метки, а не событие).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path(os.environ.get("FAC_WORK", "/Users/victorkhudyakov/work"))
AN = WORK / "analyst_v25"


def count_aba(lab):
    return sum(1 for i in range(len(lab) - 2)
               if lab[i] != lab[i + 1] and lab[i + 1] != lab[i + 2] and lab[i] == lab[i + 2])


def main():
    rng = np.random.default_rng(11)
    ev = pd.read_csv(AN / "events.csv").sort_values("date").reset_index(drop=True)
    lab = ev["cluster2"].to_numpy()
    obs = count_aba(lab)
    null = np.array([count_aba(rng.permutation(lab)) for _ in range(1000)])
    print(f"ABA raw: obs={obs} null med={np.median(null):.0f} p95={np.quantile(null, .95):.0f} "
          f"p={(null >= obs).mean():.3f} -> R0", flush=True)
    # high-Z гейтированный: границы с опорой на matched Z>4
    pa = pd.read_csv(AN / "matched_pairs.csv")
    hi = pa[pa.z_corrected > 4]
    bydate = {}
    for _, r in hi.iterrows():
        bydate.setdefault(r["date_a"], set()).add(r["date_b"])
        bydate.setdefault(r["date_b"], set()).add(r["date_a"])
    dates = ev["date"].to_numpy()
    gated = 0
    for i in range(len(dates) - 2):
        a, b, c = dates[i], dates[i + 1], dates[i + 2]
        if lab[i] != lab[i + 1] and lab[i + 1] != lab[i + 2] and lab[i] == lab[i + 2]:
            if b in bydate.get(a, set()) or c in bydate.get(b, set()):
                gated += 1
    # null для гейтированного: те же границы, метки переставлены
    nullg = []
    for _ in range(1000):
        lp = rng.permutation(lab)
        k = 0
        for i in range(len(dates) - 2):
            a, b, c = dates[i], dates[i + 1], dates[i + 2]
            if lp[i] != lp[i + 1] and lp[i + 1] != lp[i + 2] and lp[i] == lp[i + 2]:
                if b in bydate.get(a, set()) or c in bydate.get(b, set()):
                    k += 1
        nullg.append(k)
    nullg = np.array(nullg)
    print(f"ABA high-Z gated: obs={gated} null med={np.median(nullg):.0f} "
          f"p95={np.quantile(nullg, .95):.0f} p={(nullg >= gated).mean():.3f}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
