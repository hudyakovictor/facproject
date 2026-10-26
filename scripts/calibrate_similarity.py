"""Калибровка геометрических метрик сходства по «одной личности».

Идея: на калибровочных фото (все — один и тот же человек, углы позы в имени
файла) измерить шум реконструкции: насколько расходятся выровненные dense-меши
между парами одного человека. Это даёт обоснованные пороги вместо хардкода
(scale=0.15, vertex threshold=0.025 — прежние значения analysis.py в старых единицах).

Путь идентичен UI: reconstruct_image → align_identity_mesh →
similarity_metrics (morphing/backend/analysis.py). Никакой новой математики.

Единицы — доли RMS-масштаба по 106 ландмаркам (патч 04). Исторические сетки порогов
заданы в прежних единицах (доля max-радиуса сетки) и перемножены на
`aligner.MAXR_TO_RMS106`; кэш мешей лежит в отдельной папке, потому что `.npy`-файлы
старой нормировки не отличимы от новых по имени.

Примеры:
    # пилот: 16 ближайших к фронту фото
    python scripts/calibrate_similarity.py --limit 16

    # полный фронтальный прогон, JSON-профиль шума
    python scripts/calibrate_similarity.py --max-yaw 15 --max-pitch 15 \
        --out .runtime/calibration/noise_profile.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app8.reconstruction import reconstruct_image  # noqa: E402
from morphing.backend.aligner import MAXR_TO_RMS106, align_identity_mesh  # noqa: E402
from morphing.backend.analysis import similarity_metrics  # noqa: E402

CALIB_DIR = Path("/Volumes/SDCARD/photo/calibration")
POSE_RE = re.compile(r"y(-?\d+)p(-?\d+)r(-?\d+)")
# Кандидаты порога средней девиации вершины. Прежняя сетка 0.02–0.05 накручена на доли
# max-радиуса сетки; в боевых единицах (RMS по 106 ландмаркам) те же расстояния больше
# в MAXR_TO_RMS106 раз, поэтому сетка пересчитана, а не скопирована.
OLD_UNIT_THRESHOLDS = (0.02, 0.025, 0.03, 0.035, 0.04, 0.05)
CANDIDATE_THRESHOLDS = [round(t * MAXR_TO_RMS106, 5) for t in OLD_UNIT_THRESHOLDS]


def parse_pose(name: str) -> tuple[int, int, int] | None:
    m = POSE_RE.search(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def select_photos(calib_dir: Path, max_yaw: int, max_pitch: int, limit: int) -> list[Path]:
    photos = []
    for p in sorted(calib_dir.glob("*.jpg")) + sorted(calib_dir.glob("*.png")):
        if p.name.startswith("._") or p.name.startswith("."):
            continue  # служебные AppleDouble-файлы macOS
        pose = parse_pose(p.name)
        if pose is None:
            continue
        yaw, pitch, roll = pose
        if abs(yaw) <= max_yaw and abs(pitch) <= max_pitch and abs(roll) <= 15:
            photos.append(p)
    if limit and limit > 0:
        photos = photos[:limit]
    return photos


def load_or_reconstruct(photo: Path, cache_dir: Path) -> np.ndarray | None:
    """Выровненные dense-вершины (N,3); кэш в .npy чтобы не гонять 3DDFA повторно."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / (photo.stem + ".npy")
    if cache.exists():
        return np.load(cache)
    result = reconstruct_image(photo, device="cpu")
    if result is None:
        return None
    vertices, _ldm, _scale = align_identity_mesh(result)
    np.save(cache, vertices.astype(np.float32))
    return vertices


