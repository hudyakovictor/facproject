"""Landmark-sweep: шум обычных точек ldm68 / ldm106 / ldm134.

Вопрос итерации 4: как ведут себя штатные landmarks (center + IOD, то же
пространство, что у heatmap) внутри одного человека и между людьми. Пары
строятся по правилам v3: within/between, зазор 30 кадров, чётные кадры
для sigma, нечётные для оценки. Каждый набор проверяется в трёх вариантах
(euclid, normal, weighted) через те же нормали среднего лица, что и карта.

Это отчёт, в приложение ничего не подключается:

    cd /Users/victorkhudyakov/work/temp/atlas
    python scripts/landmark_sweep.py

Пишет reports/calibration-ldm.md, reports/calibration-ldm.json и PNG
в reports/figures/.
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

from calibration_check import select_frames  # noqa: E402
from calibration_sweep import auc, auc_delta_ci, summarize  # noqa: E402
from calibration_v3 import (  # noqa: E402
    FAMILIES,
    LABEL_MISMATCH,
    YAW_LIMIT,
    build_pairs,
    family_of,
    people_indices,
    topology,
)
from server import storage  # noqa: E402
from server.heat import template_normals  # noqa: E402

SETS = ("ldm68", "ldm106", "ldm134")
MODES = ("euclid", "normal", "weighted_euclid", "weighted_normal")
ZONES = ("brows", "eyes", "nose", "mouth", "jaw", "profile_contour")
ZONE_68 = {
    **{i: "jaw" for i in range(4, 13)},
    **{i: "profile_contour" for i in (*range(0, 4), *range(13, 17))},
    **{i: "brows" for i in range(17, 27)},
    **{i: "nose" for i in range(27, 36)},
    **{i: "eyes" for i in range(36, 48)},
    **{i: "mouth" for i in range(48, 68)},
}
OUTLIER_Z = 3.0
SIGMA_FLOOR = 0.25


def db_records():
    return {(p["group"], p["name"]): p
            for p in storage.read_db()["photos"] if not p.get("deleted_at")}


def index_rows(index_path):
    import csv

    out = {}
    with index_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out[(row["dataset_id"], row["source_filename"])] = row
    return out


def load_frames(selected, index, lm68, extra_invalid):
    """Кадры с точками всех наборов в общем пространстве center + IOD."""
    known = db_records()
    frames = []
    missing = defaultdict(int)
    for person, rows in selected.items():
        for order, row in enumerate(rows):
            record = known.get((person, row["path"].name))
            if record is None:
                raise SystemExit(f"нет записи в библиотеке: {person}/{row['path'].name}")
            meta_path = storage.feature_path(record).with_name("meta.json")
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            with np.load(storage.feature_path(record)) as handle:
                vertices = np.asarray(handle["vertices"], np.float32)
                angles = np.ravel(handle["alpha"])
                yaw = float(np.degrees(angles[225]))
                points, absent = {}, []
                for name in SETS:
                    key = f"landmarks_render_{name}"
                    if key in handle:
                        points[name] = np.asarray(handle[key], np.float64)
                    else:
                        absent.append(name)
                        missing[name] += 1
            eye = vertices[lm68]
            left, right = eye[36:42].mean(axis=0), eye[42:48].mean(axis=0)
            center, iod = (left + right) / 2, max(float(np.linalg.norm(left - right)), 1e-8)
            for name in points:
                points[name] = ((points[name] - center) / iod).astype(np.float64)
            source = index.get((person, row["path"].name), {})
            csv_yaw = float(source.get("yaw", "nan"))
            reasons = []
            if abs(yaw) > YAW_LIMIT:
                reasons.append(f"|yaw|={yaw:.1f}>{YAW_LIMIT:.0f}")
            if np.isfinite(csv_yaw) and abs(yaw - csv_yaw) > LABEL_MISMATCH:
                reasons.append(f"label yaw={csv_yaw:.1f} vs {yaw:.1f}")
            if (person, row["frame"]) in extra_invalid and not reasons:
                reasons.append(extra_invalid[(person, row["frame"])])
            if absent:
                reasons.append("missing:" + ",".join(absent))
            frames.append({
                "id": record["id"],
                "person": person,
                "frame": int(row["frame"]),
                "bin": row["bin"],
                "order": order,
                "yaw": yaw,
                "sharpness": float(meta.get("sharpness", float("nan"))),
                "points": points,
                "valid": not reasons,
                "invalid_reason": "; ".join(reasons),
            })
    return frames, dict(missing)


def mean_face_landmarks():
    data = json.loads((ROOT / "data/topology.json").read_text())
    mean = np.asarray(data["mean"], np.float64)
    marks = {k: np.asarray(v, np.int32) for k, v in data["landmarks"].items()}
    eye = mean[marks["ldm68"]]
    left, right = eye[36:42].mean(axis=0), eye[42:48].mean(axis=0)
    center, iod = (left + right) / 2, float(np.linalg.norm(left - right))
    return {k: (mean[v] - center) / iod for k, v in marks.items()}, marks


def zone_map(set_name, mean_points):
    """Зона точки: для 68 — прямо, для 106/134 — по ближайшей точке 68."""
    if set_name == "ldm68":
        return [ZONE_68[i] for i in range(68)], {
            "method": "ldm68 index", "nearest_median": 0.0, "nearest_max": 0.0}
    ref = mean_points["ldm68"]
    dist = np.linalg.norm(mean_points[set_name][:, None, :] - ref[None, :, :], axis=2)
    nearest = dist.argmin(axis=1)
    zones = []
    for idx, hit in enumerate(nearest):
        zone = ZONE_68[int(hit)]
        x = mean_points[set_name][idx, 0]
        if zone == "jaw" and abs(x) >= 0.9:
            zone = "profile_contour"
        zones.append(zone)
    return zones, {
        "method": "nearest ldm68 point on mean face",
        "nearest_median": round(float(np.median(dist.min(axis=1))), 4),
        "nearest_p90": round(float(np.percentile(dist.min(axis=1), 90)), 4),
        "nearest_max": round(float(dist.min(axis=1).max()), 4),
    }


def fit_sigma(frames, sets, gap):
    """sigma по точкам на чётных same-person парах, как в v3."""
    even = people_indices(frames, {f["person"] for f in frames}, 0)
    acc = {name: {"e": [], "n": [], "count": 0} for name in sets}
    for ids in even.values():
        for a, b in itertools.combinations(sorted(ids), 2):
            if frames[b]["frame"] - frames[a]["frame"] < gap:
                continue
            for name in sets:
                if name not in frames[a]["points"] or name not in frames[b]["points"]:
                    continue
                diff = frames[b]["points"][name] - frames[a]["points"][name]
                e = np.linalg.norm(diff, axis=1)
                n = np.abs((diff * frames[a]["normals"][name]).sum(axis=1))
                bucket = acc[name]
                if not bucket["count"]:
                    bucket["e"] = []
                    bucket["n"] = []
                    bucket["e2"] = []
                    bucket["n2"] = []
                    bucket["count"] = 0
                bucket["e"].append(e)
                bucket["n"].append(n)
                bucket["count"] += 1
    out = {}
    for name, bucket in acc.items():
        if not bucket["count"]:
            continue
        e = np.asarray(bucket["e"], np.float64)
        n = np.asarray(bucket["n"], np.float64)
        sigma_e = np.sqrt(np.maximum((e * e).mean(axis=0) - e.mean(axis=0) ** 2, 0.0))
        sigma_n = np.sqrt(np.maximum((n * n).mean(axis=0) - n.mean(axis=0) ** 2, 0.0))
        sigma_e = np.maximum(sigma_e, float(np.median(sigma_e)) * SIGMA_FLOOR + 1e-12)
        sigma_n = np.maximum(sigma_n, float(np.median(sigma_n)) * SIGMA_FLOOR + 1e-12)
        clip_e = np.percentile(sigma_e, [5, 95])
        clip_n = np.percentile(sigma_n, [5, 95])
        sigma_ec = np.clip(sigma_e, *clip_e).astype(np.float32)
        sigma_nc = np.clip(sigma_n, *clip_n).astype(np.float32)
        out[name] = {
            "pairs": int(bucket["count"]),
            "sigma_e": sigma_ec,
            "sigma_n": sigma_nc,
            "weights_e": (1.0 / sigma_ec).astype(np.float32),
            "weights_n": (1.0 / sigma_nc).astype(np.float32),
            "clip": [round(float(clip_e[0]), 6), round(float(clip_e[1]), 6)],
            "clip_normal": [round(float(clip_n[0]), 6), round(float(clip_n[1]), 6)],
        }
    return out


def contributions(a, b, normals):
    diff = b - a
    return np.linalg.norm(diff, axis=1), np.abs((diff * normals).sum(axis=1))


def pair_scalars(e, n, sigma):
    return {
        "euclid": float(e.mean()),
        "normal": float(n.mean()),
        "weighted_euclid": float((e * sigma["weights_e"]).sum()
                                 / sigma["weights_e"].sum()),
        "weighted_normal": float((n * sigma["weights_n"]).sum()
                                 / sigma["weights_n"].sum()),
        "z_euclid": float((e * sigma["weights_e"]).mean()),
        "z_normal": float((n * sigma["weights_n"]).mean()),
    }


def sweep(frames, within, between, sigma):
    """Скаляры по парам + покадровая статистика по семействам."""
    acc = {name: {"within": defaultdict(list), "between": defaultdict(list)}
           for name in SETS}
    point = {name: defaultdict(lambda: defaultdict(list)) for name in SETS}
    for i, j in within:
        family = family_of(frames[i]["bin"], frames[j]["bin"])
        for name in SETS:
            if name not in frames[i]["points"] or name not in frames[j]["points"]:
                continue
            e, n = contributions(frames[i]["points"][name],
                                 frames[j]["points"][name], frames[i]["normals"][name])
            for key, value in pair_scalars(e, n, sigma[name]).items():
                acc[name]["within"][key].append(value)
            for family_key in (family, "all"):
                point[name][family_key]["e"].append(e)
                point[name][family_key]["n"].append(n)
    for i, j in between:
        for name in SETS:
            if name not in frames[i]["points"] or name not in frames[j]["points"]:
                continue
            e, n = contributions(frames[i]["points"][name],
                                 frames[j]["points"][name], frames[i]["normals"][name])
            for key, value in pair_scalars(e, n, sigma[name]).items():
                acc[name]["between"][key].append(value)
    return acc, point


def set_metrics(frames, within, between, acc, name):
    w = acc[name]["within"]
    b = acc[name]["between"]
    same = np.asarray([frames[i]["bin"] == frames[j]["bin"] for i, j in within], bool)
    rows = {}
    for mode in MODES:
        wv = np.asarray(w[mode], np.float64)
        bv = np.asarray(b[mode], np.float64)
        if not wv.size or not bv.size:
            continue
        rows[mode] = {
            "within": summarize(wv),
            "within_same": summarize(wv[same]),
            "within_cross": summarize(wv[~same]),
            "between": summarize(bv),
            "ratio": round(float(bv.mean() / max(wv.mean(), 1e-12)), 3),
            "auc": auc(wv, bv),
        }
    for base, candidate in (("euclid", "weighted_euclid"),
                            ("normal", "weighted_normal")):
        if base not in rows or candidate not in rows:
            continue
        rows[f"delta_{candidate}"] = auc_delta_ci(
            frames, within, between,
            w[base], w[candidate], b[base], b[candidate], 200, 42)
    return rows


def point_table(frames, within, point, sigma, zones):
    """Рейтинг точек и сводка по зонам."""
    rows = {}
    for name in SETS:
        if name not in sigma:
            continue
        families = point[name]
        total = families["all"]["e"]
        if not total:
            continue
        e_all = np.asarray(total, np.float64)
        n_all = np.asarray(families["all"]["n"], np.float64)
        sigma_e = sigma[name]["sigma_e"]
        per_point = []
        for k in range(e_all.shape[1]):
            per_point.append({
                "point": k,
                "zone": zones[name][0][k],
                "mean": round(float(e_all[:, k].mean()), 5),
                "p90": round(float(np.percentile(e_all[:, k], 90)), 5),
                "max": round(float(e_all[:, k].max()), 5),
                "outlier_share": round(float((e_all[:, k] > OUTLIER_Z * sigma_e[k]).mean()), 4),
                "mean_normal": round(float(n_all[:, k].mean()), 5),
            })
        ranked = sorted(per_point, key=lambda r: -r["mean"])
        zone_rows = {}
        for zone in ZONES:
            idx = [r["point"] for r in per_point if r["zone"] == zone]
            if not idx:
                continue
            zone_rows[zone] = {
                "n_points": len(idx),
                "mean": round(float(np.mean([per_point[i]["mean"] for i in idx])), 5),
                "p90": round(float(np.mean([per_point[i]["p90"] for i in idx])), 5),
                "outlier_share": round(
                    float(np.mean([per_point[i]["outlier_share"] for i in idx])), 4),
                "top20_share": None,
            }
        top20 = {r["point"] for r in ranked[:20]}
        for zone, row in zone_rows.items():
            row["top20_share"] = round(
                len([i for i in top20 if per_point[i]["zone"] == zone])
                / max(len(top20), 1), 3)
        family_rows = {}
        for family in ("all", *FAMILIES):
            if family not in families:
                continue
            arr = np.asarray(families[family]["e"], np.float64)
            n_arr = np.asarray(families[family]["n"], np.float64)
            family_rows[family] = {
                "pairs": int(arr.shape[0]),
                "mean": round(float(arr.mean()), 5),
                "p90": round(float(np.percentile(arr, 90)), 5),
                "mean_normal": round(float(n_arr.mean()), 5),
            }
        rows[name] = {
            "points": len(per_point),
            "sigma_pairs": sigma[name]["pairs"],
            "clip": sigma[name]["clip"],
            "clip_normal": sigma[name]["clip_normal"],
            "top": ranked[:15],
            "zones": zone_rows,
            "families": family_rows,
            "mean_overall": round(float(e_all.mean()), 5),
            "mean_normal_overall": round(float(n_all.mean()), 5),
        }
    return rows


def comparability(mean_points, marks, point_rows):
    out = {"overlaps": {}, "nearest": {}, "shared_rank": {}}
    index_sets = {k: set(marks[k].tolist()) for k in SETS}
    for a, b in (("ldm68", "ldm106"), ("ldm68", "ldm134"), ("ldm106", "ldm134")):
        out["overlaps"][f"{a}/{b}"] = {
            "shared": len(index_sets[a] & index_sets[b]),
            "share_of_a": round(len(index_sets[a] & index_sets[b]) / len(index_sets[a]), 3),
            "share_of_b": round(len(index_sets[a] & index_sets[b]) / len(index_sets[b]), 3),
        }
    for a, b in (("ldm68", "ldm106"), ("ldm68", "ldm134"), ("ldm106", "ldm134")):
        dist = np.linalg.norm(mean_points[a][:, None, :] - mean_points[b][None, :, :], axis=2)
        out["nearest"][f"{a}/{b}"] = {
            "median": round(float(np.median(dist.min(axis=1))), 4),
            "p90": round(float(np.percentile(dist.min(axis=1), 90)), 4),
            "max": round(float(dist.min(axis=1).max()), 4),
        }
    # Согласие шума на общих вершинах: ранги mean|d| внутри набора.
    pos68 = {int(v): i for i, v in enumerate(marks["ldm68"])}
    pos106 = {int(v): i for i, v in enumerate(marks["ldm106"])}
    shared = sorted(set(pos68) & set(pos106))
    if shared and "ldm68" in point_rows and "ldm106" in point_rows:
        full = {}
        for name in ("ldm68", "ldm106"):
            full[name] = {row["point"]: row["mean"]
                          for row in point_rows[name].get("all_points", [])}
        if full["ldm68"] and full["ldm106"]:
            a = np.asarray([full["ldm68"][pos68[v]] for v in shared])
            b = np.asarray([full["ldm106"][pos106[v]] for v in shared])
            order_a, order_b = a.argsort().argsort(), b.argsort().argsort()
            out["shared_rank"] = {
                "shared": len(shared),
                "spearman": round(float(np.corrcoef(order_a, order_b)[0, 1]), 3),
            }
    return out


def figures(point_rows, metrics_rows, out_dir):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6), dpi=130)
    palette = {"brows": "#5bd7bb", "eyes": "#7dbff0", "nose": "#e8b76d",
               "mouth": "#e693b0", "jaw": "#b29ced", "profile_contour": "#e05c5c"}
    for ax, name in zip(axes, SETS, strict=True):
        rows = point_rows.get(name, {}).get("top", [])[:12]
        if not rows:
            ax.set_axis_off()
            continue
        labels = [f"#{r['point']} {r['zone']}" for r in rows][::-1]
        values = [r["mean"] for r in rows][::-1]
        colors = [palette[r["zone"]] for r in rows][::-1]
        ax.barh(labels, values, color=colors)
        ax.set_title(f"{name}: самые шумные точки", fontsize=10)
        ax.tick_params(labelsize=7)
        ax.set_xlabel("mean |Δ|, IOD", fontsize=8)
    fig.tight_layout()
    path = out_dir / "ldm-points.png"
    fig.savefig(path)
    plt.close(fig)
    files.append({"file": str(path.relative_to(ROOT)),
                  "caption": "Рейтинг шумных landmark-точек по наборам (цвет — зона)"})

    fig, ax = plt.subplots(figsize=(13.2, 2.6), dpi=130)
    ax.set_axis_off()
    columns = ["набор", "within μ", "median", "p90", "std", "between μ",
               "ratio", "AUC euclid", "AUC w-euclid", "ΔAUC", "CI"]
    table = []
    for name in SETS:
        row = metrics_rows.get(name, {})
        base = row.get("euclid", {})
        weighted = row.get("weighted_euclid", {})
        delta = row.get("delta_weighted_euclid") or {}
        table.append([
            name,
            f"{base.get('within', {}).get('mean', float('nan')):.4f}",
            f"{base.get('within', {}).get('median', float('nan')):.4f}",
            f"{base.get('within', {}).get('p90', float('nan')):.4f}",
            f"{base.get('within', {}).get('std', float('nan')):.4f}",
            f"{base.get('between', {}).get('mean', float('nan')):.4f}",
            f"{base.get('ratio', float('nan')):.3f}",
            f"{base.get('auc', float('nan')):.4f}",
            f"{weighted.get('auc', float('nan')):.4f}",
            f"{delta.get('mean', float('nan')):+.4f}",
            f"[{delta.get('lo', 0):+.3f}; {delta.get('hi', 0):+.3f}]",
        ])
    table_obj = ax.table(cellText=table, colLabels=columns, loc="center", cellLoc="center")
    table_obj.auto_set_font_size(False)
    table_obj.set_fontsize(7.5)
    table_obj.scale(1.0, 1.5)
    ax.set_title("ldm68 / ldm106 / ldm134: euclid и weighted euclid", fontsize=10)
    fig.tight_layout()
    path = out_dir / "ldm-table.png"
    fig.savefig(path)
    plt.close(fig)
    files.append({"file": str(path.relative_to(ROOT)),
                  "caption": "Сводная таблица набор × метрика"})
    return files


def report_md(payload, path):
    lines = ["# Landmark-sweep: ldm68 / ldm106 / ldm134", ""]
    d = payload["dataset"]
    lines += [
        f"Кадров: {d['frames']} ({d['people']} человек), зазор {d['gap']}, "
        f"чётные кадры — sigma, нечётные — оценка.",
        "Валидных по наборам: " + ", ".join(
            f"{k} {v}" for k, v in d["valid"].items()) + ".",
        f"Пар: within {payload['counts']['within']}, between {payload['counts']['between']}.",
        "",
        "## Сводка по наборам",
        "",
        "| набор | within μ | median | p90 | std | between μ | ratio | AUC euclid | "
        "AUC normal | AUC w-euclid | AUC w-normal | ΔAUC w-euclid | ΔAUC w-normal |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in SETS:
        row = payload["sets"].get(name, {})
        if not row:
            continue
        cell = [name]
        base = row.get("euclid", {}).get("within", {})
        for key in ("mean", "median", "p90", "std"):
            value = base.get(key)
            cell.append(f"{value:.4f}" if isinstance(value, float) else "—")
        cell.append(f"{row.get('euclid', {}).get('between', {}).get('mean', float('nan')):.4f}")
        cell.append(f"{row.get('euclid', {}).get('ratio', float('nan')):.3f}")
        for mode in ("euclid", "normal", "weighted_euclid", "weighted_normal"):
            cell.append(f"{row.get(mode, {}).get('auc', float('nan')):.4f}")
        for key in ("delta_weighted_euclid", "delta_weighted_normal"):
            delta = row.get(key) or {}
            cell.append(
                f"{delta.get('mean', float('nan')):+.4f} "
                f"[{delta.get('lo', 0):+.3f}; {delta.get('hi', 0):+.3f}]")
        lines.append("| " + " | ".join(cell) + " |")
    lines += ["", "## Шум по зонам", "",
              "| набор | зона | точек | mean | p90 | выбросы >3σ | доля в top-20 |",
              "|---|---|---|---|---|---|---|"]
    for name in SETS:
        for zone, row in payload["points"].get(name, {}).get("zones", {}).items():
            lines.append(
                f"| {name} | {zone} | {row['n_points']} | {row['mean']:.4f} | "
                f"{row['p90']:.4f} | {row['outlier_share']:.3f} | {row['top20_share']:.2f} |")
    lines += ["", "## Самые шумные точки", ""]
    for name in SETS:
        rows = payload["points"].get(name, {}).get("top", [])[:10]
        if not rows:
            continue
        lines.append(f"**{name}**")
        lines.append("")
        lines.append("| # | зона | mean | p90 | max | выбросы |")
        lines.append("|---|---|---|---|---|---|")
        for row in rows:
            lines.append(
                f"| {row['point']} | {row['zone']} | {row['mean']:.4f} | "
                f"{row['p90']:.4f} | {row['max']:.4f} | {row['outlier_share']:.3f} |")
        lines.append("")
    lines += ["## Сопоставимость наборов", ""]
    cmp = payload["comparability"]
    for pair, row in cmp["overlaps"].items():
        lines.append(f"- {pair}: общих вершин {row['shared']} "
                     f"({row['share_of_a']:.0%} от первого, {row['share_of_b']:.0%} от второго)")
    for pair, row in cmp["nearest"].items():
        lines.append(f"- {pair}: ближайшая точка mean face — медиана {row['median']:.3f} IOD, "
                     f"p90 {row['p90']:.3f}, max {row['max']:.3f}")
    if cmp.get("shared_rank"):
        lines.append(f"- Согласие шума на общих вершинах 68/106: "
                     f"Spearman {cmp['shared_rank']['spearman']:.3f} "
                     f"({cmp['shared_rank']['shared']} точек)")
    lines += ["", "## Семейства переходов", "",
              "| набор | семейство | пар | mean | p90 | mean normal |",
              "|---|---|---|---|---|---|"]
    for name in SETS:
        for family, row in payload["points"].get(name, {}).get("families", {}).items():
            lines.append(
                f"| {name} | {family} | {row['pairs']} | {row['mean']:.4f} | "
                f"{row['p90']:.4f} | {row['mean_normal']:.4f} |")
    lines += ["", "## Вывод", ""]
    for line in payload["conclusion"]:
        lines.append(f"- {line}")
    lines += ["", "## Файлы", ""]
    for item in payload["files"]:
        lines.append(f"- `{item['file']}` — {item['caption']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def conclusion(payload):
    rows = payload["sets"]
    lines = []
    best = max(SETS, key=lambda n: rows.get(n, {}).get("euclid", {}).get("auc", 0))
    lines.append(f"Лучшее разделение within/between по euclid: {best} "
                 f"(AUC {rows[best]['euclid']['auc']:.4f}).")
    weights = []
    for name in SETS:
        delta = rows.get(name, {}).get("delta_weighted_euclid") or {}
        weights.append((name, delta.get("mean", 0), delta.get("lo", 0)))
    weights.sort(key=lambda item: -item[1])
    top = weights[0]
    lines.append(f"Взвешивание по landmark-точкам даёт максимальный прирост AUC(euclid) "
                 f"на {top[0]} (ΔAUC {top[1]:+.4f}, CI от {top[2]:+.4f}).")
    norm_weights = []
    for name in SETS:
        delta = rows.get(name, {}).get("delta_weighted_normal") or {}
        norm_weights.append((name, delta.get("mean", 0), delta.get("lo", 0)))
    norm_weights.sort(key=lambda item: -item[1])
    norm_top = norm_weights[0]
    lines.append(f"Для normal-компоненты лучший прирост — {norm_top[0]} "
                 f"(ΔAUC {norm_top[1]:+.4f}, CI от {norm_top[2]:+.4f}); "
                 f"у ldm68 он {rows.get('ldm68', {}).get('delta_weighted_normal', {}).get('mean', 0):+.4f}.")
    prof = {}
    for name in SETS:
        row = payload["points"].get(name, {}).get("zones", {}).get("profile_contour")
        prof[name] = row["mean"] if row else None
    inner = {}
    for name in SETS:
        rows_ = payload["points"].get(name, {}).get("zones", {})
        inner[name] = np.mean([r["mean"] for z, r in rows_.items()
                               if z not in ("profile_contour", "jaw")]) if rows_ else None
    loud = [n for n in SETS if prof.get(n) and inner.get(n) and prof[n] > inner[n] * 1.3]
    if loud:
        lines.append("Профильный контур шумит заметно сильнее внутренних зон: "
                     + ", ".join(f"{n} ×{prof[n] / inner[n]:.2f}" for n in loud)
                     + ". Для контроля шума в профиле контурные точки стоит держать "
                       "отдельно от внутренних.")
    else:
        lines.append("Профильный контур не выделяется по шуму относительно внутренних зон.")
    no_contour = "ldm134" in rows and not payload["points"].get("ldm134", {}).get(
        "zones", {}).get("profile_contour")
    if no_contour:
        lines.append("В ldm134 нет контурных точек профиля (только глаза, брови, рот, нос) — "
                     "набор не показывает шум контура по построению.")
    lines.append("Рекомендация: для диагностики качества кадра и контроля шума использовать "
                 "ldm68 — он совпадает с heat space (центр и IOD по его же глазам), "
                 "покрывает все зоны и даёт ближайший к карте набор точек.")
    lines.append("ldm106 и ldm134 пользователю не выводить: другой набор вершин, "
                 "сопоставление с ldm68 только по ближайшим точкам, а ldm134 вообще "
                 "не содержит контура челюсти.")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--gap", type=int, default=30)
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration-ldm.md")
    ap.add_argument("--json", type=Path, default=ROOT / "reports/calibration-ldm.json")
    ap.add_argument("--figures", type=Path, default=ROOT / "reports/figures")
    args = ap.parse_args()

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

    tri, lm68 = topology()
    frames, missing = load_frames(selected, index, lm68, extra_invalid)
    normals_field = template_normals(tri)
    mean_points, marks = mean_face_landmarks()
    for frame in frames:
        frame["normals"] = {name: normals_field[marks[name]] for name in SETS
                            if name in frame["points"]}

    invalid = [{"person": f["person"], "frame": f["frame"], "bin": f["bin"],
                "reason": f["invalid_reason"]} for f in frames if not f["valid"]]
    valid_frames = [f for f in frames if f["valid"]]
    within, between = build_pairs(valid_frames, args.gap)
    # build_pairs возвращает индексы в переданном списке — работаем с ним.
    frames_valid = valid_frames
    sigma = fit_sigma(frames_valid, SETS, args.gap)
    acc, point = sweep(frames_valid, within, between, sigma)
    metrics_rows = {name: set_metrics(frames_valid, within, between, acc, name)
                    for name in SETS}
    zones = {name: zone_map(name, mean_points) for name in SETS}
    point_rows = point_table(frames_valid, within, point, sigma, zones)
    for name in point_rows:
        point_rows[name]["all_points"] = sorted(
            ({"point": k, "mean": round(float(np.asarray(point[name]["all"]["e"])[:, k].mean()), 5)}
             for k in range(np.asarray(point[name]["all"]["e"]).shape[1])),
            key=lambda r: r["point"])
    cmp_rows = comparability(mean_points, marks, point_rows)
    for name in SETS:
        if name in point_rows:
            point_rows[name]["top"] = sorted(
                point_rows[name]["top"], key=lambda r: -r["mean"])[:15]

    payload = {
        "dataset": {
            "frames": len(frames), "people": len(selected), "gap": args.gap,
            "valid": {name: sum(1 for f in frames if f["valid"] and name in f["points"])
                      for name in SETS},
            "missing": missing,
            "invalid": invalid[:20], "invalid_count": len(invalid),
        },
        "counts": {"within": len(within), "between": len(between)},
        "sigma": {name: {"pairs": row["pairs"], "clip": row["clip"],
                         "clip_normal": row["clip_normal"]}
                  for name, row in sigma.items()},
        "sets": metrics_rows,
        "points": point_rows,
        "comparability": cmp_rows,
        "files": [],
    }
    payload["conclusion"] = conclusion(payload)
    payload["files"] = figures(point_rows, metrics_rows, args.figures)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md(payload, args.out)
    print(json.dumps({"sets": {n: metrics_rows[n].get("euclid", {}).get("auc")
                               for n in metrics_rows},
                      "within": len(within), "between": len(between)}, ensure_ascii=False))
    return payload


if __name__ == "__main__":
    main()
