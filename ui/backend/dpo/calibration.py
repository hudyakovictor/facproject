"""Calibration Run Group integrity core.

Enforces the two guarantees the journalist's methodology depends on:

1. A Run Group (fresh main extraction + fresh seven-person calibration
   extraction + calibration build + main analysis) may never be assembled
   from outputs that disagree on dataset/code/model/config provenance. Any
   mismatch is rejected outright (fail-closed), never silently merged.
2. A calibration table's already-classified trusted rows (see ``datasets.py``)
   are re-validated defensively before being attached to a Run Group, so a
   landmark/keypoint/mesh/coordinate field can never enter the pipeline even
   if an upstream classifier regresses.

This module never writes into app6 or dataset roots; it only persists JSON
bookkeeping under the control-plane root, mirroring the pattern used by
``BackupManager``/``LayoutStore``/``SnapshotStore``.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .datasets import CalibrationTableReport

REQUIRED_ROLES = ("main_extraction", "calibration_extraction", "calibration_build", "main_analysis")
HASH_FIELDS = ("dataset_hash", "code_hash", "model_hash", "config_hash")
_FORBIDDEN_TOKENS = ("landmark", "keypoint", "mesh", "vertex", "coord")
_FORBIDDEN_EXACT = {"x", "y", "z", "x1", "y1", "z1", "x2", "y2", "z2"}
_ID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
_POSE_BIN_CODES = {"left_profile": "LP", "left_deep": "LD", "left_mid": "LM", "left_light": "LL", "frontal": "F", "right_light": "RL", "right_mid": "RM", "right_deep": "RD", "right_profile": "RP"}


def load_pose_bins(app6_root: Path) -> list[dict[str, Any]]:
    """Statically parses the 9 canonical pose bins from app6/stage1/config.py
    without importing app6 code (read-only observation policy). Returns the
    real ``POSE_BINS`` boundaries/canonical yaw used by geometry.classify_pose().
    Pitch/roll boundaries, residual distance, pair eligibility and coverage are
    not defined by this static policy and require an actual calibration run,
    so callers must not fabricate them here."""
    text = (Path(app6_root) / "stage1" / "config.py").read_text(encoding="utf-8")
    marker = "POSE_BINS = "
    open_paren = text.index("(", text.index(marker) + len(marker))
    depth = 0
    end = open_paren
    for i in range(open_paren, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    import ast as _ast

    bins = _ast.literal_eval(text[open_paren:end])
    return [
        {"name": name, "code": _POSE_BIN_CODES.get(name, name[:2].upper()), "yaw_min": lo, "yaw_max": hi, "canonical_yaw": canonical}
        for name, lo, hi, canonical in bins
    ]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HashMismatchError(RuntimeError):
    """Raised when a run's provenance hashes conflict with its run group."""


class RunGroupStateError(RuntimeError):
    """Raised when an operation is invalid for the run group's current status."""


class ForbiddenFieldError(ValueError):
    """Raised when a trusted-table row still carries a landmark/mesh/coordinate field."""


def assert_trusted_only(rows: list[dict[str, Any]]) -> None:
    """Defense-in-depth: reject any row carrying a recomputed-geometry or raw
    coordinate field, even if it was already supposed to be filtered upstream
    by ``datasets.classify_field``. Never silently drops a bad field."""
    for row in rows:
        for key in row:
            k = key.strip().lower()
            if k in _FORBIDDEN_EXACT or any(token in k for token in _FORBIDDEN_TOKENS):
                raise ForbiddenFieldError(f"trusted table row still carries a forbidden field: {key!r}")


@dataclass(frozen=True)
class RunHashes:
    dataset_hash: str
    code_hash: str
    model_hash: str
    config_hash: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class RunGroupMember:
    run_id: str
    role: str
    hashes: RunHashes
    registered_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "role": self.role, "hashes": self.hashes.to_dict(), "registered_at": self.registered_at}


@dataclass
class CalibrationRunGroup:
    id: str
    status: str
    members: dict[str, RunGroupMember]
    created_at: str
    updated_at: str
    approved_at: str | None = None
    approved_by: str | None = None
    rejected_reason: str | None = None
    trusted_table: dict[str, Any] | None = None
    bundle_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "dpo-calibration-run-group-v1",
            "id": self.id,
            "status": self.status,
            "members": {role: m.to_dict() for role, m in self.members.items()},
            "missing_roles": [r for r in REQUIRED_ROLES if r not in self.members],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "rejected_reason": self.rejected_reason,
            "trusted_table": self.trusted_table,
            "bundle_hash": self.bundle_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationRunGroup":
        members = {
            role: RunGroupMember(m["run_id"], m["role"], RunHashes(**m["hashes"]), m["registered_at"])
            for role, m in data.get("members", {}).items()
        }
        return cls(
            id=data["id"],
            status=data["status"],
            members=members,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            approved_at=data.get("approved_at"),
            approved_by=data.get("approved_by"),
            rejected_reason=data.get("rejected_reason"),
            trusted_table=data.get("trusted_table"),
            bundle_hash=data.get("bundle_hash"),
        )


