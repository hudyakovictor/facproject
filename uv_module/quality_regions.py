"""Model-semantic UV regions; explicit proxies until manually validated."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .uv_semantic import build_semantic_uv_masks

NAMES = ["eyes", "brows", "nasal_bridge", "nose", "lips", "cheeks", "lower_contour", "chin", "forehead", "other"]
_REGION_CACHE = {}


def build_regions(uv_coords, triangles, uv_size, asset_path: Path):
    cache_key = (str(asset_path), asset_path.stat().st_mtime_ns, uv_size,
                 hash(np.asarray(uv_coords).tobytes()), hash(np.asarray(triangles).tobytes()))
    if cache_key in _REGION_CACHE:
        return _REGION_CACHE[cache_key]
    basis = np.load(asset_path, allow_pickle=True).item()
    mean = np.asarray(basis["u"], dtype=float).reshape(-1, 3)[:len(uv_coords)]
    l106 = np.asarray(basis["ldm106"], dtype=int)
    annotation = [set(np.asarray(group, dtype=int).tolist()) for group in basis["annotation"]]
    eye_y = float(mean[l106[[74, 83]], 1].mean())
    mouth_y, chin_y = float(mean[l106[[87, 93]], 1].mean()), float(mean[l106[16], 1])
    x = np.abs(mean[:, 0])
    max_x = float(np.max(x))
    skin = np.array([index in annotation[7] for index in range(len(mean))])
    groups = {"eyes": annotation[0] | annotation[1], "brows": annotation[2] | annotation[3],
              "nose": annotation[4], "lips": annotation[5] | annotation[6],
              "nasal_bridge": {index for index in annotation[4] if mean[index, 1] > mean[l106[54], 1]},
              "cheeks": set(np.flatnonzero(skin & (mean[:, 1] < eye_y) & (mean[:, 1] > mouth_y) & (x > 0.25 * max_x))),
              "lower_contour": set(np.flatnonzero(skin & (mean[:, 1] <= mouth_y) & (x >= 0.25 * max_x))),
              "chin": set(np.flatnonzero(skin & (mean[:, 1] < (mouth_y + chin_y) / 2) & (x < 0.25 * max_x))),
              "forehead": set(np.flatnonzero(skin & (mean[:, 1] > eye_y + 0.2 * (eye_y - mouth_y)))),
              "other": set(range(len(mean)))}
    vertex_labels = np.full(len(mean), len(NAMES) - 1, dtype=int)
    for name in reversed(NAMES[:-1]):
        vertex_labels[list(groups[name])] = NAMES.index(name)
    groups["other"] = set(np.flatnonzero(vertex_labels == len(NAMES) - 1))
    memberships = vertex_labels[np.asarray(triangles, dtype=int)]
    counts = np.stack([np.sum(memberships == index, axis=1) for index in range(len(NAMES))], axis=1)
    triangle_regions = counts.argmax(axis=1)
    masks = build_semantic_uv_masks(uv_coords, triangles, uv_size, zone_names=NAMES,
                                    macro_indices={name: frozenset(groups[name]) for name in NAMES})
    triangle_regions.flags.writeable = False
    for mask in masks.values():
        mask.flags.writeable = False
    result = (triangle_regions, masks, {"names": NAMES, "method": "8 model semantic parts plus mean-template skin bands",
                                      "validation_status": "model_proxy_not_manual_ground_truth"})
    _REGION_CACHE[cache_key] = result
    return result
