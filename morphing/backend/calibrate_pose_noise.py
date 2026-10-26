"""📏 Калибровка шума реконструкции по ракурсам (morphing).

Источник: /Volumes/SDCARD/calibration_rakurs/{person}/{pose_bin}/frame_*.jpg —
6 человек, разложенные по 9 бинам POSE_BINS, несколько кадров в каждом бине.

Идея: сравнение двух кадров одного ракурса одного человека показывает, насколько
устойчива реконструкция конвейера (детектор → 3DDFA → нормировка) к перестановке
входной картинки. Сравнение центроидов разных людей в том же бине даёт сигнал.
По этим двум распределениям на бин хранится полоса (p50/p95) и разделимость (AUC),
которые использует `pose_noise_model.py`.

СТАТУС ПОЛУЧЕННЫХ ПОЛОС (важно не терять): источник — кадры одной видеосерии на
бин, отобранные `linspace` по всем кадрам папки. В примерах это 10 кадров из окна
в 24–50 кадров, где голова плавно проходит весь бин (yaw от +9.9° до −9.9°), т.е.
это не независимые пересъёмки. Поэтому:
— общее смещение сессии (камера, свет, обработка) сокращается в парной разности;
— ошибки соседних по времени кадров коррелированы, Var(e_t − e_{t+h}) = 2σ²(1−ρ(h));
— полосы описывают внутри-сессионную повторяемость, условную по |Δyaw|, и не
  являются оценкой шума независимой пересъёмки (для неё нужен отдельный прогон
  на разных сессиях с замороженными порогами).
Пары внутри группы не независимы (один кадр участвует в 9 расстояниях), так что
`auc` — описательная разделимость этих видеогрупп, а не вероятность «разные люди».

Сетки берутся как есть (`aligner.align_identity_mesh`): `vertices_identity_only` —
форма в объектном пространстве 3DMM, поза в неё не входит. Показатель |Δyaw| у пары
сохраняется в кэше и сводится в `drift`, чтобы видеть, насколько «шум» бина на самом
деле остаётся разницей ракурсов внутри папки.

Единицы — доли краниометрического радиуса (после нормировки max |v - center| = 1).

Запуск (офлайн, по 2 потока на воркер):
    cd /Users/victorkhudyakov/work
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m morphing.backend.calibrate_pose_noise \
        --max-per-group 10 --workers 4
Прерванный прогон продолжается с кэша .runtime/pose_noise_cache/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from itertools import combinations
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app8.config import POSE_BINS  # единый источник бинов и канонических yaw

DEFAULT_INPUT = Path("/Volumes/SDCARD/calibration_rakurs")
CACHE_DIR = ROOT / ".runtime" / "pose_noise_cache"
OUTPUT_PATH = Path(__file__).resolve().parent / "pose_noise_calibration.json"
BINS = tuple(name for name, _lo, _hi, _canonical in POSE_BINS)
SCHEMA_VERSION = "morphing-pose-noise-v2"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
# Пара с |Δyaw| меньше этого порога считается «тот же ракурс»: её разница — почти чистый
# шум конвейера, без вклада дрейфа головы внутри папки.
CLOSE_POSE_DEG = 2.0
# Границы карманов по |Δyaw| (°): шум внутри бина сильно зависит от того, насколько
# разные позы у пары, поэтому полоса шума задаётся условно по этому разбросу.
DRIFT_BUCKETS = (0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 100.0)
# Шаг между кадрами пары (в кадрах серии), с которого пару считаем «разнесённой по
# времени»: нужно для `_lag_audit`, чтобы проверить, не соседство ли кадров задаёт
# ширину полосы.
FAR_LAG_FRAMES = 5
# Меньше этого числа наблюдений хвост (p95) не сравниваем: он держится 1–2 точек.
MIN_TAIL_PAIRS = 12
# Статус полос едет в самом JSON: читатель метрик (и UI) должен видеть, каким
# именно материалом они измерены, а не принимать их за универсальный шум.
BAND_STATUS = (
    "внутри-сессионная повторяемость реконструкции на видеокадрах одной серии "
    "(6 человек × 9 бинов, по 10 кадров на бин), условная по |Δyaw|; "
    "на независимых пересъёмках проверена и занижена — см. assess_band_transfer.py "
    "и reshoot_bands.json (78% пар одного человека легли выше этого p95)"
)


def _files_digest(input_dir: Path, files: list[Path]) -> str:
    """Короткий отпечаток набора кадров: без него `--input` с теми же именами
    групп (person/bin) молча переиспользует кэш предыдущего источника."""
    try:
        root = str(input_dir.resolve())
    except OSError:
        root = str(input_dir)
    rel = [str(Path(f).resolve()).removeprefix(root + "/") for f in files]
    return hashlib.sha1("\n".join(sorted(rel)).encode(), usedforsecurity=False).hexdigest()[:10]


def _frame_id(name: str) -> int | None:
    match = re.search(r"frame_(\d+)", name)
    return int(match.group(1)) if match else None


def _pair_lag(name_a: str, name_b: str) -> int | None:
    """Шаг в кадрах между двумя кадрами пары; None, если имена не нумерованы по кадрам."""
    first, second = _frame_id(name_a), _frame_id(name_b)
    return abs(second - first) if first is not None and second is not None else None


def _sampling_footprint(names: list[str]) -> dict[str, Any]:
    """Насколько во времени разнесены реально посчитанные кадры группы.

    Это не метрика качества реконструкции, а evidence для интерпретации полос: если
    весь бин — окно в десятки смежных кадров, полосы измеряют короткоинтервальную
    повторяемость, и в JSON это должно быть видно.
    """
    ids = sorted(i for i in (_frame_id(n) for n in names) if i is not None)
    if len(ids) < 2:
        return {"frame_ids": False}
    gaps = [b - a for a, b in zip(ids[:-1], ids[1:], strict=True)]
    return {
        "frame_ids": True,
        "frame_first": ids[0],
        "frame_last": ids[-1],
        "frame_span": ids[-1] - ids[0],
        "median_frame_gap": round(float(np.median(gaps)), 2),
        "min_frame_gap": int(min(gaps)),
    }


def _percentiles(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return {}
    return {
        "n": int(arr.size),
        "p10": round(float(np.percentile(arr, 10)), 8),
        "p50": round(float(np.percentile(arr, 50)), 8),
        "p90": round(float(np.percentile(arr, 90)), 8),
        "p95": round(float(np.percentile(arr, 95)), 8),
        "max": round(float(arr.max()), 8),
    }


def _corr(x: list[float], y: list[float]) -> float | None:
    """Корреляция Пирсона; None на вырожденной выборке (мало точек или нулевой разброс)."""
    ax = np.asarray(x, dtype=np.float64)
    ay = np.asarray(y, dtype=np.float64)
    if ax.size < 3 or float(ax.std()) < 1e-9 or float(ay.std()) < 1e-9:
        return None
    return round(float(np.corrcoef(ax, ay)[0, 1]), 4)


def _drift_buckets(drift: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Полоса шума внутри бина по карманам |Δyaw| (°, доля радиуса на пару)."""
    buckets: list[dict[str, Any]] = []
    for lo, hi in zip(DRIFT_BUCKETS[:-1], DRIFT_BUCKETS[1:], strict=True):
        values = [delta for dyaw, delta in drift if lo <= dyaw < hi]
        buckets.append({"lo_deg": lo, "hi_deg": hi, "pairs": len(values), **_percentiles(values)})
    return buckets


