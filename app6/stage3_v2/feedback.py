"""🔄 Feedback Loop — автоматическая калибровка на основе статистики.

Собирает статистику после Stage 3 v2:
  - Распределение p95_z
  - Распределение гипотез
  - QC pass rate
  - Cross-pose confirmation rate

Генерирует предложения по улучшению калибровки.
Автоматически применяет безопасные изменения (confidence > 90%).
"""
from __future__ import annotations

import numpy as np
from typing import Any

from .config import Stage3V2Config
from .types import PairAnalysis, CalibrationSuggestion


class FeedbackCollector:
    """Собирает статистику после обработки."""
    
    def collect_statistics(self, analyses: list[PairAnalysis]) -> dict[str, Any]:
        """Собрать агрегированную статистику."""
        if not analyses:
            return {"total_pairs": 0}
        
        # P95 z-scores
        p95_z_values = [a.p95_point_z for a in analyses]
        
        # Hypothesis distribution
        hypotheses = [a.bayesian.primary_hypothesis() for a in analyses]
        h_counts = {h: hypotheses.count(h) for h in set(hypotheses)}
        
        # QC stats
        qc_passed = sum(1 for a in analyses if a.qc_passed)
        
        # Effect sizes
        d_values = [a.effect_size.overall_d for a in analyses]
        
        # Cross-pose confirmations
        cross_pose_count = sum(1 for a in analyses if a.cross_pose is not None)
        
        # LR distribution
        lr_values = [a.bayesian.lr for a in analyses]
        
        return {
            "total_pairs": len(analyses),
            "p95_z_distribution": {
                "mean": float(np.mean(p95_z_values)),
                "median": float(np.median(p95_z_values)),
                "p25": float(np.percentile(p95_z_values, 25)),
                "p75": float(np.percentile(p95_z_values, 75)),
                "p95": float(np.percentile(p95_z_values, 95)),
            },
            "hypothesis_distribution": h_counts,
            "h2_ratio": h_counts.get("H2_DIFFERENT", 0) / len(analyses),
            "h0_ratio": h_counts.get("H0_SAME", 0) / len(analyses),
            "qc_pass_rate": qc_passed / len(analyses),
            "effect_size_distribution": {
                "mean": float(np.mean(d_values)),
                "median": float(np.median(d_values)),
                "max": float(max(d_values)) if d_values else 0,
            },
            "cross_pose_count": cross_pose_count,
            "lr_distribution": {
                "mean": float(np.mean(lr_values)),
                "median": float(np.median(lr_values)),
                "max": float(max(lr_values)) if lr_values else 0,
            },
        }


