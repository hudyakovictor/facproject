#!/usr/bin/env python
"""MediaPipe-усиление классификатора put/vas/udmurt.

Считает FaceLandmarker (Tasks API, 478 точек + iris) по всем оригиналам,
разбивает по ракурсу из *_angles.csv и вычисляет набор 2D-метрик формы,
которых НЕТ в текущих 17 признаках 3DDFA: iris-расстояния, плотные контуры
(скулы/челюсть), геометрия губ/бров, плюс выражения (blendshapes). Цель —
найти признаки, лучше всего разделяющие три личности на фронтальных фото,
чтобы потом усилить гибрид 3ddfa_v3 + mediapipe.

Запуск:  python .runtime/mp_identity_probe.py
Выход:   .runtime/mp_identity_probe.json  + печатный отчёт.
"""
from __future__ import annotations

import csv
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
DATA = Path("/Volumes/SDCARD/test_photos")
ASSET = ROOT / "temp/atlas/.cache/models/mediapipe/face_landmarker.task"
OUT = ROOT / ".runtime" / "mp_identity_probe.json"

IDENTITIES = ("put", "vas", "udmurt")
CSVS = {name: ROOT / f"{name}_angles.csv" for name in IDENTITIES}

# Индексы MediaPipe FaceMesh (478 точек, 468-477 = iris).
MP = {
    "iris_l": 468, "iris_r": 473,
    "eye_out_l": 33, "eye_in_l": 133, "eye_out_r": 362, "eye_in_r": 263,
    "eye_top_l": 159, "eye_bot_l": 145, "eye_top_r": 386, "eye_bot_r": 374,
    "brow_l_out": 70, "brow_r_out": 300, "brow_l_top": 65, "brow_l_bot": 105,
    "brow_r_top": 293, "brow_r_bot": 334,
    "nose_bridge_top": 168, "nose_tip": 1, "nose_base": 2,
    "alar_l": 98, "alar_r": 327,
    "mouth_l": 61, "mouth_r": 291, "lip_up_in": 13, "lip_dn_in": 14,
    "lip_up_out": 0, "lip_dn_out": 17,
    "cheek_l": 234, "cheek_r": 454, "jaw_l": 58, "jaw_r": 288,
    "chin": 152, "forehead_top": 10,
}

# Пороги «чистого» нейтрального выражения (blendshape-фильтр).
EXPR_MAX = {"jawOpen": 0.12, "mouthSmileLeft": 0.25, "mouthSmileRight": 0.25,
            "browInnerUp": 0.30, "eyeBlinkLeft": 0.35, "eyeBlinkRight": 0.35}
EXPR_TRACK = ["jawOpen", "mouthSmileLeft", "mouthSmileRight", "browInnerUp",
              "browDownLeft", "browDownRight", "cheekSquintLeft", "eyeBlinkLeft"]


