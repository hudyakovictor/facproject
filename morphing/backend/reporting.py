"""Deterministic forensic-style report construction for morphing analyses."""
from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from morphing.backend.analysis import forensic_metrics, similarity_metrics, symmetry_metrics, temporal_drift_metrics
from morphing.backend.quality import QualityReport
from morphing.backend.regions import region_registry, rank_regions

REPORT_SCHEMA = "facproject-morphing-report-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def report_id(kind: str, payload: Mapping[str, Any]) -> str:
    return f"{kind}-{digest_payload(payload)[:16]}"


def _round(value: Any, digits: int = 8) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {key: _round(item, digits) for key, item in value.items()}
    if isinstance(value, list):
        return [_round(item, digits) for item in value]
    return value


def _finding_summary(quality: Mapping[str, Any] | None) -> dict[str, Any]:
    if not quality:
        return {"status": "not_run", "count": 0, "critical": 0, "errors": 0, "warnings": 0}
    findings = quality.get("findings", [])
    return {
        "status": quality.get("status", "unknown"),
        "count": len(findings),
        "critical": sum(item.get("severity") == "critical" for item in findings),
        "errors": sum(item.get("severity") == "error" for item in findings),
        "warnings": sum(item.get("severity") == "warning" for item in findings),
    }


def build_pair_report(
    vertices_a: np.ndarray,
    vertices_b: np.ndarray,
    *,
    labels: tuple[str, str] = ("A", "B"),
    quality_a: QualityReport | Mapping[str, Any] | None = None,
    quality_b: QualityReport | Mapping[str, Any] | None = None,
    mesh_quality_a: QualityReport | Mapping[str, Any] | None = None,
    mesh_quality_b: QualityReport | Mapping[str, Any] | None = None,
    symmetry_a: Mapping[str, Any] | None = None,
    symmetry_b: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    a = np.asarray(vertices_a, dtype=np.float32)
    b = np.asarray(vertices_b, dtype=np.float32)
    similarity = similarity_metrics(a, b)
    forensic = forensic_metrics(a, b)
    quality_payload_a = quality_a.to_dict() if isinstance(quality_a, QualityReport) else quality_a
    quality_payload_b = quality_b.to_dict() if isinstance(quality_b, QualityReport) else quality_b
    mesh_quality_payload_a = mesh_quality_a.to_dict() if isinstance(mesh_quality_a, QualityReport) else mesh_quality_a
    mesh_quality_payload_b = mesh_quality_b.to_dict() if isinstance(mesh_quality_b, QualityReport) else mesh_quality_b
    if symmetry_a is None:
        symmetry_a = symmetry_metrics(a)
    if symmetry_b is None:
        symmetry_b = symmetry_metrics(b)
    payload: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "kind": "pair",
        "created_at": utc_now(),
        "labels": list(labels),
        "vertex_count": int(len(a)),
        "similarity": similarity,
        "forensic": forensic,
        "quality": {
            "a": quality_payload_a,
            "b": quality_payload_b,
            "mesh_a": mesh_quality_payload_a,
            "mesh_b": mesh_quality_payload_b,
            "summary": {
                "photo_a": _finding_summary(quality_payload_a),
                "photo_b": _finding_summary(quality_payload_b),
                "mesh_a": _finding_summary(mesh_quality_payload_a),
                "mesh_b": _finding_summary(mesh_quality_payload_b),
            },
        },
        "symmetry": {"a": symmetry_a, "b": symmetry_b},
        "regions": region_registry(len(a)),
        "provenance": dict(provenance or {}),
        "limitations": [
            "Scores are geometric similarity indicators, not calibrated identity probabilities.",
            "Texture and mesh reconstruction quality can dominate the observed difference.",
            "A forensic conclusion requires a validated reference population and operating threshold.",
        ],
    }
    payload["report_id"] = report_id("pair", {key: value for key, value in payload.items() if key != "created_at"})
    return _round(payload)


