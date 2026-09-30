"""Batch comparison utilities for aligned dense face meshes.

The module deliberately reports distances, ranks and descriptive uncertainty;
it does not turn geometric scores into person-identity probabilities.
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from morphing.backend.analysis import similarity_metrics, zone_ranges


def _validate_meshes(meshes: Sequence[np.ndarray], labels: Sequence[str] | None = None) -> tuple[list[np.ndarray], list[str]]:
    if not 2 <= len(meshes) <= 32:
        raise ValueError("batch comparison requires between 2 and 32 meshes")
    arrays = [np.asarray(mesh, dtype=np.float64) for mesh in meshes]
    first = arrays[0]
    if first.ndim != 2 or first.shape[1] != 3:
        raise ValueError("each mesh must have shape (N, 3)")
    if first.shape[0] < 7:
        raise ValueError("each mesh must contain at least seven vertices")
    if not np.isfinite(first).all():
        raise ValueError("mesh coordinates must be finite")
    for index, mesh in enumerate(arrays[1:], start=1):
        if mesh.shape != first.shape:
            raise ValueError(f"mesh {index} has a different topology shape")
        if not np.isfinite(mesh).all():
            raise ValueError(f"mesh {index} contains non-finite coordinates")
    names = list(labels) if labels is not None else [f"Face {i + 1}" for i in range(len(arrays))]
    if len(names) != len(arrays):
        raise ValueError("labels must match the mesh count")
    return arrays, [str(name) for name in names]


def _pair_matrices(meshes: list[np.ndarray]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    count = len(meshes)
    mean_distance = np.zeros((count, count), dtype=np.float64)
    cosine = np.eye(count, dtype=np.float64)
    zone_keys = list(zone_ranges(len(meshes[0])))
    zone_distances = {key: np.zeros((count, count), dtype=np.float64) for key in zone_keys}
    for left in range(count):
        for right in range(left + 1, count):
            metrics = similarity_metrics(meshes[left], meshes[right])
            mean_distance[left, right] = mean_distance[right, left] = metrics["euclidean_mean"]
            cosine[left, right] = cosine[right, left] = metrics["cosine_similarity"]
            for key in zone_keys:
                distance = metrics["zones"].get(key, {}).get("mean_delta", 0.0)
                zone_distances[key][left, right] = zone_distances[key][right, left] = distance
    return mean_distance, {"cosine_similarity": cosine, **zone_distances}


def _robust_z(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    scale = 1.4826 * mad
    if scale <= 1e-12:
        return np.zeros_like(values)
    return (values - median) / scale


def similarity_matrix(meshes: Sequence[np.ndarray], labels: Sequence[str] | None = None) -> dict[str, Any]:
    """Build symmetric distance and cosine matrices with peer outlier ranks."""
    arrays, names = _validate_meshes(meshes, labels)
    distances, auxiliary = _pair_matrices(arrays)
    count = len(arrays)
    peer_means = np.asarray([
        float(np.mean(np.delete(distances[index], index)))
        for index in range(count)
    ])
    outlier_z = _robust_z(peer_means)
    order = np.argsort(peer_means)[::-1]
    rows = []
    for index in order:
        rows.append({
            "index": int(index),
            "label": names[int(index)],
            "mean_distance_to_peers": round(float(peer_means[index]), 8),
            "robust_outlier_z": round(float(outlier_z[index]), 4),
            "is_geometric_outlier": bool(outlier_z[index] >= 2.5),
        })
    return {
        "schema": "facproject-morphing-batch-v1",
        "count": count,
        "labels": names,
        "mean_distance_matrix": np.round(distances, 8).tolist(),
        "cosine_similarity_matrix": np.round(auxiliary.pop("cosine_similarity"), 8).tolist(),
        "regional_distance_matrices": {key: np.round(value, 8).tolist() for key, value in auxiliary.items()},
        "peer_outlier_ranking": rows,
        "interpretation": "descriptive geometric distances; outlier ranking is not an identity decision",
        "limitations": [
            "All meshes must share a topology and canonical coordinate system.",
            "Pose, expression, lighting and reconstruction error can affect geometric distances.",
            "Small batches provide unstable robust-outlier estimates.",
        ],
    }


def bootstrap_mean_interval(
    values: Sequence[float] | np.ndarray,
    *,
    confidence: float = 0.95,
    iterations: int = 2000,
    seed: int = 0,
) -> dict[str, float | int]:
    """Return a deterministic percentile bootstrap interval for a mean.

    This generic helper is intended for descriptive resampling. For face meshes,
    resampling vertices ignores spatial dependence and therefore does not yield
    a calibrated confidence interval for identity or population inference.
    """
    data = np.asarray(values, dtype=np.float64).reshape(-1)
    if data.size == 0 or not np.isfinite(data).all():
        raise ValueError("bootstrap values must be a non-empty finite sequence")
    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence must be between 0.5 and 1")
    if iterations < 100:
        raise ValueError("iterations must be at least 100")
    if iterations > 20000:
        raise ValueError("iterations must not exceed 20000")
    rng = np.random.default_rng(seed)
    # Bound temporary memory: a dense face can have tens of thousands of
    # vertices, so allocating [iterations, vertices] would be wasteful.
    means = np.empty(iterations, dtype=np.float64)
    chunk_size = max(1, min(128, iterations))
    for start in range(0, iterations, chunk_size):
        stop = min(start + chunk_size, iterations)
        sampled_indices = rng.integers(0, data.size, size=(stop - start, data.size))
        means[start:stop] = np.mean(data[sampled_indices], axis=1)
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return {
        "mean": round(float(np.mean(data)), 8),
        "lower": round(float(low), 8),
        "upper": round(float(high), 8),
        "confidence": float(confidence),
        "iterations": int(iterations),
        "sample_count": int(data.size),
        "method": "percentile bootstrap over supplied observations",
        "calibration": "descriptive only; does not model vertex spatial dependence",
    }


def regional_displacement_intervals(
    vertices_a: np.ndarray,
    vertices_b: np.ndarray,
    *,
    confidence: float = 0.95,
    iterations: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    """Summarize per-zone displacement with deterministic bootstrap ranges."""
    a = np.asarray(vertices_a, dtype=np.float64)
    b = np.asarray(vertices_b, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 3 or len(a) < 7:
        raise ValueError("vertices must be matching arrays with shape (N, 3)")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("mesh coordinates must be finite")
    displacement = np.linalg.norm(a - b, axis=1)
    results = {}
    for index, (name, (start, end)) in enumerate(zone_ranges(len(a)).items()):
        results[name] = bootstrap_mean_interval(
            displacement[start:end],
            confidence=confidence,
            iterations=iterations,
            seed=seed + index,
        )
    return {
        "zones": results,
        "interpretation": "descriptive resampling interval across mesh vertices; not a calibrated population confidence interval",
    }


def timeline_speed_summary(years: Sequence[float], meshes: Sequence[np.ndarray]) -> dict[str, Any]:
    """Calculate adjacent and overall geometric change rates per year."""
    arrays, names = _validate_meshes(meshes)
    dates = np.asarray(years, dtype=np.float64)
    if dates.shape != (len(arrays),) or not np.isfinite(dates).all():
        raise ValueError("years must be a finite value for each mesh")
    if np.any(np.diff(dates) <= 0):
        raise ValueError("years must be strictly increasing")
    segments = []
    for index in range(len(arrays) - 1):
        metrics = similarity_metrics(arrays[index], arrays[index + 1])
        span = float(dates[index + 1] - dates[index])
        segments.append({
            "from": names[index],
            "to": names[index + 1],
            "year_span": span,
            "mean_displacement_per_year": round(metrics["euclidean_mean"] / span, 8),
            "l2_displacement_per_year": round(metrics["euclidean_distance"] / span, 8),
            "zone_mean_displacement_per_year": {
                zone: round(item["mean_delta"] / span, 8)
                for zone, item in metrics["zones"].items()
            },
        })
    endpoints = similarity_metrics(arrays[0], arrays[-1])
    full_span = float(dates[-1] - dates[0])
    return {
        "years": dates.tolist(),
        "segments": segments,
        "overall": {
            "year_span": full_span,
            "mean_displacement_per_year": round(endpoints["euclidean_mean"] / full_span, 8),
            "l2_displacement_per_year": round(endpoints["euclidean_distance"] / full_span, 8),
        },
        "interpretation": "geometric change rate; does not identify the cause of change",
    }
