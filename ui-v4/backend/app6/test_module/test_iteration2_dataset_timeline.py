from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from app6.api.dataset_inventory import CORE_ARTIFACTS, inventory_stage1, list_stage1_issues
from app6.api.research_timeline import build_merged_timeline


class IterationTwoDatasetTests(unittest.TestCase):
    def _write_stage1(self, root: Path) -> None:
        root.mkdir(parents=True)
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
                "pose_bin": "frontal",
                "combined_visible_fraction": ".8",
                "yaw": "1",
                "pitch": "0",
                "roll": "0",
                "date_provenance_status": "conflict",
                "near_duplicate_of": "1999_01_01__a",
            },
            {
                "photo_id": "2001_01_01__c",
                "date": "2001-01-01",
                "pose_bin": "right_mid",
                "combined_visible_fraction": ".7",
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
        (root / rows[-1]["photo_id"] / "validation.json").unlink()

    def _write_stage2(self, root: Path) -> None:
        root.mkdir(parents=True)
        (root / "analysis_manifest.json").write_text(
            json.dumps({"schema_version": "test"}), encoding="utf-8"
        )
        fields = [
            "photo_a", "photo_b", "date_a", "date_b", "pose_bin",
            "status", "evidence_state", "p95_point_z",
        ]
        with (root / "pair_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "photo_a": "1999_01_01__a",
                    "photo_b": "2000_01_01__b",
                    "date_a": "1999-01-01",
                    "date_b": "2000-01-01",
                    "pose_bin": "frontal",
                    "status": "ok",
                    "evidence_state": "within_noise",
                    "p95_point_z": "1.2",
                }
            )

    def test_inventory_counts_years_provenance_and_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage1 = Path(tmp) / "stage1"
            self._write_stage1(stage1)
            result = inventory_stage1(stage1)
            self.assertEqual(result["year_counts"], {"1999": 1, "2000": 1, "2001": 1})
            self.assertEqual(result["provenance"]["date_conflict_count"], 1)
            self.assertEqual(result["provenance"]["near_duplicate_count"], 1)
            self.assertEqual(result["incomplete_record_count"], 1)

    def test_issue_register_is_paginated_and_filterable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage1 = Path(tmp) / "stage1"
            self._write_stage1(stage1)
            all_issues = list_stage1_issues(stage1, offset=0, limit=100)
            self.assertGreaterEqual(all_issues["total"], 3)
            self.assertEqual(all_issues["category_counts"]["date_provenance_conflict"], 1)
            filtered = list_stage1_issues(stage1, offset=0, limit=10, category="missing_artifact")
            self.assertEqual(filtered["total"], 1)
            self.assertEqual(filtered["issues"][0]["detail"], "validation.json")

    def test_merged_timeline_never_drops_unpaired_stage1_photo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage1, stage2 = root / "stage1", root / "stage2"
            self._write_stage1(stage1)
            self._write_stage2(stage2)
            result = build_merged_timeline(stage1, stage2)
            self.assertEqual(len(result["photos"]), 3)
            rows = {row["id"]: row for row in result["photos"]}
            self.assertEqual(rows["2001_01_01__c"]["measurementStatus"], "not_compared")
            self.assertEqual(result["stage2_compared_photo_count"], 2)
            self.assertEqual(result["stage2_orphan_photo_ids"], [])


if __name__ == "__main__":
    unittest.main()
