"""💾 Унифицированное бинарное сохранение результатов 1-го этапа (app8).

Сохраняет ЕДИНЫЙ компактный файл `reconstruction.npz` и легковесный `info.json`.
Полностью исключает генерацию 8 избыточных CSV-файлов точек.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np

from .config import SCHEMA_VERSION, PHOTO_SCHEMA_VERSION
from .visibility import pack_mask


def save_stage1_record(out_dir: Path,
                       photo_id: str,
                       data: dict[str, Any]) -> dict[str, str]:
    """Сохраняет структурированный результат реконструкции одного кадра.
    
    Возвращает словарь созданных файлов.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Подготовка бинарных массивов для npz
    arrays: dict[str, np.ndarray] = {
        # Схема и метаданные
        "schema": np.asarray(SCHEMA_VERSION),
        "photo_id": np.asarray(photo_id),
        "date_iso": np.asarray(str(data.get("date_iso", ""))),
        
        # 3DMM Коэффициенты
        "alpha_id": np.asarray(data["alpha_id"], np.float32),
        "alpha_exp": np.asarray(data["alpha_exp"], np.float32),
        "alpha_alb": np.asarray(data.get("alpha_alb", np.zeros(80)), np.float32),
        "alpha_sh": np.asarray(data.get("alpha_sh", np.zeros(27)), np.float32),
        
        # Ориентация и каноническая классификация позы
        "angle_deg_pitch_yaw_roll": np.asarray(data["angles_deg"], np.float32),
        "angle_rad": np.asarray(data["angles_rad"], np.float32),
        "pose_bin": np.asarray(str(data["pose_bin"])),
        "canonical_yaw": np.asarray([float(data["canonical_yaw"])], np.float32),
        "rotation_matrix": np.asarray(data["rotation_matrix"], np.float32),
        "translation": np.asarray(data["translation"], np.float32),
        "trans_params": np.asarray(data["trans_params"], np.float32),
        "chronology_correction_matrix": np.asarray(data["chronology_correction_matrix"], np.float32),
        
        # Полная 3DMM Сетка (35 709 вершин)
        "vertices_object": np.asarray(data["vertices_object"], np.float32),
        "vertices_identity_only": np.asarray(data["vertices_identity_only"], np.float32),
        "vertices_chronology_aligned": np.asarray(data["vertices_chronology_aligned"], np.float32),
        "normals_object": np.asarray(data["normals_object"], np.float32),
        "uv_coords": np.asarray(data["uv_coords"], np.float32),
        "triangles": np.asarray(data["triangles"], np.int64),
        
        # Карты видимости и достоверности
        "vertex_confidence": np.asarray(data["vertex_confidence"], np.float32),
        "full_mesh_visible_packbits": pack_mask(data["visible_mask"]),
        "full_mesh_front_facing_packbits": pack_mask(data["front_facing"]),
        "full_mesh_renderer_visible_packbits": pack_mask(data["renderer_visible"]),
        
        # Индексы ключевых точек (топология)
        "ldm134_vertex_indices": np.asarray(data["ldm134_indices"], np.int64),
        "ldm106_vertex_indices": np.asarray(data["ldm106_indices"], np.int64),
    }
    
    # Сохранение сжатого бинарного контейнера
    npz_path = out_dir / "reconstruction.npz"
    np.savez_compressed(npz_path, **arrays)
    
    # Легковесный информационный JSON для быстрого листинга каталога
    info_dict = {
        "schema": PHOTO_SCHEMA_VERSION,
        "photo_id": photo_id,
        "date_iso": str(data.get("date_iso", "")),
        "pose": {
            "pitch_deg": float(data["angles_deg"][0]),
            "yaw_deg": float(data["angles_deg"][1]),
            "roll_deg": float(data["angles_deg"][2]),
            "pose_bin": str(data["pose_bin"]),
            "canonical_yaw": float(data["canonical_yaw"]),
        },
        "expression_qc": data.get("expression_qc", {}),
        "vertex_count": int(data["vertices_object"].shape[0]),
        "visible_vertex_count": int(np.sum(data["visible_mask"])),
        "files": {
            "reconstruction": "reconstruction.npz",
            "info": "info.json",
        }
    }
    
    info_path = out_dir / "info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info_dict, f, indent=2, ensure_ascii=False)
        
    return {
        "reconstruction": "reconstruction.npz",
        "info": "info.json",
    }
