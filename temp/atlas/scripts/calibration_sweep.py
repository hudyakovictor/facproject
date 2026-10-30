"""Калибровочный полигон: покрытие, представления, веса, z-карта.

Отвечает на четыре вопроса из плана второго этапа, не меняя приложение:

  A. покрытие person x pose_bin: сколько кадров, какой yaw, резкость, сколько пар;
  B. sweep представлений: identity / vertices / identity + доля expression,
     плюс регионы лица и нормальная компонента расстояния;
  C. веса шума: per-vertex sigma по same-person парам чётных кадров,
     оценка на нечётных — уменьшает ли это within без падения AUC;
  D. z-карта: d_i / sigma_i вместо сырого d_i.

Сигма обучается только на чётных кадрах, метрики считаются только на нечётных,
поэтому оценка в C и D не видит тех же пар, на которых подбирались веса.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 python scripts/calibration_sweep.py
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from calibration_check import ingest_and_process, select_frames  # noqa: E402

BINS = [
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
]
# Регионы задаются индексами ldm68: геометрия зоны считается по этим точкам.
REGIONS = {
    "jaw": list(range(0, 17)),
    "brows": list(range(17, 27)),
    "nose": list(range(27, 36)),
    "eyes": list(range(36, 48)),
    "mouth": list(range(48, 68)),
}
REPS = ("identity", "vertices", "identity+0.3exp", "identity+0.6exp")


class _Job:
    """Минимальный стенд-ин объекта задачи для storage.process."""

    def __init__(self):
        self.id = "calibration-sweep"


def vertex_normals(mean: np.ndarray, tri: np.ndarray) -> np.ndarray:
    out = np.zeros_like(mean, dtype=np.float64)
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    n = np.cross(mean[b] - mean[a], mean[c] - mean[a])
    for k in range(3):
        np.add.at(out, tri[:, k], n)
    return (out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)).astype(
        np.float32
    )


def load_frames(selected):
    from server import storage

    frames = []
    for person, rows in selected.items():
        for order, row in enumerate(rows):
            record = storage.photo(row["id"])
            meta_path = storage.feature_path(record).with_name("meta.json")
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            with np.load(storage.feature_path(record)) as handle:
                vertices = np.asarray(handle["vertices"], np.float32)
                identity = np.asarray(handle["identity"], np.float32)
                yaw = float(np.degrees(np.ravel(handle["alpha"])[225]))
            frames.append(
                {
                    "id": row["id"],
                    "person": person,
                    "frame": row["frame"],
                    "bin": row["bin"],
                    "order": order,
                    "yaw": yaw,
                    "sharpness": float(meta.get("sharpness", float("nan"))),
                    "confidence": float(
                        (meta.get("alignment") or {}).get("confidence", float("nan"))
                    ),
                    "vertices": vertices,
                    "identity": identity,
                    "expression": vertices - identity,
                }
            )
    return frames


def normalize_scale(frames, lm):
    """Та же нормализация, что в heatmap: центр и IOD по уголкам глаз."""
    left, right = int(lm[36]), int(lm[45])
    for f in frames:
        v = f["vertices"]
        center = (v[left] + v[right]) / 2
        iod = max(float(np.linalg.norm(v[left] - v[right])), 1e-8)
        for key in ("vertices", "identity"):
            f[key] = ((f[key] - center) / iod).astype(np.float32)
        f["expression"] = f["vertices"] - f["identity"]
    return frames


def rep_arrays(frames, name):
    """Материализует представление целиком: 210 x 35709 x 3 float32 ≈ 90 MB."""
    if name == "identity":
        return [f["identity"] for f in frames]
    if name == "vertices":
        return [f["vertices"] for f in frames]
    weight = float(name.split("+")[1].replace("exp", ""))
    return [f["identity"] + weight * f["expression"] for f in frames]


def pair_blocks(frames, min_gap):
    """Внутри-пары (все и только нечётные кадры) и подвыборка между-пар."""
    by_person = defaultdict(list)
    for i, f in enumerate(frames):
        by_person[f["person"]].append(i)

    within, within_odd = [], []
    for person, ids in by_person.items():
        ids = sorted(ids, key=lambda i: frames[i]["frame"])
        for a, b in itertools.combinations(ids, 2):
            if abs(frames[a]["frame"] - frames[b]["frame"]) < min_gap:
                continue
            within.append((a, b))
            if frames[a]["order"] % 2 == 1 and frames[b]["order"] % 2 == 1:
                within_odd.append((a, b))
    even = {p: [i for i in ids if frames[i]["order"] % 2 == 0]
            for p, ids in by_person.items()}
    return by_person, within, within_odd, even


def fit_sigma(frames, arrays, even, min_gap):
    """Per-vertex sigma по same-person парам чётных кадров (только они)."""
    n = len(frames[0]["identity"])
    total = np.zeros((n, 3), np.float64)
    total_sq = np.zeros((n, 3), np.float64)
    count = 0
    for person, ids in even.items():
        for a, b in itertools.combinations(ids, 2):
            if abs(frames[a]["frame"] - frames[b]["frame"]) < min_gap:
                continue
            diff = (arrays[a] - arrays[b]).astype(np.float64)
            total += diff
            total_sq += diff * diff
            count += 1
    if count < 3:
        raise SystemExit("слишком мало чётных пар для оценки sigma")
    mean = total / count
    var = np.maximum(total_sq / count - mean * mean, 0.0)
    sigma = np.sqrt(var).mean(axis=1)
    floor = float(np.median(sigma)) * 0.25
    return np.maximum(sigma, floor).astype(np.float32), count


def pair_metrics(a, b, normals, sigma, inv_sum, lm, regions, heavy=True):
    diff = a - b
    e = np.sqrt((diff * diff).sum(axis=1))
    normal = np.abs((diff * normals).sum(axis=1))
    z = e / sigma
    out = {
        "euclid": float(e.mean()),
        "normal": float(normal.mean()),
        "weighted": float((e / sigma).sum() / inv_sum),
        "z_mean": float(z.mean()),
    }
    if not heavy:
        return out
    out["z_p95"] = float(np.percentile(z, 95))
    out["z_frac3"] = float((z > 3).mean())
    for name, idx in regions.items():
        out[f"region_{name}"] = float(e[idx].mean())
    return out


def auc(neg, pos):
    from sklearn.metrics import roc_auc_score

    y = np.concatenate([np.zeros(len(neg)), np.ones(len(pos))])
    s = np.concatenate([neg, pos])
    return round(float(roc_auc_score(y, s)), 4)


def summarize(values):
    v = np.asarray(values, np.float64)
    if v.size == 0:
        return {"n": 0}
    return {
        "n": int(v.size),
        "mean": round(float(v.mean()), 5),
        "median": round(float(np.median(v)), 5),
        "p90": round(float(np.percentile(v, 90)), 5),
        "std": round(float(v.std()), 5),
    }


def evaluate(frames, arrays, normals, sigma, inv_sum, lm, regions, within, between,
             heavy=True, keep=False):
    keys = ["euclid", "normal", "weighted", "z_mean"]
    if heavy:
        keys += ["z_p95", "z_frac3", *(f"region_{r}" for r in regions)]
    w = {k: [] for k in keys}
    b = {k: [] for k in keys}
    for a, c in within:
        for k, v in pair_metrics(arrays[a], arrays[c], normals, sigma, inv_sum, lm,
                                 regions, heavy).items():
            w[k].append(v)
    for a, c in between:
        for k, v in pair_metrics(arrays[a], arrays[c], normals, sigma, inv_sum, lm,
                                 regions, heavy).items():
            b[k].append(v)
    rows = {}
    for k in keys:
        wv, bv = np.asarray(w[k]), np.asarray(b[k])
        rows[k] = {
            "within": summarize(wv),
            "between": summarize(bv),
            "ratio": round(float(bv.mean() / wv.mean()), 3) if wv.mean() else None,
            "auc": auc(wv, bv),
        }
    if keep:
        return rows, w, b
    return rows


def auc_delta_ci(frames, within, between, wa, wb, ba, bb, rounds, seed):
    """Парный bootstrap: AUC(weighted) − AUC(euclid) на тех же парах.

    Ресэмплируются кадры внутри человека (с возвращением), пары строятся заново,
    поэтому корреляция пар, делящих общий кадр, попадает в разброс.
    """
    rng = random.Random(seed)
    wmap = {}
    for (a, b), x, y in zip(within, wa, wb):
        wmap[(a, b)] = wmap[(b, a)] = (x, y)
    bmap = {}
    for (a, b), x, y in zip(between, ba, bb):
        bmap[(a, b)] = bmap[(b, a)] = (x, y)
    people = sorted({f["person"] for f in frames if f["order"] % 2 == 1})
    by_person = {p: [i for i, f in enumerate(frames)
                     if f["person"] == p and f["order"] % 2 == 1] for p in people}
    deltas = []
    for _ in range(rounds):
        chosen = [rng.choices(by_person[p], k=len(by_person[p])) for p in people]
        wv, bv = [], []
        for ch in chosen:
            for a, b in itertools.combinations(ch, 2):
                hit = wmap.get((a, b))
                if hit:
                    wv.append(hit)
        for p1, p2 in itertools.combinations(range(len(chosen)), 2):
            for a in chosen[p1]:
                for b in chosen[p2]:
                    hit = bmap.get((a, b))
                    if hit:
                        bv.append(hit)
        if len(wv) < 10 or len(bv) < 10:
            continue
        wa_, wb_ = zip(*wv)
        ba_, bb_ = zip(*bv)
        deltas.append(auc(wb_, bb_) - auc(wa_, ba_))
    if not deltas:
        return None
    deltas.sort()
    return {
        "mean": round(float(np.mean(deltas)), 4),
        "lo": round(deltas[int(0.025 * len(deltas))], 4),
        "hi": round(deltas[int(0.975 * len(deltas)) - 1], 4),
        "p_positive": round(float(np.mean(np.asarray(deltas) > 0)), 3),
        "rounds": rounds,
    }


def breakdown(frames, within, wv):
    """Разрез within-пар: один бин против перехода между бинами + по бинам."""
    def row(items):
        if not items:
            return None
        e = np.asarray([x for x, _ in items])
        w = np.asarray([y for _, y in items])
        return {"n": int(e.size), "euclid": round(float(e.mean()), 5),
                "weighted": round(float(w.mean()), 5),
                "delta": round(100 * (float(w.mean()) / float(e.mean()) - 1), 1)}

    zipped = [((a, b), x, y) for (a, b), x, y in
              zip(within, wv["euclid"], wv["weighted"])]
    same = [(x, y) for (a, b), x, y in zipped if frames[a]["bin"] == frames[b]["bin"]]
    cross = [(x, y) for (a, b), x, y in zipped if frames[a]["bin"] != frames[b]["bin"]]
    per_bin = {}
    for name in BINS:
        items = [(x, y) for (a, b), x, y in zipped
                 if frames[a]["bin"] == name and frames[b]["bin"] == name]
        if items:
            per_bin[name] = row(items)
    return {"same_bin": row(same), "cross_bin": row(cross), "per_bin": per_bin}


def frontal_check(frames, arrays, sigma, inv, gap):
    """Индикативная проверка фронтальных пар (только нечётные кадры, n мал)."""
    by = defaultdict(list)
    for i, f in enumerate(frames):
        if f["bin"] == "frontal" and f["order"] % 2 == 1:
            by[f["person"]].append(i)
    items = [(a, b) for ids in by.values() for a, b in itertools.combinations(ids, 2)
             if abs(frames[a]["frame"] - frames[b]["frame"]) >= gap]
    if not items:
        return None
    e, w = [], []
    for a, b in items:
        d = np.sqrt(((arrays[a] - arrays[b]) ** 2).sum(axis=1))
        e.append(float(d.mean()))
        w.append(float((d / sigma).sum() / inv))
    return {"n": len(items), "gap": gap,
            "euclid": round(float(np.mean(e)), 5),
            "weighted": round(float(np.mean(w)), 5),
            "delta": round(100 * (float(np.mean(w)) / float(np.mean(e)) - 1), 1),
            "frames": sorted({int(frames[a]["frame"]) for a, _ in items}
                             | {int(frames[b]["frame"]) for _, b in items})}


def lopo_check(frames, arrays, min_gap, max_between=600, seed=42):
    """Leave-one-person-out: sigma по чужим людям, проверка на отложенном."""
    rng = random.Random(seed)
    people = sorted({f["person"] for f in frames})
    idx = defaultdict(list)
    for i, f in enumerate(frames):
        idx[f["person"]].append(i)
    rows = []
    for p in people:
        even = {q: [i for i in idx[q] if frames[i]["order"] % 2 == 0]
                for q in people if q != p}
        sigma, pairs = fit_sigma(frames, arrays, even, min_gap)
        inv = float((1 / sigma).sum())
        mine = [i for i in idx[p] if frames[i]["order"] % 2 == 1]
        others = [i for q in people if q != p
                  for i in idx[q] if frames[i]["order"] % 2 == 1]
        within = [(a, b) for a, b in itertools.combinations(mine, 2)
                  if abs(frames[a]["frame"] - frames[b]["frame"]) >= min_gap]
        between = [(a, b) for a in mine for b in others]
        if len(between) > max_between:
            between = rng.sample(between, max_between)
        if len(within) < 10:
            continue
        e_w, w_w, e_b, w_b = [], [], [], []

        def measure(items, e_out, w_out):
            for a, b in items:
                d = np.sqrt(((arrays[a] - arrays[b]) ** 2).sum(axis=1))
                e_out.append(float(d.mean()))
                w_out.append(float((d / sigma).sum() / inv))

        measure(within, e_w, w_w)
        measure(between, e_b, w_b)
        rows.append({"person": p, "sigma_pairs": pairs, "n_within": len(e_w),
                     "within_euclid": round(float(np.mean(e_w)), 5),
                     "within_weighted": round(float(np.mean(w_w)), 5),
                     "auc_euclid": auc(e_w, e_b),
                     "auc_weighted": auc(w_w, w_b)})
    if not rows:
        return None
    deltas = [r["auc_weighted"] - r["auc_euclid"] for r in rows]
    return {"rows": rows, "n": len(rows),
            "mean_delta_auc": round(float(np.mean(deltas)), 4),
            "min_delta_auc": round(min(deltas), 4),
            "wins": sum(1 for d in deltas if d > 0)}


def gap_counts(frames, gaps=(1, 5, 10, 20, 30)):
    """Сколько within-пар остаётся при разных хронологических зазорах."""
    by = defaultdict(list)
    for i, f in enumerate(frames):
        by[f["person"]].append(i)
    out = {}
    for gap in gaps:
        same = cross = 0
        for ids in by.values():
            ids = sorted(ids, key=lambda i: frames[i]["frame"])
            for a, b in itertools.combinations(ids, 2):
                if frames[b]["frame"] - frames[a]["frame"] < gap:
                    continue
                if frames[a]["bin"] == frames[b]["bin"]:
                    same += 1
                else:
                    cross += 1
        out[str(gap)] = {"same": same, "cross": cross}
    return out


def coverage(frames):
    cells = defaultdict(list)
    for f in frames:
        cells[(f["person"], f["bin"])].append(f)
    rows = []
    for person in sorted({f["person"] for f in frames}):
        for name in BINS:
            items = cells.get((person, name), [])
            if not items:
                continue
            yaw = np.array([f["yaw"] for f in items])
            sharp = np.array([f["sharpness"] for f in items])
            rows.append({
                "person": person,
                "bin": name,
                "n": len(items),
                "yaw_min": round(float(yaw.min()), 1),
                "yaw_max": round(float(yaw.max()), 1),
                "yaw_spread": round(float(yaw.max() - yaw.min()), 1),
                "sharpness": round(float(np.nanmean(sharp)), 1),
                "frames": [f["frame"] for f in items],
            })
    return rows


def transition_counts(coverage_rows, min_gap):
    """Сколько пар приходится на каждый переход между бинами."""
    by = defaultdict(list)
    for c in coverage_rows:
        by[c["person"]].extend((f, c["bin"]) for f in c["frames"])
    cell = defaultdict(int)
    for items in by.values():
        for (fa, ba), (fb, bb) in itertools.combinations(sorted(items), 2):
            if fb - fa < min_gap:
                continue
            cell[tuple(sorted((ba, bb)))] += 1
    return cell


def cluster_bootstrap(frames, within, dist, rounds, seed):
    """Ресэмплинг кадров внутри человека, пары пересобираются заново."""
    rng = random.Random(seed)
    by_person = defaultdict(list)
    for i, f in enumerate(frames):
        by_person[f["person"]].append(i)
    lookup = {tuple(sorted((a, b))): v for (a, b), v in zip(within, dist)}
    samples = []
    for _ in range(rounds):
        picked, values = [], []
        for person, ids in by_person.items():
            chosen = set(rng.choices(ids, k=len(ids)))
            picked.append(chosen)
        for chosen in picked:
            idx = sorted(chosen)
            for a, b in itertools.combinations(idx, 2):
                key = (a, b)
                if key in lookup:
                    values.append(lookup[key])
        if values:
            samples.append(float(np.mean(values)))
    if not samples:
        return None
    samples.sort()
    return {
        "lo": round(samples[int(0.025 * len(samples))], 5),
        "hi": round(samples[int(0.975 * len(samples)) - 1], 5),
        "rounds": rounds,
    }


def heat_figure(frames, arrays, sigma, normals, tri, out_path, size=300, vmax=0.06,
                zmax=4.0):
    """d_i, нормальная компонента и z_i для пары «фронтал ↔ профиль»."""
    from calibration_check import compose_rows, heat_panel

    frontal = [i for i, f in enumerate(frames) if f["bin"] == "frontal"]
    profile = [i for i, f in enumerate(frames)
               if f["bin"] in ("left_profile", "right_profile")]
    pair = next(
        ((i, j) for i in frontal for j in profile
         if frames[i]["person"] == frames[j]["person"]),
        None,
    )
    if pair is None:
        return None
    i, j = pair
    a, b = arrays[i], arrays[j]
    diff = a - b
    e = np.sqrt((diff * diff).sum(axis=1))
    z = e / sigma
    normal = np.abs((diff * normals).sum(axis=1))
    rows = [
        [heat_panel(e, a, tri, size, vmax),
         heat_panel(normal, a, tri, size, vmax * 0.6),
         heat_panel(z, a, tri, size, zmax)],
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    compose_rows(rows, out_path)
    return {"file": str(out_path.relative_to(ROOT)),
            "pair": [frames[i]["frame"], frames[j]["frame"]],
            "person": frames[i]["person"],
            "bins": [frames[i]["bin"], frames[j]["bin"]],
            "euclid": round(float(e.mean()), 5),
            "normal": round(float(normal.mean()), 5),
            "z_mean": round(float(z.mean()), 3),
            "z_p95": round(float(np.percentile(z, 95)), 3),
            "z_frac_above_3": round(float((z > 3).mean()), 3)}


def write_report(path, payload):
    out = []
    add = out.append
    add("# Калибровочный полигон · этап 2\n")
    add(f"Корпус: {payload['sampled']} кадров · внутри-пар {payload['n_within']} "
        f"· между-пар {payload['n_between']} · зазор {payload['min_gap']} кадров "
        f"· пространство: {payload.get('space', 'raw')}\n")
    add("Первый этап и вердикт по metric layer — `reports/calibration-check.md`.\n")

    add("## A. Покрытие person × pose_bin\n")
    bins = [b for b in BINS if any(c["bin"] == b for c in payload["coverage"])]
    add("| персона | " + " | ".join(bins) + " |")
    add("|---" * (len(bins) + 1) + "|")
    grid = {(c["person"], c["bin"]): c for c in payload["coverage"]}
    for person in sorted({c["person"] for c in payload["coverage"]}):
        cells = [str(grid[(person, b)]["n"]) if (person, b) in grid else "—" for b in bins]
        add(f"| {person} | " + " | ".join(cells) + " |")
    add("\n| бин | кадров | yaw диапазон | разброс | резкость |\n|---|---|---|---|---|")
    for b in bins:
        items = [c for c in payload["coverage"] if c["bin"] == b]
        n = sum(c["n"] for c in items)
        lo = min(c["yaw_min"] for c in items)
        hi = max(c["yaw_max"] for c in items)
        sharp = round(float(np.mean([c["sharpness"] for c in items])), 1)
        add(f"| {b} | {n} | {lo}…{hi} | {round(hi - lo, 1)} | {sharp} |")
    add(f"\nПолная сетка с номерами кадров — в `{payload['json']}`.\n")
    outliers = payload.get("yaw_outliers") or []
    if outliers:
        add(f"Кадры с |yaw| > 95° (проверить метку бина): "
            + ", ".join(f"{o['person']}/{o['frame']} ({o['bin']}, {o['yaw']}°)"
                        for o in outliers) + ".\n")
    gaps = payload.get("gap_counts") or {}
    if gaps:
        add("\nСколько within-пар остаётся при разных зазорах (весь корпус):\n")
        add("| зазор, кадров | оба кадра в одном бине | переход между бинами |")
        add("|---|---|---|")
        for gap, row in gaps.items():
            add(f"| {gap} | {row['same']} | {row['cross']} |")
        last = gaps[str(payload["min_gap"])] if str(payload["min_gap"]) in gaps else None
        if last:
            add(f"\nНа рабочем зазоре {payload['min_gap']} внутрибиновых пар всего "
                f"{last['same']} из {last['same'] + last['cross']}, поэтому "
                f"CI по ячейкам person × pose_bin на этом корпусе не строятся: "
                f"ячейка осталась бы из 1–2 пар.\n")
    trans = transition_counts(payload["coverage"], payload["min_gap"])
    if trans:
        vals = sorted(trans.values())
        rare = [f"{'/'.join(k)}={v}" for k, v in trans.items() if v < 10]
        add(f"Пары по переходам между бинами: {len(vals)} переходов, медиана "
            f"{vals[len(vals) // 2]}, минимум {vals[0]}, максимум {vals[-1]}. "
            f"Меньше 10 пар: {len(rare)} — {', '.join(rare) if rare else 'нет'}.\n")

    add("## B. Sweep представлений\n")
    add("Нечётные кадры: метрики не видят пар, на которых подбиралась sigma.\n")
    add("| представление | метрика | within μ | between μ | ratio | AUC |")
    add("|---|---|---|---|---|---|")
    for rep, row in payload["sweep"].items():
        for metric in ("euclid", "normal", "weighted", "z_mean"):
            m = row["odd"][metric]
            add(f"| {rep} | {metric} | {m['within']['mean']} | {m['between']['mean']} "
                f"| {m['ratio']} | {m['auc']} |")
    add("")
    add("Регионы лица (только euclid, представление `vertices`):\n")
    add("| зона | within μ | between μ | ratio | AUC |")
    add("|---|---|---|---|---|")
    for key, m in payload["sweep"]["vertices"]["odd"].items():
        if key.startswith("region_"):
            add(f"| {key[7:]} | {m['within']['mean']} | {m['between']['mean']} "
                f"| {m['ratio']} | {m['auc']} |")
    add("")

    add("## C. Веса шума\n")
    add(f"sigma обучена на {payload['sigma_pairs']} парах чётных кадров.\n")
    add("| представление | within μ (euclid) | within μ (weighted) | Δ | "
        "AUC euclid | AUC weighted |")
    add("|---|---|---|---|---|---|")
    for rep, row in payload["sweep"].items():
        e, w = row["odd"]["euclid"], row["odd"]["weighted"]
        delta = 100 * (w["within"]["mean"] / e["within"]["mean"] - 1)
        add(f"| {rep} | {e['within']['mean']} | {w['within']['mean']} | {delta:+.1f}% "
            f"| {e['auc']} | {w['auc']} |")
    boot = payload.get("bootstrap")
    if boot:
        add(f"\nКластерный bootstrap (кадры внутри человека, {boot['rounds']} итераций) "
            f"для within μ у `vertices`: {boot['lo']}…{boot['hi']}.\n")
    delta = payload.get("auc_delta")
    if delta:
        add(f"\nЗначимость прироста (парный bootstrap по кадрам, `vertices`, "
            f"{delta['rounds']} итераций): ΔAUC = {delta['mean']} "
            f"[{delta['lo']}; {delta['hi']}], доля итераций с ΔAUC > 0 — "
            f"{delta['p_positive']}.\n")
    split = payload.get("breakdown")
    if split:
        add("\nГде именно выигрыш (`vertices`, нечётные кадры, within-пары):\n")
        add("| подвыборка | пар | within μ euclid | within μ weighted | Δ |")
        add("|---|---|---|---|---|")
        for key, label in (("same_bin", "оба кадра в одном бине"),
                           ("cross_bin", "переход между бинами")):
            r = split[key]
            if r:
                add(f"| {label} | {r['n']} | {r['euclid']} | {r['weighted']} | {r['delta']:+.1f}% |")
        for name, r in split["per_bin"].items():
            if r["n"] >= 5:
                add(f"| {name} (внутри бина) | {r['n']} | {r['euclid']} | {r['weighted']} "
                    f"| {r['delta']:+.1f}% |")
        front = payload.get("frontal")
        if front:
            add(f"| frontal, зазор {front['gap']} | {front['n']} | {front['euclid']} "
                f"| {front['weighted']} | {front['delta']:+.1f}% |")
        add("")
        add("Ячейки с n < 5 не печатаются: на зазоре 30 в одном бине остаётся 1–2 пары.\n")
    lopo = payload.get("lopo")
    if lopo:
        add(f"\nПроверка на новом человеке (sigma по шести людям, оценка на седьмом): "
            f"выигрыш у {lopo['wins']} из {lopo['n']}, средний ΔAUC "
            f"{lopo['mean_delta_auc']:+.4f}, худший {lopo['min_delta_auc']:+.4f}.\n")
        add("| отложенный | пар within | AUC euclid | AUC weighted | Δ |")
        add("|---|---|---|---|---|")
        for r in lopo["rows"]:
            add(f"| {r['person']} | {r['n_within']} | {r['auc_euclid']} | {r['auc_weighted']} "
                f"| {r['auc_weighted'] - r['auc_euclid']:+.4f} |")
        add("")

    add("## D. z-карта\n")
    heat = payload.get("heat")
    if heat:
        add(f"Пара `{heat['person']}` кадры {heat['pair']} ({', '.join(heat['bins'])}): "
            f"euclid μ {heat['euclid']}, нормальная μ {heat['normal']}, "
            f"z μ {heat['z_mean']}, z p95 {heat['z_p95']}, "
            f"доля вершин z>3 — {100 * heat['z_frac_above_3']:.1f}%.\n")
        zv = payload["sweep"]["vertices"]["odd"]["z_frac3"]
        add(f"Доля вершин z>3 в среднем по парам: внутри {100 * zv['within']['mean']:.1f}%, "
            f"между {100 * zv['between']['mean']:.1f}% — чем больше разрыв, тем меньше "
            f"риск равномерной заливки у одного человека.\n")
        add(f"![d, normal, z](file://{ROOT / heat['file']})\n")
    else:
        add("Пара не найдена.\n")

    add("## Критерии приёмки\n")
    add(payload["verdict"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--min-frame-gap", type=int, default=30)
    ap.add_argument("--max-between", type=int, default=4000)
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-refresh-stale", action="store_true")
    ap.add_argument("--normalize-scale", action="store_true",
                    help="привести меши к пространству heatmap: центр + IOD")
    ap.add_argument("--purge", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration-sweep.md")
    ap.add_argument("--json", type=Path, default=ROOT / "reports/calibration-sweep.json")
    args = ap.parse_args()

    from server import storage

    index_path = args.calibration_root / "all_calibration_index.csv"
    if not index_path.exists():
        raise SystemExit(f"нет индекса: {index_path}")
    before = {p["id"] for p in storage.read_db()["photos"]}
    selected = select_frames(index_path, args.photos_root, args.per_person)
    targets, summary = ingest_and_process(selected,
                                          refresh_stale=not args.no_refresh_stale)
    print("обработка:", {k: v for k, v in summary.items() if k != "errors"}, flush=True)

    frames = load_frames(selected)
    print("кадров:", len(frames), flush=True)
    topo = json.loads((ROOT / "data/topology.json").read_text())
    tri = np.asarray(topo["triangles"], np.int32)
    normals = vertex_normals(np.asarray(topo["mean"], np.float32), tri)
    lm = np.asarray(topo["landmarks"]["ldm68"], np.int32)
    regions = {k: lm[v] for k, v in REGIONS.items()}
    space = "raw"
    if args.normalize_scale:
        frames = normalize_scale(frames, lm)
        space = "center + IOD"

    by_person, within, within_odd, even = pair_blocks(frames, args.min_frame_gap)
    rng = random.Random(args.seed)
    between = [(a, b) for p1, p2 in itertools.combinations(sorted(by_person), 2)
               for a in by_person[p1] for b in by_person[p2]]
    if len(between) > args.max_between:
        between = rng.sample(between, args.max_between)
    odd = {i for i, f in enumerate(frames) if f["order"] % 2 == 1}
    between_odd = [(a, b) for a, b in between if a in odd and b in odd]
    print(f"пар: внутри {len(within)} (нечётных {len(within_odd)}) · "
          f"между {len(between)} (нечётных {len(between_odd)})", flush=True)

    coverage_rows = coverage(frames)
    outliers = [f for f in frames if abs(f["yaw"]) > 95]
    sweep, sigma_pairs = {}, 0
    fig_arrays = fig_sigma = None
    within_dists = None
    auc_ci = None
    split = None
    frontal = None
    lopo = None
    for name in REPS:
        arrays = rep_arrays(frames, name)
        sigma, fitted = fit_sigma(frames, arrays, even, args.min_frame_gap)
        inv = float((1 / sigma).sum())
        odd_rows, wv, bv = evaluate(
            frames, arrays, normals, sigma, inv,
            lm, regions, within_odd, between_odd, heavy=True, keep=True,
        )
        sweep[name] = {
            "sigma_pairs": fitted,
            "all": evaluate(frames, arrays, normals, sigma, inv,
                            lm, regions, within, between, heavy=False),
            "odd": odd_rows,
        }
        if name == "vertices":
            sigma_pairs = fitted
            fig_arrays, fig_sigma = arrays, sigma
            auc_ci = auc_delta_ci(frames, within_odd, between_odd,
                                  wv["euclid"], wv["weighted"],
                                  bv["euclid"], bv["weighted"],
                                  args.bootstrap, args.seed)
            split = breakdown(frames, within_odd, wv)
            frontal = frontal_check(frames, arrays, sigma, inv, 10)
            lopo = lopo_check(frames, arrays, args.min_frame_gap)
            within_dists = [
                float(np.sqrt(((arrays[a] - arrays[b]) ** 2).sum(axis=1)).mean())
                for a, b in within
            ]
        print(f"{name:18s} euclid within {sweep[name]['all']['euclid']['within']['mean']} "
              f"auc {sweep[name]['all']['euclid']['auc']}", flush=True)

    boot = cluster_bootstrap(frames, within, within_dists, args.bootstrap, args.seed) \
        if within_dists is not None else None
    heat = None
    if fig_arrays is not None:
        heat = heat_figure(frames, fig_arrays, fig_sigma, normals, tri,
                           ROOT / "reports/calibration" / f"{args.json.stem}.png")

    base = sweep["vertices"]["all"]["euclid"]
    best = max(
        ((r, m, row["odd"][m]) for r, row in sweep.items()
         for m in ("euclid", "normal", "weighted", "z_mean")),
        key=lambda item: item[2]["auc"],
    )
    verdict = [
        f"- baseline `vertices`/euclid на всём корпусе: within {base['within']['mean']}, "
        f"between {base['between']['mean']}, ratio {base['ratio']}, AUC {base['auc']}.",
        f"- лучший вариант на нечётных кадрах: `{best[0]}`/{best[1]} — "
        f"within {best[2]['within']['mean']}, ratio {best[2]['ratio']}, "
        f"AUC {best[2]['auc']}.",
    ]
    if split:
        verdict.append(
            f"- within: {split['cross_bin']['delta']:+.1f}% на переходах между бинами, "
            f"{split['same_bin']['delta']:+.1f}% внутри бина."
        )
    if frontal:
        verdict.append(f"- фронтальные пары: {frontal['delta']:+.1f}% (n={frontal['n']}, "
                       f"зазор {frontal['gap']}).")
    if auc_ci:
        verdict.append(f"- ΔAUC = {auc_ci['mean']} [{auc_ci['lo']}; {auc_ci['hi']}], "
                       f"доля итераций с ΔAUC > 0 — {auc_ci['p_positive']}.")
    zv = sweep["vertices"]["odd"]["z_frac3"]
    verdict.append(f"- доля вершин z>3: внутри {100 * zv['within']['mean']:.1f}%, "
                   f"между {100 * zv['between']['mean']:.1f}%.")
    verdict.append("- морфинг и паритет preview/export этим прогоном не затрагивались.")
    payload = {
        "index": str(index_path), "json": str(args.json),
        "sampled": len(frames), "n_within": len(within), "n_between": len(between),
        "space": space,
        "min_gap": args.min_frame_gap, "coverage": coverage_rows,
        "sweep": sweep, "sigma_pairs": sigma_pairs, "bootstrap": boot,
        "auc_delta": auc_ci, "breakdown": split, "frontal": frontal, "lopo": lopo,
        "gap_counts": gap_counts(frames),
        "yaw_outliers": [{"person": f["person"], "frame": f["frame"],
                          "bin": f["bin"], "yaw": round(f["yaw"], 1)} for f in outliers],
        "heat": heat, "verdict": "\n".join(verdict),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")
    write_report(args.out, payload)
    print("отчёт:", args.out, flush=True)
    if args.purge:
        created = {r["id"] for r in targets} - before
        from calibration_check import purge_records

        print("удалено записей:", purge_records(created), flush=True)


if __name__ == "__main__":
    main()
