"""Плоскость симметрии лица по парам «правая–левая» точка и вспомогательная геометрия.

Плоскость n·p = c оценивается так, чтобы отражение правой точки пары попадало в левую:
вектор b−a параллелен нормали, середина пары лежит на плоскости. Нормаль берётся как сумма
векторов пар, ориентированных в сторону +x (длинные пары весят больше и меньше страдают от
шума ориентиров), поэтому порядок точек внутри пары не важен. Остаточный поворот головы
превращается в наклон нормали, а не в сдвиг плоскости.
"""
import numpy as np


def fit_symmetry_plane(lm, pairs):
    """lm: (K,3) координаты ориентов, pairs: список [i, j]. Возвращает dict с normal, offset, tilt_deg, rms."""
    lm = np.asarray(lm, dtype=np.float64)
    pairs = np.asarray(pairs, dtype=np.int64)
    a, b = lm[pairs[:, 0]], lm[pairs[:, 1]]
    d = b - a
    length = np.linalg.norm(d, axis=1)
    ok = length > 1e-9
    if ok.sum() < 3:
        raise ValueError("для плоскости симметрии нужно минимум 3 непустые пары ориентиров")
    a, b, d = a[ok], b[ok], d[ok]
    d = np.where((d[:, 0] < 0)[:, None], -d, d)  # ориентируем все векторы в сторону +x
    n = d.sum(axis=0)
    norm = np.linalg.norm(n)
    if norm < 1e-9 or n[0] / norm < 0.5:
        raise ValueError("нормаль плоскости симметрии не близка к оси x: пары ориентиров выбраны неверно")
    n = n / norm
    c = float(np.mean(((a + b) / 2.0) @ n))
    reflected = a - 2.0 * ((a @ n) - c)[:, None] * n[None, :]
    rms = float(np.sqrt(np.mean(np.sum((reflected - b) ** 2, axis=1))))
    return {"normal": n, "offset": c, "tilt_deg": float(np.degrees(np.arccos(np.clip(n[0], -1, 1)))),
            "rms_reflection": rms, "n_pairs": int(ok.sum())}


def rotation_to_x(n):
    """Минимальный поворот R такой, что R @ n = (1, 0, 0)."""
    n = np.asarray(n, dtype=np.float64)
    n = n / np.linalg.norm(n)
    x = np.array([1.0, 0.0, 0.0])
    v = np.cross(n, x)
    s = np.linalg.norm(v)
    c = float(n @ x)
    if s < 1e-12:
        return np.eye(3) if c > 0 else np.diag([-1.0, 1.0, -1.0])
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + (vx @ vx) * ((1.0 - c) / s ** 2)


def to_symmetry_frame(v, plane):
    """Координаты, в которых плоскость симметрии — это x = 0."""
    n = plane["normal"]
    p0 = plane["offset"] * n
    return (np.asarray(v, dtype=np.float64) - p0) @ rotation_to_x(n).T


def points_in_polygon(points, polygon, tol=0.0):
    """Чётно-нечётный тест «точка внутри многоугольника» (points (N,2), polygon (M,2)).

    tol > 0 — допуск на границу: точка в пределах tol от края считается внутренней. Ориентиры
    лежат на вершинах сетки, то есть ровно на границе многоугольника, и без допуска результат
    для таких вершин зависит от округления (в том числе нарушает зеркальную симметрию).
    """
    if tol > 0:
        out = points_in_polygon(points, polygon)
        for dx, dy in ((tol, 0.0), (-tol, 0.0), (0.0, tol), (0.0, -tol)):
            out |= points_in_polygon(points + np.array([dx, dy]), polygon)
        return out
    x, y = points[:, 0], points[:, 1]
    inside = np.zeros(len(points), dtype=bool)
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        crosses = (yi > y) != (yj > y)
        if yj != yi:
            x_at = (xj - xi) * (y - yi) / (yj - yi) + xi
            inside ^= crosses & (x < x_at)
        j = i
    return inside
