"""🎯 GUARD → Golden synthetic fixture: сценарии R-G05 (ER-168 / R-G05).

Проверяет, что golden-synthetic snapshot покрывает сценарии date_conflict,
clean, null, step, return_a_b_a и все 9 pose bins (D-001), а запись побайтово
детерминирована (R-G04/ER-029).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app6.stage2.golden_fixture import (
    CANONICAL_POSE_BINS,
    GOLDEN_FIXTURE_SCHEMA,
    build_golden_snapshot_data,
    write_golden_snapshot,
)


class GoldenFixtureTests(unittest.TestCase):
    def test_covers_all_rg05_scenarios(self):
        data = build_golden_snapshot_data()
        self.assertEqual(data["schema"], GOLDEN_FIXTURE_SCHEMA)
        self.assertTrue(data["has_date_conflict_pair"])
        self.assertTrue(data["has_null_pair"])
        self.assertTrue(data["has_step_pair"])
        self.assertTrue(data["has_return_pair"])

    def test_null_metrics_are_none_not_zero(self):
        data = build_golden_snapshot_data()
        null_pair = [p for p in data["pairs"] if p["scenario"] == "null"]
        self.assertEqual(len(null_pair), 1)
        self.assertIsNone(null_pair[0]["mesh_p95"])
        self.assertIsNone(null_pair[0]["primary_robust_z"])
        self.assertFalse(null_pair[0]["looked_up"])

    def test_covers_all_9_pose_bins(self):
        data = build_golden_snapshot_data()
        self.assertEqual(set(data["pose_bins"]), set(CANONICAL_POSE_BINS))
        self.assertEqual(data["pose_bin_count"], 9)

    def test_return_scenario_marked(self):
        data = build_golden_snapshot_data()
        ret = [p for p in data["pairs"] if p["scenario"] == "return_a_b_a"]
        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0]["return_ab_a"])

    def test_also_contains_clean_pair(self):
        data = build_golden_snapshot_data()
        clean = [p for p in data["pairs"] if p["scenario"] == "clean"]
        self.assertGreaterEqual(len(clean), 1)

    def test_data_is_deterministic(self):
        self.assertEqual(build_golden_snapshot_data(), build_golden_snapshot_data())

    def test_snapshot_file_roundtrip_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            snap = Path(td) / "golden.json"
            write_golden_snapshot(snap)
            first = snap.read_text(encoding="utf-8")
            write_golden_snapshot(snap)
            second = snap.read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_written_snapshot_is_valid_canonical_json(self):
        with tempfile.TemporaryDirectory() as td:
            snap = Path(td) / "golden.json"
            write_golden_snapshot(snap)
            parsed = json.loads(snap.read_text(encoding="utf-8"))
            self.assertEqual(parsed["schema"], "deeputin-snapshot-canonical-v1.0")
            payload = parsed["payload"]
            self.assertEqual(payload["schema"], GOLDEN_FIXTURE_SCHEMA)
            self.assertEqual(payload["pose_bin_count"], 9)


if __name__ == "__main__":
    unittest.main()