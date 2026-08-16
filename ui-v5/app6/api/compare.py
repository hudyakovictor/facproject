"""🎯 CRITICAL → Реальное попарное сравнение двух фото для `/api/v1/compare`.

Использует тот же `app6.stage2.core.compare_landmarks`, что и Stage 2, чтобы
раздел "Сравнение" в интерфейсе не был отдельной, потенциально расходящейся
реализацией. Возвращает не только агрегированные метрики, но и per-vertex
residual (после Kabsch-выравнивания), достаточный для честной тепловой карты
без хардкода зон — та же геометрия, что видит исследователь.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app6.stage2.core import Record, build_coordinate_zone_map, compare_landmarks, robust_rigid_align
from app6.stage2.anchor_policy import stable_anchor_mask

from .bfm_topology import is_bfm_available, load_bfm_model
COMPARE_SCHEMA = "deeputin-api-compare-v1.0"


def compare_records(a: Record, b: Record) -> dict[str, Any]:
    """🔍 QUERY → Полное сравнение пары записей: агрегаты + per-point heatmap data.

    Возвращает `status` (тот же словарь состояний, что и Stage 2:
    `measured`, `pose_mismatch`, `residual_pose_mismatch`,
    `insufficient_visibility`), метрики, зоны и point-level residual в
    пространстве A (после робастного Kabsch-выравнивания B→A) для рендера
    тепловой карты на фронтенде.
    """
    zone106, _ = build_coordinate_zone_map([a, b], 106)
    zone134, _ = build_coordinate_zone_map([a, b], 134)
    comparison = compare_landmarks(a, b, zone106, zone134)

    result: dict[str, Any] = {
        "schema": COMPARE_SCHEMA,
        "status": comparison.status,
        "metrics": comparison.metrics,
        "zones": comparison.zones,
        "diagnostics": {k: v for k, v in comparison.diagnostics.items()
                        if not isinstance(v, np.ndarray)},
        "not_a_verdict": True,
        "heatmap_points": [],
    }
    if comparison.status != "measured":
        return result

    common134 = np.asarray(a.visible134, bool) & np.asarray(b.visible134, bool)
    anchor134, _ = stable_anchor_mask(a.ldm134, common134, min_count=30)
    _, rotation, translation, _ = robust_rigid_align(b.ldm134[anchor134], a.ldm134[anchor134])
    aligned_b = b.ldm134 @ rotation + translation

    # Координатные зоны точек: НЕ анатомические метки (см. build_coordinate_zone_map).
    zone_labels = zone134

    points = []
    for i in range(a.ldm134.shape[0]):
        if not common134[i]:
            # Невидимая в одном из кадров точка не выбрасывается молча:
            # интерфейс обязан показать её как "нет данных", иначе исчезнувшие
            # точки читаются как "совпали" (`app6/AGENTS.md`).
            points.append({
                "index": i, "visible": False, "residual": None,
                "x": None, "y": None, "z": None,
                "bx": None, "by": None, "bz": None,
                "dx": None, "dy": None, "dz": None,
                "zone": str(zone_labels[i]) if i < len(zone_labels) else None,
            })
            continue
        delta = aligned_b[i] - a.ldm134[i]
        residual = float(np.linalg.norm(delta))
        points.append({
            "index": i, "visible": True,
            "x": float(a.ldm134[i, 0]), "y": float(a.ldm134[i, 1]), "z": float(a.ldm134[i, 2]),
            # Позиция точки B ПОСЛЕ Kabsch-выравнивания в систему координат A.
            # Нужна фронтенду для линейной интерполяции A→B (морфинг точек).
            "bx": float(aligned_b[i, 0]), "by": float(aligned_b[i, 1]), "bz": float(aligned_b[i, 2]),
            # Знаковое смещение по осям: показывает НАПРАВЛЕНИЕ ухода точки.
            "dx": float(delta[0]), "dy": float(delta[1]), "dz": float(delta[2]),
            "residual": residual,
            "zone": str(zone_labels[i]) if i < len(zone_labels) else None,
        })
    result["heatmap_points"] = points
    result["landmark_count"] = int(a.ldm134.shape[0])
    result["visible_point_count"] = int(common134.sum())
    result["zone_policy"] = "coordinate-grid-v1: НЕ анатомические метки"
    measured = [p for p in points if p["visible"]]
    if measured:
        residuals = np.array([p["residual"] for p in measured])
        result["heatmap_stats"] = {
            "min": float(residuals.min()), "max": float(residuals.max()),
            "median": float(np.median(residuals)), "p95": float(np.percentile(residuals, 95)),
        }
    return result


def full_mesh_compare(photo_a: Record, photo_b: Record) -> dict[str, Any] | None:
    """📤 Полное BFM-сравнение (35 709 вершин) для 3D Inspector-режима морфинга.

    Реконструирует identity-форму каждого carrier'а (`alpha_exp=0` — костная
    форма без мимики, соответствует принципу "фокус на костных структурах,
    независимых от выражения" из `aboutplatform.txt`), выравнивает B→A по
    Kabsch на всём множестве вершин и возвращает per-vertex residual вместе с
    подлинной топологией треугольников — для рендера настоящего меша, а не
    landmark-подмножества.

    Returns:
        `None`, если BFM-геометрия недоступна в этом окружении (вызывающий
        код должен деградировать до landmark-уровневого `compare_records`,
        а не выдумывать полный меш).
    """
    if not is_bfm_available():
        return None
    bfm = load_bfm_model()
    if not (np.isfinite(photo_a.alpha_id).all() and np.isfinite(photo_b.alpha_id).all()):
        return None
    shape_a = bfm.compute_shape(photo_a.alpha_id, np.zeros(64, np.float32)).astype(np.float64)
    shape_b = bfm.compute_shape(photo_b.alpha_id, np.zeros(64, np.float32)).astype(np.float64)

    _, rotation, translation, _ = robust_rigid_align(shape_b, shape_a)
    aligned_b = shape_b @ rotation + translation
    residuals = np.linalg.norm(aligned_b - shape_a, axis=1)

    return {
        "schema": COMPARE_SCHEMA + "-full-mesh",
        "vertex_count": int(shape_a.shape[0]),
        "triangle_count": int(bfm.triangles.shape[0]),
        "vertices_a": shape_a.astype(np.float32).tolist(),
        "vertices_b_aligned": aligned_b.astype(np.float32).tolist(),
        "residuals": residuals.astype(np.float32).tolist(),
        "triangles": bfm.triangles.tolist(),
        "primary_zone_ids": bfm.primary_zone_ids,
        "primary_zone_names": bfm.primary_zone_names,
        "primary_triangle_zone": bfm.primary_triangle_zone.tolist(),
        "residual_stats": {
            "min": float(residuals.min()), "max": float(residuals.max()),
            "median": float(np.median(residuals)), "p95": float(np.percentile(residuals, 95)),
        },
        "not_a_verdict": True,
        "note": (
            "Identity-only reconstruction (alpha_exp=0): костная форма без мимики. "
            "Полная топология BFM (не landmark-подмножество). vertices_b_aligned — "
            "форма B после Kabsch-выравнивания в систему координат A, готова для "
            "линейной интерполяции (морфинга) A→B на фронтенде."
        ),
    }

