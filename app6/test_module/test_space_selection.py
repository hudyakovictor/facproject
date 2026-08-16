"""🎯 GUARD → Дисциплина координатного пространства (ER-158 / D-003, ER-009).

space_selection кодирует инвариант AGENTS.md D-003: analysis работает только в
raw_object_normalized; chronology/chronology_aligned запрещены (содержат коррекцию
позы — уничтожает измеряемый сигнал, ER-009/ER-122).
"""
from __future__ import annotations

import unittest

from app6.stage2.analysis_policy import ANALYSIS_COORDINATE_SPACE
from app6.stage2.space_selection import (
    ALLOWED_SPACES,
    FORBIDDEN_SPACES,
    assert_analysis_space,
    space_manifest,
)


class SpaceSelectionTests(unittest.TestCase):
    def test_canonical_space_is_allowed(self):
        assert_analysis_space(ANALYSIS_COORDINATE_SPACE)  # не должно бросить

    def test_canonical_space_is_raw_object_normalized(self):
        self.assertEqual(ANALYSIS_COORDINATE_SPACE, "raw_object_normalized")

    def test_chronology_space_is_forbidden(self):
        for space in ("chronology", "chronology_aligned"):
            with self.assertRaises(ValueError):
                assert_analysis_space(space)

    def test_unknown_space_is_rejected(self):
        for space in ("aligned", "original_image_px", "bogus"):
            with self.assertRaises(ValueError):
                assert_analysis_space(space)

    def test_forbidden_and_allowed_are_disjoint(self):
        self.assertTrue(ALLOWED_SPACES.isdisjoint(FORBIDDEN_SPACES))

    def test_allowed_is_exactly_canonical(self):
        self.assertEqual(ALLOWED_SPACES, frozenset({"raw_object_normalized"}))

    def test_manifest_declares_decision_d003(self):
        manifest = space_manifest()
        self.assertEqual(manifest["active_space"], ANALYSIS_COORDINATE_SPACE)
        self.assertEqual(manifest["decision"], "D-003")
        self.assertTrue(manifest["revalidated"])
        # Заявленные AUC отражают задокументированный попадание raw в CI aligned.
        self.assertIn("raw", manifest["measured_auc"])


if __name__ == "__main__":
    unittest.main()