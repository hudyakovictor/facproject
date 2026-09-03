"""🎯 GUARD → Хеш-интеграция Stage 1 и нормативная политика ракурсов (ER-003/ER-011, D-001).

utils.digest_file/digest_json/digest_paths: 64-hex детерминированные хеши
(ER-003 — контракт make_photo_id). pose_policy.assert_canonical_yaw:
fail-closed сверка canonical_yaw с нормативным центром бина (D-001),
legacy-центры отклоняются с требованием миграции.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from app6.stage1.utils import digest_file, digest_json, digest_paths, json_ready
from app6.stage2.pose_policy import BIN_NAME_TO_YAW, assert_canonical_yaw, profile_sub_bin, yaw_for_bin


class DigestFileTests(unittest.TestCase):
    def test_returns_64_lowercase_hex(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "f.bin"
            p.write_bytes(b"content")
            digest = digest_file(p)
            self.assertEqual(len(digest), 64)
            self.assertTrue(all(c in "0123456789abcdef" for c in digest))

    def test_deterministic(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "f.bin"
            p.write_bytes(b"content")
            self.assertEqual(digest_file(p), digest_file(p))

    def test_different_content_different_digest(self):
        with TemporaryDirectory() as td:
            a, b = Path(td) / "a", Path(td) / "b"
            a.write_bytes(b"x")
            b.write_bytes(b"y")
            self.assertNotEqual(digest_file(a), digest_file(b))


class DigestJsonTests(unittest.TestCase):
    def test_deterministic_regardless_of_key_order(self):
        self.assertEqual(digest_json({"a": 1, "b": 2}), digest_json({"b": 2, "a": 1}))


class DigestPathsTests(unittest.TestCase):
    def test_order_independent(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            a, b = root / "a.txt", root / "b.txt"
            a.write_text("a", encoding="utf-8")
            b.write_text("b", encoding="utf-8")
            self.assertEqual(digest_paths([a, b], root), digest_paths([b, a], root))

    def test_rejects_no_existing_files(self):
        with self.assertRaises(ValueError):
            digest_paths([Path("/nonexistent_1"), Path("/nonexistent_2")])


class JsonReadyTests(unittest.TestCase):
    def test_numpy_arrays_become_lists(self):
        self.assertEqual(json_ready(np.array([1.0, 2.0])), [1.0, 2.0])

    def test_nan_to_none(self):
        self.assertIsNone(json_ready(float("nan")))

    def test_dict_keys_stringified(self):
        self.assertEqual(json_ready({1: "v"}), {"1": "v"})


class PosePolicyTests(unittest.TestCase):
    def test_canonical_yaw_accepted(self):
        assert_canonical_yaw("frontal", 0.0)  # не должно бросить

    def test_wrong_canonical_yaw_rejected(self):
        with self.assertRaises(ValueError):
            assert_canonical_yaw("frontal", 99.0)

    def test_unknown_pose_bin_rejected(self):
        with self.assertRaises(ValueError):
            assert_canonical_yaw("bogus_bin", 0.0)

    def test_yaw_for_bin_returns_center(self):
        self.assertEqual(yaw_for_bin("frontal"), 0.0)
        self.assertEqual(yaw_for_bin("left_light"), BIN_NAME_TO_YAW["left_light"])

    def test_profile_sub_bin_maps_yaw(self):
        self.assertEqual(profile_sub_bin(70.0), "right_profile_70_80")

    def test_profile_sub_bin_out_of_range(self):
        self.assertIsNone(profile_sub_bin(10.0))
        self.assertIsNone(profile_sub_bin(float("nan")))


if __name__ == "__main__":
    unittest.main()