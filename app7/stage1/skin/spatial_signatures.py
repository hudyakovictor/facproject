"""Spatial skin signatures — per-zone spatial histograms of unique features.

The key insight: same person → same unique skin structure at same anatomical
location. This module computes per-zone spatial signatures that capture WHERE
within a zone specific features (wrinkle density, pore density, texture
pattern) are located. This makes comparison far more robust than just
comparing mean feature values.

Signatures are computed relative to zone centroid, making them
approximately pose-invariant within a pose bin.
"""

from __future__ import annotations

import cv2
import numpy as np
from typing import Any


def compute_zone_spatial_signatures(
    bgr: np.ndarray,
    zone_id_a20: np.ndarray,
    quality_weight: np.ndarray,
    ridge_probability: np.ndarray | None = None,
    ffhq_probability: np.ndarray | None = None,
    domain_mask: np.ndarray | None = None,
    n_spatial_bins: int = 8,
) -> dict[str, Any]:
    """Compute per-zone spatial signature histograms.

    For each of the 20 A20 zones:
    1. Find zone pixels with quality > threshold
    2. Compute zone centroid
    3. Divide zone into spatial bins (quadrants relative to centroid)
    4. Compute per-bin: wrinkle density, mean texture energy, pore density

    This creates a spatial "fingerprint" for each zone that is far more
    discriminative than zone-wide averages.

    Args:
        bgr: Original BGR image
        zone_id_a20: (H, W) zone assignment map
        quality_weight: (H, W) quality weight map
        ridge_probability: (H, W) ridge probability (optional)
        ffhq_probability: (H, W) FFHQ wrinkle probability (optional)
        domain_mask: (H, W) valid domain mask
        n_spatial_bins: number of spatial bins per zone (4=quadrants, 8=octants)
    """
    H, W = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    # Gradient magnitude for texture energy
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = np.hypot(gx, gy)

    # Local entropy (approximated by local MAD)
    local_med = cv2.medianBlur(gray, 5)
    local_mad = np.abs(gray - local_med)

    domain = np.asarray(domain_mask, bool) if domain_mask is not None else np.ones((H, W), bool)
    qw = np.asarray(quality_weight, np.float32)

    zone_signatures = {}

    for zi in range(20):
        zone_mask = (zone_id_a20 == zi) & domain & (qw > 0.05)
        if not zone_mask.any():
            zone_signatures[f"A{zi + 1:02d}"] = {
                "status": "not_observed",
                "n_pixels": 0,
            }
            continue

        # Zone centroid
        ys, xs = np.where(zone_mask)
        cy, cx = float(np.mean(ys)), float(np.mean(xs))

        # Compute angle and distance from centroid for each zone pixel
        dy = ys - cy
        dx = xs - cx
        angles = np.arctan2(dy, dx)  # -π to π
        distances = np.hypot(dx, dy)

        # Assign spatial bin by angle
        angle_bins = np.floor((angles + np.pi) / (2 * np.pi) * n_spatial_bins).astype(int)
        angle_bins = np.clip(angle_bins, 0, n_spatial_bins - 1)

        # Per-spatial-bin features
        bin_features = []
        for bi in range(n_spatial_bins):
            bmask = angle_bins == bi
            if not bmask.any():
                bin_features.append({
                    "bin_id": bi,
                    "n_pixels": 0,
                    "wrinkle_density": 0.0,
                    "mean_texture_energy": 0.0,
                    "mean_local_mad": 0.0,
                    "mean_gray": 0.0,
                })
                continue

            bpx = zone_mask.copy()
            # Map back to 2D for indexing
            bin_ys = ys[bmask]
            bin_xs = xs[bmask]

            # Sample features in this spatial bin
            w = qw[bin_ys, bin_xs]
            w_sum = w.sum() + 1e-9

            # Wrinkle density
            wrinkle_dens = 0.0
            if ridge_probability is not None:
                rp = np.asarray(ridge_probability, np.float32)
                wrinkle_dens = float(np.average(rp[bin_ys, bin_xs], weights=w))

            ffhq_dens = 0.0
            if ffhq_probability is not None:
                fp = np.asarray(ffhq_probability, np.float32)
                ffhq_dens = float(np.average(fp[bin_ys, bin_xs], weights=w))

            bin_features.append({
                "bin_id": bi,
                "n_pixels": int(bmask.sum()),
                "wrinkle_density": wrinkle_dens,
                "ffhq_wrinkle_density": ffhq_dens,
                "mean_texture_energy": float(np.average(grad_mag[bin_ys, bin_xs], weights=w)),
                "mean_local_mad": float(np.average(local_mad[bin_ys, bin_xs], weights=w)),
                "mean_gray": float(np.average(gray[bin_ys, bin_xs], weights=w)),
            })

        zone_signatures[f"A{zi + 1:02d}"] = {
            "status": "usable" if len(ys) > 50 else "coarse_only",
            "n_pixels": int(len(ys)),
            "centroid_y": cy,
            "centroid_x": cx,
            "spatial_bins": bin_features,
        }

    return zone_signatures


