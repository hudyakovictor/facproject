"""Safe adapter for pre-extracted landmark archives used by scenario planning.

It accepts either an extracted ``person_*/frame_*/info.json`` tree or a tar
archive containing that tree.  It does not infer faces and does not alter the
source landmark files.  Scenario dates are explicitly synthetic.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
import json
from pathlib import Path
import tarfile
from typing import Final

POSE_BINS: Final[tuple[str, ...]] = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)


@dataclass(frozen=True)
class ArchiveRecord:
    dataset_id: str
    record_id: str
    pose_bin: str
    source_dir: Path
    date: str | None = None


def safe_extract_archive(archive: Path, destination: Path) -> Path:
    """Extract a tar archive while rejecting path traversal and links."""
    destination.mkdir(parents=True, exist_ok=True)
    base = destination.resolve()
    with tarfile.open(archive, "r:*") as handle:
        members = handle.getmembers()
        for member in members:
            target = (base / member.name).resolve()
            if not target.is_relative_to(base) or member.issym() or member.islnk():
                raise ValueError(f"unsafe archive member: {member.name!r}")
        handle.extractall(base, members, filter="data")
    # Some archives have one top-level directory; support both layouts.
    candidates = [base, *[p for p in base.iterdir() if p.is_dir()]]
    return next((p for p in candidates if any(p.glob("person_*/frame_*/info.json"))), base)


def load_archive_records(root: Path | None) -> list[ArchiveRecord]:
    if root is None or not root.is_dir():
        return []
    records: list[ArchiveRecord] = []
    for info_path in sorted(root.glob("person_*/frame_*/info.json")):
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            pose = info.get("pose") or info.get("chronology") or {}
            pose_bin = str(pose.get("pose_bin") or "")
            if pose_bin not in POSE_BINS:
                continue
            directory = info_path.parent
            records.append(ArchiveRecord(
                dataset_id=directory.parent.name,
                record_id=str(info.get("photo_id") or directory.name),
                pose_bin=pose_bin,
                source_dir=directory,
            ))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return records


def group_by_person_pose(records: list[ArchiveRecord]) -> dict[tuple[str, str], list[ArchiveRecord]]:
    grouped: dict[tuple[str, str], list[ArchiveRecord]] = {}
    for record in records:
        grouped.setdefault((record.dataset_id, record.pose_bin), []).append(record)
    for values in grouped.values():
        values.sort(key=lambda x: x.record_id)
    return grouped


def with_synthetic_dates(records: list[ArchiveRecord], start: date = date(2000, 1, 1)) -> list[ArchiveRecord]:
    """Assign order-only dates, never capture dates, for a test chronology."""
    return [replace(record, date=(start + timedelta(days=index)).isoformat())
            for index, record in enumerate(records)]
