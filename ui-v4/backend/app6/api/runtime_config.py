"""Canonical runtime path configuration for the interactive workstation.

The extracted Stage 1 and calibration trees are evidence inputs and are treated
as read-only by this module. Runtime metadata is stored separately under
``<storage>/registry``. Environment variables remain available for portable
and test deployments, while the documented removable-disk layout works without
additional configuration on the investigator workstation.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RUNTIME_PATHS_SCHEMA = "deeputin-runtime-paths-v1.0"
DEFAULT_STORAGE_ROOT = Path("/Volumes/SDCARD/storage")
DEFAULT_CALIBRATION_ROOT = Path("/Volumes/SDCARD/calibration")


@dataclass(frozen=True)
class RuntimePaths:
    storage_root: Path
    stage1_root: Path
    stage2_root: Path
    stage3_root: Path
    calibration_root: Path
    uploads_root: Path
    registry_root: Path
    settings_path: Path

    def json_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def _path_from_env(name: str, fallback: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else fallback


def load_runtime_paths() -> RuntimePaths:
    """Resolve all runtime paths from one deterministic policy.

    Per-component environment overrides take precedence over the storage root.
    No directory is created here, so a read/health request never mutates an
    evidence disk merely by inspecting it.
    """
    storage = _path_from_env("DEEPUTIN_STORAGE_ROOT", DEFAULT_STORAGE_ROOT)
    calibration = _path_from_env("DEEPUTIN_CALIBRATION_ROOT", DEFAULT_CALIBRATION_ROOT)
    registry = _path_from_env("DEEPUTIN_REGISTRY_ROOT", storage / "registry")
    return RuntimePaths(
        storage_root=storage,
        stage1_root=_path_from_env("DEEPUTIN_STAGE1_ROOT", storage / "stage1"),
        stage2_root=_path_from_env("DEEPUTIN_STAGE2_ROOT", storage / "stage2"),
        stage3_root=_path_from_env("DEEPUTIN_STAGE3_ROOT", storage / "stage3"),
        calibration_root=calibration,
        uploads_root=_path_from_env("DEEPUTIN_UPLOADS_ROOT", storage / "api_uploads"),
        registry_root=registry,
        settings_path=_path_from_env("DEEPUTIN_SETTINGS_PATH", registry / "api_settings.json"),
    )


def ensure_runtime_write_dirs(paths: RuntimePaths) -> None:
    """Create only mutable runtime directories, never Stage 1/calibration."""
    paths.registry_root.mkdir(parents=True, exist_ok=True)
    paths.uploads_root.mkdir(parents=True, exist_ok=True)


def runtime_path_report(paths: RuntimePaths | None = None) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    stage1_ready = (current.stage1_root / "main_timeline.csv").is_file()
    calibration_ready = (current.calibration_root / "all_calibration_index.csv").is_file()
    return {
        "schema": RUNTIME_PATHS_SCHEMA,
        "paths": current.json_dict(),
        "status": {
            "storage_present": current.storage_root.is_dir(),
            "stage1_present": current.stage1_root.is_dir(),
            "stage1_ready": stage1_ready,
            "stage2_present": current.stage2_root.is_dir(),
            "stage3_present": current.stage3_root.is_dir(),
            "calibration_present": current.calibration_root.is_dir(),
            "calibration_ready": calibration_ready,
            "registry_present": current.registry_root.is_dir(),
        },
        "read_only_inputs": [str(current.stage1_root), str(current.calibration_root)],
        "not_a_verdict": True,
    }


def stage1_integrity_snapshot(paths: RuntimePaths | None = None) -> dict[str, Any]:
    """Content hash of the immutable Stage 1 evidence (baseline + current).

    The snapshot is stored in the registry on first call and re-computed on
    every call; any difference means Stage 1 was modified (a violation of the
    evidence contract). Stage 1 itself is never written by this function.
    """
    import hashlib as _hashlib

    current = paths or load_runtime_paths()
    stage1 = current.stage1_root
    timeline = stage1 / "main_timeline.csv"

    def _sha(path: Path) -> str:
        if not path.is_file():
            return "missing"
        digest = _hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    timeline_digest = _sha(timeline)
    photo_dirs = sorted(
        item.name for item in stage1.iterdir() if item.is_dir() and (item / "info.json").is_file()
    ) if stage1.is_dir() else []
    manifest_digest = _sha(stage1 / "stage1_manifest.json")
    # dataset hash is path-independent (ordered photo ids + timeline content)
    dataset_hash = _hashlib.sha256()
    dataset_hash.update(timeline_digest.encode())
    for name in photo_dirs:
        dataset_hash.update(name.encode())
    dataset_hash.update(manifest_digest.encode())

    current_snapshot = {
        "schema": "deeputin-stage1-integrity-v1.0",
        "stage1_root": str(stage1),
        "timeline_sha256": timeline_digest,
        "manifest_sha256": manifest_digest,
        "photo_count": len(photo_dirs),
        "dataset_hash": dataset_hash.hexdigest(),
    }

    current.registry_root.mkdir(parents=True, exist_ok=True)
    baseline_path = current.registry_root / "stage1_integrity_baseline.json"
    if baseline_path.is_file():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            baseline = None
    else:
        baseline = None

    if baseline is None:
        # first sighting: store the current snapshot as the immutable baseline
        baseline = current_snapshot
        temporary = baseline_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(baseline_path)

    unchanged = bool(
        baseline.get("dataset_hash") == current_snapshot["dataset_hash"]
        and baseline.get("timeline_sha256") == current_snapshot["timeline_sha256"]
        and baseline.get("photo_count") == current_snapshot["photo_count"]
    )
    return {
        "schema": "deeputin-stage1-integrity-v1.0",
        "unchanged": unchanged,
        "baseline": baseline,
        "current": current_snapshot,
        "note": "Stage 1 evidence is immutable; any change invalidates rollback guarantees.",
    }


def save_active_dataset_registration(
    payload: dict[str, Any], paths: RuntimePaths | None = None
) -> Path:
    """Persist active dataset metadata outside the immutable Stage 1 tree."""
    current = paths or load_runtime_paths()
    current.registry_root.mkdir(parents=True, exist_ok=True)
    destination = current.registry_root / "active_dataset.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_active_dataset_registration(paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    current = paths or load_runtime_paths()
    destination = current.registry_root / "active_dataset.json"
    if not destination.is_file():
        return None
    try:
        value = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
