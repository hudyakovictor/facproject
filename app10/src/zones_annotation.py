"""Зоны лица из разметки модели (annotation) + деление кожи по положению частей лица.

Части из разметки (глаза, брови, нос, губы) берутся как есть. Остальная кожа делится
по центроидам частей, а не по абсолютным числам: лоб выше бровей, подбородок и челюсть
ниже нижней губы, щёки между ними. Лево и право определяются по знаку x правого глаза.

ВНИМАНИЕ: деление кожи НЕ валидировано. Проверь картинку zones_check.png перед использованием.
Предполагается, что ось Y направлена вверх.
"""
import numpy as np

from .face_model_io import ANNOTATION_NAMES


def zones_from_annotation(annotation, canon_v, min_vertices=10):
    v = np.asarray(canon_v, dtype=np.float64)
    n = len(v)
    part = dict(zip(ANNOTATION_NAMES, annotation))
    assigned = np.zeros(n, dtype=bool)
    zones = {}
    for src, name in [("right_eye", "right_eye"), ("left_eye", "left_eye"),
                      ("right_eyebrow", "right_eyebrow"), ("left_eyebrow", "left_eyebrow"),
                      ("nose", "nose"), ("up_lip", "upper_lip"), ("down_lip", "lower_lip")]:
        idx = np.unique(part[src])
        idx = idx[~assigned[idx]]
        zones[name] = idx
        assigned[idx] = True

    brow_idx = np.concatenate([zones["right_eyebrow"], zones["left_eyebrow"]])
    lips_idx = np.concatenate([zones["upper_lip"], zones["lower_lip"]])
    brow_y = float(v[brow_idx, 1].mean())
    lip_low_y = float(v[zones["lower_lip"], 1].mean())
    if brow_y <= lip_low_y:
        raise ValueError("брови не выше губ: ось Y перевёрнута или разметка не совпадает с сеткой")
    half_mouth = 0.5 * float(np.ptp(v[lips_idx, 0]))
    side = np.sign(float(v[zones["right_eye"], 0].mean())) or 1.0

    skin = np.unique(part["skin"])
    skin = skin[~assigned[skin]]
    x, y = v[skin, 0], v[skin, 1]
    on_right = (x * side) > 0
    forehead = y > brow_y
    lower = (~forehead) & (y < lip_low_y)
    central = np.abs(x) <= half_mouth
    groups = {
        "forehead": forehead,
        "chin": lower & central,
        "jaw_r": lower & ~central & on_right,
        "jaw_l": lower & ~central & ~on_right,
        "cheek_r": ~forehead & ~lower & on_right,
        "cheek_l": ~forehead & ~lower & ~on_right,
    }
    for name, m in groups.items():
        zones[name] = skin[m]
    for name, idx in zones.items():
        if len(idx) < min_vertices:
            raise ValueError(f"зона {name}: {len(idx)} вершин (< {min_vertices})")
    return zones
