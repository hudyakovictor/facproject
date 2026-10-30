#!/usr/bin/env python
"""Раскладка ldm134: какая точка за что отвечает.

Нужно перед тем, как писать метрики по векам/бровям/губам: у 134-набора нет
документированной нумерации, а угадывать её по памяти нельзя (мы уже обжигались
на том, что «левое/правое» в nomenclature модели инвертировано).

Метод без угадывания: каждая точка 134-набора — это индекс вершины BFM, а у
модели есть 8-канальная сегментация `annotation` =
[right_eye, left_eye, right_eyebrow, left_eyebrow, nose, up_lip, down_lip, skin].
Значит, принадлежность точки зоне берётся из данных. Сторона и порядок внутри
зоны — из координат средней формы (`u`), а не из названия канала.

Запуск: python3 -m app9.validation.ldm134_layout
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np

ASSETS = Path(__file__).resolve().parents[2] / "3ddfa_v3" / "assets"
PARTS = ["right_eye", "left_eye", "right_eyebrow", "left_eyebrow",
         "nose", "up_lip", "down_lip", "skin"]


def load():
    b = np.load(ASSETS / "face_model.npy", allow_pickle=True).item()
    u = np.asarray(b["u"], dtype=np.float64).reshape(-1, 3)
    mean = u[: 35709]                      # средняя форма, вершины в порядке tri
    ldm134 = np.asarray(b["ldm134"], dtype=np.int64)
    ldm106 = np.asarray(b["ldm106"], dtype=np.int64)
    ann = {name: set(np.asarray(v, dtype=np.int64).tolist())
           for name, v in zip(PARTS, b["annotation"], strict=True)}
    return mean, ldm134, ldm106, ann


def _band(mean: np.ndarray, xr: tuple[float, float], yr: tuple[float, float],
          side: int = 0) -> np.ndarray:
    """Вершины в прямоугольнике топологических координат средней формы.

    Берём по средней форме, а не по фото: топология BFM фиксирована, поэтому
    «вершина №N» — это одна и та же анатомическая точка на любом лице, и её можно
    один раз захардкодить в реестре метрик. `side` = -1 / +1 / 0 — половина лица.
    """
    x, y, z = mean[:, 0], mean[:, 1], mean[:, 2]
    m = (np.abs(x) >= xr[0]) & (np.abs(x) <= xr[1]) & (y >= yr[0]) & (y <= yr[1]) & (z > 0)
    if side:
        m &= np.sign(x) == side
    return np.flatnonzero(m)


def anatomy(mean: np.ndarray) -> dict[str, int]:
    """Точки-базисы, которых нет ни в 106, ни в 134: скула, глабелла, подгубная борозда.

    Нужны как «плоскость отсчёта» для глубинных метрик: без них пришлось бы мерить
    глубину относительно произвольного среднего, и признак зависел бы от нормировки.
    """
    out: dict[str, int] = {}
    # Зигиум: самая латеральная точка средней зоны. Полосу по y берём узкой и
    # одинаковой для обеих сторон, иначе стороны расходятся по высоте (широкая полоса
    # на левом и правом крае силуэта даёт разные y — метрика стала бы асимметрией).
    for side, tag in ((-1, "l"), (1, "r")):
        cand = _band(mean, (0.30, 0.50), (0.02, 0.12), side)
        out[f"zygion_{tag}"] = int(cand[np.argmax(np.abs(mean[cand, 0]))]) if cand.size else -1
        # Передняя скула (malar): наиболее выступающая вперёд точка щеки.
        cand = _band(mean, (0.20, 0.40), (-0.10, 0.10), side)
        out[f"cheek_{tag}"] = int(cand[np.argmax(mean[cand, 2])]) if cand.size else -1
        # Колонка фильтра: самый выступающий гребень рядом с жёлобом.
        cand = _band(mean, (0.02, 0.09), (-0.33, -0.20), side)
        out[f"philtrum_{tag}"] = int(cand[np.argmax(mean[cand, 2])]) if cand.size else -1
    # Глабелла: наиболее выступающая точка лба между бровями.
    cand = _band(mean, (0.0, 0.06), (0.50, 0.62))
    out["glabella"] = int(cand[np.argmax(mean[cand, 2])]) if cand.size else -1
    # Подгубная борозда: самая глубокая точка между нижней губой и подбородком.
    cand = np.flatnonzero((np.abs(mean[:, 0]) < 0.06) & (mean[:, 1] > -0.60)
                          & (mean[:, 1] < -0.46) & (mean[:, 2] > 0))
    out["mentolabial"] = int(cand[np.argmin(mean[cand, 2])]) if cand.size else -1
    # Погоний: выступание подбородка.
    cand = np.flatnonzero((np.abs(mean[:, 0]) < 0.06) & (mean[:, 1] > -0.72)
                          & (mean[:, 1] < -0.50) & (mean[:, 2] > 0))
    out["pogonion"] = int(cand[np.argmax(mean[cand, 2])]) if cand.size else -1
    return out


#: Порядок ключей `anatomy` — он же порядок строк массива `refs` в кэше экстракции.
ANAT_KEYS = ("zygion_l", "zygion_r", "cheek_l", "cheek_r", "philtrum_l", "philtrum_r",
             "glabella", "mentolabial", "pogonion")


def main() -> int:
    mean, ldm134, ldm106, ann = load()
    pos106 = {int(v): i for i, v in enumerate(ldm106)}
    print(f"ldm134: {len(ldm134)} точек, уникальных вершин {len(set(ldm134.tolist()))}")
    in106 = [i for i, v in enumerate(ldm134) if int(v) in pos106]
    print(f"совпадает с вершинами из ldm106: {len(in106)} точек")
    anat = anatomy(mean)
    print("\nанатомические базисы (индекс вершины BFM -> координаты средней формы):")
    for name in ANAT_KEYS:
        v = anat[name]
        print(f"  {name:14s} {v:6d}  " + "  ".join(f"{c:+.4f}" for c in mean[v]))
    print("\nлитерал для metric_registry (ANAT_VERTS):")
    print("ANAT_VERTS = (" + ", ".join(str(anat[k]) for k in ANAT_KEYS) + ",)")

    zones: dict[str, list[int]] = defaultdict(list)
    rows = []
    for i, v in enumerate(ldm134):
        v = int(v)
        hit = [name for name, s in ann.items() if v in s]
        zone = next((h for h in hit if h != "skin"), "skin-only" if hit else "UNTAGGED")
        x, y, z = mean[v]
        side = "L" if x < 0 else ("R" if x > 0 else "C")
        rows.append((i, v, zone, side, x, y, z, pos106.get(v)))
        zones[zone].append(i)
    print("\nзона -> сколько точек:")
    for name in list(PARTS) + ["skin-only", "UNTAGGED"]:
        if zones.get(name):
            print(f"  {name:14s} {len(zones[name]):3d}  {[i for i in zones[name]]}")
    print("\nidx  vert   зона           ст    x         y         z       есть в ldm106")
    for r in rows:
        i, v, zone, side, x, y, z, p106 = r
        print(f"{i:3d} {v:6d}  {zone:14s} {side}  {x:9.4f} {y:9.4f} {z:9.4f}   "
              f"{'' if p106 is None else p106}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
