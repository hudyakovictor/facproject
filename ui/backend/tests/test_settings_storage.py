from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import yaml

from dpo.settings import ProjectSettings, SettingsError
from dpo.storage import StorageManager, StorageState, StorageUnavailable


class ProjectFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.ui = root / "ui"
        self.config_dir = self.ui / "config"
        self.app6 = root / "app6"
        self.volume = root / "SDCARD"
        self.heavy = self.volume / "uidata"
        self.main = self.volume / "photo" / "main"
        self.calibration = self.volume / "photo" / "calibration"
        for path in (self.config_dir, self.app6, self.volume, self.main, self.calibration / "photos"):
            path.mkdir(parents=True, exist_ok=True)
        self.config = self.config_dir / "project.yaml"
        self.write()

    def write(self, *, allow_fallback: bool = False, heavy: Path | None = None) -> None:
        payload = {
            "project": {"app6_root": "../app6"},
            "storage": {
                "control_root": ".data",
                "heavy_root": str(heavy or self.heavy),
                "required_volume": {
                    "mount_path": str(self.volume),
                    "allow_local_fallback": allow_fallback,
                    "verify_volume_identity": True,
                    "verify_writable": True,
                    "verify_free_space": True,
                },
                "heavy_directories": ["runs", "stage1", "artifacts", "backups", "trash"],
            },
            "datasets": {
                "main": {"root": str(self.main)},
                "calibration": {
                    "root": "${DPO_CALIBRATION_ROOT}",
                    "photos_subdir": "photos",
                    "expected_people": 7,
                    "index_candidates": ["all_calibration_index.csv"],
                },
            },
        }
        self.config.write_text(yaml.safe_dump(payload), encoding="utf-8")

    def settings(self) -> ProjectSettings:
        return ProjectSettings.load(self.config, env={"DPO_CALIBRATION_ROOT": str(self.calibration)})


class SettingsStorageTests(unittest.TestCase):
    def test_relative_app6_and_control_paths_resolve_from_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = ProjectFixture(Path(tmp))
            settings = fx.settings()
            self.assertEqual(settings.app6_root, fx.app6.resolve())
            self.assertEqual(settings.storage.control_root, (fx.ui / ".data").resolve())

    def test_missing_optional_calibration_path_does_not_guess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = ProjectFixture(Path(tmp))
            settings = ProjectSettings.load(fx.config, env={})
            self.assertIsNone(settings.datasets.calibration_root)

    def test_local_fallback_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = ProjectFixture(Path(tmp))
            fx.write(allow_fallback=True)
            with self.assertRaises(SettingsError):
                fx.settings()

    def test_heavy_root_overlap_with_main_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = ProjectFixture(Path(tmp))
            fx.write(heavy=fx.main / "outputs")
            with self.assertRaises(SettingsError):
                fx.settings()

    def test_storage_initialization_and_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = ProjectFixture(Path(tmp))
            settings = fx.settings()
            manager = StorageManager(settings.storage, protected_roots=(settings.app6_root, settings.datasets.main_root))
            before = manager.check()
            self.assertEqual(before.state, StorageState.HEAVY_ROOT_MISSING)
            health = manager.initialize("test-volume-001")
            self.assertTrue(health.ready)
            for name in settings.storage.heavy_directories:
                self.assertTrue((settings.storage.heavy_root / name).is_dir())
            run = manager.run_directory("run-001")
            self.assertTrue(run.is_dir())
            with self.assertRaises(ValueError):
                manager.run_directory("../unsafe")

    def test_wrong_volume_identity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = ProjectFixture(Path(tmp))
            settings = fx.settings()
            manager = StorageManager(settings.storage)
            manager.initialize("expected")
            marker = settings.storage.control_root / "expected-volume.json"
            marker.write_text(json.dumps({"volume_identity": "different"}), encoding="utf-8")
            health = StorageManager(settings.storage).check()
            self.assertEqual(health.state, StorageState.WRONG_VOLUME)
            self.assertFalse(health.ready)
            with self.assertRaises(StorageUnavailable):
                StorageManager(settings.storage).require_ready()

    def test_required_bytes_can_fail_for_low_space(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = ProjectFixture(Path(tmp))
            settings = fx.settings()
            manager = StorageManager(settings.storage)
            manager.initialize("low-space-test")
            health = StorageManager(settings.storage).check(required_bytes=10**30)
            self.assertEqual(health.state, StorageState.LOW_SPACE)
            self.assertFalse(health.ready)

    def test_disconnect_after_ready_becomes_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = ProjectFixture(Path(tmp))
            settings = fx.settings()
            manager = StorageManager(settings.storage)
            manager.initialize("disconnect-test")
            moved = fx.root / "removed-volume"
            fx.volume.rename(moved)
            health = manager.check()
            self.assertEqual(health.state, StorageState.STORAGE_INTERRUPTED)
            self.assertFalse(health.ready)


if __name__ == "__main__":
    unittest.main()
