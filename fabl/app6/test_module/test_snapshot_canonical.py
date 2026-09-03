"""🎯 GUARD → Канонизация snapshot (ER-173 / ER-029).

canonical_snapshot делает вывод детерминированным: порядок ключей dict
нормализуется, float-точность фиксируется, -0.0→0.0, NaN/Inf→None. Два прогона
на одинаковых данных дают побайтово одинаковый канонический вывод.
"""
from __future__ import annotations

import unittest

from app6.stage2.snapshot_canonical import (
    snapshot_file_roundtrip_is_deterministic,
    compare_snapshots,
    canonical_json,
    canonical_snapshot,
    read_snapshot,
    snapshot_category,
    write_snapshot,
)


class CanonicalSnapshotTests(unittest.TestCase):
    def test_dict_keys_sorted_regardless_of_order(self):
        a = canonical_snapshot({"b": 1, "a": 2, "c": 3})
        b = canonical_snapshot({"c": 3, "a": 2, "b": 1})
        self.assertEqual(a, b)
        self.assertEqual(list(a.keys()), ["a", "b", "c"])

    def test_float_rounded_to_fixed_precision(self):
        value = canonical_snapshot(0.1 + 0.2)
        self.assertEqual(value, 0.3)

    def test_negative_zero_normalized_to_zero(self):
        self.assertEqual(canonical_snapshot(-0.0), 0.0)

    def test_nan_and_inf_become_none(self):
        self.assertIsNone(canonical_snapshot(float("nan")))
        self.assertIsNone(canonical_snapshot(float("inf")))

    def test_nested_structures_normalized(self):
        value = {
            "metrics": {"zz": [1.0, 0.1 + 0.2], "aa": {"x": float("nan")}},
            "top": -0.0,
        }
        canon = canonical_snapshot(value)
        self.assertEqual(canon["metrics"]["aa"]["x"], None)
        self.assertEqual(canon["metrics"]["zz"], [1.0, 0.3])
        self.assertEqual(canon["top"], 0.0)
        self.assertEqual(list(canon["metrics"].keys()), ["aa", "zz"])

    def test_scalars_passed_through(self):
        self.assertEqual(canonical_snapshot(42), 42)
        self.assertEqual(canonical_snapshot("s"), "s")
        self.assertEqual(canonical_snapshot(True), True)
        self.assertEqual(canonical_snapshot(None), None)

    def test_roundtrip_is_idempotent(self):
        value = {"a": [1.0, -0.0, float("nan")], "b": {"c": 0.1 + 0.2}}
        once = canonical_snapshot(value)
        twice = canonical_snapshot(once)
        self.assertEqual(once, twice)


class CanonicalJsonTests(unittest.TestCase):
    def test_metadata_contract(self):
        out = canonical_json({"b": 1.0, "a": float("inf")})
        self.assertEqual(out["schema"], "deeputin-snapshot-canonical-v1.0")
        self.assertEqual(out["canonical_version"], "v1")
        self.assertEqual(out["payload"]["a"], None)
        self.assertEqual(list(out["payload"].keys()), ["a", "b"])

    def test_float_precision_custom(self):
        out = canonical_json({"x": 0.123456789}, float_precision=3)
        self.assertEqual(out["payload"]["x"], 0.123)


class SnapshotCategoryTests(unittest.TestCase):
    def test_category_by_substring(self):
        self.assertFalse(snapshot_category("mesh_p95")["exact"])
        self.assertLess(snapshot_category("mesh_p95")["tolerance"], 1e-2)

    def test_exact_default_for_unknown(self):
        self.assertTrue(snapshot_category("pair_id")["exact"])
        self.assertEqual(snapshot_category("pair_id")["tolerance"], 0.0)

    def test_hash_schema_date_exact(self):
        for name in ("config_hash", "schema_version", "date_a"):
            self.assertTrue(snapshot_category(name)["exact"])


