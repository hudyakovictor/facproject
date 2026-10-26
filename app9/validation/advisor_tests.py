#!/usr/bin/env python
"""Мини-тесты 1-8 по замечаниям советника. Данные - кэш .runtime/level_cache (606 кадров),
новых реконструкций нет.

T1 sanity Procrustes: эмпирически проверяем, когда d(best) <= d(canon) (гарантии нет:
    Procrustes минимизирует сумму квадратов, а vdist - среднюю длину).
T2 rotneg на правильном входе: матрица app8 к cam (с z-флипом to_camera) против той же матрицы к canon.
T3 блочный пол шума: эталон без соседей по индексу кадра.
T4 нормировки: боевая RMS по 106 точкам (aligner.normalize_ldm106) против старой max-radius.
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
from morphing.backend.aligner import normalize_ldm106  # noqa: E402

CANON_YAW = {b[0]: float(b[3]) for b in POSE_BINS}
ALAR_L, ALAR_R, NOSE_BASE, NOSE_TIP = 58, 62, 60, 54
NOSE_SET = [NOSE_BASE, ALAR_L, ALAR_R, NOSE_TIP, 51, 52, 53]


def fidx(name):
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else -1


def vdist(a, b, idx=None):
    a, b = np.asarray(a), np.asarray(b)
    if idx is not None:
        a, b = a[idx], b[idx]
    return float(np.mean(np.linalg.norm(a - b, axis=1)))


def proc_rot(A, B):
    U, _, Vt = np.linalg.svd(np.asarray(A).T @ np.asarray(B))
    return U @ np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]) @ Vt


def maxr(p):
    return float(np.max(np.linalg.norm(p, axis=1)))


def load():
    """Одна нормировка с продом: `aligner.normalize_ldm106` (центр и RMS по 106 точкам).

    Кэш level_extract содержал центрированные, но НЕ отмасштабированные точки (баг
    norm()), а нормировка идемпотентна, поэтому старый кэш проходит через неё второй раз
    без изменения — переизвлечение кадров не нужно. Старая нормировка (max-радиус по одной
    крайней точке) остаётся только в диагностике T4 как `m`-колонки, чтобы было видно,
    насколько она расходится с боевой. Кэшированный `v17` пересчитываем из canon: он был
    собран в старом пространстве и на старых эталонах, а метрики и облака должны жить
    в одной нормировке с продом.
    """
    rows = []
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "fail" in r or len(r.get("canon", [])) != 318:
            continue
        r.setdefault("bin", "frontal")
        for k in STATE:
            p = np.asarray(r[k], float).reshape(106, 3)
            p = p - p.mean(axis=0)
            # сырой масштаб кадра: модельные единицы / пиксели. Новые строки кэша несут его
            # отдельно (`k_rawscale`), в старых он восстанавливается как max-радиус.
            r["scale" + k] = float(r.get(k + "_rawscale") or maxr(p))
            r[k] = normalize_ldm106(p)[0]     # боевая нормировка: RMS по 106 точкам
            r["m" + k] = p / maxr(p)          # старая нормировка по одной крайней точке
        r["v17"] = [float(x) for x in np.asarray(I.form_vector(r["canon"]), float)]
        r["fidx"] = fidx(r["frame"])
        r["tilt"] = r["yaw"] - CANON_YAW.get(r["bin"], 0.0)
        r["ok"] = r["fidx"] >= 0
        rows.append(r)
    return [r for r in rows if r["ok"]]


def norm_convention(rows):
    """Расхождение «прод vs валидация» после патча 04 равно нулю по построению: обе стороны
    юстируются одной функцией `aligner.normalize_ldm106` (центр и RMS по 106 точкам).

    Что по-прежнему имеет смысл померить — насколько масштаб по ОДНОЙ крайней точке
    (`max |p|`, старая норма валидации) расходится со средним квадратом по 106 точкам.
    Ниже — разброс max-радиуса этих же 106 точек в RMS-единицах: медиана показывает, во
    сколько раз сдвинутся абсолютные расстояния валидации при переходе со старой нормы на
    новую, а min..max — насколько неустойчив сам старый масштаб от кадра к кадру (из-за него
    пороги калибровки и съезжают). Для прода (масштаб по max-радиусу всех 35 709 вершин)
    сдвиг другой и измерен на сетках: `aligner.MAXR_TO_RMS106` = 1.564.
    """
    vals = np.array([maxr(r[k]) for r in rows for k in STATE], float)
    vals = vals[np.isfinite(vals)]
    return {"median": round(float(np.median(vals)), 4), "min": round(float(vals.min()), 4),
            "max": round(float(vals.max()), 4), "p05": round(float(np.percentile(vals, 5)), 4),
            "p95": round(float(np.percentile(vals, 95)), 4), "n": int(len(vals))}


def level_set(rs):
    lvl = [r for r in rs if abs(r["tilt"]) <= 2.0 and abs(r["pitch"]) <= 5.0]
    if len(lvl) < 3:
        lvl = sorted(rs, key=lambda r: abs(r["tilt"]))[:3]
    return lvl


def R_corr(r, canon_yaw):
    return full_pose_correction_matrix(np.array([r["pitch"], r["yaw"], r["roll"]], np.float32),
                                       np.array([0.0, canon_yaw, 0.0], np.float32))


def column_stats(rs_all, cloud_for, gap=0):
    """По каждой колонке (имя -> функция кадр->облако): пол (leave-one-out, с защитным
    зазором gap по индексу) и расстояние наклонных кадров до эталона.

    Считаем по ЛЮДЯМ: внутри человека медиана, затем медиана по людям. Иначе 28 ровных
    кадров person_01 задавливают 3-5 кадров остальных.
    Возвращает {имя: floor, d_tilt, ratio, n_people, n_tilt}.
    """
    names = list(cloud_for)
    per = {n: {"floor": [], "d": []} for n in names}
    for p in sorted({r["person"] for r in rs_all}):
        rs = [r for r in rs_all if r["person"] == p]
        if len(rs) < 6:
            continue
        lvl, side = level_set(rs), [r for r in rs if abs(r["tilt"]) > 2]
        for n in names:
            L = [cloud_for[n](r) for r in lvl]
            fl = []
            for i, c in enumerate(L):
                pool = [L[j] for j in range(len(L)) if j != i and abs(lvl[j]["fidx"] - lvl[i]["fidx"]) > gap]
                if len(pool) >= 2:
                    fl.append(vdist(c, np.median(np.stack(pool), axis=0)))
            ref = np.median(np.stack(L), axis=0) if L else None
            if ref is None:
                continue
            dd = [vdist(cloud_for[n](r), ref) for r in side
                  if not any(abs(q["fidx"] - r["fidx"]) <= gap for q in lvl)]
            if fl and dd:
                per[n]["floor"].append(float(np.median(fl)))
                per[n]["d"].append(float(np.median(dd)))
    out = {}
    for n in names:
        fl, dd = per[n]["floor"], per[n]["d"]
        if not fl:
            continue
        f, d = float(np.median(fl)), float(np.median(dd))
        out[n] = {"floor": round(f, 5), "d_tilt": round(d, 5), "ratio": round(d / f, 2),
                  "n_people": len(fl), "n_tilt": len(dd)}
    return out


def show(title, stats, order=None, gap=None):
    """Таблица по колонкам `column_stats`. `gap` — зазор между людьми в тех же единицах:
    с ним `d` перестаёт читаться через ratio (ratio в профиле врёт, см. T2) и становится
    величиной с линейкой. Строки с `d/gap < 1` лежат ВНУТРИ межличностного разброса."""
    print(title)
    head = f"{'колонка':22s}{'людей':>6s}{'n накл':>7s}{'пол(LOO)':>10s}{'d наклон':>11s}{'ratio':>8s}"
    if gap:
        head += f"{'d/зазор':>9s}"
    print(head)
    for n in (order or stats.keys()):
        s = stats.get(n)
        if not s:
            continue
        line = f"{n:22s}{s['n_people']:>6d}{s['n_tilt']:>7d}{s['floor']:>10.5f}{s['d_tilt']:>11.5f}{s['ratio']:>8.2f}"
        if gap:
            line += f"{s['d_tilt'] / gap:>9.2f}"
        print(line)


# --------------------------------------------------------------------------- T1
def t1(rows):
    print("\n### T1 Sanity Procrustes: эмпирика d(best) <= d(canon) (гарантии нет)")
    per = {}
    for r in rows:
        per.setdefault((r["person"], r["bin"]), []).append(r)
    cand = [r for rs in per.values() if len(rs) >= 6 for r in rs]
    cand.sort(key=lambda r: -abs(r["tilt"]))
    margins = []
    print(f"{'person/bin':26s}{'frame':16s}{'tilt':>7s}{'d_canon':>10s}{'d_best':>10s}{'выигрыш':>10s}")
    for r in cand[:20]:
        rc = np.median(np.stack([q["canon"] for q in level_set(per[(r["person"], r["bin"])])]), axis=0)
        d0 = vdist(r["canon"], rc)
        d1 = vdist(r["canon"] @ proc_rot(r["canon"], rc), rc)
        margins.append(d0 - d1)
        print(f"{r['person']+'/'+r['bin']:26s}{r['frame']:16s}{r['tilt']:>7.1f}{d0:>10.5f}{d1:>10.5f}{d0-d1:>10.5f}")
    # Procrustes минимизирует сумму квадратов, а vdist - среднюю длину, поэтому теоремы
    # «best <= canon» нет. Проверяем эмпирически на ВСЕХ кадрах, а не на 20.
    allm, viol = [], 0
    for rs in per.values():
        rc = np.median(np.stack([q["canon"] for q in level_set(rs)]), axis=0)
        for r in rs:
            d0 = vdist(r["canon"], rc)
            d1 = vdist(r["canon"] @ proc_rot(r["canon"], rc), rc)
            allm.append(d0 - d1)
            viol += int(d1 > d0 + 1e-12)
    share = 1.0 - viol / len(allm)
    print(f"нарушений d_best > d_canon: {viol} из {len(allm)} кадров; доля «не хуже canon» {share:.3f}; "
          f"медиана выигрыша = {float(np.median(allm)):.7f}, 5-й перцентиль = {float(np.percentile(allm, 5)):.7f}")
    return {"violations": viol, "n": len(allm), "share_gain": round(share, 4),
            "median_gain": round(float(np.median(allm)), 6),
            "p05_gain": round(float(np.percentile(allm, 5)), 6)}


# --------------------------------------------------------------------------- T2
def t2(rows, gap=None):
    print("\n### T2 rotneg на правильном входе. R_corr = (R_target R_actual^T) - в матрице app8")
    print(" С патча 03 прод доворот НЕ применяет: колонка `canon x R_corr` — это старый прод,")
    print(" она оставлена как контроль «что мы убрали». Сравнивать состояния между собой по")
    print(" ratio нельзя (в профиле ratio ниже у старого прода просто потому, что поворот")
    print(" домножает на одно и то же число); для сравнения состояний — абсолютный d и")
    if gap is None:
        print(" зазор между людьми. Колонка d/зазор не выведена: T5 не посчитан раньше.")
    else:
        print(f" зазор между людьми из T5 = {gap:.5f}. Колонка d/зазор: <1 — разница лежит")
        print(" внутри межличностного разброса (личность не различима), >1 — во сколько раз")
        print(" d больше ближайшей пары разных людей.")
    out = {}
    for b in ("frontal", "left_profile", "right_profile"):
        cy = CANON_YAW.get(b, 0.0)

        def cloud(r, n, cy=cy):
            M = R_corr(r, cy)
            if n == "canon":                       # mesh БЕЗ позы = текущий прод (патч 03)
                return r["canon"]
            if n == "canon x R_corr":              # так делал прод до патча 03 (доворот в канон бина)
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
        show(f"--- бин {b} (канонический yaw {cy:+.0f}) ---", stats, names, gap=gap)
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
    print(" при gap>15 большинство ровных кадров отсекаются: их burst короче 15 индексов")

    # 3b: d между ПАРАМИ ровных кадров. Такая пара примерно в sqrt(2) больше, чем
    # расстояние одного кадра до истинного значения, поэтому независимую оценку пола
    # делим на sqrt(2) (предположение независимого шума - на непрерывном прогоне оно
    # оптимистично, и это надо держать в голове, читая ratio ниже).
    print("\n--- 3b: d между парами ровных фронтальных кадров против зазора по индексу ---")
    buck = [(0, 2), (2, 5), (5, 15), (15, 50), (50, 10 ** 9)]
    print(f"{'зазор':>12s}{'пар':>7s}{'d canon':>10s}{'d/sqrt2':>10s}{'d cam':>10s}")
    curve, indep = {}, {}
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
        mc = float(np.median(dc)) if dc else float("nan")
        mm = float(np.median(dm)) if dm else float("nan")
        curve[tag] = {"pairs": len(dc), "canon": round(mc, 5) if dc else None,
                      "canon_over_sqrt2": round(mc / 2 ** 0.5, 5) if dc else None,
                      "cam": round(mm, 5) if dm else None}
        if lo >= 5 and dc:
            indep[f"gap_gt_{lo}"] = mc / 2 ** 0.5
        print(f"{tag:>12s}{len(dc):>7d}{mc:>10.5f}{mc / 2 ** 0.5:>10.5f}{mm:>10.5f}"
              if dm else f"{tag:>12s}{len(dc):>7d}{mc:>10.5f}{mc / 2 ** 0.5:>10.5f}{'-':>10s}")

    # 3c: ровные кадры каждого человека - ОДИН непрерывный прогон (всплесков нет), поэтому
    # блочный пол считаем split-half: кадр против медианы ДРУГОЙ половины его же ровных кадров
    print("\n--- 3c: split-half пол (кадр против эталона другой половины того же прогона) ---")
    floor, floorc, dts, dtsc, msize, drift = [], [], [], [], [], []
    for p in sorted({r["person"] for r in fr}):
        rs = [x for x in fr if x["person"] == p]
        lvl = sorted(level_set(rs), key=lambda r: r["fidx"])
        if len(lvl) < 6:
            continue
        h = len(lvl) // 2
        A, B = lvl[:h], lvl[h:]
        msize.append(min(h, len(lvl) - h))
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
    d_can = float(np.median(dts))
    print(f" людей {len(drift)}: пол(canon, split-half)={f:.5f} (кадров {len(floor)}),"
          f"  d наклонных={d_can:.5f},  ratio={d_can / f:.2f}")
    print(f"  пол(cam, split-half)={float(np.median(floorc)):.5f}  d(cam наклонных)={float(np.median(dtsc)):.5f}"
          f"  ratio cam={float(np.median(dtsc)) / float(np.median(floorc)):.2f}")
    print(f"  разница медиан yaw между половинами (загрязнение пола позой): "
          f"med={float(np.median(drift)):.2f} max={max(drift):.2f} град")
    ms = float(np.median(msize))
    print(f"  размер меньшей половины = {ms:.0f} кадров -> эталон сам шумит, завышение пола ~{np.sqrt(1 + 1 / ms):.2f}x")
    for tag, val in sorted(indep.items()):
        print(f"  независимый пол из пар ({tag}, canon/sqrt2) = {val:.5f} -> ratio = {d_can / val:.2f}")
    print(f"  сравнение: пол LOO gap>0 = {out['gap>0']['canon']['floor']}, ratio = {out['gap>0']['canon']['ratio']}")
    out["3b_curve"] = curve
    out["3c_splithalf"] = {"floor_canon": round(f, 5), "floor_cam": round(float(np.median(floorc)), 5),
                           "d_tilt": round(d_can, 5), "ratio_canon": round(d_can / f, 2),
                           "yaw_drift_median_deg": round(float(np.median(drift)), 2),
                           "n_floor": len(floor), "half_size_median": int(ms),
                           "independent_floor_over_sqrt2": {k: round(v, 5) for k, v in indep.items()},
                           "ratio_vs_independent": {k: round(d_can / v, 2) for k, v in indep.items()}}
    return out


# --------------------------------------------------------------------------- T4
def t4(rows):
    print("\n### T4 нормировки: RMS по 106 точкам (боевая) против max-radius (старая aligner)")
    print(" после исправления norm() и перехода на normalize_ldm106 все облака отмасштабированы;")
    print(" колонки отличаются только выбором масштаба: RMS по 106 точкам против max-радиуса")
    print(" одной крайней точки. Разница — систематический коэффициент и его гуляние по кадрам.")
    fr = [r for r in rows if r["bin"] == "frontal"]
    cf = {}
    for st in STATE:
        cf[st + " rms106"] = (lambda r, s=st: r[s])
        cf[st + " maxr"] = (lambda r, s=st: r["m" + s])
    stats = column_stats(fr, cf)
    show("--- фронтал ---", stats, list(cf))
    spread = {}
    for st in STATE:
        sc = [r["scale" + st] for r in fr]
        rel = [maxr(r[st]) for r in fr]   # max-радиус ПОСЛЕ RMS-нормировки = форма, не масштаб
        spread[st] = {"raw_min": round(min(sc), 4), "raw_median": round(float(np.median(sc)), 4),
                      "raw_max": round(max(sc), 4), "maxr_over_rms": round(float(np.median(rel)), 4),
                      "maxr_over_rms_min": round(min(rel), 4), "maxr_over_rms_max": round(max(rel), 4)}
        print(f" {st}: сырой масштаб кадра min/med/max = {min(sc):.4f}/{float(np.median(sc)):.4f}/{max(sc):.4f}"
              f"   |  после RMS-нормировки max-радиус = {min(rel):.4f}/{float(np.median(rel)):.4f}/{max(rel):.4f}")
    print(" у two_d сырой масштаб - пиксели (размер лица на фото), у cam/canon - модельные единицы;")
    print(" именно этот разброс раньше выдавался за «неустойчивость max-radius»")
    print(" max-радиус в RMS-единицах скачет по кадрам: крайняя вершина - не мера формы,")
    print(" поэтому боевая нормировка считает средний квадрат по всем 106 точкам")
    stats["_raw_scale_spread"] = spread
    return stats


# --------------------------------------------------------------------------- T5
def t5(rows):
    print("\n### T5 расстояние между людьми (фронтал, эталоны по ровным кадрам)")
    res = {}
    for key, nm in (("canon", "RMS-106"), ("mcanon", "max-radius")):
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
    print("\n### T6 ICC по 17 метрикам (фронтал): ровные / с поправкой на автокорреляцию / наклонные")
    print(" ровный = level_set (|tilt|<=2 и |pitch|<=5) - единый критерий со всеми тестами")
    print(" оговорка: ровные кадры идут непрерывным прогоном, соседние кадры почти одинаковы,")
    print(" поэтому выборочная внутривидовая дисперсия занижена и ICC завышен. Поправка:")
    print(" s2_истинная = s2 / (1 - (2/n) * sum_k (1-k/n) rho_k) - формула Тьюки для E[s2]")
    print(" при автокорреляции rho_k. thin3 не считаем: у 4 из 6 людей прогон короче 6 кадров.")
    keys = list(I.FEATURE_ORDER)
    fr = [r for r in rows if r["bin"] == "frontal"]
    people = sorted({r["person"] for r in fr})
    series = {}
    for p in people:
        series[p] = sorted(level_set([r for r in fr if r["person"] == p]), key=lambda r: r["fidx"])
    tilt_ids = {id(r) for r in fr if abs(r["tilt"]) > 2}

    def icc(i, sel):
        means, withins = [], []
        for p in people:
            v = [r["v17"][i] for r in fr if r["person"] == p and id(r) in sel[p] and np.isfinite(r["v17"][i])]
            if len(v) >= 3:
                means.append(float(np.mean(v)))
                withins.append(float(np.var(v, ddof=1)))
        b = float(np.var(means, ddof=1)) if len(means) >= 3 else float("nan")
        w = float(np.mean(withins))
        return round(b / (b + w), 3) if np.isfinite(b) and (b + w) > 1e-12 else None

    def icc_acf(i):
        """ICC с внутривидовой дисперсией, раздутой по оценке автокорреляции прогона."""
        per = []
        for p in people:
            v = np.array([r["v17"][i] for r in series[p]], float)
            v = v[np.isfinite(v)]
            if v.size >= 3:
                per.append((v, v - v.mean()))
        if len(per) < 3:
            return None, None
        den = sum(float(np.sum(res * res)) for _, res in per)
        if den <= 1e-15:
            return None, None
        rho1 = sum(float(np.sum(res[:-1] * res[1:])) for _, res in per) / den
        rho2 = sum(float(np.sum(res[:-2] * res[2:])) for _, res in per if res.size > 2) / den
        means = [float(v.mean()) for v, _ in per]
        b = float(np.var(means, ddof=1))
        cor = []
        for v, _ in per:
            n = v.size
            f = 1.0 - (2.0 / n) * ((1.0 - 1.0 / n) * rho1 + (1.0 - 2.0 / n) * rho2 * (n > 2))
            cor.append(float(np.var(v, ddof=1)) / max(f, 0.2))   # пол не занижаем ниже 0.2*s2
        icc_cor = round(b / (b + float(np.mean(cor))), 3) if b + float(np.mean(cor)) > 1e-12 else None
        return icc_cor, round(rho1, 3) if icc_cor is not None else None

    out = []
    for i, nm in enumerate(keys):
        raw = icc(i, {p: {id(r) for r in series[p]} for p in people})
        tilted = icc(i, {p: tilt_ids for p in people})
        cor, rho = icc_acf(i)
        out.append({"metric": nm, "level": raw, "level_acf": cor, "rho1": rho, "tilted": tilted})
    out.sort(key=lambda d: -(d["level"] or 0))
    print(f"{'metric':24s}{'ICC level':>11s}{'ICC +acf':>10s}{'rho1':>7s}{'ICC tilted':>12s}")
    for d in out:
        print(f"{d['metric']:24s}{str(d['level']):>11s}{str(d['level_acf']):>10s}"
              f"{str(d['rho1']):>7s}{str(d['tilted']):>12s}")
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
            keep = {id(q) for q in level_set([q for q in rows if q["person"] == p and q["bin"] == "frontal"])}
            v = [r["v17"][i] for r in rows if id(r) in keep]
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
    print(" пороги обнаружения - в абсолютных единицах и с блок-бутстрапом в t8_absolute.py;")
    print(" здесь только геометрия: как добавка к ширине носа меняет d(106) до ровного эталона")
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
        print(f" {p}: пол={floor:.5f}  остаток ракурса={resid:.5f}  ширина носа={w0:.4f}  наклонных={len(side)}")
        scan = []
        for s in (0.01, 0.02, 0.03, 0.05):
            dall = []
            for r in side:
                q = r["canon"].copy()
                cx = 0.5 * (q[ALAR_L, 0] + q[ALAR_R, 0])
                q[ALAR_L, 0] = cx - (cx - q[ALAR_L, 0]) * (1 + s)
                q[ALAR_R, 0] = cx + (q[ALAR_R, 0] - cx) * (1 + s)
                dall.append(vdist(q, ref))
            row = {"shift_pct": round(100 * s, 2), "d_all106": round(float(np.median(dall)), 5),
                   "gain_over_residual": round((float(np.median(dall)) - resid) / resid, 4)}
            scan.append(row)
            print(f"   +{100 * s:>4.1f}%: d(106)={row['d_all106']:.5f}"
                  f"  прирост сверх остатка = x{row['gain_over_residual']}")
        res["geo_" + p] = {"floor": round(floor, 5), "pose_residual": round(resid, 5),
                           "nose_width": round(w0, 4), "n_tilt": len(side), "scan": scan}
    res["note"] = "прошлая версия 8a со статистикой |own*(1+s)-ref| удалена: она немонотонна"
    return res


def main():
    rows = load()
    print(f"кадров: {len(rows)}, персон: {len({r['person'] for r in rows})}, бинов: {len({r['bin'] for r in rows})}")
    nc = norm_convention(rows)
    print(f" нормировка: max-радиус в RMS-единицах (старый масштаб / новый) = "
          f"med {nc['median']}  p05..p95 {nc['p05']}..{nc['p95']}  min..max {nc['min']}..{nc['max']}  n={nc['n']}")
    # T5 идёт раньше T2: зазор между людьми нужен колонке T2 «d/зазор» (ratio для сравнения
    # состояний не годится, см. docstring t2).
    t1_out = t1(rows)
    t5_out = t5(rows)
    gap = t5_out.get("RMS-106", {}).get("min")
    out = {"norm_convention": nc, "T1": t1_out, "T2": t2(rows, gap=gap), "T3": t3(rows),
           "T4": t4(rows), "T5": t5_out,
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
