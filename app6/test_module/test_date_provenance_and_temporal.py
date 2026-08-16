"""🎯 GUARD → Покрытие часовых модулей временной оси и провенанса даты (ER-158).

Фокусированная 1-я волна «тестовой пирамиды»: date_provenance (D-002, ER-127)
и temporal_axis — оба чистые функции, гейтируют хронологические решения Stage 2.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from app6.stage2.date_provenance import CONFLICT_DAYS, parse_filename_date, resolve_date
from app6.stage2.temporal_axis import require_temporal_axis, temporal_status


def _rec(date, precision="day", role="evidence", axis=True):
    return SimpleNamespace(
        date=date,
        date_precision=precision,
        dataset_role=role,
        has_temporal_axis=lambda: axis,
    )


class ParseFilenameDateTests(unittest.TestCase):
    def test_day_precision(self):
        self.assertEqual(parse_filename_date("2020_05_17.jpg")[0], "2020-05-17")
        self.assertEqual(parse_filename_date("2020_05_17.jpg")[1], "day")

    def test_dotted_formats(self):
        self.assertEqual(parse_filename_date("IMG-2019.12.31.png")[0], "2019-12-31")

    def test_month_precision_when_no_day(self):
        value, precision = parse_filename_date("2018_06_archive")
        self.assertEqual(precision, "month")
        self.assertEqual(value, "2018-06-01")

    def test_year_precision_when_no_month(self):
        value, precision = parse_filename_date("video2001_clip")
        self.assertEqual(precision, "year")
        self.assertEqual(value, "2001-01-01")

    def test_no_date_yields_none(self):
        self.assertEqual(parse_filename_date("misc_label")[0], None)
        self.assertEqual(parse_filename_date("misc_label")[1], "none")

    def test_first_date_pattern_wins(self):
        self.assertEqual(parse_filename_date("2020_01_01_b_2021_02_02")[0], "2020-01-01")


class ResolveDateSemanticsTests(unittest.TestCase):
    def test_calibration_never_fabricates_a_date(self):
        out = resolve_date(filename="2020_01_01.jpg", dataset_role="calibration")
        self.assertEqual(out["date"], None)
        self.assertEqual(out["date_provenance_status"], "not_applicable")

    def test_missing_date_is_missing_not_zero(self):
        out = resolve_date(filename=None)
        self.assertEqual(out["date"], None)
        self.assertEqual(out["date_provenance_status"], "missing")

    def test_exif_takes_priority_over_filename(self):
        # D-002: EXIF — corroboration-надёжнее имени; source=exif.
        out = resolve_date(filename="2020_01_01.jpg", exif_date="2020-01-10")
        self.assertEqual(out["date_source"], "exif")
        self.assertEqual(out["date"], "2020-01-10")

    def test_exif_far_future_ignored_as_scan_date(self):
        # Пересканированные фото: EXIF далеко в будущем — датировка по имени.
        out = resolve_date(filename="2020_01_01.jpg", exif_date="2026-05-01")
        self.assertEqual(out["date_source"], "filename")
        self.assertEqual(out["date"], "2020-01-01")

    def test_close_exif_within_conflict_window_resolved_clean(self):
        out = resolve_date(filename="2020_01_01.jpg", exif_date="2020-01-02")
        self.assertEqual(out["date_provenance_status"], "resolved_exif")
        self.assertEqual(out["date_conflict_sources"], [])

    def test_conflicting_sources_report_conflict(self):
        # EXIF на 20 дней позже имени: не отсеян как «перескан» (>365 дн),
        # но расхождение > CONFLICT_DAYS => конфликт.
        out = resolve_date(filename="2020_01_01.jpg", exif_date="2020-01-20")
        self.assertEqual(out["date_source"], "exif")
        self.assertEqual(out["date_provenance_status"], "conflict")
        self.assertIn("filename", out["date_conflict_sources"])
        self.assertGreaterEqual(out["date_delta_days"], CONFLICT_DAYS)

    def test_rescan_exif_more_than_year_future_ignored(self):
        # Перескан: EXIF более чем на 365 дней впереди имени — игнорируется,
        # датировка честно остаётся за именем файла (D-002).
        out = resolve_date(filename="2020_01_01.jpg", exif_date="2021-06-01")
        self.assertEqual(out["date_source"], "filename")
        self.assertEqual(out["date"], "2020-01-01")
        self.assertEqual(out["date_provenance_status"], "resolved_filename")

    def test_claimed_used_only_as_last_resort(self):
        out = resolve_date(exif_date=None, filename=None, claimed_date="1999-12-25")
        self.assertEqual(out["date_source"], "claimed")
        self.assertEqual(out["date"], "1999-12-25")


class TemporalAxisTests(unittest.TestCase):
    def test_calibration_only_is_skipped(self):
        st = temporal_status([_rec(None, role="calibration") for _ in range(5)])
        self.assertFalse(st["applicable"])
        self.assertEqual(st["reason"], "calibration_dataset")

    def test_insufficient_dated_records_skipped(self):
        st = temporal_status([_rec("2020-01-01"), _rec("2020-01-02")])
        self.assertFalse(st["applicable"])
        self.assertEqual(st["reason"], "insufficient_dated_records")

    def test_insufficient_distinct_dates_skipped(self):
        st = temporal_status([_rec("2020-01-01"), _rec("2020-01-01"), _rec("2020-01-01")])
        self.assertFalse(st["applicable"])

    def test_undated_records_not_counted_toward_axis(self):
        records = [_rec("2020-01-01"), _rec("2020-01-02"), _rec("2020-01-03"),
                   _rec(None, axis=False)]
        st = temporal_status(records)
        self.assertTrue(st["applicable"])
        self.assertEqual(st["dated_count"], 3)

    def test_applicable_reports_distinct_dates(self):
        st = temporal_status([
            _rec("2020-01-01"), _rec("2020-01-01"), _rec("2020-02-01"), _rec("2020-03-01"),
        ])
        self.assertTrue(st["applicable"])
        self.assertEqual(st["distinct_dates"], 3)

    def test_applicable_confidence_limited_with_coarse_dates(self):
        st = temporal_status([
            _rec("2020-01-01", precision="year"),
            _rec("2020-02-01"), _rec("2020-03-01"),
        ])
        self.assertTrue(st["applicable"])
        self.assertEqual(st["confidence"], "limited_coarse_dates")
        self.assertEqual(st["coarse_precision_count"], 1)

    def test_require_temporal_axis_returns_skip_or_none(self):
        skip = require_temporal_axis([_rec("2020-01-01"), _rec("2020-01-02")])
        if skip is None:
            self.fail("expected a skip result for insufficient axis")
        self.assertFalse(skip["applicable"])
        self.assertEqual(require_temporal_axis([
            _rec("2020-01-01"), _rec("2020-01-02"), _rec("2020-03-05"),
        ]), None)


if __name__ == "__main__":
    unittest.main()