"""Sampling provenance, including supersampling support and synthetic modifications."""
from __future__ import annotations

import numpy as np

MISSING, DIRECT, INTERPOLATED_OBSERVED, MIRROR, INPAINT, SYNTHETIC_OTHER = range(6)
METHOD_NAMES = {MISSING: "unavailable", DIRECT: "direct", INTERPOLATED_OBSERVED: "interpolated_observed",
                MIRROR: "mirror_fill", INPAINT: "inpaint", SYNTHETIC_OTHER: "synthetic_or_seam_modified"}


class TexelProvenance:
    def __init__(self, work_size: int, max_texels: int = 16_777_216):
        if work_size * work_size > max_texels:
            raise ValueError("provenance memory budget exceeded; reduce supersampling or UV size explicitly")
        self.size = work_size
        shape = (work_size, work_size)
        self.triangle_id = np.full(shape, -1, dtype=np.int32)
        self.barycentric = np.full((*shape, 3), np.nan, dtype=np.float32)
        self.source_xy = np.full((*shape, 2), np.nan, dtype=np.float32)
        self.weight = np.zeros(shape, dtype=np.float32)
        self.priority = np.full(shape, -np.inf, dtype=np.float32)
        self.in_bounds = np.zeros(shape, dtype=bool)
        self.geometry_visible = np.zeros(shape, dtype=bool)
        self.contribution_count = np.zeros(shape, dtype=np.uint16)

    def record(self, triangle_id, ys, xs, barycentric, source_xy, weight, in_bounds, geometry_visible):
        observed = in_bounds & geometry_visible & (weight > 0)
        score = np.where(observed, weight, np.where(in_bounds & geometry_visible, 0.0, -1.0))
        self.contribution_count[ys, xs] += 1
        update = (self.triangle_id[ys, xs] < 0) | (score > self.priority[ys, xs])
        y, x = ys[update], xs[update]
        self.triangle_id[y, x] = triangle_id
        self.barycentric[y, x] = barycentric[update]
        self.source_xy[y, x] = source_xy[update]
        self.weight[y, x] = np.where(observed[update], weight, 0)
        self.priority[y, x] = score[update]
        self.in_bounds[y, x] = in_bounds[update]
        self.geometry_visible[y, x] = geometry_visible[update]
        return update, observed

    def finish(self, super_sample: int) -> dict[str, np.ndarray]:
        target = self.size // super_sample

        def blocks(array):
            tail = array.shape[2:]
            shaped = array.reshape(target, super_sample, target, super_sample, *tail)
            axes = [0, 2, 1, 3, *range(4, shaped.ndim)]
            return shaped.transpose(axes).reshape(target, target, super_sample ** 2, *tail)

        ids, priority = blocks(self.triangle_id), blocks(self.priority)
        selected_index = priority.argmax(axis=2)
        selected_id = np.take_along_axis(ids, selected_index[..., None], axis=2)[..., 0]
        same = (ids == selected_id[..., None]) & (ids >= 0)
        observed = blocks(self.weight) > 0
        count = observed.sum(axis=2)
        observed_share = observed.mean(axis=2).astype(np.float32)
        denominator = np.maximum(same.sum(axis=2), 1)

        def primary_mean(array):
            values = blocks(array)
            weights = same[..., None] if values.ndim == 4 else same
            divisor = denominator[..., None] if values.ndim == 4 else denominator
            return (np.nansum(np.where(weights, values, 0), axis=2) / divisor).astype(np.float32)

        source_blocks = blocks(self.source_xy)
        source_mean = np.nansum(np.where(observed[..., None], source_blocks, 0), axis=2) / np.maximum(count[..., None], 1)
        primary_source = primary_mean(self.source_xy)
        source_mean[count == 0] = primary_source[count == 0]
        source_covariance = np.nansum(np.where(observed[..., None], (source_blocks - source_mean[..., None, :]) ** 2, 0), axis=2)
        source_covariance /= np.maximum(count[..., None], 1)
        source_min = np.min(np.where(observed[..., None], source_blocks, np.inf), axis=2)
        source_max = np.max(np.where(observed[..., None], source_blocks, -np.inf), axis=2)
        source_bounds = np.concatenate((source_min, source_max), axis=2).astype(np.float32)
        source_bounds[count == 0] = np.nan
        primary_fraction = np.sum(same & observed, axis=2) / np.maximum(count, 1)
        shape = (target, target)
        result = {
            "triangle_id": selected_id.astype(np.int32), "barycentric": primary_mean(self.barycentric),
            "source_xy": source_mean.astype(np.float32), "primary_source_xy": primary_source,
            "source_xy_variance": source_covariance.astype(np.float32), "sample_count": count.astype(np.uint16),
            "source_bounds": source_bounds,
            "observed_fraction": observed_share, "primary_fraction": primary_fraction.astype(np.float32),
            "weight": primary_mean(self.weight), "in_image": primary_mean(self.in_bounds.astype(float)) > 0.999,
            "geometry_visible": primary_mean(self.geometry_visible.astype(float)) > 0.999,
            "contribution_count": blocks(self.contribution_count).max(axis=2),
            "raw_method": np.where(count > 0, INTERPOLATED_OBSERVED, MISSING).astype(np.uint8),
            "external_occlusion": np.full(shape, -1, dtype=np.int8),
        }
        result["measurement_suitable"] = np.zeros(shape, dtype=bool)
        result["beauty_method"] = result["raw_method"].copy()
        result["beauty_modified"] = np.zeros(shape, dtype=bool)
        unavailable = selected_id < 0
        for key in ("barycentric", "source_xy", "primary_source_xy", "source_xy_variance"):
            result[key][unavailable] = np.nan
        return result


def apply_beauty_provenance(provenance: dict, masks: dict):
    method = provenance["beauty_method"]
    for key, value in (("mirror", MIRROR), ("inpaint", INPAINT), ("seam", SYNTHETIC_OTHER)):
        mask = np.asarray(masks.get(key, np.zeros_like(method)), dtype=bool)
        method[mask] = value
        provenance["beauty_modified"] |= mask


def measurement_mask(provenance: dict, min_weight: float = 0.05) -> np.ndarray:
    return (provenance["observed_fraction"] >= 0.999) & provenance["in_image"] & provenance["geometry_visible"] \
        & (provenance["weight"] >= min_weight) & (provenance["external_occlusion"] == 0) \
        & provenance.get("sampling_kernel_in_image", np.ones_like(provenance["in_image"]))
