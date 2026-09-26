"""📐 Геометрия поз, проекции и хронологическое каноническое выравнивание (app8).

Гарантирует, что кадры внутри одного pose bin при хронологическом анализе
приводятся к единой канонической позе (0, canonical_yaw, 0) через полную коррекцию
pitch+yaw+roll: R_corr = R_target @ R_actual^T.
"""
from __future__ import annotations
import numpy as np
from .config import POSE_BINS


def classify_pose(yaw: float) -> tuple[str, float]:
    """Классификация позы по углу Yaw в 9 жестких бинов."""
    y = float(yaw)
    if not np.isfinite(y):
        raise ValueError("yaw must be finite")
    for name, lo, hi, canonical in POSE_BINS:
        if lo <= y < hi:
            return name, canonical
    return ("right_profile" if y >= 0 else "left_profile"), float(np.clip(y, -70.0, 70.0))


def nearest_canonical_yaw(yaw: float) -> tuple[str, float]:
    """Soft assignment: выбор ближайшего канонического угла без разрывов на границах."""
    y = float(yaw)
    if not np.isfinite(y):
        raise ValueError("yaw must be finite")
    best_name = "frontal"
    best_canonical = 0.0
    best_dist = float("inf")
    for name, _lo, _hi, canonical in POSE_BINS:
        dist = abs(y - canonical)
        if dist < best_dist:
            best_dist = dist
            best_name = name
            best_canonical = canonical
    return best_name, best_canonical


def row_rotation_matrix(pitch_deg: float, yaw_deg: float, roll_deg: float) -> np.ndarray:
    """Матрица вращения Эйлера (Rz @ Ry @ Rx)^T для row-vector конвенции (V @ R)."""
    p, y, r = np.radians([pitch_deg, yaw_deg, roll_deg])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]], np.float32)
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]], np.float32)
    rz = np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1]], np.float32)
    return (rz @ ry @ rx).T.astype(np.float32)


def full_pose_correction_matrix(actual_pose_deg: list[float] | np.ndarray,
                                target_pose_deg: list[float] | np.ndarray) -> np.ndarray:
    """Вычисляет матрицу перехода R_corr: V_chronology = V_object @ R_corr.
    
    R_corr = R_target @ R_actual^T.
    Устраняет паразитный pitch и roll, фиксируя yaw на каноническом угле бина.
    """
    p_act = np.asarray(actual_pose_deg, np.float32)
    p_tgt = np.asarray(target_pose_deg, np.float32)
    r_actual = row_rotation_matrix(float(p_act[0]), float(p_act[1]), float(p_act[2]))
    r_target = row_rotation_matrix(float(p_tgt[0]), float(p_tgt[1]), float(p_tgt[2]))
    return (r_actual.T @ r_target).astype(np.float32)


def apply_pose_correction(vertices: np.ndarray, r_corr: np.ndarray) -> np.ndarray:
    """Применяет матрицу коррекции позы к 3D-вершинам."""
    v = np.asarray(vertices, np.float32)
    return (v @ r_corr).astype(np.float32)


def to_original_image(points_224: np.ndarray, trans_params: np.ndarray) -> np.ndarray:
    """Отображает координаты плоскости 224x224 назад в пиксели исходного изображения."""
    q = np.asarray(points_224, np.float32).copy()
    if q.ndim != 2 or q.shape[1] < 2:
        raise ValueError("points_224 must have shape (N, 2+)")
    trans = np.asarray(trans_params, np.float64).reshape(-1)
    if trans.size < 5 or not np.isfinite(trans[:5]).all():
        raise ValueError("trans_params must contain five finite values")
    q[:, 1] = 223.0 - q[:, 1]
    w0, h0, scale, cx, cy = map(float, trans[:5])
    w = max(int(w0 * scale), 1)
    h = max(int(h0 * scale), 1)
    left = int(w / 2 - 112 + (cx - w0 / 2) * scale)
    up = int(h / 2 - 112 + (h0 / 2 - cy) * scale)
    q[:, 0] = (q[:, 0] + left) / w * w0
    q[:, 1] = (q[:, 1] + up) / h * h0
    return q.astype(np.float32)
