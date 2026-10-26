"""🧪 Переносимость полос реконструкции на независимые съёмки (morphing).

Вопрос, на который отвечает скрипт, — можно ли границы `pose_noise_calibration.json`
переносить с видеокадров одной серии на два разных фото. Калибровка собрана на 10
кадрах на бин (медиана папки — 11 кадров), и в парной разности таких кадров сокращается
общее смещение сессии: камера, свет, обработка. Поэтому её полоса — повторяемость
конвейера, а не шум пересъёмки.

Материал: фотоархивы людей, не входивших в калибровку
(`/Volumes/SDCARD/test_photos/{put,vas,udmurt}`), имена файлов содержат дату съёмки.
Держим в уме два разных понятия, которые легко склеить неправильно:

    `near`   — пары с интервалом съёмки ≤ `--near-days` (морфология та же: это почти
               чистый шум конвейера и условий съёмки, годится как граница);
    `spread` — пары с любым интервалом, вплоть до десятилетий (включает настоящее
               изменение лица; это ориентир, а не доказательство «лица совпадают»).

Замеры:
1. доля пар одного человека в том же бине, лежащих ВЫШЕ замороженного p95 (по
   умолчанию — видео-полоса; через `--frozen-bands` — любой ранее выпущенный artifact);
2. полосы near/spread по бинам и межличностное распределение тех же бинов по
   отдельным фото (не по центроидам групп);
3. AUC по бинам: P(пара разных людей дальше, чем пара одного человека). Пары
   «всех сразу» не смешиваем — состав бинов сам создаёт разделение.

Пары не прореживаются произвольно: при превышении `--max-pairs` берём детерминированный
шаг по списку и пишем в отчёт, что прореживание было (прореживание по шагу искажает
хвост распределения сильнее, чем середина).

Запуск (офлайн, CPU; сетки кэшируются в `.runtime/band_transfer/`):
    cd /Users/victorkhudyakov/work
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m morphing.backend.assess_band_transfer \\
        --mode all --max-photos 150 --workers 4 --emit-bands
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from itertools import combinations
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app8.config import POSE_BINS  # noqa: E402
from morphing.backend.pose_noise_model import noise_reference  # noqa: E402

DEFAULT_INPUT = Path("/Volumes/SDCARD/test_photos")
IDENTITIES = ("put", "vas", "udmurt")
CACHE_DIR = ROOT / ".runtime" / "band_transfer"
OUTPUT_PATH = CACHE_DIR / "transfer_report.json"
BANDS_PATH = CACHE_DIR / "reshoot_bands.json"
BINS = tuple(name for name, _lo, _hi, _canonical in POSE_BINS)
DATE_RE = re.compile(r"(?P<year>\d{4})[-_.](?P<month>\d{2})[-_.](?P<day>\d{2})")
RESHOOT_SCHEMA_VERSION = "morphing-reshoot-bands-v2"
MIN_RESHOOT_PAIRS = 20
NEAR_DAYS = 7
#несуществующий путь: оценка пар идёт по замороженной видео-полосе, а не по той самой
#полосе пересъёмок, которую мы измеряем (иначе замер проверяет сам себя).
NO_RESHOOT_MARK = CACHE_DIR / "video_band_only.json"
GAP_STRATA = ("same_day", "within_7d", "within_30d", "within_1y", "over_1y", "unknown_date")


def _photo_date(path: Path) -> date | None:
    """Дата съёмки из имени файла; None — если имени не доверяем."""
    match = DATE_RE.search(path.name)
    if not match:
        return None
    try:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError:
        return None


def _listed_photos(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.glob("*")
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and not p.name.startswith(".")
    )


def discover_photos(input_dir: Path, identities: tuple[str, ...], mode: str,
                    max_photos: int, samples: int, max_dates: int, per_date: int) -> dict[str, list[Path]]:
    """Отбор фото на личность.

    `duplicates` — только дни, где есть ≥2 снимка: самый чистый контроль пересъёмки;
    `spread` — равномерно по всему архиву; `all` — все многодневные дни целиком плюс
    равномерная сетка по остальному архиву до потолка `max_photos` (потолок нужен,
    чтобы межличностные пары не раздулись до O(n²)).
    """
    out: dict[str, list[Path]] = {}
    for name in identities:
        folder = input_dir / name
        if not folder.is_dir():
            continue
        files = _listed_photos(folder)
        if len(files) < 2:
            continue
        by_date: dict[date, list[Path]] = {}
        for path in files:
            day = _photo_date(path)
            if day:
                by_date.setdefault(day, []).append(path)
        multi = [(day, group) for day, group in sorted(by_date.items()) if len(group) >= 2]
        if mode == "duplicates":
            picks: list[Path] = []
            for _day, group in multi[:max_dates]:
                picks.extend(group[:per_date])
        elif mode == "spread":
            count = min(samples, max_photos, len(files))
            indices = np.linspace(0, len(files) - 1, count).round().astype(int)
            picks = [files[i] for i in dict.fromkeys(indices.tolist())]
        else:
            picks = []
            for _day, group in multi:
                picks.extend(group[:per_date])
            remaining = min(max_photos - len(picks), len(files))
            if remaining > 0:
                indices = np.linspace(0, len(files) - 1, remaining).round().astype(int)
                picks.extend(files[i] for i in indices.tolist())
            picks = list(dict.fromkeys(picks))[:max_photos]
        if len(picks) >= 2:
            out[name] = picks
    return out


def _cache_path(photo: Path) -> Path:
    digest = hashlib.sha1(str(photo.resolve()).encode(), usedforsecurity=False).hexdigest()[:16]
    return CACHE_DIR / f"{photo.stem[:24]}__{digest}.npz"


def _reconstruct_one(path_str: str) -> dict[str, Any] | None:
    """Реконструкция одного фото с кэшем сетки в compact-виде."""
    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh, pose_summary

    photo = Path(path_str)
    cache = _cache_path(photo)
    if cache.exists():
        with np.load(cache) as blob:
            return {
                "photo": str(photo), "file": photo.name, "vertices": blob["vertices"],
                "yaw": float(blob["yaw"]), "pose_bin": str(blob["pose_bin"]), "cached": True,
            }
    try:
        recon = reconstruct_image(photo, device="cpu")
    except Exception as exc:  # noqa: BLE001 — архивный обход: сбойный кадр не роняет прогон
        print(f"  ! {photo}: {type(exc).__name__}: {exc}", flush=True)
        return None
    if not recon:
        return None
    vertices, _, radius = align_identity_mesh(recon)
    summary = pose_summary(recon)
    np.savez_compressed(
        cache, vertices=vertices.astype(np.float32), yaw=np.float32(summary["yaw"]),
        pose_bin=np.array(summary["pose_bin"]), radius=np.float32(radius),
    )
    return {
        "photo": str(photo), "file": photo.name, "vertices": vertices,
        "yaw": float(summary["yaw"]), "pose_bin": summary["pose_bin"], "cached": False,
    }


def load_meshes(photos: list[Path], workers: int) -> list[dict[str, Any]]:
    jobs = [str(p.resolve()) for p in photos]
    if workers <= 1:
        return [row for row in map(_reconstruct_one, jobs) if row]
    done = 0
    rows: list[dict[str, Any]] = []
    with Pool(processes=min(workers, len(jobs)), maxtasksperchild=1) as pool:
        for row in pool.imap_unordered(_reconstruct_one, jobs):
            done += 1
            if done % 10 == 0 or not row:
                print(f"    {done}/{len(jobs)}" + ("" if row else " — сбой реконструкции"), flush=True)
            if row:
                rows.append(row)
    return rows


def _gap_stratum(days: int | None) -> str:
    if days is None:
        return "unknown_date"
    if days == 0:
        return "same_day"
    if days <= 7:
        return "within_7d"
    if days <= 30:
        return "within_30d"
    if days <= 365:
        return "within_1y"
    return "over_1y"


def _percentiles(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": int(arr.size),
        "p50": round(float(np.percentile(arr, 50)), 8),
        "p90": round(float(np.percentile(arr, 90)), 8),
        "p95": round(float(np.percentile(arr, 95)), 8),
        "max": round(float(arr.max()), 8),
    }


def _auc(within: list[float], between: list[float]) -> float | None:
    """P(пара разных людей дальше, чем два снимка одного) в пределах одной страты."""
    if not within or not between:
        return None
    wins = sum(1 for a in within for b in between if b > a) + 0.5 * sum(
        1 for a in within for b in between if b == a
    )
    return round(wins / (len(within) * len(between)), 4)


def _stride(rows: list[dict[str, Any]], cap: int) -> tuple[list[dict[str, Any]], bool]:
    """Детерминированный шаг по списку, если пар больше потолка."""
    if len(rows) <= cap:
        return rows, False
    step = len(rows) / cap
    return [rows[int(i * step)] for i in range(cap)], True


def build_within_pairs(rows: list[dict[str, Any]], identity: str) -> list[dict[str, Any]]:
    """Пары одного человека в одном бине: только тогда полоса ракурса применима."""
    pairs: list[dict[str, Any]] = []
    for index_a, row_a in enumerate(rows):
        for row_b in rows[index_a + 1:]:
            if row_a["pose_bin"] != row_b["pose_bin"]:
                continue
            dist = np.linalg.norm(row_a["vertices"] - row_b["vertices"], axis=1)
            gap = _gap_days(_photo_date(Path(row_a["photo"])), _photo_date(Path(row_b["photo"])))
            pairs.append({
                "identity": identity,
                "pair": f"{row_a['file']}|{row_b['file']}",
                "pose_bin": row_a["pose_bin"],
                "gap_days": gap,
                "gap_stratum": _gap_stratum(gap),
                "dyaw": round(abs(row_a["yaw"] - row_b["yaw"]), 3),
                "mean_delta": round(float(dist.mean()), 8),
                "p95_vertex": round(float(np.percentile(dist, 95)), 8),
                "max_delta": round(float(dist.max()), 8),
            })
    return pairs


def build_between_pairs(by_identity: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Пары разных людей в одном бине, из отдельных фото (без центроидов групп)."""
    pairs: list[dict[str, Any]] = []
    for (name_a, rows_a), (name_b, rows_b) in combinations(by_identity.items(), 2):
        for row_a in rows_a:
            for row_b in rows_b:
                if row_a["pose_bin"] != row_b["pose_bin"]:
                    continue
                dist = np.linalg.norm(row_a["vertices"] - row_b["vertices"], axis=1)
                pairs.append({
                    "pair": f"{name_a}:{row_a['file']}|{name_b}:{row_b['file']}",
                    "people": f"{name_a}≠{name_b}",
                    "pose_bin": row_a["pose_bin"],
                    "dyaw": round(abs(row_a["yaw"] - row_b["yaw"]), 3),
                    "mean_delta": round(float(dist.mean()), 8),
                })
    return pairs