def _auc(within: list[float], between: list[float]) -> float | None:
    """Mann-Whitney: вероятность, что центроид другого человека дальше, чем пара одного."""
    if not within or not between:
        return None
    wins = sum(1 for a in within for b in between if b > a) + 0.5 * sum(
        1 for a in within for b in between if b == a
    )
    return round(wins / (len(within) * len(between)), 4)


def discover_groups(input_dir: Path, max_per_group: int) -> list[tuple[str, str, list[Path]]]:
    groups: list[tuple[str, str, list[Path]]] = []
    for person in sorted(p for p in input_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for pose_bin in BINS:
            folder = person / pose_bin
            if not folder.is_dir():
                continue
            files = sorted(
                p for p in folder.glob("*")
                if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in IMAGE_SUFFIXES
            )
            if len(files) < 2:
                continue
            if len(files) > max_per_group:
                # Кадров в бине до 52 — берём равномерно по всей серии.
                picks = np.linspace(0, len(files) - 1, max_per_group).round().astype(int)
                files = [files[i] for i in dict.fromkeys(picks.tolist())]
            groups.append((person.name, pose_bin, files))
    return groups


def _group_paths(
    person: str,
    pose_bin: str,
    max_per_group: int,
    digest: str | None = None,
) -> tuple[Path, Path]:
    """Кэш ключуется версией модели, размером выборки и отпечатком списка кадров.

    Прогон k=3 не подменяет k=10, данные старой схемы (с доворотом позы) не
    смешиваются с новой, а другой `--input` с теми же именами папок не переиспользует
    чужие результаты. Без `digest` возвращается прежнее имя — так старый кэш,
    собранный до появления отпечатка, остаётся читаемым.
    """
    stem = str(CACHE_DIR / f"{person}__{pose_bin}__{SCHEMA_VERSION}__k{max_per_group}")
    if digest:
        stem = f"{stem}__h{digest}"
    return Path(f"{stem}.json"), Path(f"{stem}__centroid.npy")


def _process_group(job: tuple[str, str, list[str], int, str]) -> dict[str, Any]:
    """Реконструирует группу (человек, бин), пишет попарные статистики и центроид."""
    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh
    from morphing.backend.analysis import similarity_metrics

    person, pose_bin, paths, max_per_group, input_dir = job
    digest = _files_digest(Path(input_dir), [Path(p) for p in paths])
    meshes: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    for path in paths:
        try:
            recon = reconstruct_image(Path(path), device="cpu")
        except Exception as exc:  # noqa: BLE001 — офлайн-обход: сбойный кадр не роняет прогон
            print(f"  ! {path}: {exc}", flush=True)
            recon = None
        if not recon:
            continue
        vertices, _, _ = align_identity_mesh(recon)
        meshes.append(vertices)
        yaw = float(np.asarray(recon["angles_deg"], np.float32)[1])
        records.append({
            "file": Path(path).name,
            "yaw": round(yaw, 3),
            "detected_bin": recon["pose_bin"],
        })
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "person": person,
        "pose_bin": pose_bin,
        "requested_per_group": int(max_per_group),
        "input_dir": str(input_dir),
        "digest": digest,
        "sampling": _sampling_footprint([rec["file"] for rec in records]),
        "n_photos": len(meshes),
        "records": records,
        "within_pairs": [],
    }
    if len(meshes) < 2:
        return payload
    for (index_a, mesh_a), (index_b, mesh_b) in combinations(list(enumerate(meshes)), 2):
        metrics = similarity_metrics(mesh_a, mesh_b)
        payload["within_pairs"].append({
            "pair": f"{records[index_a]['file']}|{records[index_b]['file']}",
            "lag": _pair_lag(records[index_a]["file"], records[index_b]["file"]),
            "dyaw": round(abs(records[index_a]["yaw"] - records[index_b]["yaw"]), 3),
            "mean_delta": metrics["euclidean_mean"],
            "p95_delta": metrics["p95_delta"],
            "max_delta": metrics["euclidean_max"],
            **{f"zone_{name}": data["mean_delta"] for name, data in metrics["zones"].items()},
        })
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    centroid = _group_paths(person, pose_bin, max_per_group, digest)[1]
    np.save(centroid, np.mean(np.stack(meshes), axis=0).astype(np.float32))
    return payload


