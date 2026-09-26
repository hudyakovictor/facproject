"""🖼 Декодирование входных изображений (app8).

Единая точка декода для ВСЕГО пайплайна: 3D-реконструкция, UV-развертка, кропы и
текстурные метрики должны видеть одни и те же пиксели.

🔗 ССЫЛКА: повторяет `app6.stage1.input_provenance.decode_oriented` (Pillow +
`ImageOps.exif_transpose` + RGB->BGR), чтобы метрики app6 и app8 считались по
идентичным пикселям. Провенанс EXIF здесь не сериализуется - только пиксели.
"""
from __future__ import annotations
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def decode_oriented_bgr(path: str | Path) -> np.ndarray:
    """Читает фото с применением EXIF-ориентации и возвращает uint8 BGR.

    Raises:
        ValueError: файл не читается как изображение.
    """
    try:
        with Image.open(path) as im:
            rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
    except Exception as exc:
        raise ValueError(f"cannot decode image {path}: {exc}") from exc
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
