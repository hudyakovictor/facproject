"""🧪 Тесты модуля агрегации и упаковки 9 ракурсов (app8 Packer)."""
from __future__ import annotations
import tempfile
from pathlib import Path
import numpy as np
import pytest

from app8.storage import save_stage1_record
from app8.packer import pack_pose_bins


def test_pack_pose_bins_e2e():
    with tempfile.TemporaryDirectory() as tmp_dir:
        stage1_out = Path(tmp_dir) / "stage1_test"
        packed_out = Path(tmp_dir) / "packed_9bins"
        
        n_vert = 35709
        # Создаем 2 кадра во фронте и 1 в профиле
        for p_id, d_iso, y_deg, p_bin, c_yaw in [
            ("photo_1999", "1999-01-01", 2.0, "frontal", 0.0),
            ("photo_2005", "2005-05-05", -3.0, "frontal", 0.0),
            ("photo_2010", "2010-10-10", 65.0, "right_profile", 70.0),
        ]:
            out_d = stage1_out / p_id
            fake_data = {
                "date_iso": d_iso,
                "alpha_id": np.random.randn(80).astype(np.float32),
                "alpha_exp": np.random.randn(64).astype(np.float32),
                "angles_deg": np.array([0.0, y_deg, 0.0], np.float32),
                "angles_rad": np.deg2rad(np.array([0.0, y_deg, 0.0], np.float32)),
                "pose_bin": p_bin,
                "canonical_yaw": c_yaw,
                "rotation_matrix": np.eye(3, dtype=np.float32),
                "translation": np.zeros(3, dtype=np.float32),
                "trans_params": np.zeros(4, dtype=np.float32),
                "chronology_correction_matrix": np.eye(3, dtype=np.float32),
                "vertices_object": np.random.randn(n_vert, 3).astype(np.float32),
                "vertices_identity_only": np.random.randn(n_vert, 3).astype(np.float32),
                "vertices_chronology_aligned": np.random.randn(n_vert, 3).astype(np.float32),
                "normals_object": np.random.randn(n_vert, 3).astype(np.float32),
                "visible_mask": np.ones(n_vert, bool),
                "front_facing": np.ones(n_vert, bool),
                "renderer_visible": np.ones(n_vert, bool),
                "vertex_confidence": np.ones(n_vert, np.float32),
                "ldm134_indices": np.arange(134, dtype=np.int64),
                "ldm106_indices": np.arange(106, dtype=np.int64),
                "uv_coords": np.random.rand(n_vert, 2).astype(np.float32),
                "triangles": np.zeros((70789, 3), dtype=np.int64),
                "expression_qc": {"is_smiling": False, "is_mouth_open": False},
            }
            save_stage1_record(out_d, p_id, fake_data)
            
        report = pack_pose_bins(stage1_out, packed_out)
        assert report["active_bins_count"] == 2
        assert (packed_out / "packed_manifest.json").is_file()
        
        # Проверка фронтального пакета
        front_d = packed_out / "frontal"
        assert (front_d / "frontal.npz").is_file()
        assert (front_d / "landmarks_106_chronology.csv").is_file()
        assert (front_d / "landmarks_134_chronology.csv").is_file()
        assert (front_d / "skin_texture_chronology.csv").is_file()
        assert (front_d / "timeline_summary.txt").is_file()
        assert (front_d / "info.json").is_file()
        
        # Проверка содержимого frontal.npz - БЕЗ 35k вершин сетки
        with np.load(front_d / "frontal.npz") as z:
            assert len(z["photo_ids"]) == 2
            assert "vertices_chronology" not in z  # Сетки исключены!
            assert z["ldm106_chronology"].shape == (2, 106, 3)
            assert z["ldm134_chronology"].shape == (2, 134, 3)
            assert z["ldm106_confidence"].shape == (2, 106)
            assert z["ldm134_confidence"].shape == (2, 134)
