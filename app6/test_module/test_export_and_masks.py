"""🎯 GUARD → Стабильная выгрузка CSV и маска кожи (ER-025/026, ER-018).

export: стабильный порядок колонок между прогонами (D9), валидация заголовков
прямо и строго. masks: skin-маска из 8 семантических каналов; при недоступной
проекции 224px-маска НЕ растягивается на исходное изображение (fallback_used),
а выставляется projection_failed — маска остаётся в 224px.
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage1.masks import build_mask_bundle
from app6.stage2.export import CsvHeaderError, stable_fieldnames, validate_csv_headers


class ValidateCsvHeadersTests(unittest.TestCase):
    def test_valid_data_returns_true(self):
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        self.assertTrue(validate_csv_headers(rows, ["a", "b"], strict=True))

    def test_missing_field_raises_in_strict_mode(self):
        rows = [{"a": 1, "b": 2}]
        with self.assertRaises(CsvHeaderError):
            validate_csv_headers(rows, ["a", "b", "c"], strict=True)

    def test_extra_field_not_allowed_in_strict(self):
        rows = [{"a": 1, "b": 2, "z": 9}]
        self.assertFalse(validate_csv_headers(rows, ["a", "b"], strict=True))

    def test_empty_expected_rejected(self):
        with self.assertRaises(ValueError):
            validate_csv_headers([{"a": 1}], [])

    def test_duplicate_expected_rejected(self):
        with self.assertRaises(ValueError):
            validate_csv_headers([{"a": 1}], ["a", "a"])


class StableFieldnamesTests(unittest.TestCase):
    def test_preferred_first_then_alphabetical(self):
        rows = [{"z": 1, "a": 2, "m": 3}]
        self.assertEqual(stable_fieldnames(rows, preferred=["m"]), ["m", "a", "z"])

    def test_deterministic_across_row_orders(self):
        rows1 = [{"b": 1, "a": 2}, {"c": 3}]
        rows2 = [{"c": 3}, {"a": 2, "b": 1}]
        self.assertEqual(stable_fieldnames(rows1), stable_fieldnames(rows2))

    def test_preferred_missing_keys_ignored(self):
        rows = [{"x": 1}]
        self.assertEqual(stable_fieldnames(rows, preferred=["ghost", "x"]), ["x"])


class BuildMaskBundleTests(unittest.TestCase):
    def _channels(self):
        a = np.zeros((224, 224, 8), np.float32)
        a[:, :, 7] = 1.0   # skin
        a[50:100, 50:100, 0] = 1.0  # eye region
        return a

    def test_bad_shape_rejected(self):
        with self.assertRaises(ValueError):
            build_mask_bundle(np.zeros((10, 10, 3)), np.zeros(6), (224, 224))

    def test_produces_finite_224_masks(self):
        bundle = build_mask_bundle(self._channels(), np.zeros(6, np.float32), (224, 224))
        self.assertEqual(bundle.hard_224.shape, (224, 224))
        self.assertTrue(np.isfinite(bundle.soft_224).all())
        self.assertIn(bundle.status, ("valid", "projection_failed"))

    def test_fallback_never_stretches_224_over_full_image(self):
        # Если проекция недоступна — original-маски None, а не растянутые 224px.
        bundle = build_mask_bundle(self._channels(), np.zeros(6, np.float32), (224, 224))
        if bundle.status == "projection_failed":
            self.assertTrue(bundle.metadata["fallback_used"])
            self.assertIsNone(bundle.soft_original)
            self.assertIsNone(bundle.hard_original)


if __name__ == "__main__":
    unittest.main()