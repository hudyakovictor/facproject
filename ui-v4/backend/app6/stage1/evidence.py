"""Deprecated compatibility import for the canonical Stage 2 evidence layer.

Evidence classification belongs to :mod:`app6.stage2.evidence`.  This module is
kept only so old internal imports fail safely onto the canonical implementation
instead of using a stale duplicate contract.
"""
from app6.stage2.evidence import (
    EVIDENCE_SCHEMA,
    REPORTABLE_CHANGE_STATES,
    STATUS_TO_EVIDENCE_STATE,
    EvidencePacket,
    alternative_reasons,
    evidence_state,
    is_reportable_change,
    packet_from_pair,
)

__all__ = [
    "EVIDENCE_SCHEMA",
    "REPORTABLE_CHANGE_STATES",
    "STATUS_TO_EVIDENCE_STATE",
    "EvidencePacket",
    "alternative_reasons",
    "evidence_state",
    "is_reportable_change",
    "packet_from_pair",
]
