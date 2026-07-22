#!/usr/bin/env python3
"""
🎯 CRITICAL → Standalone тест для full_pose_correction_matrix.
Не требует cv2 или других тяжёлых зависимостей.
Запуск: python test_pose_correction_standalone.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

# Импортируем только geometry (без engine)
from app6.stage1.geometry import (
    full_pose_correction_matrix,
    compute_chronology_alignment,
    row_rotation_matrix,
)


def test_correction_is_orthonormal():
    """Матрица коррекции должна быть ортогональной с det=1."""
    test_cases = [
        ([0, -24, 0], [0, -17.5, 0]),
        ([0, 24, 0], [0, 17.5, 0]),
        ([5, -30, -3], [0, -32.5, 0]),
        ([0, 0, 0], [0, 0, 0]),
        ([10, -50, 5], [0, -45, 0]),
    ]
    for actual, target in test_cases:
        R = full_pose_correction_matrix(actual, target)
        # Ортогональность
        product = R.T @ R
        assert np.allclose(product, np.eye(3), atol=1e-5), \
            f"Failed orthonormality for {actual}->{target}: R^T@R={product}"
        # det=1
        det = float(np.linalg.det(R))
        assert abs(det - 1.0) < 1e-4, \
            f"Failed det for {actual}->{target}: det={det}"
    print("✅ test_correction_is_orthonormal PASSED")


def test_correction_direction_yaw():
    """Проверка направления коррекции для yaw."""
    point = np.array([[1.0, 0.0, 0.0]], np.float32)

    # actual=-24° (влево), target=-17.5° (ближе к фронтальному)
    R = full_pose_correction_matrix([0, -24, 0], [0, -17.5, 0])
    corrected = point @ R

    # После коррекции z-компонента должна быть отрицательной
    # (yaw-вращение происходит вокруг вертикальной оси Y: точка на оси X
    # смещается в плоскости XZ; y остаётся 0, знак z задаёт направление)
    assert corrected[0, 1] == 0, \
        f"Expected y unchanged after yaw correction, got {corrected[0, 1]}"
    assert corrected[0, 2] < 0, \
        f"Expected negative z after correction, got {corrected[0, 2]}"
    print("✅ test_correction_direction_yaw PASSED")


def test_correction_magnitude():
    """Проверка величины коррекции."""
    R = full_pose_correction_matrix([0, -24, 0], [0, -17.5, 0])

    trace = float(np.trace(R))
    angle_rad = np.arccos(np.clip((trace - 1) / 2, -1, 1))
    angle_deg = np.degrees(angle_rad)

    assert abs(angle_deg - 6.5) < 0.5, \
        f"Expected ~6.5° rotation, got {angle_deg:.2f}°"
    print(f"✅ test_correction_magnitude PASSED (angle={angle_deg:.2f}°)")


def test_roundtrip_correction():
    """Round-trip: коррекция и обратная должны дать единичную."""
    actual = [5, -30, -3]
    target = [0, -32.5, 0]

    R_forward = full_pose_correction_matrix(actual, target)
    R_backward = full_pose_correction_matrix(target, actual)

    combined = R_forward @ R_backward
    assert np.allclose(combined, np.eye(3), atol=1e-5), \
        f"Round-trip failed: R_fwd @ R_bwd = {combined}"
    print("✅ test_roundtrip_correction PASSED")


def test_chronology_alignment_finite():
    """compute_chronology_alignment должна давать конечные значения."""
    rng = np.random.default_rng(42)
    vertices = rng.normal(size=(100, 3)).astype(np.float32)

    result = compute_chronology_alignment(
        vertices=vertices,
        actual_pose_deg=[5, -30, -3],
        canonical_yaw=-32.5,
    )

    assert np.isfinite(result["vertices_aligned"]).all(), \
        "Alignment produced NaN/Inf"
    assert result["vertices_aligned"].shape == vertices.shape
    print("✅ test_chronology_alignment_finite PASSED")


def test_all_pose_bins():
    """Тест для всех 9 pose bins."""
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
        if "left" in bin_name:
            actual_yaw = canonical_yaw - 3
        elif "right" in bin_name:
            actual_yaw = canonical_yaw + 3
        else:
            actual_yaw = canonical_yaw + 0  # frontal

        R = full_pose_correction_matrix(
            [0, actual_yaw, 0], [0, canonical_yaw, 0]
        )

        assert np.allclose(R.T @ R, np.eye(3), atol=1e-5), \
            f"Failed orthonormality for {bin_name}"
        assert abs(float(np.linalg.det(R)) - 1.0) < 1e-4, \
            f"Failed det for {bin_name}"

    print("✅ test_all_pose_bins PASSED")


def test_pitch_roll_correction():
    """Проверка что pitch и roll тоже корректируются."""
    # actual с pitch=5°, roll=-3°
    R = full_pose_correction_matrix([5, -30, -3], [0, -30, 0])

    # Коррекция должна убрать pitch и roll
    # (поворот вокруг X и Z осей)
    # Проверяем что R ≠ I (есть реальная коррекция)
    assert not np.allclose(R, np.eye(3), atol=1e-3), \
        "Correction should be non-trivial for pitch/roll"

    # Проверяем ортогональность
    assert np.allclose(R.T @ R, np.eye(3), atol=1e-5)
    print("✅ test_pitch_roll_correction PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("🎯 CRITICAL: Testing full_pose_correction_matrix")
    print("=" * 60)

    tests = [
        test_correction_is_orthonormal,
        test_correction_direction_yaw,
        test_correction_magnitude,
        test_roundtrip_correction,
        test_chronology_alignment_finite,
        test_all_pose_bins,
        test_pitch_roll_correction,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} ERROR: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("✅ ALL TESTS PASSED — Formula is correct!")
    else:
        print("❌ SOME TESTS FAILED — Formula needs fixing!")
        sys.exit(1)
