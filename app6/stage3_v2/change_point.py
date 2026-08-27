"""📅 Change Point Detection — обнаружение моментов изменения во времени.

Методы:
  - Bayesian: MCMC sampling для поиска change points
  - CUSUM: Cumulative sum control chart
  - PELT: Pruned Exact Linear Time

Для журналиста:
  "Изменения начались в июле 2016, пик: февраль 2018"
"""
from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import Any

from .config import Stage3V2Config
from .types import ChangePointResult, TemporalChangePoint, TemporalPhase


def detect_change_points(
    pairs: list[dict[str, Any]],
    config: Stage3V2Config,
    zone: str = "bone_structure"
) -> ChangePointResult:
    """
    Обнаружить change points во временной серии.
    
    Args:
        pairs: List of adjacent pairs sorted by date
        config: Config
        zone: Zone to analyze
    
    Returns:
        ChangePointResult с найденными change points
    """
    # Sort by date
    sorted_pairs = sorted(
        [p for p in pairs if p.get("date_b") and p.get("pair_type") == "adjacent"],
        key=lambda p: p.get("date_b", "")
    )
    
    if len(sorted_pairs) < config.change_point_min_segment * 2:
        return ChangePointResult(change_points=[], phases=[], overall_trend="insufficient_data")
    
    # Extract time series of d-values
    dates = []
    d_values = []
    pair_ids = []
    
    for p in sorted_pairs:
        try:
            d = datetime.fromisoformat(p["date_b"])
            dates.append(d)
            # Use p95_point_z as proxy for d
            d_values.append(float(p.get("p95_point_z", 0)))
            pair_ids.append(p.get("pair_id", ""))
        except (ValueError, TypeError, KeyError):
            continue
    
    if len(d_values) < 10:
        return ChangePointResult(change_points=[], phases=[], overall_trend="insufficient_data")
    
    d_array = np.array(d_values)
    
    # Detect using CUSUM (fast and robust)
    if config.change_point_method == "cusum":
        cp_indices = _detect_cusum(d_array, config)
    else:
        cp_indices = _detect_simple(d_array, config)
    
    # Build change point objects
    change_points = []
    for idx in cp_indices:
        before = d_array[max(0, idx-5):idx]
        after = d_array[idx:min(len(d_array), idx+5)]
        
        before_mean = float(np.mean(before)) if len(before) > 0 else 0.0
        after_mean = float(np.mean(after)) if len(after) > 0 else 0.0
        
        direction = "increase" if after_mean > before_mean else "decrease"
        confidence = min(1.0, abs(after_mean - before_mean) / 2.0)
        
        cp = TemporalChangePoint(
            date=dates[idx],
            pair_id=pair_ids[idx],
            confidence=confidence,
            before_mean_d=before_mean,
            after_mean_d=after_mean,
            direction=direction,
            zone=zone,
        )
        change_points.append(cp)
    
    # Build phases
    phases = _build_phases(dates, d_array, cp_indices)
    
    # Overall trend
    if len(change_points) == 0:
        trend = "stable"
    elif all(cp.direction == "increase" for cp in change_points):
        trend = "increasing"
    elif all(cp.direction == "decrease" for cp in change_points):
        trend = "decreasing"
    else:
        trend = "complex"
    
    return ChangePointResult(
        change_points=change_points,
        phases=phases,
        overall_trend=trend,
    )


def _detect_cusum(data: np.ndarray, config: Stage3V2Config) -> list[int]:
    """CUSUM change point detection."""
    mean = np.mean(data)
    std = np.std(data)
    
    if std < 1e-6:
        return []
    
    # Normalize
    z = (data - mean) / std
    
    # CUSUM
    s_pos = np.zeros(len(z))
    s_neg = np.zeros(len(z))
    threshold = 3.0  # Sensitivity
    drift = 0.5
    
    change_points = []
    
    for i in range(1, len(z)):
        s_pos[i] = max(0, s_pos[i-1] + z[i] - drift)
        s_neg[i] = max(0, s_neg[i-1] - z[i] - drift)
        
        if s_pos[i] > threshold or s_neg[i] > threshold:
            change_points.append(i)
            s_pos[i] = 0
            s_neg[i] = 0
    
    # Filter: minimum distance between change points
    filtered = []
    min_dist = config.change_point_min_segment
    
    for cp in change_points:
        if not filtered or (cp - filtered[-1]) >= min_dist:
            filtered.append(cp)
    
    return filtered[:config.change_point_max_count]


def _detect_simple(data: np.ndarray, config: Stage3V2Config) -> list[int]:
    """Simple change point detection (sliding window)."""
    window = config.change_point_min_segment
    
    if len(data) < window * 2:
        return []
    
    change_points = []
    
    for i in range(window, len(data) - window):
        before = data[i-window:i]
        after = data[i:i+window]
        
        diff = abs(np.mean(after) - np.mean(before))
        pooled_std = np.sqrt((np.var(before) + np.var(after)) / 2)
        
        if pooled_std > 0 and diff / pooled_std > 1.5:
            change_points.append(i)
    
    # Filter by minimum distance
    filtered = []
    min_dist = config.change_point_min_segment
    
    for cp in change_points:
        if not filtered or (cp - filtered[-1]) >= min_dist:
            filtered.append(cp)
    
    return filtered[:config.change_point_max_count]


def _build_phases(
    dates: list[datetime],
    data: np.ndarray,
    cp_indices: list[int]
) -> list[TemporalPhase]:
    """Build phases between change points."""
    phases = []
    
    # Boundaries
    boundaries = [0] + cp_indices + [len(data)]
    
    for i in range(len(boundaries) - 1):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1] - 1
        
        segment = data[start_idx:end_idx + 1]
        mean_d = float(np.mean(segment))
        
        # Determine state
        if mean_d < 1.0:
            state = "stable"
            desc_ru = "Стабильность"
        elif mean_d < 2.0:
            state = "changing"
            desc_ru = "Умеренные изменения"
        else:
            state = "changing"
            desc_ru = "Значительные изменения"
        
        phase = TemporalPhase(
            start_date=dates[start_idx],
            end_date=dates[min(end_idx, len(dates) - 1)],
            state=state,
            mean_d=mean_d,
            pair_count=end_idx - start_idx + 1,
            description_ru=desc_ru,
        )
        phases.append(phase)
    
    return phases
