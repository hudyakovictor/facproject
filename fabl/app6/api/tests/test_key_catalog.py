"""🎯 GUARD → Каталог ключей API (категоризация колонок / info.json / manifest).

coerce: CSV-строка → JSON-тип БЕЗ потери «нет данных» (nan/"" → None; ноль не
подставляется за пропуск). category_for: неизвестные колонки не теряются молча,
а уходят в (I, other).
"""
from __future__ import annotations

import unittest

from app6.api.key_catalog import (
    categorize_manifest,
    categorize_pair_columns,
    categorize_stage1_info,
    category_for,
    coerce,
)


class CoerceTests(unittest.TestCase):
    def test_missing_strings_become_none(self):
        for raw in ("", "nan", "None", "null", "NA", "  "):
            self.assertIsNone(coerce(raw), f"{raw!r} should be None")

    def test_boolean_parsing(self):
        self.assertIs(coerce("true"), True)
        self.assertIs(coerce("no"), False)

    def test_int_versus_float(self):
        self.assertEqual(coerce("42"), 42)
        self.assertEqual(coerce("4.5"), 4.5)

    def test_non_numeric_returns_string(self):
        self.assertEqual(coerce("ldm134_rmse"), "ldm134_rmse")

    def test_nan_float_returns_none(self):
        self.assertIsNone(coerce("nan"))

    def test_none_input_is_none(self):
        self.assertIsNone(coerce(None))


class CategoryForTests(unittest.TestCase):
    def test_header_keys_land_in_header(self):
        self.assertEqual(category_for("photo_a"), ("A", "header"))
        self.assertEqual(category_for("pose_bin"), ("A", "header"))

    def test_unknown_column_falls_back_without_loss(self):
        self.assertEqual(category_for("brand_new_col"), ("I", "other"))

    def test_known_prefix_maps(self):
        # mesh_rmse → категория B (mesh).
        self.assertEqual(category_for("mesh_rmse")[0], "B")
        # p95_point_z → категория D (point metrics), не fallback "other".
        self.assertEqual(category_for("p95_point_z")[0], "D")


class CategorizeColumnsTests(unittest.TestCase):
    def test_categories_split_by_prefix(self):
        row = {"p95_point_z": "3.2", "photo_a": "A", "unknown_x": "v"}
        cat = categorize_pair_columns(row)
        self.assertIn("A", cat)      # p95_point_z
        self.assertIn("I", cat)      # unknown_x
        self.assertEqual(cat["I"]["other"]["unknown_x"], "v")


class CategorizeStage1InfoTests(unittest.TestCase):
    def test_root_and_scalar_categorized(self):
        info = {"photo_id": "1999_08_12_1", "pose": {"yaw": 5.0}, "brand_new_root": {"a": 1}}
        cat = categorize_stage1_info(info)
        self.assertIn("G", cat)      # photo_id scalar
        self.assertIn("C", cat)      # pose root
        self.assertIn("H", cat)      # unknown root → other

    def test_nested_root_value_inlined(self):
        cat = categorize_stage1_info({"pose": {"yaw": 5.0, "pitch": 1.0}})
        pose_bucket = cat["C"].get("pose", {})
        self.assertEqual(pose_bucket.get("yaw"), 5.0)


class CategorizeManifestTests(unittest.TestCase):
    def test_rules_and_default_summary(self):
        manifest = {"config_hash": "h", "some_counter": 3}
        cat = categorize_manifest(manifest)
        self.assertIn("G", cat)      # config_hash → G reproducibility
        self.assertIn("I", cat)      # some_counter → I summary


if __name__ == "__main__":
    unittest.main()