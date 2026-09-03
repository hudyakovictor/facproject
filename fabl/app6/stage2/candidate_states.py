"""🔒 SINGLE SOURCE OF TRUTH → Каноническое множество состояний-кандидатов.

Используется в:
- stage2/evidence.py → REPORTABLE_CHANGE_STATES (change_points)
- stage2/postprocess_reports.py → CANDIDATE_STATES (manual_review_queue)

Любое расширение/изменение — ТОЛЬКО здесь. Никаких дубликатов.
"""
from __future__ import annotations

# Базовые состояния, означающие «есть сигнал изменения»
CORE_CHANGE_STATES = frozenset({
    "coherent_jump_candidate",
    "persistent_geometric_change",
    "reversible_change_candidate",
    "alpha_id_change_candidate",
    "same_day_conflict_candidate",
    "rate_change_candidate",
    "persistent_rate_change_candidate",
})

# Ограничивающие состояния (quality/calibration/pose_leakage limited)
# Включены в очередь ревью для ручной проверки, но НЕ в change_points
LIMITED_STATES = frozenset({
    "quality_limited",
    "calibration_limited",
    "pose_leakage_limited",
})

# Полное множество для change_points (публичные кандидаты изменений)
REPORTABLE_CHANGE_STATES = CORE_CHANGE_STATES

# Полное множество для manual_review_queue (всё, что требует внимания человека)
CANDIDATE_STATES = CORE_CHANGE_STATES | LIMITED_STATES