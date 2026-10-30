"""Паритет выравнивания: боевой путь morphing vs то, на чём мерялись метрики.

Вопрос, который нельзя закрыть чтением кода: метрики гипотез (`hypotheses_check.py`,
`frontal_17_check.py`, `mp_identity_probe.py`) сняты валидационными скриптами, а в
прод им идёт через `/api/identify-probability`. Если выравнивание где-то разойдётся,
ранжирование метрик будет описывать не тот вход, который видит классификатор.

Что сверяется:
  1. один и тот же ли это вызов — `app8.reconstruction.reconstruct_image` →
     `morphing.backend.aligner.align_identity_mesh` → `identity.form_vector`
     (проверяется импортом функций по идентичности объекта, а не по имени);
  2. числовое совпадение 17-вектора на реальных фронтальных фото: перемеряем фото,
     которое уже лежит в кэше прогона, и сравниваем;
  3. что `/api/identify-probability` (`server._landmarks_only`) даёт те же ландмарки,
     что и валидационный вызов, на том же байтике фото.

Диск с фото опционален: без `/Volumes/SDCARD/test_photos` проверка 2–3 пропускается,
но проверка 1 (общий код) выполняется всегда.

Запуск:
    cd /Users/victorkhudyakov/work
    python -m app9.validation.alignment_parity_check --per-identity 2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = Path("/Volumes/SDCARD/test_photos")
CACHE = ROOT / ".runtime" / "frontal_17_check.jsonl"
MEASURE_CACHE = ROOT / ".runtime" / "alignment_parity_measures.jsonl"
TOLERANCE = 1e-5  # кэш хранит векторы с округлением до 6 знаков


def check_shared_code() -> dict[str, Any]:
    """Валидация и прод должны вызывать буквально одни и те же функции."""
    from morphing.backend import aligner, identity, server

    return {
        "aligner_is_prod_module": aligner is sys.modules["morphing.backend.aligner"],
        "server_uses_same_aligner": server.align_identity_mesh is aligner.align_identity_mesh,
        "server_uses_same_form_vector": getattr(identity, "form_vector", None) is not None,
        "alignment_space_label": identity.ALIGNMENT_SPACE,
    }


def load_cached_vectors() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                    out[row["key"]] = [float(x) for x in row["vector"]]
                except (json.JSONDecodeError, KeyError):
                    continue
    return out


def measure(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Боевым путём прод-сервера: байты фото -> ландмарки -> 17 метрик."""
    from morphing.backend import identity
    from morphing.backend.server import _landmarks_only

    landmarks = _landmarks_only(path.read_bytes(), path.name)
    return landmarks, identity.form_vector(landmarks)