def load_angles(path: Path) -> dict[str, dict[str, float | str]]:
    rows: dict[str, dict[str, float | str]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            name = (rec.get("filename") or "").strip()
            if not name:
                continue
            rows[name] = {
                "yaw": _f(rec.get("yaw_deg")),
                "pitch": _f(rec.get("pitch_deg")),
                "roll": _f(rec.get("roll_deg")),
                "bin": (rec.get("pose_bin") or "").strip(),
                "status": (rec.get("status") or "").strip(),
            }
    return rows


def _f(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _d(p, a: str, b: str) -> float:
    return float(np.linalg.norm(p[MP[a], :2] - p[MP[b], :2]))


def _angle(p, a, b, c):
    u = p[a, :2] - p[b, :2]
    v = p[c, :2] - p[b, :2]
    den = max(np.linalg.norm(u) * np.linalg.norm(v), 1e-9)
    return float(np.degrees(np.arccos(np.clip(np.dot(u, v) / den, -1, 1))))


def metrics(pts: np.ndarray) -> dict[str, float]:
    p = pts.copy()
    scale = float(np.sqrt(((p[:, :2] - p[:, :2].mean(0)) ** 2).sum(1).mean())) or 1.0
    face_w = _d(p, "cheek_l", "cheek_r")
    face_len = _d(p, "forehead_top", "chin")
    lower_w = _d(p, "jaw_l", "jaw_r")
    ipd = _d(p, "iris_l", "iris_r")
    mouth_w = _d(p, "mouth_l", "mouth_r")
    ew_l = _d(p, "eye_out_l", "eye_in_l")
    ew_r = _d(p, "eye_out_r", "eye_in_r")
    eh_l = _d(p, "eye_top_l", "eye_bot_l")
    eh_r = _d(p, "eye_top_r", "eye_bot_r")
    nose_w = _d(p, "alar_l", "alar_r")
    nose_len = _d(p, "nose_bridge_top", "nose_base")
    out = {
        "ipd_over_face_w": ipd / face_w,
        "face_w_over_face_len": face_w / face_len,
        "lower_w_over_face_w": lower_w / face_w,
        "zygomatic_flare": face_w / lower_w,
        "brow_span_over_face_w": _d(p, "brow_l_out", "brow_r_out") / face_w,
        "nose_w_over_mouth_w": nose_w / mouth_w,
        "nose_len_over_face_len": nose_len / face_len,
        "mouth_w_over_face_w": mouth_w / face_w,
        "philtrum_over_face_len": _d(p, "nose_base", "lip_up_out") / face_len,
        "mouth_open_over_mouth_w": _d(p, "lip_up_in", "lip_dn_in") / mouth_w,
        "lip_thick_over_mouth_w": _d(p, "lip_up_out", "lip_dn_out") / mouth_w,
        "midface_over_face_len": _d(p, "nose_base", "chin") / face_len,
        "eye_open_l": eh_l / ew_l,
        "eye_open_r": eh_r / ew_r,
        "eye_w_asym": abs(ew_l - ew_r) / ((ew_l + ew_r) / 2 + 1e-9),
        "eye_h_asym": abs(eh_l - eh_r) / ((eh_l + eh_r) / 2 + 1e-9),
        "brow_thk_l": _d(p, "brow_l_top", "brow_l_bot") / scale,
        "brow_thk_r": _d(p, "brow_r_top", "brow_r_bot") / scale,
        "nose_tip_to_base_over_len": _d(p, "nose_base", "nose_tip") / nose_len,
        "jaw_contour_angle": np.mean([
            _angle(p, MP["cheek_l"], MP["jaw_l"], MP["chin"]),
            _angle(p, MP["cheek_r"], MP["jaw_r"], MP["chin"]),
        ]),
        "chin_angle": _angle(p, MP["jaw_l"], MP["chin"], MP["jaw_r"]),
    }
    return {k: (v if v == v and math.isfinite(v) else math.nan) for k, v in out.items()}


FEATURES = list(metrics(np.stack(
    [np.arange(478.0), np.arange(478.0) * 0.5, np.zeros(478)], axis=1
)).keys())


def is_frontal(row) -> bool:
    return row["bin"] == "frontal" and abs(row["yaw"]) <= 15


def main() -> None:
    import mediapipe as mp

    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(ASSET),
                                          delegate=mp.tasks.BaseOptions.Delegate.CPU),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1, output_face_blendshapes=True,
        output_facial_transformation_matrixes=False,
    )
    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

    per_identity: dict[str, dict[str, list[float]]] = {
        ident: {feat: [] for feat in FEATURES} for ident in IDENTITIES}
    expr_identity: dict[str, dict[str, list[float]]] = {
        ident: {k: [] for k in EXPR_TRACK} for ident in IDENTITIES}
    detect_rate: dict[str, dict[str, dict[str, int]]] = {
        ident: defaultdict(lambda: {"detected": 0, "missed": 0}) for ident in IDENTITIES}
    records: list[dict] = []

    started = time.time()
    total = ok = miss = 0
    for ident in IDENTITIES:
        angles = load_angles(CSVS[ident])
        for path in sorted((DATA / ident).iterdir()):
            if path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            row = angles.get(path.name)
            if row is None or row["status"] != "ok":
                continue
            grp = "frontal" if is_frontal(row) else ("light" if abs(row["yaw"]) <= 32 else "profile")
            img = cv2.imread(str(path))
            if img is None:
                detect_rate[ident][grp]["missed"] += 1
                continue
            total += 1
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            if not res.face_landmarks:
                detect_rate[ident][grp]["missed"] += 1
                miss += 1
                continue
            detect_rate[ident][grp]["detected"] += 1
            ok += 1
            lm = res.face_landmarks[0]
            if len(lm) != 478:
                continue
            H, W = img.shape[:2]
            pts = np.array([(q.x * W, q.y * H, q.z * W) for q in lm], dtype=np.float32)
            blend = {}
            if res.face_blendshapes:
                blend = {s.category_name: float(s.score) for s in res.face_blendshapes[0]}
            vals = metrics(pts)
            expr_ok = all(blend.get(k, 0.0) <= thr for k, thr in EXPR_MAX.items())
            records.append({
                "identity": ident, "file": path.name, "grp": grp,
                "yaw": row["yaw"], "expr_ok": expr_ok,
                "vals": {k: (None if v != v else round(v, 5)) for k, v in vals.items()},
                "expr": {k: blend.get(k) for k in EXPR_TRACK},
            })
            if grp == "frontal" and expr_ok:  # чистый анфас без кривой гримасы
                for feat in FEATURES:
                    if vals[feat] == vals[feat]:
                        per_identity[ident][feat].append(vals[feat])
                for k in EXPR_TRACK:
                    if blend.get(k) is not None:
                        expr_identity[ident][k].append(blend[k])
        print(f"[{ident}] done {time.time() - started:.0f}s", flush=True)

    separation = []
    for feat in FEATURES:
        groups = [np.array(per_identity[i][feat], dtype=np.float64) for i in IDENTITIES]
        if min(len(g) for g in groups) < 5:
            continue
        allv = np.concatenate(groups)
        grand = allv.mean()
        ss_b = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
        ss_t = ((allv - grand) ** 2).sum()
        eta2 = ss_b / ss_t if ss_t > 1e-12 else 0.0
        meds = {i: float(np.median(g)) for i, g in zip(IDENTITIES, groups, strict=False)}
        mad = float(np.median(np.abs(allv - np.median(allv)))) or 1e-9
        separation.append({
            "feature": feat, "eta2": round(eta2, 4),
            "spread_over_mad": round((max(meds.values()) - min(meds.values())) / mad, 3),
            "medians": {k: round(v, 4) for k, v in meds.items()},
            "n": {i: len(g) for i, g in zip(IDENTITIES, groups, strict=False)},
        })
    separation.sort(key=lambda r: r["eta2"], reverse=True)

    expr_report = {
        i: {k: round(float(np.median(expr_identity[i][k])), 3) for k in EXPR_TRACK}
        for i in IDENTITIES if expr_identity[i][EXPR_TRACK[0]]
    }

    report = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_sec": round(time.time() - started, 1),
        "photos_tried": total, "mp_detected": ok, "mp_missed": miss,
        "detection_rate": {i: {g: dict(v) for g, v in dict(detect_rate[i]).items()} for i in IDENTITIES},
        "clean_frontal_n": {i: len(per_identity[i][FEATURES[0]]) for i in IDENTITIES},
        "separation": separation,
        "top_features": [r["feature"] for r in separation[:8]],
        "expression_medians": expr_report,
    }
    OUT.write_text(json.dumps({"report": report, "records": records}, ensure_ascii=False), encoding="utf-8")

    print("\n=== ИТОГО ===")
    print(f"обработано {total}, MP нашёл {ok}, не нашёл {miss}")
    print("ставка обнаружения по ракурсам:")
    for i in IDENTITIES:
        print(f"  {i}: {report['detection_rate'][i]}")
    print(f"чистых фронтальных замеров/личность: {report['clean_frontal_n']}")
    print("\nТоп разделяющих признаков (eta^2):")
    for r in separation[:14]:
        print(f"  eta2={r['eta2']:.3f} spread/MAD={r['spread_over_mad']:.2f} {r['feature']:34s} {r['medians']}")
    print("\nМедианы выражений (нейтральный анфас):")
    for i, e in expr_report.items():
        print(f"  {i}: {e}")
    print(f"\nОтчёт: {OUT}")


if __name__ == "__main__":
    main()
