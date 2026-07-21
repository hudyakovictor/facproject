"""Decode image with EXIF orientation handling."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def decode_oriented(path: Path) -> tuple[np.ndarray, dict]:
    """Read image, apply EXIF orientation, return BGR array + decode metadata.

    Returns:
        bgr: HxWxBGR uint8 array
        meta: dict with orientation info
    """
    with Image.open(path) as img:
        had_exif = hasattr(img, "_getexif") and img._getexif() is not None
        oriented = ImageOps.exif_transpose(img)
        rgb = np.asarray(oriented.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    meta = {
        "exif_orientation_applied": had_exif,
        "original_size": list(img.size) if hasattr(img, "size") else None,
        "oriented_size": [int(bgr.shape[1]), int(bgr.shape[0])],
    }
    return bgr, meta
