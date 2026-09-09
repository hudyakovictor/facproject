"""Narrative layer - turns measurements into sentences.

This is the most dangerous module in the project, and it is worth being blunt
about why. Everything upstream produces numbers, and a wrong number is usually
obviously wrong. This module produces *prose*, and wrong prose is persuasive.
A sentence like "the jawline shifted markedly after 2012" will be believed,
quoted, and repeated long after anyone checks whether q was 0.04 or 0.4.

So the generator is built around one rule:

    **No sentence may assert more than its evidence class permits.**

That rule is enforced mechanically, not by good intentions:

  * `Claim` carries its own evidence and refuses to render language stronger
    than that evidence supports. The verb is *selected by* the statistics, not
    chosen by whoever wrote the template.
  * Zone names are only spoken when the zone map is a measured atlas. On a
    fallback partition, prose falls back to neutral identifiers, because a
    confident anatomical noun over an unverified index range is a fabrication
    with good grammar.
  * Every rendered sentence carries a `sources` list of the pair IDs behind it,
    so any claim can be walked back to the rows that produced it.
  * There is no template for a conclusion the pipeline cannot reach. You cannot
    render "this is a different person" because no such `Claim` type exists.

The writing style is deliberately plain: short sentences, concrete numbers,
uncertainty stated inline rather than buried in a footnote. That is not a
stylistic preference. A reader who cannot see the uncertainty cannot weigh the
claim, and a report that hides it is not journalism.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np


# --------------------------------------------------------------------------
# Evidence vocabulary
# --------------------------------------------------------------------------
#: Strength tiers, weakest first. The index is used for comparisons, so order
#: is load-bearing.
STRENGTH = ("none", "insufficient", "weak", "moderate", "strong")

#: The verb each tier is allowed to use. Nothing above "strong" exists: the
#: pipeline measures geometry, and geometry does not license certainty about
#: causes.
VERBS = {
    "none": "shows no measurable",
    "insufficient": "cannot be assessed for",
    "weak": "shows a possible",
    "moderate": "shows a",
    "strong": "shows a clear",
}

#: What each tier is permitted to be used for downstream.
USAGE = {
    "none": "reportable as a negative result",
    "insufficient": "not reportable; describes a gap in the data",
    "weak": "background only; must not be a headline",
    "moderate": "reportable with stated uncertainty",
    "strong": "reportable as a primary finding",
}


def classify_strength(
    *,
    significant: bool,
    q_value: float,
    coherence: float,
    evidence_class: str,
    support: int,
) -> tuple[str, list[str]]:
    """Decide how strongly a finding may be stated, and say why.

    Returns the tier plus the reasons that produced it, so the report can show
    its work instead of asserting a grade.
    """
    reasons: list[str] = []

    if evidence_class == "excluded":
        return "insufficient", ["pair was excluded before measurement"]
    if support <= 0:
        return "insufficient", ["no measured pairs support this period"]

    if not np.isfinite(q_value):
        return "insufficient", [
            "no noise floor was available, so significance is undefined"
        ]

    if not significant:
        reasons.append(f"q = {q_value:.3f} after correction, above the {0.05:.2f} level")
        return "none", reasons

    tier = "moderate"
    reasons.append(f"q = {q_value:.3f} after multiple-testing correction")

    if coherence >= 0.7:
        reasons.append(f"displacement is directionally coherent ({coherence:.2f})")
        tier = "strong"
    elif coherence >= 0.5:
        reasons.append(f"displacement is partly coherent ({coherence:.2f})")
    else:
        reasons.append(
            f"displacement directions largely cancel ({coherence:.2f}), "
            "which is more consistent with noise than with movement"
        )
        tier = "weak"

    if support < 2:
        reasons.append("only one pair supports this period")
        tier = STRENGTH[max(0, STRENGTH.index(tier) - 1)]
    else:
        reasons.append(f"{support} independent pairs agree")

    if evidence_class == "limited":
        reasons.append(
            "pair carries quality or provenance limits, so it may corroborate "
            "but may not lead"
        )
        tier = STRENGTH[max(0, STRENGTH.index(tier) - 1)]

    return tier, reasons


# --------------------------------------------------------------------------
# Claims
# --------------------------------------------------------------------------
@dataclass
class Claim:
    """One statement, bound to the evidence that permits it."""

    subject: str
    strength: str
    reasons: list[str]
    sources: list[str]
    magnitude_ioc: float = float("nan")
    period: str = ""
    anatomical_ok: bool = True

    def __post_init__(self) -> None:
        if self.strength not in STRENGTH:
            raise ValueError(f"unknown strength tier: {self.strength!r}")

    @property
    def usage(self) -> str:
        return USAGE[self.strength]

    @property
    def reportable(self) -> bool:
        return self.strength in {"none", "moderate", "strong"}

    def magnitude_phrase(self) -> str:
        """Express size in units a reader can picture.

        Interocular fractions are meaningless to a general reader, so they are
        also given as millimetres against a stated 63 mm reference. The
        reference is named inline every time: a bare millimetre figure would
        imply a precision of measurement on the original photograph that we do
        not have.
        """
        if not np.isfinite(self.magnitude_ioc):
            return "of unmeasured size"
        mm = self.magnitude_ioc * 63.0
        return (
            f"about {self.magnitude_ioc * 100:.2f}% of eye-to-eye distance "
            f"(roughly {mm:.2f} mm on a typical 63 mm adult interocular span)"
        )

    def sentence(self) -> str:
        """Render the claim. The verb comes from the evidence, not the author."""
        verb = VERBS[self.strength]
        subject = self.subject if self.anatomical_ok else f"region {self.subject}"
        period = f" between {self.period}" if self.period else ""

        if self.strength == "none":
            return f"The {subject} {verb} change{period}."
        if self.strength == "insufficient":
            return f"The {subject} {verb} change{period}."
        return (
            f"The {subject} {verb} change{period}, "
            f"{self.magnitude_phrase()}."
        )

    def to_json(self) -> dict:
        return {
            "subject": self.subject,
            "period": self.period,
            "strength": self.strength,
            "reportable": self.reportable,
            "usage": self.usage,
            "sentence": self.sentence(),
            "magnitude_ioc": (
                round(float(self.magnitude_ioc), 6)
                if np.isfinite(self.magnitude_ioc)
                else None
            ),
            "reasons": self.reasons,
            "sources": self.sources,
        }


# --------------------------------------------------------------------------
# Chronology
# --------------------------------------------------------------------------
@dataclass
class Period:
    """One interval between two dated observations."""

    start: str
    end: str
    pairs: list = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.start} and {self.end}"

    @property
    def days(self) -> int | None:
        try:
            a = date.fromisoformat(self.start.replace("_", "-"))
            b = date.fromisoformat(self.end.replace("_", "-"))
        except ValueError:
            return None
        return abs((b - a).days)

    @property
    def years(self) -> float | None:
        days = self.days
        return None if days is None else days / 365.25


def build_periods(pairs: list) -> list[Period]:
    """Group cross-date pairs into chronological intervals."""
    buckets: dict[tuple[str, str], Period] = {}
    for pair in pairs:
        if pair.pair_type == "same_day":
            continue
        if not (pair.date_a and pair.date_b):
            continue
        key = tuple(sorted((pair.date_a, pair.date_b)))
        if key not in buckets:
            buckets[key] = Period(start=key[0], end=key[1])
        buckets[key].pairs.append(pair)
    return [buckets[key] for key in sorted(buckets)]


def period_claim(period: Period, *, anatomical: bool) -> Claim:
    """Summarise one interval as a single claim."""
    scored = [p for p in period.pairs if np.isfinite(p.q_value)]
    sources = [p.pair_id for p in period.pairs]

    if not scored:
        return Claim(
            subject="face",
            strength="insufficient",
            reasons=["no pair in this interval could be scored against a noise floor"],
            sources=sources,
            period=period.label,
            anatomical_ok=anatomical,
        )

    # The strongest pair leads, but support counts how many agree with it.
    best = min(scored, key=lambda p: p.q_value)
    agreeing = sum(1 for p in scored if p.significant)
    strength, reasons = classify_strength(
        significant=best.significant,
        q_value=best.q_value,
        coherence=best.coherence,
        evidence_class=best.verdict.evidence_class,
        support=agreeing if best.significant else len(scored),
    )

    # A whole-face residual that stays inside the noise does not mean the
    # interval is quiet. The global statistic averages over every landmark, so
    # a change confined to one region is diluted below detection - this was
    # measured, not assumed (see VALIDATION.md, experiment 1). When a zone
    # test fired, the interval must not be reported as "no measurable change".
    localized = [p for p in period.pairs if getattr(p, "zone_significant", False)]
    if localized and strength in {"none", "insufficient"}:
        zone_count = len({z for p in localized for z in p.significant_zones})
        strength = "weak"
        reasons.append(
            f"the whole-face residual stayed inside the noise, but {zone_count} "
            "zone(s) exceeded their own noise floor in "
            f"{len(localized)} pair(s); a regional change is diluted by the "
            "whole-face average, so the zone result is the informative one"
        )
        reasons.append(
            "graded no higher than weak because this pipeline dated an "
            "injected change correctly but misattributed its zone in testing"
        )

    if period.years:
        reasons.append(f"interval spans {period.years:.1f} years")

    magnitudes = [p.rmse_ioc for p in scored if np.isfinite(p.rmse_ioc)]
    magnitude = float(np.median(magnitudes)) if magnitudes else float("nan")

    return Claim(
        subject="face",
        strength=strength,
        reasons=reasons,
        sources=sources,
        magnitude_ioc=magnitude,
        period=period.label,
        anatomical_ok=anatomical,
    )


def localized_zone_claims(period: Period, *, anatomical: bool) -> list[Claim]:
    """Claims for zones that cleared their own noise floor in this interval.

    Kept separate from `zone_claims`, which reports the zone breakdown of an
    already-significant whole-face result. This function covers the opposite
    and more common case: the whole face looks quiet while one region moved.

    Every claim here is capped at "weak" regardless of its q-value. On the
    fixture, zone attribution landed on a neighbouring zone rather than the
    one carrying the injected change, because global alignment leaks residual
    across zone boundaries. The date was right; the zone was not. So a zone
    name is a pointer for a human to check, never a finding.
    """
    claims: list[Claim] = []
    by_zone: dict[str, list] = {}

    for pair in period.pairs:
        for zone in getattr(pair, "significant_zones", []):
            by_zone.setdefault(zone, []).append(pair)

    for zone, pairs in sorted(by_zone.items(), key=lambda kv: -len(kv[1])):
        qs = [
            pair.zone_metrics[zone].get("zone_q")
            for pair in pairs
            if pair.zone_metrics.get(zone, {}).get("zone_q") is not None
        ]
        best_q = min(qs) if qs else float("nan")
        reasons = [
            f"zone q = {best_q:.4f} against a noise floor built from "
            "same-day pairs of this zone",
            f"seen in {len(pairs)} pair(s) in this interval",
            "zone attribution is unreliable in this pipeline: adjacent zones "
            "absorb leaked residual, so treat this as a region to inspect "
            "rather than a located change",
        ]
        claims.append(
            Claim(
                subject=zone,
                strength="weak",
                reasons=reasons,
                sources=[p.pair_id for p in pairs],
                period=period.label,
                anatomical_ok=anatomical,
            )
        )

    return claims


def zone_claims(
    period: Period, *, anatomical: bool, top_n: int = 3
) -> list[Claim]:
    """Per-zone claims for one interval, strongest first.

    Only produced for periods that already cleared significance overall.
    Zone-level attribution on a null result is how a non-finding gets
    retold as "the cheeks changed slightly".
    """
    significant = [p for p in period.pairs if p.significant]
    if not significant:
        return []

    aggregate: dict[str, list[tuple[float, float, str]]] = {}
    for pair in significant:
        for name, metrics in pair.zone_metrics.items():
            rmse = metrics.get("rmse")
            coherence = metrics.get("coherence")
            if rmse is None:
                continue
            aggregate.setdefault(name, []).append(
                (float(rmse), float(coherence or 0.0), pair.pair_id)
            )

    ranked: list[Claim] = []
    for name, entries in aggregate.items():
        if len(entries) < 1:
            continue
        rmse = float(np.median([e[0] for e in entries]))
        coherence = float(np.median([e[1] for e in entries]))
        sources = sorted({e[2] for e in entries})

        # Zone claims inherit the period's correction; they are never given an
        # independent significance test, which would multiply the test count
        # without multiplying the correction.
        strength = "moderate" if coherence >= 0.5 else "weak"
        if coherence >= 0.7 and len(entries) >= 2:
            strength = "strong"
        if not anatomical:
            # Never let an unverified index block carry a strong claim.
            strength = "weak" if strength == "strong" else strength

        ranked.append(
            Claim(
                subject=name,
                strength=strength,
                reasons=[
                    f"zone residual {rmse:.5f} in normalised units",
                    f"directional coherence {coherence:.2f}",
                    f"observed in {len(entries)} significant pair(s)",
                    (
                        "inherits the period's corrected significance; not "
                        "independently tested"
                    ),
                ],
                sources=sources,
                magnitude_ioc=rmse,
                period=period.label,
                anatomical_ok=anatomical,
            )
        )

    ranked.sort(key=lambda c: c.magnitude_ioc, reverse=True)
    return ranked[:top_n]


# --------------------------------------------------------------------------
# Counter-explanations
# --------------------------------------------------------------------------
#: Every alternative explanation for a residual that is not a real change.
#: A finding is only worth publishing once each of these has been addressed,
#: so the report enumerates them explicitly rather than leaving them for a
#: critic to raise later.
COUNTER_EXPLANATIONS = (
    (
        "Head pose",
        "Two photos taken at different angles produce a residual that looks "
        "exactly like a shape change.",
        "pose_gate",
        "Pairs outside the yaw/pitch/roll budget are rejected before scoring, "
        "not corrected afterwards.",
    ),
    (
        "Expression",
        "A smile moves the mid-face by more than a decade of ageing does.",
        "expression_gate",
        "Expression is classified from landmark geometry and mismatched pairs "
        "are excluded.",
    ),
    (
        "Image quality",
        "A low-resolution or soft photo yields noisier landmarks, inflating "
        "the residual.",
        "quality_gate",
        "Low-quality pairs keep their measurement but their significance "
        "threshold is inflated.",
    ),
    (
        "Reconstruction error",
        "The 3D model itself is an estimate and differs slightly every time.",
        "noise_floor",
        "The null distribution is built from same-day pairs, which contain "
        "only this error and no real change.",
    ),
    (
        "Multiple comparisons",
        "Testing thousands of points and pairs guarantees some will look "
        "significant by chance.",
        "fdr",
        "All p-values are corrected across the run; only corrected q-values "
        "are reported.",
    ),
    (
        "Dating",
        "A change attributed to the wrong year is not evidence of anything.",
        "provenance_gate",
        "Photos with conflicting date sources are flagged and downgraded.",
    ),
    (
        "Ageing",
        "Faces change over time on their own.",
        "not_controlled",
        "NOT CONTROLLED BY THIS PIPELINE. Ageing is a real and expected cause "
        "of geometric change. Nothing here distinguishes it from any other "
        "cause, and no result should be read as excluding it.",
    ),
    (
        "Weight and health",
        "Weight change, illness, and medication visibly alter facial soft "
        "tissue.",
        "not_controlled",
        "NOT CONTROLLED BY THIS PIPELINE. These are ordinary explanations for "
        "soft-tissue change and remain fully available for any finding.",
    ),
)
