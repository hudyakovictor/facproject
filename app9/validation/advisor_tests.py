#!/usr/bin/env python
"""Мини-тесты 1-8 по замечаниям советника. Данные - кэш .runtime/level_cache (606 кадров),
новых реконструкций нет.

T1 sanity Procrustes: d(best) обязан быть <= d(canon).
T2 rotneg на правильном входе: матрица app8 к cam (с z-флипом to_camera) против той же матрицы к canon.
T3 блочный пол шума: эталон без соседей по индексу кадра.
T4 нормировка RMS (прод app6) вместо max-radius.
T5 расстояние между людьми в тех же единицах.
T6 ICC по 17 метрикам: ровные кадры против наклонных после canon.
T7 знаковый остаток против yaw, регрессия на 5 людях -> проверка на 6-м.
T8 синтетика: известная добавка к ширине носа, минимальная видимая величина.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
CACHE = ROOT / ".runtime" / "level_cache" / "frames.jsonl"
BINS = ("frontal", "left_light", "right_light", "left_mid", "right_mid",
        "left_deep", "right_deep", "left_profile", "right_profile")
STATE = ("canon", "cam", "two_d")
FZ = np.diag([1.0, 1.0, -1.0])          # to_camera делает z = camera_distance - z

from app8.config import POSE_BINS  # noqa: E402
from app8.geometry import full_pose_correction_matrix, row_rotation_matrix  # noqa: E402
from morphing.backend import identity as I  # noqa: E402

CANON_YAW = {b[0]: float(b[3]) for b in POSE_BINS}
ALAR_L, ALAR_R, NOSE_BASE, NOSE_TIP = 58, 62, 60, 54
NOSE_SET = [NOSE_BASE, ALAR_L, ALAR_R, NOSE_TIP, 51, 52, 53]


def fidx(name):
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else -1


def rms(p):
    return float(np.sqrt(np.mean(np.sum(p * p, axis=1))))


def vdist(a, b, idx=None):
    a, b = np.asarray(a), np.asarray(b)
    if idx is not None:
        a, b = a[idx], b[idx]
    return float(np.mean(np.linalg.norm(a - b, axis=1)))


def proc_rot(A, B):
    U, _, Vt = np.linalg.svd(np.asarray(A).T @ np.asarray(B))
    return U @ np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]) @ Vt


def load():
    rows = []
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "fail" in r or len(r.get("canon", [])) != 318:
            continue
        r.setdefault("bin", "frontal")
        for k in STATE:
            r[k] = np.asarray(r[k], float).reshape(106, 3)
            r["r" + k] = r[k] / rms(r[k])          # RMS-нормировка = нормировка прода app6
        r["fidx"] = fidx(r["frame"])
        r["tilt"] = r["yaw"] - CANON_YAW.get(r["bin"], 0.0)
        r["ok"] = r["fidx"] >= 0
        rows.append(r)
    return [r for r in rows if r["ok"]]


def level_set(rs):
    lvl = [r for r in rs if abs(r["tilt"]) <= 2.0 and abs(r["pitch"]) <= 5.0]
    if len(lvl) < 3:
        lvl = sorted(rs, key=lambda r: abs(r["tilt"]))[:3]
    return lvl


def R_corr(r, canon_yaw):
    return full_pose_correction_matrix(np.array([r["pitch"], r["yaw"], r["roll"]], np.float32),
                                       np.array([0.0, canon_yaw, 0.0], np.float32))


def column_stats(rs_all, cloud_for, gap=0, metric_of=None):
    """По каждой колонке (имя -> функция кадр->облако) считает пол (leave-one-out, с
    защитным зазором gap по индексу) и расстояние наклонных кадров до эталона.
    Возвращает {имя: floor, d_tilt, ratio, n_floor, n_tilt} по медианам людей."""
    names = list(cloud_for)
    floors = {n: [] for n in names}
    dts = {n: [] for n in names}
    for p in sorted({r["person"] for r in rs_all}):
        rs = [r for r in rs_all if r["person"] == p]
        if len(rs) < 6:
            continue
        lvl, side = level_set(rs), [r for r in rs if abs(r["tilt"]) > 2]
        for n in names:
            L = [cloud_for[n](r) for r in lvl]
            for i, c in enumerate(L):
                pool = [L[j] for j in range(len(L)) if j != i and abs(lvl[j]["fidx"] - lvl[i]["fidx"]) > gap]
                if len(pool) >= 2:
                    floors[n].append(vdist(c, np.median(np.stack(pool), axis=0)))
            ref = np.median(np.stack(L), axis=0) if L else None
            if ref is None:
                continue
            for r in side:
                if any(abs(q["fidx"] - r["fidx"]) <= gap for q in lvl):
                    continue
                dts[n].append(vdist(cloud_for[n](r), ref))
        _ = metric_of
    out = {}
    for n in names:
        if not floors[n] or not dts[n]:
            continue
        f, d = float(np.median(floors[n])), float(np.median(dts[n]))
        out[n] = {"floor": round(f, 5), "d_tilt": round(d, 5), "ratio": round(d / f, 2),
                  "n_floor": len(floors[n]), "n_tilt": len(dts[n])}
    return out


def show(title, stats, order=None):
    print(title)
    print(f"{'колонка':22s}{'n':>5s}{'пол':>10s}{'d наклон':>11s}{'ratio':>8s}")
    for n in (order or stats.keys()):
        s = stats.get(n)
        if not s:
            continue
        print(f"{n:22s}{s['n_tilt']:>5d}{s['floor']:>10.5f}{s['d_tilt']:>11.5f}{s['ratio']:>8.2f}")


# --------------------------------------------------------------------------- T1
def t1(rows):
    print("\n### T1 Sanity Procrustes: d(best) обязан быть <= d(canon)")
    per = {}
    for r in rows:
        per.setdefault((r["person"], r["bin"]), []).append(r)
    cand = [r for rs in per.values() if len(rs) >= 6 for r in rs]
    cand.sort(key=lambda r: -abs(r["tilt"]))
    bad, margins = 0, []
    print(f"{'person/bin':26s}{'frame':16s}{'tilt':>7s}{'d_canon':>10s}{'d_best':>10s}{'выигрыш':>10s}")
    for r in cand[:20]:
        rc = np.median(np.stack([q["canon"] for q in level_set(per[(r["person"], r["bin"])])]), axis=0)
        d0 = vdist(r["canon"], rc)
        d1 = vdist(r["canon"] @ proc_rot(r["canon"], rc), rc)
        bad += int(d1 > d0 + 1e-12)
        margins.append(d0 - d1)
        print(f"{r['person']+'/'+r['bin']:26s}{r['frame']:16s}{r['tilt']:>7.1f}{d0:>10.5f}{d1:>10.5f}{d0-d1:>10.5f}")
    allm = []
    for r in cand:
        rc = np.median(np.stack([q["canon"] for q in level_set(per[(r["person"], r["bin"])])]), axis=0)
        allm.append(vdist(r["canon"], rc) - vdist(r["canon"] @ proc_rot(r["canon"], rc), rc))
    print(f"нарушений d_best > d_canon: {bad} из 20; на всех {len(cand)} кадрах медианный выигрыш best = {np.median(allm):.7f},"
          f" 95-й перцентиль = {np.percentile(allm, 95):.7f}")
    return {"violations": bad, "median_gain": round(float(np.median(allm)), 6),
            "p95_gain": round(float(np.percentile(allm, 95)), 6), "n": len(cand)}


# --------------------------------------------------------------------------- T2
def t2(rows):
    print("\n### T2 rotneg на правильном входе. R_corr = (R_target R_actual^T) - в матрице app8")
    out = {}
    for b in ("frontal", "left_profile", "right_profile"):
        cy = CANON_YAW.get(b, 0.0)

        def cloud(r, n, cy=cy):
            M = R_corr(r, cy)
            if n == "canon":                       # mesh БЕЗ позы (vertices_identity_only)
                return r["canon"]
            if n == "canon x R_corr":              # так делает прод (app6/app8 chronology)
                return r["canon"] @ M
            if n == "cam":                         # mesh С позой, в базисе камеры
                return r["cam"]
            if n == "cam x R_corr":                # та же матрица наивняком к cam
                return r["cam"] @ M
            if n == "cam x Fz x R_corr":           # снятие позы с учётом z-флипа to_camera
                return r["cam"] @ FZ @ M
            raise KeyError(n)

        names = ["canon", "canon x R_corr", "cam", "cam x R_corr", "cam x Fz x R_corr"]
        cf = {n: (lambda r, n=n: cloud(r, n)) for n in names}
        stats = column_stats([r for r in rows if r["bin"] == b], cf)
        show(f"--- бин {b} (канонический yaw {cy:+.0f}) ---", stats, names)
        out[b] = stats
    # контроль: row_rotation_matrix совпадает с матрицей модели? (проверка соглашения)
    r = next(x for x in rows if x["bin"] == "frontal")
    A = row_rotation_matrix(r["pitch"], r["yaw"], r["roll"])
    B = np.asarray(r["R"], float).reshape(3, 3)
    off = float(np.max(np.abs(A - B)))
    print(f" контроль соглашения: max|row_rotation_matrix(углы) - rotation_matrix модели| = {off:.4f}"
          f" (0 => матрицы совпадают, знак доворота выведен верно)")
    return out


# --------------------------------------------------------------------------- T3
def t3(rows):
    print("\n### T3 блочный пол шума (фронтал): эталон без соседей по индексу кадра")
    fr = [r for r in rows if r["bin"] == "frontal"]
    idx = sorted({r["fidx"] for r in fr})
    print(f" индексы ровных кадров: размах {min(idx)}..{max(idx)}, типичный шаг 1 (непрерывное видео)")
    cf = {"canon": lambda r: r["canon"], "cam": lambda r: r["cam"]}
    out = {}
    for gap in (0, 5, 15, 30):
        stats = column_stats(fr, cf, gap=gap)
        out[f"gap>{gap}"] = stats
        show(f"--- защитный зазор gap>{gap} кадров ---", stats, ["canon", "cam"])
    print(" при gap>15 большинство ровных кадров отсекаются: их burst короче 15 индексов;")
    print(" ср. отношение пола gap>15 / пола gap>0 печатается ниже")
    f0 = out["gap>0"]["canon"]["floor"]
    f15 = out["gap>15"]["canon"]["floor"] if "canon" in out["gap>15"] else None
    print(f" пол canon: gap>0 {f0} -> gap>15 {f15}; ratio: {out['gap>0']['canon']['ratio']} -> "
          f"{out['gap>15']['canon']['ratio'] if f15 else 'n/a'}")

    # 3b: пол как функция зазора между парами ровных кадров (не leave-one-out, а попарно)
    print("\n--- 3b: d между парами ровных фронтальных кадров против зазора по индексу ---")
    buck = [(0, 2), (2, 5), (5, 15), (15, 50), (50, 10 ** 9)]
    print(f"{'зазор':>12s}{'пар':>7s}{'d canon':>10s}{'d cam':>10s}")
    curve = {}
    for lo, hi in buck:
        dc, dm = [], []
        for p in sorted({r["person"] for r in fr}):
            lvl = sorted((r for r in level_set([x for x in fr if x["person"] == p])), key=lambda r: r["fidx"])
            for i, a in enumerate(lvl):
                for b in lvl[i + 1:]:
                    g = abs(a["fidx"] - b["fidx"])
                    if lo < g <= hi:
                        dc.append(vdist(a["canon"], b["canon"]))
                        dm.append(vdist(a["cam"], b["cam"]))
        tag = f"({lo},{hi if hi < 10**8 else 'inf'}]"
        curve[tag] = {"pairs": len(dc), "canon": round(float(np.median(dc)), 5) if dc else None,
                      "cam": round(float(np.median(dm)), 5) if dm else None}
        print(f"{tag:>12s}{len(dc):>7d}{curve[tag]['canon'] if dc else '-':>10}{curve[tag]['cam'] if dm else '-':>10}")

    # 3c: ровные кадры каждого человека - ОДИН непрерывный прогон (всплесков нет), поэтому
    # блочный пол считаем split-half: кадр против медианы ДРУГОЙ половины его же ровных кадров
    print("\n--- 3c: split-half пол (кадр против эталона другой половины того же прогона) ---")
    floor, floorc, dts, dtsc = [], [], [], []
    drift = []
    for p in sorted({r["person"] for r in fr}):
        rs = [x for x in fr if x["person"] == p]
        lvl = sorted(level_set(rs), key=lambda r: r["fidx"])
        if len(lvl) < 6:
            continue
        h = len(lvl) // 2
        A, B = lvl[:h], lvl[h:]
        mA = np.median(np.stack([q["canon"] for q in A]), axis=0)
        mB = np.median(np.stack([q["canon"] for q in B]), axis=0)
        mA_c = np.median(np.stack([q["cam"] for q in A]), axis=0)
        mB_c = np.median(np.stack([q["cam"] for q in B]), axis=0)
        floor += [vdist(q["canon"], mB) for q in A] + [vdist(q["canon"], mA) for q in B]
        floorc += [vdist(q["cam"], mB_c) for q in A] + [vdist(q["cam"], mA_c) for q in B]
        drift.append(abs(float(np.median([q["yaw"] for q in A])) - float(np.median([q["yaw"] for q in B]))))
        ref = np.median(np.stack([q["canon"] for q in lvl]), axis=0)
        refc = np.median(np.stack([q["cam"] for q in lvl]), axis=0)
        dts += [vdist(r["canon"], ref) for r in rs if abs(r["tilt"]) > 2]
        dtsc += [vdist(r["cam"], refc) for r in rs if abs(r["tilt"]) > 2]
    f = float(np.median(floor))
    print(f" людей {len(drift)}: пол(canon, split-half)={f:.5f} (кадров {len(floor)}),"
          f"  d наклонных={float(np.median(dts)):.5f},  ratio={float(np.median(dts))/f:.2f}")
    print(f"  пол(cam, split-half)={float(np.median(floorc)):.5f}  d(cam наклонных)={float(np.median(dtsc)):.5f}"
          f"  ratio cam={float(np.median(dtsc))/float(np.median(floorc)):.2f}")
    print(f"  разница медиан yaw между половинами (загрязнение пола позой): med={float(np.median(drift)):.2f} max={max(drift):.2f} град")
    print(f"  сравнение: пол LOO gap>0 = {out['gap>0']['canon']['floor']}, ratio = {out['gap>0']['canon']['ratio']}")
    out["3b_curve"] = curve
    out["3c_splithalf"] = {"floor_canon": round(f, 5), "floor_cam": round(float(np.median(floorc)), 5),
                           "d_tilt": round(float(np.median(dts)), 5), "ratio_canon": round(float(np.median(dts)) / f, 2),
                           "yaw_drift_median_deg": round(float(np.median(drift)), 2), "n_floor": len(floor)}
    return out


# --------------------------------------------------------------------------- T4
def t4(rows):
    print("\n### T4 нормировка: max-radius (как в aligner) против RMS (как в app6/stage1)")
    fr = [r for r in rows if r["bin"] == "frontal"]
    cf = {}
    for st in STATE:
        cf[st + " maxr"] = (lambda r, s=st: r[s])
        cf[st + " rms"] = (lambda r, s=st: r["r" + s])
    stats = column_stats(fr, cf)
    show("--- фронтал ---", stats, list(cf))
    for st in STATE:
        a = [rms(r[st]) for r in fr]
        print(f" неустойчивость max-радиуса ({st}): RMS-радиус после max-нормировки "
              f"min/med/max = {min(a):.4f}/{float(np.median(a)):.4f}/{max(a):.4f}")
    return stats


# --------------------------------------------------------------------------- T5
def t5(rows):
    print("\n### T5 расстояние между людьми (фронтал, эталоны по ровным кадрам)")
    res = {}
    for key, nm in (("canon", "max-radius"), ("rcanon", "RMS")):
        ref = {}
        for p in sorted({r["person"] for r in rows}):
            rs = [r for r in rows if r["person"] == p and r["bin"] == "frontal"]
            if len(rs) >= 6:
                ref[p] = np.median(np.stack([r[key] for r in level_set(rs)]), axis=0)
        ps = sorted(ref)
        d = sorted((vdist(ref[a], ref[b]), a, b) for i, a in enumerate(ps) for b in ps[i + 1:])
        vals = [x[0] for x in d]
        fl, tr = [], []
        for p in ps:
            rs = [r for r in rows if r["person"] == p and r["bin"] == "frontal"]
            lvl = level_set(rs)
            fl += [vdist(r[key], ref[p]) for r in lvl]
            tr += [vdist(r[key], ref[p]) for r in rs if abs(r["tilt"]) > 2]
        f, t = float(np.median(fl)), float(np.median(tr))
        res[nm] = {"pairs": len(vals), "min": round(vals[0], 5), "median": round(float(np.median(vals)), 5),
                   "max": round(vals[-1], 5), "floor": round(f, 5), "tilt_residual": round(t, 5),
                   "min_over_residual": round(vals[0] / t, 2), "min_over_floor": round(vals[0] / f, 2),
                   "closest_pair": f"{d[0][1]}/{d[0][2]}"}
        print(f" {nm:12s} пар={len(vals)}  min={vals[0]:.5f} (пара {d[0][1]}/{d[0][2]})  "
              f"медиана={np.median(vals):.5f}  max={vals[-1]:.5f}")
        print(f"     пол={f:.5f}  остаток наклонных={t:.5f}  min_между_людьми/остаток={vals[0]/t:.2f}"
              f"  min_между_людьми/пол={vals[0]/f:.2f}")
    return res


# --------------------------------------------------------------------------- T6
def t6(rows):
    print("\n### T6 ICC по 17 метрикам (фронтал): ровные кадры / наклонные после canon")
    keys = list(I.FEATURE_ORDER)
    fr = [r for r in rows if r["bin"] == "frontal"]
    out = []
    for i, nm in enumerate(keys):
        row = {"metric": nm}
        for tag, pred in (("level", lambda r: abs(r["tilt"]) <= 2), ("tilted", lambda r: abs(r["tilt"]) > 2)):
            means, withins = [], []
            for p in sorted({r["person"] for r in fr}):
                v = [r["v17"][i] for r in fr if r["person"] == p and pred(r) and np.isfinite(r["v17"][i])]
                if len(v) >= 3:
                    means.append(float(np.mean(v)))
                    withins.append(float(np.var(v, ddof=1)))
            b, w = float(np.var(means, ddof=1)) if len(means) >= 3 else float("nan"), float(np.mean(withins))
            row[tag] = round(b / (b + w), 3) if np.isfinite(b) and (b + w) > 1e-12 else None
        out.append(row)
    out.sort(key=lambda d: -(d["level"] or 0))
    print(f"{'metric':24s}{'ICC level':>11s}{'ICC tilted':>12s}")
    for d in out:
        print(f"{d['metric']:24s}{str(d['level']):>11s}{str(d['tilted']):>12s}")
    return out


# --------------------------------------------------------------------------- T7
def t7(rows):
    print("\n### T7 знаковый остаток против yaw: LOPO-регрессия (5 человек -> 6-й)")
    anchor, jitter = {}, {}
    for p in sorted({r["person"] for r in rows}):
        rs = [r for r in rows if r["person"] == p and r["bin"] == "frontal"]
        if len(rs) >= 6:
            anchor[p] = np.median(np.stack([r["v17"] for r in level_set(rs)]), axis=0)
    people = sorted(anchor)
    keys = list(I.FEATURE_ORDER)
    for i, nm in enumerate(keys):
        j = []
        for p in people:
            v = [r["v17"][i] for r in rows if r["person"] == p and r["bin"] == "frontal" and abs(r["tilt"]) <= 2]
            if len(v) > 3:
                j.append(float(np.median(np.abs(np.array(v) - np.median(v)))) * 1.4826)
        jitter[nm] = float(np.median(j)) if j else float("nan")
    worst = ["brow_eye_right_3d", "eye_level_asym", "brow_eye_left_3d", "mouth_nose_offset"]
    bestm = ["nose_axis_bend_3d", "brow_span_3d", "eye_anchor_spacing_3d", "nose_ridge_length_3d"]
    res = []
    for nm in worst + bestm:
        i = keys.index(nm)
        z0, z1, r2o = [], [], []
        for p in people:
            tr = [r for r in rows if r["person"] != p and np.isfinite(r["v17"][i])]
            te = [r for r in rows if r["person"] == p and np.isfinite(r["v17"][i])]
            if len(te) < 5:
                continue
            ytr = np.array([r["yaw"] for r in tr])
            Xtr = np.stack([np.ones_like(ytr), ytr, np.abs(ytr), ytr ** 2], 1)
            y = np.array([r["v17"][i] - anchor[r["person"]][i] for r in tr])
            beta, *_ = np.linalg.lstsq(Xtr, y, rcond=None)
            yte = np.array([r["yaw"] for r in te])
            Xte = np.stack([np.ones_like(yte), yte, np.abs(yte), yte ** 2], 1)
            obs = np.array([r["v17"][i] - anchor[p][i] for r in te])
            pred = Xte @ beta
            st = float(np.sum((obs - obs.mean()) ** 2))
            r2o.append(1.0 - float(np.sum((obs - pred) ** 2)) / st if st > 1e-15 else np.nan)
            den = jitter[nm] if jitter[nm] > 1e-12 else 1e-12
            z0.append(float(np.median(np.abs(obs)) / den))
            z1.append(float(np.median(np.abs(obs - pred)) / den))
        res.append({"metric": nm, "z_before": round(float(np.median(z0)), 2),
                    "z_after_LOPO": round(float(np.median(z1)), 2),
                    "drop_pct": round(100 * (1 - float(np.median(z1)) / float(np.median(z0))), 1),
                    "r2_out": round(float(np.nanmedian(r2o)), 3)})
    print(f"{'metric':24s}{'z до':>8s}{'z после':>10s}{'падение %':>11s}{'R2 вне':>10s}")
    for d in res:
        print(f"{d['metric']:24s}{d['z_before']:>8.2f}{d['z_after_LOPO']:>10.2f}{d['drop_pct']:>11.1f}{d['r2_out']:>10.3f}")
    print(" z здесь - по ВСЕМ 606 кадрам против фронтального якоря, т.е. включает межинную разницу бин")
    return res


# --------------------------------------------------------------------------- T8
def t8(rows):
    print("\n### T8 минимальная видимая добавка")
    # 8a: синтетика в геометрии, один человек, readout локальной шириной (не средним по 106 точкам)
    res = {}
    for p in sorted({r["person"] for r in rows}):
        rs = [r for r in rows if r["person"] == p and r["bin"] == "frontal"]
        if len(rs) < 8:
            continue
        lvl, side = level_set(rs), [r for r in rs if abs(r["tilt"]) > 2]
        if not side:
            continue
        ref = np.median(np.stack([r["canon"] for r in lvl]), axis=0)
        floor = float(np.median([vdist(r["canon"], ref) for r in lvl]))
        resid = float(np.median([vdist(r["canon"], ref) for r in side]))
        w0 = float(np.linalg.norm(ref[ALAR_L] - ref[ALAR_R]))
        jitter_w = float(np.median([abs(float(np.linalg.norm(r["canon"][ALAR_L] - r["canon"][ALAR_R])) - w0)
                                    for r in lvl]))
        print(f" {p}: пол={floor:.5f}  остаток ракурса={resid:.5f}  ширина носа={w0:.4f}  "
              f"дрожание ширины на ровных={jitter_w:.5f} ({100*jitter_w/w0:.2f}%)  наклонных={len(side)}")
        # null = |ширина ровного кадра - ширина эталона|; порог = 90-й перцентиль null
        null = np.array([abs(float(np.linalg.norm(r["canon"][ALAR_L] - r["canon"][ALAR_R])) - w0) for r in lvl])
        thr = float(np.percentile(null, 90))
        own = np.array([float(np.linalg.norm(r["canon"][ALAR_L] - r["canon"][ALAR_R])) for r in side])
        base = float(np.mean(np.abs(own - w0) > thr))
        print(f"   порог пола ({100*thr/w0:.2f}% ширины), доля наклонных кадров выше него БЕЗ добавки = {base:.2f}")
        scan = []
        for s in (0.005, 0.01, 0.015, 0.02, 0.03, 0.05):
            dall = []
            for r in side:
                q = r["canon"].copy()
                cx = 0.5 * (q[ALAR_L, 0] + q[ALAR_R, 0])
                q[ALAR_L, 0] = cx - (cx - q[ALAR_L, 0]) * (1 + s)
                q[ALAR_R, 0] = cx + (q[ALAR_R, 0] - cx) * (1 + s)
                dall.append(vdist(q, ref))
            dev = np.abs(own * (1 + s) - w0)
            scan.append({"shift_pct": round(100 * s, 2),
                         "detect_vs_floor": round(float(np.mean(dev > thr)), 2),
                         "detect_vs_own_median": round(float(np.mean(dev > float(np.median(null)) * 3)), 2),
                         "d_all106": round(float(np.median(dall)), 5),
                         "d_all106_over_resid": round(float(np.median(dall)) / resid, 3)})
        for d in scan:
            print(f"   +{d['shift_pct']:>4.1f}% ширины: кадров выше порога пола={d['detect_vs_floor']:.2f}"
                  f"  выше 3x пола={d['detect_vs_own_median']:.2f}"
                  f"  d(106)={d['d_all106']:.5f} = x{d['d_all106_over_resid']} остатка")
        res["geo_" + p] = {"floor": round(floor, 5), "pose_residual": round(resid, 5),
                           "nose_width": round(w0, 4), "width_jitter": round(jitter_w, 5),
                           "width_floor_thresh_pct": round(100 * thr / w0, 2),
                           "baseline_detect": round(base, 2), "scan": scan}
        break  # один человек, как просил советник

    # 8b: то же в метрическом пространстве по всем 17 метрикам: какой % добавки вообще виден
    print("\n--- 8b: минимальный видимый % по каждой метрике (фронтал) ---")
    keys = list(I.FEATURE_ORDER)
    people = sorted({r["person"] for r in rows})
    table = []
    for i, nm in enumerate(keys):
        means, jit, res_t = {}, [], []
        for p in people:
            v = np.array([r["v17"][i] for r in rows if r["person"] == p and r["bin"] == "frontal"
                          and abs(r["tilt"]) <= 2 and np.isfinite(r["v17"][i])])
            t = np.array([r["v17"][i] for r in rows if r["person"] == p and r["bin"] == "frontal"
                          and abs(r["tilt"]) > 2 and np.isfinite(r["v17"][i])])
            if len(v) >= 3:
                means[p] = float(np.median(v))
                jit.append(float(np.median(np.abs(v - np.median(v)))) * 1.4826)
            if len(t) >= 3 and p in means:
                res_t.append(float(np.median(np.abs(t - means[p]))))
        if len(means) < 4:
            continue
        grand = float(np.median(list(means.values())))
        if abs(grand) < 1e-9:
            continue
        pair = sorted(abs(means[a] - means[b]) for x, a in enumerate(sorted(means)) for b in sorted(means)[x + 1:])
        j, t = float(np.median(jit)), float(np.median(res_t))
        table.append({"metric": nm, "jitter_pct": round(100 * j / abs(grand), 2),
                      "pose_resid_pct": round(100 * t / abs(grand), 2),
                      "min_between_pct": round(100 * pair[0] / abs(grand), 2),
                      "median_between_pct": round(100 * float(np.median(pair)) / abs(grand), 2),
                      "frames_to_resolve_closest": round((t / pair[0]) ** 2, 1) if pair[0] > 1e-12 else None})
    table.sort(key=lambda d: d["min_between_pct"])
    print(f"{'metric':24s}{'джиттер%':>10s}{'остаток%':>10s}{'min межд%':>11s}{'медиана межд%':>14s}{'кадров':>8s}")
    for d in table:
        print(f"{d['metric']:24s}{d['jitter_pct']:>10.2f}{d['pose_resid_pct']:>10.2f}"
              f"{d['min_between_pct']:>11.2f}{d['median_between_pct']:>14.2f}{str(d['frames_to_resolve_closest']):>8s}")
    res["metrics"] = table
    return res


def main():
    rows = load()
    print(f"кадров: {len(rows)}, персон: {len({r['person'] for r in rows})}, бинов: {len({r['bin'] for r in rows})}")
    out = {"T1": t1(rows), "T2": t2(rows), "T3": t3(rows), "T4": t4(rows), "T5": t5(rows),
           "T6": t6(rows), "T7": t7(rows), "T8": t8(rows)}

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, list | tuple):
            return [clean(x) for x in o]
        if isinstance(o, np.generic):
            o = o.item()
        if isinstance(o, float) and not np.isfinite(o):
            return None
        return o

    Path(HERE / "report" / "advisor_tests.json").write_text(
        json.dumps(clean(out), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {HERE / 'report' / 'advisor_tests.json'}")


if __name__ == "__main__":
    main()
