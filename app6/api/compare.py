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

from .demo_data import DemoPhoto

COMPARE_SCHEMA = "deeputin-api-compare-v1.0"


def photo_to_record(photo: DemoPhoto) -> Record:
    return photo.record


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

    points = []
    for i in range(a.ldm134.shape[0]):
        if not common134[i]:
            continue
        residual = float(np.linalg.norm(aligned_b[i] - a.ldm134[i]))
        points.append({
            "index": i,
            "x": float(a.ldm134[i, 0]), "y": float(a.ldm134[i, 1]), "z": float(a.ldm134[i, 2]),
            "residual": residual,
        })
    result["heatmap_points"] = points
    if points:
        residuals = np.array([p["residual"] for p in points])
        result["heatmap_stats"] = {
            "min": float(residuals.min()), "max": float(residuals.max()),
            "median": float(np.median(residuals)), "p95": float(np.percentile(residuals, 95)),
        }
    return result
