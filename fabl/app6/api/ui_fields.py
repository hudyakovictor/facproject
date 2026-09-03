"""Вычисление полей, которых нет в Stage 1, но которые требует UI.

API_CONTRACT.md объявляет обязательными id, date, t, era, bucket, quality,
boneScore, p0, p1, p2. Stage 1 не производит ни boneScore, ни p0/p1/p2,
ни era, ни t — их нужно собирать здесь, чтобы UI получал полный контракт
без подмены данных.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date as _date
from typing import Any, Final

import numpy as np

UI_FIELDS_SCHEMA: Final[str] = "deeputin-ui-fields-v1.0"
UI_FIELD_CONTRACTS: Final[dict[str, dict[str, Any]]] = {
    "boneScore": {
        "role": "derived_display_only",
        "evidence_metric": False,
        "source_metric": "p95_point_z",
        "transform": "1/(1+max(z,0)/3)",
        "not_a_verdict": True,
    },
}

#: Границы эпох. Совпадают с осью «до/после» в отчётах.
ERA_BOUNDS: Final[tuple[tuple[str, int, int], ...]] = (
    ("1999-2007", 1999, 2007),
    ("2008-2013", 2008, 2013),
    ("2014-2019", 2014, 2019),
    ("2020-2026", 2020, 2026),
)

REQUIRED_UI_FIELDS: Final[tuple[str, ...]] = (
    "id", "date", "t", "era", "bucket", "quality", "boneScore", "p0", "p1", "p2")


def era_for(iso_date: str | None) -> str:
    if not iso_date:
        return "unknown"
    try:
        year = _date.fromisoformat(str(iso_date)[:10]).year
    except (TypeError, ValueError):
        return "unknown"
    for name, lo, hi in ERA_BOUNDS:
        if lo <= year <= hi:
            return name
    return "unknown"


def normalized_t(iso_date: str | None, first: str, last: str) -> float | None:
    """Позиция кадра на шкале [0,1]. None — если дата неизвестна."""
    try:
        d = _date.fromisoformat(str(iso_date)[:10]).toordinal()
        a = _date.fromisoformat(str(first)[:10]).toordinal()
        b = _date.fromisoformat(str(last)[:10]).toordinal()
    except (TypeError, ValueError):
        return None
    if b <= a:
        return 0.0
    return float(np.clip((d - a) / (b - a), 0.0, 1.0))


def bone_score(pair_metrics: dict[str, Any]) -> float | None:
    """Derived display-only скор в [0,1]; не evidence-метрика и не вердикт.

    Строится из калиброванного z по стабильным точкам, а не из сырого RMSE:
    сырой RMSE несопоставим между бинами (профили шумнее фронта на ~40%).
    """
    z = pair_metrics.get("p95_point_z")
    if z is None:
        return None
    try:
        z = float(z)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(z):
        return None
    return float(np.clip(1.0 / (1.0 + max(z, 0.0) / 3.0), 0.0, 1.0))


def principal_coords(descriptor: Sequence[float], basis: np.ndarray) -> tuple[float, float, float]:
    """p0/p1/p2 — проекции дескриптора на первые три оси общего базиса.

    Базис обязан быть общим для всего прогона, иначе точки на графике UI
    несопоставимы между кадрами.
    """
    x = np.asarray(descriptor, dtype=float).reshape(-1)
    b = np.asarray(basis, dtype=float)
    if b.ndim != 2 or b.shape[0] < 3 or b.shape[1] != x.size:
        raise ValueError("basis must have shape (>=3, len(descriptor))")
    p = b[:3] @ x
    return float(p[0]), float(p[1]), float(p[2])


def validate_ui_row(row: dict[str, Any]) -> list[str]:
    """Вернуть список отсутствующих обязательных полей контракта."""
    return [f for f in REQUIRED_UI_FIELDS if row.get(f) is None]
