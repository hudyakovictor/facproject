"""🎯 GUARD → Стратификация по качеству съёмки (ER-158 / ER-104).

quality_gate: слишком малое лицо → пара отвергается (abstention); иначе пара
наследует худшую страту (слабое звено определяет null-модель), с суффиксом ключа
калибровки и множителем порога по стратификации.
"""
from __future__ import annotations

import unittest

from app6.stage2.quality_stratification import (
    MIN_FACE_AREA_RATIO,
    quality_gate,
)


def _meta(conf=0.9, skin=0.8, area=0.2):
    return {"detection_confidence": conf, "skin_quality_score": skin, "face_area_ratio": area}


class QualityStratificationTests(unittest.TestCase):
    def test_face_too_small_rejected(self):
        out = quality_gate(_meta(area=MIN_FACE_AREA_RATIO * 0.5), _meta(area=0.3))
        self.assertFalse(out["accepted"])
        self.assertEqual(out["reason"], "face_too_small")

    def test_high_stratum(self):
        out = quality_gate(_meta(conf=0.9, skin=0.8), _meta(conf=0.9, skin=0.8))
        self.assertTrue(out["accepted"])
        self.assertEqual(out["stratum"], "high")
        self.assertEqual(out["threshold_multiplier"], 1.00)
        self.assertEqual(out["confidence"], "normal")
        self.assertEqual(out["calibration_key_suffix"], "::q_high")

    def test_pair_inherits_worst_stratum(self):
        out = quality_gate(_meta(conf=0.9, skin=0.8), _meta(conf=0.1, skin=0.9))
        self.assertEqual(out["stratum"], "low")
        self.assertEqual(out["threshold_multiplier"], 2.05)
        self.assertEqual(out["confidence"], "reduced")

    def test_mixed_stratum_maps_to_mixed(self):
        out = quality_gate(_meta(conf=0.9, skin=0.8), _meta(conf=0.6, skin=0.6))
        self.assertEqual(out["stratum"], "mixed")
        self.assertEqual(out["threshold_multiplier"], 1.45)

    def test_schema_declared(self):
        out = quality_gate(_meta(), _meta())
        self.assertEqual(out["schema"], "deeputin-quality-stratification-v1.0")


if __name__ == "__main__":
    unittest.main()