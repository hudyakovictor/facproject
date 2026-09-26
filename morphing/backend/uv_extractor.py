"""🎨 Генерация улучшенных HD UV-текстур через uv_module для 3D-морфинга."""
from __future__ import annotations
import base64
from pathlib import Path
from typing import Any
import cv2
import numpy as np
from uv_module import HDUVConfig, HDUVTextureGenerator


def extract_enhanced_uv(bgr: np.ndarray,
                        recon_data: dict[str, Any],
                        uv_size: int = 1024) -> tuple[np.ndarray, str]:
    """Генерирует улучшенную HD UV-текстуру через uv_module с усилением деталей и симметрией.
    
    Returns:
        tuple[np.ndarray, str]: (BGR изображение текстуры, base64 data-URL)
    """
    v_cam = recon_data["vertices_camera"]
    v_2d = recon_data["vertices_2d_orig"]
    triangles = recon_data["triangles"]
    uv_coords = recon_data["uv_coords"]
    normals = recon_data["normals_object"]
    alpha_sh = recon_data.get("alpha_sh", np.zeros(27, np.float32))
    
    recon_dict = {
        "vertices": v_cam,
        "vertices_3d": v_cam,
        "vertices_2d": v_2d,
        "triangles": triangles,
        "uv_coords": uv_coords,
        "normals_3d": recon_data.get("normals_posed", normals),
        "alpha_sh": alpha_sh,
        "skin_mask": None,
    }
    
    cfg = HDUVConfig(
        uv_size=int(uv_size),
        super_sample=2,
        enable_delighting=False,
        enable_symmetry_fill=True,
        enable_detail_boost=True,
        detail_strength=1.15,
        unsharp_amount=0.25,
        device="cpu",
    )
    
    gen = HDUVTextureGenerator(cfg)
    _, uv_beauty, _, _, _ = gen.generate(bgr, recon_dict)
    
    # Конвертация в Base64 для передачи на фронтенд
    _, buf = cv2.imencode(".png", uv_beauty, [cv2.IMWRITE_PNG_COMPRESSION, 4])
    b64_str = "data:image/png;base64," + base64.b64encode(buf).decode("utf-8")
    
    return uv_beauty, b64_str
