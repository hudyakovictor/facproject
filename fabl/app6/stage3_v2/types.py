"""📊 Stage 3 v2 Types — все структуры данных для результатов анализа.

Содержит:
  - BayesianResult (posterior, LR, BF)
  - EffectSizeResult (Cohen's d per zone)
  - BootstrapResult (CI per metric)
  - ChangePointResult (temporal events)
  - CrossPoseResult (multi-pose confirmation)
  - ZoneAnalysisResult (zone-level aggregation)
  - NarrativeResult (timeline, arc, text)
  - PairAnalysis (полный анализ одной пары)
  - FullReport (финальный отчёт)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import numpy as np


# ═══════════════════════════════════════════
# BAYESIAN / LR RESULT
# ═══════════════════════════════════════════

@dataclass
class BayesianResult:
    """Результат Bayesian анализа для одной пары."""
    
    pair_id: str
    
    # Prior (может быть adaptive)
    prior: dict[str, float]
    
    # Posterior (после всех evidence)
    posterior: dict[str, float]
    
    # Likelihood Ratio (для журналиста)
    lr: float                    # Combined LR
    lr_per_evidence: dict[str, float]  # LR per module
    lr_verbal_ru: str            # "сильные доказательства"
    
    # Bayes Factor
    bayes_factor: float
    bf_level: str                # "strong", "moderate", etc.
    
    # Update history
    update_history: list[dict[str, Any]] = field(default_factory=list)
    
    # Calibrated posterior (isotonic regression)
    calibrated_posterior: Optional[dict[str, float]] = None
    
    def primary_hypothesis(self) -> str:
        """Гипотеза с максимальной posterior probability."""
        return max(self.posterior, key=self.posterior.get)
    
    def confidence(self) -> float:
        """Уверенность = max posterior probability."""
        return max(self.posterior.values())
    
    def entropy(self) -> float:
        """Shannon entropy posterior (мера неопределённости)."""
        h = 0.0
        for p in self.posterior.values():
            if p > 0:
                h -= p * np.log2(p)
        return h


# ═══════════════════════════════════════════
# EFFECT SIZE RESULT
# ═══════════════════════════════════════════

@dataclass
class EffectSizeResult:
    """Effect Size (Cohen's d) для одной пары."""
    
    pair_id: str
    
    # Overall weighted effect size
    overall_d: float
    overall_verbal_ru: str  # "большой", "средний", etc.
    
    # Per zone
    per_zone: dict[str, ZoneEffectSize]
    
    # Journalist format
    journalist_phrases: list[str] = field(default_factory=list)


@dataclass
class ZoneEffectSize:
    """Effect Size для одной зоны."""
    
    zone: str
    d: float                    # Cohen's d
    glass_delta: float          # Glass's delta
    mean_displacement_mm: float # Среднее смещение в мм
    std_displacement_mm: float  # Стандартное отклонение
    verbal_ru: str              # "большой эффект"
    n_points: int               # Количество точек в зоне
    weight: float               # Weight из config


# ═══════════════════════════════════════════
# BOOTSTRAP RESULT
# ═══════════════════════════════════════════

@dataclass
class BootstrapResult:
    """Bootstrap Confidence Intervals для одной пары."""
    
    pair_id: str
    
    # Per zone CI
    per_zone: dict[str, ZoneBootstrap]
    
    # Overall
    overall_d: float
    overall_ci_lower: float
    overall_ci_upper: float
    overall_significant: bool  # CI не включает 0


@dataclass
class ZoneBootstrap:
    """Bootstrap CI для одной зоны."""
    
    zone: str
    d: float
    ci_lower: float
    ci_upper: float
    significant: bool  # CI не включает 0
    p_value: float     # p(d > threshold)


# ═══════════════════════════════════════════
# CHANGE POINT RESULT
# ═══════════════════════════════════════════

@dataclass
class ChangePointResult:
    """Результат Change Point Detection."""
    
    # Detected change points
    change_points: list[TemporalChangePoint]
    
    # Phases (between change points)
    phases: list[TemporalPhase]
    
    # Overall trend
    overall_trend: str  # "increasing", "decreasing", "stable", "complex"


@dataclass
class TemporalChangePoint:
    """Один change point."""
    
    date: datetime
    pair_id: str
    confidence: float  # 0-1
    before_mean_d: float
    after_mean_d: float
    direction: str  # "increase", "decrease"
    zone: str  # Какая зона затронута


@dataclass
class TemporalPhase:
    """Фаза между change points."""
    
    start_date: datetime
    end_date: datetime
    state: str  # "stable", "changing", "stabilizing"
    mean_d: float
    pair_count: int
    description_ru: str  # "Стабильность", "Нарастание изменений"


# ═══════════════════════════════════════════
# CROSS-POSE RESULT
# ═══════════════════════════════════════════

@dataclass
class CrossPoseResult:
    """Cross-pose confirmation для одного события."""
    
    primary_pair_id: str
    
    # Confirming poses
    confirming_poses: list[PoseConfirmation]
    n_confirming: int
    consistency: float  # 0-1
    
    # Combined evidence
    combined_lr: float
    combined_bf: float
    
    # Journalist note
    journalist_note_ru: str


@dataclass
class PoseConfirmation:
    """Подтверждение из одного ракурса."""
    
    pair_id: str
    pose_bin: str
    yaw_deg: float
    days_offset: int
    d: float
    lr: float


# ═══════════════════════════════════════════
# ZONE ANALYSIS RESULT
# ═══════════════════════════════════════════

@dataclass
class ZoneAnalysisResult:
    """Агрегированный анализ по зонам."""
    
    # Per zone summary
    per_zone: dict[str, ZoneSummary]
    
    # Overall
    most_affected_zone: str
    overall_h2_rate: float  # Доля H2 пар
    overall_mean_d: float


@dataclass
class ZoneSummary:
    """Сводка по одной зоне."""
    
    zone: str
    zone_label_ru: str  # "Костные структуры"
    n_pairs: int
    h2_count: int
    h2_rate: float
    mean_d: float
    mean_lr: float
    top_points: list[str]  # Самые затронутые точки
    reliability_note_ru: str  # "Высокая надёжность"


# ═══════════════════════════════════════════
# NARRATIVE RESULT
# ═══════════════════════════════════════════

@dataclass
class NarrativeResult:
    """Результат Narrative Engine."""
    
    # Headline
    headline_ru: str
    
    # Lead (первый абзац)
    lead_ru: str
    
    # Sections
    exposition_ru: str
    rising_action_ru: str
    climax_ru: str
    falling_action_ru: str
    resolution_ru: str
    
    # Full text
    full_text_ru: str
    word_count: int
    
    # Metadata
    key_findings: list[str]
    disclaimers_ru: list[str]


# ═══════════════════════════════════════════
# PAIR ANALYSIS (полный анализ одной пары)
# ═══════════════════════════════════════════

@dataclass
class PairAnalysis:
    """Полный анализ одной пары."""
    
    pair_id: str
    photo_a: str
    photo_b: str
    date_a: Optional[datetime]
    date_b: Optional[datetime]
    pose_bin: str
    
    # Raw metrics from Stage 2
    p95_point_z: float
    coherent_motion_fraction: float
    significant_point_fraction: float
    mesh_rmse: float
    descriptor_p95_z: float
    
    # Analysis results
    bayesian: BayesianResult
    effect_size: EffectSizeResult
    bootstrap: BootstrapResult
    cross_pose: Optional[CrossPoseResult]
    
    # QC
    qc_passed: bool
    quality_score: float
    
    # Fast Pass (if used)
    fast_pass_hypothesis: Optional[str] = None
    fast_pass_agreed: Optional[bool] = None


# ═══════════════════════════════════════════
# FEEDBACK SUGGESTION
# ═══════════════════════════════════════════

@dataclass
class CalibrationSuggestion:
    """Предложение по улучшению калибровки."""
    
    parameter: str
    current_value: Any
    suggested_value: Any
    reason_ru: str
    confidence: float  # 0-1
    impact_ru: str
    auto_apply: bool  # Можно ли применить автоматически


# ═══════════════════════════════════════════
# FULL REPORT (финальный отчёт)
# ═══════════════════════════════════════════

@dataclass
class FullReport:
    """Полный отчёт Stage 3 v2."""
    
    # Metadata
    schema_version: str
    created_at: datetime
    stage2_root: str
    
    # Summary statistics
    total_pairs: int
    pairs_analyzed: int
    pairs_with_changes: int
    
    # Analysis results
    pair_analyses: list[PairAnalysis]
    zone_analysis: ZoneAnalysisResult
    change_points: ChangePointResult
    
    # Narrative
    narrative: NarrativeResult
    
    # Feedback
    suggestions: list[CalibrationSuggestion]
    
    # Performance
    processing_time_seconds: float
    memory_peak_mb: float
    
    def to_dict(self) -> dict[str, Any]:
        """Сериализовать отчёт."""
        import dataclasses
        
        def _serialize(obj):
            if dataclasses.is_dataclass(obj):
                return {k: _serialize(v) for k, v in dataclasses.asdict(obj).items()}
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, (list, tuple)):
                return [_serialize(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            return obj
        
        return _serialize(self)
