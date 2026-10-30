"""Pixel-space ocular morphometry, not identity recognition or a mask detector.
478-point MediaPipe estimates are auditable against original pixels. Low quality,
head pose and approximate gaze are filters, not an 'authenticity' classification.
"""

from pathlib import Path
import json, threading, hashlib, math, time
from functools import lru_cache
import numpy as np
from PIL import Image, ImageOps
from server.config import ROOT, atomic_json, digest
from server import storage

VERSION = "ocular-mp478-v1"
FACE_POSE_AVAILABLE = False
ASSET = ROOT / ".cache/models/mediapipe/face_landmarker.task"
LOCK = threading.RLock()
_model = None
CATALOG = [
    (
        "iris_width_ratio",
        "Радужка / ширина глазной щели",
        "ratio",
        "D радужки / расстояние между уголками; среднее двух глаз.",
    ),
    (
        "iris_height_ratio",
        "Радужка / высота глазной щели",
        "ratio",
        "D радужки / раскрытие век. Значение >1 само по себе нормально: веки закрывают часть радужки.",
    ),
    (
        "aperture_area_ratio",
        "Площадь щели / ширина²",
        "ratio",
        "Площадь контура век, нормированная на квадрат ширины.",
    ),
    (
        "eye_aspect_ratio",
        "EAR · раскрытие глаз",
        "ratio",
        "Сумма двух вертикальных отрезков / удвоенная ширина.",
    ),
    (
        "canthal_tilt_left",
        "Наклон уголков · слева на фото",
        "deg",
        "Наклон наружного уголка относительно внутреннего после устранения крена.",
    ),
    (
        "canthal_tilt_right",
        "Наклон уголков · справа на фото",
        "deg",
        "То же для другого глаза; не медицинская оценка.",
    ),
    (
        "eye_width_asymmetry",
        "Асимметрия ширины глаз",
        "ratio",
        "Абсолютная разность / средняя ширина.",
    ),
    (
        "eye_height_asymmetry",
        "Асимметрия раскрытия век",
        "ratio",
        "Абсолютная разность / среднее раскрытие.",
    ),
    (
        "intercanthal_ipd",
        "Межуголковое расстояние / IPD",
        "ratio",
        "Внутренние уголки / расстояние центров радужек.",
    ),
    (
        "eye_width_ipd",
        "Ширина глаза / IPD",
        "ratio",
        "Средняя ширина щели / расстояние центров радужек.",
    ),
    (
        "nose_width_ipd",
        "Ширина крыльев носа / IPD",
        "ratio",
        "Точки 98–327 / расстояние центров радужек.",
    ),
    (
        "nose_length_ipd",
        "Длина носа / IPD",
        "ratio",
        "Переносица 168 – основание 2, в плоскости изображения.",
    ),
    (
        "bridge_width_ipd",
        "Ширина переносицы / IPD",
        "ratio",
        "Точки 193–417; ориентировочная ширина мягких тканей, не кости.",
    ),
    (
        "nose_bridge_ratio",
        "Крылья носа / переносица",
        "ratio",
        "Ширина 98–327 / ширина 193–417.",
    ),
    (
        "midface_width_ratio",
        "Средняя зона / ширина лица",
        "ratio",
        "168–2 / 234–454; двумерная проекция.",
    ),
    (
        "face_height_width",
        "Высота лицевой сетки / ширина",
        "ratio",
        "10–152 / 234–454. Не высота или форма черепа.",
    ),
    (
        "jaw_cheek_ratio",
        "Ширина челюсти / скулы",
        "ratio",
        "172–397 / 234–454; контур мягких тканей.",
    ),
    ("lower_face_ratio", "Нижняя зона / высота лица", "ratio", "2–152 / 10–152."),
    ("chin_jaw_ratio", "Ширина подбородка / челюсть", "ratio", "149–378 / 172–397."),
    (
        "jaw_contour_angle",
        "Угол контура нижней челюсти",
        "deg",
        "Среднее углов 234–172–152 и 454–397–152. Не костный гониальный угол.",
    ),
]
EYES = [
    dict(
        side="left",
        label="Слева на фото",
        outer=33,
        inner=133,
        top=159,
        bottom=145,
        iris=468,
        ring=[469, 470, 471, 472],
        ear=[33, 160, 158, 133, 153, 144],
        contour=[
            33,
            7,
            163,
            144,
            145,
            153,
            154,
            155,
            133,
            173,
            157,
            158,
            159,
            160,
            161,
            246,
        ],
    ),
    dict(
        side="right",
        label="Справа на фото",
        outer=263,
        inner=362,
        top=386,
        bottom=374,
        iris=473,
        ring=[474, 475, 476, 477],
        ear=[362, 385, 387, 263, 373, 380],
        contour=[
            263,
            249,
            390,
            373,
            374,
            380,
            381,
            382,
            362,
            398,
            384,
            385,
            386,
            387,
            388,
            466,
        ],
    ),
]


