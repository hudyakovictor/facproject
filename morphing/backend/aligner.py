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
только центрирует сетку и приводит её масштаб к единичному краниометрическому радиусу.
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


def align_identity_mesh(recon_data: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, float]:
    """Юстирует identity-сетку в канон 3DMM: центр в (0,0,0), краниометрический радиус = 1.

    Returns:
        tuple: (нормализованные вершины (N, 3), 106 канонических точек (106, 3), радиус до нормировки)
    """
    # Чистая форма лица без мимики; мимика намеренно исключена из сравнения формы.
    v_aligned = np.asarray(recon_data["vertices_identity_only"], dtype=np.float32)

    # Выравнивание центра черепа в (0, 0, 0).
    v_aligned = v_aligned - np.mean(v_aligned, axis=0)

    # Инвариантная нормализация масштаба по краниометрическому радиусу.
    scale = float(np.max(np.linalg.norm(v_aligned, axis=1)))
    if scale > 1e-4:
        v_aligned /= scale

    ldm106_idx = np.asarray(recon_data["ldm106_indices"], dtype=np.int64)
    ldm106_pts = v_aligned[ldm106_idx]

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