class CompareSnapshotsTests(unittest.TestCase):
    def test_identical_matches(self):
        snap = {"a": {"mesh_p95": 1.23456}, "schema": "v1"}
        result = compare_snapshots(snap, {"schema": "v1", "a": {"mesh_p95": 1.23456}})
        self.assertTrue(result["match"])
        self.assertEqual(result["field_count"], 2)

    def test_numeric_drift_within_tolerance_matches(self):
        expected = {"mesh_p95": 1.23456}
        actual = {"mesh_p95": 1.2345671}  # drift < 1e-3
        result = compare_snapshots(expected, actual)
        self.assertTrue(result["match"])

    def test_numeric_drift_beyond_tolerance_reported(self):
        expected = {"mesh_p95": 1.0}
        actual = {"mesh_p95": 5.0}
        result = compare_snapshots(expected, actual)
        self.assertFalse(result["match"])
        self.assertEqual(result["mismatches"][0]["status"], "numeric_drift")

    def test_exact_field_mismatch_reported(self):
        expected = {"schema": "v1"}
        actual = {"schema": "v2"}
        result = compare_snapshots(expected, actual)
        self.assertFalse(result["match"])
        self.assertEqual(result["mismatches"][0]["status"], "mismatch")

    def test_missing_field_reported(self):
        result = compare_snapshots({"a": 1, "b": 2}, {"a": 1})
        self.assertFalse(result["match"])
        self.assertTrue(any(m["status"] == "missing" for m in result["mismatches"]))

    def test_unexpected_field_reported(self):
        result = compare_snapshots({"a": 1}, {"a": 1, "extra": 2})
        self.assertFalse(result["match"])
        self.assertTrue(any(m["status"] == "unexpected" for m in result["mismatches"]))

    def test_list_length_mismatch(self):
        result = compare_snapshots({"vals": [1, 2, 3]}, {"vals": [1, 2]})
        self.assertFalse(result["match"])
        self.assertTrue(any(m["status"] == "length" for m in result["mismatches"]))

    def test_custom_categories_can_relax(self):
        custom = (("probe", {"tolerance": 10.0, "exact": False}),)
        result = compare_snapshots({"probe_val": 1.0}, {"probe_val": 5.0}, categories=custom)
        self.assertTrue(result["match"])


class SnapshotFileTests(unittest.TestCase):
    def _tmp(self):
        import tempfile
        from pathlib import Path
        return Path(tempfile.mkdtemp())

    def test_write_read_roundtrip(self):
        root = self._tmp()
        snap_file = root / "snapshot.json"
        value = {"photo_a": "1999_08_12_1", "metrics": {"zz": 0.1 + 0.2, "aa": float("inf")}}
        written = write_snapshot(snap_file, value)
        self.assertTrue(snap_file.exists())
        read = read_snapshot(written)
        self.assertEqual(read["payload"]["metrics"]["aa"], None)  # non-finite -> null
        self.assertEqual(list(read["payload"]["metrics"].keys()), ["aa", "zz"])  # sorted

    def test_roundtrip_is_bytewise_deterministic(self):
        root = self._tmp()
        snap_file = root / "snapshot.json"
        value = {"b": [1.0, -0.0], "a": {"c": 0.30000000000000004}}
        self.assertTrue(snapshot_file_roundtrip_is_deterministic(snap_file, value))

    def test_snapshot_sorts_keys_and_normalizes_float(self):
        root = self._tmp()
        snap_file = root / "snapshot.json"
        write_snapshot(snap_file, {"b": 1, "a": 0.1 + 0.2})
        text = snap_file.read_text(encoding="utf-8")
        self.assertIn('"payload"', text)
        self.assertIn('"a"', text)
        read = read_snapshot(snap_file)
        self.assertEqual(read["payload"]["a"], 0.3)

    def test_double_run_canonical_hash_is_deterministic(self):
        # R-G04: два независимых прогона одной логики → одинаковый canonical хэш.
        import hashlib
        import json
        from app6.stage2.snapshot_canonical import canonical_json

        def _run() -> str:
            data = {
                "metrics": {"zz": [0.1 + 0.2, -0.0], "aa": float("nan")},
                "pairs": [{"pose": "frontal", "v": 1.25}],
            }
            c = canonical_json(data)
            return hashlib.sha256(json.dumps(c, sort_keys=True).encode("utf-8")).hexdigest()

        self.assertEqual(_run(), _run())


if __name__ == "__main__":
    unittest.main()