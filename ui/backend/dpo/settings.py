"""Fail-closed project settings with no writes to app6 or dataset roots."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any, Mapping

import yaml

_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class SettingsError(ValueError):
    """Configuration is missing, malformed, or violates path boundaries."""


def _expand(value: str, env: Mapping[str, str], *, required: bool = True) -> str | None:
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in env or not env[key].strip():
            missing.append(key)
            return ""
        return env[key]

    expanded = _ENV.sub(replace, value)
    if missing:
        if required:
            raise SettingsError(f"environment variables are not set: {', '.join(sorted(missing))}")
        return None
    return os.path.expanduser(expanded)


def _path(value: str, base: Path, env: Mapping[str, str], *, required: bool = True) -> Path | None:
    expanded = _expand(value, env, required=required)
    if expanded is None:
        return None
    candidate = Path(expanded)
    return (candidate if candidate.is_absolute() else base / candidate).resolve(strict=False)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class StorageSettings:
    control_root: Path
    heavy_root: Path
    mount_path: Path
    allow_local_fallback: bool
    verify_volume_identity: bool
    verify_writable: bool
    verify_free_space: bool
    minimum_free_bytes: int
    heavy_directories: tuple[str, ...]


@dataclass(frozen=True)
class DatasetSettings:
    main_root: Path
    calibration_root: Path | None
    calibration_photos_subdir: str
    calibration_index_candidates: tuple[str, ...]
    expected_people: int


@dataclass(frozen=True)
class ProjectSettings:
    config_path: Path
    project_root: Path
    app6_root: Path
    storage: StorageSettings
    datasets: DatasetSettings

    @classmethod
    def load(
        cls,
        config_path: str | Path,
        *,
        env: Mapping[str, str] | None = None,
    ) -> "ProjectSettings":
        path = Path(config_path).resolve(strict=True)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise SettingsError("project config must be a YAML mapping")
        environment = dict(os.environ if env is None else env)
        # Relative paths in ui/config/*.yaml are resolved from the ui directory.
        ui_root = path.parent.parent.resolve(strict=False)
        project_root = ui_root.parent.resolve(strict=False)
        project = raw.get("project") or {}
        storage = raw.get("storage") or {}
        datasets = raw.get("datasets") or {}
        required_volume = storage.get("required_volume") or {}
        main = datasets.get("main") or {}
        calibration = datasets.get("calibration") or {}

        app6_root = _path(str(project.get("app6_root", "../app6")), ui_root, environment)
        control_root = _path(str(storage.get("control_root", ".data")), ui_root, environment)
        heavy_root = _path(str(storage.get("heavy_root", "/Volumes/SDCARD/uidata")), ui_root, environment)
        mount_path = _path(str(required_volume.get("mount_path", "/Volumes/SDCARD")), ui_root, environment)
        main_root = _path(str(main.get("root", "/Volumes/SDCARD/photo/main")), ui_root, environment)
        calibration_raw = str(calibration.get("root", "${DPO_CALIBRATION_ROOT}"))
        calibration_root = _path(calibration_raw, ui_root, environment, required=False)
        assert app6_root and control_root and heavy_root and mount_path and main_root

        if _inside(control_root, app6_root):
            raise SettingsError("control_root must not be inside app6")
        if _inside(heavy_root, app6_root):
            raise SettingsError("heavy_root must not be inside app6")
        if _inside(heavy_root, main_root) or _inside(main_root, heavy_root):
            raise SettingsError("heavy_root and main dataset root must not contain each other")
        if bool(required_volume.get("allow_local_fallback", False)):
            raise SettingsError("local heavy-data fallback is forbidden")

        directory_names = tuple(str(x) for x in storage.get("heavy_directories", ()))
        if not directory_names:
            directory_names = ("runs", "stage1", "stage2", "stage2b", "stage3", "test-cache", "scenarios", "calibration", "artifacts", "previews", "backups", "trash")
        for name in directory_names:
            if not name or name in {".", ".."} or Path(name).is_absolute() or len(Path(name).parts) != 1:
                raise SettingsError(f"unsafe heavy directory name: {name!r}")

        indexes = tuple(str(x) for x in calibration.get("index_candidates", ("all_calibration_index.csv",)))
        return cls(
            config_path=path,
            project_root=project_root,
            app6_root=app6_root,
            storage=StorageSettings(
                control_root=control_root,
                heavy_root=heavy_root,
                mount_path=mount_path,
                allow_local_fallback=False,
                verify_volume_identity=bool(required_volume.get("verify_volume_identity", True)),
                verify_writable=bool(required_volume.get("verify_writable", True)),
                verify_free_space=bool(required_volume.get("verify_free_space", True)),
                minimum_free_bytes=int(storage.get("minimum_free_bytes", 0)),
                heavy_directories=directory_names,
            ),
            datasets=DatasetSettings(
                main_root=main_root,
                calibration_root=calibration_root,
                calibration_photos_subdir=str(calibration.get("photos_subdir", "photos")),
                calibration_index_candidates=indexes,
                expected_people=int(calibration.get("expected_people", 7)),
            ),
        )
