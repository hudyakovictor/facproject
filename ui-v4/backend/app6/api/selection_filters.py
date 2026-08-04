"""Interactive Stage-1 selection filters (quality + pose outliers).

Filters never mutate Stage 1 evidence. They produce a deterministic selection
manifest describing included/excluded photos and exclusion reasons.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .calibration import POSE_BINS
from .runtime_config import RuntimePaths, ensure_runtime_write_dirs, load_runtime_paths

SELECTION_SCHEMA = "deeputin-selection-manifest-v1.0"
FILTER_EVAL_SCHEMA = "deeputin-filter-eval-v1.0"

# Numeric filter keys exposed to the UI. Values come from enriched timeline rows.
QUALITY_FILTER_KEYS: tuple[str, ...] = (
    "visibility",           # combined_visible_fraction
    "confidence",           # pose_confidence / detection confidence proxy
    "faceResolution",       # face_bbox_area_ratio or face width proxy
    "blur",                 # laplacian_variance (higher = sharper)
    "exposure",             # skin_mask_coverage used as exposure/skin proxy when EXIF exposure absent
    "occlusion",            # 1 - visibility
    "reconstructionResidual",  # reprojection_p95 / residual magnitude
    "alignmentQuality",
    "landmarkVisibility",   # visible landmarks ratio 106
    "textureApplicability", # uv_observed_coverage
    "expressionMagnitude",
    "jawOpenRatio",
    "smileScore",           # corner_lift_ioc
)

BOOLEAN_FILTER_KEYS: tuple[str, ...] = (
    "smileDetected",
    "jawOpenDetected",
    "dateConflict",
    "nearDuplicate",
    "missingSourceChain",
)

DEFAULT_FILTER_STATE: dict[str, Any] = {
    "schema": "deeputin-filter-state-v1.0",
    "enabled": {key: False for key in QUALITY_FILTER_KEYS},
    "ranges": {key: {"min": None, "max": None} for key in QUALITY_FILTER_KEYS},
    "booleans": {
        "excludeSmileDetected": False,
        "excludeJawOpenDetected": False,
        "excludeDateConflict": True,
        "excludeNearDuplicate": False,
        "excludeMissingSourceChain": False,
    },
    "poseOutlier": {
        "enabled": False,
        "method": "mad",  # mad | percentile
        "masterPercentile": 100.0,  # keep innermost N% by robust distance
        "yawLimit": None,
        "pitchLimit": None,
        "rollLimit": None,
        "madMultiplier": 3.5,
    },
    "manualExclude": [],
    "manualInclude": [],
}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or math.isinf(number):
        return None
    return number


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _get(photo: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in photo and photo[key] is not None:
            return photo[key]
    return None


def metric_value(photo: dict[str, Any], key: str) -> float | None:
    """Resolve a filter metric from an enriched timeline photo row."""
    if key == "visibility":
        return _finite(_get(photo, "visibility", "combined_visible_fraction", "quality"))
    if key == "confidence":
        return _finite(_get(photo, "confidence", "pose_confidence", "detection_confidence"))
    if key == "faceResolution":
        return _finite(_get(photo, "faceResolution", "face_bbox_area_ratio", "face_area_ratio"))
    if key == "blur":
        return _finite(_get(photo, "blur", "laplacian_variance"))
    if key == "exposure":
        return _finite(_get(photo, "exposure", "skin_mask_coverage"))
    if key == "occlusion":
        visibility = metric_value(photo, "visibility")
        if visibility is None:
            return _finite(_get(photo, "occlusion"))
        return float(max(0.0, min(1.0, 1.0 - visibility)))
    if key == "reconstructionResidual":
        return _finite(
            _get(
                photo,
                "reconstructionResidual",
                "reprojection_p95",
                "residual_yaw_deg",
            )
        )
    if key == "alignmentQuality":
        return _finite(_get(photo, "alignmentQuality", "alignment_quality"))
    if key == "landmarkVisibility":
        return _finite(
            _get(
                photo,
                "landmarkVisibility",
                "visible_landmarks_106_ratio",
                "landmark_visibility_106",
            )
        )
    if key == "textureApplicability":
        return _finite(_get(photo, "textureApplicability", "uv_observed_coverage"))
    if key == "expressionMagnitude":
        return _finite(_get(photo, "expressionMagnitude", "expression_magnitude"))
    if key == "jawOpenRatio":
        return _finite(_get(photo, "jawOpenRatio", "jaw_open_ratio", "jawOpenDegree"))
    if key == "smileScore":
        return _finite(_get(photo, "smileScore", "corner_lift_ioc"))
    return _finite(photo.get(key))


def build_histograms(photos: list[dict[str, Any]], bins: int = 20) -> dict[str, Any]:
    histograms: dict[str, Any] = {}
    for key in QUALITY_FILTER_KEYS:
        values = [value for photo in photos if (value := metric_value(photo, key)) is not None]
        if not values:
            histograms[key] = {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
                "bins": [],
                "counts": [],
            }
            continue
        lo, hi = min(values), max(values)
        if lo == hi:
            hi = lo + 1e-9
        width = (hi - lo) / bins
        counts = [0] * bins
        for value in values:
            index = min(bins - 1, int((value - lo) / width))
            counts[index] += 1
        edges = [lo + width * i for i in range(bins + 1)]
        histograms[key] = {
            "count": len(values),
            "min": lo,
            "max": max(values),
            "mean": statistics.fmean(values),
            "bins": edges,
            "counts": counts,
        }
    return histograms


def _median(values: list[float]) -> float:
    return float(statistics.median(values))


def _mad(values: list[float], center: float) -> float:
    deviations = [abs(value - center) for value in values]
    return float(statistics.median(deviations)) if deviations else 0.0


def compute_pose_outlier_stats(photos: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-bin robust pose statistics for outlier sliders."""
    by_bin: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for photo in photos:
        pose = str(photo.get("bucket") or photo.get("pose_bin") or "unknown")
        yaw = _finite(_get(photo, "yaw"))
        pitch = _finite(_get(photo, "pitch"))
        roll = _finite(_get(photo, "roll"))
        if yaw is None or pitch is None or roll is None:
            continue
        by_bin[pose].append(
            {
                "id": photo.get("id"),
                "yaw": yaw,
                "pitch": pitch,
                "roll": roll,
            }
        )

    bins: dict[str, Any] = {}
    for pose in POSE_BINS:
        rows = by_bin.get(pose, [])
        if len(rows) < 3:
            bins[pose] = {
                "count": len(rows),
                "median": None,
                "mad": None,
                "distances": [],
                "status": "insufficient",
            }
            continue
        yaw_vals = [row["yaw"] for row in rows]
        pitch_vals = [row["pitch"] for row in rows]
        roll_vals = [row["roll"] for row in rows]
        med = {
            "yaw": _median(yaw_vals),
            "pitch": _median(pitch_vals),
            "roll": _median(roll_vals),
        }
        mad = {
            "yaw": max(_mad(yaw_vals, med["yaw"]), 1e-6),
            "pitch": max(_mad(pitch_vals, med["pitch"]), 1e-6),
            "roll": max(_mad(roll_vals, med["roll"]), 1e-6),
        }
        distances = []
        for row in rows:
            distance = math.sqrt(
                ((row["yaw"] - med["yaw"]) / mad["yaw"]) ** 2
                + ((row["pitch"] - med["pitch"]) / mad["pitch"]) ** 2
                + ((row["roll"] - med["roll"]) / mad["roll"]) ** 2
            )
            distances.append({"id": row["id"], "distance": distance, **row})
        distances.sort(key=lambda item: item["distance"])
        bins[pose] = {
            "count": len(rows),
            "median": med,
            "mad": mad,
            "distances": distances,
            "distance_min": distances[0]["distance"],
            "distance_max": distances[-1]["distance"],
            "distance_p50": _median([item["distance"] for item in distances]),
            "distance_p90": _percentile([item["distance"] for item in distances], 90),
            "distance_p95": _percentile([item["distance"] for item in distances], 95),
            "status": "ok",
        }
    return {"schema": "deeputin-pose-outlier-stats-v1.0", "bins": bins, "not_a_verdict": True}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (percentile / 100.0) * (len(ordered) - 1)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _merge_filter_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    state = json.loads(json.dumps(DEFAULT_FILTER_STATE))
    if not isinstance(raw, dict):
        return state
    enabled = raw.get("enabled")
    if isinstance(enabled, dict):
        for key in QUALITY_FILTER_KEYS:
            if key in enabled:
                state["enabled"][key] = bool(enabled[key])
    ranges = raw.get("ranges")
    if isinstance(ranges, dict):
        for key in QUALITY_FILTER_KEYS:
            item = ranges.get(key)
            if isinstance(item, dict):
                state["ranges"][key] = {
                    "min": _finite(item.get("min")),
                    "max": _finite(item.get("max")),
                }
    booleans = raw.get("booleans")
    if isinstance(booleans, dict):
        for key in state["booleans"]:
            if key in booleans:
                state["booleans"][key] = bool(booleans[key])
    pose = raw.get("poseOutlier")
    if isinstance(pose, dict):
        state["poseOutlier"].update(
            {
                "enabled": bool(pose.get("enabled", False)),
                "method": str(pose.get("method") or "mad"),
                "masterPercentile": _finite(pose.get("masterPercentile")) or 100.0,
                "yawLimit": _finite(pose.get("yawLimit")),
                "pitchLimit": _finite(pose.get("pitchLimit")),
                "rollLimit": _finite(pose.get("rollLimit")),
                "madMultiplier": _finite(pose.get("madMultiplier")) or 3.5,
            }
        )
    for field in ("manualExclude", "manualInclude"):
        values = raw.get(field)
        if isinstance(values, list):
            state[field] = [str(item) for item in values if str(item).strip()]
    return state


