"""Primary-зоны гипотез и мимика не ломают их."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from app6.stage2.core import robust_rigid_align
from app6.stage2.expression_qc import BONE_ZONES, MIMIC_ZONES
from app6.stage2.pair_row_patch import enrich_pair_row
from app6.stage2.primary_zones import (
    PRIMARY_HYPOTHESIS_ZONES,
    expression_zone_policy,
    pair_expression_active,
    primary_zone_aggregate,
)
from app6.stage2.quality_gate import compensate_quality_disparity


class PrimaryZonePolicyTests(unittest.TestCase):
    def test_hypothesis_zones_are_named_not_grid(self):
        self.assertIn("orbit_L", PRIMARY_HYPOTHESIS_ZONES)
        self.assertIn("nose_bridge_tip", PRIMARY_HYPOTHESIS_ZONES)
        self.assertNotIn("x_center_center", PRIMARY_HYPOTHESIS_ZONES)

    def test_smile_zeroes_mimic_keeps_primary(self):
        policy = expression_zone_policy(None, smile_detected=True)
        self.assertTrue(policy["expression"]["expression_active"])
        for zone in MIMIC_ZONES:
            self.assertEqual(policy["zone_weights"][zone], 0.0)
        for zone in PRIMARY_HYPOTHESIS_ZONES:
            self.assertGreater(policy["zone_weights"][zone], 0.0)
            self.assertIn(zone, BONE_ZONES)

    def test_primary_aggregate_ignores_mimic_and_grid(self):
        policy = expression_zone_policy(None, smile_detected=True)
        agg = primary_zone_aggregate(
            [
                {"zone": "orbit_L", "status": "measured", "rmse": 0.02},
                {"zone": "cheek_soft_L", "status": "measured", "rmse": 0.90},
                {"zone": "x_center_center", "status": "measured", "rmse": 0.50},
                {"zone": "chin", "status": "measured", "rmse": 0.04},
            ],
            policy["zone_weights"],
        )
        self.assertEqual(agg["status"], "measured")
        self.assertEqual(agg["primary_zone_count"], 2)
        self.assertAlmostEqual(agg["primary_zone_rmse"], (0.02 * 1.2 + 0.04 * 1.0) / 2.2, places=6)

    def test_pair_expression_active(self):
        self.assertTrue(pair_expression_active({"smile_detected": True}, {}))
        self.assertFalse(pair_expression_active({}, {}))


class PairRowEnrichmentTests(unittest.TestCase):
    def test_enrich_adds_patch_columns(self):
        a = SimpleNamespace(record_id="a", ldm106=None, quality_texture_score=0.2)
        b = SimpleNamespace(record_id="b", ldm106=None, quality_texture_score=0.8)
        row = enrich_pair_row(
            {"photo_a": "a", "photo_b": "b", "status": "measured", "quality_limited": False},
            zones=[
                {"zone": "orbit_L", "status": "measured", "rmse": 0.03},
                {"zone": "cheek_soft_L", "status": "measured", "rmse": 0.8},
            ],
            record_a=a,
            record_b=b,
            qc_a={"pixels": 100000},
            qc_b={"pixels": 4000000},
            smile_a=True,
        )
        self.assertIn("primary_zone_rmse", row)
        self.assertIn("expression_active", row)
        self.assertTrue(row["expression_active"])
        self.assertIn("cheek_soft_L", row["expression_excluded_zones"])
        self.assertTrue(row["quality_disparity"])
        self.assertFalse(row["texture_conclusions_allowed"])


class QualityDisparityWiringTests(unittest.TestCase):
    def test_disparity_blocks_texture_not_geometry(self):
        row = compensate_quality_disparity(
            {"photo_a": "a", "photo_b": "b", "texture_score_0_1": 0.1, "ldm134_rmse": 0.03},
            {
                "a": {"pixels": 100000, "texture_score_0_1": 0.1, "quality_limited": False},
                "b": {"pixels": 4000000, "texture_score_0_1": 0.8, "quality_limited": False},
            },
        )
        self.assertTrue(row["quality_disparity"])
        self.assertFalse(row["texture_conclusions_allowed"])
        self.assertEqual(row["ldm134_rmse"], 0.03)


class KabschIterationTests(unittest.TestCase):
    def test_iterations_increment(self):
        rng = np.random.default_rng(0)
        src = rng.normal(size=(40, 3)).astype(np.float64)
        dst = src + np.array([0.01, -0.02, 0.03])
        _, _, _, meta = robust_rigid_align(src, dst, max_iterations=5)
        self.assertGreaterEqual(int(meta["iterations"]), 1)


if __name__ == "__main__":
    unittest.main()
