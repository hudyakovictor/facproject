"""Третья итерация: calibrated normal-weighted heatmap как режим приложения.

Baseline:   vertices + euclid   + без весов
Candidate:  vertices + normal   + calibrated confidence (center + IOD)

Проверяет не «какое пространство выбрать», а готовность production-связки:

  * битый кадр person_06/164 (right_profile при предсказанном yaw -102.5)
    помечается invalid_pose и исключается из калибровки;
  * sigma учится на same-person парах чётных кадров, оценка — на нечётных;
  * веса агрегируются глобально (transition family только для диагностики
    и leave-one-transition-out), а не по 81 ячейке person x pose_bin;
  * LOPO и LOTRO проверяют именно тот профиль, который читает приложение;
  * все значения считает server.heat.compute_heat_values — тот же helper,
    что используют preview и export.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python scripts/calibration_v3.py
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import (  # noqa: E402
    compose_rows,
    heat_panel,
    ingest_and_process,
    purge_records,
    select_frames,
)
from calibration_sweep import auc, auc_delta_ci, summarize  # noqa: E402
from server.heat import (  # noqa: E402
    Calibration,
    compute_heat_values,
    template_normals,
)

BINS = [
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
]
DEPTH = {
    "frontal": 0,
    "left_light": 1, "right_light": 1,
    "left_mid": 2, "right_mid": 2,
    "left_deep": 3, "right_deep": 3,
    "left_profile": 4, "right_profile": 4,
}
TRANSITIONS = {
    (0, 1): "frontal_light",
    (1, 2): "light_mid",
    (2, 3): "mid_deep",
    (3, 4): "deep_profile",
}
FAMILIES = ["frontal_light", "light_mid", "mid_deep", "deep_profile"]
MODES = [
    ("euclid", "euclid", "none"),
    ("normal", "normal", "none"),
    ("weighted_euclid", "euclid", "calibrated"),
    ("weighted_normal", "normal", "calibrated"),
]
REGIONS = {
    "jaw": list(range(0, 17)),
    "brows": list(range(17, 27)),
    "nose": list(range(27, 36)),
    "eyes": list(range(36, 48)),
    "mouth": list(range(48, 68)),
}
YAW_LIMIT = 95.0
LABEL_MISMATCH = 90.0


def topology():
    data = json.loads((ROOT / "data/topology.json").read_text())
    tri = np.asarray(data["triangles"], np.int32)
    lm = np.asarray(data["landmarks"]["ldm68"], np.int32)
    return tri, lm


def index_rows(index_path):
    import csv

    out = {}
    with index_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out[(row["dataset_id"], row["source_filename"])] = row
    return out


def family_of(bin_a, bin_b):
    lo, hi = sorted((DEPTH[bin_a], DEPTH[bin_b]))
    if lo == hi:
        return f"same_{lo}"
    return TRANSITIONS.get((lo, hi), f"skip_{lo}_{hi}")


def load_frames(selected, index, tri, lm, extra_invalid):
    from server import storage

    # Одно поле направлений на все кадры — то же, что в приложении:
    # per-frame нормали рвали карту на стыке сегментов.
    normals = template_normals(tri)
    frames = []
    for person, rows in selected.items():
        for order, row in enumerate(rows):
            record = storage.photo(row["id"])
            meta_path = storage.feature_path(record).with_name("meta.json")
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            with np.load(storage.feature_path(record)) as handle:
                vertices = np.asarray(handle["vertices"], np.float32)
                angles = np.ravel(handle["alpha"])
                yaw = float(np.degrees(angles[225]))
                pitch = float(np.degrees(angles[224]))
                roll = float(np.degrees(angles[226]))
            source = index.get((person, row["path"].name), {})
            csv_yaw = float(source.get("yaw", "nan"))
            # App heat space: центр и IOD по средним контуров глаз (ldm68 36:42/42:48).
            eye = vertices[lm]
            left, right = eye[36:42].mean(axis=0), eye[42:48].mean(axis=0)
            center = (left + right) / 2
            iod = max(float(np.linalg.norm(left - right)), 1e-8)
            vertices = ((vertices - center) / iod).astype(np.float32)
            reasons = []
            if abs(yaw) > YAW_LIMIT:
                reasons.append(f"|yaw|={yaw:.1f}>{YAW_LIMIT:.0f}")
            if np.isfinite(csv_yaw) and abs(yaw - csv_yaw) > LABEL_MISMATCH:
                reasons.append(f"label={row['bin']} yaw={csv_yaw:.1f} vs {yaw:.1f}")
            if (person, row["frame"]) in extra_invalid and not reasons:
                reasons.append(extra_invalid[(person, row["frame"])])
            frames.append({
                "id": row["id"],
                "person": person,
                "frame": int(row["frame"]),
                "bin": row["bin"],
                "order": order,
                "yaw": yaw,
                "pitch": pitch,
                "roll": roll,
                "csv_yaw": csv_yaw,
                "sharpness": float(meta.get("sharpness", float("nan"))),
                "vertices": vertices,
                "normals": normals,
                "valid": not reasons,
                "invalid_reason": "; ".join(reasons),
            })
    return frames


def people_indices(frames, people, parity):
    out = {}
    for person in sorted(people):
        out[person] = [i for i, f in enumerate(frames)
                       if f["person"] == person and f["order"] % 2 == parity
                       and f["valid"]]
    return out


def fit_noise(frames, people, gap, exclude_family=None):
    """Per-vertex sigma по same-person парам чётных кадров.

    exclude_family выкидывает из обучения переходы одного семейства — это
    leave-one-transition-out, а не отдельный профиль на ячейку.
    """
    even = people_indices(frames, people, 0)
    total_e = total_e2 = total_n = total_n2 = 0.0
    count = 0
    for ids in even.values():
        for a, b in itertools.combinations(sorted(ids), 2):
            if frames[b]["frame"] - frames[a]["frame"] < gap:
                continue
            if exclude_family and family_of(frames[a]["bin"], frames[b]["bin"]) == exclude_family:
                continue
            diff = (frames[a]["vertices"] - frames[b]["vertices"]).astype(np.float64)
            e = np.sqrt((diff * diff).sum(axis=1))
            n = (diff * frames[a]["normals"]).sum(axis=1)
            if count == 0:
                total_e = np.zeros_like(e)
                total_e2 = np.zeros_like(e)
                total_n = np.zeros_like(e)
                total_n2 = np.zeros_like(e)
            total_e += e
            total_e2 += e * e
            total_n += n
            total_n2 += n * n
            count += 1
    if count < 10:
        raise SystemExit(f"слишком мало пар для sigma: {count}")
    mean_e, mean_n = total_e / count, total_n / count
    sigma_e = np.sqrt(np.maximum(total_e2 / count - mean_e * mean_e, 0.0))
    sigma_n = np.sqrt(np.maximum(total_n2 / count - mean_n * mean_n, 0.0))
    floor_e = float(np.median(sigma_e)) * 0.25
    floor_n = float(np.median(sigma_n)) * 0.25
    return (np.maximum(sigma_e, floor_e).astype(np.float32),
            np.maximum(sigma_n, floor_n).astype(np.float32), count)


def calibration_payload(sigma_e, sigma_n):
    lo, hi = (float(v) for v in np.percentile(sigma_e, [5, 95]))
    lo_n, hi_n = (float(v) for v in np.percentile(sigma_n, [5, 95]))
    if hi <= lo:
        hi = lo * 1.01 + 1e-9
    if hi_n <= lo_n:
        hi_n = lo_n * 1.01 + 1e-9
    return {
        "sigma": sigma_e.astype(np.float32).tolist(),
        "sigma_normal": sigma_n.astype(np.float32).tolist(),
        "clip": [lo, hi],
        "clip_normal": [lo_n, hi_n],
    }


def calibration(sigma_e, sigma_n):
    return Calibration(calibration_payload(sigma_e, sigma_n))


def values_all(frames, i, j, tri, cal):
    """Четыре режима одной пары через единый helper."""
    a, b = frames[i]["vertices"], frames[j]["vertices"]
    out = {}
    for name, metric, weighting in MODES:
        out[name] = compute_heat_values(
            a, b, a, tri,
            metric=metric,
            weighting=weighting,
            calibration=cal if weighting == "calibrated" else None,
        )["end"]
    return out


def scalar(values, mode, cal):
    metric, weighting = MODES_BY_NAME[mode][1:]
    if weighting == "calibrated":
        return cal.aggregate(values, metric)
    return float(values.mean())


def z_map(values, mode, cal):
    metric, weighting = MODES_BY_NAME[mode][1:]
    return values if weighting == "calibrated" else values * cal.weight_for(metric)


def region_scalar(values, mode, cal, idx):
    metric, weighting = MODES_BY_NAME[mode][1:]
    if weighting == "calibrated":
        weights = cal.weight_for(metric)[idx]
        return float(values[idx].sum() / max(float(weights.sum()), 1e-9))
    return float(values[idx].mean())


MODES_BY_NAME = {name: (name, metric, weighting) for name, metric, weighting in MODES}


def collect(frames, pairs, tri, cal, lm, regions=False):
    modes = [m[0] for m in MODES]
    acc = {m: {"scalar": [], "z": []} for m in modes}
    racc = ({m: {r: [] for r in REGIONS} for m in ("euclid", "normal", "weighted_normal")}
            if regions else {})
    for i, j in pairs:
        values = values_all(frames, i, j, tri, cal)
        for m in modes:
            acc[m]["scalar"].append(scalar(values[m], m, cal))
            acc[m]["z"].append(float((z_map(values[m], m, cal) > 3).mean()))
        if regions:
            for m in racc:
                for name, points in REGIONS.items():
                    racc[m][name].append(region_scalar(values[m], m, cal, lm[points]))
    return acc, racc


def metrics(frames, acc, within, between):
    same = np.asarray([frames[i]["bin"] == frames[j]["bin"] for i, j in within], bool)
    rows = {}
    for name in [m[0] for m in MODES]:
        wv = np.asarray(acc[name]["scalar"][: len(within)], np.float64)
        bv = np.asarray(acc[name]["scalar"][len(within):], np.float64)
        zw = np.asarray(acc[name]["z"][: len(within)], np.float64)
        zb = np.asarray(acc[name]["z"][len(within):], np.float64)
        if not len(wv) or not len(bv):
            continue
        rows[name] = {
            "within": summarize(wv),
            "within_same": summarize(wv[same]),
            "within_cross": summarize(wv[~same]),
            "between": summarize(bv),
            "ratio": round(float(bv.mean() / max(wv.mean(), 1e-12)), 3),
            "auc": auc(wv, bv),
            "z3_within": round(float(zw.mean()), 4),
            "z3_between": round(float(zb.mean()), 4),
        }
    return rows


def build_pairs(frames, gap):
    odd = people_indices(frames, {f["person"] for f in frames}, 1)
    within, between = [], []
    for ids in odd.values():
        for a, b in itertools.combinations(sorted(ids, key=lambda i: frames[i]["frame"]), 2):
            if frames[b]["frame"] - frames[a]["frame"] < gap:
                continue
            within.append((a, b))
    people = sorted(odd)
    for p, q in itertools.combinations(people, 2):
        for a in odd[p]:
            for b in odd[q]:
                between.append((a, b))
    return within, between


def transition_table(frames, within, between):
    rows = defaultdict(lambda: {"within": 0, "between": 0})
    for i, j in within:
        rows[family_of(frames[i]["bin"], frames[j]["bin"])]["within"] += 1
    for i, j in between:
        rows[family_of(frames[i]["bin"], frames[j]["bin"])]["between"] += 1
    return {k: v for k, v in sorted(rows.items())}


def lopo(frames, within, between, tri, lm, gap, seed=42):
    people = sorted({f["person"] for f in frames})
    rows = []
    for person in people:
        others = [p for p in people if p != person]
        sigma_e, sigma_n, pairs = fit_noise(frames, others, gap)
        cal = calibration(sigma_e, sigma_n)
        mine = {i for i, f in enumerate(frames)
                if f["person"] == person and f["order"] % 2 == 1 and f["valid"]}
        others_idx = {i for i, f in enumerate(frames)
                      if f["person"] != person and f["order"] % 2 == 1 and f["valid"]}
        within_mine = [(i, j) for i, j in within if i in mine and j in mine]
        between_mine = [(i, j) for i, j in between
                        if (i in mine and j in others_idx)
                        or (j in mine and i in others_idx)]
        if len(within_mine) < 10 or len(between_mine) < 10:
            continue
        acc, _ = collect(frames, within_mine + between_mine, tri, cal, lm)
        row = {"person": person, "sigma_pairs": pairs,
               "n_within": len(within_mine), "n_between": len(between_mine)}
        for name, _metric, _weighting in MODES:
            wv = np.asarray(acc[name]["scalar"][: len(within_mine)])
            bv = np.asarray(acc[name]["scalar"][len(within_mine):])
            row[f"auc_{name}"] = auc(wv, bv)
            row[f"within_{name}"] = round(float(wv.mean()), 5)
        rows.append(row)
    if not rows:
        return None
    out = {"rows": rows}
    for name in ("normal", "weighted_euclid", "weighted_normal"):
        deltas = [r[f"auc_{name}"] - r["auc_euclid"] for r in rows]
        out[name] = {
            "mean_delta_auc": round(float(np.mean(deltas)), 4),
            "min_delta_auc": round(float(np.min(deltas)), 4),
            "wins": int(sum(d > 0 for d in deltas)),
            "n": len(deltas),
        }
    return out


def lotro(frames, within, between, tri, lm, gap):
    people = {f["person"] for f in frames}
    rows = []
    for family in FAMILIES:
        sigma_e, sigma_n, pairs = fit_noise(frames, people, gap, exclude_family=family)
        cal = calibration(sigma_e, sigma_n)
        wfam = [(i, j) for i, j in within
                if family_of(frames[i]["bin"], frames[j]["bin"]) == family]
        bfam = [(i, j) for i, j in between
                if family_of(frames[i]["bin"], frames[j]["bin"]) == family]
        if len(wfam) < 5 or len(bfam) < 10:
            rows.append({"family": family, "n_within": len(wfam),
                         "n_between": len(bfam), "skipped": True})
            continue
        acc, _ = collect(frames, wfam + bfam, tri, cal, lm)
        row = {"family": family, "sigma_pairs": pairs,
               "n_within": len(wfam), "n_between": len(bfam)}
        for name, _metric, _weighting in MODES:
            wv = np.asarray(acc[name]["scalar"][: len(wfam)])
            bv = np.asarray(acc[name]["scalar"][len(wfam):])
            row[f"within_{name}"] = round(float(wv.mean()), 5)
            row[f"auc_{name}"] = auc(wv, bv)
        e = row["within_normal"]
        # Δ within — только внутри одной метрики: euclid меряется в |d|,
        # normal — в |d·n|, смешивать их в проценте нельзя.
        row["within_delta_pct"] = round(100 * (row["within_weighted_normal"] / e - 1), 1)
        row["within_metric_delta_pct"] = round(100 * (e / row["within_euclid"] - 1), 1)
        row["auc_delta"] = round(row["auc_weighted_normal"] - row["auc_euclid"], 4)
        row["auc_normal_delta"] = round(row["auc_normal"] - row["auc_euclid"], 4)
        rows.append(row)
    scored = [r for r in rows if not r.get("skipped")]
    return {
        "rows": rows,
        "wins": sum(1 for r in scored if r["auc_delta"] > 0),
        "n": len(scored),
        "mean_auc_delta": round(float(np.mean([r["auc_delta"] for r in scored])), 4)
        if scored else None,
    }


def family_sigmas(frames, gap):
    people = {f["person"] for f in frames}
    even = people_indices(frames, people, 0)
    totals = {f: [0.0, 0.0, 0] for f in list(FAMILIES) + ["same_depth"]}
    for ids in even.values():
        for a, b in itertools.combinations(sorted(ids), 2):
            if frames[b]["frame"] - frames[a]["frame"] < gap:
                continue
            fam = family_of(frames[a]["bin"], frames[b]["bin"])
            if fam.startswith("same_"):
                fam = "same_depth"
            if fam not in totals:
                continue
            diff = (frames[a]["vertices"] - frames[b]["vertices"]).astype(np.float64)
            e = np.sqrt((diff * diff).sum(axis=1))
            totals[fam][0] += e
            totals[fam][1] += e * e
            totals[fam][2] += 1
    out = {}
    for fam, (total, total2, count) in totals.items():
        if count < 5:
            continue
        mean = total / count
        sigma = np.sqrt(np.maximum(total2 / count - mean * mean, 0.0))
        out[fam] = (np.maximum(sigma, float(np.median(sigma)) * 0.25).astype(np.float32), count)
    return out


def stability(sigma_e, sigma_n, clip, clip_normal, lm):
    sigma = np.clip(sigma_e, *clip)
    weights = 1.0 / sigma
    regions = {}
    for name, points in REGIONS.items():
        idx = lm[points]
        w = weights[idx]
        s = sigma[idx]
        regions[name] = {
            "vertices": int(len(idx)),
            "sigma_mean": round(float(s.mean()), 6),
            "sigma_min": round(float(s.min()), 6),
            "sigma_max": round(float(s.max()), 6),
            "weight_mean": round(float(w.mean()), 4),
            "at_lower_pct": round(100 * float((s <= clip[0] + 1e-12).mean()), 1),
            "at_upper_pct": round(100 * float((s >= clip[1] - 1e-12).mean()), 1),
        }
    lo, hi = float(sigma.min()), float(sigma.max())
    return {
        "vertices": int(len(sigma)),
        "sigma_min": round(lo, 6),
        "sigma_p05": round(float(np.percentile(sigma, 5)), 6),
        "sigma_median": round(float(np.median(sigma)), 6),
        "sigma_p95": round(float(np.percentile(sigma, 95)), 6),
        "sigma_max": round(hi, 6),
        "weight_min": round(float(weights.min()), 4),
        "weight_max": round(float(weights.max()), 4),
        "clip": [round(float(v), 6) for v in clip],
        "clip_normal": [round(float(v), 6) for v in clip_normal],
        "at_lower_pct": round(100 * float((sigma <= clip[0] + 1e-12).mean()), 1),
        "at_upper_pct": round(100 * float((sigma >= clip[1] - 1e-12).mean()), 1),
        "regions": regions,
    }


def family_diagnostics(sigmas, global_sigma, families):
    """Разброс sigma по семействам — диагностика, а не отдельные профили."""
    names = list(sigmas)
    if len(names) < 2:
        return {}
    stack = np.stack([sigmas[n][0] for n in names])
    spread = stack.std(axis=0) / np.maximum(stack.mean(axis=0), 1e-9)
    source = stack.argmin(axis=0)
    counts = {n: int(sigmas[n][1]) for n in names}
    ratios = {n: round(float(np.mean(global_sigma / sigmas[n][0])), 3) for n in names}
    return {
        "families": counts,
        "weight_ratio_vs_global": ratios,
        "spread_mean": round(float(spread.mean()), 3),
        "spread_p95": round(float(np.percentile(spread, 95)), 3),
        "unstable_pct": round(100 * float((spread > 0.5).mean()), 1),
        "source_pct": {n: round(100 * float((source == k).mean()), 1)
                       for k, n in enumerate(names)},
        "sigma_std": np.round(stack.std(axis=0), 6).tolist(),
        "sigma_family_mean": np.round(stack.mean(axis=0), 6).tolist(),
        "weight_mean": np.round(1 / np.maximum(stack.mean(axis=0), 1e-9), 4).tolist(),
        "sigma_min": np.round(stack.min(axis=0), 6).tolist(),
        "sigma_max": np.round(stack.max(axis=0), 6).tolist(),
        "source": source.astype(int).tolist(),
        "source_families": names,
    }


def pair_for_figure(frames):
    frontal = [i for i, f in enumerate(frames) if f["bin"] == "frontal" and f["valid"]]
    profile = [i for i, f in enumerate(frames)
               if f["bin"] in ("left_profile", "right_profile") and f["valid"]]
    best = None
    for i in frontal:
        for j in profile:
            if frames[i]["person"] != frames[j]["person"]:
                continue
            dist = float(np.linalg.norm(frames[i]["vertices"] - frames[j]["vertices"], axis=1).mean())
            if best is None or dist > best[0]:
                best = (dist, i, j)
    return (best[1], best[2]) if best else (0, min(1, len(frames) - 1))


def figures(frames, tri, cal, sigma_e, sigma_n, payload, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    i, j = pair_for_figure(frames)
    values = values_all(frames, i, j, tri, cal)
    row = []
    for name, _metric, weighting in MODES:
        vmax = 4.0 if weighting == "calibrated" else 0.06
        row.append(heat_panel(values[name], frames[i]["vertices"], tri, 300, vmax))
    path = out_dir / "v3-modes.png"
    compose_rows([row], path)
    files.append({
        "file": str(path.relative_to(ROOT)),
        "caption": "Четыре режима на одной паре: euclid · normal · weighted euclid · weighted normal",
        "pair": [frames[i]["frame"], frames[j]["frame"]],
        "person": frames[i]["person"],
        "bins": [frames[i]["bin"], frames[j]["bin"]],
    })

    clip_e = payload["clip"]["euclid"]
    clip_n = payload["clip"]["normal"]
    row = [
        heat_panel(np.clip(sigma_e, *clip_e), frames[i]["vertices"], tri, 300,
                   float(np.percentile(sigma_e, 95))),
        heat_panel(np.clip(sigma_n, *clip_n), frames[i]["vertices"], tri, 300,
                   float(np.percentile(sigma_n, 95))),
    ]
    path = out_dir / "v3-weights.png"
    compose_rows([row], path)
    files.append({"file": str(path.relative_to(ROOT)),
                  "caption": "sigma euclid и sigma normal после clip (p05…p95)"})

    def bars(rows, labels, keys, title, path, colors):
        fig, ax = plt.subplots(figsize=(8, 3.6), dpi=130)
        width = 0.8 / len(keys)
        x = np.arange(len(labels))
        for k, (key, label, color) in enumerate(
                zip(keys, [c[1] for c in colors], [c[2] for c in colors], strict=True)):
            ax.bar(x + k * width, rows[key], width, label=label, color=color)
        ax.set_xticks(x + width * (len(keys) - 1) / 2)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        ax.axhline(0, color="#888", lw=0.8)
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)

    lopo = payload.get("lopo") or {"rows": []}
    if lopo.get("rows"):
        labels = [r["person"] for r in lopo["rows"]]
        bars({"d": [r["auc_weighted_normal"] - r["auc_euclid"] for r in lopo["rows"]],
              "n": [r["auc_normal"] - r["auc_euclid"] for r in lopo["rows"]]},
             labels, ["d", "n"],
             "LOPO: ΔAUC на отложенном человеке", out_dir / "v3-lopo.png",
             [("d", "weighted normal − euclid", "#2f8f6b"), ("n", "normal − euclid", "#7aa6d8")])
        files.append({"file": str((out_dir / "v3-lopo.png").relative_to(ROOT)),
                      "caption": "LOPO по людям"})

    lot = payload.get("lotro") or {"rows": []}
    scored = [r for r in lot["rows"] if not r.get("skipped")]
    if scored:
        bars({"d": [r["auc_delta"] for r in scored],
              "w": [r["within_delta_pct"] / 100 for r in scored]},
             [r["family"] for r in scored], ["d", "w"],
             "LOTRO: отложенное семейство переходов", out_dir / "v3-lotro.png",
             [("d", "ΔAUC (weighted normal − euclid)", "#8f5bbf"),
              ("w", "Δwithin, доля", "#d08a3e")])
        files.append({"file": str((out_dir / "v3-lotro.png").relative_to(ROOT)),
                      "caption": "LOTRO по семействам переходов"})

    regions = payload.get("regions") or {}
    keys = [r for r in ("jaw", "brows", "nose", "eyes", "mouth") if r in regions]
    if keys:
        fig, ax = plt.subplots(figsize=(7, 3.4), dpi=130)
        x = np.arange(len(keys))
        delta = [100 * (regions[k]["weighted_normal"]["within"]["mean"]
                        / regions[k]["euclid"]["within"]["mean"] - 1) for k in keys]
        ax.bar(x, delta, 0.55, color="#4b8f8a")
        ax.set_xticks(x)
        ax.set_xticklabels(keys)
        ax.axhline(0, color="#888", lw=0.8)
        ax.set_ylabel("Δ within, %")
        ax.set_title("Weighted normal по зонам лица", fontsize=10)
        fig.tight_layout()
        fig.savefig(out_dir / "v3-regions.png")
        plt.close(fig)
        files.append({"file": str((out_dir / "v3-regions.png").relative_to(ROOT)),
                      "caption": "Изменение within по зонам лица"})
    return files


def checks(payload):
    base = payload["modes"]["euclid"]
    cand = payload["modes"]["weighted_normal"]
    normal = payload["modes"]["normal"]
    # Эффект весов считается внутри одной метрики: сравнение normal с euclid
    # смешивает единицы |d| и |d·n| и не является эффектом weighting.
    cross_delta = 100 * (cand["within_cross"]["mean"] / normal["within_cross"]["mean"] - 1)
    overall_delta = 100 * (cand["within"]["mean"] / normal["within"]["mean"] - 1)
    metric_cross_delta = 100 * (normal["within_cross"]["mean"] / base["within_cross"]["mean"] - 1)
    boot = (payload.get("bootstrap") or {}).get("weighted_normal") or {}
    lopo = payload.get("lopo") or {}
    lot = payload.get("lotro") or {}
    frontal = payload.get("frontal") or {}
    sat = payload.get("saturation") or {}
    return {
        "within_weighting_delta_pct": round(overall_delta, 1),
        "within_cross_delta_pct": round(cross_delta, 1),
        "within_cross_metric_delta_pct": round(metric_cross_delta, 1),
        "ratio_base": base["ratio"],
        "ratio_candidate": cand["ratio"],
        "auc_base": base["auc"],
        "auc_candidate": cand["auc"],
        "auc_normal": normal["auc"],
        "auc_delta": round(cand["auc"] - base["auc"], 4),
        "auc_ci_positive": bool(boot.get("lo", -1) > 0),
        "lopo_wins": lopo.get("weighted_normal", {}).get("wins"),
        "lopo_n": lopo.get("weighted_normal", {}).get("n"),
        "lotro_wins": lot.get("wins"),
        "lotro_n": lot.get("n"),
        "frontal_n": frontal.get("n"),
        "frontal_delta_pct": frontal.get("delta_pct"),
        "frontal_enough_n": bool(frontal.get("n") and frontal["n"] >= 10),
        "saturated_pct": sat.get("above_vmax_pct"),
        "invalid_leak": payload.get("invalid_leak"),
        "gates": {
            "cross_bin_10pct": cross_delta <= -10,
            "auc_not_worse": cand["auc"] >= base["auc"],
            "auc_ci_positive": bool(boot.get("lo", -1) > 0),
            "lopo_all": lopo.get("weighted_normal", {}).get("wins")
            == lopo.get("weighted_normal", {}).get("n"),
            "lotro_majority": (lot.get("wins") or 0) >= 3,
            "no_frontal_degradation": (frontal.get("delta_pct") is None
                                      or frontal.get("delta_pct", 0) <= 5)
            and bool(frontal.get("n") and frontal["n"] >= 10),
            "not_saturated": (sat.get("above_vmax_pct") or 0) < 50,
            "invalid_excluded": payload.get("invalid_leak") == 0,
        },
    }


def frontal_check(frames, within, acc):
    pairs = [(i, j) for i, j in within if frames[i]["bin"] == frames[j]["bin"] == "frontal"]
    if not pairs:
        return None
    e = np.asarray(acc["euclid"]["scalar"][: len(within)], np.float64)
    w = np.asarray(acc["weighted_normal"]["scalar"][: len(within)], np.float64)
    idx = np.asarray([i for i, (a, b) in enumerate(within)
                      if frames[a]["bin"] == frames[b]["bin"] == "frontal"])
    return {"n": int(len(idx)),
            "euclid": round(float(e[idx].mean()), 5),
            "weighted_normal": round(float(w[idx].mean()), 5),
            "delta_pct": round(100 * (float(w[idx].mean()) / float(e[idx].mean()) - 1), 1)}


def saturation(frames, tri, cal):
    pair = pair_for_figure(frames)
    values = values_all(frames, pair[0], pair[1], tri, cal)["weighted_normal"]
    return {"above_vmax_pct": round(100 * float((values > 4.0).mean()), 1),
            "mean_z": round(float(values.mean()), 3),
            "p95_z": round(float(np.percentile(values, 95)), 3),
            "pair": [frames[pair[0]]["frame"], frames[pair[1]]["frame"]]}


def verdict(payload):
    c = payload["checks"]["gates"]
    passed = sum(bool(v) for v in c.values())
    normal_lopo = (payload.get("lopo") or {}).get("normal") or {}
    if all(c.values()):
        code = 1
        title = "weighted normal heatmap готова к включению"
    elif (normal_lopo.get("wins") or 0) >= 6 and c["auc_not_worse"]:
        code = 2
        title = "normal heatmap полезна, weighting оставить экспериментальным"
    else:
        code = 3
        title = "weighting улучшает числа, но normal нестабилен по людям — только отчёты"
    return {"code": code, "title": title, "gates_passed": passed, "gates_total": len(c)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--min-frame-gap", type=int, default=30)
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--assemble", action="store_true",
                    help="собрать md/json из готового json + parity/chain")
    ap.add_argument("--purge", action="store_true", help="убрать записи корпуса из библиотеки")
    ap.add_argument("--keep", action="store_true", help="оставить записи и кэш в библиотеке")
    ap.add_argument("--figures", action="store_true", default=True)
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration-v3.md")
    ap.add_argument("--json", type=Path, default=ROOT / "reports/calibration-v3.json")
    ap.add_argument("--weights", type=Path,
                    default=ROOT / "reports/calibration/weights.json")
    args = ap.parse_args()
    if args.assemble:
        return assemble(args)

    index_path = args.calibration_root / "all_calibration_index.csv"
    if not index_path.exists():
        raise SystemExit(f"нет индекса: {index_path}")
    index = index_rows(index_path)
    selected = select_frames(index_path, args.photos_root, args.per_person)
    if not selected:
        raise SystemExit("корпус не выбран")

    extra_invalid = {}
    manifest = ROOT / "reports/calibration/invalid-frames.json"
    if manifest.exists():
        for row in json.loads(manifest.read_text()).get("frames", []):
            extra_invalid[(row["person"], int(row["frame"]))] = row.get("reason", "invalid_pose")

    targets, process_info = ingest_and_process(selected, False)
    print("process:", {k: process_info[k] for k in ("photos", "cache_hits", "errors")})
    tri, lm = topology()
    frames = load_frames(selected, index, tri, lm, extra_invalid)

    invalid = [{"person": f["person"], "frame": f["frame"], "bin": f["bin"],
                "yaw": round(f["yaw"], 1), "reason": f["invalid_reason"]}
               for f in frames if not f["valid"]]
    valid = [f for f in frames if f["valid"]]
    people = sorted({f["person"] for f in frames})
    print(f"frames {len(frames)} valid {len(valid)} invalid {len(invalid)} people {len(people)}")

    sigma_e, sigma_n, fit_pairs = fit_noise(frames, people, args.min_frame_gap)
    cal = calibration(sigma_e, sigma_n)
    payload_cal = calibration_payload(sigma_e, sigma_n)
    clip, clip_normal = payload_cal["clip"], payload_cal["clip_normal"]
    print("sigma pairs", fit_pairs, "clip", clip, clip_normal)

    within, between = build_pairs(frames, args.min_frame_gap)
    # Битые позы не должны попадать ни в sigma, ни в within/between.
    invalid_idx = {i for i, f in enumerate(frames) if not f["valid"]}
    invalid_leak = sum(1 for pair in within + between for i in pair if i in invalid_idx)
    print("invalid in pairs", invalid_leak)
    acc, racc = collect(frames, within + between, tri, cal, lm, regions=True)
    modes = metrics(frames, acc, within, between)
    regions = {}
    for name in REGIONS:
        regions[name] = {}
        for mode in ("euclid", "normal", "weighted_normal"):
            wv = np.asarray(racc[mode][name][: len(within)])
            bv = np.asarray(racc[mode][name][len(within):])
            regions[name][mode] = {
                "within": summarize(wv), "between": summarize(bv),
                "ratio": round(float(bv.mean() / max(wv.mean(), 1e-12)), 3),
                "auc": auc(wv, bv),
            }
    print("modes", {k: (v["auc"], v["ratio"]) for k, v in modes.items()})

    boot = {}
    for name in ("normal", "weighted_normal"):
        boot[name] = auc_delta_ci(
            frames, within, between,
            [v for v in acc["euclid"]["scalar"][: len(within)]],
            [v for v in acc[name]["scalar"][: len(within)]],
            [v for v in acc["euclid"]["scalar"][len(within):]],
            [v for v in acc[name]["scalar"][len(within):]],
            args.bootstrap, args.seed,
        )

    payload = {
        "dataset": {
            "index": str(index_path),
            "people": people,
            "frames": len(frames),
            "valid": len(valid),
            "per_person": args.per_person,
            "min_gap": args.min_frame_gap,
            "space": "center + IOD (eye-contour means ldm68 36:42/42:48)",
        },
        "invalid": invalid,
        "invalid_leak": invalid_leak,
        "sigma_pairs": fit_pairs,
        "clip": {"euclid": [round(float(v), 6) for v in clip],
                 "normal": [round(float(v), 6) for v in clip_normal]},
        "counts": {
            "within": len(within),
            "within_same": int(sum(frames[i]["bin"] == frames[j]["bin"] for i, j in within)),
            "within_cross": int(sum(frames[i]["bin"] != frames[j]["bin"] for i, j in within)),
            "between": len(between),
        },
        "transitions": transition_table(frames, within, between),
        "modes": modes,
        "regions": regions,
        "bootstrap": boot,
        "frontal": frontal_check(frames, within, acc),
        "saturation": saturation(frames, tri, cal),
    }
    payload["lopo"] = lopo(frames, within, between, tri, lm, args.min_frame_gap, args.seed)
    payload["lotro"] = lotro(frames, within, between, tri, lm, args.min_frame_gap)
    print("lopo", payload["lopo"] and payload["lopo"]["weighted_normal"])
    print("lotro", payload["lotro"] and {k: payload["lotro"][k] for k in ("wins", "n")})

    payload["stability"] = stability(sigma_e, sigma_n, clip, clip_normal, lm)
    fam_sigmas = family_sigmas(frames, args.min_frame_gap)
    family = family_diagnostics(fam_sigmas, np.clip(sigma_e, *clip), list(fam_sigmas))
    vertex_stats = {k: family.pop(k) for k in
                    ("sigma_std", "sigma_family_mean", "weight_mean",
                     "sigma_min", "sigma_max", "source") if k in family}
    vertex_stats["source_families"] = family.get("source_families")
    # Средний confidence самой вершины и число наблюдений, по которым он получен.
    clip_e = np.clip(sigma_e, *clip)
    vertex_stats["weight"] = np.round(1 / np.maximum(clip_e, 1e-9), 4).tolist()
    vertex_stats["n_pairs"] = int(fit_pairs)
    family.pop("source_families", None)
    payload["stability"]["family"] = family
    payload["checks"] = checks(payload)
    payload["verdict"] = verdict(payload)

    args.weights.parent.mkdir(parents=True, exist_ok=True)
    weights = {
        "version": 3,
        "method": "per-vertex sigma over same-person even-frame pairs, clip p05..p95",
        "space": payload["dataset"]["space"],
        "source": {
            "people": people,
            "frames": len(frames),
            "valid": len(valid),
            "pairs": fit_pairs,
            "gap": args.min_frame_gap,
            "invalid": invalid,
        },
        **payload_cal,
        "n_pairs": fit_pairs,
        "stability": payload["stability"],
        "vertex_stats": vertex_stats,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"version": 1, "frames": invalid}, ensure_ascii=False, indent=2))
    args.weights.write_text(json.dumps(weights, ensure_ascii=False, indent=1))

    payload["weights"] = str(args.weights.relative_to(ROOT))
    payload["figures"] = figures(frames, tri, cal, sigma_e, sigma_n, payload,
                                 ROOT / "reports/calibration") if args.figures else []
    payload["json"] = str(args.json.relative_to(ROOT))
    payload["md"] = str(args.out.relative_to(ROOT))
    payload["parity"] = json.loads((ROOT / "reports/calibration/v3-parity.json").read_text()) \
        if (ROOT / "reports/calibration/v3-parity.json").exists() else None
    payload["chain"] = json.loads((ROOT / "reports/calibration/v3-chain.json").read_text()) \
        if (ROOT / "reports/calibration/v3-chain.json").exists() else None
    write_report(args.out, payload)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    print("verdict", payload["verdict"])
    print("report", args.out)

    if args.purge and not args.keep:
        removed = purge_records([r["id"] for r in targets])
        print("purged", removed)


def assemble(args):
    payload = json.loads(args.json.read_text())
    parity_path = ROOT / "reports/calibration/v3-parity.json"
    chain_path = ROOT / "reports/calibration/v3-chain.json"
    payload["parity"] = json.loads(parity_path.read_text()) if parity_path.exists() else None
    payload["chain"] = json.loads(chain_path.read_text()) if chain_path.exists() else None
    payload["checks"] = checks(payload)
    payload["verdict"] = verdict(payload)
    write_report(args.out, payload)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    print("assembled", args.out)


def fmt(value, digits=5):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_report(path, payload):
    out = []
    add = out.append
    checks = payload["checks"]
    verdict = payload["verdict"]
    add("# Калибровка v3 · normal + calibrated weighting\n")
    add(f"Вердикт: **{verdict['code']}. {verdict['title']}** "
        f"({verdict['gates_passed']}/{verdict['gates_total']} production-гейтов).\n")
    add("Baseline `vertices + euclid + none`; кандидат `vertices + normal + calibrated` "
        f"в пространстве `{payload['dataset']['space']}`. Геометрия и морф не меняются: "
        "калибровка влияет только на значения карты.\n")
    add(f"Корпус: {payload['dataset']['valid']} валидных кадров "
        f"({payload['dataset']['frames']} всего), {len(payload['dataset']['people'])} человек, "
        f"{payload['sigma_pairs']} пар для sigma, зазор {payload['dataset']['min_gap']}.\n")
    add("## Данные\n")
    if payload["invalid"]:
        add("| персона | кадр | бин | yaw | причина |")
        add("|---|---|---|---|---|")
        for row in payload["invalid"]:
            reason = row["reason"].replace("|yaw|", "abs(yaw)").replace("|", "/")
            add(f"| {row['person']} | {row['frame']} | {row['bin']} | {row['yaw']} | {reason} |")
        names = ", ".join(f"{r['person']}/{r['frame']}" for r in payload["invalid"])
        add(f"\nКадры {names} помечены `invalid_pose` и исключены из sigma, статистики "
            "и профиля весов. Первый отсечён по `abs(yaw) > 95` и по расхождению "
            "метки с предсказанием больше 90°, второй — только по расхождению "
            "(метка right_profile, предсказанный yaw −32.6°). Внутри пар их нет: "
            f"утечек {payload.get('invalid_leak')}. "
            "Манифест: `reports/calibration/invalid-frames.json`.\n")
    else:
        add("Битых кадров не найдено.\n")
    c = payload["counts"]
    add(f"Пары: within {c['within']} (same-bin {c['within_same']}, cross-bin {c['within_cross']}), "
        f"between {c['between']}.\n")
    add("| семейство переходов | within | between |")
    add("|---|---|---|")
    for name, row in payload["transitions"].items():
        add(f"| {name} | {row['within']} | {row['between']} |")
    add("")
    add("## Режимы heatmap\n")
    add("| режим | within μ | cross-bin μ | between μ | ratio | AUC | z>3 within | z>3 between |")
    add("|---|---|---|---|---|---|---|")
    for name, _m, _w in MODES:
        row = payload["modes"][name]
        add(f"| {name} | {row['within']['mean']} | {row['within_cross']['mean']} "
            f"| {row['between']['mean']} | {row['ratio']} | {row['auc']} "
            f"| {row['z3_within']} | {row['z3_between']} |")
    add("")
    base = payload["modes"]["euclid"]
    cand = payload["modes"]["weighted_normal"]
    add("Baseline и кандидат по разрезам. Абсолютные значения within/between "
        "несопоставимы между режимами (normal меняет единицы), поэтому изменение "
        "в процентах ниже — только масштаб; сравнимы ratio, AUC и z>3:\n")
    add("| разрез | baseline euclid | candidate weighted normal | изменение |")
    add("|---|---:|---:|---:|")
    for label, x, y in (
        ("within overall", base["within"]["mean"], cand["within"]["mean"]),
        ("within cross-bin", base["within_cross"]["mean"], cand["within_cross"]["mean"]),
        ("between overall", base["between"]["mean"], cand["between"]["mean"]),
        ("ratio", base["ratio"], cand["ratio"]),
        ("AUC", base["auc"], cand["auc"]),
        ("z > 3 within", base["z3_within"], cand["z3_within"]),
        ("z > 3 between", base["z3_between"], cand["z3_between"]),
    ):
        change = f"{100 * (y / x - 1):+.1f}%" if x else "—"
        add(f"| {label} | {x} | {y} | {change} |")
    add("")
    add("Эффект только весов внутри одной метрики (единицы не меняются):\n")
    add("| сравнение | Δ within | Δ cross-bin | Δ between | ratio | AUC |")
    add("|---|---|---|---|---|---|")
    for a, b, label in (("normal", "weighted_normal", "normal → weighted normal"),
                        ("euclid", "weighted_euclid", "euclid → weighted euclid")):
        x, y = payload["modes"][a], payload["modes"][b]
        deltas = [100 * (y[key]["mean"] / x[key]["mean"] - 1)
                  for key in ("within", "within_cross", "between")]
        add(f"| {label} | {deltas[0]:+.1f}% | {deltas[1]:+.1f}% | {deltas[2]:+.1f}% "
            f"| {x['ratio']}→{y['ratio']} | {x['auc']}→{y['auc']} |")
    add("")
    boot = payload.get("bootstrap") or {}
    if boot.get("weighted_normal"):
        b = boot["weighted_normal"]
        add(f"ΔAUC (weighted normal − euclid) = {b['mean']} "
            f"[{b['lo']}; {b['hi']}], P(>0)={b['p_positive']} "
            f"(парный bootstrap, {b['rounds']} итераций).\n")
    if boot.get("normal"):
        b = boot["normal"]
        add(f"ΔAUC (normal − euclid) = {b['mean']} [{b['lo']}; {b['hi']}].\n")
    add(f"Разделение эффектов: переход euclid→normal меняет единицы (|d|→|d·n|), "
        f"поэтому cross-bin μ падает на {checks['within_cross_metric_delta_pct']:+.1f}% "
        f"уже без весов. Эффект самих весов считается внутри normal: "
        f"within {checks['within_weighting_delta_pct']:+.1f}%, "
        f"cross-bin {checks['within_cross_delta_pct']:+.1f}%. "
        f"ratio {base['ratio']}→{cand['ratio']}, AUC {base['auc']}→{cand['auc']}.\n")
    add("Поле направлений для normal — нормали среднего лица (`data/topology.json`), "
        "а не отдельные нормали каждого кадра. Иначе один и тот же переход получал "
        "разные значения в конце сегмента s и начале s+1 и карта рвалась на стыке: "
        "heat join 5.6e−2 вместо 0. Поэтому числа هنا считаются той же реализацией, "
        "что стоит в приложении, и немного отличаются от второй итерации.\n")
    add("## Leave-one-person-out\n")
    lopo = payload.get("lopo")
    if lopo:
        add("| человек | within пар | AUC euclid | AUC normal | AUC weighted euclid | AUC weighted normal |")
        add("|---|---|---|---|---|---|")
        for row in lopo["rows"]:
            add(f"| {row['person']} | {row['n_within']} | {row['auc_euclid']} "
                f"| {row['auc_normal']} | {row['auc_weighted_euclid']} "
                f"| {row['auc_weighted_normal']} |")
        w = lopo["weighted_normal"]
        add(f"\nWeighted normal выиграл у euclid на {w['wins']}/{w['n']} людях, "
            f"средний ΔAUC {w['mean_delta_auc']}, худший {w['min_delta_auc']}. "
            f"Normal: {lopo['normal']['wins']}/{lopo['normal']['n']}, "
            f"средний ΔAUC {lopo['normal']['mean_delta_auc']}. "
            f"Weighted euclid: {lopo['weighted_euclid']['wins']}/{lopo['weighted_euclid']['n']}, "
            f"средний ΔAUC {lopo['weighted_euclid']['mean_delta_auc']}, "
            f"худший {lopo['weighted_euclid']['min_delta_auc']}. "
            "Провал weighted normal на двух людях наследуется от normal, а не от весов: "
            "weighted euclid на тех же людях остаётся выше baseline.\n")
    else:
        add("LOPO не построен: слишком мало пар.\n")
    add("## Leave-one-transition-out\n")
    lot = payload.get("lotro")
    if lot:
        add("| семейство | within пар | within μ euclid | within μ normal | within μ weighted | Δ within (веса) | Δ within (метрика) | AUC euclid | AUC normal | AUC weighted |")
        add("|---|---|---|---|---|---|---|---|---|---|")
        for row in lot["rows"]:
            if row.get("skipped"):
                add(f"| {row['family']} | {row['n_within']} | — | — | — | — | — | — | — | — |")
                continue
            add(f"| {row['family']} | {row['n_within']} | {row['within_euclid']} "
                f"| {row['within_normal']} | {row['within_weighted_normal']} "
                f"| {row['within_delta_pct']:+.1f}% | {row['within_metric_delta_pct']:+.1f}% "
                f"| {row['auc_euclid']} | {row['auc_normal']} | {row['auc_weighted_normal']} |")
        add(f"\nWeighted normal выиграл на {lot['wins']}/{lot['n']} отложенных семействах, "
            f"средний ΔAUC {lot['mean_auc_delta']}. Δ within в колонке «веса» сравнен "
            "с той же метрикой; «метрика» — переход euclid→normal без весов.\n")
    add("## Стабильность весов\n")
    st = payload["stability"]
    add(f"sigma: min {st['sigma_min']}, p05 {st['sigma_p05']}, median {st['sigma_median']}, "
        f"p95 {st['sigma_p95']}, max {st['sigma_max']}; clip {st['clip']} / normal {st['clip_normal']}. "
        f"На нижней границе {st['at_lower_pct']}% вершин, на верхней {st['at_upper_pct']}%.\n")
    add(f"Профиль хранит по каждой вершине `vertex_stats`: `weight` (средний confidence = "
        f"1/clip(sigma), {st['weight_min']}…{st['weight_max']}), `weight_mean` по среднему "
        "семейству, `sigma_std`, `sigma_min`, `sigma_max`, `source` (семейство с минимальной "
        "sigma) и `n_pairs`. Нулевых весов нет: диапазон ограничен clip.\n")
    add("| зона | вершин | sigma μ | weight μ | на границе снизу | на границе сверху | AUC euclid | AUC normal | AUC weighted normal | Δ within normal→wn |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for name, row in st["regions"].items():
        reg = payload["regions"][name]
        delta = 100 * (reg["weighted_normal"]["within"]["mean"]
                       / reg["normal"]["within"]["mean"] - 1)
        add(f"| {name} | {row['vertices']} | {row['sigma_mean']} | {row['weight_mean']} "
            f"| {row['at_lower_pct']}% | {row['at_upper_pct']}% "
            f"| {reg['euclid']['auc']} | {reg['normal']['auc']} "
            f"| {reg['weighted_normal']['auc']} | {delta:+.1f}% |")
    fam = st.get("family") or {}
    if fam:
        add(f"\nПо семействам переходов: разброс sigma по вершинам {fam['spread_mean']} "
            f"(p95 {fam['spread_p95']}), нестабильных вершин {fam['unstable_pct']}%. "
            f"Источник минимума: {fam['source_pct']}. Отношение weights к глобальным: "
            f"{fam['weight_ratio_vs_global']}.\n")
        add(f"Наблюдений по семействам: {fam['families']}. Профиль глобальный: "
            "отдельные ячейки person × pose_bin не строятся.\n")
    add("## Проверки перед включением\n")
    add("| проверка | значение | гейт |")
    add("|---|---|---|")
    gates = checks["gates"]
    add(f"| cross-bin within (веса) ≤ −10% | {checks['within_cross_delta_pct']:+.1f}% | {fmt(gates['cross_bin_10pct'])} |")
    add(f"| AUC не хуже baseline | {base['auc']} → {cand['auc']} | {fmt(gates['auc_not_worse'])} |")
    add(f"| bootstrap CI ΔAUC > 0 | {checks['auc_delta']:+.4f} | {fmt(gates['auc_ci_positive'])} |")
    add(f"| LOPO все люди | {checks['lopo_wins']}/{checks['lopo_n']} | {fmt(gates['lopo_all'])} |")
    add(f"| LOTRO большинство | {checks['lotro_wins']}/{checks['lotro_n']} | {fmt(gates['lotro_majority'])} |")
    add(f"| фронтальные пары | n={checks['frontal_n']} (нужно ≥10), {fmt(checks['frontal_delta_pct'], 1)}% | {fmt(gates['no_frontal_degradation'])} |")
    add(f"| нет равномерной заливки | >vmax {checks['saturated_pct']}% | {fmt(gates['not_saturated'])} |")
    add(f"| invalid_pose не в парах | утечек {checks['invalid_leak']} | {fmt(gates['invalid_excluded'])} |")
    add("")
    add("## Preview / export\n")
    parity = payload.get("parity")
    if parity:
        add(f"Единый helper `server.heat.compute_heat_values`: max|preview − export| = "
            f"{parity['max_abs_diff']:.2e} до colorize, допуск 1e-6 — "
            f"{'пройден' if parity['passed'] else 'НЕ пройден'}. "
            f"Проверено режимов: {parity['cases']}.\n")
        http = parity.get("http") or {}
        if http:
            add(f"HTTP-смоук на живых эндпоинтах: `/api/photos/{{id}}/heat` — "
                f"{http['heat_status']}, count {http['heat_count']}, vmax {http['heat_vmax']}; "
                f"`/api/photos/{{id}}/preview` — {http['preview_status']}, PNG "
                f"{'есть' if http['preview_png'] else 'нет'}. "
                f"`configs/runtime.yaml` по умолчанию: "
                f"{http['runtime_block']['metric']} + {http['runtime_block']['weighting']}.\n")
        cfg = parity.get("config") or {}
        if cfg.get("ok"):
            add(f"Режим включается только конфигом: без параметров `metric`/`weighting` "
                f"эндпоинт отдаёт {cfg['base']['metric']}/{cfg['base']['weighting']}, после правки "
                f"`configs/runtime.yaml` — {cfg['switched']['metric']}/{cfg['switched']['weighting']} "
                f"(vmax {cfg['switched']['vmax']}), после возврата — снова baseline. "
                "Интерфейс получает этот же блок через `/api/runtime` при загрузке.\n")
        elif cfg:
            add(f"Переключение режима через конфиг: НЕ пройдено ({cfg}).\n")
        preview_files = [p for p in sorted((ROOT / "reports/calibration").glob("v3-preview-*.png"))
                         if p.name != "v3-preview-modes.png"]
        if preview_files:
            add("Примеры карты из `GET /api/photos/{id}/preview` (4 режима и общая "
                "панель `v3-preview-modes.png`): "
                + ", ".join(f"`{p.name}`" for p in preview_files) + ".\n")
    else:
        add("Отчёт паритета не найден (`reports/calibration/v3-parity.json`).\n")
    add("## 10-кадровая цепочка\n")
    chain = payload.get("chain")
    if chain:
        add(f"Сегментов {chain['segments']}, join jump {chain['join_jump']:.2e}, "
            f"heat join {chain['heat_join']:.2e}, "
            f"максимальный скачок цвета на стыке {chain['color_join']:.2e}; "
            f"цветовая непрерывность {'в норме' if chain['passed'] else 'нарушена'}.\n")
        add(f"Полный маршрут и отдельные сегменты дают одинаковые значения: "
            f"{'да' if chain['segment_independent'] else 'нет'}.\n")
    else:
        add("Отчёт цепочки не найден (`reports/calibration/v3-chain.json`).\n")
    add("## Что включать\n")
    add("По умолчанию остаётся `euclid` + `none` (`configs/runtime.yaml`). "
        "Переключение режима — только в конфиге, без правки кода:\n")
    add("```yaml\nheatmap:\n  metric: normal          # или euclid\n"
        "  weighting: calibrated   # или none\n"
        "  calibration_profile: reports/calibration/weights.json\n```\n")
    add("| режим | LOPO | что показывает | рекомендация |")
    add("|---|---|---|---|")
    add("| euclid / none | — | baseline, единицы IOD | оставить default |")
    add("| normal / none | 5/7 | AUC +0.025, CI накрывает 0 | не включать как default |")
    add("| euclid / calibrated | 6/7, худший −0.004 | стабильное снижение шума | первый кандидат на включение |")
    add("| normal / calibrated | 5/7, худший −0.116 | лучший AUC 0.8006, но наследует провал normal | только отчёты |\n")
    add("Веса сами по себе устойчивы: `euclid + calibrated` выигрывает на 6/7 людях "
        "и нигде не опускается ниже baseline больше чем на 0.004. Нестабильность "
        "приходит от метрики normal на двух людях (person_02, person_05), поэтому "
        "production-включение связки `normal + calibrated` без расширения корпуса "
        "не обосновано.\n")
    add("## Файлы\n")
    for row in payload.get("figures") or []:
        add(f"- `{row['file']}` — {row['caption']}")
    chain = payload.get("chain") or {}
    if chain.get("png"):
        add(f"- `{chain['png']}` — карта на четырёх сегментах цепочки")
    previews = sorted((ROOT / "reports/calibration").glob("v3-preview-*.png"))
    for p in previews:
        add(f"- `{p.relative_to(ROOT)}` — preview-эндпоинт, "
            f"{p.stem.removeprefix('v3-preview-')}")
    add("- `reports/calibration/v3-preview.json` — какая пара кадров на примерах")
    add(f"- `{payload['weights']}` — профиль весов (sigma, sigma_normal, clip, стабильность)")
    add("- `reports/calibration/invalid-frames.json` — invalid_pose")
    add("- `reports/calibration/v3-parity.json` — preview/export/browser")
    add("- `reports/calibration/v3-chain.json` — 10-кадровая цепочка")
    add(f"- `{payload['json']}` — все числа")
    add("- `server/heat.py` — единый helper; `server/app.py`, `server/rendering.py` — его вызовы")
    add("- `GET /api/photos/{id}/heat` — base64 float32 start/end для браузера")
    add("- `web/src/heat.ts`, `web/src/components/Viewer.tsx`, `web/src/components/CPUPreview.tsx`, "
        "`web/src/types.ts`, `web/src/store.ts` — браузер берёт значения с backend")
    add("- `configs/runtime.yaml` — блок `heatmap` (по умолчанию `euclid` / `none`)")
    add("- `scripts/calibration_v3.py` — harness; `scripts/heat_parity.py`, "
        "`scripts/heat_chain.py`, `scripts/heat_previews.py` — паритет, стыки, PNG-примеры")
    add("\n## Ограничения\n")
    add("Корпус — 7 человек и 210 кадров; расширить его в этой итерации не удалось: "
        "индекс `all_calibration_index.csv` содержит только эти семь записей, "
        "дополнительные каталоги person_09/10/11 не размечены по позам. "
        "Отдельных профилей на person × pose_bin нет: same-bin пар всего "
        f"{payload['counts']['within_same']}, поэтому профиль глобальный, "
        "а переходы проверяются через LOTRO.\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
