"""🎯 GUARD → Локальные пары-дескрипторы (ER-158, волна сигналов).

Fail-closed пути: без калибровочного эталона score() возвращает
insufficient_calibration (не фабрикует z-метрики); без достаточной видимости
local_pair_descriptors возвращает insufficient_visibility. Оба случая являются
инвариантом AGENTS.md: отсутствие данных не заменяется измерением.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from app6.stage2.descriptors import NAMES, DescriptorNoiseModel, local_pair_descriptors


def _rec(n_visible: int) -> SimpleNamespace:
    vis = np.zeros(134, bool)
    vis[:n_visible] = True
    return SimpleNamespace(visible134=vis, ldm134=np.zeros((134, 3), np.float32))


class DescriptorsFailClosedTests(unittest.TestCase):
    def test_score_without_calibration_is_insufficient_calibration(self):
        model = DescriptorNoiseModel([])  # пустой эталон калибровки
        out = model.score("frontal", _rec(100), _rec(100))
        self.assertEqual(out["status"], "insufficient_calibration")
        self.assertEqual(out["significant"].shape, (134, len(NAMES)))
        self.assertEqual(out["summary"], {})

    def test_insufficient_visibility_is_not_measured(self):
        a, b = _rec(10), _rec(10)  # 10 из 134 видимых < порога 30
        out = local_pair_descriptors(a, b, np.zeros((134, 3), np.float32))
        self.assertEqual(out["status"], "insufficient_visibility")
        self.assertTrue(np.isnan(out["values"]).all())

    def test_missing_data_never_looks_like_measurement(self):
        # Недостаточная видимость не должна дать z-скоринг в score() с эталоном.
        model = DescriptorNoiseModel([])
        score = model.score("frontal", _rec(5), _rec(5))
        self.assertEqual(score["status"], "insufficient_calibration")


if __name__ == "__main__":
    unittest.main()