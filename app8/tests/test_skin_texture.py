"""🧪 Тесты текстурного контракта app6 в app8 (flatten + fallback-маска).

Без инференса: проверяется CSV-упаковка `texture-v1` и fallback-путь
`build_skin_texture` на синтетической сетке (метрик тот же набор, но маска
из проекции видимых треугольников, origin фиксируется в texture.json).
"""
from __future__ import annotations
import tempfile
from pathlib import Path

import numpy as np
import pytest

from app8.packer import flatten_texture


def test_flatten_texture_nested_contract():
    tex = {
        "schema": "texture-v1",
        "photo_id": "x",
        "source": {"face_mask_png": "face_mask.png", "size": [10, 20], "mask_pixels": 30},
        "quality": {
            "metrics": {"q_noise_mad": 1.5, "q_mask_coverage": 0.4},
            "thresholds": {"q_noise_mad": 2.0},
            "hard_stop": False,
        },
        "authenticity": {
            "metrics": {"drv_pore_area": 0.12},
            "z_scores": {"drv_pore_area": -1.3},
            "score": 1.21,
        },
    }
    flat = flatten_texture(tex)
    assert flat["quality.metrics.q_noise_mad"] == 1.5
    assert flat["quality.metrics.q_mask_coverage"] == 0.4
    assert flat["authenticity.metrics.drv_pore_area"] == 0.12
    assert flat["authenticity.z_scores.drv_pore_area"] == -1.3
    assert flat["authenticity.score"] == 1.21
    assert flat["quality.hard_stop"] == 0  # bool → int
    # Справочные секции в CSV не попадают
    assert not any(k.startswith(("source.", "quality.thresholds.")) for k in flat)
    assert "schema" not in flat and "photo_id" not in flat


def _synthetic_recon(n_vert: int = 400) -> dict:
    """Мелкая «сетка»: вершины в прямоугольнике внутри кадра 240x200."""
    ii = np.arange(n_vert, dtype=np.float64)
    v2d = np.stack([60.0 + (ii % 20) * 5.0, 40.0 + (ii // 20) * 5.0], axis=1)
    tris = np.stack(
        [np.arange(0, n_vert - 2), np.arange(1, n_vert - 1), np.arange(2, n_vert)],
        axis=1,
    )
    return {
        "vertices_2d_orig": v2d.astype(np.float32),
        "triangles": tris.astype(np.int64),
        "visible_mask": np.ones(n_vert, bool),
        "ldm106_indices": np.arange(106, dtype=np.int64),
        "semantic_channels_224": None,  # форсируем fallback на проекцию сетки
    }


def test_build_skin_texture_fallback_origin():
    pytest.importorskip("app6.stage1.authenticity", reason="app6 contract required")
    from app8.assets import build_skin_texture

    rng = np.random.default_rng(7)
    bgr = rng.integers(0, 256, size=(240, 200, 3), dtype=np.uint8)

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "photo"
        summary = build_skin_texture(bgr, _synthetic_recon(), out_dir, photo_id="photo")

        texture_path = out_dir / "texture.json"
        assert texture_path.is_file()
        import json

        payload = json.loads(texture_path.read_text(encoding="utf-8"))
        assert payload["schema"] == "texture-v1"
        assert payload["source"]["mask_origin"] == "bfm_mesh_visible_projection"
        assert set(payload["quality"]["metrics"]) >= {
            "q_noise_mad", "q_grad_med", "q_lap_med", "q_contrast",
            "q_exposure_clip", "q_mask_coverage",
        }
        assert payload["authenticity"]["metrics"]
        # Тот же контракт, что и у app6: метрики пригодны для CSV-упаковки
        assert flatten_texture(payload)["quality.metrics.q_noise_mad"] == pytest.approx(
            payload["quality"]["metrics"]["q_noise_mad"]
        )
        assert summary["files"]["face_mask"] == "face_mask.png"
        assert (out_dir / "face_mask.png").is_file()
