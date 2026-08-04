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
