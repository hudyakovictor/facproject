"""🔒 GUARD → Краевые случаи критических защит (docs/final).

Покрывает пробелы, не закрытые существующими тестами:
  1. Tamper-тест hash quartet: fail-closed на несовпадение/отсутствие хеша
     и детекция изменения кода через `compute_code_hash`.
  2. NULL-защита irreversible-return: почти стабильная серия (малый mid
     divergence) НЕ активирует возврат благодаря абсолютному floor.
  3. Same-day contamination hardening: нижние 80% базовой линии не дают
     контаминации «протечь» в порог; конфликты-выбросы всё равно ловятся.
  4. FDR при m<20: fallback на одиночный z и явный diagnostic-only флаг.

Все тесты самодостаточны и не требуют весов 3DDFA или фотодатасета.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from app6.stage2.integrity import (
    IntegrityError,
    REQUIRED_HASH_KEYS,
    compute_code_hash,
    verify_integrity_hashes,
)
from app6.stage2.irreversible_return import detect_irreversible_return
from app6.stage2.multiple_testing import apply_pair_fdr
from app6.stage2.same_day_gate import check_same_day_conflict


class IntegrityGuardTests(unittest.TestCase):
    """Идея 1: tamper-тест hash quartet."""

    def test_mismatch_fails_closed(self):
        expected = {"dataset_hash": "a" * 64, "code_hash": "b" * 64,
                    "model_hash": "c" * 64, "config_hash": "d" * 64}
        actual = dict(expected)
        actual["code_hash"] = "e" * 64
        with self.assertRaises(IntegrityError) as ctx:
            verify_integrity_hashes(expected, actual)
        self.assertIn("code_hash", str(ctx.exception))

    def test_missing_key_fails_closed(self):
        expected = {"dataset_hash": "a" * 64, "code_hash": "b" * 64,
                    "model_hash": "c" * 64, "config_hash": "d" * 64}
        actual = {"dataset_hash": "a" * 64}  # остальные отсутствуют
        with self.assertRaises(IntegrityError) as ctx:
            verify_integrity_hashes(expected, actual)
        self.assertIn("отсутствуют", str(ctx.exception))
        self.assertIn("code_hash", str(ctx.exception))

    def test_non_strict_reports_mismatch_without_raising(self):
        expected = {"dataset_hash": "a" * 64, "code_hash": "b" * 64,
                    "model_hash": "c" * 64, "config_hash": "d" * 64}
        actual = dict(expected)
        actual["model_hash"] = "z" * 64
        report = verify_integrity_hashes(expected, actual, strict=False)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["mismatched"], ["model_hash"])

    def test_code_hash_changes_when_code_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app6" / "stage1").mkdir(parents=True)
            (root / "app6" / "stage2").mkdir(parents=True)
            f1 = root / "app6" / "stage1" / "a.py"
            f2 = root / "app6" / "stage2" / "b.py"
            f1.write_text("x = 1\n", encoding="utf-8")
            f2.write_text("y = 2\n", encoding="utf-8")
            h1 = compute_code_hash(root)
            self.assertEqual(len(h1), 64)
            # Подмена содержимого кода обязана изменить хеш.
            f2.write_text("y = 3\n", encoding="utf-8")
            h2 = compute_code_hash(root)
            self.assertNotEqual(h1, h2)

    def test_required_hash_keys_are_the_quartet(self):
        self.assertEqual(REQUIRED_HASH_KEYS,
                         ("dataset_hash", "code_hash", "model_hash", "config_hash"))


class IrreversibleReturnFloorTests(unittest.TestCase):
    """Идея 4: NULL не активирует возврат из-за абсолютного floor."""

    def test_near_stable_series_is_not_a_return(self):
        # A и B почти совпадают: mid divergence << 0.03 floor.
        a = [1.0, 0.0, 0.0]
        b = [0.999, 0.001, 0.0]  # divergence ~1e-3 < floor 0.03
        timeline = [
            {"date": "2000-01-01", "photo_id": "A1", "shape": a},
            {"date": "2004-01-01", "photo_id": "B", "shape": b},
            {"date": "2010-01-01", "photo_id": "A2", "shape": a},
        ]
        self.assertEqual(detect_irreversible_return(timeline), [])

    def test_genuine_return_with_large_divergence_is_detected(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]  # ортогонально: divergence ~1.0 >> floor
        timeline = [
            {"date": "2000-01-01", "photo_id": "A1", "shape": a},
            {"date": "2004-01-01", "photo_id": "B", "shape": b},
            {"date": "2010-01-01", "photo_id": "A2", "shape": a},
        ]
        anomalies = detect_irreversible_return(timeline)
        self.assertEqual(len(anomalies), 1)
        self.assertTrue(anomalies[0]["not_a_verdict"])

    def test_short_gap_is_not_a_return(self):
        # Разрыв < min_years (5) — не возврат.
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        timeline = [
            {"date": "2000-01-01", "photo_id": "A1", "shape": a},
            {"date": "2001-01-01", "photo_id": "B", "shape": b},
            {"date": "2002-01-01", "photo_id": "A2", "shape": a},
        ]
        self.assertEqual(detect_irreversible_return(timeline), [])


class SameDayContaminationTests(unittest.TestCase):
    """Идея 5: lower80-политика защищает порог от контаминации."""

    def test_outliers_do_not_inflate_baseline(self):
        # 8 «чистых» внутридневных пар ~1.0 и 2 выброса (6, 7).
        rows = []
        for i, v in enumerate([1.0, 1.05, 0.95, 1.02, 0.98, 1.04, 0.96, 1.01, 6.0, 7.0]):
            rows.append({"pair_id": str(i), "date_a": "2020-01-01", "date_b": "2020-01-01",
                         "photo_a": f"a{i}", "photo_b": f"b{i}", "pose_bin": "frontal",
                         "ldm134_rmse": v})
        hits = check_same_day_conflict(rows)
        # Ловятся именно выбросы, а не чистые пары.
        self.assertEqual(len(hits), 2)
        self.assertEqual({h["photo_a"] for h in hits}, {"a8", "a9"})
        for h in hits:
            # Без capture_event — одно событие на дату; квантильная политика
            # недоступна (MIN_BASELINE_EVENTS=3), включается sigma-fallback v1.
            self.assertEqual(h["baseline_policy"], "lower80_sigma_fallback_v1")
            self.assertEqual(h["baseline_retained_count"], 8)

    def test_below_min_baseline_returns_empty(self):
        rows = [{"pair_id": str(i), "date_a": "2020-01-01", "date_b": "2020-01-01",
                 "photo_a": f"a{i}", "photo_b": f"b{i}", "pose_bin": "frontal",
                 "ldm134_rmse": 5.0} for i in range(3)]
        self.assertEqual(check_same_day_conflict(rows), [])


class FdrLowCountTests(unittest.TestCase):
    """Идея 4/статистика: m<20 → fallback и diagnostic-only."""

    def test_low_calibrated_count_is_diagnostic_only(self):
        rows = [{"p95_point_z": 4.0, "calibrated_point_count": 10}]  # m < 20
        report = apply_pair_fdr(rows)
        self.assertIn("mt_p_approx", rows[0])
        self.assertIn("mt_q_value", rows[0])
        self.assertEqual(rows[0]["mt_role"], "diagnostic_only")
        self.assertTrue(rows[0]["mt_fdr10_diagnostic_flag"])
        self.assertTrue(report["not_a_verdict"])

    def test_high_count_uses_order_statistic(self):
        rows = [{"p95_point_z": 4.0, "calibrated_point_count": 120}]  # m >= 20
        apply_pair_fdr(rows)
        self.assertIn("mt_p_approx", rows[0])
        self.assertEqual(rows[0]["mt_role"], "diagnostic_only")


if __name__ == "__main__":
    unittest.main()