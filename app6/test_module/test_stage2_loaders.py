"""Regression tests for fail-closed Stage 2 loading."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app6.stage2.loaders import _read_landmark_csv, _required_npz_array


class Stage2LoaderContractTest(unittest.TestCase):
    def test_required_array_rejects_coordinate_space_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "record.npz"
            np.savez(path, ldm106_object_normalized=np.zeros((106, 3), np.float32))
            with np.load(path, allow_pickle=False) as z:
                with self.assertRaisesRegex(ValueError, "ldm106_chronology_aligned"):
                    _required_npz_array(z, "ldm106_chronology_aligned", (106, 3))

    def test_landmark_csv_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ldm.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["landmark_id", "x", "y", "z"])
                w.writeheader()
                w.writerow({"landmark_id": 0, "x": 0, "y": 0, "z": 0})
                w.writerow({"landmark_id": 0, "x": 1, "y": 1, "z": 1})
            with self.assertRaisesRegex(ValueError, "duplicate landmark_id"):
                _read_landmark_csv(path, 2)

    def test_landmark_csv_rejects_missing_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ldm.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["landmark_id", "x", "y", "z"])
                w.writeheader()
                w.writerow({"landmark_id": 0, "x": 0, "y": 0, "z": 0})
            with self.assertRaisesRegex(ValueError, "missing landmark ids"):
                _read_landmark_csv(path, 2)


if __name__ == "__main__":
    unittest.main()
