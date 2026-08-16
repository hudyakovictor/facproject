"""Построение проверяемого индекса калибровки из завершённого Stage 1."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from app6.stage1.config import POSE_BINS

_PERSON_FRAME = re.compile(r"(?P<person>person_\d+)(?:[/\\\\]|_)+(?P<frame>frame_[A-Za-z0-9_-]+)", re.I)
_REQUIRED_FILES = {
    "ldm106_raw_file": "ldm106_raw",
    "ldm106_aligned_file": "ldm106_chronology",
    "ldm134_raw_file": "ldm134_raw",
    "ldm134_aligned_file": "ldm134_chronology",
    "npz_file": "reconstruction",
}


def _relative(root: Path, child: Path) -> str:
    return child.relative_to(root).as_posix()


def _identity(info: dict[str, Any], source_path: str) -> tuple[str, str]:
    match = _PERSON_FRAME.search(source_path) or _PERSON_FRAME.search(str(info.get("source_filename", "")))
    if not match:
        raise ValueError(f"cannot derive person/frame identifier from {source_path!r}")
    return match.group("person").lower(), match.group("frame")


def build_calibration_index(stage1_root: Path, output_path: Path | None = None) -> Path:
    """Build an index only when Stage 1 completed all supplied frames.

    Paths in the CSV are relative to ``stage1_root`` so it can be passed
    unchanged to release preflight and Stage 2.
    """
    root = stage1_root.resolve()
    manifest_path, timeline_path = root / "stage1_manifest.json", root / "main_timeline.csv"
    if not manifest_path.is_file() or not timeline_path.is_file():
        raise FileNotFoundError("completed Stage 1 requires stage1_manifest.json and main_timeline.csv")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError(f"Stage 1 is not complete: {manifest.get('status')!r}")

    with timeline_path.open(newline="", encoding="utf-8") as handle:
        timeline = list(csv.DictReader(handle))
    expected = int(manifest.get("success_count", -1))
    if not timeline or len(timeline) != expected or expected != int(manifest.get("input_count", -2)):
        raise ValueError("timeline is incomplete or does not match the Stage 1 manifest")

    rows: list[dict[str, Any]] = []
    for item in timeline:
        photo_id = item.get("photo_id", "")
        info_path = root / photo_id / "info.json"
        if not info_path.is_file():
            raise FileNotFoundError(f"missing info.json for {photo_id}")
        info = json.loads(info_path.read_text(encoding="utf-8"))
        person, frame = _identity(info, item.get("source_relative_path", ""))
        pose = info.get("pose", {})
        files = info.get("files", {})
        row: dict[str, Any] = {
            "dataset_id": person, "record_id": frame,
            "pose_bin": pose.get("pose_bin"), "yaw": pose.get("yaw"),
            "pitch": pose.get("pitch"), "roll": pose.get("roll"),
            "metadata_file": _relative(root, info_path),
            "source_filename": info.get("source_filename", ""),
            "source_relative_path": info.get("source_relative_path", ""),
            "source_digest": info.get("source_digest", ""),
            "photo_id": photo_id,
        }
        for column, file_key in _REQUIRED_FILES.items():
            name = files.get(file_key)
            candidate = info_path.parent / str(name or "")
            if not name or not candidate.is_file():
                raise FileNotFoundError(f"{photo_id}: missing required artifact {file_key}")
            row[column] = _relative(root, candidate)
        rows.append(row)

    allowed_poses = {name for name, *_ in POSE_BINS}
    if {row["pose_bin"] for row in rows} - allowed_poses:
        raise ValueError("Stage 1 returned an unknown pose bin")
    keys = [(row["dataset_id"], row["record_id"], row["pose_bin"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate person/frame/pose records in calibration index")

    destination = (output_path or root / "all_calibration_index.csv").resolve()
    if destination.parent != root and root not in destination.parents:
        raise ValueError("calibration index must be written inside the Stage 1 output directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(destination)
    return destination
