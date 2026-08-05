"""🚧 GATE → Компенсация дисбаланса качества снимков (ТЗ п.8).

Ключевой конфаундер датасета 1999–2026: кадр с VHS-оцифровки и студийное фото
2025 года несопоставимы по детализации. Размытый архивный кадр даёт низкую
сложность текстуры просто потому, что деталей нет — и без защиты это выглядит
как «неестественная кожа».

Модуль делает две вещи: помечает пары с сильным расхождением качества и не
позволяет текстурному счёту опускаться ниже нейтрального уровня, когда низкое
значение объясняется качеством источника, а не свойствами поверхности.

🚨 WARNING: компенсация снижает чувствительность. Пара с флагом
`quality_disparity` пригодна для геометрии, но текстурные выводы по ней делать
нельзя — это отражено в `texture_conclusions_allowed`.
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np

QUALITY_GATE_SCHEMA: Final[str] = "deeputin-quality-gate-v1.0"

#: Нейтральное значение текстурного счёта при недостаточном качестве (ТЗ п.8).
NEUTRAL_TEXTURE_SCORE: Final[float] = 0.5

#: Во сколько раз может отличаться разрешение, прежде чем пара помечается.
DEFAULT_RESOLUTION_RATIO: Final[float] = 2.0


def resolution_ratio(pixels_a: float, pixels_b: float) -> float:
    """🔢 Отношение большего разрешения к меньшему (всегда >= 1).

    Raises:
        ValueError: неположительное или нефинитное разрешение.
    """
    a, b = float(pixels_a), float(pixels_b)
    if not (np.isfinite(a) and np.isfinite(b)) or a <= 0 or b <= 0:
        raise ValueError("разрешение должно быть положительным и финитным")
    return max(a, b) / min(a, b)


def compensate_quality_disparity(
    pair_metrics: dict[str, Any],
    photo_qualities: dict[str, dict[str, Any]],
    *,
    max_resolution_ratio: float = DEFAULT_RESOLUTION_RATIO,
) -> dict[str, Any]:
    """🚧 GATE → Скорректировать метрики пары при расхождении качества (ТЗ п.8).

    Args:
        pair_metrics: метрики пары; должен содержать `photo_a` и `photo_b`.
        photo_qualities: `{photo_id: {"pixels": int, "texture_score_0_1": float,
            "quality_limited": bool}}`.
        max_resolution_ratio: порог, за которым пара помечается `quality_disparity`.

    Returns:
        Копия метрик с полями `quality_disparity`, `resolution_ratio`,
        `texture_score_0_1`, `texture_conclusions_allowed`.

    Raises:
        KeyError: в метриках пары нет идентификаторов фото.
    """
    if "photo_a" not in pair_metrics or "photo_b" not in pair_metrics:
        raise KeyError("pair_metrics должен содержать photo_a и photo_b")

    out = dict(pair_metrics)
    out["quality_gate_schema"] = QUALITY_GATE_SCHEMA
    qa = photo_qualities.get(str(pair_metrics["photo_a"]), {})
    qb = photo_qualities.get(str(pair_metrics["photo_b"]), {})

    ratio = float("nan")
    pixels_a, pixels_b = qa.get("pixels"), qb.get("pixels")
    if pixels_a and pixels_b:
        try:
            ratio = resolution_ratio(pixels_a, pixels_b)
        except ValueError:
            ratio = float("nan")

    disparity = bool(np.isfinite(ratio) and ratio > float(max_resolution_ratio))
    quality_limited = bool(qa.get("quality_limited") or qb.get("quality_limited")
                           or pair_metrics.get("quality_limited"))

    out["resolution_ratio"] = ratio
    out["quality_disparity"] = disparity
    out["quality_limited"] = quality_limited

    # Защита: при ограниченном качестве текстурный счёт не опускается ниже
    # нейтрального. Размытость источника не должна читаться как признак материала.
    if quality_limited or disparity:
        current = pair_metrics.get("texture_score_0_1")
        try:
            current_f = float(current) if current is not None else float("nan")
        except (TypeError, ValueError):
            current_f = float("nan")
        if not np.isfinite(current_f) or current_f < NEUTRAL_TEXTURE_SCORE:
            out["texture_score_0_1"] = NEUTRAL_TEXTURE_SCORE
            out["texture_score_source"] = "neutral_default_quality_limited"
        else:
            out["texture_score_source"] = "measured"
        out["texture_conclusions_allowed"] = False
        out["quality_gate_reason"] = ("resolution_disparity" if disparity else "quality_limited")
    else:
        out["texture_score_source"] = "measured"
        out["texture_conclusions_allowed"] = True
        out["quality_gate_reason"] = ""
    return out


def quality_gate_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """📤 Сводка применения гейта качества по всем парам прогона."""
    total = len(rows)
    disparity = sum(1 for r in rows if r.get("quality_disparity"))
    limited = sum(1 for r in rows if r.get("quality_limited"))
    blocked = sum(1 for r in rows if r.get("texture_conclusions_allowed") is False)
    return {"schema": QUALITY_GATE_SCHEMA, "pair_count": total,
            "quality_disparity_count": disparity, "quality_limited_count": limited,
            "texture_blocked_count": blocked,
            "neutral_texture_score": NEUTRAL_TEXTURE_SCORE,
            "policy": "низкое качество источника не может читаться как признак материала"}
