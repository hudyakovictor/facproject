"""Gates - every admission decision for a photo or a pair.

Design rules that the legacy gates broke:

1. **No gate owns a threshold.** Every gate takes `Params`. There is no default
   to silently fall back to, which is how `_pair_qc_decision` ended up using
   its own defaults because the call site stopped passing thresholds.
2. **Every verdict carries its reason and the value behind it.** A gate returns
   a `Verdict`, not a bool, so any downstream report can explain itself.
3. **Limits accumulate.** `Verdict.limits` is a growing set. A pair that was
   downgraded once can never be silently promoted back, which was the
   `evidence_state` overwrite bug.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import contract
from .loader import Record
from .params import Params


@dataclass
class Verdict:
    """Result of one or more gates.

    `admitted=False` means the pair is not measured at all and appears in
    skipped_pairs.csv. `limits` means it *is* measured but cannot support a
    primary claim - it is reported with its evidence class reduced.
    """

    admitted: bool = True
    skip_reason: str | None = None
    limits: set[str] = field(default_factory=set)
    #: Human-readable trace: what was checked, against what, and what happened.
    trace: list[dict] = field(default_factory=list)

    def skip(self, reason: str, **detail) -> "Verdict":
        self.admitted = False
        # Keep the first reason: it is the earliest and most specific cause.
        if self.skip_reason is None:
            self.skip_reason = reason
        self.trace.append({"gate": reason, "outcome": "skip", **detail})
        return self

    def limit(self, name: str, **detail) -> "Verdict":
        self.limits.add(name)
        self.trace.append({"gate": name, "outcome": "limit", **detail})
        return self

    def note(self, gate: str, **detail) -> "Verdict":
        self.trace.append({"gate": gate, "outcome": "pass", **detail})
        return self

    def merge(self, other: "Verdict") -> "Verdict":
        if not other.admitted:
            self.admitted = False
            if self.skip_reason is None:
                self.skip_reason = other.skip_reason
        self.limits |= other.limits
        self.trace.extend(other.trace)
        return self

    @property
    def evidence_class(self) -> str:
        """What this pair is allowed to support.

        primary  - may carry a headline finding
        limited  - may corroborate, may not lead
        excluded - not measured
        """
        if not self.admitted:
            return "excluded"
        return "limited" if self.limits else "primary"

    def to_json(self) -> dict:
        return {
            "admitted": self.admitted,
            "evidence_class": self.evidence_class,
            "skip_reason": self.skip_reason,
            "limits": sorted(self.limits),
            "trace": self.trace,
        }


# --------------------------------------------------------------------------
# Per-photo gates
# --------------------------------------------------------------------------
def quality_stratum(record: Record, params: Params) -> str:
    """Bucket a photo by how much we trust its geometry.

    Used to inflate thresholds rather than to exclude: a blurry photo is not
    useless, it just has to clear a higher bar before it counts as evidence.
    """
    confidence = record.detection_confidence
    if not np.isfinite(confidence):
        return "low"
    if confidence >= params["detection_confidence_high"]:
        return "high"
    if confidence >= params["detection_confidence_low"]:
        return "mixed"
    return "low"


def photo_gate(record: Record, params: Params) -> Verdict:
    """Whether a single photo may enter any pair at all."""
    verdict = Verdict()

    if record.pose_bin in {"out_of_supported_range", "unknown", ""}:
        return verdict.skip("pose_bin_unsupported", pose_bin=record.pose_bin)

    if np.isfinite(record.face_area_ratio):
        if record.face_area_ratio < params["min_face_area_ratio"]:
            return verdict.skip(
                "face_too_small",
                value=record.face_area_ratio,
                threshold=params["min_face_area_ratio"],
            )
    elif params["fail_closed_missing_qc"]:
        return verdict.skip("face_area_ratio_missing")

    # alignment_quality does NOT gate by default: it was measured to be
    # uncorrelated with the residual. Kept switchable so the finding can be
    # re-tested rather than buried.
    if params["alignment_quality_gates"]:
        if not np.isfinite(record.alignment_quality):
            return verdict.skip("alignment_quality_missing")
        if record.alignment_quality < params["min_alignment_quality"]:
            return verdict.skip(
                "alignment_quality_low",
                value=record.alignment_quality,
                threshold=params["min_alignment_quality"],
            )

    stratum = quality_stratum(record, params)
    verdict.note("quality_stratum", stratum=stratum, confidence=record.detection_confidence)
    return verdict


def expression_state(record: Record, params: Params) -> dict:
    """Classify expression from landmark geometry.

    Geometry, not the BFM expression coefficients: `alpha_exp` has no physical
    threshold and did not separate calm faces from smiling ones on the
    calibration set, whereas the two ratios below separated them completely.
    """
    if params["expression_source"] == "disabled":
        return {"source": "disabled", "smiling": False, "jaw_open": False}
    smiling = (
        bool(record.corner_lift_ioc > params["corner_lift_threshold"])
        if np.isfinite(record.corner_lift_ioc)
        else None
    )
    jaw_open = (
        bool(record.jaw_open_ratio > params["jaw_open_threshold"])
        if np.isfinite(record.jaw_open_ratio)
        else None
    )
    return {
        "source": params["expression_source"],
        "smiling": smiling,
        "jaw_open": jaw_open,
        "corner_lift_ioc": record.corner_lift_ioc,
        "jaw_open_ratio": record.jaw_open_ratio,
    }


# --------------------------------------------------------------------------
# Pair gates
# --------------------------------------------------------------------------
def pose_gate(a: Record, b: Record, params: Params) -> Verdict:
    """Reject pairs whose pose differs enough to fake a geometric change.

    This is the single most important gate in the stage. Pose separation
    produces residuals that look exactly like real change, so it is rejected
    *before* scoring rather than corrected afterwards.
    """
    verdict = Verdict()

    if a.pose_bin != b.pose_bin:
        if not params["cross_bin_pairs"]:
            return verdict.skip(
                "cross_pose_bin", bin_a=a.pose_bin, bin_b=b.pose_bin
            )
        verdict.limit("cross_bin_limited", bin_a=a.pose_bin, bin_b=b.pose_bin)

    yaw_gap = abs(a.yaw - b.yaw)
    pitch_gap = abs(a.pitch - b.pitch)
    roll_gap = abs(a.roll - b.roll)

    # Profile bins span ~45 deg of yaw, far too wide to compare directly, so
    # they get a much tighter budget and are split into sub-bins.
    in_profile = a.pose_bin in contract.PROFILE_BINS
    yaw_budget = (
        params["profile_sub_bin_max_yaw_gap_deg"]
        if in_profile
        else params["max_yaw_gap_deg"]
    )

    if yaw_gap > yaw_budget:
        return verdict.skip("yaw_gap_exceeded", value=yaw_gap, threshold=yaw_budget)
    if pitch_gap > params.max_pitch_gap_deg:
        return verdict.skip(
            "pitch_gap_exceeded", value=pitch_gap, threshold=params.max_pitch_gap_deg
        )
    if roll_gap > params.max_roll_gap_deg:
        return verdict.skip(
            "roll_gap_exceeded", value=roll_gap, threshold=params.max_roll_gap_deg
        )

    if in_profile:
        sub_a = int(a.yaw // params["profile_sub_bin_width_deg"])
        sub_b = int(b.yaw // params["profile_sub_bin_width_deg"])
        if sub_a != sub_b:
            return verdict.skip("profile_sub_bin_mismatch", sub_a=sub_a, sub_b=sub_b)

    if a.pose_bin in params["limited_bins"]:
        verdict.limit("structurally_limited_bin", pose_bin=a.pose_bin)

    verdict.note("pose_gate", yaw_gap=yaw_gap, pitch_gap=pitch_gap, roll_gap=roll_gap)
    return verdict


def expression_gate(a: Record, b: Record, params: Params) -> Verdict:
    """Reject or downgrade pairs whose expressions differ.

    A smile moves the mid-face by far more than a decade of ageing does. An
    uncontrolled expression difference is the most common way to manufacture a
    dramatic false finding.
    """
    verdict = Verdict()
    policy = params["expression_policy"]
    if policy == "off":
        return verdict

    state_a = expression_state(a, params)
    state_b = expression_state(b, params)

    unknown = any(
        state[key] is None
        for state in (state_a, state_b)
        for key in ("smiling", "jaw_open")
    )
    if unknown:
        if params["fail_closed_missing_qc"]:
            return verdict.skip("expression_state_unknown")
        verdict.limit("expression_unknown_limited")
        return verdict

    any_expression = (
        state_a["smiling"] or state_b["smiling"]
        or state_a["jaw_open"] or state_b["jaw_open"]
    )
    mismatch = (
        state_a["smiling"] != state_b["smiling"]
        or state_a["jaw_open"] != state_b["jaw_open"]
    )

    if policy == "exclude_any" and any_expression:
        return verdict.skip("expression_present", a=state_a, b=state_b)
    if policy == "exclude_mismatch" and mismatch:
        return verdict.skip("expression_mismatch", a=state_a, b=state_b)
    if policy == "stratify" and mismatch:
        verdict.limit("expression_mismatch_limited", a=state_a, b=state_b)

    if params["jaw_degree_gap_enforced"]:
        gap = abs(a.jaw_open_degree - b.jaw_open_degree)
        if np.isfinite(gap) and gap > params["max_jaw_degree_gap"]:
            return verdict.skip(
                "jaw_degree_gap_exceeded",
                value=gap,
                threshold=params["max_jaw_degree_gap"],
            )

    verdict.note("expression_gate", policy=policy, mismatch=mismatch)
    return verdict


def quality_gate(a: Record, b: Record, params: Params) -> Verdict:
    """Downgrade pairs whose image quality cannot support a primary claim."""
    verdict = Verdict()

    # Texture quality read from the correct contract location. The legacy code
    # read a key Stage 1 never wrote, defaulted it to 0.0, and thereby marked
    # every pair in every run as quality-limited.
    scores = [s for s in (a.texture_quality, b.texture_quality) if np.isfinite(s)]
    if not scores:
        verdict.limit("texture_quality_unknown")
    elif min(scores) < params["min_texture_quality"]:
        verdict.limit(
            "quality_limited",
            value=min(scores),
            threshold=params["min_texture_quality"],
        )

    if a.pixels and b.pixels:
        ratio = max(a.pixels, b.pixels) / max(min(a.pixels, b.pixels), 1)
        if ratio > params["max_resolution_ratio"]:
            verdict.limit(
                "resolution_mismatch_limited",
                value=ratio,
                threshold=params["max_resolution_ratio"],
            )

    strata = {quality_stratum(a, params), quality_stratum(b, params)}
    stratum = "high" if strata == {"high"} else ("low" if "low" in strata else "mixed")
    inflation = params.quality_inflation_map[stratum]
    verdict.note("quality_gate", stratum=stratum, threshold_inflation=inflation)
    return verdict


def provenance_gate(a: Record, b: Record, params: Params) -> Verdict:
    """Downgrade pairs whose dates or independence cannot be trusted.

    A finding is only as good as its dating. If we cannot say when a photo was
    taken, we cannot say when a change happened, and a chronology built on it
    is not evidence of anything.
    """
    verdict = Verdict()

    for record in (a, b):
        if record.date_conflict_days > params["date_conflict_days"]:
            verdict.limit(
                "date_provenance_limited",
                photo_id=record.photo_id,
                conflict_days=record.date_conflict_days,
                threshold=params["date_conflict_days"],
            )
        if not record.is_dated:
            verdict.limit("undated_limited", photo_id=record.photo_id)

    duplicates = [r.photo_id for r in (a, b) if r.near_duplicate_of]
    if duplicates:
        if params["exclude_near_duplicates"]:
            return verdict.skip("near_duplicate", photo_ids=duplicates)
        verdict.limit("near_duplicate_limited", photo_ids=duplicates)

    return verdict


def visibility_intersection(
    a: Record, b: Record, params: Params, scheme: int = 134
) -> tuple[np.ndarray, Verdict]:
    """Landmarks usable in both photos, plus a verdict on whether there are enough.

    Intersection, never union: a landmark hidden in one photo has no measured
    position there, so including it would compare a real coordinate against an
    inferred one.
    """
    verdict = Verdict()
    try:
        visible_a = a.visible(scheme)
        visible_b = b.visible(scheme)
    except KeyError as exc:
        verdict.skip("visibility_arrays_missing", detail=str(exc))
        return np.zeros(0, dtype=int), verdict

    if params["visibility_policy"] == "union":
        mask = visible_a | visible_b
        verdict.limit("visibility_union_limited")
    else:
        mask = visible_a & visible_b

    indices = np.flatnonzero(mask)
    minimum = params[f"min_points_{scheme}"]
    if indices.size < minimum:
        verdict.skip(
            "insufficient_visible_points",
            value=int(indices.size),
            threshold=minimum,
            scheme=scheme,
        )
    else:
        verdict.note(
            "visibility_gate", usable_points=int(indices.size), threshold=minimum
        )
    return indices, verdict


def pair_gate(a: Record, b: Record, params: Params) -> Verdict:
    """Run every pair gate that does not need the geometry arrays.

    Ordered cheapest-first and short-circuiting on rejection, so a run over
    thousands of candidate pairs does not load reconstructions it will discard.
    """
    verdict = Verdict()
    for gate in (pose_gate, expression_gate, provenance_gate, quality_gate):
        verdict.merge(gate(a, b, params))
        if not verdict.admitted:
            break
    return verdict


def temporal_axis(records: list[Record], params: Params) -> Verdict:
    """Whether the dataset supports any temporal claim at all.

    Without this check a dataset with two usable dates produces empty results
    that read exactly like "we looked and found no change", which is a very
    different statement from "we could not look".
    """
    verdict = Verdict()
    dated = [r for r in records if r.is_dated]
    distinct = sorted({r.date for r in dated if r.date})
    if len(dated) < params["min_dated_records"]:
        return verdict.skip(
            "skipped_no_temporal_axis",
            dated=len(dated),
            threshold=params["min_dated_records"],
        )
    if len(distinct) < params["min_distinct_dates"]:
        return verdict.skip(
            "skipped_no_temporal_axis",
            distinct_dates=len(distinct),
            threshold=params["min_distinct_dates"],
        )
    verdict.note(
        "temporal_axis",
        dated=len(dated),
        distinct_dates=len(distinct),
        span=f"{distinct[0]} .. {distinct[-1]}",
    )
    return verdict
