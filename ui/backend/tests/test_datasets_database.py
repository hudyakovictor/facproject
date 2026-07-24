from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from dpo.database import ControlDatabase, SCHEMA_VERSION
from dpo.datasets import DatasetRegistry, TrustClass, classify_field
from dpo.settings import DatasetSettings


class DatasetDatabaseTests(unittest.TestCase):
    def test_coordinate_fields_are_never_trusted(self) -> None:
        for field in ("x", "y", "z", "landmark_0_x", "keypoint_left_y", "mesh_vertex_3"):
            self.assertEqual(classify_field(field), TrustClass.IGNORED_INVALID_COORDINATE)
        self.assertEqual(classify_field("yaw"), TrustClass.TRUSTED_POSE_ANGLE)
        self.assertEqual(classify_field("main_photo_id"), TrustClass.TRUSTED_PAIR_BINDING)
        self.assertEqual(classify_field("pose_bin"), TrustClass.RECOMPUTE_FROM_PHOTO)

    def test_calibration_parser_keeps_only_pairs_angles_and_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photos = root / "photos" / "person_01"
            photos.mkdir(parents=True)
            (photos / "frame.jpg").write_bytes(b"jpeg-placeholder")
            table = root / "all_calibration_index.csv"
            fields = ["main_photo_id", "calibration_photo_id", "dataset_id", "yaw", "pitch", "roll", "x", "landmark_1_y", "pose_bin", "mystery"]
            with table.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "main_photo_id": "main-1", "calibration_photo_id": "cal-1", "dataset_id": "person_01",
                    "yaw": "12.5", "pitch": "-1", "roll": "0.5", "x": "999", "landmark_1_y": "888",
                    "pose_bin": "wrong-bin", "mystery": "unreviewed",
                })
            settings = DatasetSettings(root, root, "photos", ("all_calibration_index.csv",), 7)
            registry = DatasetRegistry(settings)
            report = registry.parse_calibration_table(table)
            self.assertEqual(report.row_count, 1)
            clean = report.trusted_rows[0]
            self.assertEqual(clean["main_photo_id"], "main-1")
            self.assertEqual(clean["yaw"], 12.5)
            self.assertNotIn("x", clean)
            self.assertNotIn("landmark_1_y", clean)
            self.assertNotIn("pose_bin", clean)
            self.assertNotIn("mystery", clean)
            self.assertIn("pose_bin", report.ignored_fields)
            self.assertIn("mystery", report.review_fields)

    def test_photo_registry_does_not_copy_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photos = root / "main"
            photos.mkdir()
            (photos / "a.jpg").write_bytes(b"a")
            (photos / "b.png").write_bytes(b"bb")
            (photos / "ignored.txt").write_text("x", encoding="utf-8")
            settings = DatasetSettings(photos, None, "photos", ("all_calibration_index.csv",), 7)
            result = DatasetRegistry(settings).inspect_photos(photos, "main")
            self.assertTrue(result.available)
            self.assertEqual(result.file_count, 2)
            self.assertEqual(result.total_bytes, 3)
            self.assertIsNotNone(result.fingerprint)
            self.assertEqual(sorted(p.name for p in photos.iterdir()), ["a.jpg", "b.png", "ignored.txt"])

    def test_sqlite_wal_migration_and_compact_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = ControlDatabase(Path(tmp) / "control" / "studio.sqlite")
            self.assertEqual(db.migrate(), SCHEMA_VERSION)
            db.record_storage({"state": "ready", "ready": True, "free_bytes": 123, "reasons": []})
            db.upsert_dataset("main", {"root": "/photos", "available": True, "file_count": 2, "total_bytes": 3, "fingerprint": "abc", "reasons": []})
            counts = db.counts()
            self.assertEqual(counts["storage_checks"], 1)
            self.assertEqual(counts["datasets"], 1)
            self.assertEqual(counts["projects"], 0)
            self.assertEqual(counts["modules"], 0)
            self.assertEqual(counts["functions"], 0)
            self.assertEqual(counts["runs"], 0)
            self.assertEqual(counts["events"], 0)
            conn = db.connect()
            try:
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(str(mode).lower(), "wal")


if __name__ == "__main__":
    unittest.main()
