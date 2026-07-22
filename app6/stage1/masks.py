"""🎯 CRITICAL → Построение бандла масок (семантика 8 каналов + skin-производные).
🔗 DEPENDS ON: config.SEMANTIC_POLICY — правила сведения каналов
🚪 API: build_mask_bundle() — вызывается из engine._one()
🚨 WARNING: порядок CHANNEL_NAMES жёсткий — валидатор stage1 проверяет shape.
"""
from __future__ import annotations
from .status_logger import log_status, log_blocker, log_warning

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .config import SEMANTIC_POLICY

CHANNEL_NAMES = (
    "right_eye", "left_eye", "right_eyebrow", "left_eyebrow",
    "nose", "upper_lip", "lower_lip", "skin",
)


@dataclass
class MaskBundle:
    channels_224: np.ndarray
    soft_224: np.ndarray
    hard_224: np.ndarray
    soft_original: np.ndarray | None
    hard_original: np.ndarray | None
    status: str
    error: str | None
    metadata: dict[str, Any]


def build_mask_bundle(channels: np.ndarray, trans_params: np.ndarray, image_shape: tuple[int, ...]) -> MaskBundle:
    """🎯 CRITICAL → Создание маски кожи из семантических каналов 3DDFA.

    Использует 8 каналов сегментации:
    0,1 = right/left eye | 2,3 = right/left eyebrow | 4 = nose | 5,6 = upper/lower lip | 7 = skin

    Маска кожи = max(skin, nose) * (1 - max(eyes, eyebrows, lips))

    🔗 DEPENDS ON:
      - engine._one() — вызывается после 3DDFA inference
      - semantic_channels_224 — из результатов 3DDFA

    ⚠️ IN PROGRESS:
      - Hard threshold 0.5 может быть слишком строгим для границ
      - Нет проверки что маска достаточно большая (мин. площадь)

    💡 NOTE:
      - Soft mask (0-1) для взвешенного анализа
      - Hard mask (bool) для бинарных решений
      - Projection в оригинальное изображение через back_resize_crop_img

    🚨 WARNING:
      - При projection failure — soft_original/hard_original = None
      - Никогда не растягивать 224px маску на полное изображение!
    """
    log_status("build_mask_bundle", "complete")
    a = np.asarray(channels, np.float32)
    if a.shape != (224, 224, 8):
        raise ValueError(f"semantic channels must be (224,224,8), got {a.shape}")
    face_skin = np.maximum(a[:, :, 7], a[:, :, 4])
    excluded = np.maximum.reduce([a[:, :, i] for i in (0, 1, 2, 3, 5, 6)])
    soft = np.clip(face_skin * (1.0 - np.clip(excluded, 0.0, 1.0)), 0.0, 1.0)
    hard = soft >= 0.50
    areas = {name: float(np.mean(a[:, :, i] >= 0.5)) for i, name in enumerate(CHANNEL_NAMES)}
    meta = {
        "policy": SEMANTIC_POLICY,
        "channel_names": list(CHANNEL_NAMES),
        "channel_area_fraction_224": areas,
        "soft_area_fraction_224": float(np.mean(soft > 0.05)),
        "hard_area_fraction_224": float(np.mean(hard)),
        "fallback_used": False,
    }
    try:
        from util.io import back_resize_crop_img
        h, w = image_shape[:2]
        skin_u8 = np.clip(face_skin * 255.0, 0, 255).astype(np.uint8)
        excluded_u8 = np.clip(excluded * 255.0, 0, 255).astype(np.uint8)
        blank = np.zeros((h, w, 3), np.uint8)
        skin_projected = back_resize_crop_img(np.repeat(skin_u8[:, :, None], 3, axis=2), trans_params, blank, resample_method=Image.BILINEAR)
        excluded_projected = back_resize_crop_img(np.repeat(excluded_u8[:, :, None], 3, axis=2), trans_params, blank, resample_method=Image.NEAREST)
        full_skin = np.asarray(skin_projected[:, :, 0], np.uint8)
        full_excluded = np.asarray(excluded_projected[:, :, 0], np.uint8)
        # One-pixel safety dilation prevents eye/brow/lip boundary leakage into
        # texture measurements. It only removes evidence; it never adds skin.
        full_excluded = cv2.dilate((full_excluded >= 32).astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1).astype(bool)
        full_soft = np.where(full_excluded, 0, full_skin).astype(np.uint8)
        full_hard = (full_skin >= 128) & ~full_excluded
        meta["original_exclusion_policy"] = "eye+brow+upper_lip+lower_lip nearest projection, threshold 32/255, dilate 1px"
        meta["soft_area_fraction_original"] = float(np.mean(full_soft > 10))
        meta["hard_area_fraction_original"] = float(np.mean(full_hard))
        return MaskBundle(a.astype(np.float16), soft, hard, full_soft, full_hard, "valid", None, meta)
    except Exception as exc:
        # Never stretch aligned 224x224 data over the full source image.
        meta["fallback_used"] = True  # projection failed; using 224px masks only
        return MaskBundle(a.astype(np.float16), soft, hard, None, None, "projection_failed", str(exc), meta)

