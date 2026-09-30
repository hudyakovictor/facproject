from __future__ import annotations

import unittest

import numpy as np

from morphing.backend.analysis import (
    forensic_metrics,
    pca_projection,
    similarity_metrics,
    symmetry_metrics,
    temporal_drift_metrics,
    uv_difference,
)


def shape(offset: float = 0.0, n: int = 70) -> np.ndarray:
    index = np.arange(n, dtype=np.float64)
    return np.column_stack((index / n, np.sin(index / 8) * 0.1 + offset, np.cos(index / 9) * 0.15))


class SimilarityTests(unittest.TestCase):
    def test_identical_mesh_similarity_is_maximal(self) -> None:
        points = shape()
        result = similarity_metrics(points, points.copy())
        self.assertEqual(result["euclidean_distance"], 0)
        self.assertEqual(result["morphability_score"], 100)
        self.assertEqual(result["cosine_similarity"], 1)
        self.assertEqual(len(result["top_5_zones"]), 5)

    def test_mismatched_or_nonfinite_meshes_are_rejected(self) -> None:
        points = shape()
        with self.assertRaisesRegex(ValueError, "shape"):
            similarity_metrics(points, points[:-1])
        invalid = points.copy()
        invalid[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            similarity_metrics(points, invalid)

    def test_custom_zone_bounds_are_checked(self) -> None:
        points = shape()
        with self.assertRaisesRegex(ValueError, "bounds"):
            similarity_metrics(points, points, zones={"broken": (-1, 5)})

    def test_forensic_index_is_not_reported_as_probability(self) -> None:
        result = forensic_metrics(shape(), shape(0.03))
        self.assertIsInstance(result["forensic_score"], float)
        self.assertIsNone(result["probability_same_person"])
        self.assertIn("uncalibrated", result["score_type"])

    def test_forensic_weights_are_validated(self) -> None:
        points = shape()
        with self.assertRaisesRegex(ValueError, "non-negative"):
            forensic_metrics(points, points, weights={"nose": -1})
        with self.assertRaisesRegex(ValueError, "unknown"):
            forensic_metrics(points, points, weights={"unknown": 1})


class GeometryDiagnosticTests(unittest.TestCase):
    def test_pca_returns_three_coordinates_for_each_mesh(self) -> None:
        result = pca_projection([shape(), shape(0.1), shape(0.2)])
        self.assertEqual(np.asarray(result["coordinates"]).shape, (3, 3))
        self.assertEqual(len(result["explained_variance"]), 3)

    def test_pca_requires_same_shape_and_finite_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "identical shapes"):
            pca_projection([shape(), np.zeros((71, 3))])
        broken = shape()
        broken[0, 0] = np.inf
        with self.assertRaisesRegex(ValueError, "finite"):
            pca_projection([shape(), broken])

    def test_temporal_drift_orders_keyframes_by_year(self) -> None:
        meshes = [shape(0.2), shape(), shape(0.1)]
        result = temporal_drift_metrics([2020, 2000, 2010], meshes)
        self.assertEqual(result["ordered_indices"], [1, 2, 0])
        self.assertEqual(result["years"], [2000.0, 2010.0, 2020.0])
        self.assertEqual(len(result["residuals"]), 3)

    def test_temporal_drift_rejects_duplicate_years(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            temporal_drift_metrics([2000, 2000, 2010], [shape(), shape(0.1), shape(0.2)])

    def test_symmetry_requires_finite_points(self) -> None:
        broken = shape()
        broken[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            symmetry_metrics(broken)

    def test_uv_diff_handles_identical_and_changed_textures(self) -> None:
        a = np.zeros((16, 16, 3), dtype=np.uint8)
        b = a.copy()
        unchanged = uv_difference(a, b)
        b[4:8, 5:9] = 255
        changed = uv_difference(a, b)
        self.assertEqual(unchanged.shape, (16, 16, 3))
        self.assertGreater(int(np.max(changed)), 0)


if __name__ == "__main__":
    unittest.main()
