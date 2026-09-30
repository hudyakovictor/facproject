from __future__ import annotations

import unittest

import numpy as np

from morphing.backend.extrapolation import extrapolate_shape
from morphing.backend.timeline import blend_vertices, catmull_rom_weights, interpolate_sequence, timeline_metadata


def mesh(offset: float = 0.0, count: int = 70) -> np.ndarray:
    values = np.arange(count * 3, dtype=np.float64).reshape(count, 3) / 100
    return values + np.asarray([offset, 0, 0])


class TimelineTests(unittest.TestCase):
    def test_catmull_rom_passes_through_keyframes(self) -> None:
        positions = [0, 0.2, 0.65, 1]
        meshes = [mesh(float(index)) for index in range(4)]
        for index, time in enumerate(positions):
            result = interpolate_sequence(meshes, time, positions)
            self.assertTrue(np.allclose(result, meshes[index], atol=1e-6))

    def test_nonuniform_weights_sum_to_one(self) -> None:
        positions = [0, 0.1, 0.8, 1]
        for progress in np.linspace(0, 1, 31):
            weights = catmull_rom_weights(float(progress), 4, positions)
            self.assertAlmostEqual(float(weights.sum()), 1, places=6)

    def test_two_keyframe_weights_are_linear(self) -> None:
        weights = catmull_rom_weights(0.25, 2, [0, 1])
        self.assertTrue(np.allclose(weights, [0.75, 0.25, 0, 0]))

    def test_progress_is_clamped_to_timeline(self) -> None:
        start = catmull_rom_weights(-4, 3)
        end = catmull_rom_weights(4, 3)
        self.assertTrue(np.allclose(start, [1, 0, 0, 0]))
        self.assertTrue(np.allclose(end, [0, 0, 1, 0]))

    def test_nonfinite_progress_and_positions_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            catmull_rom_weights(float("nan"), 3)
        with self.assertRaisesRegex(ValueError, "finite"):
            catmull_rom_weights(0.5, 3, [0, float("nan"), 1])

    def test_timeline_metadata_requires_matching_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "labels"):
            timeline_metadata(3, ["A", "B"])

    def test_blend_weights_are_normalized(self) -> None:
        a, b, c = mesh(0), mesh(1), mesh(2)
        result = blend_vertices([a, b, c], [1, 2, 1])
        expected = (a + 2 * b + c) / 4
        self.assertTrue(np.allclose(result, expected))

    def test_blend_rejects_negative_or_zero_weights(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            blend_vertices([mesh(), mesh(1)], [1, -1])
        with self.assertRaisesRegex(ValueError, "positive"):
            blend_vertices([mesh(), mesh(1)], [0, 0])

    def test_interpolation_rejects_nonfinite_mesh(self) -> None:
        broken = mesh(1)
        broken[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            interpolate_sequence([mesh(), broken], 0.5)


class ExtrapolationTests(unittest.TestCase):
    def test_linear_shape_trajectory_is_projected(self) -> None:
        base = mesh()
        meshes = [base, base + 0.1, base + 0.2]
        prediction, metadata = extrapolate_shape([2000, 2005, 2010], meshes, 2020)
        self.assertTrue(np.allclose(prediction, base + 0.4, atol=1e-4))
        self.assertEqual(metadata["degree"], 2)
        self.assertEqual(metadata["extrapolation_span_years"], 10)
        self.assertEqual(metadata["max_horizon_years"], 50)

    def test_polynomial_degree_is_bounded_by_training_count(self) -> None:
        base = mesh()
        prediction, metadata = extrapolate_shape([2000, 2010, 2020], [base, base + 1, base + 4], 2025, degree=8)
        self.assertEqual(metadata["degree"], 2)
        self.assertTrue(np.isfinite(prediction).all())

    def test_years_must_be_strictly_increasing(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            extrapolate_shape([2000, 2000, 2010], [mesh(), mesh(1), mesh(2)], 2020)

    def test_future_year_must_be_later(self) -> None:
        with self.assertRaisesRegex(ValueError, "later"):
            extrapolate_shape([2000, 2005, 2010], [mesh(), mesh(1), mesh(2)], 2010)

    def test_forecast_horizon_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "limit"):
            extrapolate_shape([2000, 2005, 2010], [mesh(), mesh(1), mesh(2)], 2061)

    def test_mesh_coordinates_must_be_finite(self) -> None:
        broken = mesh()
        broken[0, 0] = np.inf
        with self.assertRaisesRegex(ValueError, "finite"):
            extrapolate_shape([2000, 2005, 2010], [mesh(), mesh(1), broken], 2020)


if __name__ == "__main__":
    unittest.main()
