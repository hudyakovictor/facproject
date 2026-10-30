"""Пересчёт таблиц v3 на расширенном корпусе (7 размеченных + 3 wild).

Читает reports/calibration/corpus-extra.json, где позы person_9/10/11
предсказаны моделью (ручной разметки нет). Считает те же четыре режима,
LOPO и LOTRO, что и v3, и сравнивает старый профиль весов с новым.

Новый профиль пишется только в reports/calibration/weights-v4.json —
production reports/calibration/weights.json не трогается.

    python scripts/corpus_v4.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import select_frames  # noqa: E402
from calibration_v3 import (  # noqa: E402
    MODES,
    build_pairs,
    collect,
    fit_noise,
    index_rows,
    load_frames,
    lopo,
    lotro,
    metrics,
    stability,
    topology,
)

LABELED = [f"person_{i:02d}" for i in range(1, 8)]
WILD = ["person_9", "person_10", "person_11"]


def load_extra(path: Path, photos_root: Path):
    payload = json.loads(path.read_text())
    selected, index = {}, {}
    skipped = []
    for row in payload["rows"]:
        person = row["person"]
        if row.get("status") != "ready":
            skipped.append(row)
            continue
        selected.setdefault(person, []).append({
            "frame": int(row["frame"]),
            "bin": row["bin"],
            "path": photos_root / person / row["filename"],
            "id": row["id"],
            "label_source": "predicted",
        })
        index[(person, row["filename"])] = {
            "yaw": row["yaw"], "pitch": row["pitch"], "roll": row["roll"],
            "pose_bin": row["bin"], "frame_index": row["frame"],
        }
    for person in selected:
        selected[person].sort(key=lambda r: r["frame"])
    return selected, index, skipped


def combined(args):
    index_path = args.calibration_root / "all_calibration_index.csv"
    labeled = select_frames(index_path, args.photos_root, args.per_person)
    index = index_rows(index_path)
    extra, extra_index, skipped = load_extra(args.extra, args.photos_root)
    for person, rows in extra.items():
        labeled.setdefault(person, [])
        labeled[person].extend(rows)
        labeled[person].sort(key=lambda r: r["frame"])
    index.update(extra_index)
    return labeled, index, skipped


def compare_profiles(path: Path, payload: dict):
    old = json.loads(path.read_text())
    old_sigma = np.clip(np.asarray(old["sigma"], np.float64), *old["clip"])
    new_sigma = np.clip(np.asarray(payload["sigma"], np.float64), *payload["clip"])
    old_w = 1.0 / np.maximum(old_sigma, 1e-12)
    new_w = 1.0 / np.maximum(new_sigma, 1e-12)
    rel = np.abs(new_w - old_w) / np.maximum(old_w, 1e-12)
    old_lo, old_hi = (float(v) for v in old["clip"])
    new_lo, new_hi = (float(v) for v in payload["clip"])
    old_lo_n, old_hi_n = (float(v) for v in old.get("clip_normal", old["clip"]))
    new_lo_n, new_hi_n = (float(v) for v in payload.get("clip_normal", payload["clip"]))
    old_sn = np.clip(np.asarray(old.get("sigma_normal", old["sigma"]), np.float64),
                     old_lo_n, old_hi_n)
    new_sn = np.clip(np.asarray(payload.get("sigma_normal", payload["sigma"]), np.float64),
                     new_lo_n, new_hi_n)
    return {
        "weights": int(len(old_w)),
        "relative_change": {
            "median": round(float(np.median(rel)), 4),
            "p90": round(float(np.percentile(rel, 90)), 4),
            "max": round(float(rel.max()), 4),
            "share_gt_10pct": round(float((rel > 0.10).mean()), 4),
            "share_gt_25pct": round(float((rel > 0.25).mean()), 4),
        },
        "correlation": round(float(np.corrcoef(old_w, new_w)[0, 1]), 4),
        "clip": {"old": [old_lo, old_hi], "new": [new_lo, new_hi]},
        "clip_normal": {"old": [old_lo_n, old_hi_n], "new": [new_lo_n, new_hi_n]},
        "at_bounds": {
            "old_lower": round(100 * float((old_sigma <= old_lo + 1e-12).mean()), 1),
            "old_upper": round(100 * float((old_sigma >= old_hi - 1e-12).mean()), 1),
            "new_lower": round(100 * float((new_sigma <= new_lo + 1e-12).mean()), 1),
            "new_upper": round(100 * float((new_sigma >= new_hi - 1e-12).mean()), 1),
            "old_lower_normal": round(100 * float((old_sn <= old_lo_n + 1e-12).mean()), 1),
            "new_lower_normal": round(100 * float((new_sn <= new_lo_n + 1e-12).mean()), 1),
        },
        "sigma_median": {"old": round(float(np.median(old_sigma)), 6),
                         "new": round(float(np.median(new_sigma)), 6)},
        "sigma_normal_median": {"old": round(float(np.median(old_sn)), 6),
                                "new": round(float(np.median(new_sn)), 6)},
    }


def frontal_split(frames, within, acc):
    def row(items):
        if not items:
            return None
        idx = np.asarray(items)
        e = np.asarray(acc["euclid"]["scalar"][: len(within)])
        w = np.asarray(acc["weighted_normal"]["scalar"][: len(within)])
        return {"n": int(len(idx)), "euclid": round(float(e[idx].mean()), 5),
                "weighted_normal": round(float(w[idx].mean()), 5)}

    pairs = [(k, i, j) for k, (i, j) in enumerate(within)
             if frames[i]["bin"] == frames[j]["bin"] == "frontal"]
    labeled = [k for k, i, _ in pairs if frames[i]["person"] in LABELED]
    wild = [k for k, i, _ in pairs if frames[i]["person"] in WILD]
    return {"labeled": row(labeled), "predicted": row(wild),
            "labeled_people": len({frames[i]["person"] for _, i, _ in pairs
                                   if frames[i]["person"] in LABELED}),
            "predicted_people": len({frames[i]["person"] for _, i, _ in pairs
                                     if frames[i]["person"] in WILD})}


def frontal_gap10(frames, gap=10):
    """Фронтальные кадры и пары при зазоре 10 — диагностика корпуса."""
    out = {}
    for key, people in (("labeled", LABELED), ("predicted", WILD)):
        rows = {}
        for person in people:
            ids = sorted(f["frame"] for f in frames
                         if f["person"] == person and f["valid"] and f["bin"] == "frontal")
            pairs = sum(1 for i, a in enumerate(ids) for b in ids[i + 1:] if b - a >= gap)
            rows[person] = {"frames": len(ids), "pairs_gap10": pairs}
        out[key] = {
            "people": rows,
            "people_with_3_frames": sum(1 for r in rows.values() if r["frames"] >= 3),
            "pairs_gap10": sum(r["pairs_gap10"] for r in rows.values()),
        }
    return out


def frontal_gap10_eval(frames, tri, cal, lm, people, gap=10):
    """Фронтальные within-пары при зазоре 10 (нечётные кадры, как в v3)."""
    pairs = []
    seen = set()
    for person in sorted({f["person"] for f in frames} & set(people)):
        ids = sorted(f["frame"] for f in frames
                     if f["person"] == person and f["valid"] and f["bin"] == "frontal"
                     and f["order"] % 2 == 1)
        index = {f["frame"]: i for i, f in enumerate(frames)
                 if f["person"] == person and f["valid"] and f["bin"] == "frontal"
                 and f["order"] % 2 == 1}
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if b - a >= gap:
                    pairs.append((index[a], index[b]))
                    seen.add(person)
    if not pairs:
        return None
    acc, _ = collect(frames, pairs, tri, cal, lm)
    row = {"n": len(pairs), "people": len(seen)}
    for name, _metric, _weighting in MODES:
        values = np.asarray(acc[name]["scalar"], np.float64)
        row[name] = round(float(values.mean()), 5)
    row["delta_pct"] = round(100 * (row["weighted_normal"] / row["euclid"] - 1), 1)
    return row


def lopo_figure(payload, out_dir: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = (payload["lopo"] or {}).get("rows", [])
    if not rows:
        return None
    modes = ["euclid", "normal", "weighted_euclid", "weighted_normal"]
    labels = ["euclid", "normal", "w-euclid", "w-normal"]
    colors = ["#7dbff0", "#e8b76d", "#5bd7bb", "#e05c5c"]
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11.5, 4.0), dpi=130)
    width = 0.2
    x = np.arange(len(rows))
    for k, (mode, label, color) in enumerate(zip(modes, labels, colors, strict=True)):
        values = [r[f"auc_{mode}"] for r in rows]
        ax.bar(x + (k - 1.5) * width, values, width, label=label, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels([r["person"] for r in rows], rotation=25, ha="right", fontsize=8)
    ax.set_ylim(0.45, 1.0)
    ax.set_ylabel("AUC (LOPO)", fontsize=9)
    ax.set_title("LOPO на расширенном корпусе: 7 размеченных + 3 wild", fontsize=10)
    ax.legend(fontsize=8, ncol=4)
    fig.tight_layout()
    path = out_dir / "v4-lopo.png"
    fig.savefig(path)
    plt.close(fig)
    return {"file": str(path.relative_to(ROOT)),
            "caption": "LOPO на 10 людях: 4 режима"}


def fmt(value):
    if value is None:
        return "—"
    return str(value)


def write_report(path: Path, payload: dict):
    lines = ["# Корпус v4: 7 размеченных + 3 wild", ""]
    d = payload["dataset"]
    lines += [
        f"Кадров {d['frames']}, валидных {d['valid']}, человек {len(d['people'])}. "
        f"Зазор {d['gap']}. Пространство: {d['space']}.",
        "",
        "person_9/10/11 — Wikimedia Commons без ручной разметки поз. Их позы "
        "предсказаны моделью (`label_source: predicted`), поэтому контроль "
        "`invalid_pose` по расхождению метки и yaw для них не работает. "
        "Это влияет на фронтальный гейт и на между-людьми статистику.",
        "",
        "| персона | кадров | валидных | фронтальных | источник поз |",
        "|---|---|---|---|---|",
    ]
    for person in d["people"]:
        row = d["per_person"][person]
        lines.append(f"| {person} | {row['frames']} | {row['valid']} | "
                     f"{row['frontal']} | {row['label_source']} |")
    lines += [
        "",
        f"Пропущено при обработке: {d['skipped']} кадров (лицо не найдено).",
        "",
        "## Четыре режима",
        "",
        "| режим | within μ | cross-bin μ | between μ | ratio | AUC |",
        "|---|---|---|---|---|---|",
    ]
    for name, _metric, _weighting in MODES:
        row = payload["modes"][name]
        lines.append(
            f"| {name} | {row['within']['mean']} | {row['within_cross']['mean']} "
            f"| {row['between']['mean']} | {row['ratio']} | {row['auc']} |")
    lines += ["", "## Leave-one-person-out", "",
              "| человек | within пар | AUC euclid | AUC normal | AUC w-euclid | AUC w-normal |",
              "|---|---|---|---|---|---|"]
    for row in (payload["lopo"] or {}).get("rows", []):
        lines.append(f"| {row['person']} | {row['n_within']} | {row['auc_euclid']} | "
                     f"{row['auc_normal']} | {row['auc_weighted_euclid']} | "
                     f"{row['auc_weighted_normal']} |")
    summary = {}
    for name in ("normal", "weighted_euclid", "weighted_normal"):
        summary[name] = (payload["lopo"] or {}).get(name)
    lines += ["", "Свод LOPO:"]
    for name, row in summary.items():
        if row:
            lines.append(f"- {name}: побед {row['wins']}/{row['n']}, "
                         f"средний ΔAUC {row['mean_delta_auc']:+.4f}, "
                         f"минимум {row['min_delta_auc']:+.4f}")
    lines += ["", "## Leave-one-transition-out", "",
              "| семейство | within пар | between пар | ΔAUC w-normal | пропущено |",
              "|---|---|---|---|---|"]
    for row in (payload["lotro"] or {}).get("rows", []):
        lines.append(f"| {row['family']} | {row['n_within']} | {row['n_between']} | "
                     f"{row.get('auc_delta', '—')} | {row.get('skipped', False)} |")
    lines += ["", "## Фронтальный гейт", ""]
    fr = payload["frontal"]
    if fr:
        for key, label in (("labeled", "размеченные"), ("predicted", "предсказанные")):
            row = fr.get(key)
            if row:
                lines.append(f"- {label}: пар {row['n']}, euclid {row['euclid']}, "
                             f"weighted normal {row['weighted_normal']}, "
                             f"людей {fr[key + '_people']}")
        pred = fr.get("predicted") or {}
        lab = fr.get("labeled") or {}
        if pred and lab and pred["euclid"]:
            lines.append(f"- Фронтальный гейт на размеченных: {lab['n']} пар; "
                         f"на предсказанных: {pred['n']} пар. Смешивать их нельзя: "
                         "у wild нет ручной метки.")
        gap10 = payload.get("frontal_gap10") or {}
        for key, label in (("labeled", "размеченные"), ("predicted", "предсказанные")):
            row = gap10.get(key)
            if row:
                lines.append(f"- {label}, зазор 10 (все кадры): "
                             f"{row['people_with_3_frames']} человек с ≥3 фронтальными, "
                             f"пар {row['pairs_gap10']}.")
        gap_eval = payload.get("frontal_gap10_eval") or {}
        for key, label in (("labeled", "размеченные"), ("predicted", "предсказанные")):
            row = gap_eval.get(key)
            if row:
                lines.append(f"- Зазор 10, нечётные кадры, {label}: {row['n']} пар, "
                             f"{row['people']} человек; euclid {row['euclid']}, "
                             f"weighted normal {row['weighted_normal']} "
                             f"({row['delta_pct']:+.1f}%).")
    else:
        lines.append("- Фронтальных within-пар нет; гейт не измеряется.")
    lines += ["", "## Стабильность весов", ""]
    w = payload["weights"]
    lines += [
        f"Старый профиль: `{w['old_profile']}`, новый: `{w['new_profile']}` "
        f"(в приложение не подключён).",
        "",
        f"- Медиана |Δweight|/weight: {w['relative_change']['median']:.2%}, "
        f"p90 {w['relative_change']['p90']:.2%}, max {w['relative_change']['max']:.2%}",
        f"- Доля вершин с изменением >10%: {w['relative_change']['share_gt_10pct']:.1%}, "
        f">25%: {w['relative_change']['share_gt_25pct']:.1%}",
        f"- Корреляция весов: {w['correlation']}",
        f"- Clip: старый {w['clip']['old']} → новый {w['clip']['new']}",
        f"- На нижней границе clip: {w['at_bounds']['old_lower']}% → "
        f"{w['at_bounds']['new_lower']}% (euclid), "
        f"{w['at_bounds']['old_lower_normal']}% → {w['at_bounds']['new_lower_normal']}% (normal)",
        f"- На верхней границе clip: {w['at_bounds']['old_upper']}% → "
        f"{w['at_bounds']['new_upper']}%",
        "",
        "## Вывод",
        "",
    ]
    lines += [f"- {line}" for line in payload["conclusion"]]
    for item in payload["files"]:
        lines.append(f"- `{item['file']}` — {item['caption']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--gap", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--extra", type=Path,
                    default=ROOT / "reports/calibration/corpus-extra.json")
    ap.add_argument("--old-weights", type=Path,
                    default=ROOT / "reports/calibration/weights.json")
    ap.add_argument("--weights", type=Path,
                    default=ROOT / "reports/calibration/weights-v4.json")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration-v4-corpus.md")
    ap.add_argument("--json", type=Path, default=ROOT / "reports/calibration-v4-corpus.json")
    args = ap.parse_args()

    selected, index, skipped = combined(args)
    print("people", sorted(selected), "rows", sum(len(v) for v in selected.values()))
    from calibration_check import ingest_and_process

    targets, process_info = ingest_and_process(selected, False)
    print("process", {k: process_info[k] for k in ("photos", "cache_hits", "errors")})
    tri, lm = topology()
    frames = load_frames(selected, index, tri, lm, {})
    valid = [f for f in frames if f["valid"]]
    people = sorted({f["person"] for f in frames})
    print("frames", len(frames), "valid", len(valid), "people", len(people))

    sigma_e, sigma_n, fit_pairs = fit_noise(frames, people, args.gap)
    from calibration_v3 import calibration, calibration_payload

    cal = calibration(sigma_e, sigma_n)
    cal_payload = calibration_payload(sigma_e, sigma_n)
    within, between = build_pairs(frames, args.gap)
    acc, _ = collect(frames, within + between, tri, cal, lm)
    modes = metrics(frames, acc, within, between)

    per_person = {}
    for person in people:
        own = [f for f in frames if f["person"] == person]
        per_person[person] = {
            "frames": len(own),
            "valid": sum(1 for f in own if f["valid"]),
            "frontal": sum(1 for f in own if f["valid"] and f["bin"] == "frontal"),
            "label_source": "manual+yaw" if person in LABELED else "predicted",
        }

    lopo_rows = lopo(frames, within, between, tri, lm, args.gap, args.seed)
    lotro_rows = lotro(frames, within, between, tri, lm, args.gap)
    old_weights = json.loads(args.old_weights.read_text())
    weights = {
        "old_profile": str(args.old_weights.relative_to(ROOT)),
        "new_profile": str(args.weights.relative_to(ROOT)),
        **compare_profiles(args.old_weights, cal_payload),
        "old_clip": old_weights.get("clip"),
        "new_clip": cal_payload["clip"],
        "source": {
            "people": people, "frames": len(frames), "valid": len(valid),
            "pairs": fit_pairs, "gap": args.gap,
            "label_sources": {p: per_person[p]["label_source"] for p in people},
        },
    }
    payload = {
        "dataset": {
            "people": people,
            "frames": len(frames),
            "valid": len(valid),
            "per_person": per_person,
            "gap": args.gap,
            "space": "center + IOD (eye-contour means ldm68 36:42/42:48)",
            "skipped": len(skipped),
        },
        "sigma_pairs": fit_pairs,
        "counts": {"within": len(within), "between": len(between)},
        "modes": modes,
        "lopo": lopo_rows,
        "lotro": lotro_rows,
        "frontal": frontal_split(frames, within, acc),
        "frontal_gap10": frontal_gap10(frames),
        "frontal_gap10_eval": {
            "labeled": frontal_gap10_eval(frames, tri, cal, lm, LABELED),
            "predicted": frontal_gap10_eval(frames, tri, cal, lm, WILD),
        },
        "weights": weights,
        "stability": stability(sigma_e, sigma_n, cal_payload["clip"],
                               cal_payload["clip_normal"], lm),
        "files": [],
    }
    base = modes["euclid"]
    cand = modes["weighted_normal"]
    lopo_wn = (lopo_rows or {}).get("weighted_normal") or {}
    lines = [
        f"Расширенный корпус: {len(people)} человек, {len(valid)} валидных кадров; "
        f"within {len(within)}, between {len(between)}.",
        f"Baseline euclid AUC {base['auc']}, weighted normal AUC {cand['auc']} "
        f"(Δ {cand['auc'] - base['auc']:+.4f}).",
        f"LOPO weighted normal: {lopo_wn.get('wins')}/{lopo_wn.get('n')} побед, "
        f"минимум {lopo_wn.get('min_delta_auc')}.",
        f"LOTRO: {(lotro_rows or {}).get('wins')}/{(lotro_rows or {}).get('n')} семейств.",
        f"Веса: медиана изменения {weights['relative_change']['median']:.1%}, "
        f"p90 {weights['relative_change']['p90']:.1%}, корреляция {weights['correlation']}.",
    ]
    payload["conclusion"] = lines
    figure = lopo_figure(payload, ROOT / "reports/figures")
    payload["files"] = [figure] if figure else []

    args.weights.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "version": 4,
        "method": "per-vertex sigma over same-person even-frame pairs, clip p05..p95",
        "space": payload["dataset"]["space"],
        "source": weights["source"],
        **cal_payload,
        "n_pairs": fit_pairs,
        "note": "Пересчёт на расширенном корпусе; в приложение не подключён.",
    }
    args.weights.write_text(json.dumps(profile, ensure_ascii=False, indent=1))
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    write_report(args.out, payload)
    print("modes", {k: (v["auc"], v["ratio"]) for k, v in modes.items()})
    print("lopo", lopo_wn)
    print("lotro", (lotro_rows or {}).get("wins"), (lotro_rows or {}).get("n"))
    print("report", args.out)


if __name__ == "__main__":
    main()
