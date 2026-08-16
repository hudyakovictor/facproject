"""🎯 GUARD → Текстурная статистика — visualization-only (ER-161 / CD-124).

_texture_image: недостаточная маска (<64 px) → значения-нули (fail-closed,
а не фабрикация измерения). lbp-гистограмма при недостаточных данных — нулевой
вектор. Текстура остаётся visualization-only каналом, не evidence-метрикой.
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage2.texture_image import LBP_BINS, _glcm_stats, _lbp_histogram, _stats


class LbpHistogramTests(unittest.TestCase):
    def test_insufficient_mask_returns_zero_histogram(self):
        gray = np.zeros((50, 50), np.uint8)
        mask = np.zeros((50, 50), bool)
        mask[0:5, 0:5] = True  # 25 px < 64
        hist = _lbp_histogram(gray, mask)
        self.assertFalse(hist.any())
        self.assertEqual(len(hist), LBP_BINS)


class GlcmStatsTests(unittest.TestCase):
    def test_insufficient_mask_returns_zeros(self):
        gray = np.zeros((50, 50), np.uint8)
        mask = np.zeros((50, 50), bool)
        out = _glcm_stats(gray, mask)
        self.assertEqual(out["glcm_contrast"], 0.0)
        self.assertEqual(out["glcm_energy"], 0.0)
        # Не фабрикуется как «измеренная плоская текстура».
        self.assertEqual(out["glcm_homogeneity"], 0.0)


class StatsFailClosedTests(unittest.TestCase):
    def test_insufficient_mask_returns_zero_contract(self):
        img = np.zeros((50, 50, 3), np.uint8)
        mask = np.zeros((50, 50), bool)
        out = _stats(img, mask)
        self.assertEqual(out["texture_pixels"], 0)
        self.assertEqual(out["gray_mean"], 0.0)
        self.assertEqual(out["lbp_histogram"], [0.0] * LBP_BINS)

    def test_missing_texture_never_looks_measured(self):
        img = np.zeros((60, 60, 3), np.uint8)
        mask = np.zeros((60, 60), bool)
        mask[0:7, 0:7] = True  # 49 px < 64
        out = _stats(img, mask)
        # Маленькая маска не даёт ненулевые текстурные метрики, которые можно
        # принять за реальное измерение.
        self.assertEqual(out["texture_pixels"], 49)
        self.assertEqual(out["gray_std"], 0.0)


if __name__ == "__main__":
    unittest.main()