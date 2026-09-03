"""🎯 GUARD → Генератор анатомических mesh-зон (ER-205/геометрия).

generate_zones: сопоставляет вершины с UV-зонами по приоритету (первый
выигравший зону выигрывает), без пересечений зон; вершина вне всех zone-box
не назначается ни в одну зону.
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage2.generate_mesh_zones import generate_zones, ZONE_UV_BOXES


class GenerateZonesTests(unittest.TestCase):
    def test_vertex_in_zone_box_is_assigned(self):
        # Точка строго в box 'forehead' (0.20..0.80, 0.70..0.95).
        uv = np.array([[0.5, 0.8]])
        zones = generate_zones(uv)
        self.assertEqual(zones["forehead"], [0])

    def test_vertex_inside_higher_priority_wins_each_zone_once(self):
        # Точка в перекрытии forehead и brow_ridge_L → одна зона.
        uv = np.array([[0.4, 0.68]])  # brow_ridge_L (0.20..0.45, 0.60..0.72)
        zones = generate_zones(uv)
        assigned = [z for z, idx in zones.items() if 0 in idx]
        self.assertEqual(len(assigned), 1)  # ровно одна зона

    def test_zones_do_not_overlap(self):
        # каждая вершина попадает не более чем в одну зону.
        rng = np.random.default_rng(0)
        uv = rng.uniform(0, 1, (500, 2)).astype(np.float32)
        zones = generate_zones(uv)
        seen: set[int] = set()
        for indices in zones.values():
            for i in indices:
                self.assertNotIn(i, seen)
                seen.add(i)

    def test_vertex_outside_all_boxes_unassigned(self):
        uv = np.array([[0.99, 0.01]])  # вне всех zone box (если не в правом углу)
        zones = generate_zones(uv)
        all_assigned = set().union(*[set(idx) for idx in zones.values()])
        self.assertNotIn(0, all_assigned)

    def test_empty_uv(self):
        zones = generate_zones(np.empty((0, 2), np.float32))
        self.assertTrue(all(idx == [] for idx in zones.values()))

    def test_every_zone_present_in_output(self):
        uv = np.array([[0.5, 0.8], [0.4, 0.68], [0.5, 0.5]])
        zones = generate_zones(uv)
        self.assertEqual(set(zones.keys()), set(ZONE_UV_BOXES.keys()))


if __name__ == "__main__":
    unittest.main()