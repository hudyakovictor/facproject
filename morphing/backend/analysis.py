"""Reproducible, model-agnostic analysis for the morphing API.

These functions intentionally accept already aligned vertices.  Keeping the
math separate from image reconstruction makes the metrics usable by the API,
CLI tools and unit tests without loading a GPU model.
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np

DEFAULT_ZONE_WEIGHTS: dict[str, float] = {
    "forehead": 0.10,
    "left_eye": 0.09,
    "right_eye": 0.09,
    "nose": 0.22,
    "left_cheek": 0.10,
    "right_cheek": 0.10,
    "mouth_chin": 0.30,
}


def zone_ranges(vertex_count: int) -> dict[str, tuple[int, int]]:
    """Return stable proportional mesh zones for any topology size.

    The original project assumed exactly 35,709 vertices and could silently
    produce empty or truncated zones with another 3DMM.  Fractions preserve
    the existing ordering convention while making the API topology-aware.
    """
    if vertex_count < 7:
        raise ValueError("at least seven vertices are required for zone metrics")
    fractions = (0.0, 0.084, 0.196, 0.308, 0.476, 0.644, 0.812, 1.0)
    names = tuple(DEFAULT_ZONE_WEIGHTS)
    edges = [int(round(vertex_count * value)) for value in fractions]
    return {name: (edges[i], edges[i + 1]) for i, name in enumerate(names)}


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    flat_a = np.asarray(a, dtype=np.float64).reshape(-1)
    flat_b = np.asarray(b, dtype=np.float64).reshape(-1)
    denominator = float(np.linalg.norm(flat_a) * np.linalg.norm(flat_b))
    return float(np.dot(flat_a, flat_b) / denominator) if denominator > 1e-12 else 0.0


def _score_from_distance(distance: float, scale: float = 0.15) -> float:
    return float(np.clip((1.0 - distance / scale) * 100.0, 0.0, 100.0))


def similarity_metrics(
    vertices_a: np.ndarray,
    vertices_b: np.ndarray,
    *,
    zones: Mapping[str, tuple[int, int]] | None = None,
) -> dict[str, Any]:
    """Compute dense shape metrics and a ranked anatomical breakdown."""
    a = np.asarray(vertices_a, dtype=np.float32)
    b = np.asarray(vertices_b, dtype=np.float32)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 3 or len(a) < 7:
        raise ValueError("vertices_a and vertices_b must both have shape (N, 3), N >= 7")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("vertex coordinates must be finite")
    dists = np.linalg.norm(a - b, axis=1).astype(np.float64)
    zones = dict(zones or zone_ranges(len(a)))
    for name, (start, end) in zones.items():
        if not isinstance(start, (int, np.integer)) or not isinstance(end, (int, np.integer)) or not 0 <= start < end <= len(a):
            raise ValueError(f"invalid zone bounds for {name}: {(start, end)}")
    zone_metrics: dict[str, dict[str, float]] = {}
    for name, (start, end) in zones.items():
        delta = dists[start:end]
        if len(delta) == 0:
            continue
        mean_delta = float(np.mean(delta))
        zone_metrics[name] = {
            "mean_delta": round(mean_delta, 8),
            "max_delta": round(float(np.max(delta)), 8),
            "similarity": round(_score_from_distance(mean_delta), 2),
            "vertices": int(len(delta)),
        }

    ranked = sorted(zone_metrics.items(), key=lambda item: item[1]["mean_delta"], reverse=True)
    mean_distance = float(np.mean(dists))
    return {
        "vertex_count": int(len(a)),
        # ``euclidean_distance`` is the full L2 norm requested by the API;
        # ``euclidean_mean`` is easier to compare across topologies.
        "euclidean_distance": round(float(np.linalg.norm(a - b)), 8),
        "euclidean_mean": round(mean_distance, 8),
        "euclidean_max": round(float(np.max(dists)), 8),
        "p95_delta": round(float(np.percentile(dists, 95)), 8),
        "pct_above_threshold": round(float(np.mean(dists > 0.025) * 100.0), 3),
        "cosine_similarity": round(_cosine(a, b), 8),
        "morphability_score": round(_score_from_distance(mean_distance), 2),
        "zones": zone_metrics,
        "top_5_zones": [
            {"zone": name, **metrics} for name, metrics in ranked[:5]
        ],
    }


def forensic_metrics(
    vertices_a: np.ndarray,
    vertices_b: np.ndarray,
    *,
    zones: Mapping[str, tuple[int, int]] | None = None,
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Return an explainable similarity proxy with zone contributions.

    This is a geometric similarity indicator, not a legally valid biometric
    identification probability.  The explicit caveat is included in the API
    response so callers cannot accidentally present it as a verified identity.
    """
    metrics = similarity_metrics(vertices_a, vertices_b, zones=zones)
    chosen_weights = {str(key): float(value) for key, value in (weights or DEFAULT_ZONE_WEIGHTS).items()}
    unknown = set(chosen_weights) - set(metrics["zones"])
    if unknown:
        raise ValueError(f"unknown forensic zones: {', '.join(sorted(unknown))}")
    if any(not np.isfinite(value) or value < 0 for value in chosen_weights.values()):
        raise ValueError("forensic zone weights must be finite and non-negative")
    available = {name: data for name, data in metrics["zones"].items() if name in chosen_weights}
    total_weight = sum(chosen_weights[name] for name in available) or 1.0
    weighted_score = sum(
        data["similarity"] * chosen_weights[name] for name, data in available.items()
    ) / total_weight
    ordered = sorted(available.items(), key=lambda item: item[1]["similarity"], reverse=True)
    explanations = {
        "supporting_zones": [name for name, data in ordered[:3] if data["similarity"] >= 70],
        "differing_zones": [name for name, data in ordered[::-1][:3] if data["similarity"] < 70],
    }
    return {
        **metrics,
        "forensic_score": round(float(weighted_score), 2),
        "score_type": "uncalibrated geometric similarity index on a 0–100 scale",
        # Deprecated compatibility field; deliberately null because this
        # score has not been calibrated to a probability of shared identity.
        "probability_same_person": None,
        "zone_weights": chosen_weights,
        "explanations": explanations,
        "interpretation": "geometric similarity proxy; not a calibrated identity probability",
    }


