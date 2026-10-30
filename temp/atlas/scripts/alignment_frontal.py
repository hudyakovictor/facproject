"""Тест выравнивания позы на фронтальных фото (атлас, свежее извлечение).

Смысл: проверка, что коррекция позы не портит геометрию лица. Только фронтальные
кадры (yaw в [-10, +10]). Эталон человека — кадр с минимальным |yaw|, его НЕ
выравниваем. Тестовый кадр «позим» (posed = identity @ R(углы)), затем снимает
позу полной коррекцией pitch+yaw+roll к канону (0,0,0); сравниваем с эталоном в
нормировке «центр глаз + IOD» (ldm68). M1 — после выравнивания, M2 — до,
M3 = M2 - M1 (>0 — выравнивание помогло). Контроль против чужого эталона.

Извлечение — штатный путь приложения: server.storage.ingest + process
(TDDFA-V3 infer), старые таблицы и precomputed-файлы не читаем.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python scripts/alignment_frontal.py \
        --limit 6 --smoke
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import ingest_and_process, mean_vertex_distance, purge_records  # noqa: E402
from server.models.tddfa import (  # noqa: E402
    VERSION,
    classify_pose_bin,
    full_pose_correction_matrix,
    row_rotation_matrix,
)
from server.models.tddfa import POSE_BINS  # noqa: E402

# ── пороги/параметры ТЗ (§4/§5/§11) ───────────────────────────────────────────
FRONTAL = next(b for b in POSE_BINS if b[0] == "frontal")  # ("frontal", -10, 10, 0)
YAW_LO, YAW_HI = FRONTAL[1], FRONTAL[2]
CANONICAL_YAW = FRONTAL[3]
EXPRESSION_CORNER_LIFT = 0.005   # подъём уголков рта (улыбка), IOC-единицы
EXPRESSION_JAW_OPEN = 0.28       # раскрытие рта, IOC-единицы
CONFIDENCE_MIN = 0.5             # надёжность детекции лица (meta.alignment.confidence)
# ldm68: глаза 36:42 / 42:48; уголки рта 48/54; губы (внутр. центр) 62 верх / 66 низ
EYE_L, EYE_R = (36, 42), (42, 48)
L_CORNER, R_CORNER = 48, 54
UP_LIP, LOW_LIP = 62, 66
REF_TIE_DEG = 0.5                # «равные» |yaw| → решающий критерий (§6.3)
THRESHOLDS = {"median_m1": 0.03, "p95_m1": 0.06, "frac_m3_gt0": 0.80, "control_acc": 0.95}


def load_topology():
    data = json.loads((ROOT / "data/topology.json").read_text())
    return np.asarray(data["landmarks"]["ldm68"], np.int32)


def eye_center_iod(mesh, lm68):
    """Центр глаз и IOD по вершинам ldm68 на данной сетке (§8)."""
    eye = mesh[lm68]
    left = eye[list(range(*EYE_L))].mean(axis=0)
    right = eye[list(range(*EYE_R))].mean(axis=0)
    center = (left + right) / 2.0
    iod = max(float(np.linalg.norm(left - right)), 1e-8)
    return center.astype(np.float32), iod


def normalize(mesh, lm68):
    """Сдвиг в центр глаз + масштаб по IOD (§8)."""
    center, iod = eye_center_iod(mesh, lm68)
    return ((mesh - center) / iod).astype(np.float32)


def posed_mesh(identity, pitch, yaw, roll):
    """Сетка «как в кадре»: канон, повёрнутый предсказанной позой (row-vector)."""
    return (np.asarray(identity, np.float32) @ row_rotation_matrix(pitch, yaw, roll)).astype(np.float32)


def canonicalize(posed, pitch, yaw, roll):
    """Снять позу полной коррекцией к канону (0, canonical_yaw, 0)."""
    r_corr = full_pose_correction_matrix([pitch, yaw, roll], [0.0, CANONICAL_YAW, 0.0])
    return (posed @ r_corr).astype(np.float32)


def expression_flags(lmk68, lm68):
    """Мимика по ldm68 рендер-ландмарков (с экспрессией), нормировано по IOD (§5.5)."""
    pts = lmk68
    iod = eye_center_iod_from_landmarks(pts)
    if iod <= 1e-8:
        return False, {"corner_lift": None, "jaw_open": None}
    mouth_center_y = (pts[UP_LIP][1] + pts[LOW_LIP][1]) / 2.0
    corner_avg_y = (pts[L_CORNER][1] + pts[R_CORNER][1]) / 2.0
    corner_lift = float((corner_avg_y - mouth_center_y) / iod)
    jaw_open = float(np.linalg.norm(pts[UP_LIP] - pts[LOW_LIP]) / iod)
    smile = corner_lift > EXPRESSION_CORNER_LIFT
    open_mouth = jaw_open > EXPRESSION_JAW_OPEN
    return (smile or open_mouth), {"corner_lift": round(corner_lift, 5), "jaw_open": round(jaw_open, 5)}


def eye_center_iod_from_landmarks(pts68):
    left = pts68[list(range(*EYE_L))].mean(axis=0)
    right = pts68[list(range(*EYE_R))].mean(axis=0)
    return float(np.linalg.norm(left - right))


def enumerate_selected(photos_root, persons, per_person_limit):
    """Собрать {person: [{frame, path}]} из папок person_* (model-only, без таблиц).

    Битые/нечитаемые файлы пропускаем и возвращаем в списке corrupt_files.
    """
    from PIL import Image

    selected = {}
    corrupt_files = []  # (person, filename, reason)
    for pdir in sorted(photos_root.glob("person_*")):
        if persons and pdir.name not in persons:
            continue
        rows = []
        for i, jpg in enumerate(sorted(pdir.iterdir())):
            if jpg.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
                continue
            if jpg.name.startswith("._"):
                continue
            # per-file pre-validation (must match what storage.ingest does)
            try:
                img = Image.open(jpg)
                img.verify()
                img = Image.open(jpg)  # reopen after verify
                img.load()            # decode full pixel data
            except Exception as exc:
                corrupt_files.append((pdir.name, jpg.name, f"нечитаемый файл: {exc}"))
                continue
            digits = re.findall(r"\d+", jpg.stem)
            frame = int(digits[-1]) if digits else i
            rows.append({"frame": frame, "bin": "?", "path": jpg})
        if per_person_limit and 0 < per_person_limit < len(rows):
            idx = np.linspace(0, len(rows) - 1, per_person_limit).round().astype(int)
            rows = [rows[j] for j in sorted(set(idx.tolist()))]
        if len(rows) >= 2:
            selected[pdir.name] = rows
    return selected, corrupt_files


def read_feature(photo_id):
    from server import storage

    record = storage.photo(photo_id)
    path = storage.feature_path(record)
    with np.load(path) as handle:
        identity = np.asarray(handle["identity"], np.float32)
        lmk68 = np.asarray(handle["landmarks_render_ldm68"], np.float32)
        alpha = np.ravel(np.asarray(handle["alpha"], np.float32))
    pitch = float(np.degrees(alpha[224]))
    yaw = float(np.degrees(alpha[225]))
    roll = float(np.degrees(alpha[226]))
    meta_path = path.with_name("meta.json")
    conf = None
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        conf = (meta.get("alignment") or {}).get("confidence")
    crop = path.with_name("aligned.jpg")
    return {
        "identity": identity, "lmk68": lmk68, "pose_bin": classify_pose_bin(yaw)[0],
        "pitch": pitch, "yaw": yaw, "roll": roll, "confidence": conf,
        "aligned_jpg": crop if crop.exists() else None,
    }


def pick_reference(frames, lm68):
    """Эталон: min |yaw|; тай-брейк min(|pitch|+|roll|), затем раннее имя (§6)."""
    def key(item):
        _name, fr = item
        return (round(abs(fr["yaw"]), 6), abs(fr["pitch"]) + abs(fr["roll"]), _name)
    return sorted(frames.items(), key=key)[0][0]


def run(args):
    photos_root = args.photos_root
    if not photos_root.is_dir():
        raise SystemExit(f"нет фото: {photos_root}")
    persons = set(p.strip() for p in args.persons.split(",") if p.strip())
    selected, corrupt = enumerate_selected(photos_root, persons, args.per_person or args.limit)
    if corrupt:
        print(f"пропущено битых файлов: {len(corrupt)}", flush=True)
        for person, fn, reason in corrupt[:5]:
            print(f"  {person}/{fn}: {reason}", flush=True)
    if not selected:
        raise SystemExit("нет людей с >=2 фото")
    print("кадров на человека:", {p: len(r) for p, r in sorted(selected.items())}, flush=True)

    # свежее извлечение: индекс + (опция) снос кэша + реинференс
    targets, info = ingest_and_process(selected, refresh_stale=False)
    if args.reforce:
        from server import storage

        job = type("J", (), {"check": lambda s: None, "update": lambda *a, **k: None})()
        for rec in targets:
            fp = storage.feature_path(rec)
            fp.unlink(missing_ok=True)
            fp.with_name("meta.json").unlink(missing_ok=True)
        info = storage.process(job, [r["id"] for r in targets])
    print("process:", {k: info[k] for k in ("photos", "cache_hits", "errors")}, flush=True)

    lm68 = load_topology()
    name_to_row = {p: {row["path"].name: row for row in rows} for p, rows in selected.items()}

    # собрать кадры по людям
    per_person = {}
    skipped = list(corrupt)  # битые файлы → в skipped.csv
    for person, rows in selected.items():
        frames = {}
        for row in rows:
            fname = row["path"].name
            fr = read_feature(row["id"])
            status = "ok"
            if fr["pose_bin"] != "frontal" or not (YAW_LO <= fr["yaw"] <= YAW_HI):
                status = "skip_pose" if abs(fr["yaw"]) > YAW_HI else "skip_pose"
                skipped.append((person, fname, "вне фронтального диапазона yaw"))
                continue
            if fr["confidence"] is None or fr["confidence"] < CONFIDENCE_MIN:
                skipped.append((person, fname, f"низкая надёжность {fr['confidence']}"))
                fr["status"] = "skip_confidence"
                continue
            expressive, exp = expression_flags(fr["lmk68"], lm68)
            if expressive:
                skipped.append((person, fname, f"мимика {exp}"))
                fr["status"] = "skip_expression"
                continue
            fr["name"] = fname
            fr["norm_ref"] = normalize(fr["identity"], lm68)      # «после» == канон (identity)
            fr["norm_posed"] = normalize(posed_mesh(fr["identity"], fr["pitch"], fr["yaw"], fr["roll"]), lm68)
            frames[fname] = fr
        if len(frames) < 2:
            for row in rows:
                if row["path"].name not in frames:
                    continue
            skipped.append((person, "", "мало фото после фильтров"))
            continue
        per_person[person] = frames

    # предвычислить эталон и его вектор на человека (один проход)
    person_ref = {}
    for person, frames in sorted(per_person.items()):
        ref_name = pick_reference(frames, lm68)
        person_ref[person] = {"name": ref_name, "vec": frames[ref_name]["norm_ref"]}

    results = []
    for person, frames in sorted(per_person.items()):
        ref_name = person_ref[person]["name"]
        ref_vec = person_ref[person]["vec"]
        others = [p for p in per_person if p != person]
        for fname, fr in sorted(frames.items()):
            is_ref = fname == ref_name
            m1 = None if is_ref else mean_vertex_distance(fr["norm_ref"], ref_vec)
            m2 = None if is_ref else mean_vertex_distance(fr["norm_posed"], ref_vec)
            m3 = (m2 - m1) if (m1 is not None and m2 is not None) else None
            m1_other = None
            if others and not is_ref:
                # детерминированный выбор чужого человека и его эталона (§10, §14.2)
                code = zlib.crc32(f"{person}/{fname}".encode())
                rng = np.random.default_rng(args.seed + code)
                other = others[int(rng.integers(len(others)))]
                m1_other = mean_vertex_distance(fr["norm_ref"], person_ref[other]["vec"])
            results.append({
                "person": person, "file": fname, "yaw": round(fr["yaw"], 3),
                "pitch": round(fr["pitch"], 3), "roll": round(fr["roll"], 3),
                "M1": None if m1 is None else round(m1, 6),
                "M2": None if m2 is None else round(m2, 6),
                "M3": None if m3 is None else round(m3, 6),
                "M1_other": None if m1_other is None else round(m1_other, 6),
                "status": "reference" if is_ref else "ok",
                "is_reference": is_ref,
            })

    return per_person, results, skipped, info, person_ref, targets


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--persons", default="person_01,person_02,person_03,person_04,person_05,person_06,person_07",
                    help="через запятую (default: person_01..07)")
    ap.add_argument("--per-person", type=int, default=0, help="макс кадров на человека (0=все)")
    ap.add_argument("--limit", type=int, default=0, help="алиас per-person для дым-теста")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reforce", action="store_true", help="снести кэш и переизвлечь заново")
    ap.add_argument("--smoke", action="store_true", help="только печать чисел без отчётов")
    ap.add_argument("--purge", action="store_true", help="убрать записи корпуса из библиотеки")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/alignment-frontal")
    args = ap.parse_args()

    per_person, results, skipped, info, person_ref, targets = run(args)
    if args.smoke:
        test_rows = [r for r in results if not r["is_reference"]]
        m1 = [r["M1"] for r in test_rows if r["M1"] is not None]
        m3 = [r["M3"] for r in test_rows if r["M3"] is not None]
        ctrl = [(r["M1"], r["M1_other"]) for r in test_rows
                if r["M1"] is not None and r["M1_other"] is not None]
        print(f"smoke: test-кадров {len(test_rows)}  людей {len(person_ref)}  "
              f"M1 med {np.median(m1) if m1 else float('nan'):.4f}  "
              f"M3 med {np.median(m3) if m3 else float('nan'):.4f}  "
              f"M3>0 {np.mean([m > 0 for m in m3]) if m3 else float('nan'):.3f}  "
              f"control {np.mean([a < b for a, b in ctrl]) if ctrl else float('nan'):.3f}")
        if args.purge:
            print("purged", purge_records([t["id"] for t in targets]))
        return

    write_reports(args, per_person, results, skipped, info, person_ref, targets)
    if args.purge:
        print("purged", purge_records([t["id"] for t in targets]))


def p95(values):
    arr = np.asarray(values, float)
    return None if arr.size == 0 else round(float(np.percentile(arr, 95)), 6)


def write_reports(args, per_person, results, skipped, info, person_ref, targets):
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    test_rows = [r for r in results if not r["is_reference"]]

    # 1. results_per_photo.csv
    cols = ["person", "file", "yaw", "pitch", "roll", "M1", "M2", "M3", "M1_other", "status"]
    with (out / "results_per_photo.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter=";")
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k) for k in cols})

    # 2. results_per_person.csv (§9: среднее по тестовым фото человека)
    per_person_stats = {}
    with (out / "results_per_person.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["person", "n_test", "mean_M1", "mean_M3", "status"])
        for person in sorted(person_ref):
            rows = [r for r in test_rows if r["person"] == person]
            if not rows:
                continue
            mean_m1 = float(np.mean([r["M1"] for r in rows]))
            mean_m3 = float(np.mean([r["M3"] for r in rows if r["M3"] is not None]))
            per_person_stats[person] = {"n_test": len(rows), "mean_M1": round(mean_m1, 6),
                                         "mean_M3": round(mean_m3, 6)}
            w.writerow([person, len(rows), round(mean_m1, 6), round(mean_m3, 6), "ok"])

    # 3. skipped.csv
    with (out / "skipped.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["person_or_file", "reason"])
        for person, fname, reason in skipped:
            w.writerow([f"{person}/{fname}" if fname else person, reason])

    # 4. summary.json
    m1_people = [s["mean_M1"] for s in per_person_stats.values()]
    m3_people = [s["mean_M3"] for s in per_person_stats.values()]
    m3_photo = [r["M3"] for r in test_rows if r["M3"] is not None]
    ctrl = [(r["M1"], r["M1_other"]) for r in test_rows
            if r["M1"] is not None and r["M1_other"] is not None]
    median_m1 = round(float(np.median(m1_people)), 6) if m1_people else None
    p95_m1 = p95(m1_people)
    frac_m3 = round(float(np.mean([m > 0 for m in m3_photo])), 4) if m3_photo else None
    control_acc = round(float(np.mean([a < b for a, b in ctrl])), 4) if ctrl else None
    gates = {
        "median_m1<=0.03": (median_m1 is not None and median_m1 <= THRESHOLDS["median_m1"]),
        "p95_m1<=0.06": (p95_m1 is not None and p95_m1 <= THRESHOLDS["p95_m1"]),
        "frac_m3>0>=0.80": (frac_m3 is not None and frac_m3 >= THRESHOLDS["frac_m3_gt0"]),
        "control>=0.95": (control_acc is not None and control_acc >= THRESHOLDS["control_acc"]),
    }
    summary = {
        "people": len(person_ref), "test_photos": len(test_rows), "skipped_rows": len(skipped),
        "yaw_range_observed": [round(min((r["yaw"] for r in results), default=0), 3),
                                round(max((r["yaw"] for r in results), default=0), 3)],
        "M1_by_person_mean": {"median": median_m1, "p95": p95_m1,
                               "mean": round(float(np.mean(m1_people)), 6) if m1_people else None},
        "M3_by_person_mean": {"median": round(float(np.median(m3_people)), 6) if m3_people else None,
                               "p95": p95(m3_people)},
        "M3_by_photo": {"n": len(m3_photo), "median": round(float(np.median(m3_photo)), 6) if m3_photo else None,
                         "frac_gt0": frac_m3},
        "control": {"n": len(ctrl), "accuracy": control_acc},
        "gates": {k: bool(v) for k, v in gates.items()},
        "verdict": "пройден" if all(gates.values()) else "не пройден",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. config_snapshot.json (§12.5)
    snapshot = {
        "schema_version": VERSION, "yaw_range": [YAW_LO, YAW_HI],
        "canonical_yaw": CANONICAL_YAW, "expression": {
            "corner_lift": EXPRESSION_CORNER_LIFT, "jaw_open": EXPRESSION_JAW_OPEN,
            "magnitude_12_0": "не используется (atlas: мимика по ldm68-геометрии)"},
        "confidence_min": CONFIDENCE_MIN, "seed": args.seed,
        "normalization": "центр глаз (ldm68 36:42/42:48) + IOD", "thresholds": THRESHOLDS,
    }
    (out / "config_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6. worst_20/ — 20 худших тестовых фото по M1: ориг + выровненный кроп + эталон
    worst = sorted(test_rows, key=lambda r: (r["M1"] is None, -(r["M1"] or 0)))[:20]
    worst_dir = out / "worst_20"
    worst_dir.mkdir(parents=True, exist_ok=True)
    from server import storage

    by_key = {(t["group"], t["name"]): t for t in targets}
    for r in worst:
        person, fname = r["person"], r["file"]
        base = f"{person}__{Path(fname).stem}"
        src = args.photos_root / person / fname
        if src.is_file():
            shutil.copy(src, worst_dir / f"{base}__orig.jpg")
        rec = by_key.get((person, fname))
        if rec:
            crop = storage.feature_path(rec).with_name("aligned.jpg")
            if crop.exists():
                shutil.copy(crop, worst_dir / f"{base}__test_aligned.jpg")
            ref_name = person_ref[person]["name"]
            refrec = by_key.get((person, ref_name))
            if refrec:
                rc = storage.feature_path(refrec).with_name("aligned.jpg")
                if rc.exists():
                    shutil.copy(rc, worst_dir / f"{base}__reference.jpg")
    print("отчёт:", out, "| verdict:", summary["verdict"], "| gates:", summary["gates"])


if __name__ == "__main__":
    main()
