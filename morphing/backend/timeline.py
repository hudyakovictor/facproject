"""Numerical helpers for multi-face morphing timelines.

The frontend uses the same weights as the API so a saved timeline is
reproducible in both places.  The implementation deliberately works on
``numpy`` arrays only; it does not import the reconstruction models and is
therefore cheap to test and reuse in batch jobs.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np


def catmull_rom_weights(
    progress: float,
    count: int,
    positions: Iterable[float] | None = None,
) -> np.ndarray:
    """Return Catmull-Rom basis weights for up to four timeline keyframes.

    ``progress`` is in ``[0, 1]``.  ``positions`` may provide normalized,
    strictly increasing time positions for age-aware timelines; when omitted,
    keyframes are evenly spaced.  Endpoints
    are duplicated at the boundary, which makes the curve pass through every
    uploaded face (rather than overshooting beyond the first or last face).
    Negative weights are valid and are an expected property of a cubic spline.
    """
    if count < 2 or count > 4:
        raise ValueError("a morph timeline must contain between 2 and 4 keyframes")
    t = float(np.clip(progress, 0.0, 1.0))
    if count == 2:
        return np.array([1.0 - t, t, 0.0, 0.0], dtype=np.float32)

    # Segment number and local t. The last point belongs to the last segment.
    if positions is None:
        timeline_positions = np.linspace(0.0, 1.0, count)
    else:
        timeline_positions = np.asarray(list(positions), dtype=np.float64)
        if len(timeline_positions) != count or timeline_positions[0] != 0 or timeline_positions[-1] != 1 or np.any(np.diff(timeline_positions) <= 0):
            raise ValueError("timeline positions must be strictly increasing from 0 to 1")
    segment = int(np.searchsorted(timeline_positions, t, side="right") - 1)
    segment = min(max(segment, 0), count - 2)
    span = timeline_positions[segment + 1] - timeline_positions[segment]
    u = 1.0 if t >= 1.0 else (t - timeline_positions[segment]) / span
    u2, u3 = u * u, u * u * u
    basis = np.array(
        [
            -0.5 * u3 + u2 - 0.5 * u,
            1.5 * u3 - 2.5 * u2 + 1.0,
            -1.5 * u3 + 2.0 * u2 + 0.5 * u,
            0.5 * u3 - 0.5 * u2,
        ],
        dtype=np.float32,
    )

    # P0/P3 are duplicated for a segment touching a boundary.  The four
    # control points are accumulated into the fixed A/B/C/D output slots.
    control_indices = [segment - 1, segment, segment + 1, segment + 2]
    weights = np.zeros(4, dtype=np.float32)
    for weight, index in zip(basis, control_indices):
        weights[min(max(index, 0), count - 1)] += weight
    return weights


def interpolate_sequence(
    vertices: Iterable[np.ndarray],
    progress: float,
    positions: Iterable[float] | None = None,
) -> np.ndarray:
    """Interpolate a sequence of equally shaped vertex arrays."""
    arrays = [np.asarray(item, dtype=np.float32) for item in vertices]
    if not 2 <= len(arrays) <= 4:
        raise ValueError("a morph timeline must contain between 2 and 4 keyframes")
    if any(item.shape != arrays[0].shape for item in arrays[1:]):
        raise ValueError("all timeline meshes must have the same shape")
    weights = catmull_rom_weights(progress, len(arrays), positions)
    result = np.zeros_like(arrays[0], dtype=np.float32)
    for index, array in enumerate(arrays):
        result += weights[index] * array
    return result


def blend_vertices(vertices: Iterable[np.ndarray], weights: Iterable[float]) -> np.ndarray:
    """Blend 2–4 meshes using normalized barycentric weights."""
    arrays = [np.asarray(item, dtype=np.float32) for item in vertices]
    raw_weights = np.asarray(list(weights), dtype=np.float64)
    if not 2 <= len(arrays) <= 4 or len(raw_weights) != len(arrays):
        raise ValueError("blend requires 2–4 meshes and one weight per mesh")
    if any(item.shape != arrays[0].shape for item in arrays[1:]):
        raise ValueError("all blend meshes must have the same shape")
    if not np.all(np.isfinite(raw_weights)) or np.any(raw_weights < 0):
        raise ValueError("blend weights must be finite and non-negative")
    total = float(raw_weights.sum())
    if total <= 0:
        raise ValueError("at least one blend weight must be positive")
    normalized = raw_weights / total
    return np.tensordot(normalized.astype(np.float32), np.stack(arrays), axes=(0, 0))


def timeline_metadata(
    count: int,
    labels: list[str] | None = None,
    positions: Iterable[float] | None = None,
) -> dict:
    """Create a small serializable description for API responses."""
    if not 2 <= count <= 4:
        raise ValueError("a morph timeline must contain between 2 and 4 keyframes")
    names = labels or [f"Face {chr(65 + i)}" for i in range(count)]
    times = list(positions) if positions is not None else list(np.linspace(0.0, 1.0, count))
    catmull_rom_weights(0.0, count, times)  # validate and normalize the contract
    return {
        "method": "catmull-rom",
        "keyframe_count": count,
        "labels": names,
        "keyframe_times": [round(float(value), 6) for value in times],
        "domain": [0.0, 1.0],
        "endpoint_policy": "duplicated-boundary-control-points",
    }
