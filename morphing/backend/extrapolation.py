"""Dated dense-shape extrapolation helpers.

This is a transparent mathematical projection, not an age-estimation model.
It is useful for a visual what-if preview and must not be interpreted as a
validated prediction of a person's future appearance.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def extrapolate_shape(
    years: list[float],
    vertices: list[np.ndarray],
    future_year: float,
    *,
    degree: int = 2,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Fit a bounded polynomial per mesh coordinate and evaluate it later."""
    if len(years) != len(vertices) or len(years) < 3:
        raise ValueError("extrapolation requires at least three dated keyframes")
    x = np.asarray(years, dtype=np.float64)
    if not np.all(np.isfinite(x)) or not np.isfinite(float(future_year)):
        raise ValueError("years and future_year must be finite")
    if np.any(np.diff(x) <= 0):
        raise ValueError("years must be strictly increasing in upload order")
    arrays = [np.asarray(item, dtype=np.float64) for item in vertices]
    if any(item.shape != arrays[0].shape for item in arrays[1:]):
        raise ValueError("all extrapolation meshes must have identical shapes")
    fit_degree = min(max(int(degree), 1), len(years) - 1)
    matrix = np.stack([item.reshape(-1) for item in arrays])
    origin = float(x[-1])
    centered_years = x - origin
    coefficients = np.polynomial.polynomial.polyfit(centered_years, matrix, fit_degree)
    future_offset = float(future_year) - origin
    powers = np.asarray([future_offset ** power for power in range(fit_degree + 1)])
    predicted = powers @ coefficients
    prediction = predicted.reshape(arrays[0].shape).astype(np.float32)
    fitted = np.stack([sum((year ** power) * coefficients[power] for power in range(fit_degree + 1)) for year in centered_years])
    residuals = np.linalg.norm(matrix - fitted, axis=1) / max(np.sqrt(matrix.shape[1]), 1.0)
    span = float(future_year - x[-1])
    return prediction, {
        "future_year": float(future_year),
        "training_years": [float(value) for value in x],
        "degree": fit_degree,
        "extrapolation_span_years": round(span, 4),
        "training_residuals": [round(float(value), 8) for value in residuals],
        "method": "per-coordinate polynomial regression on aligned dense mesh",
        "interpretation": "what-if geometric projection; not a calibrated age or surgery prediction",
    }
