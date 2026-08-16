"""🔬 GUARD → retest-ветка приватного слоя гипотез (ER-190, ER-193).

_retest_record решает статус retest по текущим парам: при отсутствии matching
текущих данных — fail-closed «pending_missing_current_data» (legacy target
сохраняется, а не подтверждается/отвергается); при matched парах переводит
состояние evidence в technical_anomaly_candidate / inconclusive /
within_current_noise_or_no_strong_change.
"""
from __future__ import annotations

import unittest

from app6.stage2.private_hypothesis import _candidate_keys, _retest_record


class CandidateKeysTests(unittest.TestCase):
    def test_extracts_photos_dates_metrics(self):
        photos, dates, metrics = _candidate_keys({
            "photo_id": "1999_08_12_1",
            "date_str": "1999-08-12",
            "carrier": "span_lateral",
            "feature": "bbox_volume",
        })
        self.assertIn("1999_08_12_1", photos)
        self.assertIn("1999-08-12", dates)
        self.assertIn("span_lateral", metrics)
        self.assertIn("bbox_volume", metrics)

    def test_walks_nested_structures(self):
        photos, dates, _ = _candidate_keys({"a": {"b": [{"photo_id_a": "x"}, {"date_b": "1999-08-12"}]}})
        self.assertIn("x", photos)
        self.assertIn("1999-08-12", dates)

    def test_empty_payload_gives_empty_keys(self):
        photos, dates, metrics = _candidate_keys({})
        self.assertEqual((photos, dates, metrics), (set(), set(), set()))


class RetestRecordTests(unittest.TestCase):
    def _pair(self, photo_a, photo_b, date_a, state="within_reconstruction_noise"):
        return {"photo_a": photo_a, "photo_b": photo_b, "date_a": date_a,
                "date_b": "1999-09-01", "evidence_state": state}

    def test_no_match_is_pending_missing_current_data(self):
        result = _retest_record({"photo_id": "1990_01_01_1"}, [], set())
        self.assertEqual(result["status"], "pending_missing_current_data")
        self.assertEqual(result["result"], "not_tested_no_current_matching_data")
        self.assertEqual(result["matched_pair_count"], 0)

    def test_strong_evidence_state_is_technical_anomaly_candidate(self):
        result = _retest_record(
            {"photo_id": "A"},
            [self._pair("A", "B", "1999-08-12", state="coherent_jump_candidate")],
            {"candidate"},
        )
        self.assertEqual(result["status"], "retested_with_current_alignment")
        self.assertEqual(result["result"], "technical_anomaly_candidate")
        self.assertEqual(result["matched_pair_count"], 1)

    def test_limited_evidence_state_is_inconclusive(self):
        result = _retest_record(
            {"photo_id": "A"},
            [self._pair("A", "B", "1999-08-12", state="quality_limited")],
            set(),
        )
        self.assertEqual(result["result"], "inconclusive")
        self.assertEqual(result["status"], "retested_with_current_alignment")

    def test_neutral_state_is_within_current_noise(self):
        result = _retest_record(
            {"photo_id": "A"},
            [self._pair("A", "B", "1999-08-12", state="within_reconstruction_noise")],
            set(),
        )
        self.assertEqual(result["result"], "within_current_noise_or_no_strong_change")

    def test_metric_hits_computed(self):
        result = _retest_record(
            {"photo_id": "A", "carrier": "span_lateral", "feature": "unknown_metric"},
            [self._pair("A", "B", "1999-08-12")],
            {"span_lateral"},
        )
        # unknown_metric не в текущем реестре — не считается хитом.
        self.assertEqual(result["current_metric_name_hits"], ["span_lateral"])

    def test_current_states_aggregated(self):
        result = _retest_record(
            {"photo_id": "A"},
            [self._pair("A", "B", "1999-08-12", state="scattered_or_uncertain"),
             self._pair("A", "C", "1999-08-12", state="coherent_jump_candidate")],
            set(),
        )
        self.assertEqual(sorted(result["current_states"]),
                         ["coherent_jump_candidate", "scattered_or_uncertain"])


if __name__ == "__main__":
    unittest.main()