def availability():
    import importlib.util

    ok = ASSET.exists() and importlib.util.find_spec("mediapipe") is not None
    return {
        "id": "mediapipe",
        "title": "MediaPipe · 478 + iris",
        "available": ok,
        "enabled": ok,
        "device": "CPU",
        "version": VERSION,
        "reason": None if ok else "Нет MediaPipe или face_landmarker.task",
    }


def landmarker():
    global _model
    with LOCK:
        if _model is None:
            if not availability()["available"]:
                raise RuntimeError(availability()["reason"])
            import mediapipe as mp

            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path=str(ASSET),
                    delegate=mp.tasks.BaseOptions.Delegate.CPU,
                ),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_faces=1,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
            )
            _model = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        return _model


def paths(p):
    directory = ROOT / "cache" / p["id"]
    directory.mkdir(parents=True, exist_ok=True)
    return (
        directory / "ocular-detection.json",
        directory / "ocular-manual.json",
        directory / "ocular.json",
    )


def detection(p):
    path, _, _ = paths(p)
    if path.exists():
        data = json.loads(path.read_text())
        if data.get("source_hash") == p["hash"] and data.get("version") == VERSION:
            return data
    import mediapipe as mp

    image = ImageOps.exif_transpose(Image.open(ROOT / p["path"])).convert("RGB")
    w, h = image.size
    # Preserve native pixels in all measurements; only the detector input may shrink.
    if max(w, h) > 2200:
        image = image.resize(
            (round(w * 2200 / max(w, h)), round(h * 2200 / max(w, h))),
            Image.Resampling.LANCZOS,
        )
    with LOCK:
        result = landmarker().detect(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(image))
        )
    if not result.face_landmarks:
        raise ValueError(
            "MediaPipe не нашёл лицо; автоматические значения не выдумываются."
        )
    points = [[float(q.x * w), float(q.y * h)] for q in result.face_landmarks[0]]
    if len(points) != 478:
        raise ValueError("Модель не вернула 478 точек с радужками.")
    data = {
        "version": VERSION,
        "source_hash": p["hash"],
        "width": w,
        "height": h,
        "points": points,
        "blendshapes": {
            s.category_name: float(s.score) for s in result.face_blendshapes[0]
        }
        if result.face_blendshapes
        else {},
        "model_sha256": hashlib.sha256(ASSET.read_bytes()).hexdigest(),
        "created": time.time(),
    }
    atomic_json(path, data)
    return data


def div(a, b):
    return float(a / max(float(b), 1e-8))


def area(poly):
    return float(
        abs(
            np.dot(poly[:, 0], np.roll(poly[:, 1], 1))
            - np.dot(poly[:, 1], np.roll(poly[:, 0], 1))
        )
        / 2
    )


def angle(a, b, c):
    u = a - b
    v = c - b
    return float(
        np.degrees(
            np.arccos(
                np.clip(
                    np.dot(u, v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-8),
                    -1,
                    1,
                )
            )
        )
    )


