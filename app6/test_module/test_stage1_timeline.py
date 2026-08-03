from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from app6.api.stage1_timeline import build_stage1_inventory


class Stage1TimelineTests(unittest.TestCase):
    def test_inventory_exposes_real_stage1_fields_without_comparison_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (root / "main_timeline.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "photo_id", "date", "pose_bin", "pitch", "yaw", "roll",
                    "combined_visible_fraction", "date_provenance_status",
                ])
                writer.writeheader()
                writer.writerow({
                    "photo_id": "1999_01_11__abc", "date": "1999-01-11", "pose_bin": "front",
                    "pitch": "1.5", "yaw": "-0.2", "roll": "0.1",
                    "combined_visible_fraction": "0.77", "date_provenance_status": "filename",
                })
            payload = build_stage1_inventory(root)
        row = payload["photos"][0]
        self.assertEqual(payload["analysis_stage"], "stage1_inventory")
        self.assertEqual(row["quality"], 0.77)
        self.assertEqual(row["qualityBasis"], "combined_visible_fraction")
        self.assertIsNone(row["boneScore"])
        # До Stage 2 нет общей базы, следовательно, «нулевой drift» был бы
        # выдуманным результатом, а не измерением.
        self.assertIsNone(row["zOrbitDepth"])
        self.assertIsNone(row["zChinProj"])
        self.assertIsNone(row["zJawWidth"])
        self.assertIsNone(row["zCheek"])
        self.assertEqual(row["measurementStatus"], "not_compared")
        self.assertIn("boneScore", row["uiContractViolations"])
