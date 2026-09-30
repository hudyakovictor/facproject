"""Optional smooth deformation primitives for face morphing.

The default renderer remains the direct correspondence morph.  This module
provides a conservative thin-plate / polyharmonic spline alternative for
cases where a smooth displacement field is preferred.  It does not claim to
be an ARAP solver: an ARAP backend needs mesh edges and an iterative optimizer
(Open3D/libigl) and should be added behind the same interface later.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TPSFit:
    controls: np.ndarray
    weights: np.ndarray
    affine: np.ndarray
    smoothing: float


def _kernel(radius: np.ndarray) -> np.ndarray:
    """3D polyharmonic radial basis used by the TPS displacement field."""
    return radius


def fit_tps_displacement(source: np.ndarray, target: np.ndarray, smoothing: float = 1e-6) -> TPSFit:
    """Fit a smooth 3D displacement field from corresponding landmarks."""
    x = np.asarray(source, dtype=np.float64)
    y = np.asarray(target, dtype=np.float64)
    if x.shape != y.shape or x.ndim != 2 or x.shape[1] != 3:
        raise ValueError("source and target landmarks must have shape (M, 3)")
    if len(x) < 4:
        raise ValueError("TPS requires at least four non-coplanar landmarks")
    if smoothing < 0:
        raise ValueError("smoothing must be non-negative")
    pairwise = np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)
    k = _kernel(pairwise)
    k.flat[:: len(x) + 1] += float(smoothing)
    p = np.concatenate([np.ones((len(x), 1)), x], axis=1)
    system = np.block([[k, p], [p.T, np.zeros((4, 4), dtype=np.float64)]])
    rhs = np.vstack([y - x, np.zeros((4, 3), dtype=np.float64)])
    try:
        solution = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError as exc:
        raise ValueError("TPS control points are degenerate") from exc
    return TPSFit(controls=x, weights=solution[: len(x)], affine=solution[len(x):], smoothing=float(smoothing))


def transform_tps(points: np.ndarray, fit: TPSFit, chunk_size: int = 4096) -> np.ndarray:
    """Apply a fitted displacement field without allocating N×M×3 at once."""
    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    output = np.empty_like(values)
    for start in range(0, len(values), chunk_size):
        batch = values[start:start + chunk_size]
        distances = np.linalg.norm(batch[:, None, :] - fit.controls[None, :, :], axis=2)
        radial = _kernel(distances) @ fit.weights
        affine = np.concatenate([np.ones((len(batch), 1)), batch], axis=1) @ fit.affine
        output[start:start + len(batch)] = batch + radial + affine
    return output.astype(np.float32)


def tps_deformed_target(source_vertices: np.ndarray, source_landmarks: np.ndarray, target_landmarks: np.ndarray, smoothing: float = 1e-6) -> tuple[np.ndarray, dict[str, float]]:
    """Return a smooth target mesh plus auditable landmark fit diagnostics."""
    fit = fit_tps_displacement(source_landmarks, target_landmarks, smoothing=smoothing)
    target = transform_tps(source_vertices, fit)
    fitted_landmarks = transform_tps(source_landmarks, fit)
    landmark_rmse = float(np.sqrt(np.mean((fitted_landmarks - target_landmarks) ** 2)))
    displacement = target - np.asarray(source_vertices, dtype=np.float32)
    return target, {
        "landmark_rmse": round(landmark_rmse, 8),
        "mean_displacement": round(float(np.mean(np.linalg.norm(displacement, axis=1))), 8),
        "max_displacement": round(float(np.max(np.linalg.norm(displacement, axis=1))), 8),
        "smoothing": float(smoothing),
        "method": "3D polyharmonic TPS displacement field",
    }
