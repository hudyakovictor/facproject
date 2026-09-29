"""🌊 As-Rigid-As-Possible (ARAP) shape interpolation между двумя сетками
ОДНОЙ топологии (Alexa, Cohen-Or, Levin — "As-Rigid-As-Possible Shape
Interpolation", SIGGRAPH 2000; тот же локальный трюк с 4-й вспомогательной
вершиной по нормали также используется в Sumner & Popović 2004
"Deformation Transfer").

Зачем это нужно вместо наивной линейной интерполяции V(t) = (1-t)VA + t·VB:
линейная интерполяция вершин ломает ЛОКАЛЬНУЮ жёсткость там, где между A и B
есть относительное вращение куска геометрии (классический артефакт "candy
wrapper" — угол при повороте сминается/сжимается в середине траектории).
ARAP вместо этого интерполирует ЛОКАЛЬНОЕ вращение+растяжение каждого
треугольника (через полярное разложение), а затем реконструирует глобально
согласованную сетку через разреженную задачу наименьших квадратов
(градиентный/Пуассоновский оператор), а не собирает позиции напрямую.

Так как обе сетки (identity-only, выровненные в (0,0,0)) используют ОДНУ и ту
же топологию BFM (одинаковые triangles для А и Б — M14 в docs/30), задача
идеально ложится на этот метод: не нужен отдельный шаг поиска соответствий
(в отличие от TPS для произвольных облаков точек).

Инженерное решение: разреженный оператор G (и его факторизация G^T G) зависят
ТОЛЬКО от топологии (triangles), а не от конкретных VA/VB — поэтому
факторизуется один раз при первом вызове и кэшируется (см. `_get_cached_system`)
и переиспользуется для ЛЮБОЙ пары лиц. Замер на синтетической сетке того же
масштаба, что BFM (35721 вершин / 70688 треугольников): факторизация ~0.3 c
(один раз), а полный проход (per-triangle transform + K=9 keyframe-реконструкция,
3 оси координат) — около 1-1.5 c на запрос. Числа получены и
задокументированы в docs/31_MORPHING_PROGRESS.md (Партия 6).
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.spatial.transform import Rotation

_SYSTEM_CACHE: dict[bytes, dict] = {}


def _build_local_bases(vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Для каждого треугольника строит 3x3 матрицу [e1|e2|n_hat] (столбцы —
    2 реальных ребра + вспомогательное "ребро" вдоль нормали, масштабированное
    так, чтобы матрица была хорошо обусловлена — трюк из статьи Alexa 2000)."""
    p0 = vertices[triangles[:, 0]]
    p1 = vertices[triangles[:, 1]]
    p2 = vertices[triangles[:, 2]]
    e1 = p1 - p0
    e2 = p2 - p0
    n = np.cross(e1, e2)
    norm_n = np.linalg.norm(n, axis=1, keepdims=True)
    n_hat = n / np.sqrt(np.maximum(norm_n, 1e-12))
    return np.stack([e1, e2, n_hat], axis=-1)  # (ntri, 3coord, 3edge)


def _build_and_factorize_system(triangles: np.ndarray, nv: int) -> dict:
    """Строит разреженный градиентный оператор G (3*ntri x (nv+ntri)),
    закрепляет одну вершину (убирает 1-мерное нуль-пространство трансляции
    на каждую координатную ось) и один раз факторизует G^T·G через sparse LU.
    Кэшируется по хешу байт triangles (топология в этом приложении не
    меняется между запросами — общий BFM-меш, M21)."""
    ntri = triangles.shape[0]
    n_unknown = nv + ntri
    row_base = np.arange(ntri) * 3
    aux_idx = nv + np.arange(ntri)

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    for edge_i, target_col in enumerate([triangles[:, 1], triangles[:, 2], aux_idx]):
        rows += list(row_base + edge_i) * 2
        cols += list(target_col) + list(triangles[:, 0])
        vals += [1.0] * ntri + [-1.0] * ntri

    G = sp.coo_matrix((vals, (rows, cols)), shape=(3 * ntri, n_unknown)).tocsr()
    pin_row = sp.coo_matrix(([1.0], ([0], [0])), shape=(1, n_unknown))
    G_pinned = sp.vstack([G, pin_row]).tocsr()

    normal_matrix = (G_pinned.T @ G_pinned).tocsc()
    lu = spla.splu(normal_matrix)

    return {"G_pinned": G_pinned, "lu": lu, "row_base": row_base, "nv": nv, "ntri": ntri}


