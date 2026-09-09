"""Strict Stage 1 reader.

Two rules distinguish this from the legacy loader.

1. **Never invent a default.** Every field read here is declared in
   contract.py. If a declared field is missing, that record gets a recorded
   violation - it does not silently become 0.0. The legacy loader defaulted a
   missing texture score to 0.0, which sat below the quality floor and marked
   every pair in every run as quality-limited, with no error anywhere.

2. **Collect, do not raise.** A malformed photo produces a `LoadFailure` in the
   result. One unreadable file cannot abort a run over a thousand photos.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from . import contract
from .params import Params


@dataclass(frozen=True)
class LoadFailure:
    """Why one photo could not be used."""

    photo_id: str
    reason: str
    detail: str = ""

    def to_json(self) -> dict[str, str]:
        return {
            "photo_id": self.photo_id,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass
class Record:
    """One usable Stage 1 photo, with everything Stage 2 needs."""

    photo_id: str
    date: str | None
    sequence: int
    pose_bin: str
    path: Path

    # pose
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0

    # quality / QC
    alignment_quality: float = float("nan")
    detection_confidence: float = float("nan")
    face_area_ratio: float = float("nan")
    coordinate_noise_sigma: float = float("nan")
    reprojection_rmse: float = float("nan")
    pixels: int = 0
    texture_quality: float = float("nan")
    skin_quality: float = float("nan")

    # expression
    corner_lift_ioc: float = float("nan")
    jaw_open_ratio: float = float("nan")
    jaw_open_degree: float = float("nan")

    # provenance
    source_relative_path: str = ""
    date_conflict_days: int = 0
    conflict_sources: tuple[str, ...] = ()
    near_duplicate_of: str | None = None

    # geometry, loaded lazily
    _npz_path: Path | None = None
    _cache: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def angles(self) -> np.ndarray:
        return np.array([self.pitch, self.yaw, self.roll], dtype=np.float64)

    @property
    def is_dated(self) -> bool:
        return bool(self.date)

    def arrays(self) -> dict[str, np.ndarray]:
        """Load the reconstruction arrays, caching them for reuse."""
        if not self._cache:
            if self._npz_path is None:
                raise RuntimeError(f"{self.photo_id}: no reconstruction path")
            with np.load(self._npz_path, allow_pickle=False) as data:
                self._cache = {key: data[key] for key in data.files}
        return self._cache

    def release(self) -> None:
        """Drop cached arrays. Matters on datasets of thousands of photos."""
        self._cache = {}

    def landmarks(self, scheme: int = 134) -> np.ndarray:
        return np.asarray(
            self.arrays()[f"ldm{scheme}_object_normalized"], dtype=np.float64
        )

    def landmarks_identity_only(self, scheme: int = 134) -> np.ndarray:
        return np.asarray(
            self.arrays()[f"ldm{scheme}_identity_only"], dtype=np.float64
        )

    def visible(self, scheme: int = 134) -> np.ndarray:
        return np.asarray(self.arrays()[f"ldm{scheme}_visible"], dtype=bool)

    def to_json(self) -> dict[str, Any]:
        return {
            "photo_id": self.photo_id,
            "date": self.date,
            "same_date_sequence": self.sequence,
            "pose_bin": self.pose_bin,
            "angles_deg": {
                "pitch": round(self.pitch, 4),
                "yaw": round(self.yaw, 4),
                "roll": round(self.roll, 4),
            },
            "alignment_quality": self.alignment_quality,
            "detection_confidence": self.detection_confidence,
            "face_area_ratio": self.face_area_ratio,
            "texture_quality": self.texture_quality,
            "skin_quality": self.skin_quality,
            "pixels": self.pixels,
            "expression": {
                "corner_lift_ioc": self.corner_lift_ioc,
                "jaw_open_ratio": self.jaw_open_ratio,
                "jaw_open_degree": self.jaw_open_degree,
            },
            "source_relative_path": self.source_relative_path,
            "date_conflict_days": self.date_conflict_days,
            "near_duplicate_of": self.near_duplicate_of,
        }


@dataclass
class LoadResult:
    """Everything the loader found, good and bad."""

    records: list[Record] = field(default_factory=list)
    failures: list[LoadFailure] = field(default_factory=list)
    stage1_root: Path | None = None

    @property
    def dated(self) -> list[Record]:
        return [r for r in self.records if r.is_dated]

    @property
    def distinct_dates(self) -> list[str]:
        return sorted({r.date for r in self.records if r.date})

    def by_bin(self) -> dict[str, list[Record]]:
        out: dict[str, list[Record]] = {}
        for record in self.records:
            out.setdefault(record.pose_bin, []).append(record)
        for values in out.values():
            values.sort(key=lambda r: (r.date or "9999", r.sequence, r.photo_id))
        return out

    def summary(self) -> dict[str, Any]:
        return {
            "root": str(self.stage1_root) if self.stage1_root else None,
            "loaded": len(self.records),
            "failed": len(self.failures),
            "dated": len(self.dated),
            "distinct_dates": len(self.distinct_dates),
            "pose_bins": {
                name: len(items) for name, items in sorted(self.by_bin().items())
            },
            "failure_reasons": _count(f.reason for f in self.failures),
        }


def _count(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def _require_finite(value: Any, name: str, problems: list[str]) -> float:
    """Read a number that the contract says must be present and finite."""
    if value is None:
        problems.append(f"{name} missing")
        return float("nan")
    try:
        number = float(value)
    except (TypeError, ValueError):
        problems.append(f"{name} not numeric")
        return float("nan")
    if not np.isfinite(number):
        problems.append(f"{name} not finite")
        return float("nan")
    return number


def load_stage1(root: Path, params: Params) -> LoadResult:
    """Read a Stage 1 output tree into records, collecting per-photo failures."""
    root = Path(root)
    result = LoadResult(stage1_root=root)

    if not root.is_dir():
        result.failures.append(
            LoadFailure("", "stage1_root_missing", f"not a directory: {root}")
        )
        return result

    index_path = root / contract.MAIN_INDEX
    if not index_path.exists():
        result.failures.append(
            LoadFailure("", "index_missing", f"missing {contract.MAIN_INDEX}")
        )
        return result

    with index_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        photo_id = (row.get("photo_id") or "").strip()
        if not photo_id:
            result.failures.append(LoadFailure("", "index_row_without_photo_id"))
            continue
        record, failure = _load_one(root, photo_id, row, params)
        if failure is not None:
            result.failures.append(failure)
        else:
            result.records.append(record)

    result.records.sort(key=lambda r: (r.date or "9999", r.sequence, r.photo_id))
    return result


def _load_one(
    root: Path, photo_id: str, row: dict[str, str], params: Params
) -> tuple[Record | None, LoadFailure | None]:
    photo_dir = root / photo_id
    if not photo_dir.is_dir():
        return None, LoadFailure(photo_id, "photo_directory_missing")

    absent = [
        name for name in contract.REQUIRED_PHOTO_FILES if not (photo_dir / name).exists()
    ]
    if absent:
        return None, LoadFailure(photo_id, "required_file_missing", ", ".join(absent))

    # -- admission: Stage 1 must have declared this photo complete -----------
    try:
        validation = json.loads(
            (photo_dir / "validation.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return None, LoadFailure(photo_id, "validation_unreadable", str(exc))
    status = validation.get("status")
    if status != "complete":
        return None, LoadFailure(photo_id, "validation_not_complete", f"status={status}")

    try:
        info = json.loads((photo_dir / "info.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, LoadFailure(photo_id, "info_unreadable", str(exc))

    problems: list[str] = []
    get = lambda path, default=None: contract.dotted(info, path, default)  # noqa: E731

    # -- mandatory QC. Fail closed: a photo whose quality we cannot establish
    # -- is excluded, never assumed good.
    alignment_quality = _require_finite(
        get(contract.INFO_FIELDS["alignment_quality"]), "alignment_quality", problems
    )
    if np.isfinite(alignment_quality) and not 0.0 <= alignment_quality <= 1.0:
        problems.append("alignment_quality out of range")

    detection_confidence = _require_finite(
        get(contract.INFO_FIELDS["detection_confidence"]),
        "detection_confidence",
        problems,
    )
    face_area_ratio = _require_finite(
        get(contract.INFO_FIELDS["face_area_ratio"]), "face_area_ratio", problems
    )

    if problems and params["fail_closed_missing_qc"]:
        return None, LoadFailure(photo_id, "missing_mandatory_qc", "; ".join(problems))

    # -- texture quality: read from the location Stage 1 actually writes.
    texture_quality = float("nan")
    texture_path = photo_dir / "texture.json"
    if texture_path.exists():
        try:
            texture = json.loads(texture_path.read_text(encoding="utf-8"))
            score = contract.dotted(
                texture, f"{contract.TEXTURE_QUALITY_PATH}.score"
            )
            if score is not None:
                texture_quality = float(score)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            # Texture is a supporting channel. Its absence limits claims about
            # texture but must not exclude the photo's geometry.
            texture_quality = float("nan")

    npz_path = photo_dir / "reconstruction.npz"
    try:
        with np.load(npz_path, allow_pickle=False) as data:
            present = set(data.files)
            angles = np.asarray(data["angle_deg_pitch_yaw_roll"], dtype=np.float64)
    except (OSError, ValueError, KeyError) as exc:
        return None, LoadFailure(
            photo_id,
            "reconstruction_unreadable",
            f"invalid Stage 1 artifact at {npz_path}: {exc}",
        )

    missing_arrays = [key for key in contract.NPZ_REQUIRED if key not in present]
    if missing_arrays and params["strict_contract"]:
        return None, LoadFailure(
            photo_id, "npz_contract_violation", ", ".join(sorted(missing_arrays))
        )

    sequence_raw = (row.get("same_date_sequence") or "1").strip()
    try:
        sequence = int(sequence_raw or 1)
    except ValueError:
        sequence = 1

    record = Record(
        photo_id=photo_id,
        date=(row.get("date") or "").strip() or None,
        sequence=sequence,
        pose_bin=(row.get("pose_bin") or "unknown").strip() or "unknown",
        path=photo_dir,
        pitch=float(angles[0]),
        yaw=float(angles[1]),
        roll=float(angles[2]),
        alignment_quality=alignment_quality,
        detection_confidence=detection_confidence,
        face_area_ratio=face_area_ratio,
        coordinate_noise_sigma=float(
            get(contract.INFO_FIELDS["coordinate_noise_sigma"], float("nan")) or
            float("nan")
        ),
        reprojection_rmse=float(
            get(contract.INFO_FIELDS["reprojection_rmse"], float("nan")) or float("nan")
        ),
        pixels=int(get(contract.INFO_FIELDS["pixels"], 0) or 0),
        texture_quality=texture_quality,
        skin_quality=float(
            get(contract.INFO_FIELDS["skin_quality_score"], float("nan")) or
            float("nan")
        ),
        corner_lift_ioc=float(
            get(contract.INFO_FIELDS["corner_lift_ioc"], float("nan")) or float("nan")
        ),
        jaw_open_ratio=float(
            get(contract.INFO_FIELDS["jaw_open_ratio"], float("nan")) or float("nan")
        ),
        jaw_open_degree=float(
            get(contract.INFO_FIELDS["jaw_open_degree"], float("nan")) or float("nan")
        ),
        source_relative_path=str(
            get(contract.INFO_FIELDS["source_relative_path"], "") or ""
        ),
        date_conflict_days=int(
            get(contract.INFO_FIELDS["date_delta_days"], 0) or 0
        ),
        conflict_sources=tuple(
            get(contract.INFO_FIELDS["conflict_sources"], []) or []
        ),
        near_duplicate_of=get(contract.INFO_FIELDS["near_duplicate_of"]),
        _npz_path=npz_path,
    )
    return record, None
