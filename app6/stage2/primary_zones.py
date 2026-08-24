"""🎯 CRITICAL → Primary-зоны Stage 2: области private-гипотез, не сетка 3×3.

Primary остаётся главным каналом. Карта зон берётся из `mesh_zone_indices.json`
и вершинных индексов ландмарков (`ldm*_vertex_indices`). Это те же именованные
области, что в карантинном ledger: орбиты, надбровья, переносица, скулы,
подбородок, лоб, углы челюсти.

Мимика не выкидывает пару и не трогает эти зоны: обнуляются только мягкие
ткани (`cheek_soft`, `nose_wing`, `jaw_L/R`).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import numpy as np

from .expression_qc import BONE_ZONES, MIMIC_ZONES, exclude_mimic_zones
from .mesh_dense import load_anatomical_zones

PRIMARY_ZONES_SCHEMA: Final[str] = "deeputin-primary-hypothesis-zones-v1.0"

PRIMARY_HYPOTHESIS_ZONES: Final[tuple[str, ...]] = (
    "orbit_L", "orbit_R",
    "brow_ridge_L", "brow_ridge_R",
    "nose_bridge_tip",
    "cheekbone_L", "cheekbone_R",
    "chin",
    "forehead",
    "jaw_angle_L", "jaw_angle_R",
)

PRIMARY_ZONE_WEIGHTS: Final[dict[str, float]] = {
    "orbit_L": 1.2, "orbit_R": 1.2,
    "brow_ridge_L": 1.1, "brow_ridge_R": 1.1,
    "nose_bridge_tip": 1.2,
    "cheekbone_L": 1.0, "cheekbone_R": 1.0,
    "chin": 1.0,
    "forehead": 1.0,
    "jaw_angle_L": 0.9, "jaw_angle_R": 0.9,
}

UNASSIGNED_ZONE: Final[str] = "unassigned"


@lru_cache(maxsize=1)
def _vertex_to_zone() -> dict[int, str]:
    mapping: dict[int, str] = {}
    for zone, ids in load_anatomical_zones().items():
        for vid in ids.tolist():
            mapping[int(vid)] = str(zone)
    return mapping


def _load_landmark_vertex_indices(record: Any, landmark_count: int) -> np.ndarray | None:
    directory = getattr(record, "record_dir", None)
    if not directory:
        return None
    path = Path(directory) / "reconstruction.npz"
    if not path.is_file():
        return None
    key = f"ldm{landmark_count}_vertex_indices"
    try:
        with np.load(path, allow_pickle=False) as z:
            if key not in z.files:
                return None
            return np.asarray(z[key], dtype=np.int64).reshape(-1)
    except (OSError, ValueError, KeyError):
        return None


def build_anatomical_landmark_zone_map(
    records: list[Any],
    landmark_count: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Именованная зона на каждый ландмарк по вершине BFM."""
    if landmark_count not in (106, 134):
        raise ValueError(f"unsupported landmark_count: {landmark_count}")
    vertex_map = _vertex_to_zone()
    indices = None
    source_id = None
    for record in records:
        indices = _load_landmark_vertex_indices(record, landmark_count)
        if indices is not None and indices.size == landmark_count:
            source_id = getattr(record, "record_id", None)
            break
    if indices is None or indices.size != landmark_count:
        labels = np.full(landmark_count, UNASSIGNED_ZONE, dtype=object)
        return labels, {
            "schema": PRIMARY_ZONES_SCHEMA,
            "version": "anatomical-landmark-map-v1",
            "landmark_count": landmark_count,
            "status": "missing_vertex_indices",
            "assigned_count": 0,
            "primary_zones": list(PRIMARY_HYPOTHESIS_ZONES),
        }
    labels = np.array(
        [vertex_map.get(int(vid), UNASSIGNED_ZONE) for vid in indices],
        dtype=object,
    )
    counts: dict[str, int] = {}
    for name in labels.tolist():
        counts[str(name)] = counts.get(str(name), 0) + 1
    return labels, {
        "schema": PRIMARY_ZONES_SCHEMA,
        "version": "anatomical-landmark-map-v1",
        "landmark_count": landmark_count,
        "status": "ok",
        "source_record_id": source_id,
        "assigned_count": int(sum(1 for name in labels if name != UNASSIGNED_ZONE)),
        "zone_counts": counts,
        "primary_zones": list(PRIMARY_HYPOTHESIS_ZONES),
        "mimic_zones": sorted(MIMIC_ZONES),
        "bone_zones": sorted(BONE_ZONES),
    }


def pair_expression_active(meta_a: dict[str, Any], meta_b: dict[str, Any]) -> bool:
    return bool(
        meta_a.get("smile_detected") or meta_b.get("smile_detected")
        or meta_a.get("jaw_open_detected") or meta_b.get("jaw_open_detected")
    )


def expression_zone_policy(
    landmarks: np.ndarray | None,
    *,
    smile_detected: bool = False,
    jaw_open_detected: bool = False,
) -> dict[str, Any]:
    weights = {
        zone: float(PRIMARY_ZONE_WEIGHTS.get(zone, 1.0))
        for zone in (*PRIMARY_HYPOTHESIS_ZONES, *sorted(MIMIC_ZONES), *sorted(BONE_ZONES))
    }
    if landmarks is not None:
        try:
            result = exclude_mimic_zones(landmarks, weights)
            if smile_detected or jaw_open_detected:
                result["expression"]["expression_active"] = True
            return result
        except ValueError:
            pass
    active = bool(smile_detected or jaw_open_detected)
    excluded = sorted(MIMIC_ZONES) if active else []
    adjusted = dict(weights)
    for zone in excluded:
        adjusted[zone] = 0.0
    return {
        "schema": PRIMARY_ZONES_SCHEMA,
        "zone_weights": adjusted,
        "expression": {
            "expression_active": active,
            "smile_detected": bool(smile_detected),
            "jaw_open_detected": bool(jaw_open_detected),
        },
        "excluded_zones": excluded,
        "bone_zones_preserved": sorted(BONE_ZONES),
        "policy": "mimic zones zeroed; primary hypothesis zones never modified",
    }


def primary_zone_aggregate(
    zones: list[dict[str, Any]],
    zone_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    weights = zone_weights or {}
    used: list[dict[str, Any]] = []
    num = 0.0
    den = 0.0
    for zone in zones:
        name = str(zone.get("zone") or "")
        if name not in PRIMARY_HYPOTHESIS_ZONES:
            continue
        if zone.get("status") != "measured":
            continue
        try:
            rmse_f = float(zone.get("rmse"))
        except (TypeError, ValueError):
            continue
        if not np.isfinite(rmse_f):
            continue
        weight = float(weights.get(name, PRIMARY_ZONE_WEIGHTS.get(name, 1.0)))
        if weight <= 0:
            continue
        num += rmse_f * weight
        den += weight
        used.append({"zone": name, "rmse": rmse_f, "weight": weight})
    if den <= 0:
        return {
            "schema": PRIMARY_ZONES_SCHEMA,
            "status": "insufficient_primary_zones",
            "primary_zone_rmse": float("nan"),
            "primary_zone_count": 0,
            "zones": used,
        }
    return {
        "schema": PRIMARY_ZONES_SCHEMA,
        "status": "measured",
        "primary_zone_rmse": float(num / den),
        "primary_zone_count": len(used),
        "zones": used,
    }
