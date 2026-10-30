"""Pose/detail-matched normal references with repeat-measured floors and abstention."""
from __future__ import annotations

import numpy as np

METRICS = ("anisotropy_3d_uv", "anisotropy_uv_photo", "density_uv_photo")


def fit_reference(training_records, repeat_differences, generation_id, provisional=False):
    if not training_records:
        return {"status": "insufficient_data", "reason": "no normal training records", "generation_id": generation_id}
    if any(row["partition"] != "train" for row in training_records):
        raise ValueError("normal reference fitting may only consume training sources")
    if any(row["generation_id"] != generation_id for row in training_records):
        raise ValueError("mixed generator configurations in normal reference")
    if not provisional and any(not row.get("label_current_verified", False) for row in training_records):
        return {"status": "insufficient_data", "reason": "current normal quality labels not verified", "generation_id": generation_id}
    pose = np.array([row["pose_detail"] for row in training_records], dtype=float)
    centre = np.median(pose, axis=0)
    scale = np.maximum(1.4826 * np.median(np.abs(pose - centre), axis=0), [5, 5, 0.25])
    reference = {"status": "provisional_reference" if provisional else "fitted", "generation_id": generation_id,
                 "sample_ids": [row["sample_id"] for row in training_records], "pose_detail": pose,
                 "pose_centre": centre, "pose_scale": scale, "minimum_support": 5, "metrics": {}, "floors": {}}
    for key in METRICS:
        matrix = np.array([np.log(np.maximum(row["metrics"][key], 1e-12)) for row in training_records], dtype=float)
        differences = np.array(repeat_differences.get(key, []), dtype=float)
        if differences.ndim != 2 or not len(differences):
            return {"status": "insufficient_data", "reason": "repeat-measured scale floors unavailable", "generation_id": generation_id}
        valid_columns = np.isfinite(differences).any(axis=0)
        floors = np.full(matrix.shape[1], np.nan)
        floors[valid_columns] = 1.4826 * np.nanmedian(np.abs(differences[:, valid_columns]), axis=0)
        positive = floors[np.isfinite(floors) & (floors > 1e-8)]
        if not len(positive):
            return {"status": "insufficient_data", "reason": "no measurable repeatability floor", "generation_id": generation_id}
        # A measured low quantile substitutes for zeros; no arbitrary near-zero division.
        floors = np.maximum(np.nan_to_num(floors, nan=np.quantile(positive, 0.1)), np.quantile(positive, 0.1))
        reference["metrics"][key] = matrix
        reference["floors"][key] = floors
    return reference


def score_reference(reference, metrics, pose_detail):
    if reference["status"] not in ("fitted", "provisional_reference"):
        return {"status": "insufficient_data", "reason": reference.get("reason")}
    pose = np.asarray(pose_detail, dtype=float)
    candidates = reference["pose_detail"]
    differences = candidates - pose
    compatible = (np.abs(differences[:, 0]) <= 15) & (np.abs(differences[:, 1]) <= 15) & (np.abs(differences[:, 2]) <= np.log(2))
    distance = np.linalg.norm(differences / reference["pose_scale"], axis=1)
    selected = np.flatnonzero(compatible)[np.argsort(distance[compatible])][:12]
    if len(selected) < reference["minimum_support"]:
        return {"status": "insufficient_data", "reason": "too few comparable normal source/pose/detail observations"}
    result = {"status": reference["status"], "support_samples": len(selected), "deviation": {}, "triangle_support": {}}
    for key in METRICS:
        values = reference["metrics"][key][selected]
        support = np.isfinite(values).sum(axis=0)
        valid_columns = support > 0
        centre, sigma = np.full(values.shape[1], np.nan), np.full(values.shape[1], np.nan)
        centre[valid_columns] = np.nanmedian(values[:, valid_columns], axis=0)
        sigma[valid_columns] = 1.4826 * np.nanmedian(np.abs(values[:, valid_columns] - centre[valid_columns]), axis=0)
        scale = np.maximum(sigma, reference["floors"][key])
        z = (np.log(np.maximum(metrics[key], 1e-12)) - centre) / scale
        z[support < reference["minimum_support"]] = np.nan
        if key != "anisotropy_3d_uv" and "triangle_visible" in metrics:
            z[~np.asarray(metrics["triangle_visible"], dtype=bool)] = np.nan
        result["deviation"][key] = z
        result["triangle_support"][key] = support
    result["interpretation"] = "Unusual transport relative to comparable training normals, not an automatic defect/material verdict."
    return result
