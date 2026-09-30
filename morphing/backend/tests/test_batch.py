from __future__ import annotations

import unittest

import numpy as np

from morphing.backend.batch import (
    bootstrap_mean_interval,
    regional_displacement_intervals,
    similarity_matrix,
    timeline_speed_summary,
)


def mesh(offset: float = 0.0, scale: float = 1.0) -> np.ndarray:
    points = np.linspace(-1, 1, 90, dtype=np.float64).reshape(30, 3)
    return points * scale + np.asarray([offset, 0.0, 0.0])


class SimilarityMatrixTests(unittest.TestCase):
    def test_matrix_is_symmetric_and_diagonal_is_zero(self) -> None:
        result = similarity_matrix([mesh(), mesh(0.1), mesh(-0.2)], ["a", "b", "c"])
        matrix = np.asarray(result["mean_distance_matrix"])
        self.assertTrue(np.allclose(matrix, matrix.T))
        self.assertTrue(np.allclose(np.diag(matrix), 0))
        self.assertEqual(result["labels"], ["a", "b", "c"])
        self.assertEqual(len(result["peer_outlier_ranking"]), 3)

    def test_regional_matrices_match_overall_shape(self) -> None:
        result = similarity_matrix([mesh(), mesh(0.2)])
        for matrix in result["regional_distance_matrices"].values():
            self.assertEqual(np.asarray(matrix).shape, (2, 2))

    def test_rank_does_not_claim_identity(self) -> None:
        result = similarity_matrix([mesh(), mesh(0.1)])
        self.assertIn("not an identity decision", result["interpretation"])
        self.assertNotIn("probability_same_person", result)

    def test_mesh_count_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 2 and 32"):
            similarity_matrix([mesh()])

    def test_shapes_must_match(self) -> None:
        with self.assertRaisesRegex(ValueError, "different topology"):
            similarity_matrix([mesh(), np.zeros((40, 3))])

    def test_nonfinite_points_are_rejected(self) -> None:
        broken = mesh()
        broken[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            similarity_matrix([mesh(), broken])

    def test_labels_must_match(self) -> None:
        with self.assertRaisesRegex(ValueError, "labels"):
            similarity_matrix([mesh(), mesh(1)], ["one"])


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_is_reproducible(self) -> None:
        values = np.asarray([1, 2, 3, 4, 5], dtype=np.float64)
        a = bootstrap_mean_interval(values, iterations=500, seed=24)
        b = bootstrap_mean_interval(values, iterations=500, seed=24)
        self.assertEqual(a, b)
        self.assertLessEqual(a["lower"], a["mean"])
        self.assertGreaterEqual(a["upper"], a["mean"])

    def test_bootstrap_rejects_invalid_settings(self) -> None:
        with self.assertRaisesRegex(ValueError, "confidence"):
            bootstrap_mean_interval([1, 2], confidence=1.0)
        with self.assertRaisesRegex(ValueError, "at least 100"):
            bootstrap_mean_interval([1, 2], iterations=50)
        with self.assertRaisesRegex(ValueError, "finite"):
            bootstrap_mean_interval([1, np.inf])

    def test_regional_interval_reports_all_zones(self) -> None:
        a = mesh()
        b = a.copy()
        b[:, 2] += 0.2
        result = regional_displacement_intervals(a, b, iterations=100, seed=1)
        self.assertEqual(len(result["zones"]), 7)
        self.assertIn("descriptive", result["interpretation"])

    def test_regional_interval_is_repeatable(self) -> None:
        a = mesh()
        b = a + 0.01
        first = regional_displacement_intervals(a, b, iterations=100, seed=8)
        second = regional_displacement_intervals(a, b, iterations=100, seed=8)
        self.assertEqual(first, second)


class TimelineSpeedTests(unittest.TestCase):
    def test_segment_speed_uses_real_year_span(self) -> None:
        result = timeline_speed_summary([2000, 2010, 2030], [mesh(), mesh(0.2), mesh(0.8)])
        self.assertEqual([segment["year_span"] for segment in result["segments"]], [10, 20])
        self.assertGreater(result["segments"][0]["mean_displacement_per_year"], 0)

    def test_years_must_increase(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            timeline_speed_summary([2000, 2000], [mesh(), mesh(1)])

    def test_years_count_must_match(self) -> None:
        with self.assertRaisesRegex(ValueError, "each mesh"):
            timeline_speed_summary([2000], [mesh(), mesh(1)])


if __name__ == "__main__":
    unittest.main()
