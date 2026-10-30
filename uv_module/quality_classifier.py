"""Explanation-first UV quality models, readiness checks and one-shot closed test."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from scipy.stats import beta
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, confusion_matrix, precision_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .diagnostic_report import write_json


def allowed_features(columns):
    forbidden = {"sample_id", "partition", "generation_id", "capture_date", "session_id", "original_stem", "source_sha256",
                 "source_width", "source_height", "observer_id", "label", "quality_label_current", "target"}
    return [name for name in columns if name not in forbidden and not name.endswith(("_id", "_path"))
            and not any(token in name.lower() for token in ("filename", "person", "material", "label", "date"))]


def choose_threshold(labels, scores, maximum_fpr=0.05):
    labels, scores = np.asarray(labels), np.asarray(scores)
    normal = labels == 0
    if not normal.any() or not (labels == 1).any():
        raise ValueError("both quality classes required in validation")
    candidates = np.unique(np.r_[scores, np.nextafter(scores.max(), np.inf)])
    feasible = []
    for threshold in candidates:
        predicted = scores >= threshold
        false_alarms = int(np.sum(predicted & normal))
        fpr = false_alarms / normal.sum()
        recall = float(np.mean(predicted[labels == 1]))
        if fpr <= maximum_fpr:
            feasible.append((recall, -threshold, threshold, false_alarms))
    _, _, threshold, false_alarms = max(feasible)
    n = int(normal.sum())
    upper = float(beta.ppf(0.95, false_alarms + 1, n - false_alarms)) if false_alarms < n else 1.0
    return float(threshold), {"validation_false_alarms": false_alarms, "validation_normal_count": n,
                              "fpr_upper_one_sided95": upper, "budget": maximum_fpr,
                              "deployment_ready_for_fpr_budget": upper <= maximum_fpr}


def classification_metrics(labels, scores, threshold):
    predicted = scores >= threshold
    return {"precision": float(precision_score(labels, predicted, zero_division=0)),
            "recall": float(recall_score(labels, predicted, zero_division=0)),
            "pr_auc_average_precision": float(average_precision_score(labels, scores)),
            "balanced_accuracy": float(balanced_accuracy_score(labels, predicted)),
            "confusion_matrix": confusion_matrix(labels, predicted, labels=[0, 1]).tolist()}


def training_readiness(manifest, features, generation_id):
    labels = manifest.copy()
    if "label_generation_id" not in labels or "label_current_verified" not in labels:
        return {"ready": False, "reason": "current-generation quality labels are not manually verified"}, None
    eligible = labels.quality_label_current.isin(["normal", "distorted"]) & labels.label_current_verified.fillna(False) \
        & labels.label_generation_id.eq(generation_id)
    labels = labels.loc[eligible]
    if "generation_id" not in features or not features.generation_id.eq(generation_id).all():
        return {"ready": False, "reason": "feature generation configurations are mixed or unverified"}, None
    metadata_columns = ["sample_id", "partition", "split_group", "quality_label_current", "label_current_verified", "label_generation_id"]
    if "contour_manual_validated" in labels:
        metadata_columns.append("contour_manual_validated")
    feature_columns = [name for name in features if name not in ("partition",)]
    table = labels[metadata_columns].merge(features[feature_columns], on="sample_id", validate="one_to_one")
    if table.empty:
        return {"ready": False, "reason": "no verified labels for this pinned generator"}, None
    if table.groupby("split_group").partition.nunique().gt(1).any():
        raise ValueError("duplicate/session leakage in classifier split")
    table["target"] = table.quality_label_current.map({"normal": 0, "distorted": 1}).astype(int)
    for split in ("train", "validation"):
        counts = table.loc[table.partition.eq(split)].groupby("target").split_group.nunique()
        if len(counts) != 2 or counts.min() < 2:
            return {"ready": False, "reason": f"too few independent quality groups in {split}"}, None
    return {"ready": True, "scope": "exploratory quality classification; no calibrated probabilities or material target"}, table


def train_quality(manifest, features, output: Path, generation_id, maximum_fpr=0.05):
    output.mkdir(parents=True, exist_ok=True)
    if (output / "test_evaluation.json").exists():
        raise ValueError("this closed test was consumed; retraining must not use its feedback in the same study")
    readiness, table = training_readiness(manifest, features, generation_id)
    if not readiness["ready"]:
        write_json(output / "model_readiness.json", readiness)
        return readiness
    numeric = [name for name in features.select_dtypes(include=[np.number]).columns if name in allowed_features(features.columns)]
    numeric = [name for name in numeric if table[name].notna().any()]
    if any(name.startswith("contour_") for name in numeric) and ("contour_manual_validated" not in table or table.contour_manual_validated.fillna(False).sum() < 3):
        readiness = {"ready": False, "reason": "independent automatic contours require manual validation before full model training"}
        write_json(output / "model_readiness.json", readiness)
        return readiness
    if not numeric:
        return {"ready": False, "reason": "no allowed numerical quality features"}
    groups = {"controls": [name for name in numeric if name.startswith("pose_") or name in ("face_resolution_px", "source_sharpness")],
              "geometry": [name for name in numeric if "anisotropy" in name or "density" in name or "invalid_surface" in name],
              "contours": [name for name in numeric if name.startswith("contour_")],
              "texture": [name for name in numeric if name.startswith("texture_")]}
    groups["all"] = numeric
    groups["without_controls"] = [name for name in numeric if name not in groups["controls"]]
    quality_flags = [name for name in numeric if "invalid_surface" in name or name in ("observed_fraction", "measurement_suitable_fraction")]
    groups["without_quality_flags"] = [name for name in numeric if name not in quality_flags]
    train = table.partition.eq("train")
    validation = table.partition.eq("validation")
    outcomes, models = {}, {}
    for family, columns in groups.items():
        if not columns:
            continue
        trials = []
        for regularization in (0.1, 1.0, 10.0):
            model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                  LogisticRegression(C=regularization, class_weight="balanced", max_iter=2000, random_state=0))
            model.fit(table.loc[train, columns], table.loc[train, "target"])
            scores = model.predict_proba(table.loc[validation, columns])[:, 1]
            trials.append((average_precision_score(table.loc[validation, "target"], scores), regularization, model, scores))
        _, regularization, model, scores = max(trials, key=lambda item: item[0])
        threshold, fpr = choose_threshold(table.loc[validation, "target"].to_numpy(), scores, maximum_fpr)
        outcomes[family] = {"features": columns, "regularization": regularization, "threshold": threshold,
                            "validation": classification_metrics(table.loc[validation, "target"].to_numpy(), scores, threshold), "false_alarm_control": fpr}
        models[family] = model
    boosting = make_pipeline(SimpleImputer(strategy="median"), HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=7, l2_regularization=1, random_state=0))
    boosting.fit(table.loc[train, numeric], table.loc[train, "target"])
    boost_scores = boosting.predict_proba(table.loc[validation, numeric])[:, 1]
    outcomes["boosting_comparison"] = {"features": numeric, "validation_pr_auc": float(average_precision_score(table.loc[validation, "target"], boost_scores)),
                                        "scope": "validation comparison only; test not used to choose model"}
    full = models["all"]
    model_path = output / "quality_model.joblib"
    joblib.dump(full, model_path)
    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    coefficients = full.steps[-1][1].coef_[0]
    report = {"ready": True, "generation_id": generation_id, "model_sha256": model_sha,
              "features": numeric, "threshold": outcomes["all"]["threshold"], "comparisons": outcomes,
              "coefficients": dict(zip(numeric, coefficients.tolist(), strict=True)),
              "probability_calibrated": False, "score_kind": "uncalibrated_classifier_score",
              "test_used": False, "material_prediction": False}
    write_json(output / "model.json", report)
    return report


def evaluate_closed_test(manifest, features, output: Path):
    report = json.loads((output / "model.json").read_text())
    path = output / "quality_model.joblib"
    if hashlib.sha256(path.read_bytes()).hexdigest() != report["model_sha256"]:
        raise ValueError("model changed after validation threshold freeze")
    consumed = output / "test_evaluation.json"
    if consumed.exists():
        previous = json.loads(consumed.read_text())
        if previous["model_sha256"] != report["model_sha256"]:
            raise ValueError("closed test already consumed; do not use it to tune another model")
        return previous
    readiness, table = training_readiness(manifest, features, report["generation_id"])
    if not readiness["ready"]:
        return readiness
    test = table.loc[table.partition.eq("test")]
    if test.target.nunique() < 2:
        return {"ready": False, "reason": "closed test lacks both verified quality classes"}
    model = joblib.load(path)
    scores = model.predict_proba(test[report["features"]])[:, 1]
    result = {"model_sha256": report["model_sha256"], "generation_id": report["generation_id"],
              "threshold": report["threshold"], "test_groups": int(test.split_group.nunique()),
              "metrics": classification_metrics(test.target.to_numpy(), scores, report["threshold"]), "intervals": {}}
    rng = np.random.default_rng(20261027)
    groups = test.split_group.unique()
    draws = []
    for _ in range(2000):
        selected = rng.choice(groups, size=len(groups), replace=True)
        indices = np.concatenate([np.flatnonzero(test.split_group.to_numpy() == group) for group in selected])
        if np.unique(test.target.to_numpy()[indices]).size < 2:
            continue
        draws.append(classification_metrics(test.target.to_numpy()[indices], scores[indices], report["threshold"]))
    for metric in ("precision", "recall", "pr_auc_average_precision", "balanced_accuracy"):
        result["intervals"][metric] = np.quantile([row[metric] for row in draws], [0.025, 0.975]).tolist() if draws else []
    write_json(consumed, result)
    return result
