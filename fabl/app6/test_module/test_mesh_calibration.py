"""🎯 GUARD → Калибровка mesh-метрик (ER-158, волна сигналов).

MeshNoiseModel.score: без калибровочного эталона — insufficient_calibration;
меш не измерен — not_measured; с эталоном — детерминированный z-скоринг с
агрегацией within_mesh_noise / mesh_elevated. Пустая калибровка честно
помечается unavailable (mesh остаётся direct_uncalibrated support).
"""
from __future__ import annotations

import unittest

from app6.stage2.mesh_calibration import MeshNoiseModel, MeshNoiseReference


def _ref(pose="frontal", p95=5.0):
    return MeshNoiseReference(
        schema="deeputin-stage2-mesh-calibration-v1.0",
        status="available",
        references={pose: {
            "mesh_rmse": {"median": 1.0, "mad": 0.5, "p95": p95, "count": 100},
            "mesh_median": {"median": 0.8, "mad": 0.4, "p95": p95, "count": 100},
        }},
        pair_count=10,
        unavailable_count=0,
        pose_counts={pose: 10},
    )


class MeshCalibrationScoreTests(unittest.TestCase):
    def test_unknown_pose_without_reference_is_insufficient_calibration(self):
        out = MeshNoiseModel([]).score("bogus_bin", {"mesh_status": "measured_uncalibrated"})
        # Нет refs для bogus_bin → insufficient_calibration, независимо от count.
        self.assertEqual(out["mesh_calibration_status"], "insufficient_calibration")

    def test_not_measured_mesh_returns_not_measured(self):
        out = MeshNoiseModel([]).score("frontal", {"mesh_status": "unavailable"})
        self.assertEqual(out["mesh_calibration_status"], "not_measured")

    def test_measured_within_noise_when_below_p95(self):
        model = MeshNoiseModel([])
        ref = _ref(p95=5.0)
        # score() использует self.reference — подменяем на подготовленный эталон.
        model.reference = ref
        out = model.score("frontal", {
            "mesh_status": "measured_uncalibrated",
            "mesh_rmse": 3.0,  # z=2.7 (<3.5) и 3<5 → within_mesh_noise
            "mesh_median": 1.2,
        })
        self.assertEqual(out["mesh_calibration_status"], "within_mesh_noise")
        self.assertGreaterEqual(out["mesh_calibrated_metric_count"], 1)
        self.assertEqual(out["mesh_calibrated_elevated_count"], 0)

    def test_elevated_value_marked_mesh_elevated(self):
        model = MeshNoiseModel([])
        model.reference = _ref(p95=5.0)
        out = model.score("frontal", {
            "mesh_status": "measured_uncalibrated",
            "mesh_rmse": 10.0,  # z=12.1 (>3.5) и 10>5 → mesh_elevated
            "mesh_median": 1.1,
        })
        self.assertEqual(out["mesh_calibration_status"], "mesh_elevated")
        self.assertEqual(out["mesh_calibrated_elevated_count"], 1)

    def test_insufficient_calibration_when_no_measured_metric(self):
        model = MeshNoiseModel([])
        model.reference = _ref(p95=5.0)
        out = model.score("frontal", {
            "mesh_status": "measured_uncalibrated",
            # mesh_rmse/mesh_median val отсутствуют → count==0.
        })
        self.assertEqual(out["mesh_calibration_status"], "insufficient_calibration")


class MeshNoiseModelEmptyTests(unittest.TestCase):
    def test_empty_calibration_is_unavailable_not_fabricated(self):
        model = MeshNoiseModel([])
        self.assertEqual(model.reference.status, "unavailable")
        self.assertEqual(model.reference.pair_count, 0)

    def test_to_json_marks_unavailable_policy(self):
        model = MeshNoiseModel([])
        payload = model.to_json()
        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("uncalibrated", payload["policy"])


if __name__ == "__main__":
    unittest.main()