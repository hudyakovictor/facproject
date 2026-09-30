"""Topology-aware anatomical region utilities.

The 3DMM shipped with facproject is ordered consistently, but an index range
alone is too easy to misuse.  This module keeps region definitions, labels,
weights and aggregation in one place and makes every output auditable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np


@dataclass(frozen=True)
class RegionSpec:
    key: str
    title: str
    start_fraction: float
    end_fraction: float
    weight: float
    side: str = "midline"
    description: str = ""

    def bounds(self, vertex_count: int) -> tuple[int, int]:
        start = int(round(vertex_count * self.start_fraction))
        end = int(round(vertex_count * self.end_fraction))
        return start, max(start + 1, end)

    def to_dict(self, vertex_count: int | None = None) -> dict[str, Any]:
        payload = {
            "key": self.key,
            "title": self.title,
            "weight": self.weight,
            "side": self.side,
            "description": self.description,
            "start_fraction": self.start_fraction,
            "end_fraction": self.end_fraction,
        }
        if vertex_count is not None:
            payload["bounds"] = list(self.bounds(vertex_count))
        return payload


REGION_SPECS: tuple[RegionSpec, ...] = (
    RegionSpec("forehead", "Forehead", 0.000, 0.084, 0.10, "midline", "upper frontal contour"),
    RegionSpec("left_eye", "Left orbital zone", 0.084, 0.196, 0.09, "left", "left periocular contour"),
    RegionSpec("right_eye", "Right orbital zone", 0.196, 0.308, 0.09, "right", "right periocular contour"),
    RegionSpec("nose", "Nose", 0.308, 0.476, 0.22, "midline", "nasal bridge and tip"),
    RegionSpec("left_cheek", "Left cheek", 0.476, 0.644, 0.10, "left", "left zygomatic region"),
    RegionSpec("right_cheek", "Right cheek", 0.644, 0.812, 0.10, "right", "right zygomatic region"),
    RegionSpec("mouth_chin", "Mouth and chin", 0.812, 1.000, 0.30, "midline", "perioral and mandibular contour"),
)

REGION_BY_KEY = {spec.key: spec for spec in REGION_SPECS}


def specs() -> tuple[RegionSpec, ...]:
    return REGION_SPECS


def bounds_for(vertex_count: int) -> dict[str, tuple[int, int]]:
    if vertex_count < len(REGION_SPECS):
        raise ValueError("vertex_count is too small for anatomical regions")
    return {spec.key: spec.bounds(vertex_count) for spec in REGION_SPECS}


def normalize_weights(weights: Mapping[str, float] | None = None) -> dict[str, float]:
    unknown = set(weights or {}) - set(REGION_BY_KEY)
    if unknown:
        raise ValueError(f"unknown region weight keys: {', '.join(sorted(unknown))}")
    raw = {spec.key: float((weights or {}).get(spec.key, spec.weight)) for spec in REGION_SPECS}
    if any(not np.isfinite(value) or value < 0 for value in raw.values()):
        raise ValueError("region weights must be finite and non-negative")
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("at least one region weight must be positive")
    return {key: value / total for key, value in raw.items()}


def split_indices(vertex_count: int, region_keys: Iterable[str] | None = None) -> dict[str, np.ndarray]:
    wanted = list(region_keys) if region_keys is not None else [spec.key for spec in REGION_SPECS]
    bounds = bounds_for(vertex_count)
    output: dict[str, np.ndarray] = {}
    for key in wanted:
        if key not in bounds:
            raise KeyError(f"unknown anatomical region: {key}")
        start, end = bounds[key]
        output[key] = np.arange(start, end, dtype=np.int64)
    return output


def region_statistics(values: np.ndarray, vertex_count: int | None = None) -> dict[str, dict[str, float]]:
    """Aggregate a per-vertex scalar or vector magnitude by region."""
    array = np.asarray(values)
    if array.ndim == 2:
        if array.shape[1] != 3:
            raise ValueError("vector values must have shape (N, 3)")
        array = np.linalg.norm(array, axis=1)
    if array.ndim != 1:
        raise ValueError("values must have shape (N,) or (N, 3)")
    if len(array) < len(REGION_SPECS) or not np.isfinite(array).all():
        raise ValueError("values must contain at least seven finite vertices")
    count = vertex_count or len(array)
    if count != len(array):
        raise ValueError("vertex_count must match the value length")
    result: dict[str, dict[str, float]] = {}
    for spec in REGION_SPECS:
        start, end = spec.bounds(count)
        segment = array[start:end].astype(np.float64)
        result[spec.key] = {
            "mean": round(float(np.mean(segment)), 8),
            "median": round(float(np.median(segment)), 8),
            "p95": round(float(np.percentile(segment, 95)), 8),
            "max": round(float(np.max(segment)), 8),
            "vertex_count": int(len(segment)),
            "weight": spec.weight,
        }
    return result


def rank_regions(statistics: Mapping[str, Mapping[str, float]], metric: str = "mean", descending: bool = True) -> list[dict[str, Any]]:
    rows = []
    for key, value in statistics.items():
        if key not in REGION_BY_KEY:
            continue
        rows.append({"region": key, "title": REGION_BY_KEY[key].title, metric: float(value.get(metric, 0.0)), **dict(value)})
    return sorted(rows, key=lambda row: row.get(metric, 0.0), reverse=descending)


def weighted_score(statistics: Mapping[str, Mapping[str, float]], value_key: str = "similarity", weights: Mapping[str, float] | None = None) -> float:
    normalized = normalize_weights(weights)
    available = [(key, float(value.get(value_key, 0.0))) for key, value in statistics.items() if key in normalized]
    if not available:
        return 0.0
    total = sum(normalized[key] for key, _ in available)
    return float(sum(normalized[key] * value for key, value in available) / (total or 1.0))


def region_registry(vertex_count: int | None = None) -> dict[str, Any]:
    return {
        "schema": "facproject-morphing-regions-v1",
        "regions": [spec.to_dict(vertex_count) for spec in REGION_SPECS],
        "weights": normalize_weights(),
        "vertex_count": vertex_count,
    }
