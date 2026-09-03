"""📜 Legacy Hypothesis Integration — интеграция старых данных.

Legacy данные считались по неверному alignment → систематическое смещение.
Калибруются группами по ракурсам (pose bins).

Подход:
  Legacy posterior → correction → weak likelihood (weight=0.3)
  → интегрируется в Bayesian updating
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .config import Stage3V2Config


class LegacyIntegrator:
    """Интегратор legacy hypothesis данных."""
    
    def __init__(self, config: Stage3V2Config, legacy_path: Optional[Path] = None):
        self.config = config
        self.legacy_path = legacy_path
        self._records: dict[str, dict] = {}
        
        if legacy_path and legacy_path.exists():
            self._load_legacy_data()
    
    def _load_legacy_data(self):
        """Загрузить legacy hypothesis ledger."""
        if not self.legacy_path:
            return
        
        # Try JSONL format
        if self.legacy_path.suffix == '.jsonl':
            with self.legacy_path.open('r', encoding='utf-8') as f:
                for line in f:
                    record = json.loads(line.strip())
                    photo_id = record.get('photo_id', '')
                    if photo_id:
                        self._records[photo_id] = record
    
    def get_legacy_record(self, photo_id: str) -> Optional[dict]:
        """Получить legacy record для photo_id."""
        return self._records.get(photo_id)
    
    def compute_correction_factor(
        self,
        legacy_record: dict,
        pose_bin: str
    ) -> dict[str, float]:
        """
        Вычислить correction factors для legacy posterior.
        
        Correction зависит от:
        - pose_distance
        - match_score
        - pose_bin
        """
        correction = {
            "H0_SAME": 1.0,
            "H1_SYNTHETIC": 1.0,
            "H2_DIFFERENT": 1.0,
            "H_UNCERTAIN": 1.0,
        }
        
        cal_pair = legacy_record.get("calibration_pair", {})
        pose_dist = cal_pair.get("pose_distance_deg", 0)
        match_score = cal_pair.get("match_score", 1.0)
        
        # Pose distance correction
        if pose_dist > 15:
            correction["H2_DIFFERENT"] *= 0.7
            correction["H_UNCERTAIN"] *= 1.3
        elif pose_dist > 10:
            correction["H2_DIFFERENT"] *= 0.8
        
        # Match score correction
        if match_score < 0.6:
            correction["H2_DIFFERENT"] *= 0.6
            correction["H0_SAME"] *= 0.8
            correction["H_UNCERTAIN"] *= 1.5
        elif match_score < 0.7:
            correction["H2_DIFFERENT"] *= 0.7
        
        # Pose bin correction
        if self.config.legacy_correction_by_pose:
            pose_correction = {
                "profile_left": 0.9,
                "profile_right": 0.9,
                "left_50": 0.92,
                "right_50": 0.92,
                "left_40": 0.95,
                "right_40": 0.95,
            }
            factor = pose_correction.get(pose_bin, 1.0)
            correction["H2_DIFFERENT"] *= factor
        
        # Reliability score
        reliability = min(1.0, match_score * (1 - pose_dist / 90))
        correction["reliability"] = reliability
        
        return correction
    
    def compute_legacy_likelihood(
        self,
        legacy_record: dict,
        pose_bin: str
    ) -> dict[str, float]:
        """
        Конвертировать legacy posterior в weak likelihood.
        
        Legacy = 1 "virtual evidence" с weight = legacy_weight × reliability
        """
        # Get legacy posterior
        posterior = legacy_record.get("posterior", {})
        if not posterior:
            return {
                "H0_SAME": 0.25,
                "H1_SYNTHETIC": 0.25,
                "H2_DIFFERENT": 0.25,
                "H_UNCERTAIN": 0.25,
            }
        
        # Apply correction
        correction = self.compute_correction_factor(legacy_record, pose_bin)
        
        corrected = {}
        for h in ["H0_SAME", "H1_SYNTHETIC", "H2_DIFFERENT", "H_UNCERTAIN"]:
            corrected[h] = posterior.get(h, 0.25) * correction.get(h, 1.0)
        
        # Normalize
        total = sum(corrected.values())
        if total > 0:
            corrected = {k: v / total for k, v in corrected.items()}
        
        # Convert to weak likelihood
        reliability = correction.get("reliability", 0.5)
        legacy_weight = self.config.legacy_weight * reliability
        
        likelihood = {}
        for h in corrected:
            # Soft likelihood: raise to power < 1
            likelihood[h] = corrected[h] ** legacy_weight
        
        return likelihood
    
    def get_correction_summary(self, photo_id: str, pose_bin: str) -> Optional[dict]:
        """Получить summary коррекции для UI."""
        record = self.get_legacy_record(photo_id)
        if not record:
            return None
        
        correction = self.compute_correction_factor(record, pose_bin)
        
        return {
            "photo_id": photo_id,
            "legacy_primary": record.get("primary_hypothesis", "unknown"),
            "legacy_posterior": record.get("posterior", {}),
            "correction_factors": correction,
            "reliability": correction.get("reliability", 0),
            "limitations": record.get("limitations", []),
        }


def integrate_legacy_into_pair(
    pair: dict[str, Any],
    integrator: LegacyIntegrator,
    current_likelihoods: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """
    Интегрировать legacy данные в evidence для пары.
    
    Args:
        pair: Pair dict
        integrator: LegacyIntegrator instance
        current_likelihoods: Текущие likelihoods по evidence modules
    
    Returns:
        Updated likelihoods с legacy evidence
    """
    # Try both photos
    for photo_key in ["photo_a", "photo_b"]:
        photo_id = pair.get(photo_key, "")
        pose_bin = pair.get("pose_bin", "frontal")
        
        record = integrator.get_legacy_record(photo_id)
        if not record:
            continue
        
        # Compute legacy likelihood
        legacy_lik = integrator.compute_legacy_likelihood(record, pose_bin)
        
        # Add to evidence
        current_likelihoods["legacy"] = legacy_lik
        
        # Only use first match
        break
    
    return current_likelihoods
