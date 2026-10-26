"""T8 в абсолютных единицах: минимальная видимая добавка без процентов-артефактов.

Проблема прошлой версии: проценты для метрик с нулём в знаменателе (асимметрии) —
артефакт, а статистика `|own*(1+s) - ref|` немонотонна (кадры со шириной НИЖЕ
эталона при добавке становятся БЛИЖЕ к эталону). Здесь readout парный: одно и то же
множество наклонных кадров до/после добавки, сдвиг знаковый.

Порог «сколько кадров нужно» считается не формулой (t/Δ)², а блок-бутстрапом по
наклонным кадрам одного человека в порядке индексов: (t/Δ)² предполагает независимый
шум, а по T7 остаток ракурса зависит от yaw систематически, поэтому усреднение кадров
одной стороны его не убирает. Блок (L кадров подряд) сохраняет автокорреляцию прогона;
отношение SE_block / SE_iid даёт коэффициент оптимизма прошлой цифры.

Единицы: общие с advisor_tests.load() — canon нормирован по max-radius=1 по 106 точкам,
v17 пересчитан из этих же canon (одна нормировка на облака и метрики). Для читаемости
всё продублировано в долях IPD (eye_anchor_spacing_3d ровного эталона) и в мм при
допущении IPD = 63 мм.

Запуск: PYTHONPATH=/Users/victorkhudyakov/work python app9/validation/t8_absolute.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
IPD_MM = 63.0                      # грубое допущение только для читаемости чисел
ALAR_L, ALAR_R = 58, 62
BLOCK_L = 5                        # длина блока: кадр прогона скоррелирован с ~5 соседями
N_BOOT = 2000
RNG = np.random.default_rng(20261026)

from advisor_tests import level_set, load  # noqa: E402  (общая загрузка, отбор ровных кадров, единицы)
from morphing.backend import identity as I  # noqa: E402


def rsd(v: np.ndarray) -> float:
    """Робастное СКО = 1.4826 * MAD."""
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if v.size < 3:
        return float("nan")
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


def splits(rows: list[dict]) -> tuple[dict, dict]:
    """person -> (level, tilted) по фронтальному бину, отбор кадров как в advisor_tests."""
    people = sorted({r["person"] for r in rows})
    lvl, tilt = {}, {}
    for p in people:
        rs = [r for r in rows if r["person"] == p and r["bin"] == "frontal"]
        L = level_set(rs)
        kept = {id(r) for r in L}
        lvl[p], tilt[p] = L, [r for r in rs if abs(r["tilt"]) > 2.0 and id(r) not in kept]
    return lvl, tilt


def boot_se(x: np.ndarray, n: int, nboot: int = N_BOOT) -> tuple[float, float, int]:
    """(SE_block, SE_iid, L) среднего по n кадрам прогоновой серии x.

    SE_block - circular block bootstrap: берём блоки по L подряд идущих кадров, поэтому
    автокорреляция прогона сохраняется. L ограничиваем m//2, иначе при коротком прогоне
    один блок = вся серия и SE вырождается в ноль. SE_iid = sigma/sqrt(n) - прежняя
    формула, которая трактует остаток ракурса как независимый шум.
    """
    m = x.size
    if m < 2 or n < 1:
        return float("nan"), float("nan"), 0
    block = max(1, min(BLOCK_L, m // 2))
    nb = int(math.ceil(n / block))
    starts = RNG.integers(0, m, size=(nboot, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(nboot, nb * block) % m
    se_b = float(np.std(x[idx[:, :n]].mean(axis=1), ddof=1))
    se_i = float(np.std(x, ddof=1)) / math.sqrt(n)
    return se_b, se_i, block


def units(x: float, ipd: float) -> str:
    return f"{x:.5f}  ({100 * x / ipd:5.2f}% IPD = {IPD_MM * x / ipd:5.2f} мм)"


def side_series(rows_p: list[dict], ref: float, i: int) -> list[tuple[str, np.ndarray]]:
    """Остатки наклонных кадров одной стороны, в порядке индекса кадра: [(сторона, x), ...].

    Стороны разделяем, потому что по T7 остаток метрики зависит от yaw систематически:
    средняя по n кадрам одной стороны сходится НЕ нулю, а к биасу этой стороны.
    """
    out = []
    for side, sgn in (("left", 1.0), ("right", -1.0)):
        rs = sorted((r for r in rows_p if sgn * r["tilt"] > 2.0), key=lambda r: r["fidx"])
        x = np.array([r["v17"][i] - ref for r in rs], float)
        x = x[np.isfinite(x)]
        if x.size >= 3:
            out.append((side, x))
    return out


def side_stats(x: np.ndarray, ns: tuple[int, ...]) -> dict:
    """По одной стороне наклонных кадров: биас, SE_block и SE_iid по сетке n."""
    st = {"n": int(x.size), "bias": abs(float(np.median(x))), "sd": float(np.std(x, ddof=1)),
          "block": {}, "iid": {}, "L": 0}
    for n in ns:
        sb, si, block = boot_se(x, n)
        st["block"][n], st["iid"][n], st["L"] = sb, si, block
    return st


def n_needed(bias: float, se: dict, gap: float, big: int = 2000) -> int | None:
    """Сколько наклонных кадров ТОЙ ЖЕ стороны нужно, чтобы порог стал меньше gap.

    Порог = bias + 2*SE(n). До n=20 берём SE с сетки (ступеньками - консервативно), дальше
    экстраполяция SE(n) = SE(20)*sqrt(20/n). Если один bias не меньше gap, усреднением того
    же ракурса разрыв между людьми не закрыть - возвращаем None (в таблице BIAS).
    """
    if bias >= gap:
        return None
    for n in (1, 2, 3, 4, 5, 10, 20):
        cur = se[1] if n == 1 else (se[5] if n <= 5 else se[20])
        if bias + 2 * cur < gap:
            return n
    need = 20 * (2 * se[20] / (gap - bias)) ** 2
    return math.ceil(need) if need <= big else None


def worst(sts: list[dict], key: str, n: int, use_bias: bool) -> float:
    """Порог человека: максимум по сторонам [биас (+) 2*SE], с биасом или без него."""
    return max((s[key][n] * 2 + (s["bias"] if use_bias else 0.0)) for s in sts)


def main() -> None:
    rows = load()
    lvl, tilt = splits(rows)
    ipd = {p: float(np.median([r["v17"][I.FEATURE_ORDER.index("eye_anchor_spacing_3d")] for r in lvl[p]]))
           for p in lvl}
    print(f"кадров: {len(rows)}, персон: {len(lvl)}, IPD эталонов: "
          + "  ".join(f"{p.split('_')[1]}={ipd[p]:.4f}" for p in sorted(lvl)))

    # ---------------- T8-метрики: порог обнаружения по каждой из 17 ----------------
    print("\n### T8a: минимальная видимая добавка в абсолютных единицах (блок-бутстрап)")
    print("Остаток наклонного кадра разложен на биас стороны (не исчезает при усреднении")
    print("кадров того же ракурса) и разброс вокруг биаса (SE). SE_block - circular block")
    print("bootstrap по наклонным кадрам одной стороны в порядке индекса; SE_iid = sigma/sqrt(n)")
    print("- прежняя формула (t/Дельта)^2, которая считает остаток независимым шумом.")
    print("порог фронта = биас + 2*SE_block (кадр против ровного эталона);")
    print("порог бина  = 2*SE_block (тот же канонический yaw у обоих, биас сокращается).")
    print("n_фронт / n_бин: кадров до минимального реального зазора между людьми;")
    print("BIAS = биас сам больше зазора, >2000 = зазор не закрывается в разумных n.\n")
    ns = (1, 5, 20)
    head = (f"{'метрика':24s}{'зазор_min':>10s}{'зазор_med':>10s}{'биас':>9s}"
            f"{'фронт(1)':>9s}{'фронт(5)':>9s}{'фронт(20)':>10s}{'bin(1)':>8s}{'bin(20)':>8s}"
            f"{'VIF(5)':>7s}{'n_фр':>7s}{'n_бин':>7s}")
    print(head)
    table = {}
    for i, nm in enumerate(I.FEATURE_ORDER):
        per, refs = {}, {}
        for p in sorted(lvl):
            v = np.array([r["v17"][i] for r in lvl[p]], float)
            if not np.isfinite(v).all() or v.size < 3:
                continue
            refs[p] = float(np.median(v))
            ser = side_series(tilt[p], refs[p], i)
            if ser:
                per[p] = [side_stats(x, ns) for _, x in ser]
        if len(refs) < 4 or not per:
            continue
        vals = sorted(abs(refs[a] - refs[b]) for k, a in enumerate(sorted(refs))
                      for b in sorted(refs)[k + 1:])
        gap_min, gap_med = vals[0], float(np.median(vals))
        thr_f = {n: float(np.median([worst(st, "block", n, True) for st in per.values()])) for n in ns}
        thr_b = {n: float(np.median([worst(st, "block", n, False) for st in per.values()])) for n in ns}
        thr_iid = float(np.median([worst(st, "iid", 20, True) for st in per.values()]))
        vif5 = [(s["block"][5] / s["iid"][5]) ** 2 for st in per.values() for s in st
                if s["iid"][5] > 1e-12 and s["L"] >= 3]
        biases = [s["bias"] for st in per.values() for s in st]
        med_bias = float(np.median(biases))
        n_f = [n_needed(s["bias"], s["block"], gap_min) for st in per.values() for s in st]
        n_b = [n_needed(0.0, s["block"], gap_min) for st in per.values() for s in st]
        tag_f = "BIAS" if any(x is None for x in n_f) else str(max(n_f))
        tag_b = ">" + str(2000) if any(x is None for x in n_b) else str(max(n_b))
        row = {"gap_min": gap_min, "gap_median": gap_med, "bias_median": med_bias,
               "bias_worst": max(biases),
               "detect_front": thr_f, "detect_bin": thr_b, "detect_iid_20": thr_iid,
               "vif_at_5": float(np.median(vif5)) if vif5 else None,
               "n_to_close_gap_front": None if tag_f == "BIAS" else int(tag_f),
               "n_to_close_gap_bin": None if tag_b.startswith(">") else int(tag_b),
               "bias_blocks_gap": tag_f == "BIAS", "n_people": len(per)}
        table[nm] = row
        vif_s = f"{row['vif_at_5']:.2f}" if row["vif_at_5"] else "-"
        print(f"{nm:24s}{gap_min:10.5f}{gap_med:10.5f}{med_bias:9.5f}"
              f"{thr_f[1]:9.5f}{thr_f[5]:9.5f}{thr_f[20]:10.5f}"
              f"{thr_b[1]:8.5f}{thr_b[20]:8.5f}{vif_s:>7s}{tag_f:>7s}{tag_b:>7s}")
    print("\n(зазор_min = ближайшая реальная пара людей, зазор_med = медиана 15 пар)")

    # ---------------- T8b: нос в геометрии, биас стороны + блок-бутстрап ----------------
    print("\n### T8b: ширина носа (58-62) по сторонам: биас ракурса + 2*SE_block(n)")
    print("шаг добавки виден на n кадрах одной стороны, если s*средняя_ширина > порог(n)")
    for p in sorted(lvl):
        if not tilt[p]:
            continue
        ref = np.median(np.stack([r["canon"] for r in lvl[p]]), axis=0)
        w0 = float(np.linalg.norm(ref[ALAR_L] - ref[ALAR_R]))
        print(f" {p}: ширина ровная={units(w0, ipd[p])}  наклонных={len(tilt[p])}")
        for side, sgn in (("left", 1.0), ("right", -1.0)):
            rs = sorted((r for r in tilt[p] if sgn * r["tilt"] > 2.0), key=lambda r: r["fidx"])
            own = np.array([float(np.linalg.norm(r["canon"][ALAR_L] - r["canon"][ALAR_R])) for r in rs])
            base = own - w0
            if base.size < 3:
                continue
            st = side_stats(base, ns)
            vif_s = f"{(st['block'][5] / st['iid'][5]) ** 2:.2f}" if st["iid"][5] > 1e-12 else "-"
            print(f"   {side:5s} n={base.size:2d} биас={float(np.median(base)):+.5f} "
                  f"SE_block(1/5/20)={st['block'][1]:.5f}/{st['block'][5]:.5f}/{st['block'][20]:.5f} "
                  f"L={st['L']} SE_iid(5)={st['iid'][5]:.5f} блок/незав={vif_s}")
            for s in (0.01, 0.02, 0.03, 0.05):
                shift = s * float(np.mean(own))
                verdict = {n: ("виден" if shift > st["bias"] + 2 * st["block"][n] else "нет") for n in ns}
                verdict_iid = "виден" if shift > 2 * st["iid"][1] else "нет"
                print(f"     +{100 * s:4.1f}%: сдвиг {units(shift, ipd[p])}  "
                      f"n=1:{verdict[1]}  n=5:{verdict[5]}  n=20:{verdict[20]}"
                      f"   (по старой формуле 1 кадр: {verdict_iid})")

    out = HERE / "report" / "t8_absolute.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"ipd": ipd, "metrics": table}, ensure_ascii=False, indent=2,
                              default=lambda o: None if isinstance(o, float) and not np.isfinite(o) else str(o)),
                   encoding="utf-8")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
