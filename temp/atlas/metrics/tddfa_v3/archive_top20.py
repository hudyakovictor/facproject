"""Front-only descriptive metrics from the user's 546-metric archive.

Primary rank order is preserved. These are shape ratios/geometry descriptors,
not identity, authenticity, or defect classifiers. The source report documents
within-sample repeated CV and visibility/noise caveats; results remain
exploratory until independently validated for each pose.
"""
from itertools import combinations
import numpy as np
from server.registry import metric

POSES = ("frontal",)
EPS = 1e-12


def _p(ctx):
    points = np.asarray(ctx["ldm106"], dtype=np.float64)
    if points.shape != (106, 3):
        raise ValueError("Требуются 106 точек 3DDFA_V3")
    return points


def _d(p, i, j):
    return float(np.linalg.norm(p[i] - p[j]))


def _D(p):
    # Distance between the means of the eye-corner pairs used by the source.
    return max(float(np.linalg.norm((p[66] + p[70] - p[75] - p[79]) / 2)), EPS)


def _distances(q):
    return np.array([np.linalg.norm(q[i] - q[j]) for i, j in combinations(range(len(q)), 2)])


def _gini(values):
    x = np.sort(np.asarray(values, dtype=np.float64))
    n = len(x)
    return float(np.sum((2 * np.arange(1, n + 1) - n - 1) * x) / max(n * np.sum(x), EPS))


def _triangle_quality(q):
    values = []
    for i, j, k in combinations(range(len(q)), 3):
        a, b, c = q[i], q[j], q[k]
        twice_area = np.linalg.norm(np.cross(b - a, c - a))
        denom = np.sum((a - b) ** 2) + np.sum((b - c) ** 2) + np.sum((c - a) ** 2)
        values.append(2 * np.sqrt(3) * twice_area / max(denom, EPS))
    return float(np.median(values))


def _tetra_mean(q):
    vols = []
    for i, j, k, l in combinations(range(len(q)), 4):
        vols.append(abs(np.linalg.det(np.stack((q[j] - q[i], q[k] - q[i], q[l] - q[i]))) / 6))
    diameter = max(_distances(q), default=EPS)
    return float(np.mean(vols) / max(diameter**3, EPS))


def _triangle_compactness(q):
    a, b, c = q
    area2 = np.linalg.norm(np.cross(b - a, c - a))
    denom = np.sum((a - b) ** 2) + np.sum((b - c) ** 2) + np.sum((c - a) ** 2)
    return float(2 * np.sqrt(3) * area2 / max(denom, EPS))


# 1 — rank 1
@metric("archive_v7_nose_side_l_tetra_volume_mean", "Нос L · средний объём тетраэдров / диаметр³", unit="ratio", inputs=("ldm106",), poses=POSES)
def nose_side_l_tetra(ctx): return _tetra_mean(_p(ctx)[[51, 55, 56, 57, 58, 60]])

# 2 — rank 2
@metric("archive_v5_tetra_lower_face", "Рот—основание носа—подбородок · ориентированный объём / D³", unit="ratio", inputs=("ldm106",), poses=POSES)
def tetra_lower_face(ctx):
    p = _p(ctx); d = _D(p)
    return float(np.dot(p[90] - p[84], np.cross(p[60] - p[84], p[16] - p[84])) / (6 * d**3))

# 3 — rank 3
@metric("archive_triangle_compactness_midface_l", "Средняя зона L · компактность треугольника", unit="ratio", inputs=("ldm106",), poses=POSES)
def compactness_midface_l(ctx): return _triangle_compactness(_p(ctx)[[66, 57, 84]])

# 4 — rank 4
@metric("archive_chin_jaw_ratio", "Подбородок / средняя челюсть", unit="ratio", inputs=("ldm106",), poses=POSES)
def chin_jaw_ratio(ctx):
    p = _p(ctx); return _d(p, 13, 19) / max(_d(p, 6, 26), EPS)

# 5 — rank 5
@metric("archive_prop_outer_eye_mouth_r", "Наружный уголок глаза—рот R / высота лица", unit="ratio", inputs=("ldm106",), poses=POSES)
def prop_outer_eye_mouth_r(ctx):
    p = _p(ctx); return _d(p, 79, 90) / max(_d(p, 51, 16), EPS)

# 6 — rank 6
@metric("archive_prop_outer_eye_mouth_l", "Наружный уголок глаза—рот L / высота лица", unit="ratio", inputs=("ldm106",), poses=POSES)
def prop_outer_eye_mouth_l(ctx):
    p = _p(ctx); return _d(p, 66, 84) / max(_d(p, 51, 16), EPS)

