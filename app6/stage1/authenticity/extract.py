"""Compute skin authenticity + quality from face_mask.png and write texture.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .v12_features import derive_v12_metrics, extract_v12_bases

_DIR = Path(__file__).resolve().parent
_MODEL_PATH = _DIR / "model_quality_gate.json"
_RECIPE_PATH = _DIR / "v12_test_recipe.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_face_mask_rgba(face_mask_png: Path) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(face_mask_png) as im:
        rgba = np.asarray(im.convert("RGBA"))
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("face_mask.png must be RGBA")
    if rgba.shape[:2] != (500, 424):
        rgba = cv2.resize(rgba, (424, 500), interpolation=cv2.INTER_AREA)
    rgb = rgba[..., :3].copy()
    mask = rgba[..., 3] > 16
    if int(mask.sum()) < 1500:
        raise ValueError("face_mask coverage too small for authenticity metrics")
    return rgb, mask


def extract_quality_metrics(rgb: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    x = rgb.astype(np.float64)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    m = mask.astype(bool)
    L = 0.299 * r + 0.587 * g + 0.114 * b
    v = L[m]
    p1, p99 = np.percentile(v, [1, 99])
    N = np.clip((L - p1) / (p99 - p1 + 1e-6), 0, 1)
    gx = cv2.Sobel(N, cv2.CV_64F, 1, 0, 3)
    gy = cv2.Sobel(N, cv2.CV_64F, 0, 1, 3)
    gm = np.hypot(gx, gy)
    lap = np.abs(cv2.Laplacian(N, cv2.CV_64F))
    lum8 = np.clip(L, 0, 255).astype(np.uint8)
    med = cv2.medianBlur(lum8, 3).astype(np.float64)
    res = (L - med)[m]
    return {
        "q_noise_mad": float(np.median(np.abs(res - np.median(res)))),
        "q_grad_med": float(np.median(gm[m])),
        "q_lap_med": float(np.median(lap[m])),
        "q_contrast": float(np.percentile(v, 95) - np.percentile(v, 5)),
        "q_exposure_clip": float(np.mean((v < 8) | (v > 247))),
        "q_mask_coverage": float(m.mean()),
    }


def _quality_score(q: dict[str, float], policy: dict[str, Any]) -> tuple[float, str, bool]:
    thr = policy.get("thresholds") or {}
    metrics = policy.get("metrics") or ["q_noise_mad", "q_grad_med", "q_lap_med"]
    required = int(policy.get("required_count", 3))
    low = 0
    ratios = []
    for m in metrics:
        t = float(thr.get(m, 0.0))
        val = float(q.get(m, 0.0))
        if val < t:
            low += 1
        ratios.append(min(2.0, val / (t + 1e-9)))
    hard_stop = bool(policy.get("enabled", True)) and low >= required
    score = float(np.clip(np.mean(ratios) / 2.0, 0.0, 1.0))
    if hard_stop:
        status = "insufficient"
    elif score >= 0.70:
        status = "high"
    elif score >= 0.40:
        status = "medium"
    else:
        status = "low"
    return score, status, hard_stop


def _panel_score(metrics: dict[str, float], panel: list[dict[str, Any]]) -> tuple[float, dict[str, float]]:
    z: dict[str, float] = {}
    vals = []
    for item in panel:
        name = item["metric"]
        if name not in metrics:
            raise KeyError(f"panel metric missing: {name}")
        direction = float(item.get("direction", 1.0))
        med = float(item["median"])
        mad = float(item.get("mad", 0.0)) + 1e-9
        scale = 1.4826 * mad
        zv = direction * (float(metrics[name]) - med) / scale
        z[name] = float(zv)
        vals.append(zv)
    return float(np.median(np.asarray(vals, dtype=np.float64))), z


def _authenticity_status(score: float | None, hard_stop: bool, q95: float, q99: float) -> str:
    if hard_stop or score is None:
        return "quality_insufficient"
    if score <= q95:
        return "high_authenticity"
    if score <= q99:
        return "borderline"
    return "low_authenticity"


def build_texture_package(
    *,
    out_dir: Path | str,
    face_mask_png: Path | str,
    photo_id: str | None = None,
    model_path: Path | str | None = None,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    face_mask_png = Path(face_mask_png)
    model = _load_json(Path(model_path) if model_path else _MODEL_PATH)
    recipe = _load_json(_RECIPE_PATH)

    rgb, mask = _load_face_mask_rgba(face_mask_png)
    q_metrics = extract_quality_metrics(rgb, mask)
    q_score, q_status, hard_stop = _quality_score(q_metrics, model.get("quality_policy") or {})

    bases = extract_v12_bases(rgb, mask)
    all_metrics = derive_v12_metrics(bases, recipe)
    panel = list(model.get("panel") or [])
    panel_names = [p["metric"] for p in panel]
    panel_metrics = {k: float(all_metrics[k]) for k in panel_names if k in all_metrics}
    missing = [k for k in panel_names if k not in panel_metrics]
    if missing:
        raise KeyError(f"failed to derive panel metrics: {missing[:8]}")

    raw_score, z_scores = _panel_score(panel_metrics, panel)
    thr = model.get("thresholds") or {}
    q95 = float(thr.get("q95", 1.16559))
    q99 = float(thr.get("q99", 1.40307))

    auth_score: float | None = None if hard_stop else float(raw_score)
    auth_status = _authenticity_status(auth_score, hard_stop, q95, q99)

    payload = {
        "schema": "texture-v1",
        "photo_id": photo_id,
        "source": {
            "face_mask_png": face_mask_png.name,
            "size": [int(rgb.shape[0]), int(rgb.shape[1])],
            "mask_pixels": int(mask.sum()),
        },
        "model": {
            "version": model.get("model_version", "skin-authenticity-v1"),
            "panel_size": len(panel),
            "aggregation": model.get("aggregation", "median_z_top20"),
            "libraries": ["numpy", "opencv-python-headless", "Pillow"],
            "source": model.get("source"),
        },
        "quality": {
            "score": q_score,
            "status": q_status,
            "hard_stop": hard_stop,
            "rule": {
                "required_count": int((model.get("quality_policy") or {}).get("required_count", 3)),
                "thresholds": (model.get("quality_policy") or {}).get("thresholds", {}),
            },
            "metrics": q_metrics,
        },
        "authenticity": {
            "score": auth_score,
            "status": auth_status,
            "raw_panel_score": float(raw_score),
            "thresholds": {"q95": q95, "q99": q99},
            "decision_rule": {
                "high_authenticity": "score <= q95",
                "borderline": "q95 < score <= q99",
                "low_authenticity": "score > q99",
                "quality_insufficient": "quality.hard_stop == true",
            },
            "aggregation": "median_z_top20",
            "metrics": panel_metrics,
            "z_scores": z_scores,
        },
    }

    texture_path = out_dir / "texture.json"
    tmp = texture_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(texture_path)

    return {
        "state": "success",
        "source": "face_mask.png",
        "contract": "skin-authenticity-v1",
        "panel": "top20_z_median",
        "texture_file": "texture.json",
        "hard_stop": hard_stop,
        "hard_stop_reason": "low_detail" if hard_stop else None,
        "skin_quality_score": q_score,
        "skin_quality_status": q_status,
        "skin_authenticity_score": auth_score,
        "skin_authenticity_status": auth_status,
        "files": {"texture": "texture.json"},
    }
