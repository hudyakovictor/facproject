"""Безопасная проекция реального Stage 1 в хронологический интерфейс.

Stage 1 измеряет кадр, но не сравнивает его с другими кадрами. Поэтому этот
адаптер намеренно не создаёт identity verdict: он показывает инвентарь и
фактические quality/expression/pose метрики, достаточные для интерактивной
очистки выборки (Iteration 03).
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .ui_fields import ERA_BOUNDS, UI_FIELDS_SCHEMA, era_for, validate_ui_row

STAGE1_TIMELINE_SCHEMA = "deeputin-api-stage1-inventory-v1.1"


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _date_to_ms(value: str | None) -> int | None:
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
    return int(datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc).timestamp() * 1000)


def _deep_get(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _load_info(stage1_root: Path, photo_id: str, source: dict[str, str]) -> dict[str, Any] | None:
    candidates: list[Path] = []
    for field in ("record_dir", "output_dir"):
        raw = str(source.get(field) or "").strip()
        if raw:
            candidates.append(Path(raw) / "info.json")
    candidates.append(stage1_root / photo_id / "info.json")
    for path in candidates:
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                return value
    return None


def _enrich_from_info(row: dict[str, Any], info: dict[str, Any]) -> None:
    quality = info.get("quality_inputs") if isinstance(info.get("quality_inputs"), dict) else {}
    chronology = info.get("chronology") if isinstance(info.get("chronology"), dict) else {}
    uv = info.get("uv") if isinstance(info.get("uv"), dict) else {}

    def take(target: str, *sources: Any) -> None:
        if row.get(target) is not None:
            return
        for value in sources:
            number = _float(value)
            if number is not None:
                row[target] = number
                return
            boolean = _bool(value)
            if boolean is not None and target.endswith(("Detected", "detected")):
                row[target] = boolean
                return
            if value is not None and not isinstance(value, (dict, list)):
                row[target] = value
                return

    take("visibility", quality.get("combined_visible_fraction"), row.get("quality"))
    take("combined_visible_fraction", quality.get("combined_visible_fraction"), row.get("quality"))
    take("skin_mask_coverage", quality.get("skin_mask_coverage"))
    take("exposure", quality.get("skin_mask_coverage"))
    take("uv_observed_coverage", quality.get("uv_observed_coverage"), uv.get("observed_coverage"))
    take("textureApplicability", quality.get("uv_observed_coverage"), uv.get("observed_coverage"))
    take("laplacian_variance", quality.get("laplacian_variance"))
    take("blur", quality.get("laplacian_variance"))
    take("face_bbox_area_ratio", quality.get("face_bbox_area_ratio"), chronology.get("face_area_ratio"))
    take("faceResolution", quality.get("face_bbox_area_ratio"), chronology.get("face_area_ratio"))
    take("face_bbox_width", quality.get("face_bbox_width"))
    take("noise_residual_mean", quality.get("noise_residual_mean"))

    take("alignment_quality", chronology.get("alignment_quality"))
    take("alignmentQuality", chronology.get("alignment_quality"))
    take("expression_magnitude", chronology.get("expression_magnitude"))
    take("expressionMagnitude", chronology.get("expression_magnitude"))
    take("jaw_open_degree", chronology.get("jaw_open_degree"))
    take("jawOpenDegree", chronology.get("jaw_open_degree"))
    take("jaw_open_ratio", chronology.get("jaw_open_ratio"))
    take("jawOpenRatio", chronology.get("jaw_open_ratio"))
    take("corner_lift_ioc", chronology.get("corner_lift_ioc"))
    take("smileScore", chronology.get("corner_lift_ioc"))
    take("pose_confidence", chronology.get("pose_confidence"))
    take("detection_confidence", chronology.get("detection_confidence"))
    take("confidence", chronology.get("pose_confidence"), chronology.get("detection_confidence"))
    take("reprojection_p95", chronology.get("reprojection_p95"))
    take("reprojection_rmse", chronology.get("reprojection_rmse"))
    take("reconstructionResidual", chronology.get("reprojection_p95"), chronology.get("reprojection_rmse"))
    take("residual_yaw_deg", chronology.get("residual_yaw_deg"))
    take("residual_pitch_deg", chronology.get("residual_pitch_deg"))
    take("residual_roll_deg", chronology.get("residual_roll_deg"))
    take("correction_magnitude_deg", chronology.get("correction_magnitude_deg"))

    visible_106 = _float(chronology.get("visible_landmarks_106"))
    if visible_106 is not None:
        row["visible_landmarks_106"] = visible_106
        row["landmarkVisibility"] = visible_106 / 106.0
        row["visible_landmarks_106_ratio"] = visible_106 / 106.0
    visible_134 = _float(chronology.get("visible_landmarks_134"))
    if visible_134 is not None:
        row["visible_landmarks_134"] = visible_134

    smile = _bool(chronology.get("smile_detected"))
    if smile is not None:
        row["smileDetected"] = smile
        row["smile_detected"] = smile
    jaw = _bool(chronology.get("jaw_open_detected"))
    if jaw is not None:
        row["jawOpenDetected"] = jaw
        row["jaw_open_detected"] = jaw

    take("skinQuality", info.get("skin_quality_score"))
    take("authenticityScore", info.get("skin_authenticity_score"))
    if info.get("skin_quality_status") is not None:
        row["qualityStatus"] = info.get("skin_quality_status")
    if info.get("skin_authenticity_status") is not None:
        row["authenticityStatus"] = info.get("skin_authenticity_status")

    provenance = info.get("date_provenance") if isinstance(info.get("date_provenance"), dict) else {}
    if provenance:
        row["dateProvenanceStatus"] = provenance.get("status") or row.get("dateProvenanceStatus")
        row["exifAnomaly"] = provenance.get("status") == "conflict"
    source_prov = info.get("source_provenance") if isinstance(info.get("source_provenance"), dict) else {}
    if source_prov:
        row["sourceProvenanceStatus"] = source_prov.get("status") or "not_provided"
    if info.get("near_duplicate_of"):
        row["nearDuplicateOf"] = info.get("near_duplicate_of")
        row["near_duplicate_of"] = info.get("near_duplicate_of")


def build_stage1_inventory(stage1_root: Path, *, enrich_info: bool = True) -> dict[str, Any]:
    timeline_path = stage1_root / "main_timeline.csv"
    if not timeline_path.is_file():
        raise FileNotFoundError(f"main_timeline.csv отсутствует в {stage1_root}")
    with timeline_path.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    source_rows.sort(key=lambda row: (str(row.get("date") or ""), str(row.get("photo_id") or "")))
    dated = [str(row["date"]) for row in source_rows if row.get("date")]
    first, last = (dated[0], dated[-1]) if dated else ("", "")
    rows: list[dict[str, Any]] = []
    violations: dict[str, int] = {}
    enriched_count = 0
    for source in source_rows:
        date_iso = source.get("date") or None
        photo_id = str(source.get("photo_id") or "")
        visibility = _float(source.get("combined_visible_fraction"))
        row: dict[str, Any] = {
            "id": photo_id,
            "date": date_iso,
            "t": _date_to_ms(date_iso),
            "era": era_for(date_iso),
            "bucket": source.get("pose_bin") or "unknown",
            "quality": visibility,
            "qualityBasis": "combined_visible_fraction",
            "visibility": visibility,
            "combined_visible_fraction": visibility,
            "skin_mask_coverage": _float(source.get("skin_mask_coverage")),
            "exposure": _float(source.get("skin_mask_coverage")),
            "uv_observed_coverage": _float(source.get("uv_observed_coverage")),
            "textureApplicability": _float(source.get("uv_observed_coverage")),
            "boneScore": None,
            "orbit": None,
            "chin": None,
            "jaw": None,
            "cheek": None,
            "symmetry": None,
            "siliconeProb": None,
            "fillerProb": None,
            "skinQuality": None,
            "wrinkleDensity": None,
            "subsurface": None,
            "visualAge": None,
            "calendarAge": None,
            "zOrbitDepth": None,
            "zChinProj": None,
            "zJawWidth": None,
            "zCheek": None,
            "p0": None,
            "p1": None,
            "p2": None,
            "yaw": _float(source.get("yaw")),
            "pitch": _float(source.get("pitch")),
            "roll": _float(source.get("roll")),
            "dominant": "UNAVAILABLE",
            "fuzzy": "INSUFFICIENT_DATA",
            "confidence": None,
            "flags": ["STAGE1_INVENTORY_ONLY"],
            "sourceMode": "research",
            "analysisStage": "stage1_inventory",
            "bayesianProjectionAvailable": False,
            "measurementStatus": "not_compared",
            "dateProvenanceStatus": source.get("date_provenance_status") or "unknown",
            "dateProvenanceLimited": False,
            "exifAnomaly": (source.get("date_provenance_status") == "conflict"),
            "nearDuplicateOf": source.get("near_duplicate_of") or None,
            "near_duplicate_of": source.get("near_duplicate_of") or None,
            "sourceProvenanceStatus": source.get("source_provenance_status") or "not_provided",
            "occlusion": (1.0 - visibility) if visibility is not None else None,
            "smileDetected": None,
            "jawOpenDetected": None,
            "expressionMagnitude": None,
            "jawOpenRatio": None,
            "alignmentQuality": None,
            "landmarkVisibility": None,
            "reconstructionResidual": None,
            "blur": None,
            "faceResolution": None,
        }
        if enrich_info and photo_id:
            info = _load_info(stage1_root, photo_id, source)
            if info is not None:
                _enrich_from_info(row, info)
                enriched_count += 1
        # Keep quality alias aligned with visibility after enrichment.
        if row.get("visibility") is not None:
            row["quality"] = row["visibility"]
        if row.get("confidence") is None and row.get("pose_confidence") is not None:
            row["confidence"] = row["pose_confidence"]
        row["uiContractViolations"] = validate_ui_row(row)
        row["uiFieldsSchema"] = UI_FIELDS_SCHEMA
        for field in row["uiContractViolations"]:
            violations[field] = violations.get(field, 0) + 1
        rows.append(row)
    era_meta = {
        name: {"label": name, "start": f"{lo}-01-01", "end": f"{hi}-12-31"}
        for name, lo, hi in ERA_BOUNDS
        if any(row["era"] == name for row in rows)
    }
    if any(row["era"] == "unknown" for row in rows):
        era_meta["unknown"] = {"label": "Дата вне заданного диапазона", "start": first, "end": last}
    manifest_path = stage1_root / "stage1_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    return {
        "schema": STAGE1_TIMELINE_SCHEMA,
        "source_mode": "research",
        "not_a_verdict": True,
        "analysis_stage": "stage1_inventory",
        "era_meta": era_meta,
        "photos": rows,
        "stage1_manifest": manifest,
        "ui_fields_schema": UI_FIELDS_SCHEMA,
        "ui_fields_complete_photo_count": sum(not row["uiContractViolations"] for row in rows),
        "ui_fields_violations_by_field": violations,
        "enriched_info_count": enriched_count,
        "filter_metrics_available": True,
        "note": (
            "Реальный инвентарь Stage 1 с quality/expression/pose метриками для "
            "интерактивной очистки выборки. Сравнительные identity-метрики появятся после Stage 2."
        ),
    }
