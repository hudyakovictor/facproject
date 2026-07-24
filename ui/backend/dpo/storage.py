"""External-volume storage manager. Heavy runs fail closed."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable

from .settings import StorageSettings


class StorageState(StrEnum):
    READY = "ready"
    VOLUME_MISSING = "volume_missing"
    HEAVY_ROOT_MISSING = "heavy_root_missing"
    WRONG_VOLUME = "wrong_volume"
    NOT_WRITABLE = "not_writable"
    LOW_SPACE = "low_space"
    UNSAFE_PATH = "unsafe_path"
    STORAGE_INTERRUPTED = "storage_interrupted"


class StorageUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class StorageHealth:
    state: StorageState
    ready: bool
    mount_path: str
    heavy_root: str
    free_bytes: int | None
    volume_identity: str | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        data["reasons"] = list(self.reasons)
        return data


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


class StorageManager:
    MARKER = ".dpo-volume-id"

    def __init__(self, settings: StorageSettings, *, protected_roots: Iterable[Path] = ()) -> None:
        self.settings = settings
        self.protected_roots = tuple(Path(x).resolve(strict=False) for x in protected_roots)
        self._last_ready = False

    def _identity(self) -> str | None:
        marker = self.settings.mount_path / self.MARKER
        try:
            value = marker.read_text(encoding="utf-8").strip()
            return value or None
        except OSError:
            return None

    def check(self, *, required_bytes: int = 0, probe_write: bool = False) -> StorageHealth:
        s = self.settings
        reasons: list[str] = []
        state = StorageState.READY
        free: int | None = None

        if not s.mount_path.is_dir():
            state = StorageState.VOLUME_MISSING
            reasons.append("required removable volume is not mounted")
        elif not _inside(s.heavy_root, s.mount_path):
            state = StorageState.UNSAFE_PATH
            reasons.append("heavy_root is outside the required volume")
        elif any(_inside(s.heavy_root, root) or _inside(root, s.heavy_root) for root in self.protected_roots):
            state = StorageState.UNSAFE_PATH
            reasons.append("heavy_root overlaps a protected source/dataset root")
        elif not s.heavy_root.is_dir():
            state = StorageState.HEAVY_ROOT_MISSING
            reasons.append("heavy_root has not been initialized")
        else:
            try:
                free = shutil.disk_usage(s.heavy_root).free
            except OSError as exc:
                state = StorageState.STORAGE_INTERRUPTED
                reasons.append(f"cannot read disk usage: {exc}")
            needed = max(int(required_bytes), int(s.minimum_free_bytes))
            if state == StorageState.READY and s.verify_free_space and free is not None and free < needed:
                state = StorageState.LOW_SPACE
                reasons.append(f"free space {free} is below required {needed}")
            if state == StorageState.READY and s.verify_writable:
                writable = os.access(s.heavy_root, os.W_OK)
                if writable and probe_write:
                    try:
                        fd, name = tempfile.mkstemp(prefix=".dpo-write-probe-", dir=s.heavy_root)
                        os.close(fd)
                        Path(name).unlink(missing_ok=True)
                    except OSError:
                        writable = False
                if not writable:
                    state = StorageState.NOT_WRITABLE
                    reasons.append("heavy_root is not writable")

        identity = self._identity() if s.mount_path.is_dir() else None
        expected_marker = s.control_root / "expected-volume.json"
        if state == StorageState.READY and s.verify_volume_identity and expected_marker.is_file():
            try:
                expected = json.loads(expected_marker.read_text(encoding="utf-8")).get("volume_identity")
            except (OSError, ValueError, AttributeError):
                expected = None
            if expected and identity != expected:
                state = StorageState.WRONG_VOLUME
                reasons.append("mounted volume identity does not match the registered volume")

        ready = state == StorageState.READY
        if self._last_ready and not ready and state not in {StorageState.LOW_SPACE, StorageState.NOT_WRITABLE}:
            state = StorageState.STORAGE_INTERRUPTED
            reasons.insert(0, "storage became unavailable after being ready")
        self._last_ready = ready
        return StorageHealth(state, ready, str(s.mount_path), str(s.heavy_root), free, identity, tuple(reasons))

    def initialize(self, volume_identity: str) -> StorageHealth:
        s = self.settings
        if not s.mount_path.is_dir():
            raise StorageUnavailable("required removable volume is not mounted")
        if not _inside(s.heavy_root, s.mount_path):
            raise StorageUnavailable("heavy_root is outside required volume")
        if any(_inside(s.heavy_root, root) or _inside(root, s.heavy_root) for root in self.protected_roots):
            raise StorageUnavailable("heavy_root overlaps protected source/dataset root")
        s.heavy_root.mkdir(parents=True, exist_ok=True)
        for name in s.heavy_directories:
            (s.heavy_root / name).mkdir(exist_ok=True)
        s.control_root.mkdir(parents=True, exist_ok=True)
        marker = s.mount_path / self.MARKER
        if marker.exists() and marker.read_text(encoding="utf-8").strip() != volume_identity:
            raise StorageUnavailable("volume already has a different identity")
        marker.write_text(volume_identity + "\n", encoding="utf-8")
        (s.control_root / "expected-volume.json").write_text(
            json.dumps({"volume_identity": volume_identity}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        health = self.check(probe_write=True)
        if not health.ready:
            raise StorageUnavailable("storage initialization failed: " + "; ".join(health.reasons))
        return health

    def require_ready(self, *, required_bytes: int = 0) -> StorageHealth:
        health = self.check(required_bytes=required_bytes, probe_write=True)
        if not health.ready:
            raise StorageUnavailable(f"{health.state.value}: {'; '.join(health.reasons)}")
        return health

    def run_directory(self, run_id: str) -> Path:
        if not run_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in run_id):
            raise ValueError("run_id may contain only letters, digits, dash and underscore")
        self.require_ready()
        path = self.settings.heavy_root / "runs" / run_id
        path.mkdir(parents=True, exist_ok=False)
        return path
