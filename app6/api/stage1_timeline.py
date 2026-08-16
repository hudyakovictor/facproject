"""Безопасная проекция реального Stage 1 в хронологический интерфейс.

Stage 1 измеряет кадр, но не сравнивает его с другими кадрами. Поэтому этот
адаптер намеренно не создаёт score, вероятности или forensic verdict: он
показывает только инвентарь и фактический показатель видимости лица.
"""
from __future__ import annotations

import csv
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .ui_fields import ERA_BOUNDS, UI_FIELDS_SCHEMA, era_for, validate_ui_row

STAGE1_TIMELINE_SCHEMA = "deeputin-api-stage1-inventory-v1.0"


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _date_to_ms(value: str | None) -> int | None:
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
    return int(datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC).timestamp() * 1000)


def build_stage1_inventory(stage1_root: Path) -> dict[str, Any]:
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
    for source in source_rows:
        date_iso = source.get("date") or None
        # This is a measured Stage-1 coverage value, not a composite identity
        # or image-quality score. The explicit basis prevents UI overclaiming.
        row = {
            "id": source.get("photo_id"), "date": date_iso,
            "t": _date_to_ms(date_iso), "era": era_for(date_iso),
            "bucket": source.get("pose_bin") or "unknown",
            "quality": _float(source.get("combined_visible_fraction")),
            "qualityBasis": "combined_visible_fraction",
            "boneScore": None, "orbit": None, "chin": None, "jaw": None,
            "cheek": None, "symmetry": None, "siliconeProb": None,
            "fillerProb": None, "skinQuality": None, "wrinkleDensity": None,
            "subsurface": None, "visualAge": None, "calendarAge": None,
            # z-оценки существуют только относительно общей калиброванной
            # базы Stage 2. Ноль здесь был бы ложным измерением «нет дрейфа».
            "zOrbitDepth": None, "zChinProj": None, "zJawWidth": None,
            "zCheek": None, "p0": None, "p1": None, "p2": None,
            "yaw": _float(source.get("yaw")), "pitch": _float(source.get("pitch")),
            "roll": _float(source.get("roll")), "dominant": "UNAVAILABLE",
            "fuzzy": "INSUFFICIENT_DATA", "confidence": None,
            "flags": ["STAGE1_INVENTORY_ONLY"], "sourceMode": "research",
            "analysisStage": "stage1_inventory", "bayesianProjectionAvailable": False,
            "measurementStatus": "not_compared", "dateProvenanceStatus": source.get("date_provenance_status") or "unknown",
            "dateProvenanceLimited": False, "exifAnomaly": (source.get("date_provenance_status") == "conflict"),
        }
        row["uiContractViolations"] = validate_ui_row(row)
        row["uiFieldsSchema"] = UI_FIELDS_SCHEMA
        for field in row["uiContractViolations"]:
            violations[field] = violations.get(field, 0) + 1
        rows.append(row)
    era_meta = {
        name: {"label": name, "start": f"{lo}-01-01", "end": f"{hi}-12-31"}
        for name, lo, hi in ERA_BOUNDS if any(row["era"] == name for row in rows)
    }
    if any(row["era"] == "unknown" for row in rows):
        era_meta["unknown"] = {"label": "Дата вне заданного диапазона", "start": first, "end": last}
    manifest_path = stage1_root / "stage1_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    return {
        "schema": STAGE1_TIMELINE_SCHEMA, "source_mode": "research", "not_a_verdict": True,
        "analysis_stage": "stage1_inventory", "era_meta": era_meta, "photos": rows,
        "stage1_manifest": manifest, "ui_fields_schema": UI_FIELDS_SCHEMA,
        "ui_fields_complete_photo_count": sum(not row["uiContractViolations"] for row in rows),
        "ui_fields_violations_by_field": violations,
        "note": "Реальный инвентарь Stage 1: сравнительные метрики, вероятности и выводы появятся только после Stage 2 и калибровки.",
    }
