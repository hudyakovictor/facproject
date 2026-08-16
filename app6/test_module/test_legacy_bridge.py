"""🎯 GUARD → legacy-мост приватного слоя (ER-190, ER-195 / D12, AA-инварианты).

legacy_bridge сопоставляет ракурсы legacy→current и строит цель ретеста. Критичные
инварианты (AGENTS.md #15 / ER-192): legacy-числа — только провенанс, никогда не
текущая калибровка; ретест по умолчанию «pending_current_data» (fail-closed);
выравнивание остаётся iteratively_trimmed_kabsch_v1_no_scale.
"""
from __future__ import annotations

import unittest

from app6.stage2.legacy_bridge import (
    CURRENT_ALIGNMENT,
    LEGACY_ALIGNMENT,
    LEGACY_TO_CURRENT_BIN,
    NON_TRANSFERABLE_FIELDS,
    bridge_coverage,
    build_retest_target,
    normalize_photo_id,
    normalize_pose_bin,
)


class NormalizePoseBinTests(unittest.TestCase):
    def test_legacy_threequarter_names_map_to_current(self):
        self.assertEqual(normalize_pose_bin("left_threequarter_light"), "left_light")
        self.assertEqual(normalize_pose_bin("right_threequarter_deep"), "right_deep")
        self.assertEqual(normalize_pose_bin("left_threequarter_mid"), "left_mid")

    def test_identical_names_pass_through(self):
        self.assertEqual(normalize_pose_bin("frontal"), "frontal")
        self.assertEqual(normalize_pose_bin("left_profile"), "left_profile")

    def test_current_name_accepted(self):
        self.assertEqual(normalize_pose_bin("left_light"), "left_light")

    def test_unknown_name_returns_none(self):
        self.assertIsNone(normalize_pose_bin("bogus_angle"))
        self.assertIsNone(normalize_pose_bin(""))

    def test_strips_whitespace(self):
        self.assertEqual(normalize_pose_bin("  frontal "), "frontal")


class NormalizePhotoIdTests(unittest.TestCase):
    def test_clean_date_passthrough(self):
        self.assertEqual(normalize_photo_id("1999_08_12"), "1999_08_12")

    def test_empty_returns_empty(self):
        self.assertEqual(normalize_photo_id(""), "")

    def test_unparseable_returns_unchanged(self):
        self.assertEqual(normalize_photo_id("no-date-here"), "no-date-here")


class BuildRetestTargetTests(unittest.TestCase):
    def _legacy(self):
        return {
            "source": "legacy-seed",
            "payload": {
                "bucket": "left_threequarter_light",
                "photo_id": "1999_08_12 (2)",
                "date_str": "1999-08-12",
                "year": 1999,
                "full_posterior": 0.99,
                "confidence": "high",
                "identity_stress_score": 40.0,
            },
        }

    def test_retest_status_pending_current_data(self):
        target = build_retest_target(self._legacy())
        self.assertEqual(target["retest_status"], "pending_current_data")

    def test_bin_and_photo_normalized(self):
        target = build_retest_target(self._legacy())
        self.assertEqual(target["pose_bin"], "left_light")
        self.assertIsNotNone(target["photo_id"])

    def test_historical_values_are_provenance_not_calibration(self):
        target = build_retest_target(self._legacy())
        hist = target["historical_values"]
        for field in ("full_posterior", "confidence", "identity_stress_score"):
            self.assertIn(field, hist)
        # Non-transferable legacy-числа не должны всплывать на верхний уровень как
        # текущая калибровка/метрика — они изолированы в historical_values.
        for field in NON_TRANSFERABLE_FIELDS:
            self.assertNotIn(field, target)

    def test_transferable_fields_not_dropped_from_historical(self):
        target = build_retest_target(self._legacy())
        hist = target["historical_values"]
        # Поля, реально присутствующие в legacy-источнике, изолируются в historical_values.
        present = set(NON_TRANSFERABLE_FIELDS) & set(self._legacy()["payload"])
        self.assertEqual(set(hist), present)
        # Ключи с альтернативными posteriors ни при каких условиях не становятся
        # текущей калибровкой даже при наличии в источнике.
        filled_payload = {**self._legacy()["payload"]}
        for field in NON_TRANSFERABLE_FIELDS:
            filled_payload.setdefault(field, 0.0)
        filled = build_retest_target({"payload": filled_payload})
        self.assertEqual(set(filled["historical_values"]) & set(NON_TRANSFERABLE_FIELDS),
                         set(NON_TRANSFERABLE_FIELDS))
        for field in NON_TRANSFERABLE_FIELDS:
            self.assertNotIn(field, filled)

    def test_alignment_declares_current_kabsch(self):
        target = build_retest_target(self._legacy())
        self.assertEqual(target["current_alignment"], CURRENT_ALIGNMENT)
        self.assertEqual(target["historical_alignment"], LEGACY_ALIGNMENT)
        self.assertNotEqual(CURRENT_ALIGNMENT, LEGACY_ALIGNMENT)

    def test_missing_payload_uses_top_level_and_is_empty_safe(self):
        target = build_retest_target({"source": "x"})
        self.assertEqual(target["pose_bin"], None)
        self.assertEqual(target["historical_values"], {})


class BridgeCoverageTests(unittest.TestCase):
    def test_mapping_covers_known_bins(self):
        covered = bridge_coverage(["left_threequarter_light", "frontal", "right_profile"])
        self.assertEqual(covered["mapped_count"], 3)
        self.assertEqual(covered["unmapped_count"], 0)
        self.assertEqual(covered["coverage_fraction"], 1.0)

    def test_unknown_bins_are_reported(self):
        covered = bridge_coverage(["bad_bin", "left_threequarter_light"])
        self.assertEqual(covered["unmapped_examples"], ["bad_bin"])
        self.assertEqual(round(covered["coverage_fraction"], 4), round(1 / 2, 4))

    def test_all_nine_legacy_bins_map(self):
        legacy_bins = list(LEGACY_TO_CURRENT_BIN)
        covered = bridge_coverage(legacy_bins)
        self.assertEqual(covered["mapped_count"], 9)
        self.assertEqual(set(covered["bin_mapping"]), set(LEGACY_TO_CURRENT_BIN))

    def test_empty_coverage_is_zero(self):
        covered = bridge_coverage([])
        self.assertEqual(covered["coverage_fraction"], 0.0)


if __name__ == "__main__":
    unittest.main()