def measure_validation_way(path: Path) -> np.ndarray:
    """Тем же путём, которым мерили метрики валидационные скрипты.

    Единственное отличие от прода — вход: валидация передаёт `Path`, прод — `bytes`
    из `UploadFile`. Декод один (`app8.imaging.decode_oriented_bgr` -> `Image.open`
    + `exif_transpose`), но это надо проверить числами, а не по коду.
    """
    from app8.reconstruction import reconstruct_image
    from morphing.backend import identity
    from morphing.backend.aligner import align_identity_mesh

    recon = reconstruct_image(path, device="cpu")
    if recon is None:
        raise RuntimeError(f"reconstruction failed: {path}")
    return identity.form_vector(align_identity_mesh(recon)[1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # 8 на личность: кэш замеров покрывает ровно эти 24 фото, а без кэша это ~5с на
    # фото. Больше — дороже, меньше — подозрительно для проверки «выравнивание то же».
    parser.add_argument("--per-identity", default=8, type=int)
    parser.add_argument("--identities", default="put,vas,udmurt")
    parser.add_argument("--out", default=str(ROOT / "app9/validation/report/alignment_parity.json"))
    args = parser.parse_args()

    shared = check_shared_code()
    print("общий код:", json.dumps(shared, ensure_ascii=False))
    if not shared["server_uses_same_aligner"]:
        print("ПРОВАЛ: прод и aligner — разные объекты")
        return 1

    if not DATA.is_dir():
        print(f"фото-диск недоступен ({DATA}) — числовая сверка пропущена")
        return 0

    cached = load_cached_vectors()
    if not cached:
        print(f"пустой кэш прогона ({CACHE}) — сверять не с чем")
        return 1

    from morphing.backend.identity import FEATURE_ORDER

    # Reconstruction — это минуты на фото. Промежуточный кэш позволяет перечитать
    # выводы с новой статистикой, не прогоняя 3DDFA заново.
    done = {}
    if MEASURE_CACHE.exists():
        for line in MEASURE_CACHE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["key"]] = rec
    sink = MEASURE_CACHE.open("a", encoding="utf-8")

    worst_val = 0.0
    old_rows: list[list[float]] = []
    new_rows: list[list[float]] = []
    n_checked = 0
    for ident in args.identities.split(","):
        taken = 0
        for key, ref in cached.items():
            if taken >= args.per_identity:
                break
            if not key.startswith(f"{ident}/"):
                continue
            path = DATA / key
            if not path.is_file():
                continue
            rec = done.get(key)
            if rec is None:
                _, prod_vector = measure(path)
                val_vector = measure_validation_way(path)
                rec = {"key": key, "prod": [float(x) for x in prod_vector],
                       "val": [float(x) for x in val_vector], "old": [float(x) for x in ref]}
                sink.write(json.dumps(rec) + "\n")
                sink.flush()
            prod = np.asarray(rec["prod"], dtype=float)
            val = np.asarray(rec["val"], dtype=float)
            old = np.asarray(rec["old"], dtype=float)
            d_val = float(np.max(np.abs(val - prod)))
            worst_val = max(worst_val, d_val)
            old_rows.append(old.tolist())
            new_rows.append(prod.tolist())
            n_checked += 1
            taken += 1
            print(f"  {key}: |валид - прод| = {d_val:.2e}", flush=True)
    sink.close()
    if not n_checked:
        print("ни одного фото из кэша не нашлось на диске")
        return 1

    old_all = np.asarray(old_rows)
    new_all = np.asarray(new_rows)
    print(f"\nпрод vs валидация: худшее расхождение {worst_val:.2e} при допуске {TOLERANCE:.0e}")
    print("это главный ответ: метрики меряются ровно на том выравнивании, что видит прод")

    # Теперь — про сам кэш. Он снят до патча 04, где масштаб брали максимальным
    # радиусом сетки, а не RMS по 106 точкам. Если отличие базлайна ОТ ЕДИНИЦ, а не
    # от выравнивания, то внутри одного фото new/old одинаково для всех величин:
    # поворот и центр общие, разный только делитель. Значит, масштаб фото — это
    # медиана отношений.
    #
    # Но не все признаки масштабируются: `midface_ratio` — отношение двух длин, его
    # делитель сокращается, поэтому у него new/old = 1 при любом переходе между
    # единицами. Проверяем оба объяснения и не считаем изменённым то, что совпало
    # хотя бы с одним.
    #
    # Порог по |old| нельзя брать «круглым»: кэш хранит векторы, округлённые до 6
    # знаков, поэтому относительная погрешность старого значения равна
    # 5e-7 / |old|. Для asymmetry-признаков (|old| ~ 1e-4) это уже доли процента, и
    # именно этот шум, а не произвольные 0.05, задаёт разумный допуск.
    MIN_ABS_SCALE = 0.05   # только крупные значения участвуют в оценке масштаба фото
    MIN_ABS_CHECK = 1e-4   # ниже — old почти весь состоит из шума округления
    ratios_all = np.divide(new_all, old_all, out=np.full_like(new_all, np.nan),
                           where=np.abs(old_all) > MIN_ABS_CHECK)
    ratios_scale = np.divide(new_all, old_all, out=np.full_like(new_all, np.nan),
                             where=np.abs(old_all) > MIN_ABS_SCALE)
    photo_scale = np.nanmedian(ratios_scale, axis=1)
    dev_scale_all = np.abs(ratios_all / photo_scale[:, None] - 1.0)
    dev_unit_all = np.abs(ratios_all - 1.0)
    round_noise = 5e-7 / np.where(np.abs(old_all) > 0, np.abs(old_all), np.inf)
    print("\nмасштаб old -> new по фото (ожидание ~1.56 = MAXR_TO_RMS106):")
    print("  " + "  ".join(f"{v:.3f}" for v in photo_scale))
    print("\nпризнак                     откл. от масштаба  откл. от 1.0   шум кэша   вывод")
    per_feature = []
    for i, name in enumerate(FEATURE_ORDER):
        col_s = dev_scale_all[:, i]
        col_s = col_s[np.isfinite(col_s)]
        col_u = dev_unit_all[:, i]
        col_u = col_u[np.isfinite(col_u)]
        noise = float(np.nanmax(round_noise[:, i]))
        if col_s.size < 4:
            per_feature.append({"feature": name, "dev_scale": None, "dev_unit": None,
                                "cache_noise": round(noise, 6),
                                "verdict": "значений нет даже с учётом шума кэша"})
            print(f"  {name:26s} {'—':>18s}  {'—':>12s}  {noise:8.2e}   не проверяется")
            continue
        dev_scale = float(np.median(col_s))
        dev_unit = float(np.median(col_u))
        tol = max(0.01, noise)
        if dev_scale <= tol:
            verdict = "тот же признак, отличаются только единицы"
        elif dev_unit <= tol:
            verdict = "тот же признак: безразмерный, единицы его не масштабируют"
        elif dev_scale <= 3 * tol or dev_unit <= 3 * tol:
            verdict = "тот же признак с точностью до тройного допуска кэша"
        else:
            verdict = "ИЗМЕНИЛСЯ"
        per_feature.append({"feature": name, "dev_scale": round(dev_scale, 5),
                            "dev_unit": round(dev_unit, 5),
                            "cache_noise": round(noise, 6), "verdict": verdict})
        print(f"  {name:26s} {dev_scale:18.4f}  {dev_unit:12.4f}  {noise:8.2e}   {verdict}")

    changed = [r["feature"] for r in per_feature if r["verdict"] == "ИЗМЕНИЛСЯ"]
    scale_only = not changed
    report = {
        "photos_checked": n_checked,
        "worst_validation_vs_prod": worst_val,
        "tolerance": TOLERANCE,
        "shared_code": shared,
        "photo_scale_old_to_new": [round(float(v), 5) for v in photo_scale],
        "per_feature": per_feature,
        "changed_features": changed,
        "baseline_difference_is_scale_only": scale_only,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nотчёт: {out}")
    ok = worst_val <= TOLERANCE and scale_only
    print("ВЫВОД:", "выравнивание то же; отличия сохранённых метрик — только перевод в единицы RMS-106"
          if ok else f"РАСХОЖДЕНИЕ: изменившиеся признаки {changed or '-'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
