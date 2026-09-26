"""Evidence layer for Stage 2 v2: evidence packets + analysis validation.

Vocabulary matches what the downstream stages actually read:

  stage2b (app6/stage2b/engine.py) reads:
    - analysis_manifest.json       (now carries status:"complete")
    - analysis_validation.json     (schema stage2-validation-v1.1)
    - evidence_packets.json        (schema deeputin-stage2-evidence-v1.1,
                                    packets: [...])
    - lead_registry.json           (optional)

  stage3_v2 (app6/stage3_v2/loader.py) reads:
    - pair_metrics.csv
    - zone_metrics.csv
    - change_points.json
    - analysis_manifest.json
    - analysis_validation.json

Honesty rule: nothing in this module invents a measurement that v2 does not
make. A v2 status maps one-to-one onto an evidence state; states that require
machinery v2 does not have (persistent change across 3+ dates, texture-line
change) are deliberately *not* emitted. A claim that cannot be supported is
silence, not a guess.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .pipeline import PairMeasurement, RunResult

EVIDENCE_SCHEMA = "deeputin-stage2-evidence-v1.1"
VALIDATION_SCHEMA = "stage2-validation-v1.1"

# Evidence states stage2b classifies (app6/stage2b/engine.py):
#   SIGNIFICANT_STATES = {persistent_geometric_change, rate_change_candidate,
#                         coherent_jump_candidate, reversible_change_candidate,
#                         same_day_conflict_candidate, alpha_id_change_candidate,
#                         ...}
#   WEAK_STATES        = {elevated_uncertain, quality_limited,
#                         calibration_limited, pose_leakage_limited}
#   NO_SUPPORT_STATES  = {within_noise, insufficient_visibility,
#                         insufficient_calibration, unsupported_pose,
#                         inapplicable_pose}
#
# The set of states v2 can actually produce:
#   within_noise, coherent_change_candidate, scattered_or_uncertain,
#   localized_change_candidate, unscored_no_noise_reference,
#   unscored_no_bin_reference, unscored_no_measurement,
#   unscored_degenerate_noise
# Everything else (persistent_*, reversible_*, same_day_conflict_*) requires
# chronology machinery v2 does not run, so it is never fabricated.

STATUS_TO_EVIDENCE_STATE: dict[str, str] = {
    "within_noise": "within_noise",
    "coherent_change_candidate": "coherent_jump_candidate",
    "localized_change_candidate": "coherent_jump_candidate",
    "scattered_or_uncertain": "elevated_uncertain",
    "unscored_no_noise_reference": "insufficient_calibration",
    "unscored_no_bin_reference": "insufficient_calibration",
    "unscored_no_measurement": "not_measurable",
    "unscored_degenerate_noise": "insufficient_calibration",
    "measured": "elevated_uncertain",
}


def evidence_state_for(
    pair: PairMeasurement, *, zone_map_source: str = "partition"
) -> str:
    """Map a v2 pair status (plus verdict limits) to a stage2b state.

    `zone_map_source == "partition"` downgrades zone-significant findings to
    `elevated_uncertain`: a block_0N label cannot support a headline claim.
    """
    state = STATUS_TO_EVIDENCE_STATE.get(pair.status)
    if state is None:
        return "unknown_status_not_interpretable"

    limits = pair.verdict.limits

    if "quality_limited" in limits or "resolution_mismatch_limited" in limits:
        return "quality_limited"
    if "residual_tilt_limited" in limits:
        return "residual_tilt_limited"
    if "calibration_limited" in limits:
        return "calibration_limited"

    if pair.status == "localized_change_candidate":
        if zone_map_source != "measured":
            # The zone name is a neutral index block, not anatomy. A
            # zone-level finding without an anatomical label is corroboration
            # at best, never a headline.
            return "elevated_uncertain"
    return state


def alternative_reasons_for(pair: PairMeasurement) -> list[str]:
    """Alternative explanations, derived only from real verdict limits."""
    reasons: list[str] = []
    limits = pair.verdict.limits

    if "quality_limited" in limits or "resolution_mismatch_limited" in limits:
        reasons.append("low_or_missing_quality")
    if "texture_quality_unknown" in limits:
        reasons.append("low_or_missing_quality")
    if "calibration_limited" in limits:
        reasons.append("unstable_or_sparse_calibration")
    if "residual_tilt_limited" in limits:
        reasons.append("residual_pose_alignment_uncertain")
    if "cross_bin_limited" in limits:
        reasons.append("cross_pose_bin_comparison_limited")
    if "near_duplicate_limited" in limits:
        reasons.append("perceptual_duplicate_cluster_dependence")
    if "undated_limited" in limits:
        reasons.append("filename_corroborating_date_conflict")
    if "expression_unknown_limited" in limits or "expression_mismatch_limited" in limits:
        reasons.append("expression_or_soft_tissue_influence")
    if "structurally_limited_bin" in limits:
        reasons.append("structurally_limited_pose_bin")
    if "visibility_union_limited" in limits:
        reasons.append("limited_landmark_visibility")

    if pair.pair_type == "same_day" and pair.significant:
        reasons.append("same_day_residual_unexpected")

    return reasons


def packet_from_pair(
    pair: PairMeasurement, *, zone_map_source: str = "partition"
) -> dict[str, Any]:
    """Build one evidence packet from a measured pair.

    `visualization_only` is deliberately minimal: v2 performs no texture or UV
    identity analysis, so there is nothing to record here.
    """
    measurements: dict[str, Any] = {
        "rmse_ioc": pair.rmse_ioc,
        "p95": pair.p95,
        "coherence": pair.coherence,
        "z_score": pair.z_score,
        "p_value": pair.p_value,
        "q_value": pair.q_value,
        "significant": pair.significant,
        "usable_points": pair.usable_points,
        "residual_tilt_deg": pair.residual_tilt_deg,
    }
    if pair.zone_metrics:
        # The raw per-zone numbers travel as-is; their *interpretation* is
        # decided by `zone_map_source`, not here.
        measurements["zone_metrics"] = {
            name: metrics for name, metrics in sorted(pair.zone_metrics.items())
        }
    if pair.significant_zones:
        measurements["significant_zones"] = sorted(pair.significant_zones)

    quality = {
        "quality_limited": "quality_limited" in pair.verdict.limits,
        "limits": sorted(pair.verdict.limits),
    }

    primary_zone_or_family = "ldm134_motion"
    if pair.significant_zones:
        primary_zone_or_family = sorted(pair.significant_zones)[0]

    return {
        "schema_version": EVIDENCE_SCHEMA,
        "pair_id": pair.pair_id,
        "evidence_state": evidence_state_for(pair, zone_map_source=zone_map_source),
        "status": pair.status,
        "pair_type": pair.pair_type,
        "pose_bin": pair.pose_bin,
        "photo_a": pair.photo_a,
        "photo_b": pair.photo_b,
        "date_a": pair.date_a,
        "date_b": pair.date_b,
        "primary_zone_or_family": primary_zone_or_family,
        "quality": quality,
        "measurements": measurements,
        "alternative_explanations": alternative_reasons_for(pair),
        "visualization_only": {
            "policy": "v2 does not run texture or UV identity analysis; nothing to record",
            "synthetic": False,
        },
        "registered_metric_channel": _metric_channel(pair.zone_metrics),
    }


def _metric_channel(zone_metrics: dict[str, Any]) -> dict[str, Any]:
    """Minimal registered-metric channel, keyed the way stage2b expects.

    The legacy channel is a registry of which evidence metrics were attached;
    v2 keeps one flat, honest dict. Texture/UV keys are forbidden in the
    evidence channel by design - v2 has none.
    """
    channel: dict[str, Any] = {}
    for zone, metrics in zone_metrics.items():
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and key not in channel:
                channel[f"{zone}__{key}"] = value
    return channel


def build_evidence_packets(
    result: RunResult, *, output_dir: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return (top_payload, packets). Only scored, admitted pairs produce
    packets; skipped pairs are recorded in skipped_pairs.json by the pipeline,
    and a pair with no measurement cannot support any claim."""
    zone_source = getattr(result.zone_map, "source", "partition")
    packets = [
        packet_from_pair(pair, zone_map_source=zone_source)
        for pair in result.scored
    ]
    payload = {
        "schema": EVIDENCE_SCHEMA,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "zone_map_source": zone_source,
        "packet_count": len(packets),
        "policy": (
            "one packet per scored pair; states map one-to-one from v2 "
            "statuses, no persistence/chronology states are fabricated"
        ),
        "packets": packets,
    }
    return payload, packets


