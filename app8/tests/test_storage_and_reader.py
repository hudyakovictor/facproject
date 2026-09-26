"""🧪 Тесты бинарного хранилища и Reader API (app8)."""
from __future__ import annotations
import tempfile
from pathlib import Path
import numpy as np

from app8.storage import save_stage1_record
from app8.reader import load_record, get_ldm134, get_ldm106


def test_storage_and_reader():
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "test_photo_01"
        
        n_vert = 35709
        fake_data = {
            "date_iso": "2024-01-01",
            "alpha_id": np.random.randn(80).astype(np.float32),
            "alpha_exp": np.random.randn(64).astype(np.float32),
            "alpha_alb": np.zeros(80, np.float32),
            "alpha_sh": np.zeros(27, np.float32),
            "angles_deg": np.array([5.0, 15.0, 2.0], np.float32),
            "angles_rad": np.deg2rad(np.array([5.0, 15.0, 2.0], np.float32)),
            "pose_bin": "right_light",
            "canonical_yaw": 17.5,
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
        
        saved = save_stage1_record(out_dir, "test_photo_01", fake_data)
        assert (out_dir / "reconstruction.npz").is_file()
        assert (out_dir / "info.json").is_file()
        
        # Проверка отсутствия CSV-файлов (Zero CSV Bloat)
        csv_files = list(out_dir.glob("*.csv"))
        assert len(csv_files) == 0, f"Expected 0 CSV files, found {len(csv_files)}"
        
        # Загрузка через Reader API
        rec = load_record(out_dir)
        assert rec.photo_id == "test_photo_01"
        assert rec.date_iso == "2024-01-01"
        assert rec.pose_bin == "right_light"
        assert rec.canonical_yaw == 17.5
        assert rec.vertices_object.shape == (n_vert, 3)
        assert rec.visible_mask.sum() == n_vert
        
        # Извлечение 134 и 106 точек
        l134 = get_ldm134(rec, space="identity_only")
        assert l134.shape == (134, 3)
        
        l106 = get_ldm106(rec, space="chronology")
        assert l106.shape == (106, 3)
