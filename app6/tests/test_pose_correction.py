from __future__ import annotations

import unittest
import numpy as np

from app6.stage1.geometry import (
    classify_pose,
    compute_chronology_alignment,
    full_pose_correction_matrix,
    normalize_mesh,
    row_rotation_matrix,
)


class PoseCorrectionTests(unittest.TestCase):
    """🎯 CRITICAL → Тесты для full_pose_correction_matrix.

    Если эти тесты падают — ВСЕ хронологические данные некорректны!
    Формула должна преобразовать меш из actual_pose в target_pose.
    """

    def test_correction_is_orthonormal(self):
        """Матрица коррекции должна быть ортогональной с det=1."""
        test_cases = [
            ([0, -24, 0], [0, -17.5, 0]),   # left_light bin
            ([0, 24, 0], [0, 17.5, 0]),     # right_light bin
            ([5, -30, -3], [0, -32.5, 0]),  # left_mid with pitch/roll
            ([0, 0, 0], [0, 0, 0]),         # frontal (no correction)
            ([10, -50, 5], [0, -45, 0]),    # left_deep
        ]
        for actual, target in test_cases:
            with self.subTest(actual=actual, target=target):
                R = full_pose_correction_matrix(actual, target)
                # Ортогональность: R^T @ R = I
                np.testing.assert_allclose(R.T @ R, np.eye(3), atol=1e-5)
                # det(R) = 1 (proper rotation, not reflection)
                self.assertAlmostEqual(float(np.linalg.det(R)), 1.0, places=4)

    def test_correction_direction_yaw(self):
        """Проверка направления коррекции для yaw.
        Если actual=-24°, target=-17.5°, коррекция должна быть +6.5° (к target).
        """
        # Создаём точку на оси X (нос)
        point = np.array([[1.0, 0.0, 0.0]], np.float32)

        # actual=-24° (повёрнут влево), target=-17.5° (ближе к фронтальному)
        # Коррекция должна повернуть точку П часовой стрелке (к фронтальному)
        R = full_pose_correction_matrix([0, -24, 0], [0, -17.5, 0])
        corrected = point @ R

        # После коррекции z-компонента должна быть отрицательной
        # (yaw-вращение происходит вокруг вертикальной оси Y: точка на оси X
        # смещается в плоскости XZ; y остаётся 0, знак z задаёт направление)
        self.assertEqual(corrected[0, 1], 0,
                         "y should be unchanged after yaw correction")
        self.assertLess(corrected[0, 2], 0,
                        "Correction should rotate towards target (front)")

    def test_correction_magnitude(self):
        """Проверка величины коррекции.
        Разница между actual и target должна соответствовать углу поворота.
        """
        # actual=-24°, target=-17.5°, разница=6.5°
        R = full_pose_correction_matrix([0, -24, 0], [0, -17.5, 0])

        # Для малых углов, угол поворота ≈ arccos((trace(R)-1)/2)
        trace = float(np.trace(R))
        angle_rad = np.arccos(np.clip((trace - 1) / 2, -1, 1))
        angle_deg = np.degrees(angle_rad)

        # Ожидаем ~6.5° (с допуском на точность)
        self.assertAlmostEqual(angle_deg, 6.5, delta=0.5,
                               msg=f"Expected ~6.5° rotation, got {angle_deg:.2f}°")

    def test_roundtrip_correction(self):
        """Round-trip: применение коррекции и обратной должно дать исходное."""
        actual = [5, -30, -3]
        target = [0, -32.5, 0]

        R_forward = full_pose_correction_matrix(actual, target)
        R_backward = full_pose_correction_matrix(target, actual)

        # R_forward @ R_backward должна быть единичной
        combined = R_forward @ R_backward
        np.testing.assert_allclose(combined, np.eye(3), atol=1e-5)

    def test_chronology_alignment_produces_finite(self):
        """compute_chronology_alignment должна давать конечные значения."""
        rng = np.random.default_rng(42)
        vertices = rng.normal(size=(100, 3)).astype(np.float32)

        result = compute_chronology_alignment(
            vertices=vertices,
            actual_pose_deg=[5, -30, -3],
            canonical_yaw=-32.5,
        )

        self.assertTrue(np.isfinite(result["vertices_aligned"]).all())
        self.assertEqual(result["vertices_aligned"].shape, vertices.shape)

    def test_chronology_alignment_preserves_shape(self):
        """Alignment должен сохранять форму меша (только поворот + scale)."""
        rng = np.random.default_rng(42)
        vertices = rng.normal(size=(100, 3)).astype(np.float32)

        result = compute_chronology_alignment(
            vertices=vertices,
            actual_pose_deg=[0, 0, 0],  # frontal, no rotation needed
            canonical_yaw=0.0,
        )

        # При frontal pose расстояния между вершинами должны сохраниться
        # (только scale меняется)
        orig_dists = np.linalg.norm(vertices[1:] - vertices[:-1], axis=1)
        aligned_dists = np.linalg.norm(
            result["vertices_aligned"][1:] - result["vertices_aligned"][:-1], axis=1
        )

        # Отношение расстояний должно быть постоянным (scale)
        ratios = aligned_dists / (orig_dists + 1e-8)
        np.testing.assert_allclose(ratios, ratios[0], atol=1e-4)

    def test_all_pose_bins(self):
        """Тест для всех 9 pose bins: коррекция должна работать."""
        bins = [
            ("left_profile", -70.0),
            ("left_deep", -45.0),
            ("left_mid", -32.5),
            ("left_light", -17.5),
            ("frontal", 0.0),
            ("right_light", 17.5),
            ("right_mid", 32.5),
            ("right_deep", 45.0),
            ("right_profile", 70.0),
        ]

        for bin_name, canonical_yaw in bins:
            with self.subTest(bin=bin_name):
                # Создаём реальный yaw внутри бина
                if "left" in bin_name:
                    actual_yaw = canonical_yaw - 3  # внутри бина
                else:
                    actual_yaw = canonical_yaw + 3

                R = full_pose_correction_matrix(
                    [0, actual_yaw, 0], [0, canonical_yaw, 0]
                )

                # Проверяем что коррекция — proper rotation
                np.testing.assert_allclose(R.T @ R, np.eye(3), atol=1e-5)
                self.assertAlmostEqual(float(np.linalg.det(R)), 1.0, places=4)


if __name__ == "__main__":
    unittest.main()
