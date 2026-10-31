"""Зоны лица: части из разметки (глаза/брови/нос/губы) + кожа по анатомии от ориентов ldm106.

Раньше кожа делилась по центроидам (nearest-centroid) — из-за этого щёки заворачивались на
висок (до ~30% площади). Теперь границы строятся от подтверждённых ориентов ldm106
(см. configs/ldm106_groups.json, reports/ldm106_numbering.png) и появляется зона `side`
(висок/боковая поверхность): вершины снаружи контура лица 0–32 либо с боковой нормалью.

Соглашение: ось Y вверх, x<0 — анатомически правая сторона (совпадает с right_eye в разметке).
Покрытие и непересечение гарантированы по построению: каждая skin-вершина попадает ровно в одну
зону (фронт -> лоб/щека/челюсть/подбородок, иначе -> side).

Симметрия зон: граница лица строится зеркально относительно средней линии (|x| <= max от
полуправой/полулевой ширины контура), поэтому площади левой/правой щеки и челюсти различаются
только из-за реальной асимметрии плотности вершин сетки, а не из-за правил разделения.
Боковое правило нормали (зона `side`) применяется только выше уровня рта (висок/скула) —
по спецификации челюсть ограничена контуром, а не нормалью.

ВНИМАНИЕ: границы НЕ валидированы. `validated` ставится только вручную через approve_zones.py.
"""
import numpy as np

from .face_model_io import ANNOTATION_NAMES
from .landmarks import load_landmark_groups

SIDE_NORMAL_THRESH = 0.8  # |nx| выше — нормаль смотрит в сторону -> зона side (боко головы |nx|>=0.9, щека <=0.76)


def _interp_boundary(ys, xs, q):
    """np.interp с флагом: вне диапазона ys -> наружу (xs[0]/xs[-1])."""
    return np.interp(q, ys, xs)


def zones_from_annotation(annotation, canon_v, ldm106, tri=None, groups=None, min_vertices=10):
    v = np.asarray(canon_v, dtype=np.float64)
    n = len(v)
    part = dict(zip(ANNOTATION_NAMES, annotation, strict=False))
    groups = groups or load_landmark_groups()
    lm = v[np.asarray(ldm106, dtype=np.int64)]  # (106,3) координаты ориентов

    # 1) части из разметки
    assigned = np.zeros(n, dtype=bool)
    zones = {}
    for src, name in [("right_eye", "right_eye"), ("left_eye", "left_eye"),
                      ("right_eyebrow", "right_eyebrow"), ("left_eyebrow", "left_eyebrow"),
                      ("nose", "nose"), ("up_lip", "upper_lip"), ("down_lip", "lower_lip")]:
        idx = np.unique(part[src])
        idx = idx[~assigned[idx]]
        zones[name] = idx
        assigned[idx] = True

    # 2) скаляры границ от ориентов
    def pts(names):
        out = []
        for nm in names:
            g = groups[nm]
            out.append([g] if isinstance(g, int) else np.asarray(g, dtype=np.int64))
        return lm[np.concatenate(out).astype(np.int64)]

    brow = pts(["right_eyebrow", "left_eyebrow", "brow_outer_right", "brow_outer_left"])
    brow_top_y = float(np.percentile(brow[:, 1], 85))
    outer_brow_x = float(max(np.abs(lm[groups["brow_outer_right"], 0]).max(),
                             np.abs(lm[groups["brow_outer_left"], 0]).max()))
    cr = lm[groups["mouth_corner_right"]]
    cl = lm[groups["mouth_corner_left"]]
    mouth_y = float((cr[1] + cl[1]) / 2.0)
    mouth_cx = float((cr[0] + cl[0]) / 2.0)
    mouth_x_half = float(abs(cl[0] - cr[0]) / 2.0)
    if brow_top_y <= mouth_y:
        raise ValueError("брови не выше рта: ось Y перевёрнута или нумерация ldm106 не совпадает")

    contour = lm[np.asarray(groups["contour"], dtype=np.int64)]
    contour_top_y = float(contour[:, 1].max())
    rc = contour[contour[:, 0] <= 0]
    lc = contour[contour[:, 0] >= 0]
    rc = rc[np.argsort(rc[:, 1])]
    lc = lc[np.argsort(lc[:, 1])]

    # 3) кожа = skin минус части
    skin = np.unique(part["skin"])
    skin = skin[~assigned[skin]]
    # координаты относительно средней линии (mouth_cx): зеркальные границы по |xs|
    xs = v[skin, 0] - mouth_cx
    y = v[skin, 1]

    # фронтальная область лица: зеркальная граница = max(полуширин контура справа/слева),
    # выше вершины контура — до внешнего конца брови
    below = y <= contour_top_y
    halfwidth = np.maximum(np.abs(_interp_boundary(rc[:, 1], rc[:, 0], y)),
                           np.abs(_interp_boundary(lc[:, 1], lc[:, 0], y)))
    inside_low = below & (np.abs(xs) <= halfwidth)
    inside_up = (~below) & (np.abs(xs) <= outer_brow_x)
    front = inside_low | inside_up

    # зона side: снаружи контура (везде) либо боковая норма ВЫШЕ уровня рта (висок/скула);
    # ниже рта боковая норма не применяется — челюсть ограничена только контуром
    side = ~front
    if tri is not None:
        from .mesh_geometry import vertex_normals
        normals = vertex_normals(v, tri)
        lateral = np.abs(normals[skin, 0]) > SIDE_NORMAL_THRESH
        side = side | (front & (y > mouth_y) & lateral)

    forehead = front & ~side & (y > brow_top_y)
    mid = front & ~side & (y <= brow_top_y) & (y > mouth_y)
    low = front & ~side & (y <= mouth_y)
    central = np.abs(xs) <= mouth_x_half

    def sel(mask):
        return skin[mask]

    zones.update({
        "forehead": sel(forehead),
        "cheek_r": sel(mid & (xs < 0)),
        "cheek_l": sel(mid & (xs >= 0)),
        "chin": sel(low & central),
        "jaw_r": sel(low & ~central & (xs < 0)),
        "jaw_l": sel(low & ~central & (xs >= 0)),
        "side": sel(side),
    })

    for name, idx in zones.items():
        if len(idx) < min_vertices:
            raise ValueError(f"зона {name}: {len(idx)} вершин (< {min_vertices})")
    return zones