def evaluate_selection(photos: list[dict[str, Any]], filter_state: dict[str, Any] | None) -> dict[str, Any]:
    """Apply filters and return inclusion map + reasons (deterministic)."""
    state = _merge_filter_state(filter_state)
    pose_stats = compute_pose_outlier_stats(photos)
    distance_by_id: dict[str, float] = {}
    for pose, payload in pose_stats["bins"].items():
        for item in payload.get("distances") or []:
            if item.get("id"):
                distance_by_id[str(item["id"])] = float(item["distance"])

    manual_exclude = set(state["manualExclude"])
    manual_include = set(state["manualInclude"])
    decisions: list[dict[str, Any]] = []
    included_ids: list[str] = []
    excluded_ids: list[str] = []

    # Pre-compute pose percentile cutoffs per bin for master percentile slider.
    pose_cutoffs: dict[str, float] = {}
    master = float(state["poseOutlier"]["masterPercentile"])
    master = max(1.0, min(100.0, master))
    for pose, payload in pose_stats["bins"].items():
        distances = [float(item["distance"]) for item in payload.get("distances") or []]
        if distances:
            pose_cutoffs[pose] = _percentile(distances, master) or max(distances)

    for photo in sorted(photos, key=lambda item: (str(item.get("id") or ""))):
        photo_id = str(photo.get("id") or "")
        reasons: list[str] = []
        if not photo_id:
            continue

        if photo_id in manual_exclude and photo_id not in manual_include:
            reasons.append("manual_exclude")

        # Quality range filters
        for key in QUALITY_FILTER_KEYS:
            if not state["enabled"].get(key):
                continue
            value = metric_value(photo, key)
            bounds = state["ranges"].get(key) or {}
            lo, hi = bounds.get("min"), bounds.get("max")
            if value is None:
                reasons.append(f"{key}:missing")
                continue
            if lo is not None and value < lo:
                reasons.append(f"{key}:below_min")
            if hi is not None and value > hi:
                reasons.append(f"{key}:above_max")

        booleans = state["booleans"]
        smile = _boolish(_get(photo, "smileDetected", "smile_detected"))
        jaw = _boolish(_get(photo, "jawOpenDetected", "jaw_open_detected"))
        date_conflict = bool(
            _get(photo, "exifAnomaly")
            or str(_get(photo, "dateProvenanceStatus", "date_provenance_status") or "").lower()
            in {"conflict", "date_conflict", "exif_conflict"}
        )
        near_dup = bool(str(_get(photo, "nearDuplicateOf", "near_duplicate_of") or "").strip())
        missing_source = str(_get(photo, "sourceProvenanceStatus", "source_provenance_status") or "").lower() in {
            "missing",
            "not_provided",
            "unavailable",
            "",
        }

        if booleans.get("excludeSmileDetected") and smile is True:
            reasons.append("smile_detected")
        if booleans.get("excludeJawOpenDetected") and jaw is True:
            reasons.append("jaw_open_detected")
        if booleans.get("excludeDateConflict") and date_conflict:
            reasons.append("date_provenance_conflict")
        if booleans.get("excludeNearDuplicate") and near_dup:
            reasons.append("near_duplicate")
        if booleans.get("excludeMissingSourceChain") and missing_source:
            reasons.append("missing_source_chain")

        # Pose outlier filters
        pose_cfg = state["poseOutlier"]
        if pose_cfg.get("enabled"):
            pose = str(photo.get("bucket") or photo.get("pose_bin") or "unknown")
            yaw = _finite(_get(photo, "yaw"))
            pitch = _finite(_get(photo, "pitch"))
            roll = _finite(_get(photo, "roll"))
            stats = pose_stats["bins"].get(pose) or {}
            med = stats.get("median") or {}
            if yaw is not None and pose_cfg.get("yawLimit") is not None and med.get("yaw") is not None:
                if abs(yaw - float(med["yaw"])) > float(pose_cfg["yawLimit"]):
                    reasons.append("pose_yaw_outlier")
            if pitch is not None and pose_cfg.get("pitchLimit") is not None and med.get("pitch") is not None:
                if abs(pitch - float(med["pitch"])) > float(pose_cfg["pitchLimit"]):
                    reasons.append("pose_pitch_outlier")
            if roll is not None and pose_cfg.get("rollLimit") is not None and med.get("roll") is not None:
                if abs(roll - float(med["roll"])) > float(pose_cfg["rollLimit"]):
                    reasons.append("pose_roll_outlier")

            distance = distance_by_id.get(photo_id)
            if distance is not None:
                if pose_cfg.get("method") == "mad" and stats.get("status") == "ok":
                    # robust multi-axis distance already MAD-normalized; threshold via multiplier
                    limit = float(pose_cfg.get("madMultiplier") or 3.5) * math.sqrt(3.0)
                    if distance > limit:
                        reasons.append("pose_mad_outlier")
                cutoff = pose_cutoffs.get(pose)
                if cutoff is not None and master < 100.0 and distance > cutoff + 1e-12:
                    reasons.append("pose_percentile_outlier")

        if photo_id in manual_include:
            reasons = [reason for reason in reasons if reason != "manual_exclude"]
            # manual include overrides automatic exclusions
            included = True
            if reasons and "manual_include" not in reasons:
                reasons = []
            status = "manual_include"
        else:
            included = len(reasons) == 0
            status = "included" if included else "excluded"

        decision = {
            "photo_id": photo_id,
            "included": included,
            "status": status if included else "excluded",
            "reasons": reasons,
            "pose_bin": photo.get("bucket") or photo.get("pose_bin"),
            "pose_distance": distance_by_id.get(photo_id),
        }
        decisions.append(decision)
        if included:
            included_ids.append(photo_id)
        else:
            excluded_ids.append(photo_id)

    reason_counts: dict[str, int] = defaultdict(int)
    for decision in decisions:
        for reason in decision["reasons"]:
            reason_counts[reason] += 1

    return {
        "schema": FILTER_EVAL_SCHEMA,
        "not_a_verdict": True,
        "read_only_stage1": True,
        "filter_state": state,
        "total": len(decisions),
        "included_count": len(included_ids),
        "excluded_count": len(excluded_ids),
        "included_ids": included_ids,
        "excluded_ids": excluded_ids,
        "reason_counts": dict(sorted(reason_counts.items())),
        "decisions": decisions,
        "histograms": build_histograms(photos),
        "pose_outlier_stats": pose_stats,
    }


def build_selection_manifest(
    photos: list[dict[str, Any]],
    filter_state: dict[str, Any] | None,
    *,
    label: str = "selection",
    stage1_root: str | None = None,
) -> dict[str, Any]:
    evaluation = evaluate_selection(photos, filter_state)
    return {
        "schema": SELECTION_SCHEMA,
        "not_a_verdict": True,
        "label": label,
        "stage1_root": stage1_root,
        "filter_state": evaluation["filter_state"],
        "included_ids": evaluation["included_ids"],
        "excluded_ids": evaluation["excluded_ids"],
        "included_count": evaluation["included_count"],
        "excluded_count": evaluation["excluded_count"],
        "reason_counts": evaluation["reason_counts"],
        "decisions": evaluation["decisions"],
        "immutable_stage1": True,
    }


def save_selection_manifest(
    manifest: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
    name: str = "selection_manifest.json",
) -> Path:
    current = paths or load_runtime_paths()
    ensure_runtime_write_dirs(current)
    profiles = current.storage_root / "profiles" / "current"
    profiles.mkdir(parents=True, exist_ok=True)
    destination = profiles / name
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination
