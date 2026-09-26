"""🧪 Тесты инвариантного контроля мимики (app8)."""
from __future__ import annotations
import numpy as np
import pytest

from app8.expression_qc import compute_expression_qc


def test_expression_qc_frontal_and_profile():
    # 106 опорных точек в 3D
    pts = np.random.randn(106, 3).astype(np.float32)
    # Фиксируем реалистичные координаты глаз и рта
    pts[63:71] = np.array([-30.0, 30.0, 0.0])  # Левый глаз
    pts[71:79] = np.array([+30.0, 30.0, 0.0])  # Правый глаз
    pts[51] = np.array([0.0, 40.0, 10.0])      # Nasion
    pts[57] = np.array([0.0, 0.0, 15.0])       # Subnasale
    pts[87] = np.array([0.0, -15.0, 12.0])     # Верхняя губа
    pts[93] = np.array([0.0, -25.0, 10.0])     # Нижняя губа
    pts[84] = np.array([-20.0, -12.0, 8.0])    # Левый уголок (улыбка вверх)
    pts[90] = np.array([+20.0, -12.0, 8.0])    # Правый уголок
    
    alpha_exp = np.zeros(64, dtype=np.float32)
    
    # 1. Фронтальный тест (yaw = 0°)
    qc_front = compute_expression_qc(pts, alpha_exp, yaw_deg=0.0)
    assert qc_front["eval_mode"] == "bilateral_frontal"
    assert qc_front["corner_lift_ioc"] > 0
    assert np.isfinite(qc_front["jaw_open_ratio"])
    
    # 2. Тест профиля вправо (yaw = +70°)
    qc_prof_r = compute_expression_qc(pts, alpha_exp, yaw_deg=70.0)
    assert qc_prof_r["eval_mode"] == "unilateral_right_profile"
    assert np.isfinite(qc_prof_r["corner_lift_ioc"])
    assert np.isfinite(qc_prof_r["jaw_open_ratio"])
    
    # 3. Тест профиля влево (yaw = -65°)
    qc_prof_l = compute_expression_qc(pts, alpha_exp, yaw_deg=-65.0)
    assert qc_prof_l["eval_mode"] == "unilateral_left_profile"
    assert np.isfinite(qc_prof_l["corner_lift_ioc"])
    assert np.isfinite(qc_prof_l["jaw_open_ratio"])
