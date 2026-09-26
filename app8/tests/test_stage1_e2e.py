"""🧪 E2E интеграционный тест Stage 1 (app8)."""
from __future__ import annotations
import tempfile
from pathlib import Path
import pytest

from app8.config import Stage1Config
from app8.engine import run_stage1
from app8.reader import load_record, get_ldm134, get_ldm106


def test_stage1_e2e_real_images():
    input_dir = Path("/home/user/facproject/dataset_realtest")
    if not input_dir.is_dir():
        pytest.skip("dataset_realtest not found")
        
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "stage1_output"
        
        cfg = Stage1Config(
            project_root=Path("/home/user/facproject"),
            input_dir=input_dir,
            output_dir=out_dir,
            device="cpu",
            limit=2,
            save_mesh=False,
            save_original=False,
            overwrite=True,
        )
        
        manifest = run_stage1(cfg)
        assert manifest["processed_success"] == 2
        assert manifest["processed_failed"] == 0
        assert (out_dir / "stage1_manifest.json").is_file()
        
        # Проверяем структуру первой папки
        p1_dir = out_dir / "2024_01_01"
        assert (p1_dir / "reconstruction.npz").is_file()
        assert (p1_dir / "info.json").is_file()
        
        # Проверка отсутствия лишних CSV
        csv_files = list(p1_dir.glob("*.csv"))
        assert len(csv_files) == 0
        
        # Проверка чтения данных
        rec = load_record(p1_dir)
        assert rec.photo_id == "2024_01_01"
        assert rec.date_iso == "2024-01-01"
        assert rec.pose_bin in {"frontal", "left_light", "right_light"}
        
        # Проверка ключевых точек
        l134 = get_ldm134(rec, "chronology")
        assert l134.shape == (134, 3)
        l106 = get_ldm106(rec, "identity_only")
        assert l106.shape == (106, 3)
