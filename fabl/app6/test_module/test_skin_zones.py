from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app6.api.skin_zones import load_skin_zone_report, zone_catalog


class SkinZoneReportTests(unittest.TestCase):
    def test_catalog_uses_versioned_40_zone_atlas(self) -> None:
        catalog = zone_catalog()

        self.assertEqual(len(catalog), 40)
        self.assertEqual(catalog[0]["zone_id"], "Z01")

    def test_empty_stage1_photo_still_returns_honest_no_data_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = load_skin_zone_report(Path(tmp))

        self.assertEqual(report["zone_count"], 40)
        self.assertEqual(report["active_zone_count"], 0)
        self.assertEqual(report["no_data_zone_count"], 40)
