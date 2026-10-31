"""Зоны лица: части из разметки (глаза/брови/нос/губы) + кожа по анатомии от ориентов ldm106.

Границы строятся от подтверждённых ориентов ldm106 (configs/ldm106_groups.json,
reports/ldm106_numbering.png). Вершины снаружи контура лица 0–32 либо с боковой нормалью
выше уровня рта попадают в зону `side`.

Соглашение: ось Y вверх, x<0 — анатомически правая сторона (совпадает с right_eye в разметке).
Покрытие и непересечение гарантированы по построению: каждая skin-вершина попадает ровно в одну
зону (фронт -> лоб/щека/челюсть/подбородок, иначе -> side).

Плоскость симметрии: x = mid_x, среднее x по ориентам группы `midline` (спинка носа и низ
подбородка). ВСЕ x-границы считаются относительно mid_x, поэтому сдвиг всей сетки вдоль x
не меняет состав зон.

Симметрия зон: граница лица зеркальна относительно mid_x (|x - mid_x| <= max от полуправой/полулевой
ширины контура). Побочный эффект: на более узкой стороне лица в «переднюю» область попадает полоса
шириной порядка асимметрии контура. Симметрия щёк и челюсти по числу вершин достигается по построению,
поэтому она проверяет код, а не анатомическую точность границ — границы нужно смотреть на рендере.

Зона `side` — это НЕ зона лица: висок, боковая поверхность, скальп, уши, шея. Она перечислена в
NON_FACE_ZONES, и отчёты по различиям лица её исключают.

SIDE_NORMAL_THRESH и процентиль верхнего края бровей подобраны на одной персоне (person_01).
ВНИМАНИЕ: границы НЕ валидированы. `validated` ставится только вручную через approve_zones.py.
"""
import numpy as np

from .face_model_io import ANNOTATION_NAMES
from .landmarks import load_landmark_groups

SIDE_NORMAL_THRESH = 0.8  # |nx| выше — нормаль смотрит в сторону -> side (подобрано на person_01)
BROW_TOP_PERCENTILE = 85  # верхний край бровей = этот процентиль y по ориентирам бровей
NON_FACE_ZONES = ("side",)
EPS = 1e-9  # допуск на равенство: пороги берутся из вершин сетки, и вершина ровно на границе не должна зависеть от округления


def zones_from_annotation(annotation, canon_v, ldm106, tri=None, groups=None, min_vertices=10,
                          side_normal_thresh=SIDE_NORMAL_THRESH):
    v = np.asarray(canon_v, dtype=np.float64)
    n = len(v)
    part = dict(zip(ANNOTATION_NAMES, annotation, strict=True))
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

    # 2) плоскость симметрии и скаляры границ от ориентов
    mid_x = float(lm[np.asarray(groups["midline"], dtype=np.int64), 0].mean())

    def pts(names):
        out = []
        for nm in names:
            g = groups[nm]
            out.append([g] if isinstance(g, int) else np.asarray(g, dtype=np.int64))
        return lm[np.concatenate(out).astype(np.int64)]

    brow = pts(["right_eyebrow", "left_eyebrow", "brow_outer_right", "brow_outer_left"])
    brow_top_y = float(np.percentile(brow[:, 1], BROW_TOP_PERCENTILE))
    outer_brow_x = float(max(abs(lm[groups["brow_outer_right"], 0] - mid_x),
                             abs(lm[groups["brow_outer_left"], 0] - mid_x)))
    cr = lm[groups["mouth_corner_right"]]
    cl = lm[groups["mouth_corner_left"]]
    mouth_y = float((cr[1] + cl[1]) / 2.0)
    mouth_x_half = float(abs(cl[0] - cr[0]) / 2.0)
    if brow_top_y <= mouth_y:
        raise ValueError("брови не выше рта: ось Y перевёрнута или нумерация ldm106 не совпадает")

    contour = lm[np.asarray(groups["contour"], dtype=np.int64)]
    contour_top_y = float(contour[:, 1].max())
    rc = contour[contour[:, 0] <= mid_x]
    lc = contour[contour[:, 0] >= mid_x]
    if len(rc) < 2 or len(lc) < 2:
        raise ValueError("контур лица не делится плоскостью симметрии на две стороны: проверьте ориентиры")
    rc = rc[np.argsort(rc[:, 1])]
    lc = lc[np.argsort(lc[:, 1])]

    # 3) кожа = skin минус части; все x относительно плоскости симметрии
    skin = np.unique(part["skin"])
    skin = skin[~assigned[skin]]
    xs = v[skin, 0] - mid_x
    y = v[skin, 1]

    # фронтальная область лица: зеркальная граница = max(полуширин контура справа/слева);
    # выше вершины контура — до внешнего конца брови
    below = y <= contour_top_y
    halfwidth = np.maximum(np.abs(np.interp(y, rc[:, 1], rc[:, 0] - mid_x)),
                           np.abs(np.interp(y, lc[:, 1], lc[:, 0] - mid_x)))
    inside_low = below & (np.abs(xs) <= halfwidth + EPS)
    inside_up = (~below) & (np.abs(xs) <= outer_brow_x + EPS)
    front = inside_low | inside_up

    # зона side: снаружи контура (везде) либо боковая нормаль ВЫШЕ уровня рта (висок/скула);
    # ниже рта боковая нормаль не применяется — челюсть ограничена только контуром
    side = ~front
    if tri is not None:
        from .mesh_geometry import vertex_normals
        normals = vertex_normals(v, tri)
        lateral = np.abs(normals[skin, 0]) > side_normal_thresh
        side = side | (front & (y > mouth_y) & lateral)

    forehead = front & ~side & (y > brow_top_y)
    mid = front & ~side & (y <= brow_top_y) & (y > mouth_y)
    low = front & ~side & (y <= mouth_y)
    central = np.abs(xs) <= mouth_x_half + EPS

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
