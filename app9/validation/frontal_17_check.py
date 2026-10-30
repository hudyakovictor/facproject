#!/usr/bin/env python
"""Перепроверка ИСХОДНЫХ 17 метрик 3DDFA (identity.form_vector) на фронтальных фото.

Отбирает из *_angles.csv только фронтальные кадры (pose_bin==frontal, |yaw|<=15,
status==ok), прогоняет каждый боевым конвейером app8.reconstruction +
align_identity_mesh -> form_vector, и проверяет, что 17 исходных признаков реально
присутствуют и различают put/vas/udmurt. Дополнительно — accuracy классификатора
на этом же фронтальном подмножестве готовыми эталонами.

Выход: .runtime/frontal_17_check.jsonl (кэш на фото) и .runtime/frontal_17_check.json.
"""
from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
DATA = Path("/Volumes/SDCARD/test_photos")
CACHE = ROOT / ".runtime" / "frontal_17_check.jsonl"
OUT = ROOT / ".runtime" / "frontal_17_check.json"
IDENTITIES = ("put", "vas", "udmurt")
CSVS = {n: ROOT / f"{n}_angles.csv" for n in IDENTITIES}


def pose_files(ident: str, bins: tuple[str, ...], yaw_min: float = 0.0,
               yaw_max: float = 15.0) -> list[Path]:
    """Кадры по *_angles.csv: status==ok, бин входит в `bins`, |yaw| в [yaw_min, yaw_max].

    Один фильтр на все выборки по ракурсу: раньше он был переписан в каждой проверке
    по-своему, и правка порога разъезжалась по скриптам.
    """
    keep: list[Path] = []
    with CSVS[ident].open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            name = (rec.get("filename") or "").strip()
            if not name or (rec.get("status") or "").strip() != "ok":
                continue
            if (rec.get("pose_bin") or "").strip() not in bins:
                continue
            try:
                yaw = float(rec.get("yaw_deg"))
            except (TypeError, ValueError):
                continue
            if not yaw_min <= abs(yaw) <= yaw_max:
                continue
            path = DATA / ident / name
            if path.is_file():
                keep.append(path)
    return keep


def frontal_files(ident: str) -> list[Path]:
    return pose_files(ident, ("frontal",), 0.0, 15.0)


# Подфронтальный ракурс: голова повёрнута на 10–25°, лицо ещё целиком видно.
# Бины left_light/right_light; нижняя граница 10° стоит не для «другого диапазона»,
# а чтобы выборки не пересекались по фото: фронтальные кадры с |yaw| до 15 лежат в
# бине frontal, сюда попадают только лёгкие повороты.
SUBFRONTAL_BINS = ("left_light", "right_light")
SUBFRONTAL_YAW = (10.0, 25.0)


def subfrontal_files(ident: str) -> list[Path]:
    return pose_files(ident, SUBFRONTAL_BINS, *SUBFRONTAL_YAW)


def load_cache() -> dict[str, list[float]]:
    done: dict[str, list[float]] = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                done[r["key"]] = r["vector"]
            except json.JSONDecodeError:
                continue
    return done


