"""🎯 DEEPUTIN Stage 3 v2 — Аналитический движок поверх Stage 2.

Добавляет поверх Stage 2 output:
  • Likelihood Ratio framework (ENFSI standard)
  • Effect Size (Cohen's d) per zone
  • Bootstrap Confidence Intervals (95%)
  • Enhanced Change Point Detection
  • Cross-pose confirmation
  • Narrative Engine (Russian text for journalist)
  • Legacy hypothesis integration
  • Feedback loop (auto-calibration suggestions)

Архитектура: Bayesian ВНУТРИ, LR СНАРУЖИ.
  - Bayesian updating используется для вычислений
  - Likelihood Ratio представляется журналисту

🔗 INPUT:  Stage 2 output (pair_metrics.csv, zone_metrics.csv, change_points.json, etc.)
📤 OUTPUT: Narrative report, LR analysis, effect sizes, journalist-ready text
"""
from __future__ import annotations

from .config import Stage3V2Config
from .engine import Stage3V2Engine

__all__ = ["Stage3V2Config", "Stage3V2Engine"]
__version__ = "3.2.0"
__schema__ = "deeputin-stage3v2-v3.2"
