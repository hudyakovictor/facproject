"""📐 Каноническая юстировка моделей для 3D-морфинга.

`vertices_identity_only` приходит из `MorphableModel.compute_shape`, который
возвращает вершины «without rotation or translation»: поза фото уже вынесена в
отдельные параметры `angles_deg`/`translation`. Значит identity-сетка и так живёт в
каноническом объектном пространстве 3DMM, и юстировка — это только центрирование и
нормировка масштаба.

Дополнительный поворот в «канон бина» ракурс не убирает, а добавляет: на калибровке
`/Volumes/SDCARD/calibration_rakurs` (person_02/frontal, Δyaw = 5.5°) средняя разница
сетки без поворота была 0.0050 и с поворотом в канон — 0.0508, то есть коррекция
увеличивала меряемую «разницу лиц» в 10 раз. Коррелация |Δyaw| с разницей по всем
449 парам равна +1.00 — весь сигнал задавала именно доворачиваемая поза.

Ракурс при этом определяется и отдаётся в отчёт: сравнение осмысленно между фото
одного бина, для разных включается предупреждение «ракурсы не совпадают», а эталон
reconstruction-шума берётся по бину (`pose_noise_model`).

О названии: `align_identity_mesh` ничего не поворачивает и не выравнивает — функция
только центрирует сетку и приводит её масштаб к единице. С патча 04 масштаб считается
по RMS на 106 ландмарках (та же функция нормировки в прод-пайплайне и в app9/validation),
а не по максимальному радиусу на 35 709 вершинах: единичный максимум — это одна крайняя
точка, и из кадра в кадр она гуляет (отношение двух масштабов: медиана 1.0252,
min..max 0.6494..1.5518 — хвост прыгает на 35–55% из-за одной вершины). Средний квадрат
по 106 точкам устойчивее, и абсолютные расстояния становятся сопоставимы между продом
и валидацией.
Отсюда следует, что мерить «долю снятого этой функцией ракурса» некорректно: в
identity-сетке позы никогда не было, а отношение d_canon/d_cam в основном показывает
размер самого поворота в камерном базисе. Содержательная метрика — отношение разницы
наклонного кадра к шумовому полу ровных кадров того же человека (app9/validation).
"""
from __future__ import annotations
from typing import Any

import numpy as np

from app8.geometry import classify_pose


def pose_summary(recon_data: dict[str, Any]) -> dict[str, Any]:
    """Углы фото и бин ракурса, канонический yaw этого бина."""
    angles = np.asarray(recon_data["angles_deg"], dtype=np.float32)
    yaw = float(angles[1])
    pose_bin, canonical_yaw = classify_pose(yaw)
    return {
        "angles_deg": [round(float(value), 4) for value in angles],
        "yaw": round(yaw, 4),
        "pose_bin": pose_bin,
        "canonical_yaw": float(canonical_yaw),
    }


