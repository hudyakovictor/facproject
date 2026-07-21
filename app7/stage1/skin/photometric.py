"""Photometric normalization branches for illumination-robust analysis."""

from __future__ import annotations

import cv2
import numpy as np


def branches(bgr: np.ndarray, mask: np.ndarray) -> dict[str, np.ndarray]:
    """Compute raw and normalized luminance channels.

    The low-frequency normalized channel removes large-scale illumination
    gradients and is used as input for texture/wrinkle extractors that
    are sensitive to lighting direction.

    Args:
        bgr: HxWxBGR uint8
        mask: HxW bool domain mask

    Returns:
        dict with raw_luminance (float16), low_frequency_normalized (float16),
        and normalization_scale (float32).
    """
    raw = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    # Low-frequency illumination estimate via large Gaussian
    sigma = max(3, min(raw.shape) * 0.025)
    base = cv2.GaussianBlur(raw, (0, 0), sigma)
    norm = raw - base
    # Noise-anchored normalization: scale so that local MAD ≈ 1
    m = np.asarray(mask, bool)
    if np.any(m):
        med = float(np.median(norm[m]))
        s = 1.4826 * float(np.median(np.abs(norm[m] - med)))
        s = max(s, 1e-4)
    else:
        s = 1.0
    norm = np.clip(norm / s, -6, 6)
    norm[~m] = 0
    return {
        "raw_luminance": raw.astype(np.float16),
        "low_frequency_normalized": norm.astype(np.float16),
        "normalization_scale": np.array(s, np.float32),
    }
