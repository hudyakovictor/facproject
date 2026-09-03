"""📥 Stage 3 v2 Loader — загрузка Stage 2 output.

Читает:
  - pair_metrics.csv (основные метрики пар)
  - zone_metrics.csv (метрики по зонам)
  - change_points.json (обнаруженные change points)
  - point_noise_model.npz (калибровочный шум)
  - analysis_manifest.json (манифест Stage 2)
  - motion files (per-pair motion data)

Возвращает структурированные данные для анализа.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
import numpy as np

from .types import PairAnalysis


class Stage2Loader:
    """Загрузчик Stage 2 output."""
    
    def __init__(self, stage2_root: Path):
        self.root = Path(stage2_root).resolve()
        if not self.root.exists():
            raise ValueError(f"Stage 2 root does not exist: {self.root}")
    
    def load_pair_metrics(self) -> list[dict[str, Any]]:
        """Загрузить pair_metrics.csv."""
        path = self.root / "pair_metrics.csv"
        if not path.exists():
            raise FileNotFoundError(f"pair_metrics.csv not found: {path}")
        
        with path.open(newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    
    def load_zone_metrics(self) -> list[dict[str, Any]]:
        """Загрузить zone_metrics.csv."""
        path = self.root / "zone_metrics.csv"
        if not path.exists():
            return []
        
        with path.open(newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    
    def load_change_points(self) -> dict[str, Any]:
        """Загрузить change_points.json."""
        path = self.root / "change_points.json"
        if not path.exists():
            return {"change_points": []}
        
        return json.loads(path.read_text(encoding='utf-8'))
    
    def load_manifest(self) -> dict[str, Any]:
        """Загрузить analysis_manifest.json."""
        path = self.root / "analysis_manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"analysis_manifest.json not found: {path}")
        
        return json.loads(path.read_text(encoding='utf-8'))
    
    def load_noise_model(self) -> Optional[np.ndarray]:
        """Загрузить point_noise_model.npz."""
        path = self.root / "point_noise_model.npz"
        if not path.exists():
            return None
        
        return np.load(path, allow_pickle=False)
    
    def load_motion_file(self, motion_path: str) -> Optional[dict[str, np.ndarray]]:
        """Загрузить motion file для одной пары."""
        full_path = self.root / motion_path
        if not full_path.exists():
            return None
        
        with np.load(full_path, allow_pickle=False) as z:
            return {
                "point_z": z["ldm134_point_z"],
                "vectors": z["ldm134_vectors"],
                "magnitude": z["ldm134_magnitude"],
                "significant": z["ldm134_significant"].astype(bool),
            }
    
    def load_all_pairs(self) -> list[dict[str, Any]]:
        """Загрузить все пары с базовыми метриками."""
        pairs = self.load_pair_metrics()
        
        # Filter out invalid pairs
        valid = []
        for pair in pairs:
            if pair.get("status") == "no_pairs":
                continue
            valid.append(pair)
        
        return valid
    
    def extract_pair_features(self, pair: dict[str, Any]) -> dict[str, float]:
        """Извлечь числовые features из pair dict."""
        
        def _safe_float(val, default=0.0):
            if val in (None, '', 'nan', 'NaN'):
                return default
            try:
                v = float(val)
                return v if np.isfinite(v) else default
            except (TypeError, ValueError):
                return default
        
        return {
            "p95_point_z": _safe_float(pair.get("p95_point_z")),
            "coherent_motion_fraction": _safe_float(pair.get("coherent_motion_fraction")),
            "significant_point_fraction": _safe_float(pair.get("significant_point_fraction")),
            "mesh_rmse": _safe_float(pair.get("mesh_rmse")),
            "descriptor_p95_z": _safe_float(pair.get("descriptor_p95_z")),
            "pose_distance_deg": _safe_float(pair.get("pose_distance_deg")),
            "days_delta": _safe_float(pair.get("days_delta")),
            "quality_score": _safe_float(pair.get("quality_score"), 0.8),
        }
    
    def get_adjacent_pairs(self) -> list[dict[str, Any]]:
        """Получить только adjacent pairs (соседние по времени)."""
        pairs = self.load_all_pairs()
        return [p for p in pairs if p.get("pair_type") == "adjacent"]
    
    def get_pose_bins(self) -> set[str]:
        """Получить все pose bins."""
        pairs = self.load_all_pairs()
        return {p.get("pose_bin", "unknown") for p in pairs if p.get("pose_bin")}
    
    def get_date_range(self) -> tuple[Optional[datetime], Optional[datetime]]:
        """Получить диапазон дат."""
        pairs = self.get_adjacent_pairs()
        dates = []
        for p in pairs:
            d = p.get("date_b")
            if d:
                try:
                    dates.append(datetime.fromisoformat(d))
                except (ValueError, TypeError):
                    pass
        
        if not dates:
            return None, None
        
        return min(dates), max(dates)
    
    def validate_stage2_output(self) -> tuple[bool, list[str]]:
        """Проверить валидность Stage 2 output."""
        errors = []
        
        # Check required files
        required = ["pair_metrics.csv", "analysis_manifest.json"]
        for fname in required:
            if not (self.root / fname).exists():
                errors.append(f"Missing required file: {fname}")
        
        # Check manifest status
        if not errors:
            manifest = self.load_manifest()
            if manifest.get("status") != "complete":
                errors.append(f"Manifest status is not complete: {manifest.get('status')}")
        
        # Check validation
        validation_path = self.root / "analysis_validation.json"
        if validation_path.exists():
            validation = json.loads(validation_path.read_text(encoding='utf-8'))
            if validation.get("status") != "complete":
                errors.append(f"Validation status is not complete: {validation.get('status')}")
        
        return len(errors) == 0, errors


def load_stage2_data(stage2_root: Path) -> tuple[list[dict], dict, dict]:
    """
    Convenience function: загрузить все данные Stage 2.
    
    Returns:
        (pairs, manifest, change_points)
    """
    loader = Stage2Loader(stage2_root)
    
    # Validate
    valid, errors = loader.validate_stage2_output()
    if not valid:
        raise RuntimeError(f"Stage 2 output validation failed: {errors}")
    
    # Load
    pairs = loader.load_all_pairs()
    manifest = loader.load_manifest()
    change_points = loader.load_change_points()
    
    return pairs, manifest, change_points
