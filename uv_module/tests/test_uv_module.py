import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uv_module.config import HDUVConfig
from uv_module.generator import HDUVTextureGenerator, enhance_texture_details


def test_default_config_targets_1000px_atlas():
    cfg = HDUVConfig()
    assert cfg.uv_size == 1000
    assert cfg.super_sample >= 2  # may be upgraded; must be at least 2
    assert cfg.detail_enhance is True  # morph-only
    assert cfg.observed_erode_px >= 1
    assert cfg.seam_feather_px >= 18


def test_sampler_inverts_y_axis_for_opencv_remap():
    gen = HDUVTextureGenerator(HDUVConfig(uv_size=64, super_sample=1))
    y = np.array([[0.0, 1.0, 3.0, 7.0]], dtype=np.float32)
    np.testing.assert_allclose(
        gen._invert_y_for_remap(y, 8),
        np.array([[7.0, 6.0, 4.0, 0.0]], dtype=np.float32),
    )


def test_enhancement_never_touches_pixels_outside_mask():
    cfg = HDUVConfig()
    rng = np.random.default_rng(0)
    tex = rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)
    mask = np.zeros((64, 64), bool)
    mask[8:32, 8:32] = True
    out = enhance_texture_details(tex, mask, cfg)
    assert np.array_equal(out[~mask], tex[~mask])
