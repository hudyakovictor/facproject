#!/usr/bin/env python
"""Тест «выравнивает ли выравнивание» по /Volumes/SDCARD/calibration_rakurs.

Схема (как договорились, сначала фронтал):
  1) для каждого человека в бине берём РОВНЫЕ кадры - те, где yaw ближе всего к
     каноническому yaw этого бина (для фронтала это ~0) и pitch мал. Их выравнивание
     не нужно: они и есть эталон формы этого человека в этом ракурсе;
  2) берём до 5 кадров с наклоном в одну сторону и до 5 в другую (по local yaw);
  3) каждый наклонный кадр сравниваем с ровным эталоном в пяти состояниях точек:
       two_d  — плоскость фото (ракурс исказил лицо, никакого выравнивания)
       cam    — 3D в камерном базисе (поза НЕ убрана)
       canon  — наш пайплайн: поза убрана + центр/масштаб
       sym    — canon + зеркальная симметризация
       rotneg — canon + доворот на -local_yaw (гипотеза «довернём в канон бина»)
       best   — canon + ЛУЧШИЙ возможный поворот (Procrustes): потолок того, что
                вообще способен убрать любой доворот
  4) разница = среднее расстояние по 106 точкам до эталона. Относим её к «полу» -
     расстоянию между ровными кадрами того же человека. ratio ~ 1 -> выравнивание
     ровняет; ratio >> 1 -> ракурс протекает в метрику.
Каждое состояние сравнивается со своим ровным эталоном в том же базисе, поэтому
конвенция осей camera-пространства на результат не влияет.

Запуск: python level_verify.py [bin ...]   (по умолчанию все готовые бины)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
ROWS_P = ROOT / ".runtime" / "level_cache" / "frames.jsonl"
OUT = HERE / "report" / "level_verify.json"
LEVEL_YAW, N_SIDE = 2.0, 5
BIN_ORDER = ("frontal", "left_light", "right_light", "left_mid", "right_mid",
             "left_deep", "right_deep", "left_profile", "right_profile")

from morphing.backend import identity as I  # noqa: E402

PAIRS = [(0, 31), (1, 29), (3, 27), (5, 25), (7, 23), (9, 21), (11, 19), (13, 17),
         (33, 46), (34, 45), (35, 44), (36, 43), (37, 42), (57, 63), (59, 61),
         (66, 79), (67, 78), (69, 76), (70, 75), (71, 82), (73, 80),
         (84, 90), (85, 89), (86, 88), (91, 95), (92, 94), (96, 100), (97, 99), (101, 103)]
MIDLINE = [15, 51, 52, 53, 54, 60, 87, 93]
VARIANTS = ["two_d", "cam", "canon", "sym", "rotneg"]


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


def rot_y(deg):
    a = np.radians(deg)
    return np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])


def vdist(a, b):
    return float(np.mean(np.linalg.norm(np.asarray(a) - np.asarray(b), axis=1)))


def fm(points):
    """form_vector с защитой: на плоском (z=0) облаке часть метрик не определена."""
    try:
        v = np.asarray(I.form_vector(points), float)
    except Exception:  # noqa: BLE001
        v = np.full(len(I.FEATURE_ORDER), np.nan)
    return np.where(np.isfinite(v), v, np.nan)


def procrustes_rot(p, ref):
    A, B = np.asarray(p), np.asarray(ref)
    U, _, Vt = np.linalg.svd(A.T @ B)
    return U @ np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]) @ Vt


def load(bins):
    """Строки кэша по нужным бинам; канонический yaw бина = мода classify_pose по кадрам."""
    from app8.geometry import classify_pose
    by_bin = {}
    for line in ROWS_P.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "fail" in r or not r.get("canon") or len(r["canon"]) != 318:
            continue
        r.setdefault("bin", "frontal")
        if r["bin"] in bins:
            for k in ("canon", "cam", "two_d"):
                r[k] = np.asarray(r[k], float).reshape(106, 3)
            by_bin.setdefault(r["bin"], []).append(r)
    for b, rs in by_bin.items():
        cys = [classify_pose(r["yaw"])[1] for r in rs]
        by_bin[b] = (rs, Counter(cys).most_common(1)[0][0] if rs else 0.0)
    return by_bin


def sets_for(rs, canon_yaw):
    """Ровные кадры (ближе всех к канону бина) + до N_SIDE наклонных в каждую сторону."""
    tilt = {id(r): r["yaw"] - canon_yaw for r in rs}
    lvl = [r for r in rs if abs(tilt[id(r)]) <= LEVEL_YAW]
    if len(lvl) < 3:
        lvl = sorted(rs, key=lambda r: abs(tilt[id(r)]))[:3]
    keep = {id(r) for r in lvl}
    rest = [r for r in rs if id(r) not in keep]
    left = sorted([r for r in rest if tilt[id(r)] < 0], key=lambda r: tilt[id(r)])[:N_SIDE]
    right = sorted([r for r in rest if tilt[id(r)] > 0], key=lambda r: -tilt[id(r)])[:N_SIDE]
    return lvl, left, right, tilt


def variants(r, canon_yaw):
    can = r["canon"]
    return {"two_d": r["two_d"], "cam": r["cam"], "canon": can,
            "sym": symmetrize(can), "rotneg": can @ rot_y(-(r["yaw"] - canon_yaw))}


def analyze(rs, canon_yaw):
    for r in rs:
        r["_v"] = variants(r, canon_yaw)
    lvl, left, right, tilt = sets_for(rs, canon_yaw)
    if len(lvl) < 3 or not (left or right):
        return None
    ref = {n: np.median(np.stack([r["_v"][n] for r in lvl]), axis=0) for n in VARIANTS}
    floor = {}
    for n in VARIANTS:
        d = [vdist(r["_v"][n], np.median(np.stack([q["_v"][n] for q in lvl if q is not r]), axis=0))
             for r in lvl]
        floor[n] = float(np.median(d))
    floor["best"] = float(np.median([vdist(r["_v"]["canon"] @ procrustes_rot(r["_v"]["canon"], ref["canon"]),
                                           ref["canon"]) for r in lvl]))
    side = left + right
    acc = {n: [] for n in VARIANTS + ["best"]}
    mval = {n: [] for n in VARIANTS + ["best"]}
    for r in side:
        for n in VARIANTS:
            acc[n].append(vdist(r["_v"][n], ref[n]))
            mval[n].append(fm(r["_v"][n]))
        bp = r["_v"]["canon"] @ procrustes_rot(r["_v"]["canon"], ref["canon"])
        acc["best"].append(vdist(bp, ref["canon"]))
        mval["best"].append(fm(bp))
    out = {"n_frames": len(rs), "n_level": len(lvl), "n_side": len(side),
           "canon_yaw": round(canon_yaw, 1),
           "tilt_level": [round(tilt[id(r)], 1) for r in lvl],
           "tilt_side": [round(tilt[id(r)], 1) for r in side],
           "floor": {k: round(v, 5) for k, v in floor.items()},
           "ratio": {}, "z": {}}
    for n in VARIANTS + ["best"]:
        m = float(np.median(acc[n]))
        out["ratio"][n] = round(m / floor[n], 2) if floor[n] > 1e-9 else None
        out["d_" + n] = round(m, 5)
    for n in ("two_d", "cam"):
        if out["d_canon"] and out["d_" + n]:
            out["levelled_frac_vs_" + n] = round(1.0 - out["d_canon"] / out["d_" + n], 3)
    # z по метрикам: |наклонный - эталон| / разброс ровных канон-кадров (знаменатель общий)
    M = np.stack([fm(r["_v"]["canon"]) for r in lvl])
    spread = np.nanmedian(np.abs(M - np.nanmedian(M, 0)), 0) * 1.4826 + 1e-9
    for n in VARIANTS + ["best"]:
        refv = fm(ref["canon"]) if n == "best" else fm(ref[n])
        z = np.nanmedian(np.abs(np.stack(mval[n]) - refv), 0) / spread
        out["z"][n] = [round(float(x), 2) if np.isfinite(x) else None for x in z]
    return out


def main():
    bins = [a for a in sys.argv[1:] if a in BIN_ORDER] or list(BIN_ORDER)
    data = load(bins)
    report = {}
    print(f"бинов в кэше: {[(b, len(rs)) for b, (rs, _) in data.items()]}")
    for b, (rs, cy) in data.items():
        per = {}
        for p in sorted({r["person"] for r in rs}):
            res = analyze([r for r in rs if r["person"] == p], cy)
            if res:
                per[p] = res
        report[b] = per
        if not per:
            print(f"\n{b}: некому анализировать (мало ровных или наклонных кадров)")
            continue
        print(f"\n=== {b}: канон бина {cy:+.0f}, персон {len(per)} "
              f"(по {per[list(per)[0]]['n_side']} наклонных кадров на человека) ===")
        print(f"{'':10s}" + "".join(f"{v:>9s}" for v in VARIANTS + ["best"]) + "   убрано vs cam")
        for n in VARIANTS + ["best"]:
            vals = [d["ratio"][n] for d in per.values() if d["ratio"][n]]
            print(f"  ratio {n:5s}" + "".join(f"{x:>9.2f}" for x in vals) +
                  (f"   медиана {np.median(vals):.2f}" if vals else ""))
        fr = [d.get("levelled_frac_vs_cam") for d in per.values()]
        print("  убрано ракурса (доля расстояния camera->эталон, снятая выравниванием): " +
              " ".join(f"{x}" for x in fr if x is not None))

    # сводка по метрикам: медианный z по всем.person/bin для каждого бина
    print("\n=== z по метрикам v17 (медиана по людям; ≤2 = ровняет, >4 = ракурс протекает) ===")
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
