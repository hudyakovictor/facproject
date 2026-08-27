"""🧮 Bayesian Engine — Sequential Bayesian updating + LR conversion.

Архитектура: Bayesian ВНУТРИ, LR СНАРУЖИ.
  - Bayesian updating для вычислений (sequential, multi-evidence)
  - Likelihood Ratio для представления журналисту (ENFSI standard)

Формула:
  Posterior ∝ Likelihood × Prior
  LR = P(data | H2) / P(data | H0)

Evidence modules (в порядке обработки):
  1. Keypoint displacement (самый надёжный)
  2. 3D mesh analysis
  3. Local descriptors (13 families)
  4. Chronology
  5. Corroboration (cross-pose)
"""
from __future__ import annotations

import numpy as np
from typing import Any
from scipy import stats

from .config import Stage3V2Config
from .types import BayesianResult


class BayesianUpdater:
    """Sequential Bayesian updater для одной пары."""
    
    def __init__(self, config: Stage3V2Config, pair_context: dict[str, Any]):
        self.config = config
        self.pair_context = pair_context
        
        # Compute adaptive prior
        self.prior = self._compute_adaptive_prior()
        
        # Current posterior (starts as prior)
        self.posterior = dict(self.prior)
        
        # History of updates
        self.history: list[dict[str, Any]] = []
    
    def _compute_adaptive_prior(self) -> dict[str, float]:
        """Вычислить adaptive prior на основе контекста пары."""
        prior = dict(self.config.priors)
        
        # Модификация 1: Временной интервал
        time_diff_days = self.pair_context.get("days_delta", 30)
        if time_diff_days > 365:
            prior["H0_SAME"] *= 0.85
            prior["H2_DIFFERENT"] *= 1.8
        elif time_diff_days > 180:
            prior["H0_SAME"] *= 0.92
            prior["H2_DIFFERENT"] *= 1.4
        elif time_diff_days < 7:
            prior["H0_SAME"] *= 1.05
            prior["H2_DIFFERENT"] *= 0.6
        
        # Модификация 2: Разница в ракурсе
        pose_distance = self.pair_context.get("pose_distance_deg", 5)
        if pose_distance > 30:
            prior["H_UNCERTAIN"] *= 1.5
            prior["H0_SAME"] *= 0.9
        elif pose_distance < 5:
            prior["H_UNCERTAIN"] *= 0.7
            prior["H0_SAME"] *= 1.05
        
        # Модификация 3: Качество данных
        quality = self.pair_context.get("quality_score", 0.8)
        if quality < 0.5:
            prior["H_UNCERTAIN"] *= 2.0
            prior["H0_SAME"] *= 0.7
        
        # Normalize
        total = sum(prior.values())
        return {k: v / total for k, v in prior.items()}
    
    def update(self, evidence_name: str, likelihood: dict[str, float]) -> dict[str, float]:
        """
        Обновить posterior с новым evidence.
        
        Args:
            evidence_name: Название evidence module
            likelihood: P(evidence | H) для каждой гипотезы
        
        Returns:
            Updated posterior
        """
        new_posterior = {}
        evidence_marginal = 0.0
        
        # Bayes update: posterior ∝ likelihood × prior
        for h in self.config.hypotheses:
            new_posterior[h] = likelihood[h] * self.posterior[h]
            evidence_marginal += new_posterior[h]
        
        # Normalize
        if evidence_marginal > 0:
            for h in new_posterior:
                new_posterior[h] /= evidence_marginal
        else:
            # Fallback: не меняем posterior
            new_posterior = dict(self.posterior)
        
        # Save to history
        self.history.append({
            "evidence": evidence_name,
            "prior": dict(self.posterior),
            "likelihood": likelihood,
            "posterior": new_posterior,
            "evidence_marginal": evidence_marginal,
        })
        
        self.posterior = new_posterior
        return new_posterior
    
    def compute_bayes_factor(self, h1: str = "H2_DIFFERENT", h0: str = "H0_SAME") -> float:
        """
        Вычислить Bayes Factor: BF = posterior_odds / prior_odds
        
        BF > 1: данные поддерживают H1
        BF < 1: данные поддерживают H0
        """
        if not self.history:
            return 1.0
        
        prior_odds = self.history[0]["prior"][h1] / max(self.history[0]["prior"][h0], 1e-10)
        posterior_odds = self.posterior[h1] / max(self.posterior[h0], 1e-10)
        
        if prior_odds < 1e-10:
            return float('inf')
        
        return posterior_odds / prior_odds
    
    def compute_lr(self, evidence_likelihoods: dict[str, dict[str, float]]) -> float:
        """
        Вычислить combined Likelihood Ratio с учётом зависимости evidence.
        
        LR = P(data | H2) / P(data | H0)
        
        С поправкой на зависимость evidence modules (copula adjustment).
        """
        # Compute raw LR per evidence
        lr_per_evidence = {}
        for name, lik in evidence_likelihoods.items():
            lr_per_evidence[name] = lik["H2_DIFFERENT"] / max(lik["H0_SAME"], 1e-10)
        
        # Apply dependence correction
        if self.config.dependence_adjustment == "copula":
            adjusted_lrs = self._copula_adjustment(lr_per_evidence)
        elif self.config.dependence_adjustment == "weights":
            adjusted_lrs = self._weight_adjustment(lr_per_evidence)
        else:
            adjusted_lrs = lr_per_evidence
        
        # Combined LR (product)
        combined_lr = 1.0
        for lr in adjusted_lrs.values():
            combined_lr *= lr
        
        return combined_lr
    
    def _copula_adjustment(self, lr_per_evidence: dict[str, float]) -> dict[str, float]:
        """
        Copula adjustment для учёта зависимости evidence.
        
        Effective weight = 1 / (1 + 0.5 × mean_correlation)
        """
        evidence_names = list(lr_per_evidence.keys())
        n = len(evidence_names)
        
        if n < 2:
            return lr_per_evidence
        
        adjusted = {}
        for i, name in enumerate(evidence_names):
            # Compute mean correlation with other evidence
            correlations = []
            for j, other_name in enumerate(evidence_names):
                if i != j:
                    corr = self.config.evidence_correlations.get(name, {}).get(other_name, 0.0)
                    correlations.append(abs(corr))
            
            mean_corr = np.mean(correlations) if correlations else 0.0
            effective_weight = 1.0 / (1.0 + 0.5 * mean_corr)
            
            # Raise LR to effective weight
            adjusted[name] = lr_per_evidence[name] ** effective_weight
        
        return adjusted
    
    def _weight_adjustment(self, lr_per_evidence: dict[str, float]) -> dict[str, float]:
        """Simple weight-based adjustment."""
        # Weights based on reliability
        weights = {
            "keypoint": 1.0,
            "mesh": 0.85,
            "descriptor": 0.75,
            "chronology": 0.60,
            "corroboration": 0.70,
        }
        
        adjusted = {}
        for name, lr in lr_per_evidence.items():
            w = weights.get(name, 0.5)
            adjusted[name] = lr ** w
        
        return adjusted


