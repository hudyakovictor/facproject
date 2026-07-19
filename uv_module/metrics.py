"""Texture-detail and skin-microstructure metrics (scikit-image + skan).

All functions operate on the ANALYTIC texture only, restricted to a boolean
mask of real observed pixels. Never feed the morph texture here: its hidden
half is synthetic by construction.

scikit-image and skan are optional at import time (graceful degradation with an
explicit `available` flag) so stage1 can run without the analytics stack.
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

try:
    from skimage.feature import graycomatrix, graycoprops, local_binary_pattern
    from skimage.filters import sato, threshold_yen
    from skimage.morphology import remove_small_objects, skeletonize
    _HAS_SKIMAGE = True
except Exception:  # pragma: no cover
    _HAS_SKIMAGE = False

try:
    from skan import Skeleton, summarize
    _HAS_SKAN = True
except Exception:  # pragma: no cover
    _HAS_SKAN = False


def texture_detail_report(gray: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    """Objective detail/sharpness metrics for comparing texture pipelines
    (e.g. stock 512 per-vertex texture vs uv_module analytic texture)."""
    g = np.asarray(gray, np.float32)
    m = np.asarray(mask, bool)
    if not m.any():
        return {"pixels": 0.0}
    lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
    hp = g - cv2.GaussianBlur(g, (0, 0), 2.0)
    out = {
        "pixels": float(m.sum()),
        "laplacian_var": float(np.var(lap[m])),
        "highfreq_energy": float(np.mean(hp[m] ** 2)),
        "local_std": float(np.mean(cv2.blur((g - cv2.blur(g, (7, 7))) ** 2, (7, 7))[m]) ** 0.5),
        "dynamic_range_p2_p98": float(np.percentile(g[m], 98) - np.percentile(g[m], 2)),
    }
    if _HAS_SKIMAGE:
        lbp = local_binary_pattern(np.clip(g, 0, 255).astype(np.uint8), P=8, R=1, method="uniform")
        hist, _ = np.histogram(lbp[m], bins=10, range=(0, 10), density=True)
        hist = hist + 1e-12
        out["lbp_entropy"] = float(-np.sum(hist * np.log2(hist)))
        q = (np.clip(g, 0, 255) / 16).astype(np.uint8)
        q[~m] = 0
        glcm = graycomatrix(q, distances=[1, 2], angles=[0, np.pi / 2], levels=16, symmetric=True, normed=True)
        out["glcm_contrast"] = float(np.mean(graycoprops(glcm, "contrast")))
        out["glcm_homogeneity"] = float(np.mean(graycoprops(glcm, "homogeneity")))
    return out


def wrinkle_graph_features(gray: np.ndarray, mask: np.ndarray, min_object_px: int = 24) -> dict[str, Any]:
    """Skeleton-graph statistics of the wrinkle/micro-relief network via skan.

    Pipeline: Sato ridge filter -> Yen threshold inside the mask -> small-object
    removal -> skeletonize -> skan.Skeleton -> branch statistics. Returns
    dimensionless per-area densities usable in chronological series.
    """
    if not (_HAS_SKIMAGE and _HAS_SKAN):
        return {"available": False, "reason": "scikit-image and/or skan not installed"}
    g = np.asarray(gray, np.float32) / 255.0
    m = np.asarray(mask, bool)
    if m.sum() < 400:
        return {"available": False, "reason": "mask too small"}
    ridges = sato(g, sigmas=(1.0, 1.5, 2.0), black_ridges=True)
    r = ridges[m]
    try:
        thr = float(threshold_yen((r * 65535).astype(np.uint16))) / 65535.0
    except Exception:
        thr = float(np.percentile(r, 90))
    binary = np.zeros_like(m)
    binary[m] = ridges[m] > thr
    binary = remove_small_objects(binary, min_size=min_object_px)
    skel = skeletonize(binary)
    if skel.sum() < 10:
        return {"available": True, "n_branches": 0, "skeleton_px": int(skel.sum())}
    try:
        sk = Skeleton(skel)
        stats = summarize(sk, separator="_")
    except Exception as exc:
        return {"available": False, "reason": f"skan failed: {exc}"}
    area_kpx = float(m.sum()) / 1000.0
    lengths = stats["branch_distance"].to_numpy(np.float64)
    branch_types = stats["branch_type"].to_numpy(np.int64)
    return {
        "available": True,
        "n_branches": int(len(stats)),
        "total_length_px": float(lengths.sum()),
        "mean_branch_length_px": float(lengths.mean()),
        "median_branch_length_px": float(np.median(lengths)),
        "junction_to_junction_frac": float(np.mean(branch_types == 2)),
        "endpoint_branches_frac": float(np.mean(branch_types < 2)),
        "branch_density_per_kpx": float(len(stats) / max(area_kpx, 1e-6)),
        "length_density_per_kpx": float(lengths.sum() / max(area_kpx, 1e-6)),
        "skeleton_px": int(skel.sum()),
        "mask_px": int(m.sum()),
    }
