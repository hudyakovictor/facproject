"""ТЗ п.5–7: FFT, LBP и спектральный анализ альбедо."""
from __future__ import annotations

import numpy as np
import pytest

from app6.stage1.authenticity.albedo_analysis import albedo_spectral_analysis
from app6.stage1.authenticity.fft_analysis import fft_regularity_analysis
from app6.stage1.authenticity.lbp_analysis import lbp_complexity_analysis


class TestFFT:
    def test_regular_pattern_scores_high(self, synthetic_textures) -> None:
        result = fft_regularity_analysis(synthetic_textures["moulded"],
                                         synthetic_textures["mask"])
        assert result["measured"] is True
        assert result["regularity_score"] > 0.5

    def test_skin_scores_low(self, synthetic_textures) -> None:
        result = fft_regularity_analysis(synthetic_textures["skin"],
                                         synthetic_textures["mask"])
        assert result["regularity_score"] < 0.2

    def test_regular_separates_from_skin(self, synthetic_textures) -> None:
        moulded = fft_regularity_analysis(synthetic_textures["moulded"],
                                          synthetic_textures["mask"])
        skin = fft_regularity_analysis(synthetic_textures["skin"],
                                       synthetic_textures["mask"])
        assert moulded["regularity_score"] > skin["regularity_score"]
        assert moulded["spectral_entropy"] < skin["spectral_entropy"]

    def test_fft_empty_mask_returns_fallback(self, synthetic_textures) -> None:
        result = fft_regularity_analysis(synthetic_textures["skin"],
                                         np.zeros((160, 160), dtype=bool))
        assert result["measured"] is False
        assert result["status"] == "not_measurable"
        assert np.isnan(result["regularity_score"])

    def test_fft_bad_shape_rejected(self) -> None:
        with pytest.raises(ValueError):
            fft_regularity_analysis(np.zeros(10))


class TestLBP:
    def test_smooth_surface_has_low_complexity(self, synthetic_textures) -> None:
        result = lbp_complexity_analysis(synthetic_textures["smooth_gradient"],
                                         synthetic_textures["mask"])
        assert result["complexity"] < 0.5

    def test_skin_has_high_complexity(self, synthetic_textures) -> None:
        result = lbp_complexity_analysis(synthetic_textures["skin"],
                                         synthetic_textures["mask"])
        assert result["complexity"] > 0.7

    def test_rotation_invariance(self, synthetic_textures) -> None:
        base = lbp_complexity_analysis(synthetic_textures["skin"],
                                       synthetic_textures["mask"])["complexity"]
        rotated = lbp_complexity_analysis(np.rot90(synthetic_textures["skin"]),
                                          synthetic_textures["mask"])["complexity"]
        assert base == pytest.approx(rotated, abs=1e-6)

    def test_exposure_invariance(self, synthetic_textures) -> None:
        base = lbp_complexity_analysis(synthetic_textures["skin"],
                                       synthetic_textures["mask"])["complexity"]
        darker = lbp_complexity_analysis(synthetic_textures["skin"] * 0.5 + 40,
                                         synthetic_textures["mask"])["complexity"]
        assert base == pytest.approx(darker, abs=1e-6)

    def test_lbp_small_mask_returns_fallback(self, synthetic_textures) -> None:
        mask = np.zeros((160, 160), dtype=bool)
        mask[:5, :5] = True
        assert lbp_complexity_analysis(synthetic_textures["skin"], mask)["measured"] is False

    def test_invalid_parameters_rejected(self, synthetic_textures) -> None:
        with pytest.raises(ValueError):
            lbp_complexity_analysis(synthetic_textures["skin"], radius=0)


class TestAlbedo:
    @staticmethod
    def _skin_patch() -> np.ndarray:
        rng = np.random.default_rng(7)
        base = rng.normal(0.55, 0.07, (120, 120))
        return np.clip(np.stack([base * 1.25, base * 0.95, base * 0.9], axis=-1), 0, 1)

    @staticmethod
    def _uniform_patch() -> np.ndarray:
        rng = np.random.default_rng(8)
        flat = np.stack([np.full((120, 120), 0.72), np.full((120, 120), 0.68),
                         np.full((120, 120), 0.66)], axis=-1)
        return np.clip(flat + rng.normal(0, 0.004, (120, 120, 3)), 0, 1)

    def test_uniform_patch_differs_from_skin(self) -> None:
        skin = albedo_spectral_analysis(self._skin_patch())
        uniform = albedo_spectral_analysis(self._uniform_patch())
        assert skin["measured"] and uniform["measured"]
        assert skin["redness_ratio"] > uniform["redness_ratio"]

    def test_various_skin_tones_are_measurable(self) -> None:
        """Фототипы I–IV не должны вызывать отказ измерения."""
        for tone in (0.35, 0.5, 0.65, 0.8):
            rng = np.random.default_rng(3)
            base = np.clip(rng.normal(tone, 0.05, (120, 120)), 0, 1)
            patch = np.clip(np.stack([base * 1.2, base * 0.95, base * 0.9], -1), 0, 1)
            assert albedo_spectral_analysis(patch)["measured"] is True

    def test_albedo_small_mask_returns_fallback(self) -> None:
        mask = np.zeros((120, 120), dtype=bool)
        mask[:3, :3] = True
        assert albedo_spectral_analysis(self._skin_patch(), mask)["measured"] is False

    def test_albedo_bad_shape_rejected(self) -> None:
        with pytest.raises(ValueError):
            albedo_spectral_analysis(np.zeros((10, 10)))

    def test_accepts_uint8_range(self) -> None:
        patch = (self._skin_patch() * 255).astype(np.uint8)
        assert albedo_spectral_analysis(patch)["measured"] is True
