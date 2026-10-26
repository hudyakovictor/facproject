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


def test_pose_correction_removes_only_a_pose_that_is_present():
    """R_corr снимает позу ровно из той сетки, где она сидит (замер 01).

    Взяли сетку без позы v0, повёрнули её базисом 3DDFA в ракурс actual, затем
    применяем R_corr(actual -> target). Ожидаем сетку, повёрнутую ровно в target.
    """
    rng = np.random.default_rng(11)
    v0 = rng.normal(size=(300, 3)).astype(np.float32)
    actual, target = [3.0, 24.0, -2.0], [0.0, 17.5, 0.0]
    posed = v0 @ row_rotation_matrix(*actual)
    fixed = apply_pose_correction(posed, full_pose_correction_matrix(actual, target))
    np.testing.assert_allclose(fixed, v0 @ row_rotation_matrix(*target), atol=1e-4)


def test_pose_correction_on_identity_mesh_is_double_rotation():
    """Тот же R_corr на сетке БЕЗ позы — это баг двойного поворота (замер 02).

    `vertices_identity_only` базис 3DDFA строит с нулевой позой, поэтому вычитать
    измеренный yaw второй раз значит довернуть кадр на -yaw сверх нормы. Результат
    обязан отличаться от неизменённой сетки ровно на поворот вокруг Y на -yaw:
    это и есть то, что app9/validation видит как ratio 4.87 против 2.15 у canon.
    """
    rng = np.random.default_rng(12)
    v_id = rng.normal(size=(300, 3)).astype(np.float32)
    yaw = 24.0
    r_corr = full_pose_correction_matrix([0.0, yaw, 0.0], [0.0, 0.0, 0.0])
    over = apply_pose_correction(v_id, r_corr)
    np.testing.assert_allclose(over, v_id @ row_rotation_matrix(0.0, -yaw, 0.0), atol=1e-4)
    # Довернутая сетка не совпадает с исходной: поза, которой не было, реально уехала.
    assert float(np.mean(np.linalg.norm(over - v_id, axis=1))) > 0.1


def test_chronology_correction_does_not_depend_on_measured_pose():
    """Продный путь (reconstruction.run_reconstruction): доворот только к канону бина.

    Для всех кадров одного бина коррекция обязана быть одной и той же матрицей
    Ry(canonical_yaw) и не содержать измеренные pitch/yaw/roll.
    """
    _, canon = classify_pose(24.0)
    assert canon == 17.5
    for measured in ([0.0, 20.0, 0.0], [5.0, 24.9, -3.0], [-4.0, 21.2, 2.0]):
        r_chron = row_rotation_matrix(0.0, nearest_canonical_yaw(measured[1])[1], 0.0)
        np.testing.assert_allclose(r_chron, row_rotation_matrix(0.0, canon, 0.0), atol=1e-6)
