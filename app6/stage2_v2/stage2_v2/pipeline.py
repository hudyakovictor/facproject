"""Stage 2 orchestrator.

The measurement chain, in order:

    load -> temporal axis -> plan pairs -> gate -> align -> measure
         -> noise floor -> score -> multiple-testing correction -> artifacts

The step that carries the most weight is the noise floor. Without one, a
residual of 1.2 mm is just a number: it could be a real change or it could be
what this pipeline produces when handed two photos taken ten minutes apart.
The only way to tell is to measure the latter and subtract it.

So the floor is built from **same-day pairs**. Two photos of the same face on
the same day contain, by construction, zero real change. Whatever residual
they produce is the combined error of detection, reconstruction, and
alignment. That distribution is the null. A cross-date residual only counts as
evidence when it sits far outside it.

When a dataset has no same-day pairs, there is no null, and this module says so
and scores nothing. It does not fall back to an assumed sigma - an assumed
noise floor is how you manufacture significance.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import contract, geometry, stats, zones
from .gates import Verdict, pair_gate, photo_gate, temporal_axis, visibility_intersection
from .loader import LoadResult, Record, load_stage1
from .params import Params

SCHEMA = "deeputin-stage2-v2.0-rebuild"


@dataclass
class PairMeasurement:
    """One measured comparison between two photos."""

    pair_id: str
    photo_a: str
    photo_b: str
    date_a: str | None
    date_b: str | None
    pose_bin: str
    pair_type: str  # "same_day" | "adjacent" | "anchor" | "long_range"
    verdict: Verdict

    usable_points: int = 0
    rmse: float = float("nan")
    p95: float = float("nan")
    max_residual: float = float("nan")
    residual_tilt_deg: float = float("nan")
    coherence: float = float("nan")
    interocular: float = float("nan")

    #: RMSE expressed as a fraction of interocular distance, so magnitudes are
    #: comparable across photos of different sizes.
    rmse_ioc: float = float("nan")

    z_score: float = float("nan")
    p_value: float = float("nan")
    q_value: float = float("nan")
    significant: bool = False
    status: str = "not_scored"
    zone_metrics: dict = field(default_factory=dict)

    #: Set when at least one zone cleared correction, even if the global
    #: residual did not. This is the localised-change case.
    zone_significant: bool = False
    significant_zones: list = field(default_factory=list)

    @property
    def days_apart(self) -> int | None:
        if not (self.date_a and self.date_b):
            return None
        from datetime import date

        try:
            a = date.fromisoformat(self.date_a.replace("_", "-"))
            b = date.fromisoformat(self.date_b.replace("_", "-"))
        except ValueError:
            return None
        return abs((b - a).days)

    def to_json(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "photo_a": self.photo_a,
            "photo_b": self.photo_b,
            "date_a": self.date_a,
            "date_b": self.date_b,
            "days_apart": self.days_apart,
            "pose_bin": self.pose_bin,
            "pair_type": self.pair_type,
            "evidence_class": self.verdict.evidence_class,
            "limits": sorted(self.verdict.limits),
            "usable_points": self.usable_points,
            "rmse": _round(self.rmse),
            "rmse_ioc": _round(self.rmse_ioc),
            "p95": _round(self.p95),
            "max_residual": _round(self.max_residual),
            "residual_tilt_deg": _round(self.residual_tilt_deg, 4),
            "coherence": _round(self.coherence, 4),
            "z_score": _round(self.z_score, 4),
            "p_value": _round(self.p_value, 8),
            "q_value": _round(self.q_value, 8),
            "significant": self.significant,
            "zone_significant": self.zone_significant,
            "significant_zones": sorted(self.significant_zones),
            "status": self.status,
            "zone_metrics": self.zone_metrics,
        }


def _round(value: float, digits: int = 8) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


@dataclass
class RunResult:
    """Everything one Stage 2 run produced."""

    params: Params
    load: LoadResult
    axis: Verdict
    zone_map: zones.ZoneMap
    pairs: list[PairMeasurement] = field(default_factory=list)
    skipped: list[PairMeasurement] = field(default_factory=list)
    noise: dict = field(default_factory=dict)
    fdr: dict = field(default_factory=dict)
    zone_noise: dict = field(default_factory=dict)
    zone_fdr: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def scored(self) -> list[PairMeasurement]:
        return [p for p in self.pairs if p.status != "not_scored"]

    @property
    def significant(self) -> list[PairMeasurement]:
        return [p for p in self.pairs if p.significant]

    @property
    def zone_significant(self) -> list[PairMeasurement]:
        """Pairs with a localised change, whether or not the global test fired."""
        return [p for p in self.pairs if p.zone_significant]

    @property
    def any_significant(self) -> list[PairMeasurement]:
        return [p for p in self.pairs if p.significant or p.zone_significant]

    def manifest(self) -> dict:
        return {
            "schema": SCHEMA,
            "config_hash": self.params.hash(),
            "resume_hash": self.params.resume_hash(),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stage1": self.load.summary(),
            "temporal_axis": self.axis.to_json(),
            "zone_map": {
                "source": self.zone_map.source,
                "origin": self.zone_map.origin,
                "anatomical": self.zone_map.anatomical,
                "zone_count": len(self.zone_map.zones),
            },
            "pairs": {
                "planned": len(self.pairs) + len(self.skipped),
                "measured": len(self.pairs),
                "skipped": len(self.skipped),
                "scored": len(self.scored),
                "significant_global": len(self.significant),
                "significant_zone": len(self.zone_significant),
                "significant_any": len(self.any_significant),
                "by_evidence_class": _tally(
                    p.verdict.evidence_class for p in self.pairs
                ),
                "by_status": _tally(p.status for p in self.pairs),
                "skip_reasons": _tally(p.verdict.skip_reason for p in self.skipped),
            },
            "noise_model": self.noise,
            "multiple_testing": self.fdr,
            "zone_noise_model": self.zone_noise,
            "zone_multiple_testing": self.zone_fdr,
            "warnings": self.warnings,
        }


def _tally(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


# --------------------------------------------------------------------------
# Pair planning
# --------------------------------------------------------------------------
def plan_pairs(load: LoadResult, params: Params) -> list[tuple[Record, Record, str]]:
    """Decide which photo pairs to compare.

    Four kinds, each answering a different question:

    same_day    two photos from one day. Zero real change by construction, so
                these define the noise floor. Always planned regardless of the
                pairing switches - without them nothing can be scored.
    adjacent    consecutive dates. Catches change as it happens.
    anchor      earliest usable photo against every later one. Catches slow
                drift that adjacent pairs individually miss.
    long_range  full within-bin cross product. Expensive, off by default.
    """
    planned: list[tuple[Record, Record, str]] = []

    for pose_bin, records in load.by_bin().items():
        if len(records) < 2:
            continue

        by_date: dict[str, list[Record]] = {}
        for record in records:
            if record.date:
                by_date.setdefault(record.date, []).append(record)

        # same_day - the null distribution
        for same in by_date.values():
            for i in range(len(same)):
                for j in range(i + 1, len(same)):
                    planned.append((same[i], same[j], "same_day"))

        # one representative per date keeps cross-date pairing balanced, so a
        # day with twenty photos does not dominate the chronology
        dates = sorted(by_date)
        representatives = [by_date[d][0] for d in dates]

        if params["pair_adjacent"]:
            for i in range(len(representatives) - 1):
                planned.append((representatives[i], representatives[i + 1], "adjacent"))

        if params["pair_anchor"] and representatives:
            anchor = representatives[0]
            for later in representatives[2:]:
                planned.append((anchor, later, "anchor"))

        if params["pair_all_within_bin"]:
            for i in range(len(representatives)):
                for j in range(i + 1, len(representatives)):
                    if j - i > 1:
                        planned.append(
                            (representatives[i], representatives[j], "long_range")
                        )

    limit = params["max_pairs_per_bin"]
    if limit > 0:
        capped: list[tuple[Record, Record, str]] = []
        seen: dict[str, int] = {}
        for a, b, kind in planned:
            key = f"{a.pose_bin}:{kind}"
            if seen.get(key, 0) >= limit:
                continue
            seen[key] = seen.get(key, 0) + 1
            capped.append((a, b, kind))
        planned = capped

    return planned


# --------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------
def measure_pair(
    a: Record,
    b: Record,
    pair_type: str,
    params: Params,
    zone_map: zones.ZoneMap,
) -> PairMeasurement:
    """Gate, align, and measure one pair."""
    pair_id = f"{pair_type}__{a.photo_id}__{b.photo_id}"
    measurement = PairMeasurement(
        pair_id=pair_id,
        photo_a=a.photo_id,
        photo_b=b.photo_id,
        date_a=a.date,
        date_b=b.date,
        pose_bin=a.pose_bin,
        pair_type=pair_type,
        verdict=Verdict(),
    )

    measurement.verdict.merge(pair_gate(a, b, params))
    if not measurement.verdict.admitted:
        return measurement

    indices, visibility = visibility_intersection(a, b, params, scheme=134)
    measurement.verdict.merge(visibility)
    if not measurement.verdict.admitted:
        return measurement

    try:
        points_a = a.landmarks(134)[indices]
        points_b = b.landmarks(134)[indices]
    except (KeyError, IndexError) as exc:
        measurement.verdict.skip("landmarks_unreadable", detail=str(exc))
        return measurement

    try:
        align = geometry.trimmed_kabsch(
            points_a,
            points_b,
            trim_fraction=params["align_trim_fraction"],
            max_iterations=params["align_max_iterations"],
            min_points=params["min_points_134"],
        )
    except ValueError as exc:
        measurement.verdict.skip("alignment_failed", detail=str(exc))
        return measurement

    # A large residual rotation means the two shapes never reached a common
    # frame. Whatever residual remains is pose, not change.
    if align.residual_tilt_deg > params["residual_tilt_limit_deg"]:
        measurement.verdict.limit(
            "residual_tilt_limited",
            value=align.residual_tilt_deg,
            threshold=params["residual_tilt_limit_deg"],
        )

    vectors = geometry.displacement_vectors(points_a, points_b, align)

    # Normalise by interocular distance so magnitudes compare across photos.
    try:
        full_a = a.landmarks(134)
        ioc = geometry.interocular_distance(full_a, 36, 45)
    except (KeyError, IndexError):
        ioc = float("nan")

    measurement.usable_points = int(indices.size)
    measurement.rmse = align.rmse
    measurement.p95 = align.percentile(95)
    measurement.max_residual = float(np.max(align.residuals))
    measurement.residual_tilt_deg = align.residual_tilt_deg
    measurement.coherence = geometry.coherence(vectors)
    measurement.interocular = ioc
    measurement.rmse_ioc = align.rmse / ioc if np.isfinite(ioc) and ioc > 0 else float("nan")

    local_zones = {
        name: [int(np.flatnonzero(indices == i)[0]) for i in idx if i in set(indices.tolist())]
        for name, idx in zone_map.zones.items()
    }
    zone_result = geometry.zone_residuals(
        align.residuals, vectors, local_zones, min_points=3
    )
    measurement.zone_metrics = {
        name: zone.to_json() for name, zone in sorted(zone_result.items())
    }

    measurement.status = "measured"
    a.release()
    b.release()
    return measurement


# --------------------------------------------------------------------------
# Noise floor and scoring
# --------------------------------------------------------------------------
def build_noise_floor(
    measured: list[PairMeasurement], params: Params
) -> dict:
    """Derive the per-pose-bin null distribution from same-day pairs."""
    same_day = [
        p for p in measured if p.pair_type == "same_day" and np.isfinite(p.rmse_ioc)
    ]
    per_bin: dict[str, dict] = {}
    groups: dict[str, list[float]] = {}
    for pair in same_day:
        groups.setdefault(pair.pose_bin, []).append(pair.rmse_ioc)

    for pose_bin, values in sorted(groups.items()):
        arr = np.asarray(values, dtype=np.float64)
        if arr.size < params["min_reference_pairs"]:
            per_bin[pose_bin] = {
                "status": "insufficient_reference",
                "n": int(arr.size),
                "required": params["min_reference_pairs"],
            }
            continue
        per_bin[pose_bin] = {
            "status": "ok",
            "n": int(arr.size),
            "median": float(np.median(arr)),
            "mad_sigma": stats.mad(arr),
            "p95": float(np.quantile(arr, params["calibration_quantile"])),
        }

    usable = [b for b in per_bin.values() if b.get("status") == "ok"]
    return {
        "policy": "same_day_pairs_as_null_v1",
        "source": "same-day photo pairs (zero true change by construction)",
        "quantile": params["calibration_quantile"],
        "same_day_pairs": len(same_day),
        "per_pose_bin": per_bin,
        "usable_bins": len(usable),
        "status": "ok" if usable else "no_reference",
    }


def score_pairs(
    measured: list[PairMeasurement], noise: dict, params: Params
) -> dict:
    """Turn residuals into z, p, and FDR-corrected q values."""
    if noise.get("status") != "ok":
        for pair in measured:
            if pair.pair_type != "same_day":
                pair.status = "unscored_no_noise_reference"
        return {
            "status": "skipped_no_noise_reference",
            "reason": (
                "no same-day pairs survived gating, so the noise floor is "
                "unknown and no residual can be called significant"
            ),
        }

    per_bin = noise["per_pose_bin"]
    candidates = [p for p in measured if p.pair_type != "same_day"]

    for pair in candidates:
        reference = per_bin.get(pair.pose_bin)
        if not reference or reference.get("status") != "ok":
            pair.status = "unscored_no_bin_reference"
            pair.verdict.limit("calibration_limited", pose_bin=pair.pose_bin)
            continue
        if not np.isfinite(pair.rmse_ioc):
            pair.status = "unscored_no_measurement"
            continue

        sigma = reference["mad_sigma"]
        if not np.isfinite(sigma) or sigma <= 0.0:
            pair.status = "unscored_degenerate_noise"
            pair.verdict.limit("calibration_limited", reason="degenerate_sigma")
            continue

        # Inflate the effective sigma for lower-quality strata rather than
        # excluding those photos: a noisier measurement must clear a higher bar.
        inflation = 1.0
        for limit in pair.verdict.limits:
            if limit in {"quality_limited", "resolution_mismatch_limited"}:
                inflation = max(inflation, params.quality_inflation_map["low"])
            elif limit in {"texture_quality_unknown", "cross_bin_limited"}:
                inflation = max(inflation, params.quality_inflation_map["mixed"])

        pair.z_score = (pair.rmse_ioc - reference["median"]) / (sigma * inflation)
        pair.p_value = float(stats.normal_sf(pair.z_score))

    scorable = [p for p in candidates if np.isfinite(p.p_value)]
    if not scorable:
        return {"status": "no_scorable_pairs"}

    result = stats.adjust_p_values(
        np.asarray([p.p_value for p in scorable]),
        method=params["fdr_method"],
        level=params["fdr_level"],
    )
    for pair, q_value, rejected in zip(scorable, result.q_values, result.rejected):
        pair.q_value = float(q_value)
        pair.significant = bool(rejected)
        if not rejected:
            pair.status = "within_noise"
        elif pair.coherence >= params["min_coherent_motion_fraction"]:
            pair.status = "coherent_change_candidate"
        else:
            pair.status = "scattered_or_uncertain"

    payload = result.to_json()
    payload["status"] = "ok"
    payload["significance_note"] = (
        "q-values are corrected across all scored pairs in this run; "
        "an uncorrected p-value is not a finding"
    )
    return payload


# --------------------------------------------------------------------------
# Zone-level noise and scoring
# --------------------------------------------------------------------------
# Why this exists.
#
# The global RMSE is an average over every landmark. A change confined to a
# small region moves that average by almost nothing: on the project's own
# fixture, a deliberately injected 1% displacement across 16 of 134 landmarks
# produced a *lower* global residual than same-day noise, and scored z = -8.
# The signal was real, present, and completely invisible to the global
# statistic.
#
# That is not a tuning problem. Averaging a localised change over 134 points
# dilutes it by construction, and no threshold on the diluted number can
# recover it. Localised change is the entire subject of this analysis, so it
# needs a statistic that does not average it away.
#
# So each zone gets its own null, built from the same-day pairs, and is scored
# against it. Zone tests join the same correction family as the global tests -
# adding tests without adding correction is how a dilution problem becomes a
# false-positive problem.
def _noise_reference(values: np.ndarray, params: Params, min_pairs: int) -> dict:
    """Build one null distribution, refusing the estimates we cannot trust.

    Returns a reference whose `sigma_used` is deliberately more conservative
    than the MAD point estimate. Three refusals are possible, and each is
    reported rather than silently coerced into a usable number:

    * too few observations to estimate a scale at all;
    * a scale that collapsed to near zero relative to its own median, which
      is the signature of a small-sample MAD accident rather than genuine
      precision;
    * a non-finite or zero scale.

    The bootstrap percentile is the important part. A point-estimate sigma
    treats the scale as known, and dividing by an underestimated scale is
    exactly how a null result becomes a confident false positive. Taking an
    upper percentile of the bootstrapped sigma propagates the uncertainty in
    the scale into the score, in the conservative direction.
    """
    n = int(values.size)
    if n < min_pairs:
        return {
            "status": "insufficient_reference",
            "n": n,
            "required": int(min_pairs),
            "reason": (
                "too few same-day pairs to estimate a noise scale that can "
                "support a significance claim"
            ),
        }

    median = float(np.median(values))
    point_sigma = stats.mad(values)

    if not np.isfinite(point_sigma) or point_sigma <= 0.0:
        return {
            "status": "degenerate_reference",
            "n": n,
            "median": median,
            "mad_sigma": None if not np.isfinite(point_sigma) else float(point_sigma),
            "reason": "noise scale is zero or undefined",
        }

    ratio = point_sigma / abs(median) if median else float("inf")
    if ratio < params["min_sigma_to_median_ratio"]:
        return {
            "status": "collapsed_reference",
            "n": n,
            "median": median,
            "mad_sigma": float(point_sigma),
            "sigma_to_median_ratio": float(ratio),
            "required_ratio": params["min_sigma_to_median_ratio"],
            "reason": (
                "noise scale is implausibly small next to its own median, "
                "which indicates a small-sample estimate that collapsed "
                "rather than a genuinely precise measurement"
            ),
        }

    # Bootstrap the scale so its own uncertainty enters the score.
    rng = np.random.default_rng(params["random_seed"])
    iterations = max(200, int(params["bootstrap_iterations"]))
    draws = rng.integers(0, n, size=(iterations, n))
    sigmas = np.array([stats.mad(values[row]) for row in draws], dtype=np.float64)
    sigmas = sigmas[np.isfinite(sigmas) & (sigmas > 0.0)]

    if sigmas.size < 20:
        return {
            "status": "degenerate_reference",
            "n": n,
            "median": median,
            "mad_sigma": float(point_sigma),
            "reason": "bootstrap of the noise scale did not converge",
        }

    sigma_used = float(
        np.percentile(sigmas, params["sigma_confidence_percentile"])
    )
    sigma_used = max(sigma_used, float(point_sigma))

    return {
        "status": "ok",
        "n": n,
        "median": median,
        "mad_sigma": float(point_sigma),
        "sigma_used": sigma_used,
        "sigma_percentile": params["sigma_confidence_percentile"],
        "sigma_to_median_ratio": float(ratio),
        "p95": float(np.percentile(values, 95)),
    }


def build_zone_noise_floor(
    measured: list[PairMeasurement], params: Params
) -> dict:
    """Per-zone, per-pose-bin null distributions from same-day pairs."""
    same_day = [p for p in measured if p.pair_type == "same_day"]
    groups: dict[str, dict[str, list[float]]] = {}

    for pair in same_day:
        for zone, metrics in pair.zone_metrics.items():
            rmse = metrics.get("rmse")
            if rmse is None or not np.isfinite(rmse):
                continue
            groups.setdefault(pair.pose_bin, {}).setdefault(zone, []).append(
                float(rmse)
            )

    per_bin: dict[str, dict] = {}
    usable = 0
    for pose_bin, zone_values in sorted(groups.items()):
        per_zone: dict[str, dict] = {}
        for zone, values in sorted(zone_values.items()):
            arr = np.asarray(values, dtype=np.float64)
            reference = _noise_reference(
                arr, params, params["min_zone_reference_pairs"]
            )
            per_zone[zone] = reference
            if reference["status"] == "ok":
                usable += 1
        per_bin[pose_bin] = per_zone

    return {
        "policy": "per_zone_same_day_null_v1",
        "rationale": (
            "a change confined to one region is averaged away by the global "
            "residual, so each zone is scored against its own null"
        ),
        "per_pose_bin": per_bin,
        "usable_zone_nulls": usable,
        "status": "ok" if usable else "no_reference",
    }


def score_zones(
    measured: list[PairMeasurement], zone_noise: dict, params: Params
) -> dict:
    """Score every zone of every cross-date pair against its own null."""
    if zone_noise.get("status") != "ok":
        return {"status": "skipped_no_zone_reference"}

    per_bin = zone_noise["per_pose_bin"]
    entries: list[tuple[PairMeasurement, str, float]] = []

    for pair in measured:
        if pair.pair_type == "same_day":
            continue
        reference_bin = per_bin.get(pair.pose_bin, {})
        for zone, metrics in pair.zone_metrics.items():
            reference = reference_bin.get(zone)
            rmse = metrics.get("rmse")
            if not reference or reference.get("status") != "ok":
                # Carry the refusal reason through to the artifact, so a zone
                # that could not be tested is distinguishable from a zone that
                # was tested and found quiet.
                metrics["zone_status"] = (
                    f"unscored_{reference['status']}"
                    if reference
                    else "unscored_no_reference"
                )
                if reference and reference.get("reason"):
                    metrics["zone_unscored_reason"] = reference["reason"]
                continue
            if rmse is None or not np.isfinite(rmse):
                metrics["zone_status"] = "unscored_no_measurement"
                continue
            sigma = reference["sigma_used"]
            if not np.isfinite(sigma) or sigma <= 0.0:
                metrics["zone_status"] = "unscored_degenerate_noise"
                continue

            inflation = 1.0
            for limit in pair.verdict.limits:
                if limit in {"quality_limited", "resolution_mismatch_limited"}:
                    inflation = max(inflation, params.quality_inflation_map["low"])
                elif limit in {"texture_quality_unknown", "cross_bin_limited"}:
                    inflation = max(inflation, params.quality_inflation_map["mixed"])

            z = (float(rmse) - reference["median"]) / (sigma * inflation)
            p = float(stats.normal_sf(z))
            metrics["zone_z"] = round(z, 4)
            metrics["zone_p"] = p
            metrics["zone_status"] = "scored"
            entries.append((pair, zone, p))

    if not entries:
        return {"status": "no_scorable_zones"}

    result = stats.adjust_p_values(
        np.asarray([p for _, _, p in entries]),
        method=params["fdr_method"],
        level=params["fdr_level"],
    )

    for (pair, zone, _), q_value, rejected in zip(
        entries, result.q_values, result.rejected
    ):
        metrics = pair.zone_metrics[zone]
        metrics["zone_q"] = float(q_value)
        metrics["zone_significant"] = bool(rejected)
        if rejected:
            pair.significant_zones.append(zone)

    for pair in measured:
        if pair.significant_zones:
            pair.zone_significant = True
            # A pair whose global residual sat inside the noise but which has a
            # significant zone is exactly the localised case the global test
            # cannot see. Name that state rather than leaving it as
            # `within_noise`, which would read as "nothing here".
            if pair.status == "within_noise":
                pair.status = "localized_change_candidate"

    payload = result.to_json()
    payload["status"] = "ok"
    payload["zone_tests"] = len(entries)
    payload["note"] = (
        "zone tests are corrected in their own family across the run; a zone "
        "q-value is not comparable to an uncorrected p-value"
    )
    return payload


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def run(
    stage1_root: Path,
    params: Params,
    *,
    project_root: Path | None = None,
) -> RunResult:
    """Execute a full Stage 2 pass."""
    started = time.time()
    stage1_root = Path(stage1_root)

    load = load_stage1(stage1_root, params)
    zone_map = zones.resolve(project_root, scheme=134)
    axis = temporal_axis(load.records, params)

    result = RunResult(params=params, load=load, axis=axis, zone_map=zone_map)

    if zone_map.source == "partition":
        result.warnings.append(
            "zone map is a neutral index partition, not a measured atlas: "
            "zone-level results carry no anatomical meaning and must not be "
            "described in anatomical language"
        )

    if not load.records:
        result.warnings.append("no usable Stage 1 records; nothing to measure")
        result.elapsed_seconds = time.time() - started
        return result

    # Photos that cannot enter any pair are dropped once, here.
    usable: list[Record] = []
    for record in load.records:
        verdict = photo_gate(record, params)
        if verdict.admitted:
            usable.append(record)
    dropped = len(load.records) - len(usable)
    if dropped:
        result.warnings.append(f"{dropped} photo(s) excluded by per-photo gates")
    load.records = usable

    if not axis.admitted:
        result.warnings.append(
            "no temporal axis: the dataset cannot support any claim about "
            "change over time. Same-day pairs are still measured so the noise "
            "floor can be characterised."
        )

    planned = plan_pairs(load, params)
    for a, b, pair_type in planned:
        # Without a temporal axis, only same-day pairs are meaningful.
        if not axis.admitted and pair_type != "same_day":
            continue
        measurement = measure_pair(a, b, pair_type, params, zone_map)
        if measurement.verdict.admitted:
            result.pairs.append(measurement)
        else:
            result.skipped.append(measurement)
        if params["fail_fast"] and not measurement.verdict.admitted:
            break

    result.noise = build_noise_floor(result.pairs, params)
    result.fdr = score_pairs(result.pairs, result.noise, params)

    # Zone scoring runs after the global pass so it can see, and upgrade, the
    # pairs the global statistic left as `within_noise`.
    result.zone_noise = build_zone_noise_floor(result.pairs, params)
    result.zone_fdr = score_zones(result.pairs, result.zone_noise, params)

    localized = [
        p for p in result.pairs if p.zone_significant and not p.significant
    ]
    if localized:
        result.warnings.append(
            f"{len(localized)} pair(s) show a significant change in at least "
            "one zone while their whole-face residual stayed inside the noise. "
            "This is the localised-change case: the global average dilutes a "
            "regional shift. Read the zone results, not the headline residual."
        )

    if result.noise.get("status") != "ok":
        result.warnings.append(
            "no usable noise floor: same-day pairs were absent or too few, so "
            "no residual in this run can be called significant"
        )

    result.elapsed_seconds = time.time() - started
    return result


def write_artifacts(result: RunResult, output_dir: Path) -> list[Path]:
    """Write the machine-readable outputs of a run."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def dump(name: str, payload) -> None:
        path = output_dir / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        tmp.replace(path)
        written.append(path)

    dump("analysis_manifest.json", result.manifest())
    dump("params.json", result.params.to_json())
    dump("zone_map.json", result.zone_map.to_json())
    dump("calibration_noise_model.json", result.noise)
    dump("multiple_testing.json", result.fdr)
    dump("zone_noise_model.json", result.zone_noise)
    dump("zone_multiple_testing.json", result.zone_fdr)
    dump("pair_metrics.json", [p.to_json() for p in result.pairs])
    dump(
        "skipped_pairs.json",
        [
            {
                "pair_id": p.pair_id,
                "photo_a": p.photo_a,
                "photo_b": p.photo_b,
                "pair_type": p.pair_type,
                "skip_reason": p.verdict.skip_reason,
                "trace": p.verdict.trace,
            }
            for p in result.skipped
        ],
    )
    dump("stage1_load_report.json", {
        "summary": result.load.summary(),
        "failures": [f.to_json() for f in result.load.failures],
    })

    # CSV for the pairs, because that is what a reviewer opens first.
    import csv

    csv_path = output_dir / "pair_metrics.csv"
    columns = [
        "pair_id", "photo_a", "photo_b", "date_a", "date_b", "days_apart",
        "pose_bin", "pair_type", "evidence_class", "usable_points",
        "rmse_ioc", "coherence", "z_score", "q_value", "significant", "status",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for pair in result.pairs:
            row = pair.to_json()
            row["days_apart"] = pair.days_apart
            writer.writerow(row)
    written.append(csv_path)

    return written
