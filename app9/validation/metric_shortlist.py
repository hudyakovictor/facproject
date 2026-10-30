#!/usr/bin/env python
"""Полный набор кандидатов метрик для анфаса: снятие -> дедупликация -> ранжирование.

Зачем. Есть четыре источника метрик (боевые 17, «Top-30» других участников, 40
подтверждённых гипотез из analyze_faces.py, 21 метрика нашего MediaPipe-зонда) плюс
наши собственные кандидаты по второй сетке: 85 метрик на `ldm134` (веки, брови, губы —
то, чего в 106 точках просто нет) и 51 крест-метрика «радужка MediaPipe × глазная щель
3DDFA». Всего 253 определения.
Все сторонние числа сняты на невыровненных сетках, поэтому сравнивать их напрямую
нельзя — сравнивать можно только определения. Этот скрипт снимает ВСЕ определения
заново на боевом выравнивании (`aligner.align_identity_mesh` для 3DDFA, roll-правка
по линии глаз + собственная нормировка для MediaPipe) на фронтальных фото put/vas/
udmurt, после чего ранжирует и убирает дубли.

Три стадии (каждая resumable):

    python -m app9.validation.metric_shortlist extract-mp
    python -m app9.validation.metric_shortlist extract-ldm [--shard k/n]
    python -m app9.validation.metric_shortlist score [--n-perm 2000]

Стадия `extract-ldm` — единственная дорогая (3DDFA-реконструкция, ~5с на фото), поэтому
она делится на параллельные шарды (`--shard 0/3`, `1/3`, `2/3`), каждый пишет свой npz,
а `load_values` склеивает все `lmk_{личность}*.npz`. Неудачные реконструкции попадают в
`lmk_*.failed.txt` и больше не перемеряются. Кэш хранит три массива точек (`pts`,
`pts134`, `refs`) в одном каноне RMS-106; файлы старого формата (без `pts134`)
автоматически уводятся в `.pre134` и переснимаются — иначе resume посчитал бы 257 фото
готовыми и новые метрики не появились бы никогда.

Что считается мерой качества метрики:

  eta2        — доля дисперсии признака, объяснённая личностью (однофакторный ANOVA);
  gap_over_mad — min по парам |median_i - median_j| / объединённая MAD внутри
                личности: «насколько личности разведены относительно шума съёмки»;
  auc         — средняя pairwise AUC по парам личностей (несжимаемая ранговая мера);
  *_neutral   — то же на подвыборке нейтральной мимики (пороги EXPR_MAX по blendshapes);
  expr_rho    — корреляция Спирмена с MediaPipe jawOpen+улыбкой. Для 3DDFA-ветки это
                НЕ «метрика о выражении» (сетка identity-only), а утечка мимики в
                alpha_id: большое |rho| значит, что реконструктор подмешивает
                выражение в «форму», и на другой съёмке метрика поедет;
  n           — сколько фото дали конечное значение.

Значимость проверяется перестановочным нулём: метки личностей перемешиваются
`--n-perm` раз, из распределения берётся квантиль 1 - 0.05/N_метрик (Бонферрони). Это
важно, потому что AUC с выбранным по тем же данным знаком оптимистична: на трёх
личностях «ноль» даёт ~0.586, а не 0.5. Формулы таблицы и нуля сверяются обязательно
(`_selfcheck` падает, если они разойдутся).

Дубли снимаются в два хода: |rho| >= DUP_CORR — та же формула, написанная дважды (дубль
уходит из списка), NEAR_CORR <= |rho| < DUP_CORR — другая формула, но неразличимая по
рангам информация (остаётся, помечается мягким дублём).

Дальше метрики раскладываются по тирам: A — значимо по обоим статистикам, не дубль,
держит разделение на нейтральной мимике и не коррелирует с jawOpen; B — значимо, но
фильтр устойчивости не проходит; C — дубль или не значимо. Тир A — это предложение:
окончательный список утверждает владелец, в отчёте для него лежат сырые меры, нули и
флаги (абсолютная / угол / мимика / использует-z).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app9.validation.frontal_17_check import frontal_files  # noqa: E402
# Определения метрик живут в проде (morphing/backend): их показывает интерфейс, и
# держать второй экземпляр формул в валидации означало бы расходиться с боевыми
# значениями при первой же правке. Roll-канон MediaPipe — оттуда же: боевой воркер
# и этот прогон обязаны давать бит-в-бит одни и те же 478 точек.
from morphing.backend import metric_registry as R  # noqa: E402
from morphing.backend.mp_worker import roll_corrected  # noqa: E402

DATA = Path("/Volumes/SDCARD/test_photos")
MP_ASSET = ROOT / "temp/atlas/.cache/models/mediapipe/face_landmarker.task"
STORE = ROOT / ".runtime" / "metric_shortlist"
REPORT_JSON = ROOT / "app9/validation/report/metric_shortlist.json"
REPORT_MD = ROOT / "app9/validation/report/metric_shortlist.md"
IDENTITIES = ("put", "vas", "udmurt")
# Каркасы: `cross` — крест-метрики радужка(MediaPipe) × щель(ldm134). Отдельный каркас,
# а не «3ddfa», потому что дубли ищем внутри одной сетки, а здесь числитель и
# знаменатель из разных. Здесь же — порядок вывода в отчёте.
FRAMEWORKS = ("3ddfa", "mediapipe", "cross")
DUP_CORR = 0.995          # |rho| выше — это та же метрика, просто иначе записанная
NEAR_CORR = 0.95          # |rho| выше — разные формулы, но неотличимая информация
# Пороги предложенного списка (тир A). Это именно пороги предложения: владелец
# список утверждает сам и видит в таблице и сырые меры, и причину отсева.
TIER_A_GATES = {"auc_neutral": 0.80, "eta2_neutral": 0.30, "abs_rho_jawopen": 0.55}
EXPR_MAX = {"jawOpen": 0.12, "mouthSmileLeft": 0.25, "mouthSmileRight": 0.25,
            "browInnerUp": 0.30, "eyeBlinkLeft": 0.35, "eyeBlinkRight": 0.35}


# ── стадия 1: MediaPipe ──────────────────────────────────────────────────────
def extract_mp(per_identity: int, identities: tuple[str, ...] = IDENTITIES, *,
               files_for=frontal_files, store: Path = STORE) -> int:
    """Кэш MediaPipe по `files_for(ident)` в `store`.

    Выборка фото и хранилище — параметры, потому что та же стадия нужна и для
    подфронтальной проверки утверждённого набора (`subfrontal_check.py`), а
    переписывать детектор вторым экземпляром означало бы расхождение в мелочах.
    """
    import cv2
    import mediapipe as mp

    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MP_ASSET),
                                          delegate=mp.tasks.BaseOptions.Delegate.CPU),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=False,
    )
    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
    store.mkdir(parents=True, exist_ok=True)

    for ident in identities:
        files = files_for(ident)
        if per_identity:
            files = files[:per_identity]
        rows_pts, rows_expr, names, bad = [], [], [], []
        started = time.time()
        for path in files:
            img = cv2.imread(str(path))
            if img is None:
                bad.append(path.name)
                continue
            h, w = img.shape[:2]
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            if not res.face_landmarks or len(res.face_landmarks[0]) != 478:
                bad.append(path.name)
                continue
            lm = res.face_landmarks[0]
            pts = np.array([(q.x * w, q.y * h, q.z * w) for q in lm], dtype=np.float32)
            blend = ({s.category_name: float(s.score) for s in res.face_blendshapes[0]}
                     if res.face_blendshapes else {})
            rows_pts.append(roll_corrected(pts))
            rows_expr.append(blend)
            names.append(path.name)
        if not rows_pts:
            print(f"[{ident}] MediaPipe: ни одного лица ({len(bad)} фото), пропускаем")
            continue
        keys = sorted({k for b in rows_expr for k in b})
        np.savez_compressed(
            store / f"mp_{ident}.npz",
            files=np.array(names),
            pts=np.stack(rows_pts).astype(np.float32),
            expr_keys=np.array(keys),
            expr=np.array([[b.get(k, math.nan) for k in keys] for b in rows_expr],
                          dtype=np.float32),
            bad=np.array(bad),
        )
        print(f"[{ident}] MediaPipe: {len(names)} фото, {len(bad)} без лица, "
              f"{time.time() - started:.0f}s", flush=True)
    return 0


# ── стадия 2: 3DDFA (канонические 106 точек) ─────────────────────────────────
def extract_ldm(per_identity: int, identities: tuple[str, ...] = IDENTITIES,
                shard: tuple[int, int] = (0, 1), *,
                files_for=frontal_files, store: Path = STORE) -> int:
    """`shard=(k, n)` — брать n-ю часть фото (индекс % n == k): стадия долгая,
    а процессоров десять, так что прогон делится на параллельные шарды. Каждый
    шард пишет свой файл, `load_values` их потом склеивает.

    Кроме 106 канонических точек сохраняются `pts134` (134 точки той же сетки в том же
    каноне RMS-106) и `refs` (9 вершин-базисов: скулы, передняя поверхность щёк,
    колонки фильтрума, глабелла, губоподбородочная борозда, погонион). Оба — срез той
    же `v_aligned`, поэтому боевая нормировка на них распространяется автоматически, а
    переснимать реконструкцию второй раз не нужно.

    `files_for`/`store` — как в `extract_mp`: та же стадия на другой выборке фото.
    """
    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh

    k, n = shard
    store.mkdir(parents=True, exist_ok=True)
    for ident in identities:
        suffix = "" if n == 1 else f".shard{k}of{n}"
        out_path = store / f"lmk_{ident}{suffix}.npz"
        fail_path = store / f"lmk_{ident}{suffix}.failed.txt"
        done: dict[str, np.ndarray] = {}
        done134: dict[str, np.ndarray] = {}
        done_refs: dict[str, np.ndarray] = {}
        expr: dict[str, float] = {}
        if out_path.exists():
            z = np.load(out_path)
            if "pts134" not in z.files or "refs" not in z.files:
                # Старый кэш без 134-ветки: убираем в .pre134 и снимаем заново. Иначе
                # resume молча посчитал бы все 257 фото «готовыми» и новых метрик не
                # появилось бы вообще.
                stale = out_path.with_suffix(out_path.suffix + ".pre134")
                out_path.rename(stale)
                print(f"[{ident}{suffix}] кэш без pts134 → {stale.name}, снимаем заново",
                      flush=True)
            else:
                for name, pts, pts134, refs, emag in zip(
                        z["files"], z["pts"], z["pts134"], z["refs"], z["expr_mag"], strict=True):
                    done[str(name)] = np.asarray(pts, dtype=np.float32)
                    done134[str(name)] = np.asarray(pts134, dtype=np.float32)
                    done_refs[str(name)] = np.asarray(refs, dtype=np.float32)
                    expr[str(name)] = float(emag)
        # Неудачные реконструкции помечаем в файл, чтобы повторный запуск не тратил
        # на них минуту на фото; список честно попадает в отчёт как покрытие.
        failed = set(fail_path.read_text(encoding="utf-8").split()) if fail_path.exists() else set()
        files = [p for i, p in enumerate(files_for(ident)) if i % n == k]
        if per_identity:
            files = files[:per_identity]
        todo = [p for p in files if p.name not in done and p.name not in failed]
        print(f"[{ident}{suffix}] 3DDFA: готово {len(done)}, забито {len(failed)}, "
              f"осталось {len(todo)}", flush=True)
        started = time.time()
        for i, path in enumerate(todo, 1):
            try:
                recon = reconstruct_image(path, device="cpu")
            except Exception as exc:  # noqa: BLE001 — реконструкция падает по-разному
                print(f"  FAIL {path.name}: {type(exc).__name__} {exc}", flush=True)
                failed.add(path.name)
                _append_failed(fail_path, path.name)
                continue
            if recon is None:
                print(f"  FAIL {path.name}: лицо не реконструировано", flush=True)
                failed.add(path.name)
                _append_failed(fail_path, path.name)
                continue
            v_aligned, pts, _scale = align_identity_mesh(recon)
            if pts is None or pts.shape != (106, 3):
                failed.add(path.name)
                _append_failed(fail_path, path.name)
                continue
            # Срез той же нормированной сетки: те же центр и RMS по 106 точкам, поэтому
            # 134 и базисы живут в тех же единицах, что и 106 (паритет с продом проверен
            # на 106 — сюда он переносится без дополнительного контроля).
            pts134 = v_aligned[np.asarray(recon["ldm134_indices"], dtype=np.int64)]
            refs = v_aligned[list(R.ANAT_VERTS)]
            if pts134.shape != (134, 3) or refs.shape != (9, 3):
                failed.add(path.name)
                _append_failed(fail_path, path.name)
                continue
            done[path.name] = np.asarray(pts, dtype=np.float32)
            done134[path.name] = np.asarray(pts134, dtype=np.float32)
            done_refs[path.name] = np.asarray(refs, dtype=np.float32)
            # Норма alpha_exp — сколько мимики было в кадре; нужно, чтобы проверить
            # утечку выражения в «форму» (identity-сетка от мимики независима by design).
            expr[path.name] = float(np.linalg.norm(recon["alpha_exp"]))
            if i % 10 == 0:  # периодический сброс: перезапуск не теряет работу
                _save_ldm(out_path, done, done134, done_refs, expr)
                rate = (time.time() - started) / i
                eta = rate * (len(todo) - i)
                print(f"  {i}/{len(todo)} сохранено, {rate:.0f}s/фото, "
                      f"осталось ~{eta / 60:.0f} мин", flush=True)
        _save_ldm(out_path, done, done134, done_refs, expr)
        print(f"[{ident}{suffix}] 3DDFA: сохранено {len(done)} "
              f"за {time.time() - started:.0f}s", flush=True)
    return 0


def _append_failed(fail_path: Path, name: str) -> None:
    with fail_path.open("a", encoding="utf-8") as fh:
        fh.write(name + "\n")


def _save_ldm(out_path: Path, done: dict[str, np.ndarray],
              done134: dict[str, np.ndarray], done_refs: dict[str, np.ndarray],
              expr: dict[str, float]) -> None:
    # Порядок строк один для всех трёх массивов — по имени фото. Если у какого-то
    # имени нет пары в 134- или refs-словаре, фото выбрасываем целиком: разъехавшиеся
    # строки в npz дали бы метрикам чужие точки, и это не поймать никаким NaN.
    names = sorted(set(done) & set(done134) & set(done_refs))
    np.savez_compressed(
        out_path,
        files=np.array(names),
        pts=np.stack([done[n] for n in names]).astype(np.float32),
        pts134=np.stack([done134[n] for n in names]).astype(np.float32),
        refs=np.stack([done_refs[n] for n in names]).astype(np.float32),
        expr_mag=np.array([expr.get(n, math.nan) for n in names], dtype=np.float32),
    )


# ── стадия 3: значения, дедупликация, ранжирование ───────────────────────────
def load_values(store: Path = STORE) -> tuple[dict[str, list[str]],
                                              dict[str, dict[str, np.ndarray]],
                                              dict[str, dict[str, np.ndarray]]]:
    """(rows, values, expr) по личностям из кэша `store`.

    rows[ident]  — имена фото (общий порядок для всех колонок);
    values[ident][metric] — (len(rows),) значения, NaN там, где метрика не посчиталась
        или соответствующего каркаса в кэше нет;
    expr[ident][key] — jawOpen / smile / alpha_exp / expr_ok по тем же фото.

    Фото берётся ОБЪЕДИНЕНИЕм двух кэшей: если 3DDFA ещё не доснято, MediaPipe-ветка
    считается уже сейчас, и наоборот. Пропущенные точки дают NaN, а не выдуманное 0.
    """
    rows: dict[str, list[str]] = {}
    values: dict[str, dict[str, np.ndarray]] = {}
    expr: dict[str, dict[str, np.ndarray]] = {}

    for ident in IDENTITIES:
        mp_file = store / f"mp_{ident}.npz"
        mp_z = np.load(mp_file) if mp_file.exists() else None
        mp_pts: dict[str, np.ndarray] = {}
        mp_expr: dict[str, dict[str, float]] = {}
        if mp_z is not None:
            keys = [str(k) for k in mp_z["expr_keys"]]
            mp_pts = {str(n): p for n, p in zip(mp_z["files"], mp_z["pts"], strict=True)}
            mp_expr = {str(n): dict(zip(keys, row.tolist(), strict=True))
                       for n, row in zip(mp_z["files"], mp_z["expr"], strict=True)}
        lmk: dict[str, np.ndarray] = {}
        lmk134: dict[str, np.ndarray] = {}
        lmk_refs: dict[str, np.ndarray] = {}
        lmk_exp: dict[str, float] = {}
        # Стадия extract-ldm пишет по файлу на шард — склеиваем все, что есть.
        for part in sorted(store.glob(f"lmk_{ident}*.npz")):
            z = np.load(part)
            # Файлы старого формата (снятые до 134-ветки) не подмешиваем: без pts134
            # фото дало бы NaN-колонку и видимость, что 134-метрики «не сработали».
            if "pts134" not in z.files or "refs" not in z.files:
                print(f"  пропуск {part.name}: кэш без pts134 (переснять стадию)")
                continue
            for name, pts, pts134, refs, emag in zip(
                    z["files"], z["pts"], z["pts134"], z["refs"], z["expr_mag"], strict=True):
                lmk[str(name)] = np.asarray(pts, dtype=np.float32)
                lmk134[str(name)] = np.asarray(pts134, dtype=np.float32)
                lmk_refs[str(name)] = np.asarray(refs, dtype=np.float32)
                lmk_exp[str(name)] = float(emag)
        if not mp_pts and not lmk:
            continue

        names = sorted(set(mp_pts) | set(lmk))
        per_photo: list[dict[str, float]] = []
        ecols: dict[str, list[float]] = {k: [] for k in ("jawOpen", "smile", "alpha_exp", "expr_ok")}
        for name in names:
            pts, q = mp_pts.get(name), lmk.get(name)
            if pts is not None:
                xy = pts[:, :2] - pts[:, :2].mean(0)
                scale = float(np.sqrt((xy ** 2).sum(1).mean())) or 1.0
            else:
                scale = 1.0
            per_photo.append(R.compute_all(q, pts, scale, q134=lmk134.get(name),
                                           refs=lmk_refs.get(name)))
            blend = mp_expr.get(name, {})
            ecols["jawOpen"].append(blend.get("jawOpen", math.nan))
            smiles = [blend.get("mouthSmileLeft", math.nan), blend.get("mouthSmileRight", math.nan)]
            ecols["smile"].append(max(smiles) if any(s == s for s in smiles) else math.nan)
            ecols["alpha_exp"].append(lmk_exp.get(name, math.nan))
            ecols["expr_ok"].append(
                1.0 if not blend or all(blend.get(k, 0.0) <= thr for k, thr in EXPR_MAX.items())
                else 0.0)
        # Колонки собираем по объединению ключей: у фото без MediaPipe-кэса 134- и
        # MP-метрики отсутствуют, и «отсутствует» = NaN, а не сдвиг всей колонки.
        cols: dict[str, np.ndarray] = {
            k: np.array([d.get(k, math.nan) for d in per_photo], dtype=float)
            for k in sorted({key for d in per_photo for key in d})}
        for k, arr in cols.items():
            cols[k] = np.where(np.isfinite(arr), arr, np.nan)
        rows[ident] = names
        values[ident] = cols
        expr[ident] = {k: np.asarray(v, dtype=float) for k, v in ecols.items()}
    return rows, values, expr


def eta2(groups: list[np.ndarray]) -> float:
    """Доля межличностной дисперсии (однофакторная ANOVA по личностям)."""
    keep = [g[np.isfinite(g)] for g in groups]
    keep = [g for g in keep if g.size >= 3]
    if len(keep) < 2:
        return float("nan")
    allv = np.concatenate(keep)
    grand = allv.mean()
    ss_b = sum(g.size * (g.mean() - grand) ** 2 for g in keep)
    ss_t = float(((allv - grand) ** 2).sum())
    return float(ss_b / ss_t) if ss_t > 1e-12 else float("nan")


def mad(v: np.ndarray) -> float:
    v = v[np.isfinite(v)]
    if v.size < 3:
        return float("nan")
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


def gap_over_mad(groups: list[np.ndarray]) -> float:
    meds = [np.nanmedian(g) for g in groups if np.isfinite(g).sum() >= 3]
    if len(meds) < 2:
        return float("nan")
    gaps = [abs(meds[i] - meds[j]) for i in range(len(meds)) for j in range(i + 1, len(meds))]
    mads = [m for m in (mad(g) for g in groups) if m == m and m > 1e-12]
    if not mads:
        return float("nan")
    return float(min(gaps) / float(np.mean(mads)))


def pair_auc(groups: list[np.ndarray]) -> float:
    """Средняя pairwise AUC: вероятность, что метрика правильно разберёт пару личностей."""
    keep = [g for g in groups if np.isfinite(g).sum() >= 5]
    if len(keep) < 2:
        return float("nan")
    aucs = []
    for i in range(len(keep)):
        for j in range(i + 1, len(keep)):
            a, b = keep[i][np.isfinite(keep[i])], keep[j][np.isfinite(keep[j])]
            wins = sum((1.0 if x > y else 0.5 if x == y else 0.0) for x in a for y in b)
            best = max(wins, a.size * b.size - wins)  # ориентацию знака выбираем сами
            aucs.append(best / (a.size * b.size))
    return float(np.mean(aucs)) if aucs else float("nan")


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 8:
        return float("nan")
    rx = np.argsort(np.argsort(x[m])).astype(float)
    ry = np.argsort(np.argsort(y[m])).astype(float)
    if rx.std() < 1e-9 or ry.std() < 1e-9:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def rank_correlation(a: np.ndarray, b: np.ndarray) -> float:
    """|rho| по совпадающим непустым фото — для поиска дублей."""
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 10:
        return float("nan")
    return abs(spearman(a[m], b[m]))


def make_label_perms(labels: np.ndarray, n_perm: int, seed: int = 20261027) -> np.ndarray:
    """Один и тот же набор перестановок меток для всех метрик — чтобы нули были сопоставимы."""
    rng = np.random.default_rng(seed)
    return np.stack([rng.permutation(labels) for _ in range(n_perm)]).astype(np.int16)


def permutation_stats(col: np.ndarray, labels: np.ndarray, perms: np.ndarray,
                      bonferroni_q: float) -> dict[str, Any]:
    """Наблюдаемое разделение против того же на перемешанных личностях.

    Смысл: у нас три личности и 257 фото, поэтому «AUC = 0.78» само по себе ничего
    не значит — на шумных данных та же формула даёт ровно столько же. Ноль считается
    перестановкой меток: значения метрики те же, личности перетасованы.

    AUC пары считается как статистика Манна—Уитни по ПОЗИЦИЯМ в общем порядке
    возрастания: для каждого элемента группы i считаем, сколько элементов группы j
    лежит ниже. Это ровно то, что перебирает `pair_auc`, но за O(n) на пару вместо
    O(n_i*n_j), и берётся сразу по всем перестановкам матрицей. Ранговые суммы по
    ВСЕМ трём группам тут не годятся: из них попарные U не восстанавливаются
    (три уравнения с точностью до одного параметра).
    """
    m = np.isfinite(col)
    v, lab = col[m], labels[m]
    present = sorted(set(lab.tolist()))
    nan_out = {"eta2_null_p95": None, "auc_null_p95": None, "eta2_above_bonf": None,
               "auc_above_bonf": None, "perm_checked": False}
    if v.size < 12 or len(present) < 2 or any((lab == k).sum() < 3 for k in present):
        return nan_out
    counts = np.asarray([(lab == k).sum() for k in present], dtype=float)
    grand = float(v.mean())
    ss_t = float(((v - grand) ** 2).sum())
    if ss_t <= 1e-12:
        return nan_out
    if np.unique(v).size != v.size:
        # Нулевая AUC по позициям не различает связки; на связных метрике ноль
        # был бы смещён, поэтому честно оставляем её без оценки значимости.
        return nan_out
    pairs = [(i, j) for i in range(len(present)) for j in range(i + 1, len(present))]
    order = np.argsort(v, kind="stable")          # позиции в порядке возрастания

    def eta(assign: np.ndarray) -> np.ndarray:
        means = np.stack([((assign == k) * v).sum(axis=1) for k in range(len(present))],
                         axis=1) / counts
        return (counts * (means - grand) ** 2).sum(axis=1) / ss_t

    def auc(assign_sorted: np.ndarray) -> np.ndarray:
        out = []
        for i, j in pairs:
            mi = assign_sorted == i
            mj = assign_sorted == j
            below = np.cumsum(mj, axis=1) - mj    # строго ниже i-го элемента
            u = (below * mi).sum(axis=1).astype(float)
            a = u / (counts[i] * counts[j])
            out.append(np.maximum(a, 1.0 - a))
        return np.mean(np.stack(out, axis=1), axis=1)

    obs = lab[None, :]
    eta_obs = float(eta(obs)[0])
    auc_obs = float(auc(lab[order][None, :])[0])
    ps = perms[:, m]
    null_eta, null_auc = eta(ps), auc(ps[:, order])
    return {
        "eta2_null_p95": round(float(np.quantile(null_eta, 0.95)), 4),
        "auc_null_p95": round(float(np.quantile(null_auc, 0.95)), 4),
        "eta2_above_bonf": bool(eta_obs > float(np.quantile(null_eta, bonferroni_q))),
        "auc_above_bonf": bool(auc_obs > float(np.quantile(null_auc, bonferroni_q))),
        # сверка, что статистика в нуле и в таблице — одна и та же формула
        "perm_eta2_obs": round(eta_obs, 4),
        "perm_auc_obs": round(auc_obs, 4),
        "perm_checked": True,
    }


def score(min_n: int, n_perm: int = 0) -> int:
    rows, values, expr = load_values()
    if not values:
        print(f"нет данных в {STORE} — сначала прогнать extract-mp и/или extract-ldm")
        return 1
    idents = [i for i in IDENTITIES if i in values]
    labels = np.concatenate([np.full(len(rows[i]), k, dtype=int) for k, i in enumerate(idents)])
    jaw = np.concatenate([expr[i]["jawOpen"] for i in idents])
    smile = np.concatenate([expr[i]["smile"] for i in idents])
    neutral = np.concatenate([expr[i]["expr_ok"] for i in idents]) == 1.0
    metrics = sorted({m for i in idents for m in values[i]})
    # Перестановочный ноль: одна и та же перетасовка меток для всех метрик, чтобы
    # «AUC=0.78» было с чем сравнить. Порог значимости — квантиль 1 - 0.05/N
    # (Бонферрони по числу метрик), иначе из двухсот кандидатов «значимыми» окажутся ~10.
    perms = (make_label_perms(labels, n_perm) if n_perm > 0
             else np.empty((0, labels.size), dtype=np.int16))
    bonferroni_q = 1.0 - 0.05 / len(metrics)
    print(f"метрик в наборе: {len(metrics)} · фото: "
          + ", ".join(f"{i}={len(rows[i])}" for i in idents)
          + f" · нейтральных по мимике: {int(neutral.sum())}/{neutral.size}"
          + (f" · перестановок: {n_perm}" if n_perm else " · без перестановочного нуля"))

    series: dict[str, np.ndarray] = {}
    table: list[dict[str, Any]] = []
    for metric in metrics:
        col = np.concatenate([
            values[i].get(metric, np.full(len(rows[i]), np.nan)) for i in idents
        ])
        series[metric] = col
        groups = [col[labels == k] for k in range(len(idents))]
        groups_neutral = [col[(labels == k) & neutral] for k in range(len(idents))]
        n_ok = int(np.isfinite(col).sum())
        if n_ok < min_n:
            continue
        row = {
            "metric": metric,
            **R.meta(metric),
            "n": n_ok,
            "eta2": _r(eta2(groups)),
            "gap_over_mad": _r(gap_over_mad(groups)),
            "auc": _r(pair_auc(groups)),
            # то же на подвыборке «нейтральное выражение»: метрика, которая держит
            # разделение только за счёт гримасы, здесь проседает — это видно сразу
            "eta2_neutral": _r(eta2(groups_neutral)),
            "auc_neutral": _r(pair_auc(groups_neutral)),
            "rho_jawopen": _r(spearman(col, jaw)),
            "rho_smile": _r(spearman(col, smile)),
            "duplicate_of": None,
            "near_duplicate_of": None,
        }
        if perms.shape[0]:
            row.update(permutation_stats(col, labels, perms, bonferroni_q))
        table.append(row)

    _dedupe(table, series)
    table.sort(key=lambda r: (-(r["eta2"] or 0), -(r["auc"] or 0)))
    _assign_tiers(table)
    _selfcheck(table)
    unique = [r for r in table if not r["duplicate_of"]]
    deduped = [r for r in table if not r["duplicate_of"] and not r["near_duplicate_of"]]
    tier_a = [r for r in table if r["tier"] == "A"]
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps({
        "photos": {i: len(rows[i]) for i in idents},
        "neutral_share": _r(float(neutral.mean())),
        "n_metrics": len(table),
        "n_unique": len(unique),
        "n_after_near_dedup": len(deduped),
        "n_perm": int(perms.shape[0]),
        "bonferroni_q": round(bonferroni_q, 8),
        "auc_null_p95_range": _r_range([r.get("auc_null_p95") for r in table]),
        "eta2_null_p95_range": _r_range([r.get("eta2_null_p95") for r in table]),
        "gates": {**TIER_A_GATES, "near_corr": NEAR_CORR, "dup_corr": DUP_CORR},
        "tier_a": [r["metric"] for r in tier_a],
        "metrics": table,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(table, {i: len(rows[i]) for i in idents}, int(neutral.sum()),
              int(neutral.size), len(perms), len(deduped))
    print(f"\nотчёты: {REPORT_JSON}\n        {REPORT_MD}")
    print(f"воронка: {len(table)} кандидатов -> {len(unique)} без строгих дублей -> "
          f"{len(deduped)} без мягких -> {len(tier_a)} в предложенном списке (тир A)")
    for framework in FRAMEWORKS:
        names = [r["metric"] for r in tier_a if r["framework"] == framework]
        print(f"\nтир A · {framework} ({len(names)}):")
        for name in names:
            print(f"    {name}")
    print("\nтоп-15 по eta2:")
    for row in table[:15]:
        tag = row["tier"] + (" ДУБЛЬ " + row["duplicate_of"] if row["duplicate_of"] else "")
        print(f"  eta2={row['eta2']} auc={row['auc']} gap/MAD={row['gap_over_mad']} "
              f"n={row['n']} {row['framework']:9s} {row['metric']:44s} {tag}")
    return 0


def _assign_tiers(table: list[dict[str, Any]]) -> None:
    """Предложение владельцу, не решение: тир A — проходит все фильтры разом.

    A — значимо на перестановочном нуле с поправкой Бонферрони, не дубль, держит
        разделение на нейтральной по мимике подвыборке и не коррелирует с jawOpen;
    B — значимо и не дубль, но один из фильтров устойчивости не проходит;
    C — дубли (строгие или мягкие) либо не значимо.
    """
    for row in table:
        if row["duplicate_of"] or row["near_duplicate_of"]:
            row["tier"] = "C"
            continue
        robust = (
            (row["auc_neutral"] or 0.0) >= TIER_A_GATES["auc_neutral"]
            and (row["eta2_neutral"] or 0.0) >= TIER_A_GATES["eta2_neutral"]
            and abs(row["rho_jawopen"] or 1.0) <= TIER_A_GATES["abs_rho_jawopen"]
        )
        significant = bool(row.get("auc_above_bonf")) and bool(row.get("eta2_above_bonf"))
        row["tier"] = "A" if significant and robust else ("B" if significant else "C")


def _r(v: float | None) -> float | None:
    return None if v is None or v != v else round(float(v), 4)


def _r_range(values: list[float | None]) -> list[float | None]:
    """[min, max] по непустым — чтобы уровень нуля был виден одной строкой."""
    got = [float(v) for v in values if v is not None]
    return [round(min(got), 4), round(max(got), 4)] if got else [None, None]


def _selfcheck(table: list[dict[str, Any]]) -> None:
    """Нулевая статистика обязана считаться той же формулой, что и колонки таблицы.

    Если `pair_auc`/`eta2` и перестановочный код разойдутся, значимость станет
    фигурой речи, а не проверкой. Сверка дешёвая, поэтому обязательная.
    """
    for row in table:
        if not row.get("perm_checked"):
            continue
        for a, b in (("auc", "perm_auc_obs"), ("eta2", "perm_eta2_obs")):
            if row[a] is None:
                continue
            if abs(float(row[a]) - float(row[b])) > 1e-3:
                raise RuntimeError(
                    f"{row['metric']}: {a}={row[a]} не совпало с перестановочной "
                    f"формулой {row[b]} — статистики в таблице и в нуле разные"
                )


def _flags(r: dict[str, Any]) -> str:
    """Человеческие флаги метрики: на них смотрит утверждающий список."""
    return " ".join(f for f, on in (
        ("абсолютная", r["kind"] == "absolute"),
        ("угол", r["kind"] == "angle"),
        ("мимика", r["expression_sensitive"]),
        ("использует-z", r["uses_z"]),
    ) if on)


def _dedupe(table: list[dict[str, Any]], series: dict[str, np.ndarray]) -> None:
    """Дубли ищем по значениям, а не по названиям: одна формула в двух скриптах.

    Жадно: идём по убыванию eta2 и сравниваем с уже оставленными. |rho| >= DUP_CORR —
    это буквально та же метрика, записанная дважды (дубль снимается из списка);
    NEAR_CORR <= |rho| < DUP_CORR — разные формулы, но неразличимая по рангам
    информация: метрика остаётся в наборе, помечается как «мягкий дубль», чтобы
    утверждающий список не раздувался копиями одного признака.

    Сравниваем только внутри одного каркаса — 3DDFA и MediaPipe физически мерят
    разные сетки, и совпадение рангов между ними случайностью не считается. Крест-
    ветка (`cross`) — третий каркас: свои определения, свой круг дублей. Оговорка:
    крест-метрики используют те же точки щели, что и 134-ветка, поэтому «строгий
    дубль» крест-метрики и 134-метрики такой фильтра не увидит — он и не дубль,
    потому что числитель (радужка) у крест-ветки свой.
    """
    order = sorted(table, key=lambda r: -(r["eta2"] or 0.0))
    for framework in FRAMEWORKS:
        kept: list[tuple[str, np.ndarray]] = []
        for row in [r for r in order if r["framework"] == framework]:
            col = series[row["metric"]]
            best_rho, best_name = 0.0, None
            for name, ref in kept:
                rho = rank_correlation(col, ref)
                if rho == rho and rho > best_rho:
                    best_rho, best_name = rho, name
            if best_name is not None and best_rho >= DUP_CORR:
                row["duplicate_of"] = f"{best_name} (rho={best_rho:.3f})"
                continue
            if best_name is not None and best_rho >= NEAR_CORR:
                row["near_duplicate_of"] = f"{best_name} (rho={best_rho:.3f})"
            kept.append((row["metric"], col))


def _write_md(table: list[dict[str, Any]], photos: dict[str, int], neutral_n: int,
              neutral_total: int, n_perm: int, deduped_n: int) -> None:
    tier_a = [r for r in table if r["tier"] == "A"]
    n_dup = sum(1 for r in table if r["duplicate_of"])
    n_near = sum(1 for r in table if r["near_duplicate_of"])
    gates = ", ".join(f"{k} {v}" for k, v in TIER_A_GATES.items())

    out: list[str] = [
        "# Полный набор метрик анфаса: ранжирование и предложенный список\n\n",
        "Метрики сняты заново на БОЕВОМ выравнивании: 3DDFA — `aligner.align_identity_mesh` "
        "(identity-сетка без мимики, центр и масштаб по RMS 106 ландмарк, "
        "`identity_object_space_rms106_v2`; той же нормированной сеткой срезаются "
        "`pts134` и 9 анатомических вершин-базисов), MediaPipe — roll-правка по линии "
        "внешних уголков глаз и собственная нормировка. Определения взяты из "
        "`metric_registry.py`: боевые 17, «Top-30» и гипотезы других участников, наш "
        "MediaPipe-зонд, наши же кандидаты по второй сетке ldm134 (глаза, брови, губы) "
        "и крест-ветка «радужка MediaPipe × глазная щель 3DDFA». Числа чужих скриптов не "
        "использовались — они меряли невыровненные сетки.\n\n",
        f"Покрытие: {sum(photos.values())} фронтальных фото "
        + ", ".join(f"{k}={v}" for k, v in photos.items()) + "; "
        f"нейтральных по мимике {neutral_n}/{neutral_total}. "
        f"Воронка: {len(table)} кандидатов -> {len(table) - n_dup} без строгих дублей -> "
        f"{deduped_n} без строгих и мягких (|rho| >= {NEAR_CORR}, таких пар {n_near}) -> "
        f"тир A ниже. "
        f"Перестановочный ноль: {n_perm} перетасовок меток, порог значимости — "
        "квантиль 1 - 0.05/N по числу метрик.\n\n",
        "Как читать меры:\n\n",
        "* `eta2` — доля дисперсии признака, объяснённая личностью (ANOVA по трём лицам);\n",
        "* `AUC` — средняя по парам личностей вероятность, что метрика разберёт пару "
        "(знак ориентации выбирается по данным, поэтому AUC оптимистична — отсюда "
        "`AUC_ноль`: то же на перемешанных личностях);\n",
        "* `gap/MAD` — минимальный зазор между медианами личностей в единицах "
        "внутриличностного разброса: это про «разведённость на съёмке», а не про красоту "
        "разделения;\n",
        "* `*_нейтр` — то же только на фото с нейтральной мимикой: метрика, держащая "
        "разделение за счёт гримасы, здесь проседает;\n",
        "* `rho jawOpen` — корреляция с открытием рта по MediaPipe. Для 3DDFA-ветки это "
        "тест на утечку: сетка identity-only по построению, так что ненулевая корреляция "
        "означает, что альфа_id вбирает выражение и метрика поедет на другой съёмке;\n",
        "* флаги: `абсолютная` — величина зависит от нормировки (у нас RMS-106, но при "
        "смене нормировки сломается), `угол` — градусы, `мимика` — определение заведомо "
        "про выражение лица, `использует-z` — у MediaPipe-метрики есть координата z в "
        "пиксельных единицах, она масштабируется отдельно и надёжностью не блещет.\n\n",
        "## Предложенный список (тир A) — на утверждение владельцу\n\n",
        f"Пороги: {gates}, плюс значимость по Бонферрони и отсутствие дублей. "
        "Это предложение, а не решение: список утверждает владелец.\n\n",
        "| каркас | метрика | eta2 | AUC | AUC_ноль | eta2 нейтр | AUC нейтр | gap/MAD | "
        "rho jawOpen | флаги | источник |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n",
    ]
    for framework in FRAMEWORKS:
        for r in [x for x in tier_a if x["framework"] == framework]:
            out.append(
                f"| {framework} | `{r['metric']}` | {r['eta2']} | {r['auc']} | "
                f"{r.get('auc_null_p95', '—')} | {r['eta2_neutral']} | {r['auc_neutral']} | "
                f"{r['gap_over_mad']} | {r['rho_jawopen']} | {_flags(r) or '—'} | "
                f"{r['source']} |\n"
            )
    out.append(f"\nИтого тир A: {len(tier_a)} "
               + ", ".join(f"{fw} {sum(1 for r in tier_a if r['framework'] == fw)}"
                           for fw in FRAMEWORKS)
               + f". Тир B (значимо, но устойчивость не проходит): "
               f"{sum(1 for r in table if r['tier'] == 'B')}.\n\n")

    # Разложение предложенного списка по риску. Значимость и отсутствие дублей ещё
    # не означают, что метрику можно класть в прод: часть определений мерит мимику
    # (глаза, губы), часть зависит от z MediaPipe в пиксельных единицах. Утверждающему
    # удобно сначала взять «чистый костяк», а флаганные добавлять осознанно.
    clean = [r for r in tier_a if not _flags(r) or _flags(r) == "угол"]
    risky_expr = [r for r in tier_a if "мимика" in _flags(r)]
    risky_z = [r for r in tier_a if "z" in _flags(r) or "абсолютная" in _flags(r)]
    clean_names = ", ".join("`" + r["metric"] + "`" for r in clean)
    out.append(
        f"Разложение по риску: без флагов (или только `угол`) — {len(clean)} "
        f"({clean_names}); "
        f"определение про выражение (глаза/губы) — {len(risky_expr)}; "
        f"зависит от z MediaPipe или от нормировки (абсолютная) — {len(risky_z)}.\n\n"
    )

    # Что меряет каждая метрика из предложенного списка: список утверждает человек,
    # и по одному названию формулу не восстановить. Описания живут в metric_registry.
    out.append("### Что меряют метрики тира A\n\n")
    for r in tier_a:
        text = R.describe(r["metric"])
        if text:
            out.append(f"* `{r['metric']}` ({r['framework']}) — {text};\n")
    out.append("\n")

    # Итог по группам: вопрос владельца формулируется как «что из надуманного
    # подтвердилось», а это свойство группы определений, а не отдельной формулы. Для
    # новых групп (134 и крест) тут видно, сколько кандидатов умерло значимыми, но
    # дублями, а сколько — просто не поднялось над шумом съёмки.
    groups = R.metric_groups()
    new_groups = ("ldm134_eyes", "ldm134_brows", "ldm134_lips", "cross_iris_fissure")
    out.append("### Подтвердилось ли по группам кандидатов\n\n")
    out.append("| группа | кандидатов | тир A | тир B | строгий дубль | мягкий дубль | "
               "не значимо | лучший по eta2 (нейтр) |\n"
               "|---|---|---|---|---|---|---|---|\n")
    for group in tuple(dict.fromkeys(groups[r["metric"]] for r in table)):
        rs = [r for r in table if groups[r["metric"]] == group]
        nsig = sum(1 for r in rs if r.get("perm_checked")
                   and not (r.get("eta2_above_bonf") and r.get("auc_above_bonf")))
        best = max((r for r in rs if r["eta2_neutral"] is not None),
                   key=lambda r: r["eta2_neutral"], default=None)
        mark = " **(новая)**" if group in new_groups else ""
        out.append(
            f"| `{group}`{mark} | {len(rs)} "
            f"| {sum(1 for r in rs if r['tier'] == 'A')} "
            f"| {sum(1 for r in rs if r['tier'] == 'B')} "
            f"| {sum(1 for r in rs if r['duplicate_of'])} "
            f"| {sum(1 for r in rs if r['near_duplicate_of'] and not r['duplicate_of'])} "
            f"| {nsig} "
            f"| {('`' + best['metric'] + '` ' + str(best['eta2_neutral'])) if best else '—'} |\n"
        )
    out.append("\n")

    # Где сидят боевые 17 признаков: это вход для решения «заменять ли набор».
    # Ранг считается по eta2 среди метрик без строгого дубля — так же, как построен
    # список, поэтому позиция сравнима с предложенным списком напрямую.
    prod_src = R.SOURCES["form17"]
    kept = [r for r in table if not r["duplicate_of"]]
    pos = {r["metric"]: i + 1 for i, r in enumerate(kept)}
    prod_rows = sorted((r for r in table if r["source"] == prod_src),
                       key=lambda r: pos.get(r["metric"], 10 ** 3))
    out.append("### Где оказались боевые 17 признаков\n\n")
    out.append("| метрика | ранг (без строгих дублей) | тир | eta2 | AUC нейтр | флаги | "
               "пометка |\n|---|---|---|---|---|---|---|\n")
    for r in prod_rows:
        note = r["duplicate_of"] or (
            f"мягкий дубль: {r['near_duplicate_of']}" if r["near_duplicate_of"] else "")
        out.append(
            f"| `{r['metric']}` | {pos.get(r['metric'], '—')} | {r.get('tier', '')} | "
            f"{r['eta2']} | {r['auc_neutral']} | {_flags(r) or '—'} | {note} |\n"
        )
    best_prod = prod_rows[0] if prod_rows else None
    n_a = sum(1 for r in prod_rows if r.get("tier") == "A")
    tail = [r for r in prod_rows if r["eta2"] is not None and r["eta2"] < 0.15]
    if best_prod:
        why_c = ("тир C из-за мягкого дубля, а не из-за силы"
                 if best_prod.get("tier") == "C" and best_prod["near_duplicate_of"]
                 else f"тир {best_prod.get('tier')}")
        out.append(
            f"\nЛучший из боевых — `{best_prod['metric']}` (ранг "
            f"{pos.get(best_prod['metric'])}, {why_c}); в тир A из "
            f"боевых попало {n_a}. {len(tail)} из 17 дают eta2 < 0.15: формально это "
            "значимо, но по величине эффекта вчетверо слабее лидеров списка. Ровно это "
            "и имеет в виду ревьюер: слабое место — набор метрик, а не алгоритм "
            "сравнения.\n\n"
        )
    out.append("## Ограничения, которые надо помнить при утверждении\n\n"
               "* Личностей три. Метрика, хорошо разделяющая put/vas/udmurt, обязана "
               "разделять и четвёртого человека — это проверяется только на новой съёмке "
               "(пункт 10 плана: вторая сессия).\n"
               "* Знак ориентации в AUC выбирается по этим же данным, поэтому смотреть "
               "надо на `AUC_ноль` и тир, а не на голое число.\n"
               "* Внутриличностный шум здесь — разброс фото одного человека в одном бине; "
               "если съёмка станет другой (свет, расстояние), `gap/MAD` просядет.\n"
               "* 3DDFA-метрики зависят от качества реконструкции: на анфасе оно "
               "приемлемо, на подфронте — часть признаков уйдёт в негодность, и список "
               "для подфронтального ракурса надо утверждать отдельно по тем же фото.\n"
               "* В проде MediaPipe нет: боевой путь — 3DDFA (`reconstruct_image` -> "
               "`aligner.align_identity_mesh`). MediaPipe-метрики из списка требуют "
               "нового экстрактора в `morphing/backend` (478 точек + blendshapes) и "
               "хранения его сетки рядом с вектором формы. Если это нежелательно, "
               "список утверждается только по 3DDFA-ветке.\n"
               "* Крест-метрики (`cross_*`) требуют ОБА каркаса одновременно и смешивают "
               "2D-пиксельную мерку MediaPipe с 3D-меркой сетки: общая нормировка по IPD "
               "делает отношение законным, но систематический сдвиг от разкалибровки двух "
               "моделей (MP стабильно видит щель шире, чем 3DMM: "
               "`cross_aperture_height_agreement` ~1.1–1.2 у всех троих) остаётся в каждой "
               "величине. На новую съёмку они переносятся только вместе с проверкой этого "
               "сдвига, поэтому в проде для них нужен тот же MP-экстрактор, что и для "
               "MediaPipe-ветки.\n\n"
               f"## Полный набор ({len(table)} кандидатов, без дублей в колонке `дубль`)\n\n")
    head = ("| # | тир | метрика | каркас | eta2 | AUC | AUC_ноль | gap/MAD | eta2 нейтр | "
            "AUC нейтр | n | rho jawOpen | rho smile | дубль | мягкий дубль | флаги |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    out.append(head)
    for i, r in enumerate(table, 1):
        out.append(
            f"| {i} | {r.get('tier', '')} | `{r['metric']}` | {r['framework']} | {r['eta2']} | "
            f"{r['auc']} | {r.get('auc_null_p95', '—')} | {r['gap_over_mad']} | "
            f"{r['eta2_neutral']} | {r['auc_neutral']} | {r['n']} | {r['rho_jawopen']} | "
            f"{r['rho_smile']} | {r['duplicate_of'] or ''} | {r['near_duplicate_of'] or ''} | "
            f"{_flags(r)} |\n"
        )
    REPORT_MD.write_text("".join(out), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("extract-mp", "extract-ldm", "score"))
    parser.add_argument("--per-identity", type=int, default=0,
                        help="0 = все фронтальные фото; иначе — первые N на личность")
    parser.add_argument("--min-n", type=int, default=30,
                        help="минимум непустых значений на метрику для ранжирования")
    parser.add_argument("--identities", default=",".join(IDENTITIES),
                        help="подмножество личностей — удобно для параллельных шардов "
                             "на стадии extract-ldm")
    parser.add_argument("--n-perm", type=int, default=2000,
                        help="перестановок для нуля в стадии score; 0 — не считать")
    parser.add_argument("--shard", default="0/1",
                        help="k/n — брать только фото с индексом %% n == k (параллельные "
                             "запуски extract-ldm); по умолчанию один шард")
    args = parser.parse_args()
    idents = tuple(x.strip() for x in args.identities.split(",") if x.strip())
    bad = [x for x in idents if x not in IDENTITIES]
    if bad:
        parser.error(f"неизвестные личности: {bad}")
    k_str, _, n_str = args.shard.partition("/")
    shard = (int(k_str), max(1, int(n_str or 1)))
    if shard[0] >= shard[1]:
        parser.error(f"--shard k/n требует k < n, получено {args.shard}")
    if args.stage == "extract-mp":
        return extract_mp(args.per_identity, idents)
    if args.stage == "extract-ldm":
        return extract_ldm(args.per_identity, idents, shard)
    return score(args.min_n, args.n_perm)


if __name__ == "__main__":
    raise SystemExit(main())
