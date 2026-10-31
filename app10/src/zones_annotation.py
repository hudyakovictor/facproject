"""Зоны лица: части из разметки (глаза/брови/нос/губы) + кожа по анатомии от ориентов ldm106.

Границы строятся от подтверждённых ориентов ldm106 (configs/ldm106_groups.json,
reports/ldm106_numbering.png). Вершины снаружи контура лица 0–32 либо с боковой нормалью
выше уровня рта попадают в зону `side`.

Соглашение: ось Y вверх, x<0 — анатомически правая сторона (совпадает с right_eye в разметке).
Покрытие и непересечение гарантированы по построению: каждая skin-вершина попадает ровно в одну
зону (фронт -> лоб/щека/челюсть/подбородок, иначе -> side).

Система координат правил. Плоскость симметрии оценивается по парам «правая–левая» точка
(groups["symmetry_pairs"], см. symmetry.py) и делается плоскостью x = 0: сетка сдвигается и
поворачивается (нормаль плоскости -> ось x). Остаточный поворот головы поэтому превращается в
наклон плоскости, а не в сдвиг. Нормали для правила `side` считаются в этой же системе.

Граница лица — многоугольник: контур 0–32, замкнутый сверху полосой |x| <= внешний конец брови.
Область лица = многоугольник ИЛИ его зеркальное отражение относительно x = 0 (поэтому зоны
зеркальны). Раньше граница считалась как max двух интерполяций полуширины, и у подбородка,
где контур сходится, одна точка перескакивала между половинами и дёргала внешнюю границу
(jaw на симметричной форме прыгал на 14–22% при сдвиге плоскости на 0.005).
Побочный эффект зеркального «ИЛИ»: на более узкой стороне в область попадает полоса шириной
порядка асимметрии контура.

Зона `side` — это НЕ зона лица: висок, боковая поверхность, скальп, уши, шея. Она перечислена в
NON_FACE_ZONES, и отчёты по различиям лица её исключают.

SIDE_NORMAL_THRESH и процентиль верхнего края бровей подобраны на одной персоне (person_01).
ВНИМАНИЕ: границы НЕ валидированы. `validated` ставится только вручную через approve_zones.py.
"""
import numpy as np

from .face_model_io import ANNOTATION_NAMES
from .landmarks import load_landmark_groups
from .symmetry import fit_symmetry_plane, points_in_polygon, to_symmetry_frame

SIDE_NORMAL_THRESH = 0.8  # |nx| выше — нормаль смотрит в сторону -> side (подобрано на person_01)
BROW_TOP_PERCENTILE = 85  # верхний край бровей = этот процентиль y по ориентирам бровей
NON_FACE_ZONES = ("side",)
EPS = 1e-9  # допуск на равенство: пороги берутся из вершин сетки, и вершина ровно на границе не должна зависеть от округления


def zones_from_annotation(annotation, canon_v, ldm106, tri=None, groups=None, min_vertices=10,
                          side_normal_thresh=SIDE_NORMAL_THRESH, plane_shift=0.0, return_info=False):
    """Возвращает dict зона -> индексы вершин (и info, если return_info).

    plane_shift — диагностика чувствительности: сдвиг плоскости симметрии вдоль x (в единицах сетки)
    относительно найденной по парам. В обычной работе 0.
    """
    v0 = np.asarray(canon_v, dtype=np.float64)
    n = len(v0)
    part = dict(zip(ANNOTATION_NAMES, annotation, strict=True))
    groups = groups or load_landmark_groups()
    ldm106 = np.asarray(ldm106, dtype=np.int64)

    # 0) система координат: плоскость симметрии -> x = 0
    plane = fit_symmetry_plane(v0[ldm106], groups["symmetry_pairs"])
    v = to_symmetry_frame(v0, plane)
    v[:, 0] -= plane_shift
    lm = v[ldm106]  # (106,3) координаты ориентов в системе плоскости симметрии

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
    brow_top_y = float(np.percentile(brow[:, 1], BROW_TOP_PERCENTILE))
    outer_brow_x = float(max(abs(lm[groups["brow_outer_right"], 0]), abs(lm[groups["brow_outer_left"], 0])))
    cr = lm[groups["mouth_corner_right"]]
    cl = lm[groups["mouth_corner_left"]]
    mouth_y = float((cr[1] + cl[1]) / 2.0)
    mouth_x_half = float(abs(cl[0] - cr[0]) / 2.0)
    if brow_top_y <= mouth_y:
        raise ValueError("брови не выше рта: ось Y перевёрнута или нумерация ldm106 не совпадает")

    # граница лица: контур 0–32, сверху замкнут полосой |x| <= outer_brow_x
    contour = lm[np.asarray(groups["contour"], dtype=np.int64)][:, :2]
    y_big = float(v[:, 1].max()) + 1.0
    polygon = np.vstack([contour,
                         [[outer_brow_x, contour[-1, 1]], [outer_brow_x, y_big],
                          [-outer_brow_x, y_big], [-outer_brow_x, contour[0, 1]]]])
    mirrored = polygon * np.array([-1.0, 1.0])

    # 3) кожа = skin минус части
    skin = np.unique(part["skin"])
    skin = skin[~assigned[skin]]
    xs = v[skin, 0]
    y = v[skin, 1]
    xy = np.column_stack([xs, y])
    front = points_in_polygon(xy, polygon, tol=EPS) | points_in_polygon(xy, mirrored, tol=EPS)

    # зона side: снаружи области лица либо боковая нормаль ВЫШЕ уровня рта (висок/скула);
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
    if not return_info:
        return zones
    mid_idx = np.asarray(groups["midline"], dtype=np.int64)
    info = {
        "plane": {"normal": [float(t) for t in plane["normal"]], "offset": plane["offset"],
                  "tilt_deg": plane["tilt_deg"], "rms_reflection": plane["rms_reflection"],
                  "n_pairs": plane["n_pairs"]},
        "midline_offset": float(lm[mid_idx, 0].mean() if len(mid_idx) else 0.0),  # диагностика: ~0 при верной плоскости
        "plane_shift": float(plane_shift),
    }
    return zones, info
