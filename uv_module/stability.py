"""Controlled input-processing sensitivity, not full statistical uncertainty."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .reconstruction_adapter import reconstruct_for_uv
from .warp_metrics import triangle_warp_metrics, visible_photo_metrics, weighted_quantiles

PRESETS = ("small_symmetric_crop", "small_offset_crop", "reduced_resolution_jpeg")


def processing_variant(image, preset):
    height, width = image.shape[:2]
    if preset == "small_symmetric_crop":
        x0, y0 = int(round(width * 0.01)), int(round(height * 0.01))
        cropped = image[y0:height - y0, x0:width - x0]
        scale = 1.0
    elif preset == "small_offset_crop":
        x0, y0 = int(round(width * 0.02)), 0
        cropped = image[:, x0:]
        scale = 1.0
    elif preset == "reduced_resolution_jpeg":
        x0, y0, cropped, scale = 0, 0, image, 0.75
    else:
        raise ValueError("unknown controlled processing preset")
    new_width, new_height = int(round(cropped.shape[1] * scale)), int(round(cropped.shape[0] * scale))
    processed = cv2.resize(cropped, (new_width, new_height), interpolation=cv2.INTER_AREA) if scale != 1 else cropped.copy()
    sx, sy = new_width / cropped.shape[1], new_height / cropped.shape[0]
    to_original = np.array([[1 / sx, 0, x0 + 0.5 / sx - 0.5], [0, 1 / sy, y0 + 0.5 / sy - 0.5], [0, 0, 1]], dtype=float)
    return processed, to_original


def geometry_repeats(image, base_recon, uv_size, output: Path, reconstruction_cache: Path,
                     generator_config=None, base_raw=None, base_observed=None, base_triangle_visible=None):
    output.mkdir(parents=True, exist_ok=True)
    base = triangle_warp_metrics(base_recon["vertices_object"], base_recon["triangles"], base_recon["uv_coords"], base_recon["vertices_2d"], uv_size)
    if base_triangle_visible is None:
        base_triangle_visible = np.zeros(len(base_recon["triangles"]), dtype=bool)
    base = visible_photo_metrics(base, base_triangle_visible)
    reports, differences, variant_metrics = [], {}, []
    for preset in PRESETS:
        processed, transform = processing_variant(image, preset)
        extension = ".jpg" if preset == "reduced_resolution_jpeg" else ".png"
        path = output / (preset + extension)
        options = [cv2.IMWRITE_JPEG_QUALITY, 85] if extension == ".jpg" else []
        if not cv2.imwrite(str(path), processed, options):
            raise ValueError("cannot save controlled processing variant")
        _, recon, _ = reconstruct_for_uv(path, reconstruction_cache)
        if not np.array_equal(recon["triangles"], base_recon["triangles"]):
            raise ValueError("topology changed across processing variants")
        projection = np.column_stack((recon["vertices_2d"], np.ones(len(recon["vertices_2d"])))) @ transform.T
        metrics = triangle_warp_metrics(recon["vertices_object"], recon["triangles"], recon["uv_coords"], projection[:, :2], uv_size)
        summary = {"preset": preset, "variant_to_original": transform.tolist(), "metrics": {}}
        if generator_config is not None:
            from .hd_uv_generator import HDUVTextureGenerator
            recon["vertices_2d"] = projection[:, :2].astype(np.float32)
            recon["projection_space"] = "original"
            _, _, observed, _, aux = HDUVTextureGenerator(generator_config).generate(image, recon)
            metrics = visible_photo_metrics(metrics, aux["tri_visibility"] > 0)
            variant_raw = aux["uv_texture_raw"]
            np.savez_compressed(output / (preset + "_raw_uv.npz"), raw_uv=variant_raw, observed=observed,
                                triangle_visible=metrics["triangle_visible"],
                                anisotropy_uv_photo=metrics["anisotropy_uv_photo"], density_uv_photo=metrics["density_uv_photo"])
            if base_raw is not None and base_observed is not None:
                common = observed & base_observed
                union = observed | base_observed
                difference = np.linalg.norm(variant_raw - base_raw, axis=2) / (255 * np.sqrt(3))
                summary["raw_uv_sensitivity"] = {
                    "common_observed_fraction": float(common.mean()),
                    "observed_map_jaccard": float(common.sum() / max(union.sum(), 1)),
                    "median_normalized_color_change": float(np.median(difference[common])) if common.any() else None,
                    "p95_normalized_color_change": float(np.quantile(difference[common], 0.95)) if common.any() else None,
                     "scope": "transport/input-processing sensitivity on original observed colors; not skin/material uncertainty"}
        else:
            metrics = visible_photo_metrics(metrics, np.zeros(len(recon["triangles"]), dtype=bool))
        variant_metrics.append(metrics)
        summary["photo_common_visible_triangle_fraction"] = float((base["triangle_visible"] & metrics["triangle_visible"]).mean())
        summary["photo_metric_scope"] = "triangles visible in both base and controlled reconstruction"
        for key in ("anisotropy_3d_uv", "anisotropy_uv_photo", "density_uv_photo"):
            delta = np.log(np.maximum(metrics[key], 1e-12)) - np.log(np.maximum(base[key], 1e-12))
            differences.setdefault(key, []).append(delta)
            median, p95 = weighted_quantiles(np.abs(delta), base["area_surface"], (0.5, 0.95))
            summary["metrics"][key] = {"median_abs_log_change": float(median), "p95_abs_log_change": float(p95)}
        reports.append(summary)
    return reports, differences, variant_metrics