def _gap_days(a: date | None, b: date | None) -> int | None:
    return None if not a or not b else abs((a - b).days)


def _reference(pose_bin: str, delta: float, dyaw: float, frozen: dict[str, Any] | None) -> dict[str, Any]:
    """Граница для вердикта: видео-полоса (по умолчанию) или замороженный artifact."""
    if frozen is None:
        ref = noise_reference(pose_bin, delta, yaw_spread_deg=dyaw, reshoot_path=NO_RESHOOT_MARK)
        if not ref.get("available"):
            return {"available": False}
        return {
            "available": True, "basis": "pose_noise_calibration.json (видео-сессия)",
            "verdict": ref["verdict"], "band_p50": ref["expected_p50"], "band_p95": ref["expected_p95"],
            "band_source": ref["band_source"], "band_ratio_p95": ref["band_ratio_p95"],
        }
    data = (frozen.get("bins") or {}).get(pose_bin) or {}
    near = data.get("near") or {}
    if not near.get("pairs"):
        return {"available": False}
    p50, p95 = float(near["p50"]), float(near["p95"])
    verdict = "within_noise" if delta <= p50 else ("near_noise" if delta <= p95 else "above_noise")
    return {
        "available": True, "basis": f"замороженные полосы {frozen.get('schema_version')}",
        "verdict": verdict, "band_p50": p50, "band_p95": p95, "band_source": "reshoot_frozen",
        "band_ratio_p95": round(delta / p95, 4) if p95 > 0 else None,
    }


