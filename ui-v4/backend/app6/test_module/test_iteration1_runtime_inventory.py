from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app6.api.dataset_inventory import CORE_ARTIFACTS, build_dataset_inventory, inventory_stage1
from app6.api.runtime_config import (
    load_runtime_paths,
    runtime_path_report,
    save_active_dataset_registration,
)


def _write_stage1(root: Path, *, missing_validation: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    fields = [
        "photo_id", "date", "pose_bin", "combined_visible_fraction",
        "yaw", "pitch", "roll", "date_provenance_status", "near_duplicate_of",
    ]
    rows = [
        {
            "photo_id": "1999_01_01__a",
            "date": "1999-01-01",
            "pose_bin": "frontal",
            "combined_visible_fraction": ".9",
            "yaw": "0",
            "pitch": "0",
            "roll": "0",
            "date_provenance_status": "verified",
            "near_duplicate_of": "",
        },
        {
            "photo_id": "2000_01_01__b",
            "date": "2000-01-01",
            "pose_bin": "right_mid",
            "combined_visible_fraction": ".8",
            "yaw": "30",
            "pitch": "0",
            "roll": "0",
            "date_provenance_status": "verified",
            "near_duplicate_of": "",
        },
    ]
    with (root / "main_timeline.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (root / "stage1_manifest.json").write_text('{"schema":"stage1-test"}', encoding="utf-8")
    for row in rows:
        folder = root / row["photo_id"]
        folder.mkdir()
        for name in CORE_ARTIFACTS:
            if name == "original.jpg":
                (folder / "original.jpg").write_bytes(b"img")
            else:
                (folder / name).write_bytes(b"test")
        if missing_validation and row["photo_id"].endswith("__b"):
            (folder / "validation.json").unlink()


def _write_calibration(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    fields = ["dataset_id", "record_id", "pose_bin", "yaw", "pitch", "roll", "source_filename"]
    poses = [
        "left_profile", "left_deep", "left_mid", "left_light", "frontal",
        "right_light", "right_mid", "right_deep", "right_profile",
    ]
    rows = []
    for person_i in range(1, 8):
        person = f"person_{person_i:02d}"
        (root / person).mkdir(exist_ok=True)
        for pose in poses:
            rows.append(
                {
                    "dataset_id": person,
                    "record_id": f"{person}_{pose}",
                    "pose_bin": pose,
                    "yaw": "0",
                    "pitch": "0",
                    "roll": "0",
                    "source_filename": f"{person}_{pose}.jpg",
                }
            )
    with (root / "all_calibration_index.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (root / "calibration_manifest.json").write_text('{"schema":"cal-test"}', encoding="utf-8")


class IterationOneRuntimeTests(unittest.TestCase):
    def test_documented_defaults_are_resolved_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = Path(tmp) / "storage"
            calibration = Path(tmp) / "calibration"
            env = {
                "DEEPUTIN_STORAGE_ROOT": str(storage),
                "DEEPUTIN_CALIBRATION_ROOT": str(calibration),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                paths = load_runtime_paths()
                report = runtime_path_report(paths)
            self.assertEqual(paths.stage1_root, storage / "stage1")
            self.assertEqual(paths.calibration_root, calibration)
            self.assertEqual(paths.settings_path, storage / "registry" / "api_settings.json")
            self.assertFalse(paths.stage1_root.exists())
            self.assertFalse(paths.registry_root.exists())
            self.assertFalse(report["status"]["stage1_ready"])

    def test_storage_override_moves_stage_roots_but_not_calibration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = Path(tmp) / "storage"
            calibration = Path(tmp) / "calibration_fixed"
            env = {
                "DEEPUTIN_STORAGE_ROOT": str(storage),
                "DEEPUTIN_CALIBRATION_ROOT": str(calibration),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                paths = load_runtime_paths()
            self.assertEqual(paths.stage2_root, storage / "stage2")
            self.assertEqual(paths.stage3_root, storage / "stage3")
            self.assertEqual(paths.calibration_root, calibration)

    def test_registration_is_atomic_and_outside_stage1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = Path(tmp) / "storage"
            stage1 = storage / "stage1"
            stage1.mkdir(parents=True)
            env = {
                "DEEPUTIN_STORAGE_ROOT": str(storage),
                "DEEPUTIN_CALIBRATION_ROOT": str(Path(tmp) / "calibration"),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                path = save_active_dataset_registration({"schema": "test", "ok": True})
                payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(path, storage / "registry" / "active_dataset.json")
            self.assertTrue(payload["ok"])
            self.assertEqual(list(stage1.iterdir()), [])


class IterationOneInventoryTests(unittest.TestCase):
    def test_complete_inventory_is_ready_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage1 = Path(tmp) / "stage1"
            calibration = Path(tmp) / "calibration"
            _write_stage1(stage1)
            _write_calibration(calibration)
            env = {
                "DEEPUTIN_STORAGE_ROOT": str(Path(tmp) / "storage"),
                "DEEPUTIN_STAGE1_ROOT": str(stage1),
                "DEEPUTIN_CALIBRATION_ROOT": str(calibration),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                result = build_dataset_inventory()
            self.assertEqual(result["status"], "ready")
            self.assertTrue(result["stage1"]["read_only"])
            self.assertEqual(result["stage1"]["record_count"], 2)
            self.assertEqual(result["calibration"]["person_count"], 7)
            self.assertEqual(result["stage1"]["pose_counts"]["frontal"], 1)

    def test_missing_artifact_is_explicitly_limited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage1 = Path(tmp) / "stage1"
            _write_stage1(stage1, missing_validation=True)
            result = inventory_stage1(stage1)
            self.assertEqual(result["status"], "limited")
            self.assertEqual(result["incomplete_record_count"], 1)
            self.assertGreaterEqual(result["issue_counts"].get("missing:validation.json", 0), 1)


if __name__ == "__main__":
    unittest.main()
