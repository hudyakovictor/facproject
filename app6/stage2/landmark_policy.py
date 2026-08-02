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


def stable_subset(values, count: int = 91) -> np.ndarray:
    """Return exactly `count` indices ranked by conservative cross-bin utility."""
    if not 1 <= int(count) <= 134: raise ValueError("count must be in 1..134")
    clean=sanitize_utility(values)
    score=np.min(clean,axis=0)
    # Stable sort makes ties deterministic across platforms.
    return np.argsort(-score,kind="stable")[:int(count)].astype(np.int32)


def normalized_weights(values, pose_index: int) -> np.ndarray:
    clean=sanitize_utility(values)
    w=clean[int(pose_index)].copy()
    positive=w>0
    if not positive.any(): return np.ones(134,dtype=np.float32)
    w[~positive]=0.0
    w/=float(w[positive].mean())
    return w.astype(np.float32)
