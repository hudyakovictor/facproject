#!/usr/bin/env python3
"""Prepare lightweight UI artifacts from Stage 1/2/3 outputs."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

STORAGE = Path("/Volumes/SDCARD/storage")
UI_ARTIFACTS = STORAGE / "ui_artifacts"
UI_ARTIFACTS.mkdir(exist_ok=True)


def prepare_timeline_matrix() -> None:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with open(STORAGE / "stage1" / "main_timeline.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            year = row["date"][:4]
            matrix[year][row["pose_bin"]] += 1
    with open(UI_ARTIFACTS / "timeline_matrix.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=2)


def prepare_zone_summary() -> None:
    # Use zone_metrics.csv instead of removed pair_details.json
    rows = []
    with open(STORAGE / "stage2" / "zone_metrics.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "pair_id": row.get("pair_id", ""),
                "photo_a": row.get("photo_a", ""),
                "photo_b": row.get("photo_b", ""),
                "pose_bin": row.get("pose_bin", ""),
                "zone_count": 1,
                "avg_rmse": float(row["rmse"]) if row.get("rmse") else None,
                "avg_median": float(row["median"]) if row.get("median") else None,
                "max_rmse": float(row["rmse"]) if row.get("rmse") else None,
                "min_rmse": float(row["rmse"]) if row.get("rmse") else None,
                "status": row.get("status", ""),
                "primary_robust_z": float(row["robust_z"]) if row.get("robust_z") else None,
            })
    if rows:
        with open(UI_ARTIFACTS / "zone_summary.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


def prepare_report_meta() -> None:
    with open(STORAGE / "stage2" / "analysis_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    meta = {
        "schema_version": manifest.get("schema_version", ""),
        "status": manifest.get("status", ""),
        "photo_count": manifest.get("main_record_count", 0),
        "pair_count": manifest.get("pair_count", 0),
        "change_point_count": manifest.get("change_point_count", 0),
        "manual_review_count": manifest.get("postprocess_summary", {}).get("manual_review_count", 0),
        "public_safety_status": manifest.get("postprocess_summary", {}).get("public_safety_status", ""),
        "pose_bins": manifest.get("pose_bins", {}),
        "elapsed_seconds": manifest.get("elapsed_seconds", 0),
        "created_at_utc": manifest.get("created_at_utc", ""),
        "limitations": manifest.get("limitations", []),
        "sections": [
            {"name": "summary", "label": "Сводка", "size": "small"},
            {"name": "narrative", "label": "Narrative", "size": "medium"},
            {"name": "timelines", "label": "Timelines", "size": "medium"},
            {"name": "change_points", "label": "Change Points", "size": "small"},
            {"name": "zones", "label": "Zones", "size": "large"},
            {"name": "motion_maps", "label": "Motion Maps", "size": "medium"},
        ],
    }
    with open(UI_ARTIFACTS / "report_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def prepare_report_sections() -> None:
    sections_dir = UI_ARTIFACTS / "report_sections"
    sections_dir.mkdir(exist_ok=True)
    with open(STORAGE / "stage3" / "report_data.json", encoding="utf-8") as f:
        data = json.load(f)
    for name in ("summary", "narrative", "timelines", "change_points", "zones", "motion_maps"):
        with open(sections_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(data.get(name, {}), f, ensure_ascii=False, indent=2)


def prepare_pair_metrics_preview() -> None:
    rows = []
    with open(STORAGE / "stage2" / "pair_metrics.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 500:
                break
            rows.append({
                "pair_id": row.get("pair_id", ""),
                "photo_a": row.get("photo_a", ""),
                "photo_b": row.get("photo_b", ""),
                "pose_bin": row.get("pose_bin", ""),
                "status": row.get("status", ""),
                "mesh_rmse": row.get("mesh_rmse", ""),
                "texture_score_0_1": row.get("texture_score_0_1", ""),
                "primary_robust_z": row.get("primary_robust_z", ""),
                "quality_limited": row.get("quality_limited", ""),
                "calibration_limited": row.get("calibration_limited", ""),
            })
    if rows:
        with open(UI_ARTIFACTS / "pair_metrics_preview.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


def main() -> int:
    prepare_timeline_matrix()
    prepare_zone_summary()
    prepare_report_meta()
    prepare_report_sections()
    prepare_pair_metrics_preview()
    print("UI artifacts prepared in", UI_ARTIFACTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
