"""🎯 GUARD → Плотный mesh и анатомические зоны (ER-158, волна сигналов).

Чистые numpy-помощники (_normalize/_subsample/_zone_labels/_shape_descriptor) и
fail-closed пути dense_mesh_pair: без reconstruction.npz меш недоступен, а не
фабрикуется; недостаточная видимость → insufficient_visibility.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np

from app6.stage2.mesh_dense import (
    _normalize,
    _shape_descriptor,
    _subsample,
    _zone_labels,
    dense_mesh_pair,
)


class NormalizeTests(unittest.TestCase):
    def test_centers_and_scales_to_unit(self):
        v = np.array([[10.0, 0, 0], [12.0, 0, 0], [11.0, 0, 0]], np.float32)
        out = _normalize(v)
        self.assertTrue(np.isfinite(out).all())
        # Центрированы: среднее ~0.
        self.assertAlmostEqual(float(np.mean(out[:, 0])), 0.0, places=5)

    def test_degenerate_zero_scale_is_safe(self):
        v = np.zeros((5, 3), np.float32)
        out = _normalize(v)
        self.assertTrue(np.isfinite(out).all())
        self.assertEqual(v.shape, out.shape)


class SubsampleTests(unittest.TestCase):
    def test_small_array_unchanged(self):
        ids = np.arange(10, dtype=np.int64)
        np.testing.assert_array_equal(_subsample(ids, max_points=20), ids)

    def test_large_array_is_bounded_and_ordered(self):
        ids = np.arange(10000, dtype=np.int64)
        out = _subsample(ids, max_points=100)
        self.assertLessEqual(out.size, 100)
        self.assertTrue((np.diff(out) > 0).all())  # сохраняет порядок


class ZoneLabelsTests(unittest.TestCase):
    def test_assigns_three_by_three_grid(self):
        v = np.array([
            [0.0, 0.0, 0.0],  # low-low
            [1.0, 0.0, 0.0],  # mid-low
            [2.0, 0.0, 0.0],  # high-low
            [0.0, 1.0, 0.0],  # low-mid
            [1.0, 1.0, 0.0],  # mid-mid
            [2.0, 1.0, 0.0],  # high-mid
            [0.0, 2.0, 0.0],  # low-high
            [1.0, 2.0, 0.0],  # mid-high
            [2.0, 2.0, 0.0],  # high-high
        ], np.float32)
        labels = _zone_labels(v)
        self.assertEqual(labels.shape, (9,))
        self.assertTrue(all(isinstance(x, str) for x in labels))

    def test_scalar_z_is_ignored(self):
        v = np.zeros((4, 3), np.float32)
        labels = _zone_labels(v)
        self.assertEqual(labels.shape, (4,))


class ShapeDescriptorTests(unittest.TestCase):
    def test_fewer_than_four_points_zero(self):
        self.assertEqual(_shape_descriptor(np.zeros((3, 3), np.float64)),
                         {"mesh_shape_eig_ratio_1": 0.0, "mesh_shape_eig_ratio_2": 0.0,
                          "mesh_shape_planarity": 0.0, "mesh_shape_linearity": 0.0,
                          "mesh_geodesic_span_proxy": 0.0})

    def test_planar_shape_is_planar(self):
        # Точки в плоскости z≈const → planarity высокая.
        rng = np.random.default_rng(0)
        pts = np.column_stack([rng.normal(0, 1, 500), rng.normal(0, 1, 500), np.zeros(500)])
        d = _shape_descriptor(pts)
        self.assertGreater(d["mesh_shape_planarity"], 0.5)
        self.assertGreaterEqual(d["mesh_shape_eig_ratio_1"], d["mesh_shape_eig_ratio_2"])

    def test_returns_float_finite(self):
        rng = np.random.default_rng(3)
        d = _shape_descriptor(rng.normal(0, 1, (100, 3)))
        self.assertTrue(all(np.isfinite(v) for v in d.values()))


class DenseMeshFailClosedTests(unittest.TestCase):
    def test_missing_record_dir_is_unavailable(self):
        with TemporaryDirectory() as td:
            a = SimpleNamespace(record_dir=None)
            b = SimpleNamespace(record_dir=None)
            row, zones = dense_mesh_pair(a, b, Path(td), "p1")
            self.assertEqual(row["mesh_status"], "unavailable")
            self.assertEqual(row["mesh_evidence_level"], "not_available")
            self.assertEqual(zones, [])

    def test_missing_reconstruction_is_unavailable(self):
        with TemporaryDirectory() as td:
            empty = Path(td) / "photo"
            empty.mkdir()
            a = SimpleNamespace(record_dir=str(empty))
            b = SimpleNamespace(record_dir=str(empty))
            row, _ = dense_mesh_pair(a, b, empty, "p1")
            self.assertEqual(row["mesh_error_a"], "missing_reconstruction")
            self.assertEqual(row["mesh_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()