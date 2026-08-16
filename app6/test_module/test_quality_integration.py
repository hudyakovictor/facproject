"""🎯 GUARD → Интеграция quality-зон Stage 1 (ER-104/ER-117).

load_quality_zone_summary: отсутствующий/повреждённый файл → fail-closed status
(missing/invalid), а не молчаливый прогон нулей. pair_quality_zone_overlap:
пересечение качества A∩B; пара ограничена, если общие зоны не usable.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np

from app6.stage2.quality_integration import load_quality_zone_summary, pair_quality_zone_overlap


class LoadQualityZoneSummaryTests(unittest.TestCase):
    def test_missing_file_is_fail_closed(self):
        with TemporaryDirectory() as td:
            out = load_quality_zone_summary(Path(td))
            self.assertEqual(out["status"], "missing")
            self.assertEqual(out["zone_count"], 0)
            self.assertEqual(out["usable_zone_count"], 0)

    def test_invalid_npz_is_fail_closed(self):
        with TemporaryDirectory() as td:
            (Path(td) / "quality_zones.npz").write_bytes(b"not-an-npz")
            out = load_quality_zone_summary(Path(td))
            self.assertEqual(out["status"], "invalid")
            self.assertEqual(out["zone_count"], 0)

    def test_valid_summary_computes_usable_zones(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "quality_zones.npz"
            np.savez(
                p,
                zone_names=np.array(["forehead", "weak_zone"]),
                zone_status=np.array(["usable", "weak"]),
                zone_texture_pixels=np.array([5000, 5000], np.int64),
                zone_visible_fraction=np.array([0.9, 0.5], np.float32),
                zone_texture_score=np.array([0.8, 0.1], np.float32),
                zone_sides=np.array(["L", "L"]),
                zone_types=np.array(["skin", "skin"]),
            )
            out = load_quality_zone_summary(Path(td))
            self.assertEqual(out["status"], "loaded")
            self.assertEqual(out["zone_count"], 2)
            self.assertEqual(out["usable_zone_count"], 1)
            self.assertEqual(out["usable_zone_names"], ["forehead"])


class PairQualityZoneOverlapTests(unittest.TestCase):
    def _zones(self, usable=True, name="forehead"):
        return {
            name: {"usable": usable, "status": "usable" if usable else "weak",
                   "texture_pixels": 5000, "visible_fraction": 0.9,
                   "texture_score_0_1": 0.8},
        }

    def test_common_usable_zones_overlap(self):
        a = SimpleNamespace(quality_zones={"per_zone": self._zones(True)})
        b = SimpleNamespace(quality_zones={"per_zone": self._zones(True)})
        summary, rows = pair_quality_zone_overlap(a, b, "p1")
        self.assertEqual(summary["quality_zone_common_count"], 1)
        self.assertEqual(summary["quality_zone_usable_common_count"], 1)
        self.assertEqual(rows[0]["usable_both"], True)

    def test_pair_limited_when_common_not_usable(self):
        a = SimpleNamespace(quality_zones={"per_zone": self._zones(False)})
        b = SimpleNamespace(quality_zones={"per_zone": self._zones(False)})
        summary, _ = pair_quality_zone_overlap(a, b, "p1")
        self.assertEqual(summary["quality_zone_common_count"], 1)
        self.assertEqual(summary["quality_zone_usable_common_count"], 0)
        self.assertTrue(summary["quality_zone_pair_limited"])

    def test_no_quality_zones_is_not_limited(self):
        a = SimpleNamespace(quality_zones={})
        b = SimpleNamespace(quality_zones={})
        summary, _ = pair_quality_zone_overlap(a, b, "p1")
        self.assertEqual(summary["quality_zone_common_count"], 0)
        self.assertFalse(summary["quality_zone_pair_limited"])


if __name__ == "__main__":
    unittest.main()