"""Transport consistency and strictly masked texture features, never material inference."""
from __future__ import annotations

import cv2
import numpy as np


def scalar_texture(gray: np.ndarray, mask: np.ndarray) -> dict:
    if mask.sum() < 128:
        return {"status": "insufficient_data", "usable_texels": int(mask.sum())}
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0) / 8
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1) / 8
    xx, yy, xy = float(np.mean(gx[mask] ** 2)), float(np.mean(gy[mask] ** 2)), float(np.mean(gx[mask] * gy[mask]))
    features = {"status": "measured", "usable_texels": int(mask.sum()), "gradient_energy": xx + yy,
                "directional_coherence": float(np.sqrt((xx - yy) ** 2 + 4 * xy ** 2) / max(xx + yy, 1e-8)),
                "laplacian_variance": float(np.var(cv2.Laplacian(gray, cv2.CV_32F)[mask]))}
    for sigma in (1, 2, 4):
        smooth = cv2.GaussianBlur(gray, (0, 0), sigma)
        features[f"band_energy_sigma{sigma}"] = float(np.mean((gray[mask] - smooth[mask]) ** 2))
    return features


def texture_diagnostics(original, raw, provenance, triangle_metrics, region_masks):
    original_gray = cv2.cvtColor(original.astype(np.float32), cv2.COLOR_BGR2GRAY)
    uv_gray = cv2.cvtColor(raw.astype(np.float32), cv2.COLOR_BGR2GRAY)
    support = (provenance["observed_fraction"] >= 0.999) & provenance["geometry_visible"] & provenance["in_image"] \
        & (provenance["primary_fraction"] >= 0.999)
    support = cv2.erode(support.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    source_xy = np.nan_to_num(provenance["source_xy"], nan=-100)
    sampled_gray = cv2.remap(original_gray, source_xy[..., 0], source_xy[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    source_gx = cv2.Sobel(original_gray, cv2.CV_32F, 1, 0) / 8
    source_gy = cv2.Sobel(original_gray, cv2.CV_32F, 0, 1) / 8
    sampled_gx = cv2.remap(source_gx, source_xy[..., 0], source_xy[..., 1], cv2.INTER_LINEAR)
    sampled_gy = cv2.remap(source_gy, source_xy[..., 0], source_xy[..., 1], cv2.INTER_LINEAR)
    uv_gx, uv_gy = cv2.Sobel(uv_gray, cv2.CV_32F, 1, 0) / 8, cv2.Sobel(uv_gray, cv2.CV_32F, 0, 1) / 8
    ids = provenance["triangle_id"]
    valid = support & (ids >= 0)
    expected_x, expected_y = np.zeros_like(uv_gray), np.zeros_like(uv_gray)
    matrices = triangle_metrics["jacobian_uv_photo"][ids[valid]]
    expected_x[valid] = matrices[:, 0, 0] * sampled_gx[valid] + matrices[:, 1, 0] * sampled_gy[valid]
    expected_y[valid] = matrices[:, 0, 1] * sampled_gx[valid] + matrices[:, 1, 1] * sampled_gy[valid]
    difference = np.sqrt((uv_gx - expected_x) ** 2 + (uv_gy - expected_y) ** 2)
    output = {}
    for name, region in region_masks.items():
        eligible = valid & region
        count = int(eligible.sum())
        row = {"transport_usable_texels": count,
               "transport_gradient_residual_median": float(np.median(difference[eligible])) if count else None,
               "transport_color_residual_median": float(np.median(np.abs(uv_gray[eligible] - sampled_gray[eligible]))) if count else None,
               "transport_scope": "sampling consistency of observed colors, not skin/material properties"}
        skin_mask = eligible & provenance["measurement_suitable"]
        row["strict_raw_texture"] = scalar_texture(uv_gray, skin_mask)
        row["corresponding_source_texture"] = scalar_texture(sampled_gray, skin_mask)
        if count:
            row["source_density_median"] = float(np.nanmedian(provenance["source_density"][eligible]))
        output[name] = row
    return output
