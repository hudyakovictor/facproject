"""🎯 GUARD → Дифференциальное вычитание углового шума (ER-158 / ER-118).

angle_noise: при отсутствии подходящей калибровочной пары — angle_noise_uncompensated,
метрика остаётся сырой (подстановка нуля запрещена). При подобранной паре метрика
компенсируется с зажимом в неотрицательность (шум не может объяснить больше всего
наблюдаемого).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from app6.stage2.angle_noise import (
    angle_delta,
    find_matching_calibration_pair,
    subtract_angle_noise,
)


class AngleDeltaTests(unittest.TestCase):
    def test_absolute_difference(self):
        d = angle_delta([1.0, 2.0, 3.0], [4.0, 0.0, 1.0])
        self.assertEqual(d, {"pitch": 3.0, "yaw": 2.0, "roll": 2.0})

    def test_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            angle_delta([1.0, 2.0], [0.0, 0.0, 0.0])

    def test_rejects_nonfinite(self):
        with self.assertRaises(ValueError):
            angle_delta([float("nan"), 0.0, 0.0], [0.0, 0.0, 0.0])


class FindMatchingPairTests(unittest.TestCase):
    def test_no_match_within_tolerance_returns_none(self):
        target = {"yaw": 1.0, "pitch": 1.0, "roll": 1.0}
        pairs = [{"delta": {"yaw": 10.0, "pitch": 0.0, "roll": 0.0}}]
        self.assertIsNone(find_matching_calibration_pair(target, pairs, tolerance={"yaw": 2.0}))

    def test_matches_within_tolerance(self):
        target = {"yaw": 1.0, "pitch": 1.0, "roll": 1.0}
        pairs = [{"delta": {"yaw": 1.2, "pitch": 0.8, "roll": 1.1}}]
        match = find_matching_calibration_pair(target, pairs)
        self.assertIsNotNone(match)

    def test_pose_bin_filter(self):
        target = {"yaw": 1.0, "pitch": 1.0, "roll": 1.0}
        pairs = [{"delta": {"yaw": 1.0, "pitch": 1.0, "roll": 1.0}, "pose_bin": "frontal"}]
        self.assertIsNone(find_matching_calibration_pair(target, pairs, pose_bin="left_light"))
        self.assertIsNotNone(find_matching_calibration_pair(target, pairs, pose_bin="frontal"))

    def test_picks_nearest_pair(self):
        target = {"yaw": 0.0, "pitch": 0.0, "roll": 0.0}
        far = {"delta": {"yaw": 1.9, "pitch": 0.0, "roll": 0.0}}
        near = {"delta": {"yaw": 0.1, "pitch": 0.0, "roll": 0.0}}
        match = find_matching_calibration_pair(target, [far, near], tolerance={"yaw": 2.0})
        self.assertEqual(match, {**near, "match_distance": 0.1})


class SubtractAngleNoiseTests(unittest.TestCase):
    _PAIR = {"angles_a": [1.0, 2.0, 3.0], "angles_b": [4.0, 0.0, 1.0]}

    def test_requires_angles(self):
        with self.assertRaises(KeyError):
            subtract_angle_noise({"pose_bin": "frontal"}, [])

    def test_no_match_keeps_raw_metric(self):
        pair = {**self._PAIR, "ldm134_rmse": 5.0}
        out = subtract_angle_noise(pair, [])
        self.assertTrue(out["angle_noise_uncompensated"])
        # Подстановки нуля нет: сырая метрика не появляется как компенсированная.
        self.assertNotIn("ldm134_rmse_angle_compensated", out)
        self.assertEqual(out["angle_noise_match"], None)

    def test_compensates_and_clamps_nonnegative(self):
        pair = {**self._PAIR, "ldm134_rmse": 5.0}
        calibration_pairs = [{
            "delta": {"yaw": 2.0, "pitch": 3.0, "roll": 2.0},
            "pose_bin": None,
            "metrics": {"ldm134_rmse": 2.0},
        }]
        out = subtract_angle_noise(pair, calibration_pairs)
        self.assertFalse(out["angle_noise_uncompensated"])
        self.assertEqual(out["ldm134_rmse_angle_compensated"], 3.0)
        self.assertEqual(out["ldm134_rmse_angle_noise"], 2.0)

    def test_compensation_never_makes_metric_negative(self):
        # Шум больше наблюдаемого → компенсированное значение зажимается в 0.
        pair = {**self._PAIR, "ldm106_rmse": 1.0}
        calibration_pairs = [{
            # delta совпадает с фактическим angle_delta пары (pitch3,yaw2,roll2).
            "delta": {"yaw": 2.0, "pitch": 3.0, "roll": 2.0},
            "metrics": {"ldm106_rmse": 5.0},
        }]
        out = subtract_angle_noise(pair, calibration_pairs)
        self.assertEqual(out["ldm106_rmse_angle_compensated"], 0.0)


class ProductionIntegrationTests(unittest.TestCase):
    def test_stage2_engine_integrates_angle_noise(self):
        source = (Path(__file__).parents[1] / "stage2" / "engine.py").read_text(encoding="utf-8")
        self.assertIn("build_calibration_pair_index", source)
        self.assertIn("subtract_angle_noise", source)
        self.assertIn("angle_fields", source)


if __name__ == "__main__":
    unittest.main()