def measure(p, run=False):
    detect_path, manual_path, out = paths(p)
    if not detect_path.exists() and not run:
        raise FileNotFoundError("Измерения ещё не рассчитаны")
    data = detection(p) if run else json.loads(detect_path.read_text())
    manual = json.loads(manual_path.read_text()) if manual_path.exists() else {}
    points = np.array(data["points"], np.float64)
    for idx, xy in manual.get("points", {}).items():
        points[int(idx)] = xy
    dist = lambda a, b: float(np.linalg.norm(points[a] - points[b]))
    centers = points[[468, 473]]
    roll = math.atan2(centers[1, 1] - centers[0, 1], centers[1, 0] - centers[0, 0])
    cs, sn = math.cos(roll), math.sin(roll)
    upright = points @ np.array([[cs, -sn], [sn, cs]])
    eyes = []
    for spec in EYES:
        a, b = points[spec["outer"]], points[spec["inner"]]
        width = float(np.linalg.norm(a - b))
        axis = (b - a) / max(width, 1e-8)
        normal = np.array([-axis[1], axis[0]])
        height = abs(
            float(np.dot(points[spec["top"]] - points[spec["bottom"]], normal))
        )
        d = dist(spec["ring"][0], spec["ring"][2])
        vdiam = dist(spec["ring"][1], spec["ring"][3])
        center = points[spec["iris"]]
        gaze_x = float(np.dot(center - (a + b) / 2, axis) / max(width, 1e-8))
        gaze_y = float(
            np.dot(center - (points[spec["top"]] + points[spec["bottom"]]) / 2, normal)
            / max(height, 1e-8)
        )
        ear = spec["ear"]
        ear_value = div(
            dist(ear[1], ear[5]) + dist(ear[2], ear[4]), 2 * dist(ear[0], ear[3])
        )
        tilt = float(
            np.degrees(
                np.arctan2(
                    upright[spec["inner"], 1] - upright[spec["outer"], 1],
                    abs(upright[spec["inner"], 0] - upright[spec["outer"], 0]),
                )
            )
        )
        contour = points[spec["contour"]]
        pad = width * 0.22
        lo = np.min(contour, axis=0) - pad
        hi = np.max(contour, axis=0) + pad
        eyes.append(
            spec
            | {
                "width_px": width,
                "height_px": height,
                "iris_diameter_px": d,
                "iris_vertical_estimate_px": vdiam,
                "iris_width_ratio": div(d, width),
                "iris_height_ratio": div(d, height),
                "aperture_area_ratio": div(area(contour), width**2),
                "ear_value": ear_value,
                "tilt_deg": tilt,
                "gaze_x": gaze_x,
                "gaze_y": gaze_y,
                "bounds": [
                    float(lo[0]),
                    float(lo[1]),
                    float(hi[0] - lo[0]),
                    float(hi[1] - lo[1]),
                ],
                "pixel_sensitivity_1px": {
                    "iris_width_ratio": [
                        div(max(0, d - 1), width + 1),
                        div(d + 1, max(1, width - 1)),
                    ],
                    "iris_height_ratio": [
                        div(max(0, d - 1), height + 1),
                        div(d + 1, max(1, height - 1)),
                    ],
                },
            }
        )
    avg = lambda k: float(np.mean([e[k] for e in eyes]))
    asym = lambda k: div(abs(eyes[0][k] - eyes[1][k]), avg(k))
    ipd = dist(468, 473)
    nose = dist(98, 327)
    bridge = dist(193, 417)
    cheeks = dist(234, 454)
    face_h = dist(10, 152)
    jaw = dist(172, 397)
    values = dict(
        iris_width_ratio=avg("iris_width_ratio"),
        iris_height_ratio=avg("iris_height_ratio"),
        aperture_area_ratio=avg("aperture_area_ratio"),
        eye_aspect_ratio=avg("ear_value"),
        canthal_tilt_left=eyes[0]["tilt_deg"],
        canthal_tilt_right=eyes[1]["tilt_deg"],
        eye_width_asymmetry=asym("width_px"),
        eye_height_asymmetry=asym("height_px"),
        intercanthal_ipd=div(dist(133, 362), ipd),
        eye_width_ipd=div(avg("width_px"), ipd),
        nose_width_ipd=div(nose, ipd),
        nose_length_ipd=div(dist(168, 2), ipd),
        bridge_width_ipd=div(bridge, ipd),
        nose_bridge_ratio=div(nose, bridge),
        midface_width_ratio=div(dist(168, 2), cheeks),
        face_height_width=div(face_h, cheeks),
        jaw_cheek_ratio=div(jaw, cheeks),
        lower_face_ratio=div(dist(2, 152), face_h),
        chin_jaw_ratio=div(dist(149, 378), jaw),
        jaw_contour_angle=float(
            np.mean(
                [
                    angle(points[234], points[172], points[152]),
                    angle(points[454], points[397], points[152]),
                ]
            )
        ),
    )
    state = storage.state(p)
    head = state["angles"]
    reasons = []
    if not state.get("meta"):
        reasons.append("Нет независимой оценки ракурса 3DDFA или ручных углов")
    if abs(head["yaw"]) > 8 or abs(head["pitch"]) > 8 or abs(head["roll"]) > 5:
        reasons.append(
            "За пределами строгого фронтального окна: yaw/pitch ±8°, roll ±5°"
        )
    if (
        min(e["width_px"] for e in eyes) < 45
        or min(e["iris_diameter_px"] for e in eyes) < 10
    ):
        reasons.append(
            "Недостаточно исходных пикселей: ширина глаза <45 или радужка <10 px"
        )
    if min(e["height_px"] for e in eyes) < 3:
        reasons.append("Раскрытие <3 px: погрешность пикселя слишком велика")
    if (manual.get("gaze_ok") is not True) and (
        max(abs(e["gaze_x"]) for e in eyes) > 0.16
        or max(abs(e["gaze_y"]) for e in eyes) > 0.3
    ):
        reasons.append("Взгляд не прошёл приближённый фильтр; нужна ручная проверка")
    if manual.get("gaze_ok") is False:
        reasons.append("Направление взгляда отмечено как неподходящее")
    if (
        max(data["blendshapes"].get(k, 0) for k in ("eyeBlinkLeft", "eyeBlinkRight"))
        > 0.75
    ):
        reasons.append("Возможное моргание по blendshape-score")
    output = {
        "id": p["id"],
        "name": p["name"],
        "group": p["group"],
        "date": p.get("date"),
        "cohort": manual.get("cohort") or p.get("cohort") or "",
        "version": VERSION,
        "source_hash": p["hash"],
        "width": data["width"],
        "height": data["height"],
        "sharpness": float((state.get("meta") or {}).get("sharpness", 0)),
        "points": points.tolist(),
        "eyes": eyes,
        "metrics": values,
        "catalog": [
            {"id": k, "title": title, "unit": unit, "description": description}
            for k, title, unit, description in CATALOG
        ],
        "angles": head,
        "eligible": not reasons,
        "exclusion_reasons": reasons,
        "reviewed": bool(manual.get("reviewed")),
        "angle_source": manual.get("angle_source", "3DDFA_V3"),
        "gaze_ok": manual.get("gaze_ok"),
        "blendshapes": data["blendshapes"],
        "source": f"/api/photos/{p['id']}/image",
        "warning": "Это измерения видимой 2D-проекции и оценки разметки. Они не устанавливают личность, наличие маски, диагноз или «естественность». D радужки / высота щели >1 само по себе нормально.",
        "measurement_key": digest(
            {"detection": data["source_hash"], "manual": manual, "version": VERSION}
        ),
    }
    atomic_json(out, output)
    return output


