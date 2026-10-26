"""Разделительная калибровка: «тот же человек» vs «другой человек».

Датасет: /Volumes/SDCARD/photo/calibration_dataset — 7 подписанных личностей
(photos/person_01..07, кадры из видео) + all_calibration_index.csv с точными
углами позы (yaw/pitch/roll) на каждый кадр.

Что делаем:
  1. По CSV отбираем фронтальные кадры каждого лица (|yaw|<=--max-yaw и т.д.).
  2. Реконструируем dense-меш ровно тем же путём, что и UI:
     reconstruct_image -> align_identity_mesh  (кэш в .npy).
  3. Пары ВНУТРИ одного лица  -> распределение шума «тот же человек».
     Пары МЕЖДУ разными лицами -> распределение «другой человек».
  4. Считаем разделение и предлагаем:
       - score_scale для _score_from_distance (где «другой» уходит к 0),
       - vertex_threshold для «% выше порога» (флор шума одного человека),
       - per-zone пороги аномалии (μ+3σ того же человека).

Это калибровка ШУМОВОЙ ШКАЛЫ, а не вероятность личности (доктрина соблюдается).

Единицы — доли RMS-масштаба по 106 ландмаркам (патч 04): расстояния в ней примерно в
1.56 раза больше, чем в прежних (доля max-радиуса сетки), поэтому сетка кандидатов
пересчитана через `aligner.MAXR_TO_RMS106`, а кэш мешей лежит в отдельной папке — по
имени `.npy` старой нормировки не отличить от новой.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app8.reconstruction import reconstruct_image  # noqa: E402
from morphing.backend.aligner import MAXR_TO_RMS106, align_identity_mesh  # noqa: E402
from morphing.backend.analysis import similarity_metrics  # noqa: E402

DS_ROOT = Path("/Volumes/SDCARD/photo/calibration_dataset")
CSV_PATH = DS_ROOT / "calibration_datasets" / "all_calibration_index.csv"
PHOTOS_DIR = DS_ROOT / "photos"
OLD_UNIT_THRESHOLDS = (0.02, 0.025, 0.03, 0.035, 0.04, 0.05, 0.06)
CANDIDATE_THRESHOLDS = [round(t * MAXR_TO_RMS106, 5) for t in OLD_UNIT_THRESHOLDS]


def load_frontal_frames(csv_path: Path, max_yaw: float, max_pitch: float, max_roll: float, per_person: int):
    """Отбираем фронтальные кадры и РАЗНОСИМ их по времени внутри клипа.

    Кадры идут подряд (frame_000204, 205, ...) и почти идентичны — брать первые
    N нельзя, иначе «тот же человек» = шум одного мгновения. Сортируем по
    frame_index и берём N равномерно распределённых кадров по всему клипу.
    """
    cand: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                yaw, pitch, roll = float(row["yaw"]), float(row["pitch"]), float(row["roll"])
                fidx = int(row["frame_index"])
            except (KeyError, ValueError):
                continue
            if abs(yaw) <= max_yaw and abs(pitch) <= max_pitch and abs(roll) <= max_roll:
                jpg = PHOTOS_DIR / row["dataset_id"] / row["source_filename"]
                if jpg.exists():
                    cand[row["dataset_id"]].append((fidx, jpg))
    by_person: dict[str, list[tuple[int, Path]]] = {}
    for person, items in cand.items():
        items.sort(key=lambda t: t[0])
        if per_person and len(items) > per_person:
            picks = np.linspace(0, len(items) - 1, per_person).round().astype(int)
            items = [items[p] for p in sorted(set(picks.tolist()))]
        by_person[person] = items
    return by_person


def mesh_for(photo: Path, cache_dir: Path) -> np.ndarray | None:
    cache = cache_dir / f"{photo.parent.name}__{photo.stem}.npy"
    if cache.exists():
        return np.load(cache)
    result = reconstruct_image(photo, device="cpu")
    if result is None:
        return None
    vertices, _ldm, _scale = align_identity_mesh(result)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, vertices.astype(np.float32))
    return vertices


def pair_stats(a: np.ndarray, b: np.ndarray) -> tuple[float, float, dict[str, float]]:
    dists = np.linalg.norm(a - b, axis=1).astype(np.float64)
    m = similarity_metrics(a, b)
    zones = {name: data["mean_delta"] for name, data in m["zones"].items()}
    return float(dists.mean()), float(np.percentile(dists, 99)), zones


def summarize(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return {}
    return {
        "n": int(arr.size),
        "mu": round(float(arr.mean()), 6),
        "sigma": round(float(arr.std(ddof=1)), 6) if arr.size > 1 else 0.0,
        "p05": round(float(np.percentile(arr, 5)), 6),
        "p50": round(float(np.percentile(arr, 50)), 6),
        "p95": round(float(np.percentile(arr, 95)), 6),
        "p99": round(float(np.percentile(arr, 99)), 6),
        "min": round(float(arr.min()), 6),
        "max": round(float(arr.max()), 6),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-yaw", type=float, default=20)
    ap.add_argument("--max-pitch", type=float, default=15)
    ap.add_argument("--max-roll", type=float, default=15)
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--min-frame-gap", type=int, default=60,
                    help="мин. зазор по frame_index для пары «тот же человек» (против дублей кадров)")
    # Отдельная папка: `.npy` старой (max-radius) нормировки не отличить от новых.
    ap.add_argument("--cache-dir", default=str(ROOT / ".runtime" / "disc_mesh_rms106"))
    ap.add_argument("--out", default=str(ROOT / ".runtime" / "calibration" / "discriminative_profile.json"))
    args = ap.parse_args()

    by_person = load_frontal_frames(CSV_PATH, args.max_yaw, args.max_pitch, args.max_roll, args.per_person)
    print("Фронтальных кадров по лицам:", {p: len(v) for p, v in sorted(by_person.items())})

    cache_dir = Path(args.cache_dir)
    meshes: dict[str, list[tuple[int, np.ndarray]]] = {}
    done = 0
    total = sum(len(v) for v in by_person.values())
    for person, items in sorted(by_person.items()):
        lst = []
        for fidx, ph in items:
            v = mesh_for(ph, cache_dir)
            done += 1
            if v is not None:
                lst.append((fidx, v))
            if done % 25 == 0 or done == total:
                print(f"  реконструировано {done}/{total}")
        if len(lst) >= 2:
            meshes[person] = lst
    persons = sorted(meshes)
    print(f"Лиц с >=2 мешами: {len(persons)} | всего мешей: {sum(len(m) for m in meshes.values())}")

    same_mean, same_p99 = [], []
    diff_mean, diff_p99 = [], []
    same_zone: dict[str, list[float]] = defaultdict(list)
    diff_zone: dict[str, list[float]] = defaultdict(list)
    same_thr: dict[float, list[float]] = {t: [] for t in CANDIDATE_THRESHOLDS}
    diff_thr: dict[float, list[float]] = {t: [] for t in CANDIDATE_THRESHOLDS}

    def record(a, b, bucket_mean, bucket_p99, zb, tb):
        m, p99, zones = pair_stats(a, b)
        bucket_mean.append(m)
        bucket_p99.append(p99)
        for z, val in zones.items():
            zb[z].append(val)
        dists = np.linalg.norm(a - b, axis=1)
        for t in CANDIDATE_THRESHOLDS:
            tb[t].append(float(np.mean(dists > t) * 100.0))

    # внутрилицевые пары (только с временным зазором — против соседних дублей кадров)
    for person in persons:
        for (i1, a), (i2, b) in itertools.combinations(meshes[person], 2):
            if abs(i1 - i2) < args.min_frame_gap:
                continue
            record(a, b, same_mean, same_p99, same_zone, same_thr)
    # межлицевые пары
    for p1, p2 in itertools.combinations(persons, 2):
        for _i1, a in meshes[p1]:
            for _i2, b in meshes[p2]:
                record(a, b, diff_mean, diff_p99, diff_zone, diff_thr)

    # --- идентификация по эталонам (честно, против дублей кадров) ---
    # Галерея = чётные кадры лица -> 7 «эталонов» (средний меш).
    # Проба = нечётные кадры; относим каждую к ближайшему эталону.
    # Дубликаты не помогают: проба отделена от галереи, а вопрос — не спутает ли с чужим.
    protos, proto_labels = {}, []
    probes = []
    for p in persons:
        vs = [v for _f, v in meshes[p]]
        gal = vs[0::2]
        pr = vs[1::2]
        if gal:
            protos[p] = np.mean(np.stack(gal), axis=0)
            proto_labels.append(p)
        for v in pr:
            probes.append((p, v))
    correct = 0
    margins = []
    confusion: dict[str, int] = {}
    for true_p, v in probes:
        ds = sorted((float(np.linalg.norm(v - protos[q], axis=1).mean()), q) for q in proto_labels)
        d_best, p_best = ds[0]
        d_second, p_second = ds[1] if len(ds) > 1 else (float("inf"), None)
        if p_best == true_p:
            correct += 1
            margins.append(d_second - d_best)  # запас до ближайшего чужого (больше = надёжнее)
        else:
            margins.append(-(d_best - d_second))  # ошибка: чужой ближе своего
            key = f"{true_p} -> {p_best}"
            confusion[key] = confusion.get(key, 0) + 1
    n_probe = len(probes)
    ident = {
        "n_probe_frames": n_probe,
        "n_identities": len(proto_labels),
        "accuracy_pct": round(100.0 * correct / n_probe, 2) if n_probe else None,
        "errors": n_probe - correct,
        "median_margin_correct": round(float(np.median([m for m in margins if m > 0])), 6) if any(m > 0 for m in margins) else None,
        "min_margin": round(float(np.min(margins)), 6) if margins else None,
        "confusion": dict(sorted(confusion.items(), key=lambda kv: -kv[1])),
    }

    def _mean_sig(vals):
        if len(vals) >= 2:
            return float(np.mean(vals)), float(np.std(vals, ddof=1))
        if len(vals) == 1:
            return float(vals[0]), 0.0
        return None, None

    s_mu, s_sig = _mean_sig(same_mean)
    d_mu, d_sig = _mean_sig(diff_mean)
    d_prime = (round((d_mu - s_mu) / np.sqrt((s_sig**2 + d_sig**2) / 2), 3)
               if (s_mu is not None and s_sig and d_mu is not None) else None)
    same_p99v = float(np.percentile(same_mean, 99)) if len(same_mean) >= 2 else None
    diff_p05v = float(np.percentile(diff_mean, 5)) if len(diff_mean) >= 2 else None
    diff_med = float(np.median(diff_mean)) if diff_mean else None
    # 0.15 — прежнее насыщение `analysis._score_from_distance` в старых единицах; боевое
    # значение теперь 0.15 * MAXR_TO_RMS106, оно же fallback при пустом прогоне.
    fallback_scale = round(0.15 * MAXR_TO_RMS106, 4)
    suggested_scale = round(diff_med / 0.92, 4) if diff_med else fallback_scale  # (1 - diff_med/scale)*100 ≈ 8
    same_thr_median = {t: (float(np.median(v)) if v else None) for t, v in same_thr.items()}
    _cand = [t for t in CANDIDATE_THRESHOLDS if same_thr_median.get(t) is not None and same_thr_median[t] < 1.0]
    suggested_vertex_thr = _cand[0] if _cand else None

    zones_out = {}
    for z in sorted(set(same_zone) | set(diff_zone)):
        s_mu_z, s_sig_z = _mean_sig(same_zone.get(z) or [])
        d_vals = diff_zone.get(z)
        d_mu_z = float(np.mean(d_vals)) if d_vals else None
        entry = {"diff_mu": round(d_mu_z, 6) if d_mu_z is not None else None}
        if s_mu_z is not None:
            entry["same_mu"] = round(s_mu_z, 6)
            entry["same_sigma"] = round(s_sig_z, 6)
            entry["same_mu3sigma"] = round(s_mu_z + 3 * s_sig_z, 6)
            entry["separation"] = (round((d_mu_z - s_mu_z) / s_sig_z, 2)
                                   if (d_mu_z is not None and s_sig_z) else None)
        zones_out[z] = entry

    profile = {
        "meta": {
            "persons": persons, "meshes_per_person": {p: len(meshes[p]) for p in persons},
            "min_frame_gap": args.min_frame_gap,
            "n_same_pairs": len(same_mean), "n_diff_pairs": len(diff_mean),
            "pose_filter": {"max_yaw": args.max_yaw, "max_pitch": args.max_pitch, "max_roll": args.max_roll},
            "note": "шкала шума/разделения; НЕ вероятность личности",
        },
        "same_person_mean_dist": summarize(same_mean),
        "diff_person_mean_dist": summarize(diff_mean),
        "same_person_p99_dist": summarize(same_p99),
        "diff_person_p99_dist": summarize(diff_p99),
        "cohen_d_mean_dist": d_prime,
        "overlap_band": {"same_p99": round(same_p99v, 6) if same_p99v is not None else None,
                          "diff_p05": round(diff_p05v, 6) if diff_p05v is not None else None,
                          "separated": bool(same_p99v is not None and diff_p05v is not None and same_p99v < diff_p05v)},
        "pct_above_threshold_median": {
            "same_person": {str(t): (round(same_thr_median[t], 3) if same_thr_median[t] is not None else None) for t in CANDIDATE_THRESHOLDS},
            "diff_person": {str(t): (round(float(np.median(diff_thr[t])), 3) if diff_thr[t] else None) for t in CANDIDATE_THRESHOLDS},
        },
        "zones": zones_out,
        "identification": ident,
        "suggested": {
            "score_scale": suggested_scale,
            "vertex_threshold": suggested_vertex_thr,
            "same_person_median_mean_dist": round(float(np.median(same_mean)), 6),
            "diff_person_median_mean_dist": round(diff_med, 6),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    print("\nJSON:", out)

    print("\n=== РАЗДЕЛИТЕЛЬНЫЙ ПРОФИЛЬ ===")
    sm = profile['same_person_mean_dist']; df = profile['diff_person_mean_dist']
    print(f"ТОТ ЖЕ (внутри клипа, оптимистично): mean-dist μ={sm.get('mu')} p99={sm.get('p99')} n={sm.get('n')}")
    print(f"ДРУГОЙ: mean-dist μ={df.get('mu')} p05={df.get('p05')} p50={df.get('p50')} n={df.get('n')}")
    print(f"Cohen's d = {profile['cohen_d_mean_dist']} | overlap_band: {profile['overlap_band']}")
    print("same %выше порога:", profile["pct_above_threshold_median"]["same_person"])
    print("diff %выше порога:", profile["pct_above_threshold_median"]["diff_person"])
    print("ПРЕДЛАГАЕТСЯ:", profile["suggested"])
    print("\n=== ИДЕНТИФИКАЦИЯ ПО ЭТАЛОНАМ (7 лиц, пробы отделены от галереи) ===")
    print(f"пробных кадров: {ident['n_probe_frames']} | верно к своему эталону: {ident['accuracy_pct']}% (ошибок {ident['errors']})")
    print(f"медиана запаса до ближайшего чужого = {ident['median_margin_correct']} | min margin = {ident['min_margin']}")
    if ident.get("confusion"):
        print("ошибочные пары (истинное -> приписанное: count):", ident["confusion"])


if __name__ == "__main__":
    main()
