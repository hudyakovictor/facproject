from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from dpo.photos import PhotoIndex, infer_pose_hint, parse_filename_date


class PhotoIndexTests(unittest.TestCase):
    def test_date_contract_matches_strict_underscore_format(self) -> None:
        self.assertEqual(parse_filename_date(Path("2024_03_07_2.jpg")), ("2024-03-07", 2024, 2))
        self.assertEqual(parse_filename_date(Path("20240307.jpg")), (None, None, 1))
        self.assertEqual(parse_filename_date(Path("2024_99_99.jpg")), (None, None, 1))

    def test_pose_hint_prefers_folder_and_is_explicitly_a_hint(self) -> None:
        self.assertEqual(infer_pose_hint(Path("left_mid/2024_01_01.jpg")), ("left_mid", "folder_hint"))
        self.assertEqual(infer_pose_hint(Path("misc/2024_01_01_right_deep.jpg")), ("right_deep", "filename_hint"))
        self.assertEqual(infer_pose_hint(Path("misc/2024_01_01.jpg")), ("unknown", "none"))

    def test_scan_is_read_only_sorted_and_reports_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frontal").mkdir()
            first = root / "frontal" / "2020_01_02.jpg"
            second = root / "unknown.jpg"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            rows = PhotoIndex(root).scan()
            after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(rows[0].date, "2020-01-02")
            self.assertEqual(rows[0].pose_bin_hint, "frontal")
            self.assertIn("date_unparseable", rows[1].issues)
            self.assertIn("pose_requires_stage1", rows[1].issues)

    def test_query_filters_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder, name in (("frontal", "2001_01_01.jpg"), ("frontal", "2002_01_01.jpg"), ("left_light", "2003_01_01.jpg")):
                (root / folder).mkdir(exist_ok=True)
                (root / folder / name).write_bytes(b"x")
            result = PhotoIndex(root).query(pose="frontal", year_from=2002)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["summary"]["all_photos"], 3)
            self.assertTrue(result["summary"]["pose_values_are_hints"])

    def test_symlinks_are_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            target = Path(outside) / "2020_01_01.jpg"
            target.write_bytes(b"secret")
            try:
                (root / "link.jpg").symlink_to(target)
            except OSError:
                self.skipTest("symlinks unavailable")
            self.assertEqual(PhotoIndex(root).scan(), [])

    def test_query_rejects_unbounded_or_unknown_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = PhotoIndex(Path(tmp))
            with self.assertRaises(ValueError): index.query(limit=50000)
            with self.assertRaises(ValueError): index.query(pose="invented")