def annotate(p, changes):
    _, path, _ = paths(p)
    data = json.loads(paths(p)[0].read_text())
    manual = json.loads(path.read_text()) if path.exists() else {}
    points = changes.get("points", {})
    for idx, xy in points.items():
        if (
            not str(idx).isdigit()
            or not 0 <= int(idx) < 478
            or not isinstance(xy, list)
            or len(xy) != 2
            or not all(np.isfinite(xy))
            or not 0 <= xy[0] <= data["width"]
            or not 0 <= xy[1] <= data["height"]
        ):
            raise ValueError("Точка за пределами оригинала")
    manual["points"] = manual.get("points", {}) | points
    if "cohort" in changes:
        cohort = str(changes["cohort"]).strip()
        if len(cohort) > 100:
            raise ValueError("Название группы слишком длинное")
        manual["cohort"] = cohort
    if "head_angles" in changes:
        q = changes["head_angles"]
        if not isinstance(q, dict) or any(
            k not in ("yaw", "pitch", "roll")
            or not np.isfinite(v)
            or abs(float(v)) > 180
            for k, v in q.items()
        ):
            raise ValueError("Некорректные углы головы")
        manual["head_angles"] = {k: float(v) for k, v in q.items()}
        manual["angle_source"] = "manual"
    if "gaze_ok" in changes:
        if changes["gaze_ok"] is not None and not isinstance(changes["gaze_ok"], bool):
            raise ValueError("gaze_ok должен быть true/false/null")
        if changes["gaze_ok"] is None:
            manual.pop("gaze_ok", None)
        else:
            manual["gaze_ok"] = changes["gaze_ok"]
    if "reviewed" in changes:
        manual["reviewed"] = bool(changes["reviewed"])
    manual["updated"] = time.time()
    atomic_json(path, manual)
    return measure(p)