class LikelihoodCalculator:
    """Вычисляет P(evidence | H) для каждого evidence module."""
    
    def __init__(self, config: Stage3V2Config):
        self.config = config
    
    def compute_keypoint_likelihood(
        self,
        p95_z: float,
        sig_fraction: float,
        coherent_motion: float
    ) -> dict[str, float]:
        """
        Likelihood для keypoint displacement.
        
        P(p95_z | H0): при H0 z-scores ~ N(0,1), p95 ~ 1.64
        P(p95_z | H2): при H2 z-scores смещены, Gamma distribution
        """
        # P(data | H0): низкий p95_z более вероятен
        p_h0 = 1.0 - stats.norm.cdf(p95_z, loc=1.64, scale=0.5)
        p_h0 = max(p_h0, 1e-6)
        
        # P(data | H2): высокий p95_z более вероятен
        p_h2 = stats.gamma.pdf(p95_z, 
                               a=self.config.gamma_shape,
                               scale=self.config.gamma_scale)
        p_h2 = max(p_h2, 1e-6)
        
        # P(data | H1): синтетика может давать аномальные паттерны
        p_h1 = 0.1  # Uniform-ish
        
        # Модификация на основе когерентности
        if coherent_motion > 0.5:
            p_h2 *= 1.5
            p_h0 *= 0.7
        elif coherent_motion < 0.2:
            p_h2 *= 0.8
            p_h0 *= 1.1
        
        # Модификация на основе sig_fraction
        if sig_fraction > 0.3:
            p_h2 *= 1.3
            p_h0 *= 0.8
        
        return {
            "H0_SAME": p_h0,
            "H1_SYNTHETIC": p_h1,
            "H2_DIFFERENT": p_h2,
            "H_UNCERTAIN": 0.25,
        }
    
    def compute_mesh_likelihood(
        self,
        mesh_rmse: float,
        mesh_max_disp: float
    ) -> dict[str, float]:
        """Likelihood для 3D mesh analysis."""
        # P(mesh_rmse | H0): низкий RMSE при стабильности
        p_h0 = np.exp(-mesh_rmse / 0.001)
        p_h0 = max(p_h0, 1e-6)
        
        # P(mesh_rmse | H2): высокий RMSE при изменениях
        p_h2 = stats.gamma.pdf(mesh_rmse * 1000, shape=2.0, scale=1.5)
        p_h2 = max(p_h2, 1e-6)
        
        # P(mesh_rmse | H1)
        p_h1 = 0.1
        
        return {
            "H0_SAME": p_h0,
            "H1_SYNTHETIC": p_h1,
            "H2_DIFFERENT": p_h2,
            "H_UNCERTAIN": 0.25,
        }
    
    def compute_descriptor_likelihood(
        self,
        descriptor_p95_z: float,
        family_scores: dict[str, float]
    ) -> dict[str, float]:
        """Likelihood для local descriptors (13 families)."""
        # Базовое likelihood
        p_h0 = 1.0 - stats.norm.cdf(descriptor_p95_z, loc=1.5, scale=0.8)
        p_h0 = max(p_h0, 1e-6)
        
        p_h2 = stats.gamma.pdf(descriptor_p95_z, shape=2.5, scale=1.2)
        p_h2 = max(p_h2, 1e-6)
        
        # Модификация по информативным семействам
        informative = ["curvature", "shape_index", "dnap", "hks"]
        info_boost = sum(family_scores.get(f, 0) for f in informative) / len(informative)
        
        if info_boost > 3.0:
            p_h2 *= 1.3
            p_h0 *= 0.8
        
        return {
            "H0_SAME": p_h0,
            "H1_SYNTHETIC": 0.1,
            "H2_DIFFERENT": p_h2,
            "H_UNCERTAIN": 0.25,
        }
    
    def compute_chronology_likelihood(
        self,
        time_diff_days: float,
        has_temporal_pattern: bool
    ) -> dict[str, float]:
        """Likelihood для chronology module."""
        # Если есть временной паттерн → более вероятно H2
        if has_temporal_pattern:
            p_h2 = 0.6
            p_h0 = 0.3
        else:
            p_h2 = 0.4
            p_h0 = 0.5
        
        return {
            "H0_SAME": p_h0,
            "H1_SYNTHETIC": 0.1,
            "H2_DIFFERENT": p_h2,
            "H_UNCERTAIN": 0.25,
        }
    
    def compute_corroboration_likelihood(
        self,
        n_confirming_poses: int,
        consistency: float
    ) -> dict[str, float]:
        """Likelihood для cross-pose corroboration."""
        # Больше подтверждающих ракурсов → более вероятно H2
        if n_confirming_poses >= 3:
            p_h2 = 0.7 * consistency
            p_h0 = 0.2 * (1 - consistency)
        elif n_confirming_poses >= 2:
            p_h2 = 0.5 * consistency
            p_h0 = 0.35 * (1 - consistency)
        else:
            p_h2 = 0.3
            p_h0 = 0.5
        
        return {
            "H0_SAME": max(p_h0, 1e-6),
            "H1_SYNTHETIC": 0.1,
            "H2_DIFFERENT": max(p_h2, 1e-6),
            "H_UNCERTAIN": 0.25,
        }