def annotate(pairs: list[dict[str, Any]], frozen: dict[str, Any] | None) -> list[dict[str, Any]]:
    for pair in pairs:
        pair["reference"] = _reference(pair["pose_bin"], pair["mean_delta"], pair["dyaw"], frozen)
    return [p for p in pairs if p["reference"].get("available")]


def _share_above(rows: list[float], threshold: float | None) -> float | None:
    """Доля значений выше порога; None — если порога нет.

    В полосах пересъёмок порог — медиана разных людей того же бина, а значения — пары
    одного человека. Это и есть честная цена фразы «выше типичного различия между
    людьми»: если таких пар десятки процентов, фраза ничего не утверждает.
    """
    if not rows or threshold is None:
        return None
    return round(sum(1 for v in rows if v > threshold) / len(rows), 4)


def build_reshoot_bands(within: list[dict[str, Any]], between: list[dict[str, Any]],
                        min_pairs: int, near_days: int) -> dict[str, Any]:
    """Полосы near/spread по бинам — то, что можно применять к реальным фото.

    Границей вердикта объявляется только `near`: в `spread` входит настоящее изменение
    лица за годы, и называть её «шумом» нельзя.
    """
    def _side(rows: list[dict[str, Any]]) -> dict[str, Any]:
        stats = _percentiles([p["mean_delta"] for p in rows])
        if not stats["n"]:
            return {"pairs": 0}
        return {
            "pairs": stats["n"], "p50": stats["p50"], "p95": stats["p95"], "max": stats["max"],
            "median_dyaw": round(float(np.median([p["dyaw"] for p in rows])), 2),
        }

    bins: dict[str, Any] = {}
    for pose_bin in BINS:
        in_bin = [p for p in within if p["pose_bin"] == pose_bin]
        if not in_bin:
            continue
        dated = [p for p in in_bin if p["gap_days"] is not None]
        near = [p for p in dated if p["gap_days"] <= near_days]
        across = [p["mean_delta"] for p in between if p["pose_bin"] == pose_bin]
        near_side, spread_side = _side(near), _side(dated)
        betw = _percentiles(across)
        bins[pose_bin] = {
            "near": near_side,
            "spread": spread_side,
            "operative": near_side["pairs"] >= min_pairs,
            "between_photos": betw,
            "auc_near": _auc([p["mean_delta"] for p in near], across),
            "auc_spread": _auc([p["mean_delta"] for p in dated], across),
            "share_near_above_between_p50": _share_above(
                [p["mean_delta"] for p in near], betw.get("p50")),
            "share_spread_above_between_p50": _share_above(
                [p["mean_delta"] for p in dated], betw.get("p50")),
        }
    return {
        "schema_version": RESHOOT_SCHEMA_VERSION,
        "meaning": ("разброс средней разницы 3D-сетки между двумя независимыми снимками "
                    "одного человека в одном бине ракурса"),
        "population": ("фотоархивы людей, не входивших в видеокалибровку; "
                       f"near — интервал съёмки ≤ {near_days} дней, spread — любой интервал"),
        "near_days": near_days,
        "min_pairs_to_use": min_pairs,
        "note": ("границей вердикта может быть только near: в spread входит настоящее "
                 "морфологическое изменение, и называть его «шумом» нельзя"),
        "bins": bins,
    }


