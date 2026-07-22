"""🔄 CALLBACK (pytest) → stage1.naming: parse_photo_name, даты из имён, photo_id.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from app6.stage1.naming import make_photo_id, parse_photo_name


class NamingTests(unittest.TestCase):
    def test_plain_date_has_sequence_one(self):
        p = parse_photo_name(Path("1999_01_11.jpg"))
        self.assertEqual(p.date_iso, "1999-01-11")
        self.assertEqual(p.sequence, 1)

    def test_explicit_sequence(self):
        self.assertEqual(parse_photo_name(Path("1999_01_11_12.png")).sequence, 12)

    def test_copy_suffix_in_parentheses(self):
        p = parse_photo_name(Path("1999_01_11 (2).jpg"))
        self.assertEqual(p.sequence, 2)
        self.assertEqual(p.canonical_stem, "1999_01_11_2")

    def test_copy_suffix_with_underscore(self):
        p = parse_photo_name(Path("1999_01_11_2.jpg"))
        self.assertEqual(p.sequence, 2)

    def test_invalid_names_rejected(self):
        for name in ("1999-1-1.jpg", "copy.jpg", "2023_02_29.jpg"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_photo_name(Path(name))

    def test_different_sha256_gives_different_photo_id(self):
        p = parse_photo_name(Path("1999_01_11.jpg"))
        id_a = make_photo_id(p, "a" * 64)
        id_b = make_photo_id(p, "b" * 64)
        # Different source sha256 must produce different photo_ids
        self.assertNotEqual(id_a, id_b)
        # Both must start with the canonical stem
        self.assertTrue(id_a.startswith("1999_01_11__"))
        self.assertTrue(id_b.startswith("1999_01_11__"))

    def test_no_sha256_falls_back_to_stem(self):
        p = parse_photo_name(Path("1999_01_11.jpg"))
        # Without sha256, falls back to canonical_stem only
        self.assertEqual(make_photo_id(p, ""), "1999_01_11")
        self.assertEqual(make_photo_id(p, None), "1999_01_11")

    def test_same_photo_id_for_different_copy_suffix_same_hash(self):
        p1 = parse_photo_name(Path("1999_01_11 (2).jpg"))
        p2 = parse_photo_name(Path("1999_01_11_2.jpg"))
        self.assertEqual(make_photo_id(p1, "a" * 64), make_photo_id(p2, "a" * 64))


if __name__ == "__main__": unittest.main()
