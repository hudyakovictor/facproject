"""Geometry core - pure numpy, no scipy.

Everything here is deliberately free of policy: no thresholds, no verdicts, no
knowledge of what counts as "significant". It measures, and it reports what it
measured. Policy lives in gates.py, driven by params.py.

The one opinionated choice is the aligner: iteratively trimmed Kabsch with no
scale term. Both halves of that matter.

  * Trimming, because a plain least-squares fit spreads a large local change
    across the whole transform. If one region of a face moved, an untrimmed fit
    rotates the entire head slightly to split the difference, shrinking the
    residual in the region that actually changed and inventing residual
    everywhere else. Trimming the worst correspondences each iteration lets the
    stable majority define the frame.
  * No scale, because a free scale term absorbs real volumetric change. If a
    face genuinely became fuller, a scaling fit reports "same shape, slightly
    bigger" and the change vanishes. Scale is exactly what we are trying to
    measure, so it cannot be a free parameter.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AlignResult:
    """Outcome of aligning `moving` onto `fixed`."""

    rotation: np.ndarray  # (3, 3)
    translation: np.ndarray  # (3,)
    #: Per-point Euclidean residual after alignment, in input units.
    residuals: np.ndarray  # (n,)
    #: Boolean mask of the points that survived trimming and defined the frame.
    inliers: np.ndarray  # (n,)
    iterations: int
    #: Residual rotation magnitude in degrees. Large values mean the two shapes
    #: could not be brought into a common frame, which usually means pose
    #: leakage rather than change.
    residual_tilt_deg: float
    converged: bool

    @property
    def rmse(self) -> float:
        return float(np.sqrt(np.mean(self.residuals**2)))

    @property
    def inlier_rmse(self) -> float:
        sel = self.residuals[self.inliers]
        if sel.size == 0:
            return float("nan")
        return float(np.sqrt(np.mean(sel**2)))

    def percentile(self, q: float) -> float:
        return float(np.percentile(self.residuals, q))


def _kabsch(fixed: np.ndarray, moving: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Closed-form optimal rotation+translation, no scale. Returns (R, t).

    Reflection is explicitly forbidden: a mirrored fit would happily match a
    left cheek to a right cheek.
    """
    fixed_c = fixed.mean(axis=0)
    moving_c = moving.mean(axis=0)
    covariance = (moving - moving_c).T @ (fixed - fixed_c)
    u, _, vt = np.linalg.svd(covariance)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    correction = np.diag(np.array([1.0, 1.0, d]))
    rotation = vt.T @ correction @ u.T
    translation = fixed_c - rotation @ moving_c
    return rotation, translation


def rotation_angle_deg(rotation: np.ndarray) -> float:
    """Magnitude of a rotation matrix as a single angle, in degrees."""
    trace = float(np.trace(rotation))
    cos_theta = np.clip((trace - 1.0) / 2.0, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_theta)))


def trimmed_kabsch(
    fixed: np.ndarray,
    moving: np.ndarray,
    *,
    trim_fraction: float = 0.15,
    max_iterations: int = 5,
    min_points: int = 8,
    tolerance: float = 1e-9,
) -> AlignResult:
    """Align `moving` onto `fixed` using iteratively trimmed Kabsch.

    Both arrays must be (n, 3) and already in correspondence.
    """
    fixed = np.asarray(fixed, dtype=np.float64)
    moving = np.asarray(moving, dtype=np.float64)
    if fixed.shape != moving.shape:
        raise ValueError(f"shape mismatch: {fixed.shape} vs {moving.shape}")
    if fixed.ndim != 2 or fixed.shape[1] != 3:
        raise ValueError(f"expected (n, 3) arrays, got {fixed.shape}")
    n = fixed.shape[0]
    if n < min_points:
        raise ValueError(f"need at least {min_points} points, got {n}")

    trim_fraction = float(np.clip(trim_fraction, 0.0, 0.4))
    keep = max(int(round(n * (1.0 - trim_fraction))), min_points)
    keep = min(keep, n)

    inliers = np.ones(n, dtype=bool)
    rotation, translation = _kabsch(fixed, moving)
    previous = np.inf
    iterations = 0
    converged = False

    for iterations in range(1, max_iterations + 1):
        aligned = moving @ rotation.T + translation
        residuals = np.linalg.norm(aligned - fixed, axis=1)
        # Keep the `keep` best correspondences and refit on those alone.
        order = np.argsort(residuals)
        inliers = np.zeros(n, dtype=bool)
        inliers[order[:keep]] = True
        rotation, translation = _kabsch(fixed[inliers], moving[inliers])
        current = float(np.mean(residuals[inliers] ** 2))
        if abs(previous - current) <= tolerance:
            converged = True
            break
        previous = current

    aligned = moving @ rotation.T + translation
    residuals = np.linalg.norm(aligned - fixed, axis=1)
    return AlignResult(
        rotation=rotation,
        translation=translation,
        residuals=residuals,
        inliers=inliers,
        iterations=iterations,
        residual_tilt_deg=rotation_angle_deg(rotation),
        converged=converged,
    )


