"""🔒 GUARD → Вторая серия краевых тестов (docs/final).

Покрывает области, не затронутые существующими тестами:
  1. CUSUM-детекция постепенного дрейфа (`apply_cumulative_drift_flags`).
  2. Evidence-слой: downgrade по quality/calibration/pose и reportable gate.
  3. Контр-объяснения `alternative_reasons` (видимость, поза, expression, alpha).
  4. Хронология: same-day structural conflict и отсутствие ложного флага.
  5. Landmark policy: границы subset, форма utility, all-NaN fallback.

Все тесты самодостаточны и не требуют весов 3DDFA или фотодатасета.
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.stage2.chronology import apply_chronology_rate_flags, apply_cumulative_drift_flags
from app6.stage2.evidence import alternative_reasons, evidence_state, is_reportable_change
from app6.stage2.landmark_policy import normalized_weights, sanitize_utility, stable_subset


class CumulativeDriftTests(unittest.TestCase):
    """Идея 1: CUSUM ловит постепенный дрейф, пропущенный попарно."""

    def _row(self, i, z=4.0, quality_limited=False):
        return {
            "pair_id": f"p{i}", "pair_type": "adjacent", "pose_bin": "frontal",
            "date_a": "2000-01-01", "date_b": f"2000-0{i + 1}-01",
            "p95_point_z": z, "coherent_motion_fraction": 0.5,
            "significant_point_fraction": 0.2, "pair_index": i,
            "quality_limited": quality_limited,
        }

    def test_subthreshold_changes_accumulate_into_drift(self):
        # z=4.0, floor=2.5 → +1.5 на шаг; порог CUSUM 6.0 достигается на 4-й строке.
        rows = [self._row(i) for i in range(4)]
        res = apply_cumulative_drift_flags(rows)
        self.assertEqual(res["event_count"], 1)
        self.assertEqual(rows[-1]["cumulative_drift_status"], "cumulative_drift_candidate")
        self.assertGreaterEqual(rows[-1]["cumulative_drift_cusum"], 6.0)

    def test_excluded_rows_never_contribute(self):
        rows = [self._row(0, quality_limited=True), self._row(1)]
        apply_cumulative_drift_flags(rows)
        self.assertEqual(rows[0]["cumulative_drift_status"], "excluded")
        self.assertTrue(np.isnan(rows[0]["cumulative_drift_cusum"]))


class EvidenceLayerTests(unittest.TestCase):
    """Идея 2: downgrade и reportable gate."""

    def test_quality_limited_downgrades_non_noise(self):
        self.assertEqual(evidence_state("coherent_jump_candidate", quality_limited=True),
                         "quality_limited")
        # Шум не понижается: это не аномалия.
        self.assertEqual(evidence_state("within_reconstruction_noise", quality_limited=True),
                         "within_noise")

    def test_calibration_and_pose_downgrade(self):
        self.assertEqual(evidence_state("coherent_jump_candidate", calibration_limited=True),
                         "calibration_limited")
        self.assertEqual(evidence_state("coherent_jump_candidate", pose_leakage_limited=True),
                         "pose_leakage_limited")

    def test_not_measurable_is_explicit(self):
        self.assertEqual(evidence_state("not_measurable"), "not_measurable")

    def test_reportable_gate(self):
        self.assertTrue(is_reportable_change(
            {"pair_type": "adjacent", "evidence_state": "coherent_jump_candidate"}))
        self.assertFalse(is_reportable_change(
            {"pair_type": "adjacent", "evidence_state": "within_noise"}))
        self.assertFalse(is_reportable_change(
            {"pair_type": "baseline", "evidence_state": "coherent_jump_candidate"}))


class AlternativeReasonsTests(unittest.TestCase):
    """Идея 3: контр-объяснения покрывают ограничения."""

    def test_reasons_cover_limitations(self):
        row = {
            "date_provenance_limited": True,
            "near_duplicate_pair": True,
            "quality_limited": True,
            "common_visible134": 40,
            "matched_calibration_sets": 2,
            "pose_distance": 3.0,
            "expression_influence": 0.5,
            "alpha_id_status": "elevated",
            "alpha_exp_status": "elevated",
            "source_provenance_status_a": "provided",
            "source_provenance_status_b": "not_provided",
        }
        reasons = alternative_reasons(row)
        for expected in (
            "filename_corroborating_date_conflict",
            "perceptual_duplicate_cluster_dependence",
            "low_or_missing_quality",
            "limited_landmark_visibility",
            "limited_matched_calibration",
            "large_pose_distance",
            "expression_or_soft_tissue_influence",
            "alpha_id_shape_channel_jump_candidate",
            "expression_coefficient_jump",
            "source_chain_incomplete",
        ):
            self.assertIn(expected, reasons)

    def test_clean_row_has_no_reasons(self):
        row = {"source_provenance_status_a": "provided", "source_provenance_status_b": "provided",
               "common_visible134": 120, "matched_calibration_sets": 5,
               "pose_distance": 1.0, "expression_influence": 0.1}
        self.assertEqual(alternative_reasons(row), [])


class ChronologySameDayTests(unittest.TestCase):
    """Идея 4: same-day structural conflict и отсутствие ложного флага."""

    def _row(self, pz, date_b="2020-01-01"):
        return {"pair_type": "adjacent", "pose_bin": "frontal",
                "date_a": "2020-01-01", "date_b": date_b,
                "p95_point_z": pz, "coherent_motion_fraction": 0.5,
                "significant_point_fraction": 0.2, "pair_index": 0,
                "status": "within_reconstruction_noise"}

    def test_same_day_structural_conflict_flagged(self):
        row = self._row(pz=5.0)
        apply_chronology_rate_flags([row])
        self.assertEqual(row["chronology_rate_status"], "same_day_structural_conflict")

    def test_low_same_day_is_not_flagged(self):
        row = self._row(pz=1.0)
        apply_chronology_rate_flags([row])
        self.assertEqual(row["chronology_rate_status"], "within_expected_rate")


class LandmarkPolicyEdgeTests(unittest.TestCase):
    """Идея 5: границы формы, форма utility, all-NaN fallback."""

    def test_sanitize_utility_rejects_wrong_shape(self):
        with self.assertRaises(ValueError):
            sanitize_utility(np.zeros((5, 10)))

    def test_stable_subset_rejects_out_of_range_count(self):
        x = np.zeros((9, 134))
        with self.assertRaises(ValueError):
            stable_subset(x, 0)
        with self.assertRaises(ValueError):
            stable_subset(x, 135)

    def test_all_nan_utility_falls_back_to_ones(self):
        all_nan = np.full((9, 134), np.nan)
        with np.errstate(all="ignore"):
            w = normalized_weights(all_nan, 0)
        self.assertEqual(w.shape, (134,))
        self.assertTrue((w == 1.0).all())

    def test_stable_subset_returns_exact_unique_count(self):
        x = np.tile(np.linspace(0.1, 2.0, 134), (9, 1))
        ids = stable_subset(x, 91)
        self.assertEqual(len(ids), 91)
        self.assertEqual(len(set(ids.tolist())), 91)


if __name__ == "__main__":
    unittest.main()