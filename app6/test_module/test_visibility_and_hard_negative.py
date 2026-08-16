"""🎯 GUARD → Гейт видимости и hard-negative holdout (ER-105, ER-107).

visibility_gate.pair_visibility: вочность = пересечение видимости A и B; скрытая
зона не получает измерение (insufficient_common_visibility), а не засчитывается
как совпадение. hard_negative.evaluate: независимые персональные пары, порог
всегда external (никогда не подстраивается).
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage2.hard_negative import evaluate
from app6.stage2.visibility_gate import bin_visibility_prior, pair_visibility


class PairVisibilityTests(unittest.TestCase):
    def test_intersection_of_a_and_b(self):
        va = np.ones(50, bool)
        vb = np.zeros(50, bool)
        vb[:40] = True
        out = pair_visibility(va, vb)
        self.assertEqual(out["common"], 40)
        self.assertTrue(out["accepted"])  # 40 >= 30

    def test_insufficient_common_visibility_rejected(self):
        va = np.ones(50, bool)
        vb = np.zeros(50, bool)
        vb[:20] = True  # 20 < 30
        out = pair_visibility(va, vb)
        self.assertFalse(out["accepted"])
        self.assertEqual(out["reason"], "insufficient_common_visibility")

    def test_ldm106_has_lower_threshold(self):
        va = np.ones(40, bool)
        vb = np.zeros(40, bool)
        vb[:24] = True  # 24 == MIN_COMMON_106
        out = pair_visibility(va, vb, contract="ldm106")
        self.assertTrue(out["accepted"])
        self.assertEqual(out["contract"], "ldm106")

    def test_hidden_zone_never_counted_as_match(self):
        # Невидимые точки в обоих или одном кадре не дают измерение.
        va = np.zeros(10, bool)
        vb = np.zeros(10, bool)
        out = pair_visibility(va, vb)
        self.assertEqual(out["common"], 0)
        self.assertFalse(out["accepted"])

    def test_shape_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            pair_visibility(np.ones(5, bool), np.ones(6, bool))


class BinVisibilityPriorTests(unittest.TestCase):
    def test_fraction_of_frames_visible(self):
        matrix = np.array([[1, 1, 0], [1, 0, 0]], bool)  # 2 кадра × 3 точки
        prior = bin_visibility_prior(matrix)
        np.testing.assert_allclose(prior, [1.0, 0.5, 0.0])

    def test_non_2d_rejected(self):
        with self.assertRaises(ValueError):
            bin_visibility_prior(np.ones(5, bool))


class HardNegativeEvaluateTests(unittest.TestCase):
    def test_same_subject_pairs_excluded(self):
        rows = [
            {"subject_a": "X", "subject_b": "X", "primary_robust_z": 100.0},  # same → исключён
            {"subject_a": "a", "subject_b": "b", "primary_robust_z": 1.0},
        ]
        out = evaluate(rows, threshold=3.0)
        self.assertEqual(out["independent_person_pairs"], 1)
        self.assertEqual(out["false_match_rate"], 1.0)  # 1 пара <= threshold

    def test_false_match_rate_by_median_below_threshold(self):
        rows = [
            {"subject_a": "a", "subject_b": "b", "primary_robust_z": 1.0},
            {"subject_a": "c", "subject_b": "d", "primary_robust_z": 1.0},
            {"subject_a": "e", "subject_b": "f", "primary_robust_z": 9.0},
        ]
        out = evaluate(rows, threshold=3.0)
        self.assertEqual(out["false_match_rate"], 2 / 3)

    def test_threshold_never_tuned(self):
        rows = [{"subject_a": "a", "subject_b": "b", "primary_robust_z": 1.0}]
        out = evaluate(rows, threshold=3.0)
        self.assertEqual(out["threshold_source"], "external_calibration_only")

    def test_insufficient_input(self):
        out = evaluate([], threshold=3.0)
        self.assertEqual(out["status"], "insufficient")
        self.assertEqual(out["false_match_rate"], None)


if __name__ == "__main__":
    unittest.main()