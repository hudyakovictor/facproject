"""🎯 GUARD → Отменённая UV-аналитика и структура текстур (CD-124, ER-161).

uv_comparison: старый skin-package comparison явно удалён (CD-124) — вызов
бросает RemovedSkinPackageError с указанием использовать texture.json, а не
возвращается молча. texture_structure.register_patches: недостаточная общая
маска → достаточный статус (не фабрикуется структурное сравнение).
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage2.texture_structure import register_patches
from app6.stage2.uv_comparison import RemovedSkinPackageError, compare_packages


class RemovedUvComparisonTests(unittest.TestCase):
    def test_compare_packages_raises_clear_error(self):
        with self.assertRaises(RemovedSkinPackageError) as ctx:
            compare_packages(1, 2)
        self.assertIn("texture.json", str(ctx.exception))

    def test_error_subclasses_runtime_error(self):
        # Ожидаемый программный сигнал, перехватываемый как RuntimeError.
        self.assertTrue(issubclass(RemovedSkinPackageError, RuntimeError))


class RegisterPatchesFailClosedTests(unittest.TestCase):
    def test_insufficient_common_mask_returns_status(self):
        a = np.zeros((64, 64, 3), np.uint8)
        b = np.zeros((64, 64, 3), np.uint8)
        mask_a = np.zeros((64, 64), bool)
        mask_b = np.zeros((64, 64), bool)
        mask_a[0:10, 0:10] = True
        mask_b[0:10, 0:10] = True  # 100 px < 1000
        out = register_patches(a, b, mask_a, mask_b)
        self.assertEqual(out["status"], "insufficient_common_mask")
        self.assertEqual(out["common_pixels"], 100)

    def test_zero_common_mask_is_insufficient(self):
        a = np.zeros((64, 64, 3), np.uint8)
        b = np.zeros((64, 64, 3), np.uint8)
        mask_a = np.ones((64, 64), bool)
        mask_b = np.zeros((64, 64), bool)
        out = register_patches(a, b, mask_a, mask_b)
        self.assertEqual(out["status"], "insufficient_common_mask")


if __name__ == "__main__":
    unittest.main()