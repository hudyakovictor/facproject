"""🎯 GUARD → Чувствительность калибровки LOO (ER-102/ER-107).

leave_one_dataset_sensitivity: при < 3 калибровочных датасетов — fail-closed
insufficient_calibration_datasets (порог не доверяется слишком малому числу
независимых личностей), а не молчаливая оценка.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from app6.stage2.calibration_sensitivity import SENSITIVITY_SCHEMA, leave_one_dataset_sensitivity


def _rec(dataset_id: str) -> SimpleNamespace:
    return SimpleNamespace(dataset_id=dataset_id)


class LeaveOneDatasetSensitivityTests(unittest.TestCase):
    def test_too_few_datasets_is_fail_closed(self):
        records = [_rec("p1"), _rec("p2")]  # только 2 датасета < 3
        out = leave_one_dataset_sensitivity(records, np.zeros(10, np.float32), np.zeros(10, np.float32))
        self.assertEqual(out["schema"], SENSITIVITY_SCHEMA)
        self.assertEqual(out["status"], "insufficient_calibration_datasets")
        self.assertEqual(out["dataset_count"], 2)
        self.assertEqual(out["entries"], [])

    def test_zero_records_is_fail_closed(self):
        out = leave_one_dataset_sensitivity([], np.zeros(10, np.float32), np.zeros(10, np.float32))
        self.assertEqual(out["status"], "insufficient_calibration_datasets")

    def test_duplicate_dataset_ids_count_once(self):
        records = [_rec("p1"), _rec("p1"), _rec("p1")]  # фактически 1 датасет
        out = leave_one_dataset_sensitivity(records, np.zeros(10, np.float32), np.zeros(10, np.float32))
        self.assertEqual(out["dataset_count"], 1)
        self.assertEqual(out["status"], "insufficient_calibration_datasets")


if __name__ == "__main__":
    unittest.main()