"""📐 Модуль строгой канонической юстировки моделей в (0°, 0°, 0°) для 3D-морфинга."""
from __future__ import annotations
from typing import Any
import numpy as np


def align_identity_mesh_to_zero(recon_data: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, float]:
    """Извлекает 3D-сетку формы identity, строго выравнивает в (0, 0, 0) градусов и центрирует.
    
    Returns:
        tuple: (нормализованные вершины (35709, 3), 106 канонических точек (106, 3), масштабный коэффициент)
    """
    # 1. Используем чистую форму лица без экспрессий и без угла съемки
    v_id = np.asarray(recon_data["vertices_identity_only"], dtype=np.float32).copy()
    
    # 2. Выравнивание центра черепа строго в (0, 0, 0)
    center = np.mean(v_id, axis=0)
    v_aligned = v_id - center
    
    # 3. Инвариантная нормализация масштаба по краниометрическому радиусу
    scale = float(np.max(np.linalg.norm(v_aligned, axis=1)))
    if scale > 1e-4:
        v_aligned /= scale
        
    # 4. Извлечение 106 ключевых точек
    ldm106_idx = np.asarray(recon_data["ldm106_indices"], dtype=np.int64)
    ldm106_pts = v_aligned[ldm106_idx]
    
    return v_aligned, ldm106_pts, scale
