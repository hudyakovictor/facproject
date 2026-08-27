"""⚙️ Stage 3 v2 Configuration — все параметры аналитического движка.

Содержит:
  - Пути к Stage 2 output
  - Bayesian priors (adaptive)
  - LR thresholds (ENFSI-adapted)
  - Zone reliability weights
  - Effect Size parameters
  - Change Point Detection settings
  - Bootstrap CI settings
  - Narrative Engine settings
  - Legacy integration settings
  - Feedback loop settings
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Stage3V2Config:
    """Конфигурация Stage 3 v2."""
    
    # ═══════════════════════════════════════════
    # PATHS (обязательные)
    # ═══════════════════════════════════════════
    stage2_root: Path          # Путь к Stage 2 output
    output_dir: Path           # Путь для Stage 3 v2 output
    overwrite: bool = False    # Перезаписать если существует
    
    # ═══════════════════════════════════════════
    # BAYESIAN PRIORS (base)
    # ═══════════════════════════════════════════
    prior_h0_same: float = 0.75       # P(H0: тот же человек)
    prior_h1_synthetic: float = 0.02  # P(H1: синтетика)
    prior_h2_different: float = 0.08  # P(H2: изменение)
    prior_h_uncertain: float = 0.15   # P(HU: неопределённо)
    
    # ═══════════════════════════════════════════
    # LIKELIHOOD MODEL
    # ═══════════════════════════════════════════
    likelihood_model: str = "gamma"   # "gamma" | "gaussian" | "mixed"
    gamma_shape: float = 3.0          # Shape parameter
    gamma_scale: float = 1.5          # Scale parameter
    
    # ═══════════════════════════════════════════
    # EVIDENCE DEPENDENCE (Copula adjustment)
    # ═══════════════════════════════════════════
    dependence_adjustment: str = "copula"  # "copula" | "weights" | "none"
    # Корреляции между evidence modules (из симуляций)
    evidence_correlations: dict[str, dict[str, float]] = field(default_factory=lambda: {
        "keypoint": {"mesh": 0.65, "descriptor": 0.45, "chronology": 0.20, "corroboration": 0.35},
        "mesh": {"descriptor": 0.55, "chronology": 0.15, "corroboration": 0.30},
        "descriptor": {"chronology": 0.10, "corroboration": 0.25},
        "chronology": {"corroboration": 0.30},
    })
    
    # ═══════════════════════════════════════════
    # BAYES FACTOR THRESHOLDS (ENFSI-adapted)
    # ═══════════════════════════════════════════
    bf_threshold_anecdotal: float = 1.5
    bf_threshold_moderate: float = 3.0
    bf_threshold_strong: float = 8.0
    bf_threshold_very_strong: float = 20.0
    bf_threshold_decisive: float = 50.0
    
    # ═══════════════════════════════════════════
    # ZONE RELIABILITY WEIGHTS
    # ═══════════════════════════════════════════
    zone_weights: dict[str, float] = field(default_factory=lambda: {
        "bone_structure": 1.00,      # Костные структуры (самые надёжные)
        "head_proportions": 0.90,    # Пропорции головы
        "eyes": 0.65,                # Глаза (мимика!)
        "nose": 0.55,                # Нос (кончик подвижен)
        "mouth": 0.25,               # Рот (высокая мимика)
    })
    
    # ═══════════════════════════════════════════
    # EFFECT SIZE (Cohen's d)
    # ═══════════════════════════════════════════
    effect_size_thresholds: dict[str, float] = field(default_factory=lambda: {
        "negligible": 0.2,
        "small": 0.5,
        "medium": 0.8,
        "large": 1.2,
        "very_large": 2.0,
    })
    
    # ═══════════════════════════════════════════
    # BOOTSTRAP CONFIDENCE INTERVALS
    # ═══════════════════════════════════════════
    bootstrap_iterations: int = 1000
    confidence_level: float = 0.95    # 95% CI
    
    # ═══════════════════════════════════════════
    # CHANGE POINT DETECTION
    # ═══════════════════════════════════════════
    change_point_method: str = "bayesian"  # "bayesian" | "cusum" | "pelt"
    change_point_max_count: int = 10
    change_point_min_segment: int = 5  # Минимум пар в сегменте
    
    # ═══════════════════════════════════════════
    # TEMPORAL DECAY (для cross-pair influence)
    # ═══════════════════════════════════════════
    temporal_half_life_days: float = 180.0
    
    # ═══════════════════════════════════════════
    # CROSS-POSE CONFIRMATION
    # ═══════════════════════════════════════════
    min_poses_for_confirmation: int = 3
    cross_pose_time_window_days: int = 30
    
    # ═══════════════════════════════════════════
    # LEGACY INTEGRATION
    # ═══════════════════════════════════════════
    legacy_weight: float = 0.3  # 30% influence от legacy
    legacy_correction_by_pose: bool = True
    
    # ═══════════════════════════════════════════
    # FAST PASS (опционально)
    # ═══════════════════════════════════════════
    fast_pass_enabled: bool = True
    fast_pass_damping: float = 0.6  # Damping factor для Fast→Full bridge
    fast_pass_p95_z_threshold: float = 2.0
    full_pass_p95_z_threshold: float = 3.8
    
    # ═══════════════════════════════════════════
    # FEEDBACK LOOP
    # ═══════════════════════════════════════════
    feedback_enabled: bool = True
    feedback_min_pairs: int = 100    # Минимум пар для suggestions
    feedback_auto_apply_threshold: float = 0.90  # Confidence для auto-apply
    
    # ═══════════════════════════════════════════
    # NARRATIVE ENGINE
    # ═══════════════════════════════════════════
    narrative_language: str = "ru"  # "ru" | "en"
    narrative_tone: str = "journalistic"  # "scientific" | "journalistic" | "popular"
    narrative_audience: str = "investigation_media"
    narrative_max_words: int = 3000
    
    # ═══════════════════════════════════════════
    # LOSS MATRIX (Decision Theory)
    # ═══════════════════════════════════════════
    loss_matrix: dict[str, list[float]] = field(default_factory=lambda: {
        #             H0   H1   H2   HU
        "decide_H0": [0.0, 5.0, 10.0, 3.0],
        "decide_H1": [8.0, 0.0, 8.0,  3.0],
        "decide_H2": [10.0, 5.0, 0.0, 3.0],
        "decide_HU": [3.0, 3.0, 3.0,  0.0],
    })
    
    # ═══════════════════════════════════════════
    # CONFIDENCE CALIBRATION
    # ═══════════════════════════════════════════
    calibration_method: str = "isotonic"  # "isotonic" | "platt" | "temperature"
    
    # ═══════════════════════════════════════════
    # ENTROPY THRESHOLDS (uncertainty)
    # ═══════════════════════════════════════════
    entropy_high_confidence: float = 0.6
    entropy_moderate_confidence: float = 1.0
    entropy_low_confidence: float = 1.4
    
    # ═══════════════════════════════════════════
    # PERFORMANCE
    # ═══════════════════════════════════════════
    max_workers: int = 8
    batch_size: int = 100
    checkpoint_every: int = 50
    
    def __post_init__(self):
        """Валидация конфигурации."""
        # Paths
        stage2 = Path(self.stage2_root).resolve()
        output = Path(self.output_dir).resolve()
        if not stage2.exists():
            raise ValueError(f"stage2_root does not exist: {stage2}")
        if output == stage2 or stage2 in output.parents or output in stage2.parents:
            raise ValueError("output_dir must not equal, contain, or be inside stage2_root")
        
        # Priors must sum to ~1.0
        prior_sum = (self.prior_h0_same + self.prior_h1_synthetic + 
                     self.prior_h2_different + self.prior_h_uncertain)
        if not (0.99 <= prior_sum <= 1.01):
            raise ValueError(f"Priors must sum to 1.0, got {prior_sum:.3f}")
        
        # Zone weights must be positive
        for zone, weight in self.zone_weights.items():
            if weight < 0 or weight > 1:
                raise ValueError(f"Zone weight for {zone} must be in [0, 1], got {weight}")
        
        # BF thresholds must be ordered
        if not (self.bf_threshold_anecdotal < self.bf_threshold_moderate < 
                self.bf_threshold_strong < self.bf_threshold_very_strong < 
                self.bf_threshold_decisive):
            raise ValueError("BF thresholds must be strictly increasing")
    
    @property
    def priors(self) -> dict[str, float]:
        """Возвращает priors как словарь."""
        return {
            "H0_SAME": self.prior_h0_same,
            "H1_SYNTHETIC": self.prior_h1_synthetic,
            "H2_DIFFERENT": self.prior_h2_different,
            "H_UNCERTAIN": self.prior_h_uncertain,
        }
    
    @property
    def hypotheses(self) -> list[str]:
        """Список гипотез в стандартном порядке."""
        return ["H0_SAME", "H1_SYNTHETIC", "H2_DIFFERENT", "H_UNCERTAIN"]
    
    def bf_level(self, bf: float) -> str:
        """Определить уровень Bayes Factor."""
        if bf >= self.bf_threshold_decisive:
            return "decisive"
        elif bf >= self.bf_threshold_very_strong:
            return "very_strong"
        elif bf >= self.bf_threshold_strong:
            return "strong"
        elif bf >= self.bf_threshold_moderate:
            return "moderate"
        elif bf >= self.bf_threshold_anecdotal:
            return "anecdotal"
        else:
            return "none"
    
    def bf_verbal_ru(self, bf: float) -> str:
        """Русская вербальная шкала для LR/BF."""
        level = self.bf_level(bf)
        return {
            "decisive": "очень сильные доказательства",
            "very_strong": "очень сильные доказательства",
            "strong": "сильные доказательства",
            "moderate": "умеренные доказательства",
            "anecdotal": "слабые доказательства",
            "none": "доказательства отсутствуют",
        }[level]
    
    def effect_size_verbal_ru(self, d: float) -> str:
        """Русская вербальная шкала для Effect Size."""
        if abs(d) >= self.effect_size_thresholds["very_large"]:
            return "очень большой"
        elif abs(d) >= self.effect_size_thresholds["large"]:
            return "большой"
        elif abs(d) >= self.effect_size_thresholds["medium"]:
            return "средний"
        elif abs(d) >= self.effect_size_thresholds["small"]:
            return "малый"
        else:
            return "незначительный"
    
    def to_dict(self) -> dict[str, Any]:
        """Сериализовать конфигурацию."""
        import dataclasses
        d = {}
        for f in dataclasses.fields(self):
            val = getattr(self, f.name)
            if isinstance(val, Path):
                val = str(val)
            d[f.name] = val
        return d
