"""Patch sampler — extract representative patches from atlas zones."""

from __future__ import annotations

import numpy as np


def sample_zone_patches(
    zone_map: np.ndarray, zone_id: int, quality_weight: np.ndarray,
    patch_size: int = 16, max_patches: int = 8, min_quality: float = 0.1,
) -> list[dict]:
    """Sample rectangular patches from a zone, preferring high-quality areas."""
    z = np.asarray(zone_map)
    qw = np.asarray(quality_weight, np.float32)
    mask = (z == zone_id) & (qw > min_quality)
    if not np.any(mask):
        return []
    # Find bounding box of zone
    ys, xs = np.where(mask)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    patches = []
    step = max(patch_size, (y1 - y0) // max_patches, (x1 - x0) // max_patches)
    pid = 0
    for py in range(y0, y1 - patch_size + 1, step):
        for px in range(x0, x1 - patch_size + 1, step):
            region = mask[py:py + patch_size, px:px + patch_size]
            support = float(qw[py:py + patch_size, px:px + patch_size][region].sum()) if np.any(region) else 0.0
            if support < 10:
                continue
            patches.append({
                "patch_id": f"z{zone_id:02d}_p{pid:03d}",
                "bbox_xyxy": (px, py, px + patch_size, py + patch_size),
                "pixel_count": int(region.sum()),
                "effective_support": support,
            })
            pid += 1
            if pid >= max_patches:
                return patches
    return patches
