"""Regression tests for Stage 1 geometry input contracts."""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage1.geometry import (
    compute_chronology_alignment,
    full_pose_correction_matrix,
    normalize_mesh_landmark_anchored,
    reprojection_stats,
    to_original_image,
)


class Stage1GeometryContractTest(unittest.TestCase):
    def test_pose_correction_rejects_wrong_shape(self) -> None:
        with self.assertRaises(ValueError):
            full_pose_correction_matrix([0.0, 1.0], [0.0, 0.0, 0.0])

    def test_chronology_alignment_rejects_unknown_normalization(self) -> None:
        mesh = np.arange(30, dtype=np.float32).reshape(10, 3)
        with self.assertRaises(ValueError):
            compute_chronology_alignment(mesh, [0.0, 0.0, 0.0], 0.0, normalization="typo")

    def test_landmark_normalization_rejects_bad_anchor(self) -> None:
        mesh = np.arange(30, dtype=np.float32).reshape(10, 3)
        with self.assertRaises(IndexError):
            normalize_mesh_landmark_anchored(mesh, anchor_pair=(0, 99))

    def test_original_mapping_rejects_invalid_transform(self) -> None:
        with self.assertRaises(ValueError):
            to_original_image(np.zeros((1, 2), np.float32), [100, 100, 0, 50, 50])

    def test_reprojection_rejects_empty_arrays(self) -> None:
        with self.assertRaises(ValueError):
            reprojection_stats(np.empty((0, 2)), np.empty((0, 2)))


if __name__ == "__main__":
    unittest.main()
