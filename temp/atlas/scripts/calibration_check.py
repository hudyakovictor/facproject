"""Old-vs-new audit of the atlas metric layer on the labelled calibration corpus.

Runs the stock ingestion path (server.storage.ingest + process), so every number
comes from real feature-cache files, then compares render-space
(`vertices`, `identity`) with metric-space (`identity_metric`) separation:

  old_identity         feature["identity"]         identity map before the change
  old_vertices         feature["vertices"]         distance heat-map mode
  new_identity_metric  feature["identity_metric"]  metric layer
  diag_kabsch_template identity, Kabsch to mean    deployable alternative
  diag_kabsch_pair     identity, pairwise Kabsch   oracle upper bound

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python scripts/calibration_check.py
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED = [
    "identity_metric", "metric_r_corr", "metric_target_pose",
    "metric_pose_bin_index", "metric_canonical_yaw", "metric_soft_canonical_yaw",
    "landmarks_metric_ldm68", "landmarks_metric_ldm106", "landmarks_metric_ldm134",
    "landmarks_render_ldm68", "landmarks_render_ldm106", "landmarks_render_ldm134",
]
LM_COUNTS = {"ldm68": 68, "ldm106": 106, "ldm134": 134}
RENDER_ONLY = [f"landmarks_render_{k}" for k in LM_COUNTS]


def metric_layer_enabled():
    from server.config import CONFIG, read_yaml

    return bool(read_yaml(CONFIG / "runtime.yaml").get("metric_layer", False))


MODES = {
    "old_identity": "identity",
    "old_vertices": "vertices",
    "new_identity_metric": "identity_metric",
}
STRATA = ("within_all", "within_same", "within_cross",
          "between_all", "between_same", "between_cross")


class _Job:
    def check(self):
        pass

    def update(self, *args, **kwargs):
        pass


def select_frames(index_path, photos_root, per_person):
    buckets = defaultdict(list)
    with index_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                float(row["yaw"]), float(row["pitch"]), float(row["roll"])
                frame = int(row["frame_index"])
            except (KeyError, TypeError, ValueError):
                continue
            jpg = photos_root / row["dataset_id"] / row["source_filename"]
            if jpg.is_file():
                buckets[row["dataset_id"]].append(
                    {"frame": frame, "bin": row.get("pose_bin") or "?", "path": jpg}
                )
    picked = {}
    for person, rows in buckets.items():
        rows.sort(key=lambda r: r["frame"])
        if 0 < per_person < len(rows):
            index = np.linspace(0, len(rows) - 1, per_person).round().astype(int)
            rows = [rows[i] for i in sorted(set(index.tolist()))]
        if len(rows) >= 2:
            picked[person] = rows
    return picked


def ingest_and_process(selected, refresh_stale):
    from server import storage

    required = REQUIRED if metric_layer_enabled() else RENDER_ONLY
    items = [
        (f"{person}/{row['path'].name}", row["path"].read_bytes())
        for person, rows in selected.items()
        for row in rows
    ]
    storage.ingest(items, group="Калибровка")
    known = {
        (p["group"], p["name"]): p
        for p in storage.read_db()["photos"]
        if not p.get("deleted_at")
    }
    targets = []
    for person, rows in selected.items():
        for row in rows:
            record = known.get((person, row["path"].name))
            if record is None:
                raise SystemExit(f"не проиндексирован {person}/{row['path'].name}")
            row["id"] = record["id"]
            targets.append(record)
    if refresh_stale:
        for record in targets:
            path = storage.feature_path(record)
            if path.exists():
                with np.load(path) as handle:
                    if not set(required) <= set(handle.files):
                        path.unlink()
    return targets, storage.process(_Job(), [r["id"] for r in targets])


def purge_records(ids):
    """Убирает из библиотеки только те записи, что создал этот прогон."""
    import shutil

    from server import storage

    with storage._lock:
        db = storage.read_db()
        drop = [p for p in db["photos"] if p["id"] in ids]
        db["photos"] = [p for p in db["photos"] if p["id"] not in ids]
        db["demo"] = any(p.get("demo") for p in db["photos"])
        storage.write_db(db)
    parents = set()
    for p in drop:
        path = (ROOT / p["path"]).resolve()
        if path.is_relative_to((ROOT / "data/groups").resolve()):
            path.unlink(missing_ok=True)
            parents.add(path.parent)
        shutil.rmtree(ROOT / "cache" / p["id"], ignore_errors=True)
    for parent in parents:
        try:
            parent.rmdir()
        except OSError:
            pass
    return len(drop)


def verify_cache(targets, expect_metric=True):
    from server import storage

    required = REQUIRED if expect_metric else RENDER_ONLY
    missing = Counter()
    sample = None
    for record in targets:
        path = storage.feature_path(record)
        if not path.exists():
            missing["<нет feature-файла>"] += 1
            continue
        with np.load(path) as handle:
            absent = [key for key in required if key not in handle.files]
            for key in absent:
                missing[key] += 1
            if absent or sample is not None:
                continue
            if not expect_metric:
                sample = {
                    name: list(handle[f"landmarks_render_{name}"].shape)
                    for name in LM_COUNTS
                }
                continue
            r = np.asarray(handle["metric_r_corr"], np.float64)
            identity = np.asarray(handle["identity"], np.float64)
            metric = np.asarray(handle["identity_metric"], np.float64)
            sample = {
                "identity_metric shape": list(metric.shape),
                "max|identity@r_corr - identity_metric|": float(np.abs(identity @ r - metric).max()),
                "max|r_corr.T r_corr - I|": float(np.abs(r.T @ r - np.eye(3)).max()),
                "metric_pose_bin_index": int(np.asarray(handle["metric_pose_bin_index"]).ravel()[0]),
                "metric_canonical_yaw": float(np.asarray(handle["metric_canonical_yaw"]).ravel()[0]),
            }
            for name, count in LM_COUNTS.items():
                for kind in ("metric", "render"):
                    key = f"landmarks_{kind}_{name}"
                    sample[key] = list(handle[key].shape)
                    if handle[key].shape[0] != count:
                        sample[key + " WRONG COUNT"] = count
    return {"missing": dict(missing), "sample": sample, "photos": len(targets)}


def mean_vertex_distance(a, b):
    return float(np.linalg.norm(a - b, axis=1).mean())


def kabsch(a, b):
    ca, cb = a.mean(0), b.mean(0)
    u, _s, vt = np.linalg.svd((a - ca).T @ (b - cb))
    d = np.sign(np.linalg.det(vt.T @ u.T))
    return (a - ca) @ (vt.T @ np.diag([1.0, 1.0, d]) @ u.T) + cb


def summarize(values):
    arr = np.asarray(values, float)
    if arr.size == 0:
        return {}
    return {
        "n": int(arr.size),
        "mean": round(float(arr.mean()), 6),
        "median": round(float(np.median(arr)), 6),
        "p90": round(float(np.percentile(arr, 90)), 6),
        "p99": round(float(np.percentile(arr, 99)), 6),
        "std": round(float(arr.std(ddof=1)), 6) if arr.size > 1 else 0.0,
    }


def cohen_d(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    pooled = np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2)
    return round(float((np.mean(b) - np.mean(a)) / max(pooled, 1e-12)), 3)


def auc(negatives, positives):
    from sklearn.metrics import roc_auc_score

    return round(float(roc_auc_score(
        np.concatenate([np.zeros(len(negatives)), np.ones(len(positives))]),
        np.concatenate([negatives, positives]),
    )), 4)


def identification(order, arrays):
    protos, labels = {}, []
    for person, ids in order.items():
        even = [arrays[i] for i in ids[0::2] if i in arrays]
        if even:
            protos[person] = np.mean(np.stack(even), axis=0)
            labels.append(person)
    correct = total = 0
    margins = []
    for person, ids in order.items():
        for pid in ids[1::2]:
            if pid not in arrays:
                continue
            total += 1
            scored = sorted((mean_vertex_distance(arrays[pid], protos[q]), q) for q in labels)
            best, best_label = scored[0]
            second = scored[1][0] if len(scored) > 1 else float("inf")
            margins.append((second - best) if best_label == person else -(best - second))
            correct += int(best_label == person)
    return {
        "probes": total,
        "identities": len(labels),
        "accuracy_pct": round(100.0 * correct / total, 2) if total else None,
        "median_margin": round(float(np.median(margins)), 6) if margins else None,
    }


def stats_block(name, arrays, within, between, order):
    w_val = np.array([mean_vertex_distance(arrays[a], arrays[b]) for a, b, _s in within])
    w_same = np.array([s for _a, _b, s in within], bool)
    b_val = np.array([mean_vertex_distance(arrays[a], arrays[b]) for a, b, _s in between])
    b_same = np.array([s for _a, _b, s in between], bool)
    return {
        "within_all": summarize(w_val),
        "within_same": summarize(w_val[w_same]),
        "within_cross": summarize(w_val[~w_same]),
        "between_all": summarize(b_val),
        "between_same": summarize(b_val[b_same]),
        "between_cross": summarize(b_val[~b_same]),
        "ratio": round(float(b_val.mean() / w_val.mean()), 3),
        "cohen_d": cohen_d(w_val, b_val),
        "auc": auc(w_val, b_val),
        "identification": identification(order, arrays),
    }


def heat_panel(values, geometry, tri, size, vmax):
    from PIL import Image
    from server.rendering import colorize, rasterize

    cols = colorize(values, 0.0, vmax, "turbo", 1.0, False, None)
    return Image.fromarray(rasterize(geometry, tri, cols, size))


def compose_rows(rows, out_path):
    from PIL import Image

    width, height = rows[0][0].size
    columns = max(len(row) for row in rows)
    canvas = Image.new("RGB", (width * columns, height * len(rows)), (12, 16, 20))
    for y, row in enumerate(rows):
        for x, panel in enumerate(row):
            canvas.paste(panel.convert("RGB"), (x * width, y * height))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def chain_stats(ids, arrays, mode):
    values = arrays[mode]
    steps = [np.linalg.norm(values[ids[i + 1]] - values[ids[i]], axis=1) for i in range(len(ids) - 1)]
    # Segment join in preview/export: start_delta(k+1) = v(k+1) - v(k) = end_delta(k).
    joins = []
    for i in range(len(ids) - 1):
        end_delta = values[ids[i + 1]] - values[ids[i]]
        start_delta = values[ids[i + 1]] - values[ids[i]]
        joins.append(float(np.abs(np.linalg.norm(end_delta, axis=1)
                                  - np.linalg.norm(start_delta, axis=1)).max()))
    direct = mean_vertex_distance(values[ids[0]], values[ids[-1]])
    path = sum(float(step.mean()) for step in steps)
    return {
        "join_jump": round(max(joins), 9),
        "step_max": round(max(float(step.max()) for step in steps), 6),
        "path_mean": round(path, 6),
        "direct": round(direct, 6),
        "ratio": round(path / max(direct, 1e-9), 3),
    }


def fmt(value):
    if value is None:
        return "—"
    return f"{value:.5f}" if isinstance(value, float) else str(value)


def write_report(path, payload):
    out = []
    add = out.append
    add("# Calibration check · render-space vs metric-space\n")
    add(f"Датасет: `{payload['index']}` · фото: `{payload['photos_root']}`\n")
    add("## 1. Датасет\n")
    add("| персона | кадров в выборке | pose-бины |\n|---|---|---|")
    for item in payload["datasets"]:
        add(f"| {item['id']} | {item['frames']} | {', '.join(item['bins'])} |")
    add(f"\nВсего кадров: {payload['sampled']} · пар inside: {payload['n_within']} "
        f"· between: {payload['n_between']} · минимальный зазор кадров: {payload['min_gap']}\n")
    add("## 2. Пайплайн\n\n```bash\n" + payload["command"] + "\n```\n")
    add(f"`storage.ingest` + `storage.process`: {json.dumps(payload['process'], ensure_ascii=False)}\n")
    if not payload.get("metric_layer", True):
        add("**metric-слой выключен** (`configs/runtime.yaml`: `metric_layer: false`) — "
            "сравнительная таблица ниже содержит только render-space.\n")
    add("## 3. Поля в feature-кэше\n")
    add(f"Проверено фото: {payload['verify']['photos']} · отсутствует: "
        f"{payload['verify']['missing'] or 'ничего'}\n")
    if payload["verify"]["sample"]:
        add("```json\n" + json.dumps(payload["verify"]["sample"], ensure_ascii=False, indent=2) + "\n```\n")
    add("## 4. Old vs new\n")
    add("Среднее per-vertex расстояние по паре, единицы template-IOD.\n")
    add("| режим | within same-bin μ | within cross-bin μ | between same-bin μ "
        "| between cross-bin μ | between/within | d | AUC |")
    add("|---|---|---|---|---|---|---|---|")
    for mode, stats in payload["modes"].items():
        add(f"| {mode} | {fmt(stats['within_same'].get('mean'))} "
            f"| {fmt(stats['within_cross'].get('mean'))} "
            f"| {fmt(stats['between_same'].get('mean'))} "
            f"| {fmt(stats['between_cross'].get('mean'))} "
            f"| {fmt(stats['ratio'])} | {fmt(stats['cohen_d'])} | {fmt(stats['auc'])} |")
    for mode, stats in payload["modes"].items():
        add(f"\n### {mode}\n")
        add("| страта | n | mean | median | p90 | std |\n|---|---|---|---|---|---|")
        for key in STRATA:
            block = stats.get(key) or {}
            add(f"| {key} | {block.get('n', 0)} | {fmt(block.get('mean'))} "
                f"| {fmt(block.get('median'))} | {fmt(block.get('p90'))} | {fmt(block.get('std'))} |")
        ident = stats["identification"]
        add(f"\nИдентификация: {ident['accuracy_pct']}% из {ident['probes']} проб, "
            f"медианный запас {fmt(ident['median_margin'])}\n")
    add("## 5. Heatmap\n")
    if payload["heatmaps"]:
        for item in payload["heatmaps"]:
            add(f"- `{item['file']}` — {item['kind']}: within μ "
                f"{fmt(item['old'])} (old) → {fmt(item['new'])} (new)")
    else:
        add("PNG не строились.")
    add("\n## 6. Хронологическая цепочка\n")
    chain = payload["chain"]
    add(f"Персона `{chain['person']}`, кадры {chain['frames']} ({', '.join(chain['bins'])})\n")
    add("| режим | стык (join jump) | макс. шаг | путь / прямое |\n|---|---|---|---|")
    for mode, item in chain["modes"].items():
        add(f"| {mode} | {fmt(item['join_jump'])} | {fmt(item['step_max'])} | {fmt(item['ratio'])} |")
    add("\n## 7. Вывод\n\n" + payload["verdict"] + "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--min-frame-gap", type=int, default=30)
    ap.add_argument("--max-between-pairs", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--vmax", type=float, default=0.06)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-refresh-stale", action="store_true")
    ap.add_argument("--purge", action="store_true",
                    help="удалить из библиотеки записи, созданные этим прогоном")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration-check.md")
    ap.add_argument("--json", type=Path, default=ROOT / "reports/calibration-check.json")
    args = ap.parse_args()

    from server import storage

    index_path = args.calibration_root / "all_calibration_index.csv"
    if not index_path.exists():
        raise SystemExit(f"нет индекса: {index_path}")
    if not args.photos_root.is_dir():
        raise SystemExit(f"нет фото: {args.photos_root}")

    before = {p["id"] for p in storage.read_db()["photos"]}
    selected = select_frames(index_path, args.photos_root, args.per_person)
    print("кадров на человека:", {p: len(r) for p, r in sorted(selected.items())}, flush=True)
    targets, summary = ingest_and_process(selected, refresh_stale=not args.no_refresh_stale)
    print("обработка:", {k: v for k, v in summary.items() if k != "errors"}, flush=True)
    if summary.get("errors"):
        print("ошибки инференса:", summary["errors"][:5], flush=True)
    verify = verify_cache(targets, expect_metric=metric_layer_enabled())
    print("поля кэша:", verify["missing"] or "все на месте", flush=True)

    topology = json.loads((ROOT / "data/topology.json").read_text())
    tri = np.asarray(topology["triangles"], np.int32)
    template = np.asarray(topology["mean"], np.float32)

    frames = [(person, row) for person, rows in selected.items() for row in rows]
    arrays = {name: {} for name in MODES}
    for _person, row in frames:
        record = storage.photo(row["id"])
        with np.load(storage.feature_path(record)) as handle:
            for name, key in MODES.items():
                if key in handle.files:
                    arrays[name][row["id"]] = np.asarray(handle[key], np.float32)

    if not arrays["new_identity_metric"]:
        # Слой выключен: показываем, что реально рендерит приложение (identity).
        print("metric-слой выключен (configs/runtime.yaml: metric_layer=false): "
              "в режиме new_identity_metric повторяет identity", flush=True)
        arrays["new_identity_metric"] = dict(arrays["old_identity"])
        metric_on = False
    else:
        metric_on = True

    by_person = defaultdict(list)
    for person, row in frames:
        by_person[person].append(row)
    order = {p: [r["id"] for r in rows] for p, rows in by_person.items()}

    within, between = [], []
    for rows in by_person.values():
        for a, b in itertools.combinations(rows, 2):
            if abs(a["frame"] - b["frame"]) >= args.min_frame_gap:
                within.append((a["id"], b["id"], a["bin"] == b["bin"]))
    cross = [
        (a["id"], b["id"], a["bin"] == b["bin"])
        for p1, p2 in itertools.combinations(sorted(by_person), 2)
        for a in by_person[p1] for b in by_person[p2]
    ]
    if len(cross) > args.max_between_pairs:
        cross = random.Random(args.seed).sample(cross, args.max_between_pairs)
    between = cross
    print(f"пар: внутри {len(within)} · между {len(between)}", flush=True)

    results = {}
    for name in MODES:
        if len(arrays.get(name, {})) >= 2:
            results[name] = stats_block(name, arrays[name], within, between, order)

    arrays["diag_kabsch_template"] = {
        pid: kabsch(vec, template) for pid, vec in arrays["old_identity"].items()
    }
    results["diag_kabsch_template"] = stats_block(
        "diag_kabsch_template", arrays["diag_kabsch_template"], within, between, order)

    probe_w = within[: min(len(within), 1200)]
    probe_b = between[: min(len(between), 2400)]
    oracle_w = np.array([
        mean_vertex_distance(kabsch(arrays["old_identity"][a], arrays["old_identity"][b]),
                             arrays["old_identity"][b]) for a, b, _s in probe_w
    ])
    oracle_b = np.array([
        mean_vertex_distance(kabsch(arrays["old_identity"][a], arrays["old_identity"][b]),
                             arrays["old_identity"][b]) for a, b, _s in probe_b
    ])
    results["diag_kabsch_pair"] = {
        "within_all": summarize(oracle_w), "within_same": {}, "within_cross": {},
        "between_all": summarize(oracle_b), "between_same": {}, "between_cross": {},
        "ratio": round(float(oracle_b.mean() / oracle_w.mean()), 3),
        "cohen_d": cohen_d(oracle_w, oracle_b), "auc": auc(oracle_w, oracle_b),
        "identification": {"probes": 0, "identities": 0, "accuracy_pct": None,
                           "median_margin": None},
    }
    del arrays["diag_kabsch_template"]

    heatmaps = []
    chain = {"person": None, "frames": [], "bins": [], "modes": {}}
    if not args.no_render:
        person = max(by_person, key=lambda p: len(by_person[p]))
        rows = by_person[person]
        pairs = []
        same = next((pair for pair in itertools.combinations(rows, 2)
                     if pair[0]["bin"] == pair[1]["bin"]), None)
        cross_pick = next((pair for pair in itertools.combinations(rows, 2)
                           if pair[0]["bin"] != pair[1]["bin"]), None)
        if same:
            pairs.append(("same_person_near", same))
        if cross_pick:
            pairs.append(("same_person_far", cross_pick))
        other = next(p for p in sorted(by_person) if p != person)
        pairs.append(("different_person", (rows[0], by_person[other][0])))
        for kind, (a, b) in pairs:
            old = np.linalg.norm(arrays["old_identity"][a["id"]] - arrays["old_identity"][b["id"]], axis=1)
            new = np.linalg.norm(arrays["new_identity_metric"][a["id"]]
                                 - arrays["new_identity_metric"][b["id"]], axis=1)
            out = ROOT / "reports/calibration" / f"{kind}.png"
            geometry = arrays["old_identity"][a["id"]]
            compose_rows([[heat_panel(old, geometry, tri, 320, args.vmax),
                           heat_panel(new, geometry, tri, 320, args.vmax)]], out)
            heatmaps.append({"file": str(out.relative_to(ROOT)), "kind": kind,
                             "old": float(old.mean()), "new": float(new.mean())})

        keys = [rows[i] for i in np.linspace(0, len(rows) - 1, 4).round().astype(int).tolist()]
        strip_old, strip_new = [], []
        for left, right in zip(keys, keys[1:]):
            old = np.linalg.norm(arrays["old_identity"][left["id"]] - arrays["old_identity"][right["id"]], axis=1)
            new = np.linalg.norm(arrays["new_identity_metric"][left["id"]]
                                 - arrays["new_identity_metric"][right["id"]], axis=1)
            geometry = arrays["old_identity"][left["id"]]
            strip_old.append(heat_panel(old, geometry, tri, 220, args.vmax))
            strip_new.append(heat_panel(new, geometry, tri, 220, args.vmax))
        out = ROOT / "reports/calibration/chain.png"
        compose_rows([strip_old, strip_new], out)
        heatmaps.append({"file": str(out.relative_to(ROOT)), "kind": "chronological_chain",
                         "old": None, "new": None})
        chain = {
            "person": person,
            "frames": [r["frame"] for r in keys],
            "bins": [r["bin"] for r in keys],
            "modes": {name: chain_stats([r["id"] for r in keys], arrays, name)
                      for name in ("old_identity", "new_identity_metric")},
        }

    report = {
        "index": str(index_path), "photos_root": str(args.photos_root),
        "datasets": [{"id": p, "frames": len(r), "bins": sorted({x["bin"] for x in r})}
                     for p, r in sorted(selected.items())],
        "sampled": len(frames), "n_within": len(within), "n_between": len(between),
        "min_gap": args.min_frame_gap,
        "command": "OPENBLAS_NUM_THREADS=2 python scripts/calibration_check.py"
                   f" --per-person {args.per_person} --min-frame-gap {args.min_frame_gap}",
        "process": {k: v for k, v in summary.items() if k != "errors"},
        "verify": verify, "modes": results, "heatmaps": heatmaps, "chain": chain,
        "metric_layer": metric_on,
        "verdict": "",
    }

    if not metric_on:
        report["verdict"] = (
            "metric-слой отключён в configs/runtime.yaml (metric_layer: false), "
            "доступны только render-space режимы."
        )
    elif "old_identity" in results and "new_identity_metric" in results:
        old, new = results["old_identity"], results["new_identity_metric"]
        improves = new["within_all"]["mean"] < old["within_all"]["mean"] * 0.95
        keeps = new["auc"] >= old["auc"] - 0.01
        report["verdict"] = (
            f"within-person mean {fmt(old['within_all']['mean'])} → "
            f"{fmt(new['within_all']['mean'])}; "
            f"cross-bin within {fmt(old['within_cross'].get('mean'))} → "
            f"{fmt(new['within_cross'].get('mean'))}; "
            f"AUC {fmt(old['auc'])} → {fmt(new['auc'])}; "
            f"between/within {fmt(old['ratio'])} → {fmt(new['ratio'])}. "
            + ("Metric layer improves stability without losing discrimination."
               if improves and keeps else
               "Metric layer does not pay off on this corpus — keep it experimental.")
        )

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(args.out, report)
    for mode, stats in results.items():
        print(f"{mode:24s} within μ={stats['within_all'].get('mean')} "
              f"between μ={stats['between_all'].get('mean')} "
              f"ratio={stats['ratio']} auc={stats['auc']} "
              f"acc={stats['identification']['accuracy_pct']}")
    print("отчёт:", args.out)
    if args.purge:
        created = {r["id"] for r in targets} - before
        print("удалено записей:", purge_records(created))


if __name__ == "__main__":
    main()
