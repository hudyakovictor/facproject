"""🎯 CRITICAL → Политика стабильных якорей (точки, неподвижные при мимике).
🚪 API: stable_anchor_mask(), stable_anchor_indices()
🔗 DEPENDS ON: core.robust_rigid_align — якоря подаются туда для выравнивания
💡 NOTE: неверный якорь = смещение всех motion-метрик пары.
"""
from __future__ import annotations
from app6.stage1.status_logger import log_status

from .landmark_policy import subset_for_bin

import numpy as np

ANCHOR_SCHEMA = "deeputin-stage2-stable-anchor-policy-v1.0"


def stable_anchor_mask(points: np.ndarray, common_visible: np.ndarray, *, min_count: int = 24) -> tuple[np.ndarray, dict[str, float | int | str]]:
    """Choose conservative central-face anchors for pair alignment.

    This is a deterministic fallback policy until calibration-ranked anatomical anchors
    are introduced. It avoids using the full face for alignment, reducing the chance that
    soft peripheral/mouth/jaw changes are absorbed by the transform.
    """
    log_status("stable_anchor_mask", "complete")
    p = np.asarray(points, np.float32)
    common = np.asarray(common_visible, bool)
    anchor = np.zeros(len(p), bool)
    if p.ndim != 2 or p.shape[1] != 3 or int(common.sum()) < min_count:
        return common.copy(), {
            "anchor_policy": "fallback_all_common_insufficient_input",
            "anchor_count": int(common.sum()),
            "anchor_fraction": float(common.mean()) if common.size else 0.0,
        }
    qx1, qx2 = np.quantile(p[common, 0], [0.18, 0.82])
    qy1, qy2 = np.quantile(p[common, 1], [0.18, 0.78])
    qz1, qz2 = np.quantile(p[common, 2], [0.08, 0.92])
    anchor = common & (p[:, 0] >= qx1) & (p[:, 0] <= qx2) & (p[:, 1] >= qy1) & (p[:, 1] <= qy2) & (p[:, 2] >= qz1) & (p[:, 2] <= qz2)
    policy = "central_quantile_anchor_v1"
    if int(anchor.sum()) < min_count:
        # Relax vertical/depth gates before falling back to all common points.
        anchor = common & (p[:, 0] >= qx1) & (p[:, 0] <= qx2)
        policy = "central_x_anchor_relaxed_v1"
    if int(anchor.sum()) < min_count:
        anchor = common.copy()
        policy = "fallback_all_common_too_few_anchors"
    return anchor, {
        "anchor_policy": policy,
        "anchor_count": int(anchor.sum()),
        "anchor_fraction": float(anchor.sum() / max(int(common.sum()), 1)),
    }


def stable_anchor_indices(points: np.ndarray, common_indices: np.ndarray, *, max_points: int = 6000, min_count: int = 1200) -> tuple[np.ndarray, dict[str, float | int | str]]:
    log_status("stable_anchor_indices", "complete")
    common = np.asarray(common_indices, np.int64)
    mask = np.zeros(len(points), bool)
    mask[common[(common >= 0) & (common < len(points))]] = True
    anchor_mask, meta = stable_anchor_mask(points, mask, min_count=min_count)
    ids = np.flatnonzero(anchor_mask)
    if ids.size > max_points:
        step = int(np.ceil(ids.size / max_points))
        ids = ids[::step][:max_points]
        meta = dict(meta)
        meta["anchor_subsample_step"] = step
        meta["anchor_count_after_subsample"] = int(ids.size)
    return ids.astype(np.int64), meta


def per_bin_anchor_mask(points: np.ndarray, common_visible: np.ndarray, *, pose_bin: str,
                        utility: np.ndarray, visibility_prior: np.ndarray,
                        min_count: int = 15, bin_names=None) -> tuple[np.ndarray, dict[str, float | int | str]]:
    """Per-pose-bin anchor selection from calibration-ranked landmark utility (patch 6/A11).

    Uses ``subset_for_bin`` ranked by per-bin utility with a visibility floor.
    Falls back to ``stable_anchor_mask`` whenever the per-bin subset cannot
    reach ``min_count`` usable anchors, the pose bin is unknown, or the
    artifacts are malformed.
    """
    stable, meta = stable_anchor_mask(points, common_visible, min_count=min_count)
    try:
        if bin_names is None or pose_bin not in bin_names:
            return stable, {**meta, "anchor_source": "stable_fallback_unknown_bin"}
        bi = int(bin_names.index(pose_bin))
        u = np.asarray(utility, dtype=float)
        prior = np.asarray(visibility_prior, dtype=float)
        if u.ndim != 2 or u.shape[0] <= bi or prior.ndim != 2 or prior.shape[0] <= bi:
            return stable, {**meta, "anchor_source": "stable_fallback_bad_artifact_shape"}
        count = max(int(min_count), int(round(len(points) * 0.4)))
        sel = subset_for_bin(u, bi, count=count, visibility=prior[bi],
                             min_visible_fraction=0.60, min_count=int(min_count))
        if sel.get("status") == "fallback_cross_bin":
            # All-NaN utility row: the sanitized cross-bin median is NOT per-bin
            # coverage.  Fall back explicitly and surface it in the manifest.
            return stable, {**meta, "anchor_source": "fallback_cross_bin",
                            "fallback_reason": sel.get("reason")}
        if not sel.get("sufficient") or not sel.get("usable"):
            return stable, {**meta, "anchor_source": "stable_fallback_insufficient_subset"}
        idx = np.asarray(sel["indices"], dtype=np.int64)
        mask = np.zeros(len(points), dtype=bool)
        valid = (idx >= 0) & (idx < len(points))
        mask[idx[valid]] = True
        mask &= common_visible
        if int(mask.sum()) < int(min_count):
            return stable, {**meta, "anchor_source": "stable_fallback_common_too_small"}
        return mask, {"anchor_policy": "per_bin_subset_v1",
                      "anchor_count": int(mask.sum()),
                      "anchor_fraction": float(mask.sum() / max(int(common_visible.sum()), 1)),
                      "anchor_source": "per_bin_subset_v1",
                      "requested": sel.get("requested"), "effective": sel.get("effective"),
                      "usable": sel.get("usable")}
    except Exception:
        return stable, {**meta, "anchor_source": "stable_fallback_error"}