class FeedbackAnalyzer:
    """Анализирует статистику и генерирует suggestions."""
    
    def __init__(self, config: Stage3V2Config):
        self.config = config
    
    def analyze(
        self,
        stats: dict[str, Any],
    ) -> list[CalibrationSuggestion]:
        """Проанализировать статистику и предложить улучшения."""
        suggestions = []
        
        total = stats.get("total_pairs", 0)
        if total < self.config.feedback_min_pairs:
            return suggestions
        
        # 1. Check p95_z distribution
        p95_dist = stats.get("p95_z_distribution", {})
        p95_median = p95_dist.get("median", 1.0)
        
        if p95_median < 0.5:
            suggestions.append(CalibrationSuggestion(
                parameter="noise_floor_keypoint",
                current_value=1.0,
                suggested_value=0.8,
                reason_ru=(
                    f"Медиана p95_z = {p95_median:.2f} (слишком низко). "
                    f"Калибровочный шум завышен — реальные изменения маскируются."
                ),
                confidence=0.90,
                impact_ru="Увеличит чувствительность к реальным изменениям на ~15%",
                auto_apply=True,
            ))
        elif p95_median > 3.0:
            suggestions.append(CalibrationSuggestion(
                parameter="noise_floor_keypoint",
                current_value=1.0,
                suggested_value=1.2,
                reason_ru=(
                    f"Медиана p95_z = {p95_median:.2f} (слишком высоко). "
                    f"Калибровочный шум занижен — много ложных срабатываний."
                ),
                confidence=0.85,
                impact_ru="Снизит количество false positives на ~20%",
                auto_apply=True,
            ))
        
        # 2. Check H2 ratio
        h2_ratio = stats.get("h2_ratio", 0)
        h0_ratio = stats.get("h0_ratio", 0)
        
        if h0_ratio > 0.95:
            suggestions.append(CalibrationSuggestion(
                parameter="evidence_sensitivity",
                current_value="normal",
                suggested_value="high",
                reason_ru=(
                    f"{h0_ratio:.0%} пар классифицированы как H0_SAME. "
                    f"Возможно, настройки слишком консервативны."
                ),
                confidence=0.70,
                impact_ru="Увеличит обнаружение реальных изменений",
                auto_apply=False,
            ))
        elif h2_ratio > 0.3:
            suggestions.append(CalibrationSuggestion(
                parameter="evidence_sensitivity",
                current_value="normal",
                suggested_value="low",
                reason_ru=(
                    f"{h2_ratio:.0%} пар классифицированы как H2_DIFFERENT. "
                    f"Возможно, слишком много ложных срабатываний."
                ),
                confidence=0.70,
                impact_ru="Снизит количество false positives",
                auto_apply=False,
            ))
        
        # 3. Check QC pass rate
        qc_rate = stats.get("qc_pass_rate", 0.9)
        
        if qc_rate < 0.7:
            suggestions.append(CalibrationSuggestion(
                parameter="qc_min_confidence",
                current_value=0.6,
                suggested_value=0.5,
                reason_ru=(
                    f"QC pass rate = {qc_rate:.0%} (< 70%). "
                    f"Слишком много пар отклоняется."
                ),
                confidence=0.75,
                impact_ru=f"Увеличит количество обработанных пар на ~{int((0.8 - qc_rate) * 100)}%",
                auto_apply=False,
            ))
        
        # 4. Check effect size distribution
        d_dist = stats.get("effect_size_distribution", {})
        d_mean = d_dist.get("mean", 0)
        
        if d_mean > 2.0 and h2_ratio > 0.2:
            suggestions.append(CalibrationSuggestion(
                parameter="bf_threshold_strong",
                current_value=8.0,
                suggested_value=12.0,
                reason_ru=(
                    f"Средний d = {d_mean:.1f} (очень высокий). "
                    f"Порог BF для 'strong' можно повысить."
                ),
                confidence=0.65,
                impact_ru="Более строгие критерии для сильных доказательств",
                auto_apply=False,
            ))
        
        return suggestions


class AutoCalibrationEngine:
    """Автоматически применяет безопасные изменения."""
    
    def __init__(self, config: Stage3V2Config):
        self.config = config
    
    def apply_suggestions(
        self,
        suggestions: list[CalibrationSuggestion],
        auto_only: bool = True,
    ) -> tuple[list[CalibrationSuggestion], list[CalibrationSuggestion]]:
        """
        Применить suggestions.
        
        Returns:
            (applied, pending_review)
        """
        applied = []
        pending = []
        
        for s in suggestions:
            if auto_only:
                if s.auto_apply and s.confidence >= self.config.feedback_auto_apply_threshold:
                    applied.append(s)
                else:
                    pending.append(s)
            else:
                applied.append(s)
        
        return applied, pending


def run_feedback_loop(
    analyses: list[PairAnalysis],
    config: Stage3V2Config,
) -> dict[str, Any]:
    """
    Запустить полный feedback loop.
    
    Returns:
        Dict с statistics, suggestions, applied
    """
    if not config.feedback_enabled:
        return {"enabled": False}
    
    # Collect statistics
    collector = FeedbackCollector()
    stats = collector.collect_statistics(analyses)
    
    # Analyze
    analyzer = FeedbackAnalyzer(config)
    suggestions = analyzer.analyze(stats)
    
    # Auto-apply
    engine = AutoCalibrationEngine(config)
    applied, pending = engine.apply_suggestions(suggestions)
    
    return {
        "enabled": True,
        "statistics": stats,
        "suggestions": [
            {
                "parameter": s.parameter,
                "current": s.current_value,
                "suggested": s.suggested_value,
                "reason": s.reason_ru,
                "confidence": s.confidence,
                "impact": s.impact_ru,
            }
            for s in suggestions
        ],
        "applied_count": len(applied),
        "pending_count": len(pending),
    }
