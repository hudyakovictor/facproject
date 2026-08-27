"""🔄 Cross-Pose Confirmation — подтверждение изменений в нескольких ракурсах.

Если H2 подтверждается в N ракурсах:
  posterior_combined ∝ ∏ P(E_pose_i | H2) × prior

Это значительно увеличивает Bayes Factor.

Для журналиста:
  "Изменение подтверждено в 3 ракурсах с разных дат"
"""
from __future__ import annotations

import numpy as np
from datetime import datetime, timedelta
from typing import Any

from .config import Stage3V2Config
from .types import CrossPoseResult, PoseConfirmation, PairAnalysis


class CrossPoseAnalyzer:
    """Анализатор cross-pose confirmation."""
    
    def __init__(self, config: Stage3V2Config):
        self.config = config
    
    def find_confirmations(
        self,
        primary: PairAnalysis,
        all_analyses: list[PairAnalysis],
    ) -> CrossPoseResult | None:
        """
        Найти подтверждающие пары для primary pair.
        
        Args:
            primary: Основная пара
            all_analyses: Все проанализированные пары
        
        Returns:
            CrossPoseResult если найдены подтверждения, иначе None
        """
        if not primary.date_b:
            return None
        
        # Time window
        window = timedelta(days=self.config.cross_pose_time_window_days)
        
        # Find confirming pairs
        confirmations: list[PoseConfirmation] = []
        
        for other in all_analyses:
            if other.pair_id == primary.pair_id:
                continue
            
            if not other.date_b:
                continue
            
            # Check time window
            time_diff = abs((other.date_b - primary.date_b).days)
            if time_diff > self.config.cross_pose_time_window_days:
                continue
            
            # Check if different pose bin
            if other.pose_bin == primary.pose_bin:
                continue
            
            # Check if shows similar change
            if other.bayesian.primary_hypothesis() != "H2_DIFFERENT":
                continue
            
            # Must have reasonable effect size
            if other.effect_size.overall_d < 0.5:
                continue
            
            # Extract yaw from pose_bin
            yaw = self._pose_bin_to_yaw(other.pose_bin)
            
            confirmations.append(PoseConfirmation(
                pair_id=other.pair_id,
                pose_bin=other.pose_bin,
                yaw_deg=yaw,
                days_offset=time_diff,
                d=other.effect_size.overall_d,
                lr=other.bayesian.lr,
            ))
        
        if not confirmations:
            return None
        
        # Compute consistency
        d_values = [c.d for c in confirmations]
        primary_d = primary.effect_size.overall_d
        all_d = [primary_d] + d_values
        
        mean_d = np.mean(all_d)
        std_d = np.std(all_d) if len(all_d) > 1 else 0
        consistency = 1.0 - (std_d / mean_d) if mean_d > 0 else 0.0
        consistency = max(0.0, min(1.0, consistency))
        
        # Combined LR
        all_lrs = [primary.bayesian.lr] + [c.lr for c in confirmations]
        combined_lr = self._combine_lrs(all_lrs)
        
        # Combined BF
        combined_bf = combined_lr  # Simplified
        
        # Journalist note
        n = len(confirmations) + 1
        journalist_note = self._generate_note(n, consistency, confirmations)
        
        return CrossPoseResult(
            primary_pair_id=primary.pair_id,
            confirming_poses=confirmations,
            n_confirming=len(confirmations),
            consistency=consistency,
            combined_lr=combined_lr,
            combined_bf=combined_bf,
            journalist_note_ru=journalist_note,
        )
    
    def _pose_bin_to_yaw(self, pose_bin: str) -> float:
        """Convert pose_bin name to approximate yaw angle."""
        mapping = {
            "frontal": 0.0,
            "left_10": -10.0,
            "right_10": 10.0,
            "left_20": -20.0,
            "right_20": 20.0,
            "left_30": -30.0,
            "right_30": 30.0,
            "left_40": -40.0,
            "right_40": 40.0,
            "left_50": -50.0,
            "right_50": 50.0,
            "profile_left": -70.0,
            "profile_right": 70.0,
        }
        return mapping.get(pose_bin, 0.0)
    
    def _combine_lrs(self, lrs: list[float]) -> float:
        """Combine LRs with dependence correction."""
        if not lrs:
            return 1.0
        
        # Geometric mean with dependence penalty
        log_lrs = [np.log(max(lr, 1e-6)) for lr in lrs]
        
        # Dependence: not fully independent poses
        n = len(lrs)
        dependence_factor = 1.0 / (1.0 + 0.15 * (n - 1))
        
        combined_log = sum(log_lrs) * dependence_factor
        return np.exp(combined_log)
    
    def _generate_note(
        self,
        n_poses: int,
        consistency: float,
        confirmations: list[PoseConfirmation]
    ) -> str:
        """Generate journalist note in Russian."""
        poses_text = f"{n_poses} различных ракурсах"
        
        if consistency > 0.8:
            strength = "высокой степени"
        elif consistency > 0.5:
            strength = "умеренной степени"
        else:
            strength = "разной степени"
        
        pose_names = ", ".join(set(c.pose_bin for c in confirmations[:3]))
        
        return (
            f"Изменение подтверждено в {poses_text} с {strength} согласованностью. "
            f"Дополнительные ракурсы: {pose_names}. "
            f"Это снижает вероятность артефакта освещения или позы."
        )


def apply_cross_pose_confirmation(
    analyses: list[PairAnalysis],
    config: Stage3V2Config
) -> list[PairAnalysis]:
    """
    Apply cross-pose confirmation to all analyses.
    
    Updates each H2 pair with cross-pose data if available.
    """
    analyzer = CrossPoseAnalyzer(config)
    
    for analysis in analyses:
        if analysis.bayesian.primary_hypothesis() != "H2_DIFFERENT":
            continue
        
        result = analyzer.find_confirmations(analysis, analyses)
        
        if result and result.n_confirming >= config.min_poses_for_confirmation - 1:
            analysis.cross_pose = result
    
    return analyses
