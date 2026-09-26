"""🧪 Тесты модуля геометрии и хронологического выравнивания (app8)."""
from __future__ import annotations
import numpy as np
import pytest

from app8.geometry import (
    classify_pose,
    nearest_canonical_yaw,
    row_rotation_matrix,
    full_pose_correction_matrix,
    apply_pose_correction,
)
from app8.config import POSE_BINS


def test_classify_pose():
    # Фронт
    assert classify_pose(0.0)[0] == "frontal"
    assert classify_pose(5.0)[0] == "frontal"
    assert classify_pose(-8.0)[0] == "frontal"
    
    # 3/4 и профили
    assert classify_pose(20.0)[0] == "right_light"
    assert classify_pose(35.0)[0] == "right_mid"
    assert classify_pose(45.0)[0] == "right_deep"
    assert classify_pose(70.0)[0] == "right_profile"
    assert classify_pose(-65.0)[0] == "left_profile"


def test_nearest_canonical_yaw_soft():
    name, canon = nearest_canonical_yaw(-12.0)
    assert name == "left_light"
    assert canon == -17.5


def test_pose_correction_matrix():
    # При вращении на [pitch=10, yaw=20, roll=5]
    actual_pose = [10.0, 20.0, 5.0]
    target_pose = [0.0, 17.5, 0.0]  # Канонический угол для right_light
    
    r_corr = full_pose_correction_matrix(actual_pose, target_pose)
    assert r_corr.shape == (3, 3)
    
    # Ортогональность матрицы коррекции (R @ R^T = I)
    eye_check = r_corr @ r_corr.T
    np.testing.assert_allclose(eye_check, np.eye(3), atol=1e-5)
    
    # Проверка выравнивания
    pts = np.array([[1.0, 2.0, 3.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    pts_corr = apply_pose_correction(pts, r_corr)
    assert pts_corr.shape == pts.shape
