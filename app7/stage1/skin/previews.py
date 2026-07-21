"""Preview rendering — controlled by preview_level: none | minimal | full.

Minimal: atlas usable overlay + wrinkle FFHQ heatmap (2 files)
Full: + quality weight + skeleton + ridge heatmap + geometry-vs-usable (5 more)
"""

from __future__ import annotations

import cv2
import numpy as np


def _zone_colors(n=20):
    return np.array([
        cv2.cvtColor(np.uint8([[[i * 9 % 180, 210, 230]]]), cv2.COLOR_HSV2BGR)[0, 0]
        for i in range(n)
    ], np.uint8)


def _atlas_overlay(bgr, A, mask):
    colors = _zone_colors(20)
    layer = bgr.copy()
    for i in range(20):
        layer[A == i] = colors[i]
    m = np.asarray(mask, bool)
    return np.where(m[..., None], cv2.addWeighted(bgr, 0.55, layer, 0.45, 0), bgr)


def _smooth_map(x, mask, sigma=1.2):
    x = np.asarray(x, np.float32)
    m = np.asarray(mask, bool)
    if not np.any(m):
        return np.zeros_like(x, dtype=np.float32)
    xf = np.where(m, x, 0.0).astype(np.float32)
    mf = m.astype(np.float32)
    xb = cv2.GaussianBlur(xf, (0, 0), sigma)
    mb = cv2.GaussianBlur(mf, (0, 0), sigma)
    out = np.zeros_like(x, dtype=np.float32)
    good = mb > 1e-6
    out[good] = xb[good] / mb[good]
    out[~m] = 0.0
    return out


def save_previews(root, bgr, A, mask, quality, usable_mask=None, level="minimal"):
    """Write preview images based on preview_level."""
    if level == "none":
        return
    root.mkdir(parents=True, exist_ok=True)
    A = np.asarray(A)
    geom = np.asarray(mask, bool)
    q = np.asarray(quality, np.float32)
    usable = np.asarray(usable_mask, bool) & geom if usable_mask is not None else geom & (q > 1e-6)

    # Always save usable overlay (most important diagnostic)
    cv2.imwrite(str(root / "atlas_A20_usable.png"), _atlas_overlay(bgr, A, usable))

    if level == "full":
        cv2.imwrite(str(root / "atlas_A20_geometry.png"), _atlas_overlay(bgr, A, geom))
        # Quality heatmap
        q_disp = _smooth_map(q, geom, sigma=1.4)
        if np.any(geom):
            p99 = float(np.percentile(q_disp[geom], 99)) + 1e-6
            q_norm = np.clip(q_disp / p99, 0, 1)
        else:
            q_norm = q_disp
        q8 = np.clip(q_norm * 255.0, 0, 255).astype(np.uint8)
        heat = cv2.applyColorMap(q8, cv2.COLORMAP_TURBO)
        cv2.imwrite(str(root / "quality_weight.png"), np.where(geom[..., None], heat, 0))
        # Geometry vs usable
        split = bgr.copy()
        only_geom = geom & ~usable
        split[only_geom] = (split[only_geom] * 0.35 + np.array([0, 0, 180], np.float32) * 0.65).astype(np.uint8)
        split[usable] = _atlas_overlay(bgr, A, usable)[usable]
        cv2.imwrite(str(root / "geometry_vs_usable.png"), split)


def save_wrinkle_overlay(root, bgr, skeleton, ridge_prob, ffhq_prob, mask, usable_mask=None, level="minimal"):
    """Write wrinkle preview images."""
    if level == "none":
        return
    root.mkdir(parents=True, exist_ok=True)
    geom = np.asarray(mask, bool)
    use = np.asarray(usable_mask, bool) if usable_mask is not None else geom

    # FFHQ heatmap (most useful)
    if ffhq_prob is not None and level in ("minimal", "full"):
        p = np.asarray(ffhq_prob, np.float32)
        p_s = _smooth_map(p, use, sigma=1.0)
        if np.any(use):
            p99 = float(np.percentile(p_s[use], 99)) + 1e-6
            p_n = np.clip(p_s / p99, 0, 1)
        else:
            p_n = p_s
        fh = cv2.applyColorMap(np.clip(p_n * 255.0, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        cv2.imwrite(str(root / "wrinkle_ffhq_heatmap.png"), np.where(use[..., None], fh, 0))

    if level == "full":
        sk = np.asarray(skeleton, bool)
        overlay = bgr.copy()
        overlay[sk & use] = [0, 0, 255]
        cv2.imwrite(str(root / "wrinkle_skeleton.png"), np.where(geom[..., None], overlay, bgr))
        # Classical ridge heatmap
        r = np.asarray(ridge_prob, np.float32)
        r_s = _smooth_map(r, use, sigma=1.0)
        if np.any(use):
            p99 = float(np.percentile(r_s[use], 99)) + 1e-6
            r_n = np.clip(r_s / p99, 0, 1)
        else:
            r_n = r_s
        heat = cv2.applyColorMap(np.clip(r_n * 255.0, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        cv2.imwrite(str(root / "wrinkle_ridge_heatmap.png"), np.where(use[..., None], heat, 0))
