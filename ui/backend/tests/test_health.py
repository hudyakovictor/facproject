from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import yaml

from dpo.health import collect_health
from dpo.settings import ProjectSettings
from dpo.storage import StorageManager


class HealthTests(unittest.TestCase):
    def test_health_aggregates_app_storage_datasets_and_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ui = root / "ui"
            config_dir = ui / "config"
            config_dir.mkdir(parents=True)
            app6 = root / "app6"
            app6.mkdir()
            (app6 / "module.py").write_text("def x():\n    return 1\n", encoding="utf-8")
            volume = root / "SDCARD"
            main = volume / "photo" / "main"
            calibration = volume / "calibration"
            (calibration / "photos" / "person_01").mkdir(parents=True)
            main.mkdir(parents=True)
            (main / "a.jpg").write_bytes(b"a")
            (calibration / "photos" / "person_01" / "c.jpg").write_bytes(b"c")
            config = config_dir / "project.yaml"
            config.write_text(yaml.safe_dump({
                "project": {"app6_root": "../app6"},
                "storage": {
                    "control_root": ".data", "heavy_root": str(volume / "uidata"),
                    "required_volume": {"mount_path": str(volume), "allow_local_fallback": False, "verify_volume_identity": True},
                    "heavy_directories": ["runs", "stage1", "artifacts"],
                },
                "datasets": {"main": {"root": str(main)}, "calibration": {"root": str(calibration), "photos_subdir": "photos"}},
            }), encoding="utf-8")
            settings = ProjectSettings.load(config)
            StorageManager(settings.storage, protected_roots=(settings.app6_root, settings.datasets.main_root)).initialize("health-volume")
            app6_before = sorted((p.relative_to(app6).as_posix(), p.read_bytes()) for p in app6.rglob("*") if p.is_file())
            result = collect_health(settings).to_dict()
            app6_after = sorted((p.relative_to(app6).as_posix(), p.read_bytes()) for p in app6.rglob("*") if p.is_file())
            self.assertEqual(result["status"], "ready")
            self.assertTrue(result["storage"]["ready"])
            self.assertEqual(result["datasets"]["main"]["file_count"], 1)
            self.assertEqual(result["datasets"]["calibration"]["file_count"], 1)
            self.assertEqual(result["database"]["schema_version"], 2)
            self.assertGreaterEqual(result["database"]["storage_checks"], 1)
            self.assertEqual(app6_after, app6_before, "health collection must not write into app6")


if __name__ == "__main__":
    unittest.main()