def analyze_pair_bayesian(
    pair: dict[str, Any],
    config: Stage3V2Config,
    features: dict[str, float]
) -> BayesianResult:
    """
    Полный Bayesian анализ одной пары.
    
    Returns:
        BayesianResult с posterior, LR, BF
    """
    pair_id = pair.get("pair_id", "unknown")
    
    # Initialize updater
    updater = BayesianUpdater(config, features)
    lik_calc = LikelihoodCalculator(config)
    
    # Compute evidence likelihoods
    evidence_likelihoods = {}
    
    # 1. Keypoint
    kp_lik = lik_calc.compute_keypoint_likelihood(
        p95_z=features["p95_point_z"],
        sig_fraction=features["significant_point_fraction"],
        coherent_motion=features["coherent_motion_fraction"]
    )
    evidence_likelihoods["keypoint"] = kp_lik
    updater.update("keypoint", kp_lik)
    
    # 2. Mesh
    mesh_lik = lik_calc.compute_mesh_likelihood(
        mesh_rmse=features["mesh_rmse"],
        mesh_max_disp=0.0  # TODO: extract from pair
    )
    evidence_likelihoods["mesh"] = mesh_lik
    updater.update("mesh", mesh_lik)
    
    # 3. Descriptors
    desc_lik = lik_calc.compute_descriptor_likelihood(
        descriptor_p95_z=features["descriptor_p95_z"],
        family_scores={}  # TODO: extract from pair
    )
    evidence_likelihoods["descriptor"] = desc_lik
    updater.update("descriptor", desc_lik)
    
    # 4. Chronology
    chrono_lik = lik_calc.compute_chronology_likelihood(
        time_diff_days=features["days_delta"],
        has_temporal_pattern=features["p95_point_z"] > 3.0
    )
    evidence_likelihoods["chronology"] = chrono_lik
    updater.update("chronology", chrono_lik)
    
    # Compute LR (with dependence correction)
    combined_lr = updater.compute_lr(evidence_likelihoods)
    
    # Compute BF
    bayes_factor = updater.compute_bayes_factor()
    
    # LR per evidence
    lr_per_evidence = {}
    for name, lik in evidence_likelihoods.items():
        lr_per_evidence[name] = lik["H2_DIFFERENT"] / max(lik["H0_SAME"], 1e-10)
    
    return BayesianResult(
        pair_id=pair_id,
        prior=updater.prior,
        posterior=updater.posterior,
        lr=combined_lr,
        lr_per_evidence=lr_per_evidence,
        lr_verbal_ru=config.bf_verbal_ru(combined_lr),
        bayes_factor=bayes_factor,
        bf_level=config.bf_level(bayes_factor),
        update_history=updater.history,
    )