def symmetry_metrics(vertices: np.ndarray) -> dict[str, Any]:
    """Estimate bilateral symmetry using a reflected nearest-neighbour metric."""
    points = np.asarray(vertices, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 7 or not np.isfinite(points).all():
        raise ValueError("vertices must have finite shape (N, 3), N >= 7")
    reflected = points.copy()
    reflected[:, 0] *= -1.0
    sampled_indices = None
    try:
        from scipy.spatial import cKDTree  # optional dependency

        tree = cKDTree(points)
        distances, _ = tree.query(reflected, k=1)
    except Exception:  # pragma: no cover - exercised only without scipy
        # A bounded fallback keeps the endpoint usable in minimal installs.
        sampled_indices = np.linspace(0, len(points) - 1, min(len(points), 2500), dtype=int)
        distances = np.empty(len(sampled_indices), dtype=np.float32)
        for start in range(0, len(sampled_indices), 128):
            batch = reflected[sampled_indices[start:start + 128]]
            distances[start:start + len(batch)] = np.min(
                np.linalg.norm(batch[:, None, :] - points[None, :, :], axis=2), axis=1
            )
    scale = max(float(np.ptp(points[:, 1])), 1e-6)
    global_distance = float(np.mean(distances)) / scale
    global_score = float(np.clip(1.0 - global_distance * 4.0, 0.0, 1.0))
    zones = zone_ranges(len(points))
    regional: dict[str, dict[str, float]] = {}
    for name, (start, end) in zones.items():
        if sampled_indices is None:
            region = distances[start:end]
        else:
            region = distances[(sampled_indices >= start) & (sampled_indices < end)]
        if len(region):
            regional[name] = {
                "distance": round(float(np.mean(region) / scale), 6),
                "score": round(float(np.clip(1.0 - np.mean(region) / scale * 4.0, 0.0, 1.0)), 4),
            }
    return {
        "score": round(global_score, 4),
        "distance": round(global_distance, 6),
        "regions": regional,
        "method": "reflection across canonical x=0 plane + nearest-neighbour Procrustes proxy",
        "interpretation": "descriptive morphology metric; not an identity or medical diagnosis",
    }


def pca_projection(vertices: list[np.ndarray], components: int = 3) -> dict[str, Any]:
    """Project aligned meshes into a deterministic low-dimensional face space."""
    if len(vertices) < 2:
        raise ValueError("PCA face space needs at least two meshes")
    if components < 1:
        raise ValueError("components must be positive")
    arrays = [np.asarray(item, dtype=np.float64) for item in vertices]
    if any(array.shape != arrays[0].shape for array in arrays[1:]):
        raise ValueError("all PCA meshes must have identical shapes")
    if any(not np.isfinite(array).all() for array in arrays):
        raise ValueError("PCA mesh coordinates must be finite")
    matrix = np.stack([item.reshape(-1) for item in arrays])
    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    left, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    usable = min(int(components), left.shape[1])
    coordinates = left[:, :usable] * singular_values[:usable]
    if usable < components:
        coordinates = np.pad(coordinates, ((0, 0), (0, components - usable)))
    variance = singular_values ** 2
    total = float(np.sum(variance)) or 1.0
    explained = [float(value / total) for value in variance[:usable]]
    explained.extend([0.0] * (components - len(explained)))
    return {
        "coordinates": np.round(coordinates, 8).tolist(),
        "explained_variance": [round(value, 8) for value in explained],
        "components": components,
        "method": "SVD/PCA on aligned identity meshes",
    }


def temporal_drift_metrics(years: list[float], vertices: list[np.ndarray]) -> dict[str, Any]:
    """Fit a linear shape trajectory and report deviations from it.

    This is intentionally a diagnostic drift vector, not an age predictor.  A
    real biological-age model needs a calibrated cohort and is outside the
    reconstruction service.
    """
    if len(years) != len(vertices) or len(years) < 3:
        raise ValueError("temporal drift needs at least three dated keyframes")
    raw_years = np.asarray(years, dtype=np.float64)
    if not np.isfinite(raw_years).all():
        raise ValueError("temporal drift years must be finite")
    order = np.argsort(raw_years)
    x = raw_years[order]
    if np.any(np.diff(x) <= 0):
        raise ValueError("temporal drift years must be unique")
    arrays = [np.asarray(vertices[index], dtype=np.float64) for index in order]
    if any(array.shape != arrays[0].shape for array in arrays[1:]):
        raise ValueError("all drift meshes must have identical shapes")
    if any(array.ndim != 2 or array.shape[1] != 3 or not np.isfinite(array).all() for array in arrays):
        raise ValueError("all drift meshes must have finite shape (N, 3)")
    centered_years = x - float(np.mean(x))
    denominator = float(np.dot(centered_years, centered_years)) or 1.0
    stack = np.stack(arrays)
    velocity = np.tensordot(centered_years, stack, axes=(0, 0)) / denominator
    intercept = np.mean(stack, axis=0)
    predicted = intercept[None, ...] + centered_years[:, None, None] * velocity[None, ...]
    residuals = np.linalg.norm(stack - predicted, axis=(1, 2)) / max(np.sqrt(stack.shape[1]), 1.0)
    ranges = zone_ranges(stack.shape[1])
    zone_velocity = {
        name: round(float(np.linalg.norm(velocity[start:end]) / max(end - start, 1)), 8)
        for name, (start, end) in ranges.items()
    }
    anomaly_threshold = float(np.mean(residuals) + 2 * np.std(residuals))
    return {
        "years": [float(value) for value in x],
        "ordered_indices": [int(index) for index in order],
        "velocity_l2_per_year": round(float(np.linalg.norm(velocity)), 8),
        "zone_velocity": zone_velocity,
        "residuals": [round(float(value), 8) for value in residuals],
        "anomaly_positions": [int(position) for position, value in enumerate(residuals) if value > anomaly_threshold],
        "anomaly_keyframes": [int(index) for index, value in zip(order, residuals) if value > anomaly_threshold],
        "method": "linear regression on aligned dense vertex coordinates",
        "interpretation": "trajectory deviation is a screening signal, not a diagnosis of ageing or surgery",
    }


def uv_difference(texture_a_bgr: np.ndarray, texture_b_bgr: np.ndarray) -> np.ndarray:
    """Create a normalized, display-ready UV difference heatmap."""
    a = np.asarray(texture_a_bgr, dtype=np.float32)
    b = np.asarray(texture_b_bgr, dtype=np.float32)
    if a.shape != b.shape or a.ndim != 3 or a.shape[2] < 3 or min(a.shape[:2]) < 1:
        raise ValueError("UV textures must have identical non-empty HxWx3 shapes")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("UV texture pixels must be finite")
    delta = np.mean(np.abs(a[:, :, :3] - b[:, :, :3]), axis=2)
    normalized = np.clip(delta / max(float(np.percentile(delta, 99)), 1.0) * 255.0, 0, 255)
    # Compact blue→cyan→yellow→red LUT with the same BGR channel order used
    # by OpenCV callers, but no hard dependency on cv2 for metric consumers.
    stops = np.asarray([0, 64, 128, 192, 255], dtype=np.float64)
    palette = np.asarray([
        [128, 0, 0],
        [255, 255, 0],
        [0, 255, 255],
        [0, 128, 255],
        [0, 0, 128],
    ], dtype=np.float64)
    heatmap = np.stack([
        np.interp(normalized, stops, palette[:, channel])
        for channel in range(3)
    ], axis=2)
    return np.clip(np.rint(heatmap), 0, 255).astype(np.uint8)
