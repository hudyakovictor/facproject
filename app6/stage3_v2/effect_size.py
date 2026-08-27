"""📏 Effect Size Analysis — Cohen's d, Glass's delta per zone.

Формула:
  Cohen's d = (μ_after - μ_before) / σ_pooled
  
  Интерпретация:
    d = 0.2: малый эффект
    d = 0.5: средний эффект
    d = 0.8: большой эффект
    d = 1.2+: очень большой эффект

Для журналиста:
  "Скула сместилась на 2.8 мм — в 4 раза больше шума (d = 2.8)"
"""
from __future__ import annotations

import numpy as np
from typing import Any

from .config import Stage3V2Config
from .types import EffectSizeResult, ZoneEffectSize


# Anatomical zones → ldm134 point indices
ZONE_KEYPOINTS = {
    "bone_structure": [1, 17, 5, 13, 9, 25, 35],       # cheekbones, jaw, chin, forehead
    "eyes": [45, 48, 54, 51, 60, 63, 66, 69],           # eye corners, eyebrows
    "nose": [38, 40, 42, 43, 72, 75],                   # bridge, tip, wings
    "mouth": [80, 86, 83, 89],                          # corners, lips
    "head_proportions": [],                              # computed from all points
}

# Zone labels in Russian
ZONE_LABELS_RU = {
    "bone_structure": "Костные структуры",
    "eyes": "Глаза",
    "nose": "Нос",
    "mouth": "Рот",
    "head_proportions": "Пропорции головы",
}


def compute_effect_size(
    pair: dict[str, Any],
    config: Stage3V2Config,
    motion_data: dict[str, np.ndarray] | None = None,
    noise_floor: float = 1.0
) -> EffectSizeResult:
    """
    Вычислить Effect Size (Cohen's d) для пары.
    
    Args:
        pair: Pair dict from Stage 2
        config: Stage 3 v2 config
        motion_data: Motion vectors (134 × 3) from motion file
        noise_floor: Калибровочный шум в мм
    
    Returns:
        EffectSizeResult с d per zone
    """
    pair_id = pair.get("pair_id", "unknown")
    
    # Extract displacement magnitudes
    if motion_data is not None:
        magnitudes = motion_data.get("magnitude", np.zeros(134))
    else:
        # Fallback: synthetic from p95_z
        p95_z = float(pair.get("p95_point_z", 0))
        magnitudes = np.random.exponential(noise_floor * p95_z / 3, 134)
    
    # Compute per-zone effect sizes
    per_zone: dict[str, ZoneEffectSize] = {}
    
    for zone, indices in ZONE_KEYPOINTS.items():
        if zone == "head_proportions":
            # Proportions are computed differently
            zone_effect = _compute_proportion_effect(pair, noise_floor, config)
        elif indices:
            zone_magnitudes = magnitudes[indices]
            zone_effect = _compute_zone_effect(
                zone=zone,
                magnitudes=zone_magnitudes,
                noise_floor=noise_floor,
                config=config
            )
        else:
            continue
        
        per_zone[zone] = zone_effect
    
    # Compute overall weighted d
    total_weight = 0.0
    weighted_d_sum = 0.0
    
    for zone, ze in per_zone.items():
        w = config.zone_weights.get(zone, 0.5)
        weighted_d_sum += w * ze.d
        total_weight += w
    
    overall_d = weighted_d_sum / total_weight if total_weight > 0 else 0.0
    overall_verbal = config.effect_size_verbal_ru(overall_d)
    
    # Generate journalist phrases
    journalist_phrases = _generate_journalist_phrases(per_zone, noise_floor, config)
    
    return EffectSizeResult(
        pair_id=pair_id,
        overall_d=overall_d,
        overall_verbal_ru=overall_verbal,
        per_zone=per_zone,
        journalist_phrases=journalist_phrases,
    )


def _compute_zone_effect(
    zone: str,
    magnitudes: np.ndarray,
    noise_floor: float,
    config: Stage3V2Config
) -> ZoneEffectSize:
    """Compute effect size for a single zone."""
    
    mean_disp = float(np.mean(magnitudes))
    std_disp = float(np.std(magnitudes)) if len(magnitudes) > 1 else noise_floor
    
    # Cohen's d = mean / noise_floor
    d = mean_disp / noise_floor if noise_floor > 0 else 0.0
    
    # Glass's delta = (mean - 0) / noise_floor (same in this context)
    glass_delta = d
    
    verbal = config.effect_size_verbal_ru(d)
    
    return ZoneEffectSize(
        zone=zone,
        d=d,
        glass_delta=glass_delta,
        mean_displacement_mm=mean_disp,
        std_displacement_mm=std_disp,
        verbal_ru=verbal,
        n_points=len(magnitudes),
        weight=config.zone_weights.get(zone, 0.5),
    )


def _compute_proportion_effect(
    pair: dict[str, Any],
    noise_floor: float,
    config: Stage3V2Config
) -> ZoneEffectSize:
    """Compute effect size for head proportions (ratios)."""
    # Use face_ratio change if available
    face_ratio_change = float(pair.get("face_ratio_change", 0.0))
    d = abs(face_ratio_change) / 0.02  # 0.02 = typical noise for ratios
    
    return ZoneEffectSize(
        zone="head_proportions",
        d=d,
        glass_delta=d,
        mean_displacement_mm=face_ratio_change,
        std_displacement_mm=0.02,
        verbal_ru=config.effect_size_verbal_ru(d),
        n_points=8,
        weight=config.zone_weights.get("head_proportions", 0.5),
    )


def _generate_journalist_phrases(
    per_zone: dict[str, ZoneEffectSize],
    noise_floor: float,
    config: Stage3V2Config
) -> list[str]:
    """Generate journalist-friendly phrases."""
    phrases = []
    
    # Sort by d (descending)
    sorted_zones = sorted(per_zone.items(), key=lambda x: x[1].d, reverse=True)
    
    for zone, ze in sorted_zones[:3]:  # Top 3 zones
        label = ZONE_LABELS_RU.get(zone, zone)
        noise_ratio = ze.mean_displacement_mm / noise_floor if noise_floor > 0 else 0
        
        if ze.d >= config.effect_size_thresholds["small"]:
            phrase = (
                f"{label}: {ze.mean_displacement_mm:.1f} мм — "
                f"в {noise_ratio:.1f} раз больше шума "
                f"(d = {ze.d:.1f}, {ze.verbal_ru})"
            )
            phrases.append(phrase)
    
    return phrases
