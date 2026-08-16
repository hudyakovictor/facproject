import csv
import json
import tempfile
import unittest
from pathlib import Path

from app6.api.research_timeline import build_research_timeline


class ResearchTimelineIntegrationTests(unittest.TestCase):
    def test_stage1_measurements_and_all_pair_states_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage1 = root / "stage1"
            stage2 = root / "stage2"
            stage1.mkdir()
            stage2.mkdir()

            with (stage1 / "main_timeline.csv").open("w", newline="", encoding="utf-8") as handle:
                fields = [
                    "photo_id", "date", "pose_bin", "yaw", "pitch", "roll",
                    "combined_visible_fraction", "date_provenance_status",
                ]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows([
                    {"photo_id": "a", "date": "2000-01-01", "pose_bin": "frontal", "yaw": 1, "pitch": 2, "roll": 3, "combined_visible_fraction": .8, "date_provenance_status": "filename_only"},
                    {"photo_id": "b", "date": "2000-01-02", "pose_bin": "frontal", "yaw": 4, "pitch": 5, "roll": 6, "combined_visible_fraction": .7, "date_provenance_status": "filename_only"},
                    {"photo_id": "c", "date": "2000-01-03", "pose_bin": "frontal", "yaw": 7, "pitch": 8, "roll": 9, "combined_visible_fraction": .6, "date_provenance_status": "filename_only"},
                ])

            (stage2 / "analysis_manifest.json").write_text("{}", encoding="utf-8")
            with (stage2 / "pair_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
                fields = [
                    "photo_a", "photo_b", "date_a", "date_b", "pose_bin", "status",
                    "evidence_state", "date_provenance_limited",
                    "date_provenance_status_a", "date_provenance_status_b",
                ]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows([
                    {"photo_a": "a", "photo_b": "b", "date_a": "2000-01-01", "date_b": "2000-01-02", "pose_bin": "frontal", "status": "coherent_jump_candidate", "evidence_state": "calibration_limited", "date_provenance_limited": "False", "date_provenance_status_a": "resolved_filename", "date_provenance_status_b": "resolved_filename"},
                    {"photo_a": "a", "photo_b": "c", "date_a": "2000-01-01", "date_b": "2000-01-03", "pose_bin": "frontal", "status": "residual_pose_mismatch", "evidence_state": "calibration_limited", "date_provenance_limited": "False", "date_provenance_status_a": "resolved_filename", "date_provenance_status_b": "resolved_filename"},
                ])

            payload = build_research_timeline(stage2, stage1)
            photos = {row["id"]: row for row in payload["photos"]}
            self.assertEqual(photos["a"]["yaw"], 1.0)
            self.assertEqual(photos["a"]["pitch"], 2.0)
            self.assertEqual(photos["a"]["roll"], 3.0)
            self.assertEqual(photos["a"]["quality"], .8)
            self.assertEqual(photos["a"]["stage2PairCount"], 2)
            self.assertEqual(photos["a"]["stage2StatusCounts"]["coherent_jump_candidate"], 1)
            self.assertEqual(photos["a"]["stage2StatusCounts"]["residual_pose_mismatch"], 1)
            self.assertIn("CALIBRATION_LIMITED_PAIR", photos["a"]["flags"])
            self.assertIsNone(photos["a"]["confidence"])


if __name__ == "__main__":
    unittest.main()
