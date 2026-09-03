"""🎯 GUARD → Stage 1 assets: вычисление bbox (ER-005/ER-018).

assets._bbox: fail-closed bbox из точек с margin, обрезанный по границам
изображения; NaN/недостаточно точек/некорректный ввод → понятная ошибка.
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage1.assets import _bbox


class BboxTests(unittest.TestCase):
    def test_bbox_from_points_with_margin(self):
        points = np.array([[10.0, 20.0], [30.0, 40.0], [15.0, 25.0], [25.0, 35.0]], np.float32)
        shape = (100, 100, 3)
        x1, y1, bw, bh = _bbox(points, shape, margin=0.0)
        self.assertEqual((x1, y1), (10, 20))
        self.assertEqual((bw, bh), (20, 20))

    def test_bbox_clamped_to_image_boundaries(self):
        points = np.array([[-50.0, -50.0], [200.0, 5.0], [0.0, 0.0]], np.float32)
        shape = (100, 100, 3)
        x1, y1, bw, bh = _bbox(points, shape, margin=0.0)
        self.assertGreaterEqual(x1, 0)
        self.assertGreaterEqual(y1, 0)
        self.assertLessEqual(x1 + bw, 100)
        self.assertLessEqual(y1 + bh, 100)

    def test_margin_expands_bbox(self):
        points = np.array([[10.0, 10.0], [12.0, 12.0], [11.0, 11.0]], np.float32)
        shape = (100, 100, 3)
        no_margin = _bbox(points, shape, margin=0.0)
        with_margin = _bbox(points, shape, margin=0.5)
        self.assertGreater(with_margin[2], no_margin[2])

    def test_nan_points_rejected(self):
        points = np.array([[10.0, 10.0], [12.0, 12.0], [float("nan"), 11.0]], np.float32)
        with self.assertRaises(ValueError):
            _bbox(points, (100, 100, 3))

    def test_too_few_points_rejected(self):
        points = np.array([[10.0, 10.0], [12.0, 12.0]], np.float32)
        with self.assertRaises(ValueError):
            _bbox(points, (100, 100, 3))

    def test_invalid_shape_rejected(self):
        points = np.array([[10.0, 10.0], [12.0, 12.0], [11.0, 11.0]], np.float32)
        with self.assertRaises(ValueError):
            _bbox(points, (0, 100, 3))


if __name__ == "__main__":
    unittest.main()