def summarise(usable: list[dict[str, Any]], between: list[dict[str, Any]],
              composition: dict[str, Any]) -> dict[str, Any]:
    """Главная цифра: доля внутриличностных пар выше замороженной границы."""
    above = [p for p in usable if p["reference"]["verdict"] == "above_noise"]
    strata: dict[str, Any] = {}
    for stratum in GAP_STRATA:
        group = [p for p in usable if p["gap_stratum"] == stratum]
        if not group:
            continue
        group_above = [p for p in group if p["reference"]["verdict"] == "above_noise"]
        strata[stratum] = {
            "pairs": len(group),
            "share_above_band_p95": round(len(group_above) / len(group), 4),
            **_percentiles([p["mean_delta"] for p in group]),
        }
    per_bin: dict[str, Any] = {}
    for pose_bin in BINS:
        group = [p for p in usable if p["pose_bin"] == pose_bin]
        if not group:
            continue
        group_above = [p for p in group if p["reference"]["verdict"] == "above_noise"]
        across = [p["mean_delta"] for p in between if p["pose_bin"] == pose_bin]
        per_bin[pose_bin] = {
            "pairs": len(group),
            "share_above_band_p95": round(len(group_above) / len(group), 4),
            "median_band_ratio_p95": round(float(np.median(
                [p["reference"]["band_ratio_p95"] or 0 for p in group])), 3),
            "between_pairs": len(across),
            **_percentiles([p["mean_delta"] for p in group]),
            "auc": _auc([p["mean_delta"] for p in group], across),
        }
    per_person: dict[str, Any] = {}
    for identity in sorted({p["identity"] for p in usable}):
        group = [p for p in usable if p["identity"] == identity]
        group_above = [p for p in group if p["reference"]["verdict"] == "above_noise"]
        per_person[identity] = {
            "pairs": len(group),
            "share_above_band_p95": round(len(group_above) / len(group), 4),
            **_percentiles([p["mean_delta"] for p in group]),
        }
    qualified = [d["auc"] for d in per_bin.values() if d["pairs"] >= MIN_RESHOOT_PAIRS
                 and d["between_pairs"] >= MIN_RESHOOT_PAIRS and d["auc"] is not None]
    near_all = [p for p in usable if p["gap_days"] is not None and p["gap_days"] <= NEAR_DAYS]
    near_above = [p for p in near_all if p["reference"]["verdict"] == "above_noise"]
    return {
        "pairs_compared": len(usable),
        "share_above_band_p95": round(len(above) / len(usable), 4) if usable else None,
        "share_above_p95_near_pairs": round(len(near_above) / len(near_all), 4) if near_all else None,
        "pairs_near": len(near_all),
        "auc_median_over_qualified_bins": round(float(np.median(qualified)), 4) if qualified else None,
        "qualified_bins": len(qualified),
        "composition_note": composition,
        "by_gap_stratum": strata,
        "by_bin": per_bin,
        "by_identity": per_person,
        "between_pairs": len(between),
        "between": _percentiles([p["mean_delta"] for p in between]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Переносимость полос на независимые съёмки")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), type=Path)
    parser.add_argument("--identities", default=list(IDENTITIES), nargs="*")
    parser.add_argument("--mode", default="all", choices=("all", "spread", "duplicates"))
    parser.add_argument("--max-photos", default=150, type=int, help="потолок фото на личность")
    parser.add_argument("--samples", default=40, type=int, help="фото на личность в режиме spread")
    parser.add_argument("--max-dates", default=200, type=int, help="дней в режиме duplicates")
    parser.add_argument("--per-date", default=4, type=int, help="фото на день в режиме duplicates")
    parser.add_argument("--near-days", default=NEAR_DAYS, type=int)
    parser.add_argument("--min-pairs", default=MIN_RESHOOT_PAIRS, type=int)
    parser.add_argument("--max-pairs", default=60000, type=int, help="потолок пар на сторону")
    parser.add_argument("--workers", default=4, type=int)
    parser.add_argument("--frozen-bands", default=None, type=Path,
                        help="оценивать пары по ранее выпущенным полосам, а не по видео-полосе")
    parser.add_argument("--emit-bands", default=None, type=Path, nargs="?", const=BANDS_PATH,
                        help="записать мереные полосы near/spread по бинам")
    parser.add_argument("--out", default=str(OUTPUT_PATH), type=Path)
    args = parser.parse_args()

    found = discover_photos(Path(args.input), tuple(args.identities), args.mode, args.max_photos,
                            args.samples, args.max_dates, args.per_date)
    if len(found) < 2:
        print("Нужны минимум две личности: сравнивать «между людьми» нечем", file=sys.stderr)
        return 2
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"режим={args.mode} фото: " + ", ".join(f"{k}={len(v)}" for k, v in found.items()), flush=True)

    by_identity: dict[str, list[dict[str, Any]]] = {}
    for identity, photos in found.items():
        rows = load_meshes(photos, args.workers)
        print(f"  {identity}: реконструировано {len(rows)} из {len(photos)}", flush=True)
        if len(rows) >= 2:
            by_identity[identity] = rows
    if len(by_identity) < 2:
        return 2

    within_raw = [p for identity, rows in by_identity.items() for p in build_within_pairs(rows, identity)]
    between_raw = build_between_pairs(by_identity)
    within, thinned_within = _stride(within_raw, args.max_pairs)
    between, thinned_between = _stride(between_raw, args.max_pairs)
    composition = {
        "within_pairs_total": len(within_raw), "within_pairs_used": len(within),
        "within_thinned": thinned_within,
        "between_pairs_total": len(between_raw), "between_pairs_used": len(between),
        "between_thinned": thinned_between,
        "thinning_note": ("шаг по списку: хвост распределения при прореживании искажается "
                          "сильнее, чем середина" if (thinned_within or thinned_between) else "прореживания не было"),
    }
    frozen = json.loads(args.frozen_bands.read_text()) if args.frozen_bands else None
    usable = annotate(within, frozen)
    between_usable = annotate(between, frozen)

    report = {
        "question": ("доля сравнений одного человека по разным съёмкам выше замороженной границы "
                     "его ракурса"),
        "reference_basis": (frozen or {}).get("schema_version") if frozen else "видео-полоса калибровки",
        "mode": args.mode,
        "photos": {k: len(v) for k, v in by_identity.items()},
        "summary": summarise(usable, between_usable, composition),
        "within_pairs": usable,
        "between_pairs_sample": between_usable[:400],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    bands = build_reshoot_bands(within, between, args.min_pairs, args.near_days)
    if args.emit_bands:
        args.emit_bands.parent.mkdir(parents=True, exist_ok=True)
        args.emit_bands.write_text(json.dumps(bands, ensure_ascii=False, indent=2))
        print(f"\nполосы пересъёмок записаны: {args.emit_bands}")

    s = report["summary"]
    print(f"\nпар одного человека: {s['pairs_compared']} (near ≤{args.near_days}д: {s['pairs_near']}), "
          f"выше границы p95: {s['share_above_band_p95']:.1%} "
          f"(по near-парам: {(s['share_above_p95_near_pairs'] or 0):.1%})")
    print(f"медианная AUC по бинам с n≥{args.min_pairs}: {s['auc_median_over_qualified_bins']} "
          f"(бинов: {s['qualified_bins']})")
    for stratum, data in s["by_gap_stratum"].items():
        print(f"  {stratum:12s} n={data['pairs']:5d} выше p95 {data['share_above_band_p95']:5.1%} "
              f"p50={data.get('p50')} p95={data.get('p95')}")
    for pose_bin, data in s["by_bin"].items():
        side = (bands["bins"].get(pose_bin) or {}).get("near") or {}
        flag = "оперативная" if side.get("pairs", 0) >= args.min_pairs else "мало near-пар"
        share = (bands["bins"].get(pose_bin) or {}).get("share_spread_above_between_p50")
        print(f"  {pose_bin:12s} n={data['pairs']:5d} выше p95 {data['share_above_band_p95']:5.1%} "
              f"AUC={data['auc']} near p50={side.get('p50')} p95={side.get('p95')} ({flag}) "
              f"| доля пар одного человека выше медианы разных людей: "
              f"{share if share is not None else '—'}")
    print(f"\nСохранено: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
