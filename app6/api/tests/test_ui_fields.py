"""🎯 GUARD → UI-поля и допуски калибровки (ER-165 / ER-117).

ui_fields.bone_score — derived display-only скор [0,1], не evidence-метрика:
нефинитный/отсутствующий z → None, а не ноль-подмена. resolve_tolerance
валидирует допуски (отрицательный/нечисловой → по умолчанию, не «калибровки
нет»).
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.api.noise_calibration import resolve_tolerance
from app6.api.ui_fields import bone_score, era_for, normalized_t, principal_coords, validate_ui_row


class EraForTests(unittest.TestCase):
    def test_maps_year_to_era(self):
        self.assertEqual(era_for("2005-06-01"), "1999-2007")
        self.assertEqual(era_for("2021-03-01"), "2020-2026")

    def test_unknown_date_returns_unknown(self):
        self.assertEqual(era_for(None), "unknown")
        self.assertEqual(era_for("not-a-date"), "unknown")


class NormalizedTTests(unittest.TestCase):
    def test_position_in_range(self):
        # exact ordinal ratio: (ordinal(d)-ordinal(a))/(ordinal(b)-ordinal(a)).
        first, last = "2020-01-01", "2020-02-01"
        self.assertEqual(normalized_t(first, first, last), 0.0)
        self.assertEqual(normalized_t(last, first, last), 1.0)
        mid = normalized_t("2020-01-16", first, last)
        self.assertGreater(mid, 0.0)
        self.assertLess(mid, 1.0)

    def test_midpoint_is_ordinal_ratio(self):
        # 2020-01-16 = 15 дней от начала, диапазон = 31 день → 15/31.
        t = normalized_t("2020-01-16", "2020-01-01", "2020-02-01")
        self.assertAlmostEqual(t, 15 / 31, places=6)

    def test_unknown_date_returns_none(self):
        self.assertIsNone(normalized_t(None, "2020-01-01", "2020-02-01"))

    def test_invalid_range_returns_zero(self):
        self.assertEqual(normalized_t("2020-01-01", "2020-02-01", "2020-01-01"), 0.0)


class BoneScoreTests(unittest.TestCase):
    def test_none_z_returns_none(self):
        self.assertIsNone(bone_score({}))

    def test_nonfinite_z_returns_none(self):
        self.assertIsNone(bone_score({"p95_point_z": float("nan")}))

    def test_derived_score_in_unit_interval(self):
        score = bone_score({"p95_point_z": 3.0})
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_high_z_drives_score_toward_zero(self):
        high = bone_score({"p95_point_z": 100.0})
        low = bone_score({"p95_point_z": 0.0})
        self.assertLess(high, low)
        self.assertAlmostEqual(low, 1.0)


class PrincipalCoordsTests(unittest.TestCase):
    def test_projection_shape_and_type(self):
        basis = np.eye(6)[:3]
        p = principal_coords([1.0, 2.0, 3.0, 0.0, 0.0, 0.0], basis)
        self.assertEqual(len(p), 3)
        self.assertTrue(all(isinstance(x, float) for x in p))

    def test_basis_shape_validation(self):
        with self.assertRaises(ValueError):
            principal_coords([1.0, 2.0], np.eye(2))


class ValidateUiRowTests(unittest.TestCase):
    def test_missing_required_fields_listed(self):
        errors = validate_ui_row({"id": "x", "date": "2020-01-01"})
        self.assertIn("t", errors)
        self.assertIn("boneScore", errors)
        self.assertNotIn("id", errors)


class ResolveToleranceTests(unittest.TestCase):
    def test_defaults_applied(self):
        result = resolve_tolerance(None)
        self.assertEqual(result, {"yaw": 2.0, "pitch": 1.0, "roll": 1.0})

    def test_valid_values_applied(self):
        result = resolve_tolerance({"yaw": 3.0, "pitch": 0.5})
        self.assertEqual(result["yaw"], 3.0)
        self.assertEqual(result["pitch"], 0.5)
        self.assertEqual(result["roll"], 1.0)  # не задан → дефолт

    def test_negative_or_non_numeric_ignored(self):
        result = resolve_tolerance({"yaw": -5.0, "pitch": "abc"})
        self.assertEqual(result["yaw"], 2.0)   # отрицательный → дефолт
        self.assertEqual(result["pitch"], 1.0)  # нечисловой → дефолт

    def test_nan_ignored(self):
        result = resolve_tolerance({"yaw": float("nan")})
        self.assertEqual(result["yaw"], 2.0)


if __name__ == "__main__":
    unittest.main()