# 7 — rank 7
@metric("archive_v5_tetra_cheek_r", "Средняя зона R · ориентированный объём / D³", unit="ratio", inputs=("ldm106",), poses=POSES)
def tetra_cheek_r(ctx):
    p = _p(ctx); d = _D(p)
    return float(np.dot(p[63] - p[79], np.cross(p[90] - p[79], p[29] - p[79])) / (6 * d**3))

# 8 — rank 8
@metric("archive_v7_central_midface_distance_gini", "Центральная средняя зона · неравномерность расстояний", unit="ratio", inputs=("ldm106",), poses=POSES)
def central_midface_gini(ctx): return _gini(_distances(_p(ctx)[[70, 75, 51, 54, 60, 87]]))

# 9 — rank 9
@metric("archive_v7_lower_face_tetra_volume_mean", "Нижняя зона лица · средний объём тетраэдров / диаметр³", unit="ratio", inputs=("ldm106",), poses=POSES)
def lower_face_tetra(ctx): return _tetra_mean(_p(ctx)[[60, 84, 90, 93, 13, 16, 19]])

# 10 — rank 10
@metric("archive_v7_lower_face_triangle_quality_median", "Нижняя зона лица · медианное качество треугольников", unit="ratio", inputs=("ldm106",), poses=POSES)
def lower_face_triangle_quality(ctx): return _triangle_quality(_p(ctx)[[60, 84, 90, 93, 13, 16, 19]])

# 11 — rank 11
@metric("archive_v7_lower_face_distance_gini", "Нижняя зона лица · неравномерность расстояний", unit="ratio", inputs=("ldm106",), poses=POSES)
def lower_face_distance_gini(ctx): return _gini(_distances(_p(ctx)[[60, 84, 90, 93, 13, 16, 19]]))

# 12 — rank 12
@metric("archive_v7_nose_full_tetra_volume_mean", "Нос · средний объём тетраэдров / диаметр³", unit="ratio", inputs=("ldm106",), poses=POSES)
def nose_full_tetra(ctx): return _tetra_mean(_p(ctx)[51:66])

# 13 — rank 13
@metric("archive_v5_quad_eyes_mouth_inner", "Внутренние уголки глаз—рот · отношение расстояний", unit="ratio", inputs=("ldm106",), poses=POSES)
def quad_eyes_mouth_inner(ctx):
    p = _p(ctx)
    return (_d(p, 70, 75) * _d(p, 84, 90)) / max(_d(p, 70, 84) * _d(p, 75, 90), EPS)

# 14 — rank 14
@metric("archive_v5_quad_mouth_jaw", "Рот—нижний контур · отношение расстояний", unit="ratio", inputs=("ldm106",), poses=POSES)
def quad_mouth_jaw(ctx):
    p = _p(ctx)
    return (_d(p, 84, 90) * _d(p, 10, 22)) / max(_d(p, 84, 10) * _d(p, 90, 22), EPS)

# 15 — rank 15
@metric("archive_v4_nose_pca_flat", "Нос · отношение главных размеров", unit="ratio", inputs=("ldm106",), poses=POSES)
def nose_pca_flat(ctx):
    q = _p(ctx)[[51, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]]
    eig = np.linalg.eigvalsh(np.cov(q, rowvar=False))
    return float(np.sqrt(max(eig[-2], 0) / max(eig[-1], EPS)))

# 16 — rank 16
@metric("archive_mouth_width", "Ширина рта / D", unit="ratio", inputs=("ldm106",), poses=POSES)
def mouth_width(ctx):
    p = _p(ctx); return _d(p, 84, 90) / _D(p)

# 17 — rank 17
@metric("archive_v5_quad_nose_wings_base", "Крылья—основание носа · отношение расстояний", unit="ratio", inputs=("ldm106",), poses=POSES)
def quad_nose_wings_base(ctx):
    p = _p(ctx)
    return (_d(p, 57, 63) * _d(p, 58, 62)) / max(_d(p, 57, 58) * _d(p, 63, 62), EPS)

# 18 — rank 18
@metric("archive_v7_nasal_ridge_distance_gini", "Спинка носа · неравномерность расстояний", unit="ratio", inputs=("ldm106",), poses=POSES)
def nasal_ridge_gini(ctx): return _gini(_distances(_p(ctx)[[51, 52, 53, 54, 60]]))

# 19 — rank 19
@metric("archive_v7_nose_base_triangle_quality_median", "Основание носа · медианное качество треугольников", unit="ratio", inputs=("ldm106",), poses=POSES)
def nose_base_triangle_quality(ctx): return _triangle_quality(_p(ctx)[[54, 57, 58, 59, 60, 61, 62, 63]])

# 20 — rank 20
@metric("archive_nose_width_length", "Ширина носа / длина", unit="ratio", inputs=("ldm106",), poses=POSES)
def nose_width_length(ctx):
    p = _p(ctx); return _d(p, 57, 63) / max(_d(p, 51, 60), EPS)