def build_validation(
    *,
    result: RunResult,
    output_dir: Path,
    evidence_packets: list[dict[str, Any]],
    required_files: list[str],
) -> dict[str, Any]:
    """Deterministic contract check, mirroring legacy validate_analysis_contract
    but scoped to what v2 actually promises."""
    errors: list[str] = []

    for name in required_files:
        if not (output_dir / name).is_file():
            errors.append(f"missing {name}")

    pair_ids = [p.pair_id for p in result.scored]
    if len(pair_ids) != len(set(pair_ids)):
        errors.append("duplicate_pair_id")

    packet_ids = [p.get("pair_id") for p in evidence_packets]
    if set(packet_ids) != set(pair_ids):
        errors.append("evidence_packet_pair_ids_mismatch")

    unknown_states = {
        p.get("evidence_state")
        for p in evidence_packets
        if p.get("evidence_state") == "unknown_status_not_interpretable"
    }
    if unknown_states:
        errors.append(f"uninterpretable_evidence_states:{sorted(unknown_states)}")

    return {
        "schema": VALIDATION_SCHEMA,
        "status": "complete" if not errors else "invalid",
        "errors": errors,
        "scored_pair_count": len(pair_ids),
        "evidence_packet_count": len(evidence_packets),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def write_evidence_artifacts(
    result: RunResult, output_dir: Path, required_files: list[str]
) -> list[Path]:
    """Write analysis_validation.json and evidence_packets.json."""
    output_dir = Path(output_dir)
    payload, packets = build_evidence_packets(result, output_dir=output_dir)
    validation = build_validation(
        result=result,
        output_dir=output_dir,
        evidence_packets=packets,
        required_files=required_files,
    )

    written: list[Path] = []

    def dump(name: str, data: dict[str, Any]) -> None:
        path = output_dir / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        tmp.replace(path)
        written.append(path)

    dump("analysis_validation.json", validation)
    dump("evidence_packets.json", payload)
    return written