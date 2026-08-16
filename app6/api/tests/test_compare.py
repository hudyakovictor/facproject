"""🚪 CONTRACT → Сравнение пар через API-обёртку `/api/v1/compare` (ER-183).

compare_records: разные pose bins → status pose_mismatch (никакие метрики не
фабрикуются); результат всегда not_a_verdict. full_mesh_compare: без BFM
(недоступно или не-finite alpha_id) возвращает None — деградация к landmark,
а не выдуманный полный меш.
"""
from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from app6.api.compare import compare_records, full_mesh_compare
from app6.stage2.core import Record


def _record(record_id: str, pose_bin: str):
    n106, n134 = 106, 134
    return Record(
        record_id=record_id,
        dataset_id="test",
        date="2020-01-01",
        sequence=1,
        pose_bin=pose_bin,
        angles=np.array([0.0, 0.0, 0.0], np.float32),
        ldm106=np.random.default_rng(0).normal(0, 1, (n106, 3)).astype(np.float32),
        ldm134=np.random.default_rng(0).normal(0, 1, (n134, 3)).astype(np.float32),
        visible106=np.ones(n106, bool),
        visible134=np.ones(n134, bool),
        alpha_id=np.array([0.1] * 80, np.float32),
        alpha_exp=np.zeros(64, np.float32),
        analysis_space="raw_object_normalized",
    )


class CompareRecordsTest(unittest.TestCase):
    def test_pose_mismatch_returns_status_without_fabricated_metrics(self):
        a = _record("a", "frontal")
        b = _record("b", "left_light")
        result = compare_records(a, b)
        self.assertEqual(result["status"], "pose_mismatch")
        self.assertEqual(result["schema"], "deeputin-api-compare-v1.0")
        self.assertTrue(result["not_a_verdict"])
        self.assertEqual(result["heatmap_points"], [])

    def test_result_always_not_a_verdict(self):
        a = _record("a", "frontal")
        b = _record("b", "frontal")
        # Даже при совпадающих бинах результат обязан нести not_a_verdict=True.
        result = compare_records(a, b)
        self.assertTrue(result["not_a_verdict"])


class FullMeshCompareTest(unittest.TestCase):
    def test_returns_none_when_bfm_unavailable(self):
        a = _record("a", "frontal")
        b = _record("b", "frontal")
        with mock.patch("app6.api.compare.is_bfm_available", return_value=False):
            self.assertIsNone(full_mesh_compare(a, b))

    def test_returns_none_when_alpha_not_finite(self):
        a = _record("a", "frontal")
        b = _record("b", "frontal")
        b.alpha_id[0] = float("nan")
        with mock.patch("app6.api.compare.is_bfm_available", return_value=True):
            self.assertIsNone(full_mesh_compare(a, b))


if __name__ == "__main__":
    unittest.main()