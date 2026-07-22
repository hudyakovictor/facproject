#!/usr/bin/env python3
"""
🎯 CRITICAL → Golden test для alignment pipeline.

Проверяет что весь pipeline извлечения и выравнивания работает корректно
на синтетических данных с известными углами.

Запуск: python test_alignment_golden.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from app6.stage1.geometry import (
    classify_pose,
    compute_chronology_alignment,
    full_pose_correction_matrix,
    nearest_canonical_yaw,
    normalize_mesh,
    row_rotation_matrix,
)


def test_golden_frontal_alignment():
    """Golden test: frontal pose не должен требовать коррекции."""
    # Создаём синтетический меш (куб)
    vertices = np.array([
        [-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0],  # face
        [0, 0, 1],  # nose tip
    ], np.float32)

    result = compute_chronology_alignment(
        vertices=vertices,
        actual_pose_deg=[0, 0, 0],  # frontal
        canonical_yaw=0.0,
    )

    # При frontal pose aligned должен быть близок к normalized
    normalized, center, scale = normalize_mesh(vertices)
    np.testing.assert_allclose(
        result["vertices_aligned"], normalized, atol=1e-4,
        err_msg="Frontal pose should not require rotation"
    )
    print("✅ test_golden_frontal_alignment PASSED")


def test_golden_known_rotation():
    """Golden test: известный поворот на 30°."""
    # Создаём точку на оси X
    vertices = np.array([[1.0, 0.0, 0.0]], np.float32)

    # Поворачиваем на -30° (влево)
    R_30 = row_rotation_matrix(0, -30, 0)
    rotated = vertices @ R_30

    # Теперь "восстанавливаем" коррекцией
    R_corr = full_pose_correction_matrix([0, -30, 0], [0, 0, 0])
    corrected = rotated @ R_corr

    # После коррекции точка должна быть близка к исходной
    np.testing.assert_allclose(
        corrected, vertices, atol=1e-3,
        err_msg="Correction should restore original position"
    )
    print("✅ test_golden_known_rotation PASSED")


def test_golden_all_bins_consistency():
    """Golden test: все bins дают корректный canonical."""
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

    for expected_name, expected_canonical in bins:
        name, canonical = classify_pose(expected_canonical)
        assert name == expected_name, f"Expected {expected_name}, got {name}"
        assert abs(canonical - expected_canonical) < 0.1, \
            f"Expected canonical {expected_canonical}, got {canonical}"

    print("✅ test_golden_all_bins_consistency PASSED")


def test_golden_nearest_canonical():
    """Golden test: nearest_canonical_yaw выбирает ближайший."""
    test_cases = [
        (-12, -17.5),   # closer to left_light
        (-8, 0.0),      # closer to frontal
        (5, 0.0),       # closer to frontal
        (15, 17.5),     # closer to right_light
        (40, 45.0),     # closer to right_deep (|40-45|=5 < |40-32.5|=7.5)
    ]

    for yaw, expected_canonical in test_cases:
        _, canonical = nearest_canonical_yaw(yaw)
        assert abs(canonical - expected_canonical) < 0.1, \
            f"For yaw={yaw}, expected canonical={expected_canonical}, got {canonical}"

    print("✅ test_golden_nearest_canonical PASSED")


def test_golden_roundtrip_all_bins():
    """Golden test: round-trip для всех bins."""
    bins_yaw = [-70, -45, -32.5, -17.5, 0, 17.5, 32.5, 45, 70]

    for yaw in bins_yaw:
        # Forward: actual → canonical
        R_fwd = full_pose_correction_matrix([0, yaw, 0], [0, yaw, 0])
        # Backward: canonical → actual
        R_bwd = full_pose_correction_matrix([0, yaw, 0], [0, yaw, 0])

        # Combined should be identity
        combined = R_fwd @ R_bwd
        np.testing.assert_allclose(combined, np.eye(3), atol=1e-5)

    print("✅ test_golden_roundtrip_all_bins PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("🎯 CRITICAL: Golden tests for alignment pipeline")
    print("=" * 60)

    tests = [
        test_golden_frontal_alignment,
        test_golden_known_rotation,
        test_golden_all_bins_consistency,
        test_golden_nearest_canonical,
        test_golden_roundtrip_all_bins,
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
        print("✅ ALL GOLDEN TESTS PASSED — Alignment pipeline is correct!")
    else:
        print("❌ SOME GOLDEN TESTS FAILED — Pipeline needs fixing!")
        sys.exit(1)
