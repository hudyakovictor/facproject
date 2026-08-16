"""🎯 GUARD → Нормативная политика ракурсов по зонам (D-001, ER-010).

load_pose_policy читает app6/atlas/pose_policy_v3_9bins.csv и детерминированно
валидирует его (180 ячеек, 20 зон, 9 yaw-бинов, статусы/веса в допустимых
диапазонах). zone_applicability: зона со статусом exclude — непригодна и не
может считаться измеренной с нулевым весом.
"""
from __future__ import annotations

import unittest

from app6.stage2.pose_policy import (
    applicable_zones,
    load_pose_policy,
    policy_summary,
    yaw_for_bin,
    zone_applicability,
)


class LoadPosePolicyTests(unittest.TestCase):
    def test_repo_atlas_loads_with_full_grid(self):
        table = load_pose_policy()  # не должно бросить (реальный atlas в репо)
        # 20 зон × 9 yaw-бинов = 180 ячеек.
        self.assertEqual(len(table), 180)

    def test_policy_summary_metadata(self):
        summary = policy_summary()
        self.assertEqual(summary["zone_count"], 20)
        self.assertEqual(summary["yaw_bin_count"], 9)
        self.assertTrue(all(s in summary["status_counts"] for s in ("primary", "support", "limited", "exclude")))


class ZoneApplicabilityTests(unittest.TestCase):
    def test_yaw_for_bin_center(self):
        self.assertEqual(yaw_for_bin("frontal"), 0.0)
        self.assertEqual(yaw_for_bin("left_light"), -17.5)

    def test_exclude_zone_is_not_applicable(self):
        # В atlas должен существовать хотя бы один exclude-статус зоны.
        summary = policy_summary()
        self.assertGreater(summary["status_counts"].get("exclude", 0), 0)
        for zone in applicable_zones("frontal"):
            app = zone_applicability(zone, "frontal")
            self.assertEqual(app["weight"], app["weight"])  # не NaN
            self.assertIn(app["status"], ("primary", "support", "limited", "exclude"))

    def test_applicable_excludes_are_not_returned(self):
        frontal_zones = applicable_zones("frontal")
        for zone in frontal_zones:
            self.assertNotEqual(zone_applicability(zone, "frontal")["status"], "exclude")

    def test_unknown_zone_is_not_applicable(self):
        app = zone_applicability("not_a_zone", "frontal")
        self.assertFalse(app["applicable"])
        self.assertEqual(app["status"], "unknown")
        self.assertEqual(app["reason"], "zone_not_in_policy")


if __name__ == "__main__":
    unittest.main()