def build_timeline_report(
    vertices: list[np.ndarray],
    years: list[float] | None = None,
    *,
    labels: list[str] | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not 2 <= len(vertices) <= 4:
        raise ValueError("timeline reports require 2–4 meshes")
    arrays = [np.asarray(item, dtype=np.float32) for item in vertices]
    resolved_labels = labels or [f"Face {chr(65 + index)}" for index in range(len(arrays))]
    if len(resolved_labels) != len(arrays):
        raise ValueError("labels must match the keyframe count")
    adjacent = [similarity_metrics(arrays[index], arrays[index + 1]) for index in range(len(arrays) - 1)]
    timeline: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "kind": "timeline",
        "created_at": utc_now(),
        "labels": resolved_labels,
        "keyframe_count": len(arrays),
        "adjacent_similarity": adjacent,
        "first_last_similarity": similarity_metrics(arrays[0], arrays[-1]),
        "face_space": _safe_face_space(arrays),
        "provenance": dict(provenance or {}),
        "limitations": ["Temporal trend is descriptive and does not separate age, pose, expression or surgery without calibration."],
    }
    if years is not None:
        if len(years) != len(arrays):
            raise ValueError("years must match the keyframe count")
        normalized_years = [float(value) for value in years]
        if not np.isfinite(normalized_years).all() or np.any(np.diff(normalized_years) <= 0):
            raise ValueError("years must be finite and strictly increasing")
        timeline["years"] = normalized_years
        if len(years) >= 3:
            timeline["temporal_drift"] = temporal_drift_metrics(list(years), arrays)
    timeline["report_id"] = report_id("timeline", {key: value for key, value in timeline.items() if key != "created_at"})
    return _round(timeline)


def _safe_face_space(vertices: list[np.ndarray]) -> dict[str, Any]:
    from morphing.backend.analysis import pca_projection

    return pca_projection(vertices)


def render_report_html(report: Mapping[str, Any], title: str = "Morphing analysis report") -> str:
    payload = html.escape(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    escaped_title = html.escape(title)
    report_id_value = html.escape(str(report.get("report_id", "unknown")))
    kind = html.escape(str(report.get("kind", "analysis")))
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{escaped_title}</title>
<style>
:root {{ color-scheme: dark; font-family: Inter,system-ui,sans-serif; background:#0b0c10; color:#e6edf3; }}
body {{ max-width:1100px; margin:0 auto; padding:32px; }}
header {{ border-bottom:1px solid #30363d; padding-bottom:18px; margin-bottom:22px; }}
.card {{ background:#161b22; border:1px solid #30363d; border-radius:10px; padding:18px; margin:14px 0; }}
pre {{ white-space:pre-wrap; overflow:auto; background:#0d1117; border-radius:8px; padding:16px; color:#c9d1d9; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:99px; background:#21262d; color:#79c0ff; font-size:12px; }}
small {{ color:#8b949e; }}
</style></head><body>
<header><h1>{escaped_title}</h1><span class=\"badge\">{kind}</span> <small>Report ID: {report_id_value}</small></header>
<div class=\"card\"><h2>Interpretation</h2><p>This report contains reproducible geometric diagnostics. It is not a calibrated identity decision or medical conclusion.</p></div>
<div class=\"card\"><h2>Machine-readable payload</h2><pre>{payload}</pre></div>
</body></html>"""


def write_report(report: Mapping[str, Any], path: str | Path, format: str = "json") -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if format.lower() == "html":
        content = render_report_html(report)
    elif format.lower() == "json":
        content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    else:
        raise ValueError("format must be json or html")
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise
    return destination


def report_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    similarity = report.get("similarity") or report.get("first_last_similarity") or {}
    return {
        "report_id": report.get("report_id"),
        "kind": report.get("kind"),
        "vertex_count": report.get("vertex_count"),
        "morphability_score": similarity.get("morphability_score"),
        "cosine_similarity": similarity.get("cosine_similarity"),
        "top_zones": rank_regions(similarity.get("zones", {}))[:5] if similarity.get("zones") else [],
        "limitations_count": len(report.get("limitations", [])),
    }
