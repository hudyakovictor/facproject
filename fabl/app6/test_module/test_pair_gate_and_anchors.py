"""🎯 GUARD → Парные гейты и политика стабильных якорей (ER-158, волна пар).

expression_pair_gate: выражение не исключает пары и не меняет порог (ER-106);
диагностика jaw/smile — только информационные поля.
anchor_policy.stable_anchor_mask: консервативный центральный выбор якорей
для выравнивания с детерминированными fallback-путями.
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage2.expression_pair_gate import MAX_JAW_DEGREE_GAP, expression_gate
from app6.stage2.anchor_policy import stable_anchor_indices, stable_anchor_mask


class ExpressionGateTests(unittest.TestCase):
    def test_all_pairs_accepted_even_with_mismatch(self):
        gate = expression_gate(
            {"jaw_open_detected": True, "jaw_open_degree": 20.0},
            {"jaw_open_detected": False, "jaw_open_degree": 0.0},
        )
        self.assertTrue(gate["accepted"])
        self.assertEqual(gate["threshold_multiplier"], 1.0)

    def test_expression_never_excludes_nor_rewerights(self):
        for meta_a, meta_b in [
            ({"jaw_open_detected": True, "smile_detected": True},
             {"jaw_open_detected": False, "smile_detected": False}),
            ({}, {}),
            ({"jaw_open_degree": 30.0}, {"jaw_open_degree": 0.0}),
        ]:
            gate = expression_gate(meta_a, meta_b)
            self.assertTrue(gate["accepted"])
            self.assertEqual(gate["threshold_multiplier"], 1.0)

    def test_jaw_mismatch_diagnostic(self):
        gate = expression_gate(
            {"jaw_open_detected": True, "jaw_open_degree": 40.0},
            {"jaw_open_detected": False, "jaw_open_degree": 0.0},
        )
        self.assertTrue(gate["jaw_mismatch"])
        self.assertFalse(expression_gate({}, {})["jaw_mismatch"])

    def test_smile_mismatch_diagnostic(self):
        gate = expression_gate(
            {"smile_detected": True}, {"smile_detected": False},
        )
        self.assertTrue(gate["smile_mismatch"])
        self.assertFalse(gate["jaw_mismatch"])

    def test_jaw_degree_gap_and_exceeded_threshold(self):
        within = expression_gate(
            {"jaw_open_degree": 3.0}, {"jaw_open_degree": 0.0},
        )
        self.assertAlmostEqual(within["jaw_degree_gap"], 3.0)
        self.assertFalse(within["jaw_degree_gap_exceeded"])

        over = expression_gate(
            {"jaw_open_degree": MAX_JAW_DEGREE_GAP + 0.5},
            {"jaw_open_degree": 0.0},
        )
        self.assertTrue(over["jaw_degree_gap_exceeded"])
        self.assertGreater(over["jaw_degree_gap"], MAX_JAW_DEGREE_GAP)

    def test_nonfinite_expression_metadata_is_limited(self):
        gate = expression_gate({"jaw_open_degree": float("nan")}, {})
        self.assertEqual(gate["confidence"], "limited")
        self.assertTrue(np.isnan(gate["jaw_degree_gap"]))

    def test_schema_and_confidence(self):
        gate = expression_gate({}, {})
        self.assertEqual(gate["schema"], "deeputin-expression-pair-gate-v2.0")
        self.assertEqual(gate["confidence"], "normal")


class StableAnchorMaskTests(unittest.TestCase):
    def test_insufficient_common_falls_back_to_all_common(self):
        points = np.zeros((30, 3), np.float32)
        common = np.array([True] * 10 + [False] * 20)
        mask, meta = stable_anchor_mask(points, common, min_count=24)
        self.assertTrue(mask[0] and mask[9])
        self.assertIn("fallback_all_common_insufficient_input", str(meta["anchor_policy"]))

    def test_invalid_shape_falls_back(self):
        mask, meta = stable_anchor_mask(np.zeros((5, 2), np.float32), np.ones(5, bool))
        self.assertIn("fallback", str(meta["anchor_policy"]))

    def test_central_quantile_selects_conservative_subset(self):
        rng = np.random.default_rng(0)
        points = np.concatenate([
            rng.normal(0, 1.0, (200, 3)),
            rng.normal(6, 1.0, (40, 3)),   # peripheral outliers
        ], axis=0).astype(np.float32)
        common = np.ones(len(points), bool)
        mask, meta = stable_anchor_mask(points, common, min_count=24)
        self.assertEqual(meta["anchor_policy"], "central_quantile_anchor_v1")
        self.assertLess(mask.sum(), len(points))
        chosen = points[mask]
        self.assertLess(chosen[:, 0].max(), 4.0)  # central face only, outliers excluded

    def test_too_few_anchors_degrades_to_all_common(self):
        rng = np.random.default_rng(1)
        points = np.column_stack([
            rng.uniform(-5, 5, 300),
            rng.uniform(-5, 5, 300),
            rng.uniform(-5, 5, 300),
        ]).astype(np.float32)
        stats = stable_anchor_mask(points, np.ones(len(points), bool), min_count=250)
        # common=300 >= min_count(250), но центральный quantile-якорь (~180)
        # и x-only-relaxed (~192) оба < 250 → деградация ко всем common.
        self.assertEqual(stats[1]["anchor_policy"], "fallback_all_common_too_few_anchors")
        self.assertTrue(stats[0].all())

    def test_stable_anchor_indices_subsamples(self):
        points = np.random.default_rng(2).normal(0, 1, (100, 3)).astype(np.float32)
        common = np.arange(len(points))
        ids, meta = stable_anchor_indices(points, common, max_points=30, min_count=10)
        self.assertLessEqual(ids.size, 30)
        self.assertIn("anchor_subsample_step", meta)


if __name__ == "__main__":
    unittest.main()