def group_pose_reference(recon_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Общий ориентир группы: бин, в который попадает медианный yaw.

    Сетки в группу не доворачиваются (см. docstring модуля) — медианный бин нужен,
    чтобы понять, какой ракурс группа представляет, и взять шумовую справку по нему.
    """
    yaws = [float(np.asarray(r["angles_deg"], np.float32)[1]) for r in recon_results]
    median_yaw = float(np.median(yaws))
    pose_bin, canonical_yaw = classify_pose(median_yaw)
    return {
        "median_yaw": round(median_yaw, 4),
        "pose_bin": pose_bin,
        "canonical_yaw": float(canonical_yaw),
    }


def normalize_ldm106(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Единственная нормировка identity-метрик: центр по 106 точкам, масштаб = RMS по ним же.

    Возвращает (нормированные точки (106, 3) float32, центр (3,), масштаб float).
    RMS вместо максимального радиуса: максимум задаёт одна крайняя точка, и из кадра в
    кадр она гуляет на десятки процентов; средний квадрат по всем 106 устойчив. Эту же
    функцию вызывает валидация (app9/validation), поэтому прод и замеры живут в одних
    единицах.
    """
    p = np.asarray(points, np.float64)
    if p.ndim != 2 or p.shape[1] != 3 or p.shape[0] < 2:
        raise ValueError("points must have shape (N,3) with N >= 2")
    center = p.mean(axis=0)
    p = p - center
    s = float(np.sqrt(np.mean(np.sum(p * p, axis=1))))
    if not np.isfinite(s) or s < 1e-6:
        raise ValueError("invalid landmark RMS scale")
    return (p / s).astype(np.float32), center, s


#: Во сколько раз боевой масштаб (RMS по 106 ландмаркам) меньше прежнего
#: (max-радиус по всем 35 709 вершинам), то есть во сколько раз вырастают абсолютные
#: расстояния при переходе на нормировку патча 04. Измерено на 12 подряд идущих кадрах
#: `/Volumes/SDCARD/calibration_rakurs/person_01/frontal`: медиана 1.5640,
#: min..max 1.5551..1.5705; по 106 точкам тех же кадров коэффициент 1.56–1.64 (T4 в
#: `app9/validation/advisor_tests.py`). Нужен только чтобы перезаписать исторические пороги,
#: заданные числами в старых единицах; всё, что берётся из калибровочных артефактов,
#: пересчитывается само, а для эвристической шкалы похожести разброс в пара процентов не
#: значим.
MAXR_TO_RMS106 = 1.564


def align_identity_mesh(recon_data: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, float]:
    """Юстирует identity-сетку в канон 3DMM: центр и RMS-масштаб по 106 ландмаркам.

    Returns:
        tuple: (нормализованные вершины (N, 3), 106 канонических точек (106, 3),
        RMS-масштаб до нормировки в модельных единицах)
    """
    # Чистая форма лица без мимики; мимика намеренно исключена из сравнения формы.
    v = np.asarray(recon_data["vertices_identity_only"], dtype=np.float32)
    ldm106_idx = np.asarray(recon_data["ldm106_indices"], dtype=np.int64)

    # Инвариантная нормировка: центр и RMS по 106 точкам, тот же центр/масштаб всей сетке.
    ldm106_pts, center, scale = normalize_ldm106(v[ldm106_idx])
    v_aligned = ((v - center.astype(np.float32)) / scale).astype(np.float32)

    return v_aligned, ldm106_pts, scale


def pose_alignment_report(
    recon_results: list[dict[str, Any]],
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Описание группы фото: общий бин ракурса и несовпадение ракурсов."""
    per_photo = [pose_summary(result) for result in recon_results]
    distinct_bins = sorted({photo["pose_bin"] for photo in per_photo})
    mismatch = len(distinct_bins) > 1
    spread = max(photo["yaw"] for photo in per_photo) - min(photo["yaw"] for photo in per_photo)
    warning = None
    if mismatch:
        warning = (
            "Ракурсы не совпадают: "
            + ", ".join(f"{photo['pose_bin']} ({photo['yaw']:+.1f}°)" for photo in per_photo)
            + " — форма из разного ракурса восстанавливается с собственным смещением, "
            "сравнивайте фото одного ракурса."
        )
    elif spread > 10.0:
        warning = (
            f"Ракурсы в пределах одного бина, но разброс по yaw {spread:.1f}° — "
            "метрика растёт в основном из-за этого разброса, а не из-за формы лица."
        )
    return {
        "aligned_to": "identity_object_space",
        "canonical_bin": reference["pose_bin"],
        "canonical_yaw": reference["canonical_yaw"],
        "median_yaw": reference["median_yaw"],
        "per_photo": per_photo,
        "distinct_bins": distinct_bins,
        "same_pose_bin": not mismatch,
        "yaw_spread_deg": round(float(spread), 4),
        "warning": warning,
    }
