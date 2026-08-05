"""📊 METRIC → Частотный анализ микрорельефа поверхности (ТЗ п.5).

Литая или напечатанная поверхность несёт регулярный микрорельеф: следы формы,
растр печати, повторяющийся паттерн. В спектре Фурье это даёт узкие выраженные
пики на характерных частотах. Живая кожа даёт широкий спектр без доминирующих
периодичностей.

🚨 WARNING: высокий `regularity_score` НЕ означает «силикон». Регулярный
паттерн дают также растр сканирования, JPEG-блочность 8×8, муар печати и
интерполяция апскейла. Метрика указывает на неестественную периодичность —
причина требует отдельной проверки.
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np

FFT_SCHEMA: Final[str] = "deeputin-fft-regularity-v1.0"

#: Минимум пикселей маски для устойчивой оценки спектра.
MIN_MASK_PIXELS: Final[int] = 1024

#: Доля низких частот, исключаемая как освещение и форма лица, а не микрорельеф.
LOW_FREQUENCY_CUTOFF: Final[float] = 0.08


def _fallback(reason: str) -> dict[str, float | str | bool]:
    """Явный отказ вместо выдуманных значений (AGENTS.md: не подставлять нули)."""
    return {"schema": FFT_SCHEMA, "status": "not_measurable", "reason": reason,
            "peak_frequency": float("nan"), "peak_magnitude": float("nan"),
            "regularity_score": float("nan"), "spectral_entropy": float("nan"),
            "measured": False}


def fft_regularity_analysis(texture_map: np.ndarray,
                            mask: np.ndarray | None = None) -> dict[str, Any]:
    """📊 METRIC → Оценить регулярность микрорельефа через спектр Фурье (ТЗ п.5).

    Внутри маски берётся наибольший вписанный прямоугольник, к нему применяется
    окно Ханна и 2D-БПФ. Низкие частоты (форма лица, освещение) исключаются.
    Регулярность оценивается как отношение максимального пика к медиане спектра.

    Args:
        texture_map: изображение (H, W) или (H, W, C); цвет усредняется.
        mask: булева маска пригодных пикселей; None — весь кадр.

    Returns:
        `peak_frequency`, `peak_magnitude`, `regularity_score`,
        `spectral_entropy`, `measured`. При непригодном входе — `not_measurable`.

    Raises:
        ValueError: если `texture_map` не двумерный и не трёхмерный массив.
    """
    image = np.asarray(texture_map)
    if image.ndim == 3:
        image = image.mean(axis=2)
    elif image.ndim != 2:
        raise ValueError(f"ожидается (H,W) или (H,W,C), получено {image.shape}")

    gray = image.astype(np.float64)
    if not np.isfinite(gray).any():
        return _fallback("текстура не содержит финитных значений")

    if mask is None:
        region = gray
    else:
        mask_bool = np.asarray(mask, dtype=bool)
        if mask_bool.shape != gray.shape:
            return _fallback(f"форма маски {mask_bool.shape} != текстуры {gray.shape}")
        if int(mask_bool.sum()) < MIN_MASK_PIXELS:
            return _fallback(f"маска покрывает {int(mask_bool.sum())} < {MIN_MASK_PIXELS} пикселей")
        rows = np.flatnonzero(mask_bool.any(axis=1))
        cols = np.flatnonzero(mask_bool.any(axis=0))
        region = gray[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]

    if min(region.shape) < 16:
        return _fallback(f"область {region.shape} меньше минимальных 16x16")

    region = np.nan_to_num(region, nan=float(np.nanmean(region)))
    region = region - region.mean()
    # Окно Ханна подавляет краевой разрыв, который иначе даёт ложный пик.
    window = np.outer(np.hanning(region.shape[0]), np.hanning(region.shape[1]))
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(region * window)))

    h, w = spectrum.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    radius = np.sqrt(((yy - cy) / max(cy, 1)) ** 2 + ((xx - cx) / max(cx, 1)) ** 2)
    band = radius > LOW_FREQUENCY_CUTOFF
    if not band.any():
        return _fallback("после отсечения низких частот спектр пуст")

    values = spectrum[band]
    median = float(np.median(values))
    peak = float(values.max())
    if median < 1e-12:
        return _fallback("вырожденный спектр (нулевая медиана)")

    peak_index = np.unravel_index(int(np.argmax(np.where(band, spectrum, -np.inf))), spectrum.shape)
    peak_radius = float(radius[peak_index])

    probability = values / max(values.sum(), 1e-12)
    entropy = float(-(probability * np.log2(np.clip(probability, 1e-12, None))).sum())
    max_entropy = float(np.log2(probability.size))

    return {"schema": FFT_SCHEMA, "status": "measured", "measured": True,
            "peak_frequency": peak_radius,
            "peak_magnitude": peak / median,
            # Отношение пика к медиане: у кожи спектр ровный, у литья — острый пик.
            "regularity_score": float(np.clip((peak / median) / 50.0, 0.0, 1.0)),
            "spectral_entropy": entropy / max_entropy if max_entropy > 0 else float("nan"),
            "analyzed_pixels": int(region.size),
            "interpretation": "высокая регулярность = периодический микрорельеф; "
                              "причина (литьё, печать, растр, JPEG) требует проверки"}
