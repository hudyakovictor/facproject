"""👁️ Расчет карты достоверности видимости и Z-Buffer отсечение (app8).

Объединяет:
1. Z-Buffer видимость (renderer_visible);
2. Направление нормалей к камере (front_facing: normal_z > 0);
3. Ошибку 2D-репроекции для фильтрации краевых артефактов силуэта.
"""
from __future__ import annotations
import numpy as np


def pack_mask(mask: np.ndarray) -> np.ndarray:
    """Упаковывает булев массив в компактный uint8 битовый массив."""
    m = np.asarray(mask, bool).reshape(-1)
    return np.packbits(m)


def unpack_mask(packed: np.ndarray, count: int) -> np.ndarray:
    """Распаковывает uint8 битовый массив в булев массив длины count."""
    p = np.asarray(packed, np.uint8)
    return np.unpackbits(p)[:count].astype(bool)


def compute_vertex_confidence(front_facing: np.ndarray,
                              renderer_visible: np.ndarray,
                              reprojection_error: np.ndarray | None = None) -> np.ndarray:
    """Вычисляет непрерывный коэффициент достоверности вершины in [0, 1]."""
    ff = np.asarray(front_facing, bool).astype(np.float32)
    rv = np.asarray(renderer_visible, bool).astype(np.float32)
    base_conf = ff * rv
    
    if reprojection_error is not None:
        err = np.asarray(reprojection_error, np.float32)
        # Штраф за репроекционную ошибку > 5 пикселей
        penalty = np.clip(1.0 - (err / 10.0), 0.5, 1.0)
        base_conf *= penalty
        
    return base_conf.astype(np.float32)