def compare_zone_signatures(
    sig_a: dict[str, Any],
    sig_b: dict[str, Any],
) -> dict[str, Any]:
    """Compare spatial signatures between two photos.

    For each zone, compares the spatial distribution of features.
    Same person → same feature at same location → high correlation
    of spatial bin histograms.
    """
    results = {}
    zone_correlations = []

    for zi in range(20):
        key = f"A{zi + 1:02d}"
        sa = sig_a.get(key, {})
        sb = sig_b.get(key, {})

        if sa.get("status") not in ("usable", "coarse_only") or \
           sb.get("status") not in ("usable", "coarse_only"):
            results[key] = {"status": "not_comparable"}
            continue

        bins_a = sa.get("spatial_bins", [])
        bins_b = sb.get("spatial_bins", [])

        if len(bins_a) != len(bins_b) or not bins_a:
            results[key] = {"status": "bin_mismatch"}
            continue

        # Compare spatial distributions
        # Wrinkle density histogram
        wr_a = [b.get("wrinkle_density", 0) for b in bins_a]
        wr_b = [b.get("wrinkle_density", 0) for b in bins_b]
        tex_a = [b.get("mean_texture_energy", 0) for b in bins_a]
        tex_b = [b.get("mean_texture_energy", 0) for b in bins_b]
        mad_a = [b.get("mean_local_mad", 0) for b in bins_a]
        mad_b = [b.get("mean_local_mad", 0) for b in bins_b]
        gray_a = [b.get("mean_gray", 0) for b in bins_a]
        gray_b = [b.get("mean_gray", 0) for b in bins_b]

        wr_a, wr_b = np.array(wr_a), np.array(wr_b)
        tex_a, tex_b = np.array(tex_a), np.array(tex_b)
        mad_a, mad_b = np.array(mad_a), np.array(mad_b)
        gray_a, gray_b = np.array(gray_a), np.array(gray_b)

        def safe_corr(a, b):
            if len(a) < 3 or np.std(a) < 1e-9 or np.std(b) < 1e-9:
                return None
            return float(np.corrcoef(a, b)[0, 1])

        wr_corr = safe_corr(wr_a, wr_b)
        tex_corr = safe_corr(tex_a, tex_b)
        mad_corr = safe_corr(mad_a, mad_b)

        # Combined zone spatial similarity
        corrs = [c for c in [wr_corr, tex_corr, mad_corr] if c is not None]
        mean_corr = float(np.mean(corrs)) if corrs else None

        if mean_corr is not None:
            zone_correlations.append(mean_corr)

        results[key] = {
            "status": "compared",
            "wrinkle_spatial_corr": wr_corr,
            "texture_spatial_corr": tex_corr,
            "mad_spatial_corr": mad_corr,
            "mean_spatial_corr": mean_corr,
        }

    overall = float(np.mean(zone_correlations)) if zone_correlations else None

    return {
        "per_zone": results,
        "overall_spatial_correlation": overall,
        "n_compared_zones": len(zone_correlations),
    }
