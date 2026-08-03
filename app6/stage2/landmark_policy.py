"""NaN-safe landmark utility and subset policy.

Profile bins legitimately contain invisible landmarks.  Their utility cells are
NaN and must never poison weights or silently shrink a requested subset.
"""
from __future__ import annotations
import numpy as np


def sanitize_utility(values, *, floor: float = 0.0) -> np.ndarray:
    a=np.asarray(values,dtype=float)
    if a.ndim != 2 or a.shape[1] != 134:
        raise ValueError("utility must have shape (pose_bins, 134)")
    finite=np.where(np.isfinite(a),a,np.nan)
    with np.errstate(all="ignore"):
        fallback=np.nanmedian(finite,axis=0)
    fallback=np.nan_to_num(fallback,nan=floor,posinf=floor,neginf=floor)
    return np.where(np.isfinite(a),a,fallback[None,:]).clip(min=floor)


def row_all_nan(values) -> np.ndarray:
    """True for pose-bin rows that had NO finite utility value.

    ``sanitize_utility`` substitutes all-NaN rows with the cross-bin median;
    that substitution is numeric-only and must NEVER be read as per-bin
    coverage.  Any policy decision per bin (subset_for_bin, per_bin_anchor_mask)
    MUST consult this mask on the ORIGINAL values first.
    """
    a = np.asarray(values, dtype=float)
    if a.ndim != 2 or a.shape[1] != 134:
        raise ValueError("utility must have shape (pose_bins, 134)")
    with np.errstate(all="ignore"):
        return ~np.isfinite(a).any(axis=1)


def stable_subset(values, count: int = 91, *, pose_index=None,
                  min_visible_fraction=None, visibility=None) -> np.ndarray:
    """Return exactly `count` indices ranked by conservative utility.

    Per-bin mode (`pose_index`) ranks by that bin's utility only; invisible
    cells rank last (never removed) so a caller's requested count stays
    satisfiable.  An optional visibility floor (`visibility` + fraction) hard
    cuts points seen too rarely to `-inf` before ranking.
    """
    if not 1 <= int(count) <= 134: raise ValueError("count must be in 1..134")
    clean = sanitize_utility(values)
    if pose_index is None:
        score = np.min(clean, axis=0)
    else:
        if not 0 <= int(pose_index) < clean.shape[0]:
            raise ValueError(f"pose_index out of range: {pose_index}")
        score = clean[int(pose_index)].copy()
        if row_all_nan(values)[int(pose_index)]:
            # No per-bin coverage — must not rank by the substituted cross-bin
            # median (fail-open).  Leave all cells at -inf: no per-bin
            # preference, stable order preserved.
            score = np.full(clean.shape[1], -np.inf)
        if min_visible_fraction is not None:
            if visibility is None:
                raise ValueError("visibility required when min_visible_fraction set")
            vis = np.asarray(visibility, dtype=float)
            if vis.shape != (clean.shape[1],):
                raise ValueError("visibility must be per-landmark (134,)")
            score = np.where(vis < float(min_visible_fraction), -np.inf, score)
        score = np.where(np.isfinite(score), score, -np.inf)
    # Stable sort makes ties deterministic across platforms.
    return np.argsort(-score, kind="stable")[:int(count)].astype(np.int32)


def subset_for_bin(values, pose_index, *, count: int = 91, visibility=None,
                   min_visible_fraction: float = 0.60,
                   min_count: int = 30) -> dict:
    """Per-bin stable subset with visibility floor and truncation report.

    Returns metadata so the caller can decide: a truncated subset (fewer usable
    points than `min_count`) must not be used as a per-bin anchor.
    """
    if not 1 <= int(count) <= 134:
        raise ValueError("count must be in 1..134")
    clean = sanitize_utility(values)
    if not 0 <= int(pose_index) < clean.shape[0]:
        raise ValueError(f"pose_index out of range: {pose_index}")
    if row_all_nan(values)[int(pose_index)]:
        # Fail-closed: the bin had NO finite utility values.  sanitize_utility
        # silently substituted the cross-bin median; trusting it here would
        # claim per-bin coverage for a bin that has none.  The caller must
        # fall back explicitly (status "fallback_cross_bin").
        return {"indices": np.empty(0, dtype=np.int32),
                "requested": int(count),
                "effective": 0,
                "truncated": int(count),
                "usable": 0,
                "sufficient": False,
                "pose_index": int(pose_index),
                "status": "fallback_cross_bin",
                "reason": "no_finite_utility_in_bin"}
    score = clean[int(pose_index)].copy()
    if visibility is not None:
        vis = np.asarray(visibility, dtype=float)
        if vis.shape != (clean.shape[1],):
            raise ValueError("visibility must be per-landmark (134,)")
        score = np.where(vis < float(min_visible_fraction), -np.inf, score)
    score = np.where(np.isfinite(score), score, -np.inf)
    order = np.argsort(-score, kind="stable")
    indices = order[:int(count)].astype(np.int32)
    usable = int(np.isfinite(score[indices]).sum())
    requested = int(count)
    finite_in_bin = int(np.isfinite(clean[int(pose_index)]).sum())
    effective = min(requested, finite_in_bin)
    return {"indices": indices,
            "requested": requested,
            "effective": effective,
            "truncated": int(max(0, requested - usable)),
            "usable": usable,
            "sufficient": usable >= int(min_count),
            "pose_index": int(pose_index),
            "status": "per_bin_v1",
            "reason": ""}


def normalized_weights(values, pose_index: int) -> np.ndarray:
    if row_all_nan(values)[int(pose_index)]:
        # Fail-closed (F3): ни одного конечного значения в бине. Подставленная
        # межбинная медиана принадлежит чужой геометрии — равномерные веса,
        # никакого предпочтения точек по чужому бину.
        return np.ones(134, dtype=np.float32)
    clean=sanitize_utility(values)
    w=clean[int(pose_index)].copy()
    positive=w>0
    if not positive.any(): return np.ones(134,dtype=np.float32)
    w[~positive]=0.0
    w/=float(w[positive].mean())
    return w.astype(np.float32)
