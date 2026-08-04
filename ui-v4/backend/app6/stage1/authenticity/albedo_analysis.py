"""📊 METRIC → Спектральный анализ альбедо и отражения кожи (ТЗ п.7).

Живая кожа полупрозрачна: свет проникает в дерму, рассеивается и выходит,
смещая цвет в красную область и создавая плавные переходы насыщенности.
Силикон и плотный грим рассеивают свет иначе — распределение насыщенности
уже, а блики резче.

🚨 WARNING: цвет кожи сильно зависит от освещения, баланса белого, плёнки и
пересжатия. Метрики пригодны для сравнения зон внутри кадра и пар кадров
сопоставимого качества, но не как абсолютный признак материала. Фототипы I–VI
дают разный базовый уровень — сравнение с популяционной нормой некорректно.
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np

ALBEDO_SCHEMA: Final[str] = "deeputin-albedo-spectral-v1.0"

MIN_MASK_PIXELS: Final[int] = 512


def _fallback(reason: str) -> dict[str, Any]:
    return {"schema": ALBEDO_SCHEMA, "status": "not_measurable", "reason": reason,
            "albedo_hsv_std": float("nan"), "albedo_saturation_ratio": float("nan"),
            "hue_std": float("nan"), "value_std": float("nan"),
            "redness_ratio": float("nan"), "specular_fraction": float("nan"),
            "measured": False}


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Векторное преобразование RGB[0..1] → HSV[0..1] без внешних зависимостей."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    maximum = np.max(rgb, axis=-1)
    minimum = np.min(rgb, axis=-1)
    delta = maximum - minimum

    hue = np.zeros_like(maximum)
    safe = delta > 1e-12
    with np.errstate(invalid="ignore", divide="ignore"):
        rm = np.where(safe & (maximum == r), ((g - b) / np.where(safe, delta, 1)) % 6.0, 0.0)
        gm = np.where(safe & (maximum == g), ((b - r) / np.where(safe, delta, 1)) + 2.0, 0.0)
        bm = np.where(safe & (maximum == b), ((r - g) / np.where(safe, delta, 1)) + 4.0, 0.0)
    hue = (rm + gm + bm) / 6.0
    saturation = np.where(maximum > 1e-12, delta / np.where(maximum > 1e-12, maximum, 1), 0.0)
    return np.stack([hue % 1.0, saturation, maximum], axis=-1)


def albedo_spectral_analysis(rgb: np.ndarray,
                             mask: np.ndarray | None = None) -> dict[str, Any]:
    """📊 METRIC → Метрики цветового спектра кожи (ТЗ п.7).

    Args:
        rgb: изображение (H, W, 3); значения 0..255 или 0..1.
        mask: булева маска пикселей кожи.

    Returns:
        `albedo_hsv_std`, `albedo_saturation_ratio`, `hue_std`, `value_std`,
        `redness_ratio`, `specular_fraction`, `measured`.

    Raises:
        ValueError: если массив не (H, W, 3).
    """
    image = np.asarray(rgb)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"ожидается (H,W,3), получено {image.shape}")

    data = image.astype(np.float64)
    if not np.isfinite(data).any():
        return _fallback("изображение не содержит финитных значений")
    if float(np.nanmax(data)) > 1.5:  # диапазон 0..255
        data = data / 255.0
    data = np.clip(np.nan_to_num(data, nan=0.0), 0.0, 1.0)

    if mask is None:
        selected = data.reshape(-1, 3)
    else:
        mask_bool = np.asarray(mask, dtype=bool)
        if mask_bool.shape != data.shape[:2]:
            return _fallback(f"форма маски {mask_bool.shape} != изображения {data.shape[:2]}")
        if int(mask_bool.sum()) < MIN_MASK_PIXELS:
            return _fallback(f"маска покрывает {int(mask_bool.sum())} < {MIN_MASK_PIXELS} пикселей")
        selected = data[mask_bool]

    if selected.shape[0] < MIN_MASK_PIXELS:
        return _fallback(f"пригодных пикселей {selected.shape[0]} < {MIN_MASK_PIXELS}")

    hsv = _rgb_to_hsv(selected)
    hue, saturation, value = hsv[:, 0], hsv[:, 1], hsv[:, 2]

    saturation_std = float(np.std(saturation))
    saturation_mean = float(np.mean(saturation))
    # Коэффициент вариации насыщенности: у кожи разброс шире из-за подповерхностного
    # рассеяния, у однородного покрытия — уже.
    saturation_ratio = saturation_std / saturation_mean if saturation_mean > 1e-9 else float("nan")

    red = float(np.mean(selected[:, 0]))
    green_blue = float(np.mean(selected[:, 1] + selected[:, 2]) / 2.0)
    redness = red / green_blue if green_blue > 1e-9 else float("nan")

    # Доля пикселей с высокой яркостью и низкой насыщенностью — зеркальные блики.
    specular = float(np.mean((value > 0.92) & (saturation < 0.12)))

    return {"schema": ALBEDO_SCHEMA, "status": "measured", "measured": True,
            "albedo_hsv_std": float(np.std(hsv, axis=0).mean()),
            "albedo_saturation_ratio": saturation_ratio,
            "hue_std": float(np.std(hue)),
            "saturation_std": saturation_std,
            "saturation_mean": saturation_mean,
            "value_std": float(np.std(value)),
            "redness_ratio": redness,
            "specular_fraction": specular,
            "analyzed_pixels": int(selected.shape[0]),
            "interpretation": "метрики сравнимы только между кадрами сопоставимого "
                              "качества и освещения; не абсолютный признак материала"}