def _get_cached_system(triangles: np.ndarray, nv: int) -> dict:
    key = triangles.astype(np.int64).tobytes() + nv.to_bytes(8, "little")
    cached = _SYSTEM_CACHE.get(key)
    if cached is None:
        cached = _build_and_factorize_system(triangles, nv)
        _SYSTEM_CACHE.clear()  # в этом приложении всегда одна топология — храним только последнюю
        _SYSTEM_CACHE[key] = cached
    return cached


def compute_triangle_transforms(VA: np.ndarray, VB: np.ndarray, triangles: np.ndarray):
    """Возвращает (rotvecs (ntri,3), Sym (ntri,3,3), MA (ntri,3,3)) — векторы
    поворота (лог. отображение SO(3), для честного SLERP от единичного
    поворота), симметричные тензоры растяжения/сдвига и исходный локальный
    базис A (нужен для правой части системы на любом t)."""
    MA = _build_local_bases(VA, triangles)
    MB = _build_local_bases(VB, triangles)
    MA_inv = np.linalg.inv(MA)
    Q = np.einsum("tij,tjk->tik", MB, MA_inv)

    U, S, Vt = np.linalg.svd(Q)
    R = np.einsum("tij,tjk->tik", U, Vt)
    dets = np.linalg.det(R)
    flip = dets < 0
    if flip.any():
        Vt = Vt.copy()
        S = S.copy()
        Vt[flip, -1, :] *= -1
        S[flip, -1] *= -1
        R = np.einsum("tij,tjk->tik", U, Vt)
    Sym = np.einsum("tij,tj,tjk->tik", Vt.transpose(0, 2, 1), S, Vt)
    rotvecs = Rotation.from_matrix(R).as_rotvec()
    return rotvecs, Sym, MA


def arap_interpolate(
    VA: np.ndarray,
    VB: np.ndarray,
    triangles: np.ndarray,
    ts: list[float],
) -> list[np.ndarray]:
    """Считает K = len(ts) кадров ARAP-интерполяции между VA (t=0) и VB
    (t=1). Каждый кадр — честное решение разреженной системы наименьших
    квадратов (не приближение), с ОДНОЙ факторизацией на все K кадров и все
    3 оси координат (факторизация зависит только от топологии — переиспользуется
    из кэша)."""
    nv = VA.shape[0]
    system = _get_cached_system(triangles, nv)
    G_pinned, lu, row_base = system["G_pinned"], system["lu"], system["row_base"]

    rotvecs, Sym, MA = compute_triangle_transforms(VA, VB, triangles)
    identity3 = np.eye(3)[None, :, :]

    frames: list[np.ndarray] = []
    for t in ts:
        Rt = Rotation.from_rotvec(rotvecs * t).as_matrix()
        St = (1 - t) * identity3 + t * Sym
        Qt = np.einsum("tij,tjk->tik", Rt, St)
        target = np.einsum("tij,tjk->tik", Qt, MA)  # (ntri, coord, edge)

        anchor = (1 - t) * VA[0] + t * VB[0]  # интерполируем "якорь", убирающий трансляционную неоднозначность
        out = np.zeros((G_pinned.shape[1], 3), dtype=np.float64)
        for axis in range(3):
            b = np.zeros(G_pinned.shape[0])
            b[row_base + 0] = target[:, axis, 0]
            b[row_base + 1] = target[:, axis, 1]
            b[row_base + 2] = target[:, axis, 2]
            b[-1] = anchor[axis]
            rhs = G_pinned.T @ b
            out[:, axis] = lu.solve(rhs)
        frames.append(out[:nv].astype(np.float32))

    return frames
