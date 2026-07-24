"""Regression tests for Stage 2 applicability gates."""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage2.chronology import apply_chronology_rate_flags
from app6.stage2.core import Record, compare_landmarks
from app6.stage2.motion import aligned_point_motion


def _record(record_id: str, pose_bin: str, angles: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Record:
    points106 = np.zeros((106, 3), dtype=np.float32)
    points134 = np.zeros((134, 3), dtype=np.float32)
    return Record(
        record_id=record_id,
        dataset_id="test",
        date="2000-01-01",
        sequence=1,
        pose_bin=pose_bin,
        angles=np.asarray(angles, dtype=np.float32),
        ldm106=points106,
        ldm134=points134,
        visible106=np.ones(106, dtype=bool),
        visible134=np.ones(134, dtype=bool),
        alpha_id=np.zeros(80, dtype=np.float32),
        alpha_exp=np.zeros(64, dtype=np.float32),
    )


class Stage2QualityGateTest(unittest.TestCase):
    def test_compare_landmarks_rejects_cross_bin_pair(self) -> None:
        result = compare_landmarks(
            _record("a", "frontal"),
            _record("b", "right_light"),
            np.full(106, "zone"),
            np.full(134, "zone"),
        )
        self.assertEqual(result.status, "pose_mismatch")
        self.assertEqual(result.metrics, {})
        self.assertEqual(result.diagnostics["pose_bin_a"], "frontal")
        self.assertEqual(result.diagnostics["pose_bin_b"], "right_light")

    def test_chronology_excludes_low_alignment_pair(self) -> None:
        row = {
            "pair_type": "adjacent",
            "pose_bin": "frontal",
            "date_a": "2000-01-01",
            "date_b": "2000-01-02",
            "alignment_quality_a": 0.3,
            "alignment_quality_b": 0.9,
            "p95_point_z": 20.0,
            "coherent_motion_fraction": 0.9,
            "significant_point_fraction": 0.9,
            "status": "coherent_jump_candidate",
        }
        refs = apply_chronology_rate_flags([row])
        self.assertEqual(refs, {})
        self.assertEqual(row["chronology_rate_status"], "excluded")
        self.assertEqual(row["chronology_rate_reason"], "alignment_quality_low")

    def test_compare_landmarks_rejects_large_residual_pose_delta(self) -> None:
        result = compare_landmarks(
            _record("a", "frontal", (0.0, -9.0, 0.0)),
            _record("b", "frontal", (40.0, 9.0, 25.0)),
            np.full(106, "zone"),
            np.full(134, "zone"),
        )
        self.assertEqual(result.status, "residual_pose_mismatch")
        self.assertGreater(result.diagnostics["pose_distance"], 2.5)

    def test_motion_rejects_cross_bin_pair(self) -> None:
        result = aligned_point_motion(
            _record("a", "frontal"), _record("b", "right_light"), 134
        )
        self.assertEqual(result["status"], "pose_mismatch")

    def test_motion_rejects_unsupported_landmark_count(self) -> None:
        with self.assertRaises(ValueError):
            aligned_point_motion(_record("a", "frontal"), _record("b", "frontal"), 68)

    def test_chronology_excludes_strong_expression_pair(self) -> None:
        row = {
            "pair_type": "adjacent",
            "pose_bin": "frontal",
            "date_a": "2000-01-01",
            "date_b": "2000-01-02",
            "expression_magnitude_a": 0.2,
            "expression_magnitude_b": 2.0,
            "p95_point_z": 20.0,
            "coherent_motion_fraction": 0.9,
            "significant_point_fraction": 0.9,
            "status": "coherent_jump_candidate",
        }
        apply_chronology_rate_flags([row])
        self.assertEqual(row["chronology_rate_status"], "excluded")
        self.assertEqual(row["chronology_rate_reason"], "expression_too_strong")


if __name__ == "__main__":
    unittest.main()
