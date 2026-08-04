"""📊 METRIC → Локальные бинарные паттерны микроструктуры кожи (ТЗ п.6).

Живая кожа имеет сложный микрорельеф: поры, борозды, волосяные фолликулы. В
терминах Local Binary Patterns это даёт высокую энтропию распределения кодов.
Однородная литая поверхность даёт узкое распределение с преобладанием
«плоских» кодов.

🚨 WARNING: низкая сложность LBP возникает и при сильном шумоподавлении,
ретуши, размытии и низком разрешении. Кадр 1999 года из VHS даст низкую
сложность просто из-за отсутствия деталей — см. п.8 (компенсация качества).
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np

LBP_SCHEMA: Final[str] = "deeputin-lbp-complexity-v1.0"

MIN_MASK_PIXELS: Final[int] = 1024

try:  # scikit-image даёт эталонную реализацию с ротационной инвариантностью
    from skimage.feature import local_binary_pattern as _skimage_lbp
    _HAS_SKIMAGE = True
except Exception:  # pragma: no cover
    _skimage_lbp = None
    _HAS_SKIMAGE = False


def _fallback(reason: str) -> dict[str, Any]:
    return {"schema": LBP_SCHEMA, "status": "not_measurable", "reason": reason,
            "uniformity": float("nan"), "complexity": float("nan"),
            "entropy": float("nan"), "measured": False}


def _manual_lbp(gray: np.ndarray, radius: int, n_points: int) -> np.ndarray:
    """Резервная реализация LBP без scikit-image (кольцевая выборка)."""
    h, w = gray.shape
    codes = np.zeros((h - 2 * radius, w - 2 * radius), dtype=np.int64)
    centre = gray[radius:h - radius, radius:w - radius]
    for k in range(n_points):
        angle = 2.0 * np.pi * k / n_points
        dy = int(round(radius * np.sin(angle)))
        dx = int(round(radius * np.cos(angle)))
        shifted = gray[radius + dy:h - radius + dy, radius + dx:w - radius + dx]
        codes |= ((shifted >= centre).astype(np.int64) << k)
    return codes


def lbp_complexity_analysis(
    texture_map: np.ndarray,
    mask: np.ndarray | None = None,
    radius: int = 1,
    n_points: int = 8,
) -> dict[str, Any]:
    """📊 METRIC → Сложность микроструктуры через LBP (ТЗ п.6).

    Args:
        texture_map: (H, W) или (H, W, C); цвет усредняется.
        mask: булева маска пригодных пикселей.
        radius: радиус кольца выборки.
        n_points: число точек на кольце.

    Returns:
        `uniformity` (доля однородных кодов), `complexity` (1 - uniformity),
        `entropy` (нормированная энтропия гистограммы), `measured`.

    Raises:
        ValueError: недопустимая размерность или параметры LBP.
    """
    if radius < 1 or n_points < 4:
        raise ValueError("radius >= 1 и n_points >= 4 обязательны")

    image = np.asarray(texture_map)
    if image.ndim == 3:
        image = image.mean(axis=2)
    elif image.ndim != 2:
        raise ValueError(f"ожидается (H,W) или (H,W,C), получено {image.shape}")

    gray = image.astype(np.float64)
    if not np.isfinite(gray).any():
        return _fallback("текстура не содержит финитных значений")
    gray = np.nan_to_num(gray, nan=float(np.nanmean(gray)))

    valid: np.ndarray | None = None
    if mask is not None:
        mask_bool = np.asarray(mask, dtype=bool)
        if mask_bool.shape != gray.shape:
            return _fallback(f"форма маски {mask_bool.shape} != текстуры {gray.shape}")
        if int(mask_bool.sum()) < MIN_MASK_PIXELS:
            return _fallback(f"маска покрывает {int(mask_bool.sum())} < {MIN_MASK_PIXELS} пикселей")
        valid = mask_bool

    if min(gray.shape) < 2 * radius + 3:
        return _fallback(f"область {gray.shape} мала для radius={radius}")

    if _HAS_SKIMAGE:
        # skimage предупреждает, что на float-изображениях LBP даёт неустойчивый
        # результат из-за микроразличий соседних пикселей. Квантуем в uint8 по
        # фактическому динамическому диапазону кадра: это и убирает шум сравнения,
        # и делает метрику инвариантной к общей яркости/экспозиции.
        low, high = float(np.min(gray)), float(np.max(gray))
        span = high - low
        quantized = (np.zeros_like(gray) if span < 1e-9
                     else (gray - low) * (255.0 / span))
        codes = _skimage_lbp(quantized.astype(np.uint8), n_points, radius, method="uniform")
        inner = codes
        inner_mask = valid
        n_bins = n_points + 2
    else:  # pragma: no cover
        inner = _manual_lbp(gray, radius, n_points)
        inner_mask = None if valid is None else valid[radius:-radius, radius:-radius]
        n_bins = 2 ** n_points

    values = inner if inner_mask is None else inner[inner_mask]
    values = values[np.isfinite(values)]
    if values.size < MIN_MASK_PIXELS:
        return _fallback(f"после маскирования осталось {values.size} пикселей")

    histogram, _ = np.histogram(values, bins=n_bins, range=(0, n_bins))
    probability = histogram.astype(np.float64) / max(histogram.sum(), 1)
    nonzero = probability[probability > 0]
    entropy = float(-(nonzero * np.log2(nonzero)).sum())
    max_entropy = float(np.log2(n_bins))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else float("nan")

    # В методе "uniform" последний бин собирает НЕоднородные (шумные) паттерны,
    # а бины 0..n_points — однородные (края, пятна, плоские участки).
    # uniformity = доля однородных паттернов.
    uniformity = float(1.0 - probability[-1]) if probability.size >= 2 else float("nan")

    # Сложность микроструктуры определяется энтропией распределения кодов, а не
    # (1 - uniformity): плавный градиент состоит почти целиком из однородных
    # краевых паттернов одного типа — он "uniform", но микрорельефа не несёт,
    # и именно низкая энтропия это отражает.
    return {"schema": LBP_SCHEMA, "status": "measured", "measured": True,
            "uniformity": uniformity,
            "complexity": normalized_entropy,
            "entropy": normalized_entropy,
            "non_uniform_fraction": float(probability[-1]) if probability.size >= 2 else float("nan"),
            "analyzed_pixels": int(values.size),
            "backend": "skimage" if _HAS_SKIMAGE else "builtin",
            "interpretation": "низкая сложность = однородная поверхность; "
                              "то же даёт размытие, ретушь и низкое разрешение"}
