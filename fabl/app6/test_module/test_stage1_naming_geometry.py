"""🎯 GUARD → Stage 1: парсинг имён фото и базовая геометрия (ER-158 / ER-001).

naming (ER-001 / D-002): дата из имени файла — authoritative; copy-суффиксы (2)/_2/-copy
интерпретируются как sequence; фото без даты отклоняется.
geometry (D-001): 9 pose-бинов, центрирование/шкалирование mesh, pack/unpack mask.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from app6.stage1.geometry import (
    classify_pose,
    full_pose_correction_matrix,
    nearest_canonical_yaw,
    normalize_mesh,
    pack_mask,
    row_rotation_matrix,
    unpack_mask,
)
from app6.stage1.naming import make_nonchronological_photo_name, make_photo_id, parse_photo_name


class ParsePhotoNameTests(unittest.TestCase):
    def test_basic_date_parses(self):
        p = parse_photo_name(Path("2020_05_17.jpg"))
        self.assertEqual(p.date_iso, "2020-05-17")
        self.assertEqual((p.year, p.month, p.day), (2020, 5, 17))
        self.assertEqual(p.sequence, 1)
        self.assertEqual(p.canonical_stem, "2020_05_17")

    def test_copy_suffix_parenthesized_sets_sequence(self):
        self.assertEqual(parse_photo_name(Path("1999_08_12 (2).jpg")).sequence, 2)

    def test_underscore_copy_suffix_sets_sequence(self):
        self.assertEqual(parse_photo_name(Path("1999_08_12_2.jpg")).sequence, 2)

    def test_copy_word_suffix_is_first_copy(self):
        # P2.13: "-copy" без числа возвращает sequence=1, а не ошибку.
        self.assertEqual(parse_photo_name(Path("1999_08_12-copy.jpg")).sequence, 1)

    def test_filename_without_date_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_photo_name(Path("misc_label.png"))

    def test_date_embedded_in_alphanumeric_token_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_photo_name(Path("x2020_01_01.jpg"))

    def test_canonical_stem_keeps_normalized_rest(self):
        p = parse_photo_name(Path("2025_03_27_y5p10r0.jpg"))
        self.assertEqual(p.canonical_stem, "2025_03_27_y5p10r0")


class MakePhotoIdTests(unittest.TestCase):
    def test_without_digest_returns_canonical_stem(self):
        p = parse_photo_name(Path("2020_01_01.jpg"))
        self.assertEqual(make_photo_id(p, None), "2020_01_01")

    def test_photo_id_includes_hash_prefix(self):
        p = parse_photo_name(Path("2020_01_01.jpg"))
        pid = make_photo_id(p, "a" * 64)
        self.assertTrue(pid.startswith("2020_01_01__"))
        self.assertEqual(pid, f"2020_01_01__{'a' * 12}")

    def test_invalid_digest_rejected(self):
        p = parse_photo_name(Path("2020_01_01.jpg"))
        with self.assertRaises(ValueError):
            make_photo_id(p, "not-hex")

    def test_nonchronological_name_builds_stable_slug(self):
        p = make_nonchronological_photo_name(Path("x.jpg"), "person_1/frame_001.jpg")
        self.assertEqual(p.date_iso, "")
        self.assertTrue(p.canonical_stem.startswith("calibration_"))


class ClassifyPoseTests(unittest.TestCase):
    def test_frontal_bin(self):
        self.assertEqual(classify_pose(0.0)[0], "frontal")

    def test_left_light_bin(self):
        self.assertEqual(classify_pose(-12.0)[0], "left_light")

    def test_left_profile_bin(self):
        self.assertEqual(classify_pose(-70.0)[0], "left_profile")

    def test_right_profile_bin(self):
        self.assertEqual(classify_pose(70.0)[0], "right_profile")

    def test_nan_yaw_rejected(self):
        with self.assertRaises(ValueError):
            classify_pose(float("nan"))

    def test_out_of_range_declared(self):
        self.assertEqual(classify_pose(120.0)[0], "out_of_supported_range")

    def test_nearest_canonical_soft_assignment(self):
        # yaw=-12° ближе к canonical −17.5° (left_light), чем к frontal 0°.
        self.assertEqual(nearest_canonical_yaw(-12.0)[0], "left_light")


class GeometryHelperTests(unittest.TestCase):
    def test_rotation_matrix_is_finite_3x3(self):
        R = row_rotation_matrix(1.0, 2.0, 3.0)
        self.assertEqual(R.shape, (3, 3))
        self.assertTrue(np.isfinite(R).all())

    def test_pose_correction_matrix_finite(self):
        R = full_pose_correction_matrix([1.0, 2.0, 3.0], [0.0, 0.0, 0.0])
        self.assertEqual(R.shape, (3, 3))
        self.assertTrue(np.isfinite(R).all())

    def test_pose_correction_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            full_pose_correction_matrix([1.0, 2.0], [0.0, 0.0, 0.0])

    def test_normalize_mesh_centers_and_scales(self):
        mesh = np.array([[10.0, 0, 0], [12.0, 0, 0], [11.0, 0, 0]], np.float32)
        norm, center, scale = normalize_mesh(mesh)
        self.assertTrue(np.isfinite(norm).all())
        self.assertAlmostEqual(float(np.mean(norm[:, 0])), 0.0, places=5)
        self.assertGreater(scale, 0.0)
        self.assertTrue(np.allclose(center, [11.0, 0, 0], atol=1e-5))

    def test_pack_unpack_mask_roundtrip(self):
        mask = np.array([1, 0, 1, 1, 0, 0, 1, 0, 1], bool)
        back = unpack_mask(pack_mask(mask), len(mask)).astype(bool)
        np.testing.assert_array_equal(back[: len(mask)], mask)

    def test_unpack_mask_rejects_short_packed(self):
        with self.assertRaises(ValueError):
            unpack_mask(np.zeros(1, np.uint8), count=16)


if __name__ == "__main__":
    unittest.main()