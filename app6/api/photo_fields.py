"""Проекция уже извлечённых полей Stage 1 (info.json) в строку таймлайна.

Ничего не пересчитывает. Stage 1 уже записал позу, качество, кожу, UV,
выражение и provenance. Прежние адаптеры оставляли эти величины как None и
подсовывали в UI каталог Stage-2 полей (boneScore, p0, z-оценки), которых
в кадре нет — меню метрик выглядело как набор пустых дорожек.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def load_info(stage1_root: Path | None, photo_id: str | None) -> dict[str, Any] | None:
    if stage1_root is None or not photo_id:
        return None
    path = stage1_root / photo_id / "info.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def fields_from_info(info: dict[str, Any] | None) -> dict[str, Any]:
    """Вернуть только измеренные поля. Отсутствие остаётся None, не 0."""
    if not info:
        return {}
    pose = info.get("pose") if isinstance(info.get("pose"), dict) else {}
    chronology = info.get("chronology") if isinstance(info.get("chronology"), dict) else {}
    quality_inputs = info.get("quality_inputs") if isinstance(info.get("quality_inputs"), dict) else {}
    uv = info.get("uv") if isinstance(info.get("uv"), dict) else {}
    provenance = info.get("date_provenance") if isinstance(info.get("date_provenance"), dict) else {}
    texture_quality = None
    texture_path = None
    files = info.get("files") if isinstance(info.get("files"), dict) else {}
    if files.get("texture"):
        texture_path = files.get("texture")

    skin_quality = _num(info.get("skin_quality_score"))
    skin_auth = _num(info.get("skin_authenticity_score"))
    visible = _num(quality_inputs.get("combined_visible_fraction"))

    return {
        "yaw": _num(pose.get("yaw")),
        "pitch": _num(pose.get("pitch")),
        "roll": _num(pose.get("roll")),
        "canonicalYaw": _num(pose.get("canonical_yaw") or chronology.get("canonical_yaw")),
        "poseConfidence": _num(pose.get("pose_confidence") or chronology.get("pose_confidence")),
        "detectionConfidence": _num(chronology.get("detection_confidence")),
        "alignmentQuality": _num(chronology.get("alignment_quality")),
        "expressionMagnitude": _num(chronology.get("expression_magnitude")),
        "jawOpenDegree": _num(chronology.get("jaw_open_degree")),
        "jawOpenRatio": _num(chronology.get("jaw_open_ratio")),
        "jawOpenDetected": _bool(chronology.get("jaw_open_detected")),
        "smileDetected": _bool(chronology.get("smile_detected")),
        "visibleLdm106": _num(chronology.get("visible_landmarks_106")),
        "visibleLdm134": _num(chronology.get("visible_landmarks_134")),
        "faceAreaRatio": _num(chronology.get("face_area_ratio") or quality_inputs.get("face_bbox_area_ratio")),
        "correctionMagnitude": _num(chronology.get("correction_magnitude_deg")),
        "residualYaw": _num(chronology.get("residual_yaw_deg")),
        "residualPitch": _num(chronology.get("residual_pitch_deg")),
        "residualRoll": _num(chronology.get("residual_roll_deg")),
        "quality": visible,
        "qualityBasis": "combined_visible_fraction" if visible is not None else None,
        "confidence": _num(chronology.get("detection_confidence") or pose.get("pose_confidence")),
        "skinQuality": skin_quality,
        "skinAuthenticity": skin_auth,
        "uvCoverage": _num(uv.get("observed_coverage") or quality_inputs.get("uv_observed_coverage")),
        "laplacianVariance": _num(quality_inputs.get("laplacian_variance")),
        "tenengradMean": _num(quality_inputs.get("tenengrad_mean")),
        "noiseResidual": _num(quality_inputs.get("noise_residual_mean")),
        "skinMaskCoverage": _num(quality_inputs.get("skin_mask_coverage")),
        "dateProvenanceStatus": provenance.get("status") or None,
        "exifAnomaly": provenance.get("status") == "conflict",
        "textureFile": texture_path,
    }


def merge_photo_fields(row: dict[str, Any], stage1_root: Path | None, photo_id: str | None) -> dict[str, Any]:
    extra = fields_from_info(load_info(stage1_root, photo_id))
    for key, value in extra.items():
        current = row.get(key)
        if current is None and value is not None:
            row[key] = value
    return row


def scan_stage1_records(stage1_root: Path) -> list[dict[str, Any]]:
    """Если main_timeline.csv нет — собрать инвентарь из папок info.json."""
    rows: list[dict[str, Any]] = []
    for info_path in sorted(stage1_root.glob("*/info.json")):
        info = load_info(stage1_root, info_path.parent.name)
        if not info:
            continue
        pose = info.get("pose") if isinstance(info.get("pose"), dict) else {}
        chronology = info.get("chronology") if isinstance(info.get("chronology"), dict) else {}
        rows.append(
            {
                "photo_id": info.get("photo_id") or info_path.parent.name,
                "date": info.get("date"),
                "pose_bin": pose.get("pose_bin") or chronology.get("pose_bin") or "unknown",
                "yaw": pose.get("yaw"),
                "pitch": pose.get("pitch"),
                "roll": pose.get("roll"),
                "combined_visible_fraction": (info.get("quality_inputs") or {}).get("combined_visible_fraction")
                if isinstance(info.get("quality_inputs"), dict)
                else None,
                "date_provenance_status": (info.get("date_provenance") or {}).get("status")
                if isinstance(info.get("date_provenance"), dict)
                else None,
            }
        )
    return rows
