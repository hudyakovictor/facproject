"""Statistics core - pure numpy, no scipy.

The legacy code imported scipy for four things, all of which are a handful of
lines here. Dropping the dependency is not cosmetic: it is what lets Stage 2
run in CI and in a bare venv, which is what makes it testable at all.

The multiple-testing machinery is the part that matters most for anything that
will eventually be published. A single face comparison produces one number per
landmark and one per zone. Across a few dozen photo pairs that is thousands of
simultaneous tests, and at an uncorrected 5% level you would expect dozens of
"significant" findings from pure noise. Reporting those as discoveries is the
easiest way to produce a confident, entirely false result.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


# --------------------------------------------------------------------------
# Normal distribution, without scipy
# --------------------------------------------------------------------------
def normal_sf(z: np.ndarray | float) -> np.ndarray | float:
    """Upper tail of the standard normal, 1 - Phi(z).

    Uses the complementary error function, which is accurate into the far tail
    where a naive series expansion loses all precision. We care about the far
    tail specifically: that is where the interesting claims live.
    """
    z_arr = np.asarray(z, dtype=np.float64)
    result = 0.5 * np.vectorize(math.erfc)(z_arr / math.sqrt(2.0))
    return float(result) if np.isscalar(z) or result.ndim == 0 else result


def normal_two_sided_p(z: np.ndarray | float) -> np.ndarray | float:
    """Two-sided p-value for a z statistic."""
    z_arr = np.abs(np.asarray(z, dtype=np.float64))
    result = np.vectorize(math.erfc)(z_arr / math.sqrt(2.0))
    return float(result) if np.isscalar(z) or result.ndim == 0 else result


def normal_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation).

    Relative error below 1.15e-9 over the whole open interval, which is far
    more than adequate for turning a confidence level into a z multiplier.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1), got {p}")
    a = (
        -3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
        1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
        6.680131188771972e01, -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
        -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
        3.754408661907416e00,
    )
    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p > p_high:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
    )


# --------------------------------------------------------------------------
# Robust location and scale
# --------------------------------------------------------------------------
MAD_TO_SIGMA = 1.4826  # consistency constant for a normal distribution


def mad(values: np.ndarray, *, scale: bool = True) -> float:
    """Median absolute deviation.

    Preferred over the standard deviation throughout: a calibration set with a
    few badly-reconstructed frames would have its standard deviation inflated
    by those frames, raising the noise floor and hiding real change behind it.
    The MAD ignores them.
    """
    values = np.asarray(values, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    deviation = float(np.median(np.abs(values - np.median(values))))
    return deviation * MAD_TO_SIGMA if scale else deviation


def robust_z(value: float, reference: np.ndarray) -> float:
    """How far `value` sits from a reference distribution, in robust sigmas."""
    reference = np.asarray(reference, dtype=np.float64).ravel()
    reference = reference[np.isfinite(reference)]
    if reference.size < 2:
        return float("nan")
    centre = float(np.median(reference))
    spread = mad(reference)
    if not np.isfinite(spread) or spread <= 0.0:
        return float("nan")
    return float((value - centre) / spread)


def equal_weight_quantile(
    groups: dict[str, np.ndarray], quantile: float
) -> tuple[float, dict[str, float]]:
    """Per-group quantiles first, then the median across groups.

    This is the `equal_person_median_of_quantiles` policy. Pooling every
    calibration frame into one distribution would let whoever contributed the
    most photos define the noise floor for everyone. Computing each person's
    quantile first and then combining gives every person one vote.
    """
    per_group: dict[str, float] = {}
    for name, values in groups.items():
        arr = np.asarray(values, dtype=np.float64).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            continue
        per_group[name] = float(np.quantile(arr, quantile))
    if not per_group:
        return float("nan"), {}
    return float(np.median(list(per_group.values()))), per_group


# --------------------------------------------------------------------------
# Multiple testing
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FDRResult:
    """Outcome of a multiple-testing correction."""

    method: str
    level: float
    p_values: np.ndarray
    rejected: np.ndarray
    q_values: np.ndarray
    n_tests: int

    @property
    def n_rejected(self) -> int:
        return int(np.count_nonzero(self.rejected))

    def to_json(self) -> dict:
        return {
            "method": self.method,
            "level": self.level,
            "n_tests": self.n_tests,
            "n_rejected": self.n_rejected,
            "min_q_value": (
                float(np.min(self.q_values)) if self.q_values.size else None
            ),
        }


def adjust_p_values(
    p_values: np.ndarray, *, method: str = "benjamini_hochberg", level: float = 0.05
) -> FDRResult:
    """Correct a family of p-values for multiple testing.

    benjamini_hochberg
        Controls the false discovery rate under independence or positive
        dependence. The default.
    benjamini_yekutieli
        Valid under *arbitrary* dependence, at the cost of power. The honest
        choice when tests are correlated in ways you have not characterised -
        which is the case for neighbouring landmarks on a face, since they sit
        on shared underlying structure and move together.
    bonferroni
        Controls the family-wise error rate. Very conservative.
    none
        No correction. Exploratory only; never for anything published.
    """
    p = np.asarray(p_values, dtype=np.float64).ravel()
    finite = np.isfinite(p)
    n = int(np.count_nonzero(finite))
    q = np.full(p.shape, np.nan, dtype=np.float64)
    rejected = np.zeros(p.shape, dtype=bool)
    if n == 0:
        return FDRResult(method, level, p, rejected, q, 0)

    idx = np.flatnonzero(finite)
    p_finite = p[idx]
    order = np.argsort(p_finite)
    sorted_p = p_finite[order]
    ranks = np.arange(1, n + 1, dtype=np.float64)

    if method == "none":
        adjusted = sorted_p.copy()
    elif method == "bonferroni":
        adjusted = np.minimum(sorted_p * n, 1.0)
    elif method in {"benjamini_hochberg", "benjamini_yekutieli"}:
        factor = 1.0
        if method == "benjamini_yekutieli":
            # Harmonic sum penalty for arbitrary dependence.
            factor = float(np.sum(1.0 / ranks))
        raw = sorted_p * n * factor / ranks
        # Enforce monotonicity from the largest p downwards (step-up).
        adjusted = np.minimum.accumulate(raw[::-1])[::-1]
        adjusted = np.minimum(adjusted, 1.0)
    else:
        raise ValueError(f"unknown multiple-testing method: {method!r}")

    q_sorted = adjusted
    q_finite = np.empty(n, dtype=np.float64)
    q_finite[order] = q_sorted
    q[idx] = q_finite
    rejected[idx] = q_finite <= level
    return FDRResult(method, level, p, rejected, q, n)


# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------
def bootstrap_ci(
    values: np.ndarray,
    *,
    statistic=np.median,
    iterations: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI. Returns (point_estimate, low, high).

    A point estimate without an interval invites over-reading. If the interval
    for a change magnitude includes zero, the honest description is "no
    measurable change", regardless of how the point estimate reads.
    """
    values = np.asarray(values, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    point = float(statistic(values)) if values.size else float("nan")
    if values.size < 2 or iterations <= 0:
        return point, float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, values.size, size=(iterations, values.size))
    stats = np.asarray([statistic(values[row]) for row in draws], dtype=np.float64)
    alpha = (1.0 - confidence) / 2.0
    return (
        point,
        float(np.quantile(stats, alpha)),
        float(np.quantile(stats, 1.0 - alpha)),
    )


def cusum(values: np.ndarray, *, threshold: float = 5.0) -> dict:
    """Cumulative-sum drift detector over an ordered series.

    Catches the case that defeats pairwise comparison: a series of steps each
    too small to flag individually, which together add up to a large change.
    Consecutive pairs all look clean; the endpoints do not.
    """
    values = np.asarray(values, dtype=np.float64).ravel()
    finite = values[np.isfinite(values)]
    if finite.size < 3:
        return {
            "status": "insufficient_support",
            "n": int(finite.size),
            "alarms": [],
        }
    centre = float(np.median(finite))
    spread = mad(finite)
    if not np.isfinite(spread) or spread <= 0.0:
        return {"status": "degenerate_spread", "n": int(finite.size), "alarms": []}
    standardised = (values - centre) / spread
    high = np.zeros(values.size, dtype=np.float64)
    low = np.zeros(values.size, dtype=np.float64)
    alarms: list[int] = []
    for i in range(1, values.size):
        if not np.isfinite(standardised[i]):
            high[i], low[i] = high[i - 1], low[i - 1]
            continue
        high[i] = max(0.0, high[i - 1] + standardised[i] - 0.5)
        low[i] = min(0.0, low[i - 1] + standardised[i] + 0.5)
        if high[i] > threshold or low[i] < -threshold:
            alarms.append(i)
            high[i], low[i] = 0.0, 0.0
    return {
        "status": "ok",
        "n": int(values.size),
        "centre": centre,
        "spread": spread,
        "threshold": threshold,
        "alarms": alarms,
        "cusum_high": [round(float(v), 6) for v in high],
        "cusum_low": [round(float(v), 6) for v in low],
    }
