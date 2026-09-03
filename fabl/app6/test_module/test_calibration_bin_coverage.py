"""🍔 GUARD → Покрытие калибровки по 9 поз-ракурсам (ER-174).

Проверяет, что адаптер калибровки может дать явный отчёт о покрытии 9/9:
пустой ракурс больше не теряется молча, а возвращается как ``missing``.
Полный контракт отчёта — в src:app6.stage2.loaders.calibration_bin_coverage.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from app6.stage2.loaders import (
    CALIBRATION_BIN_COVERAGE_SCHEMA,
    CALIBRATION_POSE_BINS,
    calibration_bin_coverage,
)


def _rec(pose: str, dataset_id: str = "p1", source_group: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        pose_bin=pose,
        dataset_id=dataset_id,
        source_group=source_group or dataset_id,
    )


class CalibrationBinCoverageTests(unittest.TestCase):
    def test_full_coverage_is_9_of_9(self):
        records = [_rec(pose) for pose in CALIBRATION_POSE_BINS]
        report = calibration_bin_coverage(records)
        self.assertEqual(report["schema"], CALIBRATION_BIN_COVERAGE_SCHEMA)
        self.assertEqual(report["coverage_ratio"], 1.0)
        self.assertEqual(report["missing_bins"], [])
        self.assertEqual(report["covered_bins"], list(CALIBRATION_POSE_BINS))
        self.assertEqual(report["total_records"], 9)

    def test_empty_bin_is_reported_missing(self):
        records = [_rec(pose) for pose in CALIBRATION_POSE_BINS if pose != "right_profile"]
        report = calibration_bin_coverage(records)
        self.assertEqual(report["missing_bins"], ["right_profile"])
        self.assertEqual(report["coverage_ratio"], round(8 / 9, 4))
        self.assertTrue(report["buckets"]["right_profile"]["missing"])
        self.assertFalse(report["buckets"]["frontal"]["missing"])

    def test_empty_record_list_reports_all_missing(self):
        report = calibration_bin_coverage([])
        self.assertEqual(len(report["missing_bins"]), 9)
        self.assertEqual(report["coverage_ratio"], 0.0)
        self.assertEqual(report["total_records"], 0)

    def test_unknown_pose_bin_is_not_counted(self):
        records = [_rec(pose) for pose in CALIBRATION_POSE_BINS[:3]]
        records.append(_rec("bogus_bin", dataset_id="pX"))
        report = calibration_bin_coverage(records)
        # bogus_bin не входит ни в один из 9 канонических ракурсов.
        self.assertEqual(report["total_records"], 4)  # учитывается как запись
        self.assertEqual(report["coverage_ratio"], round(3 / 9, 4))
        self.assertEqual(len(report["missing_bins"]), 6)

    def test_person_count_is_deduped_by_dataset_id(self):
        records = [_rec("frontal", dataset_id="p1"), _rec("frontal", dataset_id="p1", source_group="other")]
        records += [_rec("frontal", dataset_id="p2")]
        report = calibration_bin_coverage(records)
        self.assertEqual(report["buckets"]["frontal"]["frame_count"], 3)
        self.assertEqual(report["buckets"]["frontal"]["person_count"], 2)

    def test_all_reports_have_nine_buckets(self):
        report = calibration_bin_coverage([])
        self.assertEqual(len(report["buckets"]), 9)
        self.assertEqual(set(report["buckets"]), set(CALIBRATION_POSE_BINS))


if __name__ == "__main__":
    unittest.main()