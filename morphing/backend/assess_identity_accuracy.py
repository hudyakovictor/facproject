"""🧪 Честная оценка 3-way эталонов формы на held-out фото (morphing).

Панель «вероятности личностей» в UI — эвристика: softmax по робастному z-расстоянию
по 17 метрикам формы. Чтобы она что-то стоила, нужен хотя бы один числовой ответ на
вопрос «а она вообще попадает в свою личность?». Раньше такого ответа не было:
`build_prototypes` пишет только число использованных фото, но не их список, поэтому
любая оценка по тем же папкам рискует быть оценкой на трейне.

Что делает скрипт:
1. воспроизводит отбор трейна детерминированно (`_pick_samples` по сортировке имён с
   `meta.samples_per_identity_requested`) и ИСКЛЮЧАЕТ эти файлы из проверки;
2. берёт из остатка равномерно до `--per-identity` фото;
3. считает `probabilities()` по боевому коду и собирает accuracy по личностям,
   confusion-матрицу и распределение отрыва лидера от второго;
4. отдельно пишет accuracy по позам (`pose_bin`) и по уровню уверенности панели
   (лидер <50% / 50–60% / ≥60%) — «мы угадываем» и «мы редко уверены» это разные
   новости, и сводить их в одну цифру нельзя;
5. хранит сырые строки по фото, чтобы вывод можно было пересчитать без перепрогона.

Запуск (офлайн, CPU; сетки кэшируются в `.runtime/identity_eval/`):
    cd /Users/victorkhudyakov/work
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m morphing.backend.assess_identity_accuracy \\
        --per-identity 40 --workers 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from morphing.backend.identity import (  # noqa: E402
    FEATURE_ORDER,
    PROTOTYPES_PATH,
    _pick_samples,
    load_prototypes,
    probabilities,
)

DEFAULT_INPUT = Path("/Volumes/SDCARD/test_photos")
CACHE_DIR = ROOT / ".runtime" / "identity_eval"
OUTPUT_PATH = CACHE_DIR / "identity_eval.json"
# Пороги «уверенности» панели: лидер по процентам сходства.
CONFIDENT_SHARE = 60.0
CONFIDENCE_BUCKETS = ((0.0, 50.0), (50.0, CONFIDENT_SHARE), (CONFIDENT_SHARE, 101.0))


def _cache_path(photo: Path) -> Path:
    digest = hashlib.sha1(str(photo.resolve()).encode(), usedforsecurity=False).hexdigest()[:16]
    return CACHE_DIR / f"{photo.stem[:24]}__{digest}.npz"


def _landmarks(path_str: str) -> dict[str, Any] | None:
    """106 канонических точек с кэшем; тяжёлый шаг, поэтому офлайн и параллельно."""
    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh, pose_summary

    photo = Path(path_str)
    cache = _cache_path(photo)
    if cache.exists():
        with np.load(cache) as blob:
            return {"photo": str(photo), "identity": photo.parent.name,
                    "landmarks": blob["landmarks"], "pose_bin": str(blob["pose_bin"])}
    try:
        recon = reconstruct_image(photo, device="cpu")
    except Exception as exc:  # noqa: BLE001 — обход архива: сбойный кадр не роняет прогон
        print(f"  ! {photo.name}: {type(exc).__name__}: {exc}", flush=True)
        return None
    if not recon:
        return None
    _verts, landmarks, _radius = align_identity_mesh(recon)
    bin_name = pose_summary(recon)["pose_bin"]
    np.savez_compressed(cache, landmarks=landmarks.astype(np.float32), pose_bin=np.array(bin_name))
    return {"photo": str(photo), "identity": photo.parent.name, "landmarks": landmarks,
            "pose_bin": str(bin_name)}


def held_out_files(root: Path, identities: list[str], per_identity: int) -> dict[str, list[Path]]:
    """Файлы для проверки: НЕ входящие в детерминированный отбор сборки эталонов."""
    meta = json.loads(PROTOTYPES_PATH.read_text()).get("meta") or {}
    requested = int(meta.get("samples_per_identity_requested") or 0)
    out: dict[str, list[Path]] = {}
    for name in identities:
        folder = root / name
        if not folder.is_dir():
            continue
        files = sorted(
            p for p in folder.glob("*")
            if p.is_file() and not p.name.startswith(".")
            and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        )
        train = {p.name for p in _pick_samples(files, requested)} if requested else set()
        rest = [p for p in files if p.name not in train]
        out[name] = rest[:per_identity] if per_identity else rest
    return out


def _rows(samples: list[dict[str, Any]], model: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in samples:
        try:
            verdict = probabilities(model, item["landmarks"])
        except ValueError:
            continue
        dist = verdict["distances"]
        order = sorted(dist.items(), key=lambda kv: kv[1])
        rows.append({
            "identity": item["identity"],
            "file": Path(item["photo"]).name,
            "pose_bin": item["pose_bin"],
            "best_match": verdict["best_match"],
            "correct": verdict["best_match"] == item["identity"],
            "top_share": verdict["probabilities"][verdict["best_match"]],
            "margin": round(order[1][1] - order[0][1], 4),
            "probabilities": verdict["probabilities"],
        })
    return rows


def summarise(rows: list[dict[str, Any]], identities: list[str]) -> dict[str, Any]:
    correct = [r for r in rows if r["correct"]]
    confusion = {name: dict(Counter(r["best_match"] for r in rows if r["identity"] == name))
                 for name in identities}
    by_identity = {}
    for name in identities:
        group = [r for r in rows if r["identity"] == name]
        if group:
            by_identity[name] = {
                "photos": len(group),
                "accuracy": round(sum(r["correct"] for r in group) / len(group), 4),
                "median_margin": round(float(np.median([r["margin"] for r in group])), 4),
            }
    by_bin = {}
    for bin_name in sorted({r["pose_bin"] for r in rows}):
        group = [r for r in rows if r["pose_bin"] == bin_name]
        by_bin[bin_name] = {
            "photos": len(group),
            "accuracy": round(sum(r["correct"] for r in group) / len(group), 4),
        }
    # Accuracy по уровню уверенности: «лидер ≥60%» ничего не стоит, если таких кадров
    # 5%. Поэтому отдельно — как часто панель уверена и что это тогда даёт.
    by_confidence = {}
    for lo, hi in CONFIDENCE_BUCKETS:
        group = [r for r in rows if lo <= r["top_share"] < hi]
        if group:
            by_confidence[f"{lo:g}–{hi:g}%"] = {
                "photos": len(group),
                "share_of_photos": round(len(group) / len(rows), 4),
                "accuracy": round(sum(r["correct"] for r in group) / len(group), 4),
            }
    confident = [r for r in rows if r["top_share"] >= CONFIDENT_SHARE]
    return {
        "photos": len(rows),
        "chance": round(1 / max(len(identities), 1), 4),
        "top1_accuracy": round(len(correct) / len(rows), 4) if rows else None,
        "accuracy_when_confident": round(
            sum(r["correct"] for r in confident) / len(confident), 4
        ) if confident else None,
        "share_confident": round(len(confident) / len(rows), 4) if rows else None,
        "by_confidence": by_confidence,
        "by_identity": by_identity,
        "by_pose_bin": by_bin,
        "confusion": confusion,
        "median_margin": round(float(np.median([r["margin"] for r in rows])), 4) if rows else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Оценка эталонов формы на held-out фото")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), type=Path)
    parser.add_argument("--identities", default=["put", "vas", "udmurt"], nargs="*")
    parser.add_argument("--per-identity", default=40, type=int)
    parser.add_argument("--workers", default=4, type=int)
    parser.add_argument("--prototypes", default=str(PROTOTYPES_PATH), type=Path)
    parser.add_argument("--out", default=str(OUTPUT_PATH), type=Path)
    args = parser.parse_args()

    model = load_prototypes(args.prototypes)
    planned = held_out_files(Path(args.input), list(args.identities), args.per_identity)
    if not planned or not any(planned.values()):
        print("held-out фото не найдены — все файлы ушли в сборку эталонов", file=sys.stderr)
        return 2
    print(f"эталоны: {model.identities}; held-out: "
          + ", ".join(f"{k}={len(v)}" for k, v in planned.items()), flush=True)

    jobs = [str(p.resolve()) for files in planned.values() for p in files]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    if args.workers <= 1:
        samples = [row for row in map(_landmarks, jobs) if row]
    else:
        done = 0
        with Pool(processes=min(args.workers, len(jobs)), maxtasksperchild=1) as pool:
            for row in pool.imap_unordered(_landmarks, jobs):
                done += 1
                if done % 10 == 0 or not row:
                    print(f"  {done}/{len(jobs)}" + ("" if row else " — сбой реконструкции"), flush=True)
                if row:
                    samples.append(row)

    rows = _rows(samples, model)
    report = {
        "question": "top-1 accuracy 3-way эталонов формы на фото, не входивших в их сборку",
        "prototypes": str(args.prototypes),
        "prototype_meta": {k: model.meta.get(k) for k in ("alignment", "photos_used",
                                                          "samples_per_identity_requested")},
        "feature_order_len": len(FEATURE_ORDER),
        "reconstructed": len(rows),
        "summary": summarise(rows, list(planned)),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    s = report["summary"]
    print(f"\ntop-1 = {s['top1_accuracy']:.1%} по {s['photos']} held-out фото "
          f"(случайно = {s['chance']:.1%})")
    for bucket, data in s["by_confidence"].items():
        print(f"  лидер {bucket:>8s}: n={data['photos']:3d} ({data['share_of_photos']:5.1%} кадров) "
              f"accuracy={data['accuracy']:.1%}")
    for name, data in s["by_identity"].items():
        print(f"  {name:8s} n={data['photos']:3d} accuracy={data['accuracy']:.1%} "
              f"медиана отрыва={data['median_margin']}")
    for bin_name, data in s["by_pose_bin"].items():
        print(f"  {bin_name:14s} n={data['photos']:3d} accuracy={data['accuracy']:.1%}")
    print(f"\nСохранено: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
