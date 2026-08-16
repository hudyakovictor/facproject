"""🎯 GUARD → Валидация записей Stage 1: _csv_check (ER-013/014).

_csv_check проверяет landmark CSV: корректное число строк, непрерывная
последовательность landmark_id. Повреждённый CSV даёт понятную ValidationError,
а не молчаливый пропуск записи (resume-валидатор).
"""
from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from app6.stage1.validator import _csv_check, ValidationError


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as h:
        writer = csv.DictWriter(h, fieldnames=["landmark_id", "x", "y", "z", "vertex_index"])
        writer.writeheader()
        writer.writerows(rows)


def _row(i: int) -> dict[str, str]:
    return {"landmark_id": str(i), "x": "0.1", "y": "0.2", "z": "0.3", "vertex_index": str(i)}


class CsvCheckTests(unittest.TestCase):
    def test_valid_csv_returns_points_and_indices(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "ldm.csv"
            _write_csv(p, [_row(i) for i in range(5)])
            points, indices = _csv_check(p, expected=5)
            self.assertEqual(points.shape, (5, 3))
            np.testing.assert_array_equal(indices, np.arange(5, dtype=np.int64))

    def test_wrong_row_count_gives_clear_error(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "ldm.csv"
            _write_csv(p, [_row(i) for i in range(3)])
            with self.assertRaises(ValidationError) as ctx:
                _csv_check(p, expected=5)
            self.assertIn("expected 5 rows", str(ctx.exception))

    def test_invalid_landmark_id_sequence_gives_clear_error(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "ldm.csv"
            rows = [_row(i) for i in range(4)]
            rows[2]["landmark_id"] = "99"  # нарушить последовательность
            _write_csv(p, rows)
            with self.assertRaises(ValidationError) as ctx:
                _csv_check(p, expected=4)
            self.assertIn("landmark_id sequence invalid", str(ctx.exception))

    def test_empty_csv_rejected(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "ldm.csv"
            _write_csv(p, [])
            with self.assertRaises(ValidationError):
                _csv_check(p, expected=5)


if __name__ == "__main__":
    unittest.main()