def main() -> None:
    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh
    from morphing.backend import identity as I

    done = load_cache()
    cache_fh = CACHE.open("a", encoding="utf-8")
    started = time.time()
    recon_ok = recon_fail = cached = 0

    for ident in IDENTITIES:
        files = frontal_files(ident)
        print(f"[{ident}] фронтальных фото: {len(files)}", flush=True)
        for path in files:
            key = f"{ident}/{path.name}"
            if key in done:
                cached += 1
                continue
            try:
                rec = reconstruct_image(path, device="cpu")
                _, lm, _ = align_identity_mesh(rec)
                vec = I.form_vector(lm)
            except Exception as exc:  # noqa: BLE001
                recon_fail += 1
                print(f"  FAIL {key}: {type(exc).__name__} {exc}", flush=True)
                continue
            if lm is None or vec is None:
                recon_fail += 1
                continue
            done[key] = [round(float(v), 6) for v in vec]
            cache_fh.write(json.dumps({"key": key, "vector": done[key]}) + "\n")
            cache_fh.flush()
            recon_ok += 1
            if (recon_ok + recon_fail) % 20 == 0:
                print(f"  прогресс {recon_ok + recon_fail},elapsed {time.time() - started:.0f}s", flush=True)
    cache_fh.close()

    # --- агрегация по личностям ---
    per_id: dict[str, np.ndarray] = {}
    for ident in IDENTITIES:
        rows = [done[f"{ident}/{p.name}"] for p in frontal_files(ident)
                if f"{ident}/{p.name}" in done]
        if rows:
            per_id[ident] = np.array(rows, dtype=float)

    pooled = np.vstack([v for v in per_id.values()])
    med = np.median(pooled, axis=0)
    mad = 1.4826 * np.median(np.abs(pooled - med), axis=0)
    mad = np.where(mad < 1e-8, np.std(pooled, axis=0) + 1e-8, mad)

    separation = []
    for j, feat in enumerate(I.FEATURE_ORDER):
        groups = [per_id[i][:, j] for i in IDENTITIES if i in per_id]
        allv = np.concatenate(groups)
        grand = allv.mean()
        ss_b = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
        ss_t = ((allv - grand) ** 2).sum()
        eta2 = ss_b / ss_t if ss_t > 1e-12 else 0.0
        meds = {i: float(np.median(per_id[i][:, j])) for i in per_id}
        spread = (max(meds.values()) - min(meds.values()))
        separation.append({
            "feature": feat, "eta2": round(eta2, 4),
            "spread_over_mad": round(spread / mad[j], 3),
            "pooled_med": round(float(med[j]), 5), "pooled_mad": round(float(mad[j]), 5),
            "medians": {k: round(v, 5) for k, v in meds.items()},
        })
    sep_sorted = sorted(separation, key=lambda r: r["eta2"], reverse=True)

    # --- accuracy боевым классификатором на фронтальном подмножестве ---
    acc = {}
    try:
        model = I.load_prototypes()
        correct = tot = 0
        conf = defaultdict(lambda: [0, 0])
        for ident in IDENTITIES:
            if ident not in per_id:
                continue
            for vec in per_id[ident]:
                z = I._robust_z(model, vec)  # vec уже 17-мерный form_vector
                dists = [I._identity_distance(model, z, name) for name in model.identities]
                logits = -I.SOFTMAX_BETA * np.array(dists)
                logits -= logits.max()
                exp = np.exp(logits)
                probs = exp / exp.sum()
                best = model.identities[int(np.argmax(probs))]
                tot += 1
                conf[ident][1] += 1
                if best == ident:
                    correct += 1
                    conf[ident][0] += 1
        acc = {"overall": round(correct / tot, 4) if tot else None, "n": tot,
               "per_identity": {i: [f"{c}/{n}", round(c / n, 3) if n else None]
                                for i, (c, n) in conf.items()}}
    except Exception as exc:  # noqa: BLE001
        acc = {"error": str(exc)}

    report = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_sec": round(time.time() - started, 1),
        "counts_frontal": {i: len(frontal_files(i)) for i in IDENTITIES},
        "recon_ok": recon_ok, "recon_fail": recon_fail, "cached_reused": cached,
        "vectors_per_identity": {i: int(v.shape[0]) for i, v in per_id.items()},
        "separation_by_eta2": sep_sorted,
        "presence_flags": {
            "strong(eta2>=0.20)": [r["feature"] for r in sep_sorted if r["eta2"] >= 0.20],
            "medium(0.08-0.20)": [r["feature"] for r in sep_sorted if 0.08 <= r["eta2"] < 0.20],
            "weak(<0.08)": [r["feature"] for r in sep_sorted if r["eta2"] < 0.08],
        },
        "accuracy_frontal": acc,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== ИТОГО ===")
    print("фронтальных vectors/личность:", report["vectors_per_identity"])
    print("recon ok/fail/cached:", recon_ok, recon_fail, cached)
    print("\nРазделение 17 исходных метрик (анфас):")
    for r in sep_sorted:
        print(f"  eta2={r['eta2']:.3f} spread/MAD={r['spread_over_mad']:.2f} {r['feature']:22s} {r['medians']}")
    print("\nAccuracy классификатора на анфасе:", json.dumps(acc, ensure_ascii=False))
    print(f"\nОтчёт: {OUT}")


if __name__ == "__main__":
    main()
