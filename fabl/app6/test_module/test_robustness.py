"""🎯 GUARD → Robustness: валидация ландмарков и калибровки (ER-102/ER-103, D6).

validate_landmarks: fail-closed проверки формы/конечности/уникальности id.
balanced_reference: <min_persons → insufficient_persons с count=0 (D6), а не
доверие шуму одного человека. cluster_bootstrap_ci/effective_sample_size:
учёт зависимости наблюдений, детерминизм по seed.
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage2.robustness import (
    balanced_reference,
    cluster_bootstrap_ci,
    effective_sample_size,
    ensure_same_pose,
    noise_adjusted_threshold,
    normalize_points,
    robust_threshold,
    validate_landmarks,
)


class ValidateLandmarksTests(unittest.TestCase):
    def test_valid_landmarks_accepted(self):
        pts = np.random.default_rng(0).normal(0, 1, (134, 3))
        self.assertTrue(validate_landmarks(pts, expected_count=134))

    def test_nonfinite_rejected(self):
        pts = np.zeros((10, 3))
        pts[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            validate_landmarks(pts)

    def test_duplicate_ids_rejected(self):
        pts = np.random.default_rng(0).normal(0, 1, (134, 3))
        with self.assertRaises(ValueError):
            validate_landmarks(pts, ids=np.zeros(134, int))

    def test_bad_shape_rejected(self):
        with self.assertRaises(ValueError):
            validate_landmarks(np.zeros((10, 2)))


class NormalizePointsTests(unittest.TestCase):
    def test_centers_and_scales(self):
        q = normalize_points(np.random.default_rng(0).normal(0, 1, (100, 3)))
        self.assertTrue(np.isfinite(q).all())
        self.assertAlmostEqual(float(np.linalg.norm(q.mean(0))), 0.0, places=5)

    def test_degenerate_rejected(self):
        with self.assertRaises(ValueError):
            normalize_points(np.zeros((100, 3)))


class EnsureSamePoseTests(unittest.TestCase):
    def test_cross_pose_rejected(self):
        with self.assertRaises(ValueError):
            ensure_same_pose("frontal", "left_light")

    def test_same_pose_accepted(self):
        self.assertTrue(ensure_same_pose("frontal", "frontal"))

    def test_non_string_rejected(self):
        with self.assertRaises(ValueError):
            ensure_same_pose(1, 2)


class BalancedReferenceTests(unittest.TestCase):
    def test_too_few_persons_is_fail_closed(self):
        by_person = {"p1": [1.0, 2.0], "p2": [3.0, 4.0]}
        out = balanced_reference(by_person, min_persons=3)
        self.assertEqual(out["status"], "insufficient_persons")
        self.assertEqual(out["count"], 0)
        self.assertEqual(out["required_persons"], 3)

    def test_three_persons_produces_aggregate(self):
        by_person = {"p1": [1.0, 2.0], "p2": [3.0, 4.0], "p3": [5.0, 6.0]}
        out = balanced_reference(by_person, min_persons=3)
        self.assertEqual(out["count"], 3)
        self.assertEqual(out["observed_value_count"], 6)
        self.assertGreater(out["p95"], 0.0)


class NoiseAdjustedThresholdTests(unittest.TestCase):
    def test_noise_increases_threshold(self):
        adj = noise_adjusted_threshold(1.0, 0.5)
        self.assertGreater(adj, 1.0)

    def test_invalid_negative_sigma_rejected(self):
        with self.assertRaises(ValueError):
            noise_adjusted_threshold(1.0, -0.1)


class RobustThresholdTests(unittest.TestCase):
    def test_threshold_is_robust_to_contamination(self):
        values = list(np.random.default_rng(0).normal(0, 1, 100)) + [50.0, 60.0]
        out = robust_threshold(values, quantile=0.95, max_contamination=0.20)
        self.assertLess(out["threshold"], 30.0)  # выбросы не доминируют

    def test_too_few_values_raises(self):
        with self.assertRaises(ValueError):
            robust_threshold([1.0, 2.0, 3.0])


class ESSandBootstrapTests(unittest.TestCase):
    def test_effective_sample_size_depends_on_clusters(self):
        independent = effective_sample_size([0, 1, 2, 3, 4])
        dependent = effective_sample_size([0, 0, 0, 1, 1])
        self.assertLess(dependent, independent)

    def test_bootstrap_deterministic_with_seed(self):
        values = np.arange(30, dtype=float)
        clusters = np.repeat([0, 1], 15)
        a = cluster_bootstrap_ci(values, clusters, seed=0)
        b = cluster_bootstrap_ci(values, clusters, seed=0)
        self.assertEqual(a["seed"], b["seed"])
        self.assertAlmostEqual(a["point"], b["point"], places=6)

    def test_bootstrap_requires_two_clusters(self):
        with self.assertRaises(ValueError):
            cluster_bootstrap_ci(np.arange(10.0), np.zeros(10, int))


if __name__ == "__main__":
    unittest.main()