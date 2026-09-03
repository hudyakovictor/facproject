"""🎯 GUARD → UV-атлас зон и постпроцесс-отчёты (ER-114).

skin_zone_atlas.build_triangle_zone_map: треугольник относится к зоне по
центроиду UV (приоритет higher-wins); фон = 0. postprocess_reports._num:
отсутствующее/нечисловое значение → default (не фабрикуется как 0).
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage1.skin_zone_atlas import build_triangle_zone_map, zone_names


class BuildTriangleZoneMapTests(unittest.TestCase):
    def test_centroid_in_zone_maps_nonzero(self):
        uv = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]], np.float32)
        tri = np.array([[0, 1, 2]], np.int64)
        labels = build_triangle_zone_map(uv, tri)
        self.assertGreater(int(labels[0]), 0)

    def test_background_uv_maps_zero(self):
        # UV вне всех зон (далеко за пределами атласа).
        uv = np.array([[-5.0, -5.0]] * 3, np.float32)
        tri = np.array([[0, 1, 2]], np.int64)
        labels = build_triangle_zone_map(uv, tri)
        self.assertEqual(int(labels[0]), 0)

    def test_invalid_triangle_shape_rejected(self):
        with self.assertRaises(ValueError):
            build_triangle_zone_map(np.zeros((6, 2), np.float32), np.zeros((3, 2), np.int64))

    def test_returns_one_label_per_triangle(self):
        uv = np.random.default_rng(0).uniform(0, 1, (30, 2)).astype(np.float32)
        tri = np.arange(30).reshape(10, 3).astype(np.int64)
        labels = build_triangle_zone_map(uv, tri)
        self.assertEqual(labels.shape, (10,))
        self.assertEqual(set(np.unique(labels)) - set(range(len(zone_names()) + 1)), set())


class ZoneNamesTests(unittest.TestCase):
    def test_zone_names_nonempty_distinct(self):
        names = zone_names()
        self.assertTrue(names)
        self.assertEqual(len(set(names)), len(names))


class PostProcessNumTests(unittest.TestCase):
    def test_num_uses_default_for_missing(self):
        from app6.stage2.postprocess_reports import _num
        self.assertEqual(_num(None, default=0.0), 0.0)

    def test_num_parses_valid(self):
        from app6.stage2.postprocess_reports import _num
        self.assertAlmostEqual(_num("3.14", default=0.0), 3.14)

    def test_num_defaults_for_non_numeric(self):
        from app6.stage2.postprocess_reports import _num
        self.assertEqual(_num("abc", default=1.5), 1.5)


if __name__ == "__main__":
    unittest.main()