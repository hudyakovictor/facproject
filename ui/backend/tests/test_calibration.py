from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from dpo.calibration import (
    CalibrationRegistry,
    ForbiddenFieldError,
    HashMismatchError,
    RunGroupStateError,
    RunHashes,
)
from dpo.datasets import DatasetRegistry, CalibrationTableReport
from dpo.settings import DatasetSettings


def _hashes(**overrides: str) -> RunHashes:
    base = {"dataset_hash": "d1", "code_hash": "c1", "model_hash": "m1", "config_hash": "g1"}
    base.update(overrides)
    return RunHashes(**base)


class CalibrationRunGroupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "calibration_runs"
        self.registry = CalibrationRegistry(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_matching_hashes_across_all_roles_become_candidate(self) -> None:
        group = self.registry.create("grp-1")
        self.assertEqual(group.status, "draft")
        self.registry.register_member("grp-1", "main_extraction", "run-a", _hashes())
        self.registry.register_member("grp-1", "calibration_extraction", "run-b", _hashes())
        self.registry.register_member("grp-1", "calibration_build", "run-c", _hashes())
        group = self.registry.register_member("grp-1", "main_analysis", "run-d", _hashes())
        self.assertEqual(group.status, "candidate")
        self.assertEqual(group.to_dict()["missing_roles"], [])

    def test_mismatched_code_hash_is_rejected_not_merged(self) -> None:
        self.registry.create("grp-2")
        self.registry.register_member("grp-2", "main_extraction", "run-a", _hashes())
        with self.assertRaises(HashMismatchError):
            self.registry.register_member("grp-2", "calibration_extraction", "run-b", _hashes(code_hash="c2"))
        # Rejected member must not have been merged into the group.
        group = self.registry.get("grp-2")
        self.assertEqual(set(group.members), {"main_extraction"})
        self.assertEqual(group.status, "draft")

    def test_mismatched_dataset_model_or_config_hash_is_also_rejected(self) -> None:
        for field in ("dataset_hash", "model_hash", "config_hash"):
            group_id = f"grp-{field}"
            self.registry.create(group_id)
            self.registry.register_member(group_id, "main_extraction", "run-a", _hashes())
            with self.assertRaises(HashMismatchError):
                self.registry.register_member(group_id, "calibration_extraction", "run-b", _hashes(**{field: "different"}))

    def test_unknown_role_is_rejected(self) -> None:
        self.registry.create("grp-3")
        with self.assertRaises(ValueError):
            self.registry.register_member("grp-3", "stage2b_extra", "run-a", _hashes())

    def test_finalized_run_group_cannot_be_modified(self) -> None:
        gid = "grp-4"
        self.registry.create(gid)
        for role, run_id in (
            ("main_extraction", "run-a"), ("calibration_extraction", "run-b"),
            ("calibration_build", "run-c"), ("main_analysis", "run-d"),
        ):
            self.registry.register_member(gid, role, run_id, _hashes())
        self.registry.approve(gid, approved_by="journalist")
        with self.assertRaises(RunGroupStateError):
            self.registry.register_member(gid, "main_extraction", "run-e", _hashes())

    def test_cannot_approve_before_all_roles_present(self) -> None:
        self.registry.create("grp-5")
        self.registry.register_member("grp-5", "main_extraction", "run-a", _hashes())
        with self.assertRaises(RunGroupStateError):
            self.registry.approve("grp-5", approved_by="journalist")

    def test_approve_sets_bundle_hash_and_verify_detects_tampering(self) -> None:
        gid = "grp-6"
        self.registry.create(gid)
        for role, run_id in (
            ("main_extraction", "run-a"), ("calibration_extraction", "run-b"),
            ("calibration_build", "run-c"), ("main_analysis", "run-d"),
        ):
            self.registry.register_member(gid, role, run_id, _hashes())
        approved = self.registry.approve(gid, approved_by="journalist")
        self.assertIsNotNone(approved.bundle_hash)
        self.assertTrue(self.registry.verify_bundle_integrity(gid))

        # Simulate tampering with the persisted file after approval.
        path = self.root / f"{gid}.json"
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        data["members"]["main_analysis"]["hashes"]["code_hash"] = "tampered"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertFalse(self.registry.verify_bundle_integrity(gid))

    def test_reject_is_blocked_once_approved(self) -> None:
        gid = "grp-7"
        self.registry.create(gid)
        for role, run_id in (
            ("main_extraction", "run-a"), ("calibration_extraction", "run-b"),
            ("calibration_build", "run-c"), ("main_analysis", "run-d"),
        ):
            self.registry.register_member(gid, role, run_id, _hashes())
        self.registry.approve(gid, approved_by="journalist")
        with self.assertRaises(RunGroupStateError):
            self.registry.reject(gid, reason="changed my mind")

    def test_attach_trusted_table_from_real_parser(self) -> None:
        gid = "grp-8"
        self.registry.create(gid)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            table = root / "all_calibration_index.csv"
            fields = ["main_photo_id", "calibration_photo_id", "yaw", "pitch", "roll", "x", "landmark_1_y"]
            with table.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerow({"main_photo_id": "main-1", "calibration_photo_id": "cal-1", "yaw": "1.0", "pitch": "2.0", "roll": "3.0", "x": "999", "landmark_1_y": "888"})
            settings = DatasetSettings(root, root, "photos", ("all_calibration_index.csv",), 7)
            report = DatasetRegistry(settings).parse_calibration_table(table)
            group = self.registry.attach_trusted_table(gid, report)
            self.assertIsNotNone(group.trusted_table)
            self.assertNotIn("x", group.trusted_table["trusted_rows"][0])
            self.assertNotIn("landmark_1_y", group.trusted_table["trusted_rows"][0])

    def test_attach_trusted_table_rejects_a_smuggled_coordinate_field(self) -> None:
        gid = "grp-9"
        self.registry.create(gid)
        # Even if some upstream classifier bug lets a coordinate field through,
        # attach_trusted_table must still refuse it (defense in depth).
        bad_report = CalibrationTableReport(
            path="synthetic", row_count=1,
            field_trust={"main_photo_id": "trusted_pair_binding", "landmark_3_x": "trusted_pose_angle"},
            trusted_rows=({"main_photo_id": "main-1", "landmark_3_x": "12.0"},),
            ignored_fields=(), review_fields=(),
        )
        with self.assertRaises(ForbiddenFieldError):
            self.registry.attach_trusted_table(gid, bad_report)

    def test_registry_never_writes_outside_its_own_root(self) -> None:
        gid = "grp-10"
        self.registry.create(gid)
        self.registry.register_member(gid, "main_extraction", "run-a", _hashes())
        for path in self.root.rglob("*"):
            self.assertTrue(str(path).startswith(str(self.root)))


if __name__ == "__main__":
    unittest.main()
