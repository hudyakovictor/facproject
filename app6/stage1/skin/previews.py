"""Preview writers: no mesh-grid imprint on analysis heatmaps."""
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
    """Gaussian smooth inside mask only; outside stays 0. Removes triangle faceting on renders."""
    x = np.asarray(x, np.float32)
    m = np.asarray(mask, bool)
    if not np.any(m):
        return np.zeros_like(x, dtype=np.float32)
    # blur value and mask, then renormalize to avoid dark edge shrinkage
    xf = np.where(m, x, 0.0).astype(np.float32)
    mf = m.astype(np.float32)
    xb = cv2.GaussianBlur(xf, (0, 0), sigma)
    mb = cv2.GaussianBlur(mf, (0, 0), sigma)
    out = np.zeros_like(x, dtype=np.float32)
    good = mb > 1e-6
    out[good] = xb[good] / mb[good]
    out[~m] = 0.0
    return out


def save_previews(root, bgr, A, mask, quality, usable_mask=None):
    """Write geometry atlas + smooth quality heatmap + usable-only atlas."""
    root.mkdir(parents=True, exist_ok=True)
    A = np.asarray(A)
    geom = np.asarray(mask, bool)
    q = np.asarray(quality, np.float32)
    if usable_mask is None:
        usable_mask = geom & (q > 1e-6)
    else:
        usable_mask = np.asarray(usable_mask, bool) & geom

    cv2.imwrite(str(root / 'atlas_A20_overlay.png'), _atlas_overlay(bgr, A, geom))
    cv2.imwrite(str(root / 'atlas_A20_overlay_usable.png'), _atlas_overlay(bgr, A, usable_mask))

    # geometry vs usable diagnostic (no mesh dependency)
    split = bgr.copy()
    only_geom = geom & ~usable_mask
    split[only_geom] = (split[only_geom] * 0.35 + np.array([0, 0, 180], np.float32) * 0.65).astype(np.uint8)
    split[usable_mask] = _atlas_overlay(bgr, A, usable_mask)[usable_mask]
    cv2.imwrite(str(root / 'atlas_geometry_vs_usable.png'), split)

    # IMPORTANT: smooth quality for display so triangle mesh is not visible
    q_disp = _smooth_map(q, geom, sigma=1.4)
    # mild percentile stretch for readability without amplifying noise
    if np.any(geom):
        p99 = float(np.percentile(q_disp[geom], 99)) + 1e-6
        q_norm = np.clip(q_disp / p99, 0, 1)
    else:
        q_norm = q_disp
    q8 = np.clip(q_norm * 255.0, 0, 255).astype(np.uint8)
    heat = cv2.applyColorMap(q8, cv2.COLORMAP_TURBO)
    cv2.imwrite(str(root / 'quality_weight.png'), np.where(geom[..., None], heat, 0))
    # raw (unsmoothed) optional diagnostic
    q8_raw = np.clip(np.clip(q, 0, None) / (float(np.percentile(q[geom], 99)) + 1e-6 if np.any(geom) else 1.0) * 255.0, 0, 255).astype(np.uint8)
    heat_raw = cv2.applyColorMap(q8_raw, cv2.COLORMAP_TURBO)
    cv2.imwrite(str(root / 'quality_weight_raw_mesh.png'), np.where(geom[..., None], heat_raw, 0))


def save_wrinkle_overlay(root, bgr, skeleton, ridge_prob, ffhq_prob, mask, usable_mask=None):
    root.mkdir(parents=True, exist_ok=True)
    geom = np.asarray(mask, bool)
    use = np.asarray(usable_mask, bool) if usable_mask is not None else geom

    sk = np.asarray(skeleton, bool)
    overlay = bgr.copy()
    overlay[sk & use] = [0, 0, 255]
    cv2.imwrite(str(root / 'wrinkle_skeleton.png'), np.where(geom[..., None], overlay, bgr))

    r = np.asarray(ridge_prob, np.float32)
    r_s = _smooth_map(r, use, sigma=1.0)
    if np.any(use):
        p99 = float(np.percentile(r_s[use], 99)) + 1e-6
        r_n = np.clip(r_s / p99, 0, 1)
    else:
        r_n = r_s
    r8 = np.clip(r_n * 255.0, 0, 255).astype(np.uint8)
    heat = cv2.applyColorMap(r8, cv2.COLORMAP_TURBO)
    cv2.imwrite(str(root / 'wrinkle_ridge_heatmap.png'), np.where(use[..., None], heat, 0))
    # geometry-domain version also smoothed
    r_sg = _smooth_map(r, geom, sigma=1.0)
    if np.any(geom):
        p99g = float(np.percentile(r_sg[geom], 99)) + 1e-6
        r_ng = np.clip(r_sg / p99g, 0, 1)
    else:
        r_ng = r_sg
    heat_g = cv2.applyColorMap(np.clip(r_ng * 255.0, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    cv2.imwrite(str(root / 'wrinkle_ridge_heatmap_geometry.png'), np.where(geom[..., None], heat_g, 0))

    if ffhq_prob is not None:
        p = np.asarray(ffhq_prob, np.float32)
        p_s = _smooth_map(p, use, sigma=1.0)
        if np.any(use):
            p99 = float(np.percentile(p_s[use], 99)) + 1e-6
            p_n = np.clip(p_s / p99, 0, 1)
        else:
            p_n = p_s
        fh = cv2.applyColorMap(np.clip(p_n * 255.0, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        cv2.imwrite(str(root / 'wrinkle_ffhq_heatmap.png'), np.where(use[..., None], fh, 0))
