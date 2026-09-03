"""🎯 GUARD → Legacy-атлас зон: чистые правила роли и UV-центроиды.

skin_zone_atlas_final (отдельно от канонического skin_zone_atlas, НЕ подключён
в пайплайн). Здесь проверяются его чистые функции: triangle_centroids_uv и
zone_role_for_pose — правила применимости зоны по pose bin (D-001).
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage1.skin_zone_atlas_final import ZONES, triangle_centroids_uv, zone_role_for_pose


def _zone(side: str):
    return next(z for z in ZONES if z.side == side)


class TriangleCentroidsTests(unittest.TestCase):
    def test_centroid_is_mean_uv(self):
        uv = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], np.float32)
        tri = np.array([[0, 1, 2]], np.int64)
        c = triangle_centroids_uv(uv, tri)
        np.testing.assert_allclose(c[0], [1 / 3, 1 / 3], atol=1e-6)

    def test_multiple_triangles(self):
        uv = np.array([[0, 0], [2, 0], [0, 2], [2, 2]], np.float32)
        tri = np.array([[0, 1, 2], [1, 2, 3]], np.int64)
        c = triangle_centroids_uv(uv, tri)
        self.assertEqual(c.shape, (2, 2))
        np.testing.assert_allclose(c[0], [2 / 3, 2 / 3], atol=1e-5)
        np.testing.assert_allclose(c[1], [4 / 3, 4 / 3], atol=1e-5)


class ZoneRoleForPoseTests(unittest.TestCase):
    def test_frontal_always_primary(self):
        for side in ("midline", "left", "right"):
            self.assertEqual(zone_role_for_pose(_zone(side), "frontal"), "primary")

    def test_midline_supports_light_or_mid(self):
        midline = _zone("midline")
        self.assertEqual(zone_role_for_pose(midline, "left_light"), "primary")
        self.assertEqual(zone_role_for_pose(midline, "right_mid"), "primary")
        self.assertEqual(zone_role_for_pose(midline, "left_profile"), "support")

    def test_left_zone_left_pose_primary_not_profile(self):
        left = _zone("left")
        self.assertEqual(zone_role_for_pose(left, "left_light"), "primary")
        self.assertEqual(zone_role_for_pose(left, "left_profile"), "support")

    def test_contralateral_profile_excluded(self):
        left = _zone("left")
        self.assertEqual(zone_role_for_pose(left, "right_profile"), "exclude")

    def test_contralateral_light_supported(self):
        left = _zone("left")
        self.assertEqual(zone_role_for_pose(left, "right_light"), "support")

    def test_contralateral_mid_limited(self):
        left = _zone("left")
        self.assertEqual(zone_role_for_pose(left, "right_mid"), "limited")


if __name__ == "__main__":
    unittest.main()