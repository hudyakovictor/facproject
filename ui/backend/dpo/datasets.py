"""Dataset registry and strict trust policy for calibration tables."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
from pathlib import Path
from typing import Iterable

from .settings import DatasetSettings


class TrustClass(StrEnum):
    TRUSTED_PAIR_BINDING = "trusted_pair_binding"
    TRUSTED_POSE_ANGLE = "trusted_pose_angle"
    IDENTIFIER_ONLY = "identifier_only"
    RECOMPUTE_FROM_PHOTO = "recompute_from_photo"
    IGNORED_INVALID_COORDINATE = "ignored_invalid_coordinate"
    UNKNOWN_REQUIRES_REVIEW = "unknown_requires_review"


_PAIR_FIELDS = {"pair_id", "pair_role", "main_photo_id", "calibration_photo_id", "paired_photo_id", "reference_photo_id"}
_ANGLE_FIELDS = {"yaw", "pitch", "roll"}
_IDENTIFIER_FIELDS = {"dataset_id", "person_id", "person", "record_id", "source_filename", "frame_index", "photo_id"}
_RECOMPUTE_FIELDS = {"pose_bin", "landmarks", "keypoints", "mesh", "visibility", "descriptors"}
_COORD_EXACT = {"x", "y", "z", "x1", "y1", "z1", "x2", "y2", "z2"}
_COORD_TOKENS = ("landmark_", "keypoint_", "mesh_", "vertex_", "coord_", "coordinate_")


def classify_field(name: str) -> TrustClass:
    key = name.strip().lower()
    if key in _PAIR_FIELDS or key.endswith("_pair_id"):
        return TrustClass.TRUSTED_PAIR_BINDING
    if key in _ANGLE_FIELDS or key.endswith(("_yaw", "_pitch", "_roll")):
        return TrustClass.TRUSTED_POSE_ANGLE
    if key in _IDENTIFIER_FIELDS or key.endswith(("_filename", "_record_id", "_photo_id")):
        return TrustClass.IDENTIFIER_ONLY
    if key in _COORD_EXACT or any(token in key for token in _COORD_TOKENS):
        return TrustClass.IGNORED_INVALID_COORDINATE
    if key in _RECOMPUTE_FIELDS:
        return TrustClass.RECOMPUTE_FROM_PHOTO
    return TrustClass.UNKNOWN_REQUIRES_REVIEW


@dataclass(frozen=True)
class DatasetInspection:
    role: str
    root: str | None
    available: bool
    file_count: int
    total_bytes: int
    fingerprint: str | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


@dataclass(frozen=True)
class CalibrationTableReport:
    path: str
    row_count: int
    field_trust: dict[str, str]
    trusted_rows: tuple[dict[str, str | float | int | None], ...]
    ignored_fields: tuple[str, ...]
    review_fields: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "row_count": self.row_count,
            "field_trust": self.field_trust,
            "trusted_rows": list(self.trusted_rows),
            "ignored_fields": list(self.ignored_fields),
            "review_fields": list(self.review_fields),
        }


class DatasetRegistry:
    PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

    def __init__(self, settings: DatasetSettings) -> None:
        self.settings = settings

    def inspect_photos(self, root: Path | None, role: str) -> DatasetInspection:
        if root is None:
            return DatasetInspection(role, None, False, 0, 0, None, ("dataset path is not configured",))
        if not root.is_dir():
            return DatasetInspection(role, str(root), False, 0, 0, None, ("dataset directory is missing",))
        count = total = 0
        digest = hashlib.sha256()
        try:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.name.startswith("._") or path.suffix.lower() not in self.PHOTO_SUFFIXES:
                    continue
                stat = path.stat()
                relative = path.relative_to(root).as_posix()
                digest.update(relative.encode("utf-8"))
                digest.update(str(stat.st_size).encode("ascii"))
                digest.update(str(stat.st_mtime_ns).encode("ascii"))
                count += 1
                total += stat.st_size
        except OSError as exc:
            return DatasetInspection(role, str(root), False, count, total, None, (f"scan interrupted: {exc}",))
        reasons = () if count else ("no supported photo files found",)
        return DatasetInspection(role, str(root), bool(count), count, total, digest.hexdigest(), reasons)

    def inspect_all(self) -> dict[str, DatasetInspection]:
        calibration_photos = None
        if self.settings.calibration_root is not None:
            calibration_photos = self.settings.calibration_root / self.settings.calibration_photos_subdir
        return {
            "main": self.inspect_photos(self.settings.main_root, "research_main"),
            "calibration": self.inspect_photos(calibration_photos, "calibration_seven_person"),
        }

    def find_calibration_index(self) -> Path | None:
        root = self.settings.calibration_root
        if root is None:
            return None
        for name in self.settings.calibration_index_candidates:
            path = root / name
            if path.is_file():
                return path
        return None

    def parse_calibration_table(self, path: Path, *, row_limit: int | None = None) -> CalibrationTableReport:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            trust = {field: classify_field(field) for field in fields}
            trusted_rows: list[dict[str, str | float | int | None]] = []
            row_count = 0
            for raw in reader:
                row_count += 1
                clean: dict[str, str | float | int | None] = {}
                for field, value in raw.items():
                    policy = trust.get(field, TrustClass.UNKNOWN_REQUIRES_REVIEW)
                    if policy in {TrustClass.IGNORED_INVALID_COORDINATE, TrustClass.RECOMPUTE_FROM_PHOTO, TrustClass.UNKNOWN_REQUIRES_REVIEW}:
                        continue
                    stripped = value.strip() if isinstance(value, str) else value
                    if policy == TrustClass.TRUSTED_POSE_ANGLE:
                        try:
                            clean[field] = float(stripped) if stripped not in (None, "") else None
                        except (TypeError, ValueError):
                            clean[field] = None
                    elif field.strip().lower() == "frame_index":
                        try:
                            clean[field] = int(stripped) if stripped not in (None, "") else None
                        except (TypeError, ValueError):
                            clean[field] = None
                    else:
                        clean[field] = stripped
                trusted_rows.append(clean)
                if row_limit is not None and row_count >= row_limit:
                    break
        ignored = tuple(sorted(k for k, v in trust.items() if v in {TrustClass.IGNORED_INVALID_COORDINATE, TrustClass.RECOMPUTE_FROM_PHOTO}))
        review = tuple(sorted(k for k, v in trust.items() if v == TrustClass.UNKNOWN_REQUIRES_REVIEW))
        return CalibrationTableReport(
            str(path), row_count, {k: v.value for k, v in trust.items()}, tuple(trusted_rows), ignored, review
        )
