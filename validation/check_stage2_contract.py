#!/usr/bin/env python3
"""Validate the real Stage 2 artifact contract with compact output.

This script deliberately does not scan every file as a data artifact. It reads
only canonical Stage 2 outputs and ignores macOS metadata (._* and .DS_Store).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "deeputin-stage2-v1.4-robustness"
CANONICAL_JSON = (
    "analysis_manifest.json",
    "artifact_index.json",
    "change_points.json",
    "analysis_validation.json",
)
OPTIONAL_JSON = (
    "alpha_chronology.json",
    "baseline_return.json",
    "cross_bin_corroboration.json",
    "cumulative_drift.json",
    "gate_report.json",
    "pose_leakage_diagnostic.json",
    "public_safety_report.json",
    "technical_summary.json",
)
CANONICAL_CSV = (
    "pair_metrics.csv",
    "zone_metrics.csv",
    "mesh_pair_metrics.csv",
    "status_summary.csv",
    "event_aggregation.csv",
)
REMOVED_ARTIFACTS = (
    "pair_details.json",
    "evidence_packets.json",
    "evidence_packets.jsonl",
    "mesh_zone_metrics.csv",
)


class Reporter:
    def __init__(self, sample_limit: int) -> None:
        self.errors = 0
        self.warnings = 0
        self.sample_limit = sample_limit
        self.seen: Counter[str] = Counter()

    def emit(self, level: str, code: str, subject: str, detail: str) -> None:
        if level == "ERROR":
            self.errors += 1
        else:
            self.warnings += 1
        key = f"{level}:{code}"
        self.seen[key] += 1
        if self.seen[key] <= self.sample_limit:
            print(f"{level} code={code} subject={subject} detail={detail}")

    def error(self, code: str, subject: str, detail: str) -> None:
        self.emit("ERROR", code, subject, detail)

    def warn(self, code: str, subject: str, detail: str) -> None:
        self.emit("WARN", code, subject, detail)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate the real Stage 2 artifact contract")
    p.add_argument("stage2_root", type=Path)
    p.add_argument("--sample-limit", type=int, default=20)
    p.add_argument("--max-depth", type=int, default=2, help="Depth for informational inventory only")
    return p.parse_args()


def is_ignored(path: Path) -> bool:
    return path.name == ".DS_Store" or path.name.startswith("._")


def safe_json(path: Path, reporter: Reporter) -> Any | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        reporter.error("JSON_PARSE_FAILED", str(path), type(exc).__name__)
        return None


def safe_csv_rows(path: Path, reporter: Reporter) -> tuple[list[str], int, list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            rows = list(reader)
            return fields, len(rows), rows
    except Exception as exc:
        reporter.error("CSV_PARSE_FAILED", str(path), type(exc).__name__)
        return [], 0, []


def schema_of(obj: Any) -> str | None:
    if isinstance(obj, dict):
        for key in ("schema", "schema_version"):
            value = obj.get(key)
            if isinstance(value, str):
                return value
    return None


def validate_manifest(obj: Any, path: Path, reporter: Reporter) -> dict[str, Any]:
    if not isinstance(obj, dict):
        reporter.error("MANIFEST_NOT_OBJECT", str(path), type(obj).__name__)
        return {}
    required = ("status", "pair_count", "pose_bins", "limitations", "schema_version")
    missing = [key for key in required if key not in obj]
    if missing:
        reporter.error("MANIFEST_KEYS_MISSING", str(path), ",".join(missing))
    if obj.get("status") not in ("complete", "completed"):
        reporter.error("MANIFEST_NOT_COMPLETE", str(path), f"status={obj.get('status')!r}")
    if not isinstance(obj.get("pair_count"), int) or obj.get("pair_count", 0) < 1:
        reporter.error("MANIFEST_PAIR_COUNT_INVALID", str(path), repr(obj.get("pair_count")))
    if not isinstance(obj.get("pose_bins"), dict) or not obj.get("pose_bins"):
        reporter.warn("MANIFEST_POSE_BINS_EMPTY", str(path), "pose_bins missing or empty")
    if not isinstance(obj.get("limitations"), list):
        reporter.warn("MANIFEST_LIMITATIONS_INVALID", str(path), "limitations is not a list")
    return obj


def validate_pairs(obj: Any, path: Path, reporter: Reporter) -> tuple[int, set[str], int]:
    if obj is None:
        reporter.warn("PAIR_DETAILS_REMOVED", str(path), "file removed from pipeline output; use pair_metrics.csv instead")
        return 0, set(), 0
    if not isinstance(obj, dict) or not isinstance(obj.get("pairs"), list):
        reporter.error("PAIR_DETAILS_SHAPE_INVALID", str(path), "expected top-level pairs list")
        return 0, set(), 0
    pairs = obj["pairs"]
    ids: list[str] = []
    zones = 0
    for index, item in enumerate(pairs):
        if not isinstance(item, dict) or not isinstance(item.get("pair"), dict):
            reporter.error("PAIR_ENTRY_SHAPE_INVALID", f"{path}#{index}", "expected pair object")
            continue
        pair = item["pair"]
        pair_id = pair.get("pair_id")
        if not pair_id:
            reporter.error("PAIR_ID_MISSING", f"{path}#{index}", "pair.pair_id missing")
        else:
            ids.append(str(pair_id))
        for key in ("photo_a", "photo_b"):
            if not pair.get(key):
                reporter.warn("PAIR_PHOTO_REF_MISSING", f"{path}#{index}", key)
        item_zones = item.get("zones", [])
        if isinstance(item_zones, list):
            zones += len(item_zones)
        elif isinstance(item_zones, dict):
            zones += len(item_zones)
        else:
            reporter.warn("PAIR_ZONES_SHAPE_INVALID", f"{path}#{index}", type(item_zones).__name__)
    duplicates = [key for key, count in Counter(ids).items() if count > 1]
    for pair_id in duplicates:
        reporter.error("PAIR_ID_DUPLICATE", pair_id, f"count={ids.count(pair_id)}")
    return len(pairs), set(ids), zones


def validate_artifact_index(obj: Any, path: Path, reporter: Reporter) -> int:
    if not isinstance(obj, dict) or not isinstance(obj.get("artifacts"), list):
        reporter.error("ARTIFACT_INDEX_SHAPE_INVALID", str(path), "expected artifacts list")
        return 0
    names = []
    for index, item in enumerate(obj["artifacts"]):
        if not isinstance(item, dict) or not item.get("name"):
            reporter.error("ARTIFACT_ENTRY_INVALID", f"{path}#{index}", "artifact name missing")
        else:
            names.append(str(item["name"]))
    if len(names) != len(set(names)):
        reporter.error("ARTIFACT_NAME_DUPLICATE", str(path), "duplicate artifact names")
    metadata = [name for name in names if name == ".DS_Store" or name.startswith("._")]
    if metadata:
        reporter.warn("ARTIFACT_INDEX_MACOS_METADATA", str(path), f"count={len(metadata)} ignored by validator")
    return len(names)


def validate_evidence(obj: Any, path: Path, pair_ids: set[str], reporter: Reporter) -> int:
    if obj is None:
        reporter.warn("EVIDENCE_PACKETS_REMOVED", str(path), "file removed from pipeline output; evidence state is in pair_metrics.csv")
        return 0
    if not isinstance(obj, dict) or not isinstance(obj.get("packets"), list):
        reporter.error("EVIDENCE_SHAPE_INVALID", str(path), "expected packets list")
        return 0
    packets = obj["packets"]
    for index, packet in enumerate(packets):
        if not isinstance(packet, dict):
            reporter.error("EVIDENCE_ENTRY_INVALID", f"{path}#{index}", "packet is not object")
            continue
        pid = packet.get("pair_id") or packet.get("pair", {}).get("pair_id") if isinstance(packet.get("pair"), dict) else packet.get("pair_id")
        if pid and pair_ids and str(pid) not in pair_ids:
            reporter.error("EVIDENCE_PAIR_REF_MISSING", f"{path}#{index}", str(pid))
    return len(packets)


def main() -> int:
    args = parse_args()
    reporter = Reporter(max(1, args.sample_limit))
    root = args.stage2_root.resolve()
    if not root.is_dir():
        reporter.error("STAGE2_ROOT_INVALID", str(root), "directory does not exist")
        print(f"SUMMARY script=check_stage2_contract status=BLOCKED checked_files=0 errors={reporter.errors} warnings={reporter.warnings}")
        return 1

    ignored = sum(1 for p in root.rglob("*") if p.is_file() and is_ignored(p))
    if ignored:
        reporter.warn("MACOS_METADATA_IGNORED", str(root), f"count={ignored}")

    checked = 0
    loaded: dict[str, Any] = {}
    for name in CANONICAL_JSON:
        path = root / name
        if not path.is_file():
            reporter.error("CANONICAL_JSON_MISSING", name, "required artifact not found")
            continue
        if is_ignored(path) or path.stat().st_size == 0:
            reporter.error("CANONICAL_JSON_INVALID", name, "ignored metadata or empty file")
            continue
        checked += 1
        obj = safe_json(path, reporter)
        if obj is None:
            continue
        loaded[name] = obj
        schema = schema_of(obj)
        if schema and schema != EXPECTED_SCHEMA:
            reporter.warn("SCHEMA_MISMATCH", name, f"schema={schema} expected={EXPECTED_SCHEMA}")

    for name in OPTIONAL_JSON:
        path = root / name
        if path.is_file() and not is_ignored(path) and path.stat().st_size:
            checked += 1
            safe_json(path, reporter)

    for name in REMOVED_ARTIFACTS:
        path = root / name
        if path.is_file() and not is_ignored(path) and path.stat().st_size:
            reporter.warn("REMOVED_ARTIFACT_PRESENT", name, "file should be removed per new pipeline config")

    csv_stats: dict[str, int] = {}
    for name in CANONICAL_CSV:
        path = root / name
        if not path.is_file():
            continue
        if is_ignored(path) or path.stat().st_size == 0:
            reporter.error("CSV_INVALID", name, "ignored metadata or empty file")
            continue
        checked += 1
        fields, count, _ = safe_csv_rows(path, reporter)
        csv_stats[name] = count
        if not fields:
            reporter.error("CSV_HEADER_MISSING", name, "no header")
        if count == 0:
            reporter.warn("CSV_NO_DATA_ROWS", name, "header exists but data rows are empty")

    manifest = loaded.get("analysis_manifest.json")
    if manifest is None:
        reporter.error("ANALYSIS_MANIFEST_UNREADABLE", "analysis_manifest.json", "manifest unavailable")
    else:
        manifest = validate_manifest(manifest, root / "analysis_manifest.json", reporter)

    pair_count, pair_ids, zone_count = validate_pairs(loaded.get("pair_details.json"), root / "pair_details.json", reporter)
    artifact_count = validate_artifact_index(loaded.get("artifact_index.json"), root / "artifact_index.json", reporter)
    evidence_count = validate_evidence(loaded.get("evidence_packets.json"), root / "evidence_packets.json", pair_ids, reporter)

    declared_pairs = manifest.get("pair_count") if isinstance(manifest, dict) else None
    csv_pairs = csv_stats.get("pair_metrics.csv")
    if isinstance(declared_pairs, int) and pair_count and declared_pairs != pair_count:
        reporter.error("PAIR_COUNT_MISMATCH", "analysis_manifest.json", f"declared={declared_pairs} pair_details={pair_count}")
    if isinstance(declared_pairs, int) and csv_pairs is not None and declared_pairs != csv_pairs:
        reporter.error("PAIR_COUNT_CSV_MISMATCH", "pair_metrics.csv", f"declared={declared_pairs} rows={csv_pairs}")
    if evidence_count and pair_count and evidence_count != pair_count:
        reporter.warn("EVIDENCE_COUNT_MISMATCH", "evidence_packets.json", f"packets={evidence_count} pairs={pair_count}")

    if not pair_ids:
        reporter.error("NO_PAIR_IDS", "pair_details.json", "no canonical pair IDs extracted")

    status = "PASS" if reporter.errors == 0 else "BLOCKED"
    print(
        f"SUMMARY script=check_stage2_contract status={status} checked_files={checked} "
        f"ignored_macos_files={ignored} errors={reporter.errors} warnings={reporter.warnings} "
        f"pairs={pair_count} pair_metrics_rows={csv_pairs or 0} zones={zone_count} "
        f"evidence_packets={evidence_count} indexed_artifacts={artifact_count}"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