def load_or_compute(
    groups: list[tuple[str, str, list[Path]]],
    workers: int,
    force: bool,
    max_per_group: int,
    input_dir: Path,
) -> list[dict[str, Any]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    pending: list[tuple[str, str, list[str], int, str]] = []
    for person, pose_bin, files in groups:
        digest = _files_digest(input_dir, files)
        cache, _ = _group_paths(person, pose_bin, max_per_group, digest)
        if cache.exists() and not force:
            payload = json.loads(cache.read_text())
            if payload.get("schema_version") == SCHEMA_VERSION:
                results.append(payload)
                continue
        pending.append((person, pose_bin, [str(f) for f in files], max_per_group, str(input_dir)))
    print(f"групп: {len(groups)}, из кэша: {len(results)}, к считаем: {len(pending)}", flush=True)
    if not pending:
        return results
    with Pool(processes=workers, maxtasksperchild=1) as pool:
        for index, payload in enumerate(pool.imap_unordered(_process_group, pending), start=1):
            cache, _ = _group_paths(
                payload["person"], payload["pose_bin"],
                payload["requested_per_group"], payload.get("digest"),
            )
            cache.write_text(json.dumps(payload, ensure_ascii=False))
            results.append(payload)
            span = payload.get("sampling", {}).get("frame_span", "?")
            print(f"  [{index}/{len(pending)}] {payload['person']}/{payload['pose_bin']}: "
                  f"n={payload['n_photos']} pairs={len(payload['within_pairs'])} span={span} кадров",
                  flush=True)
    return results


def _sampling_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Насколько во времени разнесены кадры, на которых измерена полоса.

    Нужен в самом отчёте: он отличает «шум конвейера» от «шума между соседними
    кадрами одной серии». Если медианный span — десятки смежных кадров, полосы
    переносятся на независимые пересъёмки только после отдельной проверки.
    """
    spans, gaps = [], []
    for row in rows:
        # Старые кэши (до появления ключа) восстанавливают footprint по именам кадров.
        sampling = row.get("sampling") or _sampling_footprint([rec["file"] for rec in row.get("records", [])])
        if sampling.get("frame_ids"):
            spans.append(float(sampling["frame_span"]))
            gaps.append(float(sampling["median_frame_gap"]))
    if not spans:
        return {"frame_ids": False}
    return {
        "frame_ids": True,
        "groups": len(spans),
        "median_frame_span": round(float(np.median(spans)), 2),
        "max_frame_span": int(max(spans)),
        "median_of_median_frame_gap": round(float(np.median(gaps)), 2),
        "min_of_median_frame_gap": round(float(min(gaps)), 2),
    }


def _residual(values: list[float], along: list[float]) -> np.ndarray:
    """Остатки линейной регрессии values на along — для частных корреляций."""
    ax = np.asarray(along, dtype=np.float64)
    ay = np.asarray(values, dtype=np.float64)
    design = np.vstack([np.ones_like(ax), ax]).T
    return ay - design @ np.linalg.lstsq(design, ay, rcond=None)[0]


def _partial_corr(first: list[float], second: list[float], given: list[float]) -> float | None:
    """Корреляция Пирсона остатков first|given и second|given; None на малой выборке."""
    if len(first) < 8 or len(second) < 8:
        return None
    return _corr(list(_residual(first, given)), list(_residual(second, given)))


def _pair_lags(rows: list[dict[str, Any]]) -> list[tuple[int, float, float]]:
    """(шаг в кадрах, |Δyaw|, mean_delta) для пар, где шаг восстанавливается из имён."""
    out: list[tuple[int, float, float]] = []
    for row in rows:
        for pair in row.get("within_pairs", []):
            name_a, name_b = pair["pair"].split("|")
            lag = pair.get("lag")
            if lag is None:
                lag = _pair_lag(name_a, name_b)
            if lag is not None:
                out.append((int(lag), float(pair["dyaw"]), float(pair["mean_delta"])))
    return out


def _lag_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Насколько полосам можно доверять за пределами этого материала.

    Главный риск калибровки по видеосерии — не «соседние кадры похожи», а то, что
    общая ошибка сессии (камера, свет, обработка) сокращается в парной разности.
    Первое здесь измеримо: сравнивается хвост пар с |Δyaw| < порога при малом и
    большом шаге между кадрами. Второе этим материалом не измеримо в принципе —
    для него нужны независимые съёмки, поэтому полосы и помечены как
    внутри-сессионные.
    """
    data = _pair_lags(rows)
    if len(data) < 8:
        return {"pairs_with_lag": len(data)}
    lags = [float(lag) for lag, _, _ in data]
    dyaw = [value for _, value, _ in data]
    delta = [value for _, _, value in data]
    near = [d for lag, yaw, d in data if yaw < CLOSE_POSE_DEG and lag < FAR_LAG_FRAMES]
    far = [d for lag, yaw, d in data if yaw < CLOSE_POSE_DEG and lag >= FAR_LAG_FRAMES]
    tails = _percentiles(near), _percentiles(far)
    ratio = (
        round(float(tails[1]["p95"] / tails[0]["p95"]), 3)
        if len(near) >= MIN_TAIL_PAIRS and len(far) >= MIN_TAIL_PAIRS
        and tails[0]["p95"] > 0
        else None
    )
    return {
        "pairs_with_lag": len(data),
        "median_lag": round(float(np.median(lags)), 2),
        "max_lag": int(max(lags)),
        "close_pose_near_lag": tails[0],
        "close_pose_far_lag": tails[1],
        "close_pose_p95_far_over_near": ratio,
        # Что остаётся после учёта второго признака: если вклад шага мал, полосы
        # широки не из-за соседства кадров, а из-за разброса ракурса внутри папки.
        "partial_corr_log_delta_vs_lag_given_dyaw": _partial_corr(
            [float(np.log(max(d, 1e-9))) for d in delta], [max(lag, 1.0) for lag in lags], dyaw
        ),
        "partial_corr_log_delta_vs_dyaw_given_lag": _partial_corr(
            [float(np.log(max(d, 1e-9))) for d in delta], dyaw, [max(lag, 1.0) for lag in lags]
        ),
    }


def _lag_verdict(bins: dict[str, Any]) -> dict[str, Any]:
    """Сводка по бинам: расширяется ли хвост полосы, если кадры разнесены по времени.

    По бинам, не в объединённой выборке: в общей выборке широкий хвост одного бина
    выглядел бы как эффект шага, хотя он принадлежит другому ракурсу.
    """
    ratios = [
        data["lag"]["close_pose_p95_far_over_near"]
        for data in bins.values()
        if (data.get("lag") or {}).get("close_pose_p95_far_over_near") is not None
    ]
    return {
        "bins_compared": len(ratios),
        "median_p95_far_over_near": round(float(np.median(ratios)), 3) if ratios else None,
        "note": (
            "При том же |Δyaw| хвост полосы почти не зависит от шага между кадрами в "
            f"наблюдённом диапазоне ({FAR_LAG_FRAMES}+ кадров). Это снимает только риск "
            "«соседние кадры похожи»: сокращение общей ошибки съёмочной сессии в парной "
            "разности этим материалом не измеряется, переносимость полос на независимые "
            "пересъёмки требует отдельного прогона."
        ),
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Полосы по бинам: внутри-сессионная повторяемость, межличностный сигнал, AUC."""
    zone_names = sorted({
        key[len("zone_"):]
        for row in results
        for pair in row.get("within_pairs", [])
        for key in pair
        if key.startswith("zone_")
    })
    bins: dict[str, Any] = {}
    for pose_bin in BINS:
        rows = [r for r in results if r.get("pose_bin") == pose_bin and r.get("within_pairs")]
        if not rows:
            continue
        within = [pair["mean_delta"] for row in rows for pair in row["within_pairs"]]
        drift = [(pair["dyaw"], pair["mean_delta"]) for row in rows for pair in row["within_pairs"]]
        between = _between_person_deltas(rows)
        between_mean = [item["mean_delta"] for item in between]
        close = [delta for dyaw, delta in drift if dyaw < CLOSE_POSE_DEG]
        bins[pose_bin] = {
            "people": len(rows),
            "photos": int(sum(r["n_photos"] for r in rows)),
            "sampling": _sampling_summary(rows),
            "lag": _lag_audit(rows),
            "within": _percentiles(within),
            "within_close_pose": {
                "pairs": len(close),
                "dyaw_lt_deg": CLOSE_POSE_DEG,
                **_percentiles(close),
            },
            "between": _percentiles(between_mean),
            "auc": _auc(within, between_mean),
            # Распределение пер-вершинных статистик по тем же парам: `within` — средняя
            # девиация пары, а для шкалы heatmap нужна девиация отдельной вершины.
            "within_vertex_p95": _percentiles(
                [pair["p95_delta"] for row in rows for pair in row["within_pairs"]]
            ),
            "within_vertex_max": _percentiles(
                [pair["max_delta"] for row in rows for pair in row["within_pairs"]]
            ),
            "between_vertex_p95": _percentiles([item["p95_delta"] for item in between]),
            "drift": {
                "corr_abs_dyaw_mean_delta": _corr([d for d, _ in drift], [m for _, m in drift]),
                "median_abs_dyaw_deg": round(float(np.median([d for d, _ in drift])), 3),
                "buckets": _drift_buckets(drift),
            },
            "zones": {
                zone: _percentiles([pair[f"zone_{zone}"] for row in rows for pair in row["within_pairs"]])
                for zone in zone_names
            },
        }
    mismatches = [
        {"person": row["person"], "folder_bin": row["pose_bin"], "file": rec["file"],
         "yaw": rec["yaw"], "detected_bin": rec["detected_bin"],
         "edge_margin_deg": _edge_margin(rec["yaw"], row["pose_bin"])}
        for row in results for rec in row.get("records", []) if rec["detected_bin"] != row["pose_bin"]
    ]
    total = int(sum(row["n_photos"] for row in results))
    sources = {row.get("input_dir") for row in results if row.get("input_dir")}
    return {
        "schema_version": SCHEMA_VERSION,
        "units": "доли краниометрического радиуса (после нормировки max |v - center| = 1)",
        "space": "identity-only mesh in 3DMM object space (pose-free), unit craniometric radius",
        "source": sources.pop() if len(sources) == 1 else str(DEFAULT_INPUT),
        "band_status": BAND_STATUS,
        "sampling": _sampling_summary(results),
        "lag": _lag_verdict(bins),
        "bins": bins,
        "auc_definition": (
            "Mann-Whitney для P(центроид A далёк от центроида B > средняя девиация двух "
            "кадров одного человека в том же бине). Это разделимость данных видеогрупп, "
            "а не вероятность того, что два независимых фото сняты разными людьми."
        ),
        "bin_agreement": {
            "total": total,
            "mismatched": len(mismatches),
            "note": (
                "Кадры с |yaw| у самой границы бина дают расхождение с ярлыком папки при "
                "малом edge_margin_deg — это неопределённость классификации ракурса, а не "
                "признак плохой реконструкции; систематически выбрасывать такие кадры нельзя."
            ),
            "examples": mismatches[:40],
        },
    }


_BIN_BOUNDS = {name: (lo, hi) for name, lo, hi, _canonical in POSE_BINS}


def _edge_margin(yaw: float, folder_bin: str) -> float | None:
    """Расстояние измеренного yaw до ближайшей границы бина папки (°)."""
    bounds = _BIN_BOUNDS.get(folder_bin)
    if not bounds:
        return None
    return round(min(abs(yaw - bounds[0]), abs(yaw - bounds[1])), 3)


def _between_person_deltas(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    """Расстояния между центроидами личностей внутри одного бина (mean и per-vertex p95)."""
    centroids = {}
    for row in rows:
        path = _group_paths(
            row["person"], row["pose_bin"],
            int(row.get("requested_per_group", 0)), row.get("digest"),
        )[1]
        if path.exists():
            centroids[row["person"]] = np.load(path)
    deltas: list[dict[str, float]] = []
    for mesh_a, mesh_b in combinations(centroids.values(), 2):
        dist = np.linalg.norm(mesh_a - mesh_b, axis=1)
        deltas.append({
            "mean_delta": float(dist.mean()),
            "p95_delta": float(np.percentile(dist, 95)),
        })
    return deltas


def main() -> int:
    parser = argparse.ArgumentParser(description="Калибровка шума реконструкции по ракурсам")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), type=Path)
    parser.add_argument("--out", default=str(OUTPUT_PATH), type=Path)
    parser.add_argument("--max-per-group", default=10, type=int)
    parser.add_argument("--limit-groups", default=0, type=int, help="дымовой прогон: только первые N групп")
    parser.add_argument("--workers", default=4, type=int)
    parser.add_argument("--force", action="store_true", help="игнорировать кэш групп")
    parser.add_argument("--aggregate-only", action="store_true", help="только свести имеющийся кэш")
    args = parser.parse_args()

    if args.aggregate_only:
        cached: dict[tuple[str, str], dict[str, Any]] = {}
        for cache in sorted(CACHE_DIR.glob("*__k*.json")):
            payload = json.loads(cache.read_text())
            if payload.get("schema_version") != SCHEMA_VERSION:
                continue
            key = (payload["person"], payload["pose_bin"])
            # В кэше мог лежать дымовой прогон с меньшим k: для пары (человек, бин)
            # берём самую большую выборку, иначе пары посчитаются дважды.
            best = cached.get(key)
            if best is None or int(payload.get("requested_per_group", 0)) > int(best.get("requested_per_group", 0)):
                cached[key] = payload
        results = list(cached.values())
    else:
        if not args.input.is_dir():
            print(f"Нет источника: {args.input}", file=sys.stderr)
            return 2
        groups = discover_groups(args.input, args.max_per_group)
        if args.limit_groups:
            groups = groups[:args.limit_groups]
        results = load_or_compute(groups, args.workers, args.force, args.max_per_group, args.input)

    model = aggregate(results)
    model["generated_by"] = "morphing.backend.calibrate_pose_noise"
    args.out.write_text(json.dumps(model, ensure_ascii=False, indent=2))
    print(f"\nСохранено: {args.out}")
    print(f"  статус полос: {model['band_status']}")
    sampling = model.get("sampling") or {}
    if sampling.get("frame_ids"):
        print(f"  материал: медианный span группы {sampling['median_frame_span']} кадров, "
              f"медиана шага {sampling['median_of_median_frame_gap']} (min "
              f"{sampling['min_of_median_frame_gap']})")
    for pose_bin, data in model["bins"].items():
        close = data.get("within_close_pose", {})
        print(f"  {pose_bin:14s} within p50={data['within'].get('p50')} p95={data['within'].get('p95')} "
              f"| Δyaw<{CLOSE_POSE_DEG}° n={close.get('pairs')} p50={close.get('p50')} "
              f"| between p50={data['between'].get('p50')} AUC={data['auc']} "
              f"corr(Δyaw)={data['drift'].get('corr_abs_dyaw_mean_delta')}")
    agree = model["bin_agreement"]
    print(f"  бин по папке != бин по измеренному yaw: {agree['mismatched']}/{agree['total']}")
    lag = model.get("lag") or {}
    print(f"  шаг кадров при том же ракурсе: сравнено бинов {lag.get('bins_compared')}, "
          f"медиана p95(далёкие)/p95(соседние) = {lag.get('median_p95_far_over_near')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