def summarize(values: list[float]) -> dict[str, float]:
    a = np.asarray(values, dtype=np.float64)
    if a.size == 0:
        return {}
    return {
        "n": int(a.size),
        "mu": round(float(a.mean()), 6),
        "sigma": round(float(a.std(ddof=1)), 6) if a.size > 1 else 0.0,
        "p50": round(float(np.percentile(a, 50)), 6),
        "p90": round(float(np.percentile(a, 90)), 6),
        "p95": round(float(np.percentile(a, 95)), 6),
        "max": round(float(a.max()), 6),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calib-dir", default=str(CALIB_DIR))
    ap.add_argument("--max-yaw", type=int, default=15)
    ap.add_argument("--max-pitch", type=int, default=15)
    ap.add_argument("--limit", type=int, default=0, help="ограничить число фото (0 = все)")
    # Отдельная папка: `.npy`-мешей старой (max-radius) нормировки не отличить от новых,
    # а смешать их — значит калибровать пороги по расстояниям в двух единицах сразу.
    ap.add_argument("--cache-dir", default=str(ROOT / ".runtime" / "calib_mesh_rms106"))
    ap.add_argument("--out", default=str(ROOT / ".runtime" / "calibration" / "noise_profile.json"))
    args = ap.parse_args()

    photos = select_photos(Path(args.calib_dir), args.max_yaw, args.max_pitch, args.limit)
    print(f"Отобрано фото (|yaw|<={args.max_yaw}, |pitch|<={args.max_pitch}): {len(photos)}")

    cache_dir = Path(args.cache_dir)
    verts: list[np.ndarray] = []
    used: list[str] = []
    for i, ph in enumerate(photos, 1):
        v = load_or_reconstruct(ph, cache_dir)
        if v is None:
            print(f"  [{i}/{len(photos)}] {ph.name}: лицо не обнаружено — пропуск")
            continue
        verts.append(v)
        used.append(ph.name)
        if i % 10 == 0 or i == len(photos):
            print(f"  реконструировано {len(verts)}/{len(photos)}")
    if len(verts) < 2:
        print("Недостаточно фото для пар — расширь выбор или примонтируй калибровку.")
        return

    # попарные метрики одного человека
    pair_mean, pair_p95, pair_p99, pair_max = [], [], [], []
    pct_by_thr: dict[float, list[float]] = {t: [] for t in CANDIDATE_THRESHOLDS}
    zone_deltas: dict[str, list[float]] = defaultdict(list)
    n_pairs = 0
    for a, b in itertools.combinations(range(len(verts)), 2):
        dists = np.linalg.norm(verts[a] - verts[b], axis=1).astype(np.float64)
        pair_mean.append(float(dists.mean()))
        pair_p95.append(float(np.percentile(dists, 95)))
        pair_p99.append(float(np.percentile(dists, 99)))
        pair_max.append(float(dists.max()))
        for t in CANDIDATE_THRESHOLDS:
            pct_by_thr[t].append(float(np.mean(dists > t) * 100.0))
        m = similarity_metrics(verts[a], verts[b])
        for name, data in m["zones"].items():
            zone_deltas[name].append(data["mean_delta"])
        n_pairs += 1
    print(f"Пар одного человека: {n_pairs}")

    zones = {name: summarize(vals) for name, vals in zone_deltas.items()}
    # порог по вершинам: такое t, где шум одного человека даёт <1% «выбросов» в медиане пар
    thr_median_pct = {t: float(np.median(vals)) for t, vals in pct_by_thr.items()}
    suggested_vertex_thr = next((t for t in CANDIDATE_THRESHOLDS if thr_median_pct[t] < 1.0), CANDIDATE_THRESHOLDS[-1])
    # scale для _score_from_distance: типичная дистанция одного человека -> скор ~90
    d_typ = float(np.median(pair_mean))
    # 0.15 — прежнее насыщение `analysis._score_from_distance` в старых единицах;
    # боевое значение теперь 0.15 * MAXR_TO_RMS106, оно же fallback при пустом прогоне.
    fallback_scale = round(0.15 * MAXR_TO_RMS106, 4)
    suggested_scale = round(d_typ / 0.10, 4) if d_typ > 0 else fallback_scale  # (1 - d/scale)=0.90

    profile = {
        "meta": {
            "n_photos": len(verts),
            "n_pairs": n_pairs,
            "pose_filter": {"max_yaw": args.max_yaw, "max_pitch": args.max_pitch},
            "photos": used,
            "note": "шум одного человека/одного ракурса; НЕ вероятность личности",
        },
        "pairwise_vertex_distance": {
            "mean": summarize(pair_mean),
            "p95": summarize(pair_p95),
            "p99": summarize(pair_p99),
            "max": summarize(pair_max),
        },
        "pct_above_threshold_median": {str(t): round(pct_median, 3) for t, pct_median in thr_median_pct.items()},
        "zones_mean_delta": zones,
        "suggested": {
            "vertex_threshold": suggested_vertex_thr,
            "score_scale": suggested_scale,
            "typical_same_person_mean_dist": round(d_typ, 6),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    print("JSON:", out)

    print("\n=== ПРОФИЛЬ ШУМА (один человек) ===")
    print(f"mean-dist по парам: μ={profile['pairwise_vertex_distance']['mean']['mu']} "
          f"p95={profile['pairwise_vertex_distance']['mean']['p95']} max={profile['pairwise_vertex_distance']['mean']['max']}")
    print(f"верш. dist p99 по парам: μ={profile['pairwise_vertex_distance']['p99']['mu']} max={profile['pairwise_vertex_distance']['p99']['max']}")
    print("% вершин выше порога (медиана по парам):", profile["pct_above_threshold_median"])
    print("Зоны (mean_delta): ", {k: v["mu"] for k, v in zones.items()})
    print("ПРЕДЛАГАЕТСЯ:", profile["suggested"])


if __name__ == "__main__":
    main()
