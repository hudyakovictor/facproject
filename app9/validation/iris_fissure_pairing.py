"""Проверка, какой глаз MediaPipe соответствует какому глазу 3DDFA в крест-метриках.

Зачем. Крест-метрики (радужка MediaPipe × глазная щель ldm134) нельзя строить «на веру»
в стороны: в каноне `aligner` у 3DDFA глаз лежит при x<0 (роль `L_`), а в MediaPipe
глазные точки названы «left/right» по своей конвенции, которая в боевом отображении
зеркальна. Какая из пар — одна и та же физическая Eye, зависит и от соглашения модели,
и от того, зеркальные ли фото в выборке. Проверяем по данным, а не по памяти.

Метод. В каждом каркасе считаем знаковую межглазную асимметрию одной и той же
анатомической величины (ширина и высота щели, нормированные на свой IPD) и коррелируем
её между каркасами при фиксированном соглашении индексов. Отрицательная корреляция
означала бы, что соглашения зеркальны, и тогда крест-метрики можно строить только
средними по обоим глазам.

Результат прогона (257 фронтальных фото put/vas/udmurt, кэш `.runtime/metric_shortlist`):

    асимметрия ширины  corr = +0.677   (std 3ddfa 0.008, mp 0.021)
    асимметрия высоты  corr = -0.154   (по 106 точкам нижний ряд века — 3 точки, шум)
    средняя ширина     corr = +0.369
    средняя высота     corr = +0.789
    доля фото, где радужка 468 левее 473 по пиксельному x: 1.00

То есть глаз при x<0 у 3DDFA — тот же физический глаз, что в MediaPipe дают индексы
33/133/159/145/468; ориентация корпуса в выборке единообразна. Знак асимметрии ширины
коррелирует сильно при малом шуме 3DDFA, поэтому в `metric_registry.cross_iris_fissure`
крест-метрики по сторонам строятся именно так, а величина «средняя высота» (+0.789) —
отдельное подтверждение, что IPD-нормировка согласует единицы двух каркасов.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / ".runtime" / "metric_shortlist"

# 3DDFA: щель при x<0 (веки 66..70 / 71..73, центр 74) и при x>0 (75..79 / 80..82, 83)
L_3D = list(range(66, 74))
R_3D = list(range(75, 83))
# MediaPipe: «глаз A» = 33/133 уголки, 159/145 верх/низ, 468 радужка; «глаз B» — 362/263,
# 386/374, 473. Соглашение фиксировано: сортировка по пиксельному x как раз и проверяется.
PAIR_MP = {"a": ((33, 133), (159, 145), 468), "b": ((362, 263), (386, 374), 473)}


def load(cache_glob: str, key: str) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for path in sorted(STORE.glob(cache_glob)):
        z = np.load(path)
        for name, pts in zip(z["files"], z[key], strict=True):
            out[str(name)] = np.asarray(pts, dtype=float)
    return out


def spread(pts: np.ndarray) -> float:
    """Максимальная попарная дистанция набора точек (проекция на плоскость кадра)."""
    p = pts[:, :2]
    return float(np.max(np.linalg.norm(p[:, None] - p[None, :], axis=2)))


def rows(ldm: dict, mp: dict) -> np.ndarray:
    data = []
    for name in sorted(set(ldm) & set(mp)):
        q, p = ldm[name], mp[name]
        ipd3 = float(np.linalg.norm(q[104] - q[105]))
        ipd_mp = float(np.hypot(*(p[468, :2] - p[473, :2])))
        w3 = [spread(q[L_3D]), spread(q[R_3D])]
        # Высота щели по 106: ряды век неравны (5 верхних и 3 нижних точки), поэтому
        # не попарное расстояние, а разница медиан y верхнего и нижнего ряда.
        h3 = [abs(float(np.median(q[66:71, 1])) - float(np.median(q[71:74, 1]))),
              abs(float(np.median(q[75:80, 1])) - float(np.median(q[80:83, 1])))]
        mw = [float(np.hypot(*(p[33, :2] - p[133, :2]))), float(np.hypot(*(p[362, :2] - p[263, :2])))]
        mh = [float(np.hypot(*(p[159, :2] - p[145, :2]))), float(np.hypot(*(p[386, :2] - p[374, :2])))]
        data.append([
            w3[0] / ipd3, w3[1] / ipd3, mw[0] / ipd_mp, mw[1] / ipd_mp,
            h3[0] / ipd3, h3[1] / ipd3, mh[0] / ipd_mp, mh[1] / ipd_mp,
            float(np.mean(w3)) / ipd3, float(np.mean(mw)) / ipd_mp,
            float(np.mean(h3)) / ipd3, float(np.mean(mh)) / ipd_mp,
            float(p[468, 0] < p[473, 0]),
        ])
    return np.asarray(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(sys.argv[1:])
    a = rows(load("lmk_*.npz", "pts"), load("mp_*.npz", "pts"))
    if a.shape[0] < 10:
        print("нет общего кэша — сначала extract-mp и extract-ldm")
        return 1
    corr = lambda x, y: float(np.corrcoef(x, y)[0, 1])  # noqa: E731
    print(f"фото: {a.shape[0]}; доля, где радужка 468 левее 473: {np.mean(a[:, 12] > 0):.2f}")
    print(f"асимметрия ширины corr = {corr(a[:, 0] - a[:, 1], a[:, 2] - a[:, 3]):+.3f}")
    print(f"асимметрия высоты corr = {corr(a[:, 4] - a[:, 5], a[:, 6] - a[:, 7]):+.3f}")
    print(f"средняя ширина     corr = {corr(a[:, 8], a[:, 9]):+.3f}")
    print(f"средняя высота     corr = {corr(a[:, 10], a[:, 11]):+.3f}")
    print("вывод: corr(асимметрия ширины) > 0 ⇒ глаз при x<0 (3DDFA) = глаз «A» "
          "(MP 33/159/468); см. docstring модуля")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
