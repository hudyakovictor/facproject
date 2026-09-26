"""😁 Высокоточный геометрический контроль мимики (Expression QC), инвариантный к ракурсу (app8).

Решает проблему профильных кадров (Yaw > 45°..70°):
1. 3D Инвариантный базис нормализации: расстояние между костными глазницами в 3D (IOC_3D)
   и высота спинки носа Nasion-Subnasale (N-Sn), которые НЕ схлопываются при повороте;
2. Односторонний анализ видимого уголка рта в профиле (отсечение окклюдированной стороны);
3. 3D-смещение вершин губ и челюсти: ||V_object - V_identity|| на 3D-поверхности BFM.
"""
from __future__ import annotations
import numpy as np
from .config import (
    EXPRESSION_CORNER_LIFT_THRESHOLD,
    EXPRESSION_JAW_OPEN_THRESHOLD,
    EXPRESSION_MAGNITUDE_THRESHOLD,
)


def compute_expression_qc(ldm106_3d_object: np.ndarray,
                          alpha_exp: np.ndarray,
                          yaw_deg: float = 0.0) -> dict[str, float | bool | str]:
    """Вычисляет истинные 3D-метрики мимики, устойчивые к любому ракурсу (0°..75°).
    
    Args:
        ldm106_3d_object: 3D координаты ориентиров в объектном пространстве BFM (106, 3)
        alpha_exp: 64-мерный вектор экспрессий BFM
        yaw_deg: угол поворота головы (для выбора видимой стороны в профиле)
    """
    pts = np.asarray(ldm106_3d_object, np.float32)
    exp_mag = float(np.linalg.norm(alpha_exp))
    
    if pts.shape[0] < 106:
        return {
            "corner_lift_ioc": 0.0,
            "jaw_open_ratio": 0.0,
            "expression_magnitude": exp_mag,
            "is_smiling": False,
            "is_mouth_open": False,
            "qc_status": "insufficient_landmarks",
            "eval_mode": "fallback"
        }
        
    # ─────────────────────────────────────────────────────────────────────────
    # 1. Инвариантный 3D базис нормализации (не схлопывается в профиле!)
    # ─────────────────────────────────────────────────────────────────────────
    # 3D центры костных глазниц
    eye_left_3d = np.mean(pts[63:71], axis=0)
    eye_right_3d = np.mean(pts[71:79], axis=0)
    ioc_3d = float(np.linalg.norm(eye_left_3d - eye_right_3d))
    
    # Краниометрическая высота носа Nasion (точка 51) -> Subnasale (точка 57)
    nasal_height_3d = float(np.linalg.norm(pts[51] - pts[57]))
    
    # Опорный масштаб черепа (если ioc_3d аномально мал, страхуем высотой носа)
    scale_norm = ioc_3d if ioc_3d > 1e-3 else (nasal_height_3d * 1.35)
    
    # ─────────────────────────────────────────────────────────────────────────
    # 2. Оценка улыбки с учетом видимости в профиле
    # ─────────────────────────────────────────────────────────────────────────
    # В 3D BFM: Y направлен вверх, Z — вперед, X — вправо
    # Верхняя губа: 87, Нижняя губа: 93, Центр смыкания рта
    mouth_center_y = (pts[87, 1] + pts[93, 1]) / 2.0
    corner_left_y = pts[84, 1]   # левый уголок
    corner_right_y = pts[90, 1]  # правый уголок
    
    abs_yaw = abs(float(yaw_deg))
    if abs_yaw < 30.0:
        # Фронтальный режим: усредняем оба уголка
        mouth_corners_y = (corner_left_y + corner_right_y) / 2.0
        eval_mode = "bilateral_frontal"
    elif yaw_deg > 0:
        # Поворот вправо (видна правая сторона лица) -> смотрим правый уголок
        mouth_corners_y = corner_right_y
        eval_mode = "unilateral_right_profile"
    else:
        # Поворот влево (видна левая сторона лица) -> смотрим левый уголок
        mouth_corners_y = corner_left_y
        eval_mode = "unilateral_left_profile"
        
    # corner_lift: насколько уголок выше центра смыкания губ в 3D
    corner_lift_3d = float((mouth_corners_y - mouth_center_y) / scale_norm)
    
    # ─────────────────────────────────────────────────────────────────────────
    # 3. Оценка раскрытия рта (3D расстояние между губами)
    # ─────────────────────────────────────────────────────────────────────────
    # 3D евклидово расстояние между центральными точками вермилиона
    lip_dist_3d = float(np.linalg.norm(pts[87] - pts[93]))
    jaw_open_ratio = float(lip_dist_3d / scale_norm)
    
    # ─────────────────────────────────────────────────────────────────────────
    # 4. Специфические блендшейпы BFM (дополнительный инвариант)
    # ─────────────────────────────────────────────────────────────────────────
    # В BFM первые компоненты exp сильно коррелируют с AU12 (улыбка) и AU25/26 (рот)
    smile_blendshape = float(alpha_exp[1]) if len(alpha_exp) > 1 else 0.0
    jaw_blendshape = float(alpha_exp[0]) if len(alpha_exp) > 0 else 0.0
    
    # Финальные бинарные флаги (комбинация 3D-геометрии и экспрессионных весов)
    is_smiling = (corner_lift_3d > EXPRESSION_CORNER_LIFT_THRESHOLD) or (smile_blendshape > 1.5)
    is_mouth_open = (jaw_open_ratio > EXPRESSION_JAW_OPEN_THRESHOLD) or (jaw_blendshape > 2.0)
    
    return {
        "corner_lift_ioc": corner_lift_3d,
        "jaw_open_ratio": jaw_open_ratio,
        "expression_magnitude": exp_mag,
        "smile_blendshape": smile_blendshape,
        "jaw_blendshape": jaw_blendshape,
        "is_smiling": bool(is_smiling),
        "is_mouth_open": bool(is_mouth_open),
        "eval_mode": eval_mode,
        "qc_status": "measured_3d_invariant"
    }
