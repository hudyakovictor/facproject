#!/usr/bin/env python
"""Тест «выравнивает ли выравнивание» по /Volumes/SDCARD/calibration_rakurs.

Схема (как договорились, сначала фронтал):
  1) для каждого человека в бине берём РОВНЫЕ кадры ровно тем же критерием, что и все
     остальные тесты (advisor_tests.level_set: |tilt|<=2 и |pitch|<=5, иначе 3 ближайших).
     Их выравнивание не нужно: они и есть эталон формы этого человека в этом ракурсе;
  2) берём ВСЕ наклонные кадры бина (по 5 самых крайних в каждую сторону, как раньше,
     цифры этого скрипта было бы нельзя сравнить с advisor_tests);
  3) каждый наклонный кадр сравниваем с ровным эталоном в четырёх состояниях точек:
       two_d  — плоскость фото (ракурс исказил лицо, никакого выравнивания)
       cam    — 3D в камерном базисе (поза НЕ убрана)
       canon  — наш пайплайн: поза убрана + центр/масштаб
       sym    — canon + зеркальная симметризация
     Два состояния убраны: rotneg доворачивал canon на -tilt (то есть добавлял позу к
     mesh, у которого позы нет - см. T2), а «best» считал пол не leave-one-out: эталон
     включал сам кадр и поворот подгонялся под него, поэтому best выглядел хуже canon.
     Корректная проверка доворота - колонки cam x Fz x R_corr в advisor_tests.T2.
  4) разница = среднее расстояние по 106 точкам до эталона. Относим её к «полу» -
     расстоянию между ровными кадрами того же человека (leave-one-out). ratio ~ 1 ->
     выравнивание ровняет; ratio >> 1 -> ракурс протекает в метрику.
О нормировке: облака берутся из advisor_tests.load(), то есть центрированы и приведены
к max-radius=1 (в кэше level_extract раньше лежали центрированные, но не отмасштабированные
точки). Об «убранной доле ракурса»: vertices_identity_only строится базисом 3DDFA с нулевой
позой, так что «выравнивание снимает X%» говорить некорректно - доля в основном показывает
размер самого поворота в cam. Содержательная метрика - ratio к полу.

Запуск: python level_verify.py [bin ...]   (по умолчанию все готовые бины)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "report" / "level_verify.json"
BIN_ORDER = ("frontal", "left_light", "right_light", "left_mid", "right_mid",
             "left_deep", "right_deep", "left_profile", "right_profile")

from advisor_tests import CANON_YAW, level_set, load, vdist  # noqa: E402
from morphing.backend import identity as I  # noqa: E402

PAIRS = [(0, 31), (1, 29), (3, 27), (5, 25), (7, 23), (9, 21), (11, 19), (13, 17),
         (33, 46), (34, 45), (35, 44), (36, 43), (37, 42), (57, 63), (59, 61),
         (66, 79), (67, 78), (69, 76), (70, 75), (71, 82), (73, 80),
         (84, 90), (85, 89), (86, 88), (91, 95), (92, 94), (96, 100), (97, 99), (101, 103)]
MIDLINE = [15, 51, 52, 53, 54, 60, 87, 93]
VARIANTS = ["two_d", "cam", "canon", "sym"]
WARNINGS: list[str] = []


def symmetrize(p):
    cx = float(p[:, 0].mean())
    refl = lambda q: np.array([2 * cx - q[0], q[1], q[2]])  # noqa: E731
    out = p.copy()
    for i, j in PAIRS:
        m = (p[i] + refl(p[j])) / 2.0
        out[i] = m
        out[j] = refl(m)
    for k in MIDLINE:
        out[k] = (p[k] + refl(p[k])) / 2.0
    return out


def fm(points, tag=""):
    """form_vector с открытой диагностикой: на плоском (z=0) облаке часть метрик не определена.

    Тихий except прятал реальные ошибки метрик, поэтому теперь пишем, что именно упало,
    и считаем пропуски в отчёте.
    """
    try:
        v = np.asarray(I.form_vector(points), float)
    except Exception as exc:  # noqa: BLE001 - метрика может упасть на вырожденном облаке
        WARNINGS.append(f"{tag}: {type(exc).__name__}: {exc}")
        v = np.full(len(I.FEATURE_ORDER), np.nan)
    return np.where(np.isfinite(v), v, np.nan)


def by_bin(rows, bins):
    """Кадровый набор по бинам: (строки, канонический yaw бина) - yaw берём из POSE_BINS."""
    out = {}
    for b in bins:
        rs = [r for r in rows if r["bin"] == b]
        if rs:
            out[b] = (rs, CANON_YAW.get(b, 0.0))
    return out


def sets_for(rs):
    """Ровные кадры (общий критерий level_set) + ВСЕ наклонные, разложенные по сторонам."""
    lvl = level_set(rs)
    keep = {id(r) for r in lvl}
    rest = [r for r in rs if id(r) not in keep]
    left = sorted((r for r in rest if r["tilt"] < 0), key=lambda r: r["tilt"])
    right = sorted((r for r in rest if r["tilt"] > 0), key=lambda r: -r["tilt"])
    return lvl, left, right


def variants(r):
    can = r["canon"]
    return {"two_d": r["two_d"], "cam": r["cam"], "canon": can, "sym": symmetrize(can)}


def analyze(rs, tag):
    for r in rs:
        r["_v"] = variants(r)
    lvl, left, right = sets_for(rs)
    if len(lvl) < 3 or not (left or right):
        return None
    ref = {n: np.median(np.stack([r["_v"][n] for r in lvl]), axis=0) for n in VARIANTS}
    floor = {}
    for n in VARIANTS:
        # leave-one-out: эталон собран без самого кадра, иначе пол измеряет подгонку
        d = [vdist(r["_v"][n], np.median(np.stack([q["_v"][n] for q in lvl if q is not r]), axis=0))
             for r in lvl]
        floor[n] = float(np.median(d))
    side = left + right
    acc = {n: [] for n in VARIANTS}
    mval = {n: [] for n in VARIANTS}
    for r in side:
        for n in VARIANTS:
            acc[n].append(vdist(r["_v"][n], ref[n]))
            mval[n].append(fm(r["_v"][n], tag=f"{tag}/{r['person']}/{r['frame']}/{n}"))
    out = {"n_frames": len(rs), "n_level": len(lvl), "n_side": len(side),
           "n_side_left": len(left), "n_side_right": len(right),
           "canon_yaw": round(CANON_YAW.get(tag, 0.0), 1),
           "tilt_level": [round(r["tilt"], 1) for r in lvl],
           "tilt_side": [round(r["tilt"], 1) for r in side],
           "floor": {k: round(v, 5) for k, v in floor.items()},
           "ratio": {}, "z": {}, "metric_nan": {}}
    for n in VARIANTS:
        m = float(np.median(acc[n]))
        out["ratio"][n] = round(m / floor[n], 2) if floor[n] > 1e-9 else None
        out["d_" + n] = round(m, 5)
    for n in ("two_d", "cam"):
        if out["d_canon"] and out["d_" + n]:
            out["frac_of_" + n + "_left_in_canon"] = round(out["d_canon"] / out["d_" + n], 3)
    # z по метрикам: |наклонный - эталон| / разброс ровных канон-кадров (знаменатель общий)
    M = np.stack([fm(r["_v"]["canon"], tag=f"{tag}/level/{r['frame']}") for r in lvl])
    spread = np.nanmedian(np.abs(M - np.nanmedian(M, 0)), 0) * 1.4826 + 1e-9
    refv = fm(ref["canon"], tag=f"{tag}/ref")
    for n in VARIANTS:
        z = np.nanmedian(np.abs(np.stack(mval[n]) - refv), 0) / spread
        out["z"][n] = [round(float(x), 2) if np.isfinite(x) else None for x in z]
        out["metric_nan"][n] = int(np.count_nonzero(~np.isfinite(np.stack(mval[n]))))
    return out


def main():
    bins = [a for a in sys.argv[1:] if a in BIN_ORDER] or list(BIN_ORDER)
    rows = load()
    data = by_bin(rows, bins)
    report = {}
    print(f"кадров в кэше: {len(rows)}; бинов: {[(b, len(rs)) for b, (rs, _) in data.items()]}")
    for b, (rs, cy) in data.items():
        per = {}
        for p in sorted({r["person"] for r in rs}):
            res = analyze([r for r in rs if r["person"] == p], b)
            if res:
                per[p] = res
        report[b] = per
        if not per:
            print(f"\n{b}: некому анализировать (мало ровных или наклонных кадров)")
            continue
        ns = [d["n_side"] for d in per.values()]
        print(f"\n=== {b}: канон бина {cy:+.0f}, персон {len(per)}, наклонных кадров на человека {ns} ===")
        print(f"{'':10s}" + "".join(f"{v:>9s}" for v in VARIANTS) + "   доля cam, оставшаяся в canon")
        for n in VARIANTS:
            vals = [d["ratio"][n] for d in per.values() if d["ratio"][n]]
            print(f"  ratio {n:5s}" + "".join(f"{x:>9.2f}" for x in vals) +
                  (f"   медиана {np.median(vals):.2f}" if vals else ""))
        fr = [d.get("frac_of_cam_left_in_canon") for d in per.values()]
        print("  (справочно) d_canon/d_cam - это не «снято ракурса», а доля расстояния cam,"
              " которая осталась: " + " ".join(str(x) for x in fr if x is not None))

    # сводка по метрикам: медианный z по всем людям/бинам для каждого бина
    print("\n=== z по метрикам v17 (медиана по людям; <=2 = ровняет, >4 = ракурс протекает) ===")
    keys = list(I.FEATURE_ORDER)
    print(f"{'metric':22s}" + "".join(f"{b[:8]:>9s}" for b in report if report[b]))
    for i, nm in enumerate(keys):
        line = f"{nm:22s}"
        for per in report.values():
            if not per:
                continue
            vals = [d["z"]["canon"][i] for d in per.values() if d["z"]["canon"][i] is not None]
            line += f"{np.median(vals):>9.2f}" if vals else f"{'-':>9s}"
        print(line)
    nan = sum(sum(d["metric_nan"].values()) for per in report.values() for d in per.values())
    print(f"\nпропусков form_vector (NaN по метрике): {nan}; уникальных сообщений: "
          f"{len(set(WARNINGS))}")
    for w in list(dict.fromkeys(WARNINGS))[:5]:
        print(f"  {w}")

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list | tuple):
            return [clean(v) for v in o]
        if isinstance(o, float | np.floating) and not np.isfinite(o):
            return None
        return o.tolist() if isinstance(o, np.generic) else o

    OUT.write_text(json.dumps(clean(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nОтчёт: {OUT}")


if __name__ == "__main__":
    main()