def batch(job, ids):
    done = []
    errors = []
    for i, id in enumerate(ids):
        job.update(i / max(1, len(ids)), f"Глаза: {i + 1}/{len(ids)}")
        try:
            r = measure(storage.photo(id), run=True)
            done.append({"id": id, "eligible": r["eligible"]})
        except Exception as e:
            errors.append({"id": id, "error": str(e)})
    return {
        "done": done,
        "errors": errors,
        "warning": "Автоматическая разметка требует проверки. Никаких выводов о личности или маске.",
    }


def report(group=None):
    rows = []
    for p in storage.read_db()["photos"]:
        if p.get("deleted_at") or (group and group != "__all" and p["group"] != group):
            continue
        try:
            r = measure(p)
            gaze = max(
                max(abs(e["gaze_x"]) / 0.16, abs(e["gaze_y"]) / 0.30) for e in r["eyes"]
            )
            frontal = max(
                abs(r["angles"][k]) / limit
                for k, limit in [("yaw", 8), ("pitch", 8), ("roll", 5)]
            )
            resolution = max(0, 1 - min(e["width_px"] for e in r["eyes"]) / 180)
            rows.append(
                {
                    **{
                        k: r[k]
                        for k in [
                            "id",
                            "name",
                            "group",
                            "cohort",
                            "date",
                            "angles",
                            "eligible",
                            "exclusion_reasons",
                            "reviewed",
                            "metrics",
                        ]
                    },
                    "frontal_score": round(float(frontal + gaze + resolution), 4),
                    "gaze_offset_score": round(float(gaze), 4),
                    "eye_width_px": round(min(e["width_px"] for e in r["eyes"]), 1),
                    "sharpness": r["sharpness"],
                }
            )
        except (FileNotFoundError, ValueError):
            continue
    closest = sorted(rows, key=lambda r: r["frontal_score"])
    for rank, r in enumerate(closest, 1):
        r["best_view_rank"] = rank
    accepted = sorted(
        (r for r in rows if r["eligible"]),
        key=lambda r: (r["cohort"] or "Без группы", r["frontal_score"]),
    )
    for rank, r in enumerate(accepted, 1):
        r["best_view_rank"] = rank
    groups = {}
    labeled = [r for r in accepted if r["cohort"]]
    for cohort in sorted({r["cohort"] for r in labeled}):
        subset = [r for r in labeled if r["cohort"] == cohort]
        events = {r["date"] or r["id"] for r in subset}
        stats = {}
        for key, *_ in CATALOG:
            x = np.array([r["metrics"][key] for r in subset])
            med = float(np.median(x))
            mad = float(np.median(abs(x - med)))
            stats[key] = {"median": med, "mad": mad, "n": len(x)}
        groups[cohort] = {
            "n": len(subset),
            "independent_dates": len(events),
            "reviewed": sum(r["reviewed"] for r in subset),
            "stats": stats,
        }
    return {
        "rows": sorted(
            rows, key=lambda r: (r["cohort"] or "Без группы", r["frontal_score"])
        ),
        "selected": [r["id"] for r in accepted],
        "closest": [r["id"] for r in closest[:25]],
        "groups": groups,
        "catalog": [
            {"id": k, "title": v, "unit": u, "description": d} for k, v, u, d in CATALOG
        ],
        "warning": "Сопоставляйте только одинаковые ракурсы, взгляд, выражение и сопоставимое разрешение. Малые выборки и заданное K кластеров не доказывают три личности или накладку.",
        "selection": "yaw/pitch ±8°, roll ±5°, взгляд ±0.16W / ±0.30H; глаз ≥45 px, радужка ≥10 px; без явного моргания",
        "can_compare_three_groups": len(groups) >= 3
        and all(
            g["independent_dates"] >= 5 and g["reviewed"] >= 5 for g in groups.values()
        ),
    }
