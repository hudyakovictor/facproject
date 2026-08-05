"""Read-only inventory of extracted Stage 1 and calibration datasets."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .calibration import POSE_BINS
from .runtime_config import RuntimePaths, load_runtime_paths

DATASET_INVENTORY_SCHEMA = "deeputin-dataset-inventory-v1.0"
DATASET_ISSUES_SCHEMA = "deeputin-dataset-issues-v1.0"

CORE_ARTIFACTS = (
    "original.jpg",
    "thumb.jpg",
    "face_crop.jpg",
    "reconstruction.npz",
    "ldm106_raw.csv",
    "ldm106_aligned.csv",
    "ldm106_chronology.csv",
    "ldm106_original.csv",
    "ldm134_raw.csv",
    "ldm134_aligned.csv",
    "ldm134_chronology.csv",
    "ldm134_original.csv",
    "mesh.obj",
    "mesh.mtl",
    "face_mask.png",
    "info.json",
    "semantic_channels.npz",
    "texture.json",
    "uv_texture.png",
    "uv.npz",
    "validation.json",
)
MANIFEST_CANDIDATES = ("stage1_manifest.json", "analysis_manifest.json", "manifest.json")

ISSUE_CATEGORIES = (
    "missing_photo_id",
    "duplicate_photo_id",
    "unknown_pose_bin",
    "date_provenance_conflict",
    "near_duplicate",
    "exact_duplicate_link",
    "missing_record_directory",
    "missing_artifact",
)


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _record_id(row: dict[str, str]) -> str:
    return str(row.get("photo_id") or row.get("record_id") or row.get("id") or "").strip()


def _record_dir(stage1_root: Path, row: dict[str, str], record_id: str) -> Path:
    for field in ("record_dir", "output_dir"):
        raw = str(row.get(field) or "").strip()
        if raw:
            candidate = Path(raw)
            if candidate.is_dir():
                return candidate
    return stage1_root / record_id


def _manifest(stage1_root: Path) -> tuple[Path | None, dict[str, Any] | None, str | None]:
    for name in MANIFEST_CANDIDATES:
        path = stage1_root / name
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                value = None
            return path, value if isinstance(value, dict) else None, _sha256(path)
    return None, None, None


def inventory_stage1(stage1_root: Path) -> dict[str, Any]:
    """Scan Stage 1 without modifying or loading heavy numeric artifacts."""
    index_path = stage1_root / "main_timeline.csv"
    rows = _read_csv(index_path)
    manifest_path, manifest, manifest_hash = _manifest(stage1_root)
    pose_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    artifact_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    invalid_rows: list[dict[str, Any]] = []
    incomplete_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_ids = 0
    date_conflict_count = 0
    near_duplicate_count = 0
    exact_duplicate_count = 0

    for row_number, row in enumerate(rows, start=2):
        record_id = _record_id(row)
        if not record_id:
            issue_counts["missing_photo_id"] += 1
            invalid_rows.append({"row": row_number, "reason": "missing_photo_id"})
            continue
        if record_id in seen:
            issue_counts["duplicate_photo_id"] += 1
            invalid_rows.append(
                {"row": row_number, "photo_id": record_id, "reason": "duplicate_photo_id"}
            )
            continue
        seen.add(record_id)
        valid_ids += 1
        pose = str(row.get("pose_bin") or "unknown")
        pose_counts[pose] += 1
        if pose not in POSE_BINS:
            issue_counts["unknown_pose_bin"] += 1
        date_value = str(row.get("date") or "")
        year_counts[date_value[:4] if len(date_value) >= 4 else "unknown"] += 1

        provenance = str(row.get("date_provenance_status") or "").lower()
        if provenance in {"conflict", "date_conflict", "exif_conflict"}:
            date_conflict_count += 1
            issue_counts["date_provenance_conflict"] += 1
        near_dup = str(row.get("near_duplicate_of") or "").strip()
        if near_dup:
            near_duplicate_count += 1
            issue_counts["near_duplicate"] += 1
        exact_dup = str(row.get("exact_duplicate_of") or row.get("duplicate_of") or "").strip()
        if exact_dup:
            exact_duplicate_count += 1
            issue_counts["exact_duplicate_link"] += 1

        record_dir = _record_dir(stage1_root, row, record_id)
        if not record_dir.is_dir():
            issue_counts["missing_record_directory"] += 1
            incomplete_records.append({"photo_id": record_id, "missing": ["<record_directory>"]})
            continue
        missing: list[str] = []
        for name in CORE_ARTIFACTS:
            # original may be original.jpg or original.png / original.jpeg
            if name == "original.jpg":
                if any((record_dir / f"original{ext}").is_file() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    artifact_counts["original.jpg"] += 1
                else:
                    missing.append(name)
                    issue_counts["missing:original.jpg"] += 1
                continue
            if (record_dir / name).is_file():
                artifact_counts[name] += 1
            else:
                missing.append(name)
                issue_counts[f"missing:{name}"] += 1
        if missing:
            incomplete_records.append({"photo_id": record_id, "missing": missing})

    unknown_poses = sorted(pose for pose in pose_counts if pose not in POSE_BINS)
    dates = sorted(str(row.get("date")) for row in rows if row.get("date"))
    ready_records = max(0, valid_ids - len(incomplete_records))
    if rows and not invalid_rows and not incomplete_records and not unknown_poses:
        status = "ready"
    elif rows:
        status = "limited"
    else:
        status = "unavailable"

    return {
        "schema": DATASET_INVENTORY_SCHEMA,
        "kind": "stage1",
        "status": status,
        "read_only": True,
        "root": str(stage1_root),
        "index": str(index_path),
        "index_present": index_path.is_file(),
        "index_sha256": _sha256(index_path),
        "manifest_path": str(manifest_path) if manifest_path else None,
        "manifest_sha256": manifest_hash,
        "manifest": manifest,
        "record_count": len(rows),
        "valid_id_count": valid_ids,
        "ready_record_count": ready_records,
        "incomplete_record_count": len(incomplete_records),
        "date_range": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
        "pose_counts": {pose: pose_counts.get(pose, 0) for pose in POSE_BINS}
        | ({pose: pose_counts[pose] for pose in unknown_poses} if unknown_poses else {}),
        "year_counts": dict(sorted(year_counts.items())),
        "artifact_counts": dict(artifact_counts),
        "required_artifacts": list(CORE_ARTIFACTS),
        "issue_counts": dict(issue_counts),
        "invalid_rows": invalid_rows[:100],
        "incomplete_records": incomplete_records[:100],
        "truncated_issue_lists": len(invalid_rows) > 100 or len(incomplete_records) > 100,
        "provenance": {
            "date_conflict_count": date_conflict_count,
            "near_duplicate_count": near_duplicate_count,
            "exact_duplicate_count": exact_duplicate_count,
        },
    }


def inventory_calibration(calibration_root: Path) -> dict[str, Any]:
    index_path = calibration_root / "all_calibration_index.csv"
    manifest_path = calibration_root / "calibration_manifest.json"
    rows = _read_csv(index_path)
    persons = sorted(
        {
            str(row.get("dataset_id") or row.get("person_id") or "").strip()
            for row in rows
        }
        - {""}
    )
    pose_counts = Counter(str(row.get("pose_bin") or "unknown") for row in rows)
    directory_persons = (
        sorted(path.name for path in calibration_root.glob("person_*") if path.is_dir())
        if calibration_root.is_dir()
        else []
    )
    manifest: dict[str, Any] | None = None
    if manifest_path.is_file():
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            manifest = None
    unknown_poses = sorted(pose for pose in pose_counts if pose not in POSE_BINS)
    if rows and len(persons) >= 7 and not unknown_poses:
        status = "ready"
    elif rows:
        status = "limited"
    else:
        status = "unavailable"
    return {
        "schema": DATASET_INVENTORY_SCHEMA,
        "kind": "calibration",
        "status": status,
        "read_only": True,
        "root": str(calibration_root),
        "index": str(index_path),
        "index_present": index_path.is_file(),
        "index_sha256": _sha256(index_path),
        "manifest_path": str(manifest_path) if manifest_path.is_file() else None,
        "manifest_sha256": _sha256(manifest_path),
        "manifest": manifest,
        "record_count": len(rows),
        "person_count": len(persons),
        "persons": persons,
        "person_directories": directory_persons,
        "pose_counts": {pose: pose_counts.get(pose, 0) for pose in POSE_BINS}
        | ({pose: pose_counts[pose] for pose in unknown_poses} if unknown_poses else {}),
        "unknown_pose_bins": unknown_poses,
    }


def build_dataset_inventory(paths: RuntimePaths | None = None) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    stage1 = inventory_stage1(current.stage1_root)
    calibration = inventory_calibration(current.calibration_root)
    if stage1["status"] == "ready" and calibration["status"] == "ready":
        overall = "ready"
    elif stage1["status"] != "unavailable":
        overall = "limited"
    else:
        overall = "blocked"
    return {
        "schema": DATASET_INVENTORY_SCHEMA,
        "status": overall,
        "not_a_verdict": True,
        "stage1": stage1,
        "calibration": calibration,
        "paths": current.json_dict(),
    }


def _iter_stage1_issues(stage1_root: Path) -> list[dict[str, Any]]:
    """Build deterministic flat issue list for Stage 1."""
    index_path = stage1_root / "main_timeline.csv"
    rows = _read_csv(index_path)
    issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        record_id = _record_id(row)
        if not record_id:
            issues.append(
                {
                    "photo_id": "",
                    "category": "missing_photo_id",
                    "detail": f"row {row_number}",
                    "row": row_number,
                }
            )
            continue
        if record_id in seen:
            issues.append(
                {
                    "photo_id": record_id,
                    "category": "duplicate_photo_id",
                    "detail": f"row {row_number}",
                    "row": row_number,
                }
            )
            continue
        seen.add(record_id)
        pose = str(row.get("pose_bin") or "unknown")
        if pose not in POSE_BINS:
            issues.append(
                {
                    "photo_id": record_id,
                    "category": "unknown_pose_bin",
                    "detail": pose,
                    "row": row_number,
                }
            )
        provenance = str(row.get("date_provenance_status") or "").lower()
        if provenance in {"conflict", "date_conflict", "exif_conflict"}:
            issues.append(
                {
                    "photo_id": record_id,
                    "category": "date_provenance_conflict",
                    "detail": provenance,
                    "row": row_number,
                }
            )
        near_dup = str(row.get("near_duplicate_of") or "").strip()
        if near_dup:
            issues.append(
                {
                    "photo_id": record_id,
                    "category": "near_duplicate",
                    "detail": near_dup,
                    "row": row_number,
                }
            )
        exact_dup = str(row.get("exact_duplicate_of") or row.get("duplicate_of") or "").strip()
        if exact_dup:
            issues.append(
                {
                    "photo_id": record_id,
                    "category": "exact_duplicate_link",
                    "detail": exact_dup,
                    "row": row_number,
                }
            )
        record_dir = _record_dir(stage1_root, row, record_id)
        if not record_dir.is_dir():
            issues.append(
                {
                    "photo_id": record_id,
                    "category": "missing_record_directory",
                    "detail": str(record_dir),
                    "row": row_number,
                }
            )
            continue
        for name in CORE_ARTIFACTS:
            if name == "original.jpg":
                if not any(
                    (record_dir / f"original{ext}").is_file()
                    for ext in (".jpg", ".jpeg", ".png", ".webp")
                ):
                    issues.append(
                        {
                            "photo_id": record_id,
                            "category": "missing_artifact",
                            "detail": name,
                            "row": row_number,
                        }
                    )
                continue
            if not (record_dir / name).is_file():
                issues.append(
                    {
                        "photo_id": record_id,
                        "category": "missing_artifact",
                        "detail": name,
                        "row": row_number,
                    }
                )
    issues.sort(key=lambda item: (item["category"], item.get("photo_id") or "", item.get("row") or 0))
    return issues


def list_stage1_issues(
    stage1_root: Path,
    *,
    offset: int = 0,
    limit: int = 100,
    category: str | None = None,
) -> dict[str, Any]:
    offset = max(0, int(offset))
    limit = max(1, min(int(limit), 500))
    all_issues = _iter_stage1_issues(stage1_root)
    category_counts: Counter[str] = Counter(item["category"] for item in all_issues)
    filtered = (
        [item for item in all_issues if item["category"] == category]
        if category
        else all_issues
    )
    page = filtered[offset : offset + limit]
    return {
        "schema": DATASET_ISSUES_SCHEMA,
        "not_a_verdict": True,
        "read_only": True,
        "root": str(stage1_root),
        "total": len(filtered),
        "offset": offset,
        "limit": limit,
        "category": category,
        "category_counts": {name: category_counts.get(name, 0) for name in ISSUE_CATEGORIES},
        "issues": page,
    }
