"""Геометрия треугольной сетки: нормали, площадь, кривизна. Только numpy.

Все функции работают с v (N,3) и tri (F,3, индексы с 0). Топология у всех кадров одна,
поэтому tri загружается один раз из face_model.npy (см. face_model_io.py).
"""
import numpy as np


def _tri_parts(v, tri):
    v = np.asarray(v, dtype=np.float64)
    a, b, c = v[tri[:, 0]], v[tri[:, 1]], v[tri[:, 2]]
    cross = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(cross, axis=1)
    return v, a, b, c, cross, area


def vertex_areas(v, tri):
    """Площадь вершины = 1/3 площадей смежных треугольников."""
    v, _, _, _, _, area = _tri_parts(v, tri)
    out = np.zeros(len(v))
    for k in range(3):
        np.add.at(out, tri[:, k], area / 3.0)
    return out


def vertex_normals(v, tri):
    """Нормали вершин, взвешенные по площади. Направление задаётся порядком вершин в треугольнике."""
    v, _, _, _, cross, _ = _tri_parts(v, tri)
    out = np.zeros_like(v)
    for k in range(3):
        np.add.at(out, tri[:, k], cross)
    ln = np.linalg.norm(out, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return out / ln


def boundary_vertices(tri, n_vertices):
    """Вершины на краю открытой сетки (ребро входит ровно в один треугольник)."""
    e = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
    uniq, cnt = np.unique(e, axis=0, return_counts=True)
    mask = np.zeros(n_vertices, dtype=bool)
    mask[uniq[cnt == 1].ravel()] = True
    return mask


def _cot(u, w):
    cr = np.linalg.norm(np.cross(u, w), axis=1)
    return np.einsum("ij,ij->i", u, w) / np.maximum(cr, 1e-12)


def mean_curvature(v, tri):
    """Средняя кривизна H (котангенсный лапласиан). Для сферы радиуса r при внешних нормалях H = 1/r."""
    v, a, b, c, _, _ = _tri_parts(v, tri)
    lap = np.zeros_like(v)
    ca = _cot(b - a, c - a)[:, None]
    cb = _cot(a - b, c - b)[:, None]
    cc = _cot(a - c, b - c)[:, None]
    np.add.at(lap, tri[:, 1], ca * (c - b))
    np.add.at(lap, tri[:, 2], ca * (b - c))
    np.add.at(lap, tri[:, 0], cb * (c - a))
    np.add.at(lap, tri[:, 2], cb * (a - c))
    np.add.at(lap, tri[:, 0], cc * (b - a))
    np.add.at(lap, tri[:, 1], cc * (a - b))
    area = np.maximum(vertex_areas(v, tri), 1e-12)
    lap /= (2.0 * area)[:, None]
    return -0.5 * np.einsum("ij,ij->i", lap, vertex_normals(v, tri))


def gaussian_curvature(v, tri):
    """Гауссова кривизна по дефекту угла. На краю сетки значение NaN."""
    v, a, b, c, _, _ = _tri_parts(v, tri)

    def ang(p, q, r):
        u, w = q - p, r - p
        cosv = np.einsum("ij,ij->i", u, w) / np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(w, axis=1), 1e-12)
        return np.arccos(np.clip(cosv, -1.0, 1.0))

    s = np.zeros(len(v))
    np.add.at(s, tri[:, 0], ang(a, b, c))
    np.add.at(s, tri[:, 1], ang(b, c, a))
    np.add.at(s, tri[:, 2], ang(c, a, b))
    k = (2.0 * np.pi - s) / np.maximum(vertex_areas(v, tri), 1e-12)
    k[boundary_vertices(tri, len(v))] = np.nan
    return k


def normal_angle_deg(v_a, v_b, tri):
    """Угол между нормалями соответствующих вершин двух сеток, градусы (N,)."""
    d = np.einsum("ij,ij->i", vertex_normals(v_a, tri), vertex_normals(v_b, tri))
    return np.degrees(np.arccos(np.clip(d, -1.0, 1.0)))


def weighted_mean(values, idx, weights):
    """Среднее по зоне с весом по площади, NaN пропускаются."""
    x = np.asarray(values)[idx]
    w = np.asarray(weights)[idx]
    ok = np.isfinite(x)
    if not ok.any() or w[ok].sum() <= 0:
        return float("nan")
    return float(np.sum(x[ok] * w[ok]) / np.sum(w[ok]))


def zone_features(v, tri, zones):
    """Признаки зон одной сетки: площадь, доля площади, H, K (все с весом по площади)."""
    area = vertex_areas(v, tri)
    h = mean_curvature(v, tri)
    k = gaussian_curvature(v, tri)
    total = float(area.sum())
    out = {}
    for name, idx in zones.items():
        za = float(area[idx].sum())
        out[name] = {
            "area": za,
            "area_frac": za / total if total > 0 else float("nan"),
            "mean_curvature": weighted_mean(h, idx, area),
            "gauss_curvature": weighted_mean(k, idx, area),
        }
    return out
