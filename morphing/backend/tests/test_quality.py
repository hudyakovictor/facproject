from __future__ import annotations

import unittest

import numpy as np

from morphing.backend.quality import (
    QualityThresholds,
    displacement_metrics,
    evaluate_image,
    evaluate_mesh,
    image_metrics,
    mesh_metrics,
    quality_schema,
)


class ImageQualityTests(unittest.TestCase):
    def test_constant_rgb_image_is_detected_as_low_information(self) -> None:
        image = np.full((256, 256, 3), 127, dtype=np.uint8)
        report = evaluate_image(image)
        self.assertEqual(report.status, "warn")
        self.assertTrue(any(finding.code == "low_information" for finding in report.findings))
        self.assertEqual(report.metrics["width"], 256)
        self.assertEqual(report.metrics["height"], 256)

    def test_sharp_checkerboard_has_higher_laplacian_energy_than_flat_image(self) -> None:
        y, x = np.indices((256, 256))
        checkerboard = (((x // 8 + y // 8) % 2) * 255).astype(np.uint8)
        flat = np.full((256, 256), 128, dtype=np.uint8)
        self.assertGreater(image_metrics(checkerboard)["blur_laplacian_variance"], image_metrics(flat)["blur_laplacian_variance"])

    def test_float_images_in_zero_one_range_are_supported(self) -> None:
        image = np.linspace(0, 1, 256 * 256, dtype=np.float32).reshape(256, 256)
        metrics = image_metrics(image)
        self.assertGreater(metrics["dynamic_range"], 200)
        self.assertLessEqual(metrics["brightness_mean"], 255)

    def test_small_image_fails_with_specific_finding(self) -> None:
        report = evaluate_image(np.zeros((32, 32), dtype=np.uint8))
        self.assertEqual(report.status, "fail")
        self.assertTrue(any(finding.code == "image_too_small" for finding in report.findings))

    def test_invalid_nonfinite_image_is_rejected(self) -> None:
        image = np.zeros((200, 200), dtype=np.float32)
        image[10, 10] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            image_metrics(image)

    def test_face_box_metrics_and_center_warning(self) -> None:
        image = np.random.default_rng(2).integers(0, 255, size=(300, 400, 3), dtype=np.uint8)
        report = evaluate_image(image, face_box=(5, 10, 80, 90))
        self.assertIn("face_area_fraction", report.metrics)
        self.assertTrue(any(finding.code == "face_off_center" for finding in report.findings))

    def test_face_box_is_validated(self) -> None:
        image = np.zeros((256, 256), dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, "face_box"):
            evaluate_image(image, face_box=(1, 2, -1, 3))

    def test_custom_thresholds_are_serialized(self) -> None:
        thresholds = QualityThresholds(min_width=100, max_clip_fraction=0.2)
        report = evaluate_image(np.ones((200, 200), dtype=np.uint8) * 90, thresholds)
        self.assertEqual(report.to_dict()["thresholds"]["min_width"], 100)


class MeshQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vertices = np.asarray([
            [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        ], dtype=np.float64)
        self.triangles = np.asarray([[0, 1, 2], [0, 2, 3]])

    def test_open_quad_has_expected_boundary_topology(self) -> None:
        metrics = mesh_metrics(self.vertices, self.triangles)
        self.assertEqual(metrics["triangle_count"], 2)
        self.assertEqual(metrics["boundary_edge_count"], 4)
        self.assertEqual(metrics["nonmanifold_edge_count"], 0)
        self.assertEqual(metrics["degenerate_triangles"], 0)

    def test_invalid_triangle_indices_fail_quality_gate(self) -> None:
        report = evaluate_mesh(self.vertices, [[0, 1, 99]])
        self.assertEqual(report.status, "fail")
        self.assertTrue(any(finding.code == "invalid_triangles" for finding in report.findings))

    def test_degenerate_triangle_is_reported(self) -> None:
        metrics = mesh_metrics(self.vertices, [[0, 1, 1]])
        self.assertEqual(metrics["repeated_index_triangles"], 1)
        self.assertEqual(metrics["degenerate_triangles"], 1)

    def test_nonfinite_vertex_is_critical(self) -> None:
        vertices = self.vertices.copy()
        vertices[1, 0] = np.inf
        report = evaluate_mesh(vertices, self.triangles)
        self.assertEqual(report.status, "fail")
        self.assertTrue(any(finding.code == "nonfinite_mesh" for finding in report.findings))
        self.assertEqual(report.to_dict()["metrics"]["nonfinite_triangles"], 1)

    def test_displacement_metrics(self) -> None:
        moved = self.vertices + np.asarray([0, 0, 0.1])
        result = displacement_metrics(self.vertices, moved, threshold=0.05)
        self.assertAlmostEqual(result["mean"], 0.1)
        self.assertEqual(result["above_threshold_fraction"], 1.0)

    def test_displacement_requires_identical_topology(self) -> None:
        with self.assertRaisesRegex(ValueError, "same shape"):
            displacement_metrics(self.vertices, self.vertices[:-1])

    def test_schema_exposes_topology_metrics(self) -> None:
        schema = quality_schema()
        self.assertEqual(schema["schema"], "facproject-morphing-quality-v1")
        self.assertIn("boundary_edge_count", schema["mesh_metrics"])


if __name__ == "__main__":
    unittest.main()
