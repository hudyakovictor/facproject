"""Read-only photo catalogue for the investigation UI.

Only filesystem metadata and filename/path hints are indexed. Image bytes are
never modified and pose hints are never treated as measured Stage-1 pose.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
from pathlib import Path
import re
from typing import Any

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
DATE_PATTERN = re.compile(r"(?<!\d)(?P<y>19\d{2}|20\d{2})_(?P<m>\d{1,2})_(?P<d>\d{1,2})(?!\d)")
SEQUENCE_PATTERN = re.compile(r"(?:\s*\((?P<n1>\d+)\)|[_-](?P<n2>\d+)|[-_ ]copy)$", re.I)
POSES = ("left_profile", "left_deep", "left_mid", "left_light", "frontal", "right_light", "right_mid", "right_deep", "right_profile")
POSE_ALIASES = {
    "lp": "left_profile", "leftprofile": "left_profile", "left_profile": "left_profile",
    "ld": "left_deep", "leftdeep": "left_deep", "left_deep": "left_deep",
    "lm": "left_mid", "leftmid": "left_mid", "left_mid": "left_mid", "left_medium": "left_mid",
    "ll": "left_light", "leftlight": "left_light", "left_light": "left_light",
    "f": "frontal", "front": "frontal", "frontal": "frontal",
    "rl": "right_light", "rightlight": "right_light", "right_light": "right_light",
    "rm": "right_mid", "rightmid": "right_mid", "right_mid": "right_mid", "right_medium": "right_mid",
    "rd": "right_deep", "rightdeep": "right_deep", "right_deep": "right_deep",
    "rp": "right_profile", "rightprofile": "right_profile", "right_profile": "right_profile",
}


def _normalise_token(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")


def parse_filename_date(path: Path) -> tuple[str | None, int | None, int]:
    match = DATE_PATTERN.search(path.stem)
    if not match:
        return None, None, 1
    try:
        parsed = date(int(match.group("y")), int(match.group("m")), int(match.group("d")))
    except ValueError:
        return None, None, 1
    suffix = SEQUENCE_PATTERN.search(path.stem[match.end():])
    sequence = int((suffix.group("n1") or suffix.group("n2")) if suffix else 1)
    return parsed.isoformat(), parsed.year, sequence


def infer_pose_hint(relative: Path) -> tuple[str, str]:
    # Folder names are preferred over filename fragments. This is only an
    # organisation hint; measured pose must still come from fresh Stage 1.
    for part in reversed(relative.parent.parts):
        token = _normalise_token(part)
        if token in POSE_ALIASES:
            return POSE_ALIASES[token], "folder_hint"
    stem = _normalise_token(relative.stem)
    padded = f"_{stem}_"
    for alias, canonical in sorted(POSE_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if len(alias) > 1 and f"_{alias}_" in padded:
            return canonical, "filename_hint"
    return "unknown", "none"


@dataclass(frozen=True)
class PhotoRecord:
    id: str
    relative_path: str
    filename: str
    date: str | None
    year: int | None
    sequence: int
    pose_bin_hint: str
    pose_hint_source: str
    size_bytes: int
    modified_ns: int
    processing_status: str
    issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["issues"] = list(self.issues)
        return result


class PhotoIndex:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=False)

    def scan(self) -> list[PhotoRecord]:
        if not self.root.is_dir():
            return []
        records: list[PhotoRecord] = []
        for path in sorted(self.root.rglob("*")):
            try:
                if path.is_symlink() or not path.is_file() or path.name.startswith("._") or path.suffix.lower() not in PHOTO_SUFFIXES:
                    continue
                resolved = path.resolve(strict=True)
                relative = resolved.relative_to(self.root)
                stat = resolved.stat()
            except (OSError, ValueError):
                continue
            date_iso, year, sequence = parse_filename_date(relative)
            pose, pose_source = infer_pose_hint(relative)
            issues = []
            if date_iso is None:
                issues.append("date_unparseable")
            if pose == "unknown":
                issues.append("pose_requires_stage1")
            stable_id = hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()[:20]
            records.append(PhotoRecord(stable_id, relative.as_posix(), relative.name, date_iso, year, sequence, pose, pose_source, stat.st_size, stat.st_mtime_ns, "not_indexed_by_stage1", tuple(issues)))
        records.sort(key=lambda x: (x.date is None, x.date or "9999-99-99", x.sequence, x.relative_path))
        return records

    def query(self, *, offset: int = 0, limit: int = 500, pose: str | None = None, year_from: int | None = None, year_to: int | None = None) -> dict[str, Any]:
        if offset < 0 or not 1 <= limit <= 2000:
            raise ValueError("offset must be >= 0 and limit must be in 1..2000")
        if pose is not None and pose not in set(POSES) | {"unknown"}:
            raise ValueError("unknown pose filter")
        records = self.scan()
        filtered = [r for r in records if (pose is None or r.pose_bin_hint == pose) and (year_from is None or (r.year is not None and r.year >= year_from)) and (year_to is None or (r.year is not None and r.year <= year_to))]
        pose_counts = {key: 0 for key in (*POSES, "unknown")}
        for item in records:
            pose_counts[item.pose_bin_hint] = pose_counts.get(item.pose_bin_hint, 0) + 1
        years = [r.year for r in records if r.year is not None]
        return {
            "schema": "dpo-photo-index-v1",
            "read_only": True,
            "root": str(self.root),
            "total": len(filtered),
            "offset": offset,
            "limit": limit,
            "items": [x.to_dict() for x in filtered[offset:offset + limit]],
            "summary": {
                "all_photos": len(records),
                "dated": len(years),
                "undated": len(records) - len(years),
                "year_min": min(years) if years else None,
                "year_max": max(years) if years else None,
                "pose_counts": pose_counts,
                "pose_values_are_hints": True,
            },
        }
