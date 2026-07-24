"""Semantic validation of final Stage 2 outputs."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .evidence import is_reportable_change


def validate_analysis_contract(
    out: Path,
    *,
    required_files: list[str],
    rows: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    evidence_packets: list[dict[str, Any]],
    public_safety: dict[str, Any],
) -> list[str]:
    """Return deterministic contract errors; an empty list means valid output."""
    errors=[f'missing {name}' for name in required_files if not (out/name).is_file()]
    if len(evidence_packets)!=len(rows):errors.append(f'evidence_packet_count_mismatch:{len(evidence_packets)}!={len(rows)}')
    pair_ids=[str(r.get('pair_id')) for r in rows]
    if len(pair_ids)!=len(set(pair_ids)):errors.append('duplicate_pair_id')
    packet_ids=[str(p.get('pair_id')) for p in evidence_packets]
    if set(packet_ids)!=set(pair_ids):errors.append('evidence_packet_pair_ids_mismatch')
    nonreportable=[str(c.get('pair_id')) for c in changes if not is_reportable_change(c)]
    if nonreportable:errors.append('nonreportable_change_points:'+','.join(sorted(nonreportable)))
    if public_safety.get('status')!='pass':errors.append('public_safety_failed')
    forbidden_metric_keys=[]
    for packet in evidence_packets:
        channel=packet.get('registered_metric_channel') or {}
        forbidden_metric_keys.extend(k for k in channel if str(k).startswith(('texture_','uv_')))
    if forbidden_metric_keys:errors.append('visualization_metric_leaked_into_evidence:'+','.join(sorted(set(forbidden_metric_keys))))
    return errors
