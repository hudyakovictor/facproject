"""Import version-bound manual annotations and measure blind repeat agreement."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


def import_annotations(manifest: pd.DataFrame, paths: list[Path]) -> tuple[pd.DataFrame, dict]:
    result = manifest.copy()
    if "label_generation_id" not in result:
        result["label_generation_id"] = None
        result["label_current_verified"] = False
    if "manual_contours_json" not in result:
        result["manual_contours_json"] = "{}"
        result["contour_manual_validated"] = False
        result["annotation_history_json"] = "[]"
    errors, accepted = [], 0
    for path in paths:
        annotation = json.loads(path.read_text())
        match = result.sample_id.eq(annotation.get("sample_id"))
        if match.sum() != 1 or not annotation.get("manual") or not annotation.get("observer_id"):
            errors.append({"path": str(path), "reason": "missing manual observer or unknown sample"})
            continue
        row = result.loc[match].iloc[0]
        if annotation.get("source_sha256") != row.source_sha256 or not annotation.get("generation_id"):
            errors.append({"path": str(path), "reason": "source/generator binding mismatch"})
            continue
        if annotation.get("round") == "round2_blind" and not annotation.get("blind_to_prior"):
            errors.append({"path": str(path), "reason": "repeat round was not blind"})
            continue
        label = annotation.get("quality_label_current")
        if label not in (None, "normal", "distorted"):
            errors.append({"path": str(path), "reason": "unknown UV quality class"})
            continue
        history = json.loads(row.get("annotation_history_json") or "[]")
        disagreement = any(item.get("generation_id") == annotation["generation_id"] and item.get("quality_label_current") not in (None, label)
                           for item in history) and label is not None
        history.append(annotation)
        result.loc[match, "annotation_history_json"] = json.dumps(history)
        result.loc[match, "quality_label_current"] = None if disagreement else label
        result.loc[match, "label_generation_id"] = annotation["generation_id"]
        result.loc[match, "label_current_verified"] = label is not None and not disagreement
        result.loc[match, "label_status"] = "disputed" if disagreement else "manual_current_generation" if label is not None else "unassessable"
        result.loc[match, "region_annotations_json"] = json.dumps(annotation.get("regions", []))
        result.loc[match, "manual_contours_json"] = json.dumps(annotation.get("manual_contours", {}))
        # A material assertion is never imported as a target or established fact.
        accepted += 1
    return result, {"accepted": accepted, "errors": errors, "material_fields_imported": False}


def repeat_agreement(first: list[Path], second: list[Path]):
    a = {json.loads(path.read_text())["sample_id"]: json.loads(path.read_text()) for path in first}
    b = {json.loads(path.read_text())["sample_id"]: json.loads(path.read_text()) for path in second}
    pairs = [(a[key], b[key]) for key in sorted(set(a) & set(b)) if b[key].get("blind_to_prior")]
    labels = [(one.get("quality_label_current"), two.get("quality_label_current")) for one, two in pairs]
    labels = [(one, two) for one, two in labels if one is not None and two is not None]
    if len(labels) < 3:
        return {"status": "insufficient_data", "paired_blind_labels": len(labels)}
    left, right = zip(*labels, strict=True)
    quality_kappa = float(cohen_kappa_score(left, right)) if len(set(left) | set(right)) > 1 else None
    severity = {"none": 0, "mild": 1, "moderate": 2, "severe": 3}
    severity_pairs = []
    for one, two in pairs:
        one_regions = {row["region"]: row.get("severity") for row in one.get("regions", [])}
        two_regions = {row["region"]: row.get("severity") for row in two.get("regions", [])}
        for name in set(one_regions) & set(two_regions):
            if one_regions[name] in severity and two_regions[name] in severity:
                severity_pairs.append((severity[one_regions[name]], severity[two_regions[name]]))
    weighted = None
    if len(severity_pairs) >= 3:
        x, y = zip(*severity_pairs, strict=True)
        weighted = float(cohen_kappa_score(x, y, weights="quadratic"))
    return {"status": "measured_repeat_agreement", "paired_blind_labels": len(labels), "quality_kappa": quality_kappa,
            "severity_weighted_kappa": weighted, "agreement_fraction": float(np.mean(np.array(left) == np.array(right))),
            "interpretation": "Repeat agreement, not ground truth or an independent anatomical/material validation."}
