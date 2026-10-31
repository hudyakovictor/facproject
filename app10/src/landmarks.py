"""Именованные группы ориентиров ldm106 (один источник правды по нумерации).

Нумерация подтверждена эмпирически (см. reports/ldm106_numbering.png): вершины каждого
ориента сопоставлены с анатомическими сетами face_model.annotation и координатами.
Ось Y вверх, x<0 — анатомически правая сторона.

Группа `midline` — точки на средней линии лица (спинка носа 51, 52, 55 и низ подбородка 16);
по ним оценивается плоскость симметрии, от которой строятся зеркальные границы зон.
"""
import json
from pathlib import Path

DEFAULT_GROUPS_PATH = Path(__file__).resolve().parents[1] / "configs" / "ldm106_groups.json"

# ожидаемые размеры списочных групп (для теста: если нумерацию сдвинули — тест упадёт)
EXPECTED_SIZES = {
    "contour": 33,
    "right_eyebrow": 8,
    "left_eyebrow": 9,
    "nose": 15,
    "nose_ala": 10,
    "midline": 4,
    "right_eye": 9,
    "left_eye": 9,
    "upper_lip": 8,
    "lower_lip": 11,
}
SCALAR_KEYS = ["brow_outer_right", "brow_outer_left", "mouth_corner_right",
               "mouth_corner_left", "eye_center_right", "eye_center_left"]


def load_landmark_groups(path=DEFAULT_GROUPS_PATH):
    """Возвращает dict: имя -> list[int] или int. Валидирует размеры и диапазон 0..105."""
    groups = json.loads(Path(path).read_text())
    groups = {k: v for k, v in groups.items() if not k.startswith("_")}
    for name, size in EXPECTED_SIZES.items():
        got = groups.get(name)
        if not isinstance(got, list) or len(got) != size:
            raise ValueError(f"ldm106 группа {name}: {None if got is None else len(got)} точек, ожидалось {size}")
    for name in SCALAR_KEYS:
        if not isinstance(groups.get(name), int):
            raise ValueError(f"ldm106 скаляр {name}: ожидался int, получено {groups.get(name)!r}")
    all_idx = [i for name, v in groups.items() if isinstance(v, list) for i in v] + \
              [groups[name] for name in SCALAR_KEYS]
    if min(all_idx) < 0 or max(all_idx) > 105:
        raise ValueError(f"индексы ldm106 вне диапазона 0..105: min={min(all_idx)} max={max(all_idx)}")
    return groups