def displacement_vectors(
    fixed: np.ndarray, moving: np.ndarray, align: AlignResult
) -> np.ndarray:
    """Per-point displacement after alignment, as (n, 3) vectors.

    Direction matters: coherent displacement is evidence of a real change,
    while displacement that points every which way is noise.
    """
    aligned = np.asarray(moving, dtype=np.float64) @ align.rotation.T + align.translation
    return aligned - np.asarray(fixed, dtype=np.float64)


def coherence(vectors: np.ndarray) -> float:
    """How much a set of displacement vectors agrees in direction, in [0, 1].

    1.0 means every vector points the same way (a region moved as a unit).
    0.0 means directions cancel out (noise). This is the length of the mean
    unit vector, sometimes called the resultant length.
    """
    vectors = np.asarray(vectors, dtype=np.float64)
    if vectors.size == 0:
        return float("nan")
    norms = np.linalg.norm(vectors, axis=1)
    usable = norms > 1e-12
    if not np.any(usable):
        return 0.0
    units = vectors[usable] / norms[usable, None]
    return float(np.linalg.norm(units.mean(axis=0)))


def interocular_distance(landmarks: np.ndarray, left: int, right: int) -> float:
    """Scale reference for normalising displacements into comparable units."""
    landmarks = np.asarray(landmarks, dtype=np.float64)
    return float(np.linalg.norm(landmarks[left] - landmarks[right]))


@dataclass(frozen=True)
class ZoneResidual:
    """Residual summary for one anatomical zone."""

    zone: str
    point_count: int
    rmse: float
    p95: float
    max_residual: float
    mean_displacement: np.ndarray
    coherence: float

    def to_json(self) -> dict:
        return {
            "zone": self.zone,
            "point_count": self.point_count,
            "rmse": round(self.rmse, 8),
            "p95": round(self.p95, 8),
            "max_residual": round(self.max_residual, 8),
            "mean_displacement": [round(float(v), 8) for v in self.mean_displacement],
            "coherence": round(self.coherence, 6),
        }


def zone_residuals(
    residuals: np.ndarray,
    vectors: np.ndarray,
    zone_map: dict[str, list[int]],
    *,
    min_points: int = 3,
) -> dict[str, ZoneResidual]:
    """Break a pair residual down by anatomical zone.

    Zones with too little support are omitted rather than reported with a
    meaningless number. A caller that needs to know a zone was dropped can
    compare against the keys of `zone_map`.
    """
    residuals = np.asarray(residuals, dtype=np.float64)
    vectors = np.asarray(vectors, dtype=np.float64)
    out: dict[str, ZoneResidual] = {}
    for zone, indices in zone_map.items():
        idx = np.asarray([i for i in indices if 0 <= i < residuals.size], dtype=int)
        if idx.size < min_points:
            continue
        zone_res = residuals[idx]
        zone_vec = vectors[idx]
        out[zone] = ZoneResidual(
            zone=zone,
            point_count=int(idx.size),
            rmse=float(np.sqrt(np.mean(zone_res**2))),
            p95=float(np.percentile(zone_res, 95)),
            max_residual=float(np.max(zone_res)),
            mean_displacement=zone_vec.mean(axis=0),
            coherence=coherence(zone_vec),
        )
    return out


def angle_delta(
    angles_a: np.ndarray, angles_b: np.ndarray
) -> dict[str, float]:
    """Absolute pitch/yaw/roll difference between two photos, in degrees."""
    a = np.asarray(angles_a, dtype=np.float64).ravel()
    b = np.asarray(angles_b, dtype=np.float64).ravel()
    if a.size < 3 or b.size < 3:
        raise ValueError("expected pitch, yaw, roll for both photos")
    return {
        "pitch": float(abs(a[0] - b[0])),
        "yaw": float(abs(a[1] - b[1])),
        "roll": float(abs(a[2] - b[2])),
    }


def pose_distance(delta: dict[str, float], sensitivity: dict[str, float]) -> float:
    """Single pose-separation number, weighted by measured sensitivity.

    Yaw is the reference axis (weight 1). Pitch and roll are scaled by how much
    more the residual responds to them, so a degree of pitch counts for more
    than a degree of yaw.
    """
    return float(
        np.sqrt(
            delta["yaw"] ** 2
            + (delta["pitch"] * sensitivity.get("pitch", 1.0)) ** 2
            + (delta["roll"] * sensitivity.get("roll", 1.0)) ** 2
        )
    )
