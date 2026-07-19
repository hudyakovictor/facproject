from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from app6.stage1.config import PHOTO_SCHEMA_VERSION
from app6.stage1.geometry import pack_mask
from app6.stage1.validator import MESH_COUNT, NPZ_REQUIRED, TRIANGLE_COUNT, validate_photo


def _csv(path: Path, n: int, points: np.ndarray, indices: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["landmark_id", "x", "y", "z", "visible", "vertex_index"])
        w.writeheader()
        for i in range(n):
            w.writerow({"landmark_id": i, "x": points[i, 0], "y": points[i, 1], "z": points[i, 2], "visible": 1, "vertex_index": indices[i]})


def _fixture(root: Path) -> None:
    idx106 = np.arange(106, dtype=np.int64); idx134 = np.arange(134, dtype=np.int64)
    p106 = np.zeros((106, 3), np.float32); p134 = np.zeros((134, 3), np.float32)
    for name, n, pts, idx in (("ldm106_raw.csv", 106, p106, idx106), ("ldm106_aligned.csv", 106, p106, idx106),
                              ("ldm134_raw.csv", 134, p134, idx134), ("ldm134_aligned.csv", 134, p134, idx134)):
        _csv(root / name, n, pts, idx)
    image = np.full((16, 16, 3), 127, np.uint8)
    for name in ("face_crop.jpg", "uv_texture.png"):
        cv2.imwrite(str(root / name), image)
    np.savez_compressed(root / "semantic_channels.npz", channels_224=np.zeros((224, 224, 8), np.float16))
    front = np.ones(MESH_COUNT, np.uint8); renderer = np.ones(MESH_COUNT, np.uint8)
    arrays = {k: np.zeros(shape, np.float32) for k, shape in NPZ_REQUIRED.items()}
    arrays.update({
        "triangles": np.zeros((TRIANGLE_COUNT, 3), np.int64), "ldm106_vertex_indices": idx106,
        "ldm134_vertex_indices": idx134, "rotation_matrix": np.eye(3, dtype=np.float32),
        "canonical_rotation_row_matrix": np.eye(3, dtype=np.float32), "normalization_scale": np.ones(1, np.float32),
        "full_mesh_front_facing_packbits": pack_mask(front),
        "full_mesh_renderer_visible_packbits": pack_mask(renderer), "full_mesh_visible_packbits": pack_mask(front & renderer),
        "ldm106_object": p106, "ldm106_bin_canonical": p106, "ldm134_object": p134, "ldm134_bin_canonical": p134,
        "uv_shape": np.array([8, 8], np.int32), "uv_confidence": np.zeros((8, 8), np.float16),
        "uv_observed_mask_packbits": np.zeros(8, np.uint8), "uv_is_original_packbits": np.zeros(8, np.uint8),
        "tri_visibility": np.zeros(TRIANGLE_COUNT, np.float16),
    })
    np.savez_compressed(root / "reconstruction.npz", **arrays)
    files = {
        "face_crop": "face_crop.jpg", "uv_texture": "uv_texture.png",
        "semantic_channels": "semantic_channels.npz", "reconstruction": "reconstruction.npz",
        "ldm106_raw": "ldm106_raw.csv", "ldm106_aligned": "ldm106_aligned.csv",
        "ldm134_raw": "ldm134_raw.csv", "ldm134_aligned": "ldm134_aligned.csv",
    }
    (root / "info.json").write_text(json.dumps({"schema_version": PHOTO_SCHEMA_VERSION, "photo_id": "p", "mask": {"status": "projection_failed"}, "files": files}))


class ValidatorTests(unittest.TestCase):
    def test_valid_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); _fixture(root)
            self.assertEqual(validate_photo(root, write_result=False)["status"], "complete")

    def test_corrupt_visibility_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); _fixture(root)
            with np.load(root / "reconstruction.npz") as z: arrays = {k: z[k] for k in z.files}
            arrays["full_mesh_visible_packbits"] = np.zeros(4464, np.uint8)
            np.savez_compressed(root / "reconstruction.npz", **arrays)
            result = validate_photo(root, write_result=False)
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(any("combined visibility" in e for e in result["errors"]))


if __name__ == "__main__": unittest.main()