def _bundle_hash(group_id: str, members: dict[str, RunGroupMember]) -> str:
    digest = hashlib.sha256()
    digest.update(group_id.encode("utf-8"))
    for role in REQUIRED_ROLES:
        member = members[role]
        digest.update(role.encode("utf-8"))
        for field_name in HASH_FIELDS:
            digest.update(getattr(member.hashes, field_name).encode("utf-8"))
    return digest.hexdigest()


class CalibrationRegistry:
    """Persists Run Groups as JSON files; enforces the hash-consistency guard
    and the draft -> candidate -> approved/rejected state machine. Reads and
    writes only under ``root`` (the control-plane calibration directory);
    never touches app6 or dataset roots."""

    FINALIZED = ("approved", "rejected")

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, group_id: str) -> Path:
        if not group_id or any(ch not in _ID_CHARS for ch in group_id):
            raise ValueError("group_id may contain only letters, digits, dash and underscore")
        return self.root / f"{group_id}.json"

    def _save(self, group: CalibrationRunGroup) -> None:
        path = self._path(group.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(group.to_dict(), ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def get(self, group_id: str) -> CalibrationRunGroup:
        path = self._path(group_id)
        if not path.is_file():
            raise KeyError(f"unknown calibration run group: {group_id}")
        return CalibrationRunGroup.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.root.glob("*.json"))]

    def create(self, group_id: str | None = None) -> CalibrationRunGroup:
        gid = group_id or uuid.uuid4().hex[:12]
        if self._path(gid).is_file():
            raise ValueError(f"calibration run group already exists: {gid}")
        ts = now()
        group = CalibrationRunGroup(gid, "draft", {}, ts, ts)
        self._save(group)
        return group

    def register_member(self, group_id: str, role: str, run_id: str, hashes: RunHashes) -> CalibrationRunGroup:
        if role not in REQUIRED_ROLES:
            raise ValueError(f"unknown run group role: {role!r}; expected one of {REQUIRED_ROLES}")
        group = self.get(group_id)
        if group.status in self.FINALIZED:
            raise RunGroupStateError(f"run group {group_id} is already {group.status} and cannot be modified")
        for existing_role, member in group.members.items():
            if existing_role == role:
                continue
            for field_name in HASH_FIELDS:
                theirs = getattr(member.hashes, field_name)
                mine = getattr(hashes, field_name)
                if theirs != mine:
                    raise HashMismatchError(
                        f"{field_name} mismatch between {existing_role} ({theirs}) and {role} ({mine}); "
                        "refusing to mix calibration outputs from different dataset/code/model/config hashes"
                    )
        group.members[role] = RunGroupMember(run_id, role, hashes, now())
        group.status = "candidate" if all(r in group.members for r in REQUIRED_ROLES) else "draft"
        group.updated_at = now()
        self._save(group)
        return group

    def attach_trusted_table(self, group_id: str, report: CalibrationTableReport) -> CalibrationRunGroup:
        assert_trusted_only(list(report.trusted_rows))
        group = self.get(group_id)
        if group.status in self.FINALIZED:
            raise RunGroupStateError(f"run group {group_id} is already {group.status} and cannot be modified")
        group.trusted_table = report.to_dict()
        group.updated_at = now()
        self._save(group)
        return group

    def approve(self, group_id: str, *, approved_by: str) -> CalibrationRunGroup:
        group = self.get(group_id)
        if group.status != "candidate":
            raise RunGroupStateError(f"run group {group_id} is {group.status}, not candidate; cannot approve")
        if not approved_by.strip():
            raise ValueError("approved_by is required")
        group.status = "approved"
        group.approved_at = now()
        group.approved_by = approved_by.strip()
        group.bundle_hash = _bundle_hash(group.id, group.members)
        group.updated_at = group.approved_at
        self._save(group)
        return group

    def reject(self, group_id: str, *, reason: str) -> CalibrationRunGroup:
        group = self.get(group_id)
        if group.status == "approved":
            raise RunGroupStateError(f"run group {group_id} is already approved; supersede it with a new run group instead of rejecting")
        group.status = "rejected"
        group.rejected_reason = reason.strip() or "rejected"
        group.updated_at = now()
        self._save(group)
        return group

    def verify_bundle_integrity(self, group_id: str) -> bool:
        """Recomputes the provenance bundle hash from the stored members and
        confirms it still matches the hash recorded at approval time. This is
        the reproducibility check: an approved calibration is only trusted if
        its dataset/code/model/config hashes are exactly what was approved."""
        group = self.get(group_id)
        if group.status != "approved" or group.bundle_hash is None:
            raise RunGroupStateError(f"run group {group_id} is {group.status}, not approved")
        return _bundle_hash(group.id, group.members) == group.bundle_hash
