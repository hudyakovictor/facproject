"""Stage 2 parameter registry - the single source of truth for every tunable.

Why this exists
---------------
In legacy Stage 2 the ~60 thresholds that decide whether a pair is analysed,
skipped or flagged were scattered as module-level constants across 50+ files,
sometimes duplicated with different values (MIN_ALIGNMENT_QUALITY existed in
engine.py, chronology.py AND analysis_policy.py). Changing one meant grepping
the whole tree and hoping.

Here every tunable is declared once with type, bounds, default, unit, group and
a human description. From that declaration we get for free:
  * validation, so an invalid threshold cannot reach the pipeline;
  * a JSON profile format with a content hash for reproducibility;
  * the admin panel UI, which renders itself from this registry;
  * profile diffing, so the run manifest records exactly what changed.

No Stage 2 module may read a bare constant. Everything reads Params.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import contract

PARAMS_SCHEMA = "deeputin-stage2-params-v2.0"

ParamKind = Literal["float", "int", "bool", "choice", "str", "float_list", "str_list"]


@dataclass(frozen=True)
class ParamSpec:
    """Declarative description of one tunable parameter."""

    key: str
    group: str
    kind: ParamKind
    default: Any
    title: str
    description: str
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[Any, ...] = ()
    impact: Literal["low", "medium", "high", "critical"] = "medium"
    breaks_resume: bool = True
    provenance: str = ""

    def coerce(self, value: Any) -> Any:
        """Convert an external (JSON or form-post) value to the declared type."""
        if self.kind == "bool":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        if self.kind == "int":
            return int(round(float(value)))
        if self.kind == "float":
            return float(value)
        if self.kind == "float_list":
            if isinstance(value, str):
                value = [p for p in value.replace(",", " ").split() if p]
            return [float(v) for v in value]
        if self.kind == "str_list":
            if isinstance(value, str):
                value = [p.strip() for p in value.split(",") if p.strip()]
            return [str(v) for v in value]
        return str(value)

    def validate(self, value: Any) -> list[str]:
        """Return a list of human-readable problems (empty means valid)."""
        errors: list[str] = []
        if self.kind in {"float", "int"}:
            if self.minimum is not None and value < self.minimum:
                errors.append(f"{self.key}={value} below minimum {self.minimum}")
            if self.maximum is not None and value > self.maximum:
                errors.append(f"{self.key}={value} above maximum {self.maximum}")
        if self.kind == "choice" and value not in self.choices:
            errors.append(f"{self.key}={value!r} not one of {list(self.choices)}")
        if self.kind == "float_list":
            if self.minimum is not None and any(v < self.minimum for v in value):
                errors.append(f"{self.key} contains a value below {self.minimum}")
            if self.maximum is not None and any(v > self.maximum for v in value):
                errors.append(f"{self.key} contains a value above {self.maximum}")
        return errors

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "group": self.group,
            "kind": self.kind,
            "default": self.default,
            "title": self.title,
            "description": self.description,
            "unit": self.unit,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "choices": list(self.choices),
            "impact": self.impact,
            "breaks_resume": self.breaks_resume,
            "provenance": self.provenance,
        }


def _p(*args, **kwargs) -> ParamSpec:
    return ParamSpec(*args, **kwargs)


GROUPS: tuple[tuple[str, str], ...] = (
    ("space", "Coordinate space and alignment"),
    ("pairing", "Pair planning"),
    ("pose", "Pose gates"),
    ("expression", "Expression gates"),
    ("quality", "Image quality gates"),
    ("visibility", "Visibility gates"),
    ("calibration", "Calibration noise model"),
    ("statistics", "Scoring and multiple testing"),
    ("chronology", "Temporal analysis"),
    ("texture", "Texture channel"),
    ("mesh", "Dense mesh channel"),
    ("runtime", "Runtime and reproducibility"),
)


SPECS_PART1: tuple[ParamSpec, ...] = (
    # ---------------- space -------------------------------------------------
    _p("analysis_space", "space", "choice", "raw_object_normalized",
       "Primary coordinate space",
       "Space in which the primary pair residual is measured. "
       "Chronology-aligned coordinates are diagnostic only: they absorb real "
       "change and amplify pose residuals.",
       choices=contract.ALLOWED_ANALYSIS_SPACES, impact="critical",
       provenance="chronology space scored lower AUC than raw on calibration"),
    _p("align_trim_fraction", "space", "float", 0.15,
       "Kabsch trim fraction",
       "Fraction of the highest-residual correspondences dropped on each "
       "trimmed-Kabsch iteration, so a large local change is not absorbed "
       "into the global rigid transform.",
       minimum=0.0, maximum=0.4, impact="critical"),
    _p("align_max_iterations", "space", "int", 5,
       "Kabsch iterations", "Maximum trimmed-Kabsch refinement iterations.",
       minimum=1, maximum=25, impact="low"),
    _p("align_estimate_scale", "space", "bool", False,
       "Estimate scale",
       "Never enable for evidence runs: a free scale term absorbs real "
       "volumetric change. Diagnostic use only.",
       impact="critical"),
    _p("min_points_106", "space", "int", 24,
       "Min visible LDM106 points",
       "Minimum jointly-visible 106-scheme landmarks required before a pair "
       "is measured.",
       minimum=8, maximum=106, impact="high"),
    _p("min_points_134", "space", "int", 30,
       "Min visible LDM134 points",
       "Minimum jointly-visible 134-scheme landmarks required before a pair "
       "is measured.",
       minimum=8, maximum=134, impact="high"),

    # ---------------- pairing -----------------------------------------------
    _p("pair_adjacent", "pairing", "bool", True,
       "Adjacent pairs",
       "Compare each photo with its immediate temporal neighbour inside the "
       "same pose bin.", impact="high"),
    _p("pair_anchor", "pairing", "bool", True,
       "Anchor pairs",
       "Compare every photo against the earliest valid photo of its pose bin "
       "(baseline and cumulative drift channel).", impact="high"),
    _p("pair_all_within_bin", "pairing", "bool", False,
       "All-vs-all inside bin",
       "Exhaustive pairing, O(n^2). Audits and small datasets only: it "
       "greatly increases the multiple-testing burden.", impact="high"),
    _p("max_pairs_per_bin", "pairing", "int", 0,
       "Max pairs per bin", "0 means unlimited. Caps runtime on large bins.",
       minimum=0, maximum=1000000, impact="low"),
    _p("cross_bin_pairs", "pairing", "bool", False,
       "Allow cross-bin pairs",
       "Comparing photos from different pose bins leaks pose into the "
       "residual. Rejected before scoring by default.", impact="critical"),
    _p("exclude_near_duplicates", "pairing", "bool", False,
       "Drop near-duplicate pairs",
       "Skip pairs where either photo was flagged a perceptual near-duplicate. "
       "When off the pair is kept but downgraded to near_duplicate_limited.",
       impact="medium"),

    # ---------------- pose --------------------------------------------------
    _p("max_yaw_gap_deg", "pose", "float", 6.0,
       "Max yaw gap", "Maximum in-bin yaw difference tolerated inside a pair.",
       unit="deg", minimum=0.0, maximum=90.0, impact="critical"),
    _p("pitch_to_yaw_sensitivity", "pose", "float", 1.77,
       "Pitch/yaw sensitivity",
       "Measured ratio of residual sensitivity to pitch versus yaw. The pitch "
       "budget is max_yaw_gap divided by this value.",
       minimum=0.1, maximum=10.0, impact="high",
       provenance="calibration atlas regression"),
    _p("roll_to_yaw_sensitivity", "pose", "float", 1.37,
       "Roll/yaw sensitivity",
       "Measured ratio of residual sensitivity to roll versus yaw.",
       minimum=0.1, maximum=10.0, impact="high",
       provenance="calibration atlas regression"),
    _p("profile_sub_bin_width_deg", "pose", "float", 10.0,
       "Profile sub-bin width",
       "Profile bins span 45 deg of yaw, far too wide to compare directly, so "
       "they are split into sub-bins of this width.",
       unit="deg", minimum=1.0, maximum=45.0, impact="high"),
    _p("profile_sub_bin_max_yaw_gap_deg", "pose", "float", 2.0,
       "Max yaw gap (profile)",
       "Tighter yaw budget applied inside profile sub-bins.",
       unit="deg", minimum=0.0, maximum=45.0, impact="high"),
    _p("residual_tilt_limit_deg", "pose", "float", 10.0,
       "Residual tilt limit",
       "Post-alignment residual rotation above this angle downgrades the pair "
       "to residual_tilt_limited.",
       unit="deg", minimum=0.0, maximum=90.0, impact="high"),
    _p("pose_leakage_distance_threshold", "pose", "float", 1.0,
       "Pose-leakage distance",
       "Global pose leakage only downgrades pairs whose pose distance exceeds "
       "this value, so frontal-to-frontal pairs are unaffected.",
       minimum=0.0, maximum=100.0, impact="medium"),
    _p("limited_bins", "pose", "str_list", ["right_profile"],
       "Structurally limited bins",
       "Bins whose calibration support is known to be too thin for primary "
       "evidence. Results are kept but marked limited.", impact="medium"),

    # ---------------- expression -------------------------------------------
    _p("expression_source", "expression", "choice", "geometry_landmarks",
       "Expression detector",
       "Geometric landmark ratios, not the BFM alpha_exp norm: alpha_exp has "
       "no physical threshold and does not separate calm faces from smiles on "
       "the calibration set.",
       choices=("geometry_landmarks", "alpha_exp", "disabled"),
       impact="critical", provenance="geometry separated calm from smiling 100%"),
    _p("corner_lift_threshold", "expression", "float", 0.005,
       "Smile threshold (corner lift)",
       "corner_lift_ioc is mean y of the mouth corners minus mean y of the "
       "mouth centre, divided by interocular distance. Above this the photo "
       "counts as smiling.",
       minimum=-1.0, maximum=1.0, impact="critical",
       provenance="calm <= -0.0106, smiling >= +0.0166 on calibration"),
    _p("jaw_open_threshold", "expression", "float", 0.28,
       "Open-mouth threshold",
       "jaw_open_ratio is the lip gap divided by interocular distance.",
       minimum=0.0, maximum=2.0, impact="critical",
       provenance="calm <= 0.1711, open mouth 0.3955 on calibration"),
    _p("expression_policy", "expression", "choice", "exclude_mismatch",
       "Expression pair policy",
       "exclude_any drops a pair if either photo has an expression; "
       "exclude_mismatch drops only when the two photos disagree; "
       "stratify keeps the pair and inflates its threshold instead.",
       choices=("exclude_any", "exclude_mismatch", "stratify", "off"),
       impact="critical"),
    _p("max_jaw_degree_gap", "expression", "float", 8.0,
       "Max jaw-angle gap", "Maximum jaw opening difference within a pair.",
       unit="deg", minimum=0.0, maximum=90.0, impact="medium"),
    _p("jaw_degree_gap_enforced", "expression", "bool", False,
       "Enforce jaw-angle gap",
       "The degree gate is measured and reported but suspended until it is "
       "calibrated. Enabling it will start dropping pairs.",
       impact="high"),
    _p("cross_era_stratum", "expression", "bool", True,
       "Separate cross-era stratum",
       "A jaw-state mismatch between different eras becomes its own stratum "
       "rather than a silent exclusion.", impact="medium"),
)
SPECS_PART2: tuple[ParamSpec, ...] = (
    # ---------------- quality ----------------------------------------------
    _p("detection_confidence_low", "quality", "float", 0.50,
       "Detector confidence: low",
       "Below this the photo falls into the low quality stratum.",
       minimum=0.0, maximum=1.0, impact="high"),
    _p("detection_confidence_high", "quality", "float", 0.70,
       "Detector confidence: high",
       "At or above this the photo is in the high quality stratum.",
       minimum=0.0, maximum=1.0, impact="high"),
    _p("min_face_area_ratio", "quality", "float", 0.01,
       "Min face area ratio",
       "Face bounding box area as a fraction of the image. Tiny faces carry "
       "too little geometric signal to measure.",
       minimum=0.0, maximum=1.0, impact="high"),
    _p("quality_inflation", "quality", "float_list", [1.00, 1.45, 2.05],
       "Threshold inflation (high, mixed, low)",
       "Per-stratum multiplier applied to the calibrated threshold, so a "
       "noisier stratum must clear a higher bar.",
       minimum=1.0, maximum=10.0, impact="critical"),
    _p("max_resolution_ratio", "quality", "float", 2.0,
       "Max resolution ratio",
       "Maximum megapixel ratio between the two photos of a pair.",
       minimum=1.0, maximum=100.0, impact="medium"),
    _p("min_texture_quality", "quality", "float", 0.35,
       "Min texture quality",
       "Global texture quality below this marks the pair quality_limited. "
       "Read from texture.json quality. Legacy Stage 2 read a key that never "
       "existed and silently substituted 0.0, which limited every pair.",
       minimum=0.0, maximum=1.0, impact="high"),
    _p("min_alignment_quality", "quality", "float", 0.5,
       "Min alignment quality",
       "Reference value only while alignment_quality_gates is off.",
       minimum=0.0, maximum=1.0, impact="medium"),
    _p("alignment_quality_gates", "quality", "bool", False,
       "Alignment quality gates pairs",
       "D-003: alignment_quality is uncorrelated with the residual (Spearman "
       "+0.096 over 212 frames versus -0.176 in the atlas), so it does not "
       "gate pairs. Kept switchable for re-testing.",
       impact="high", provenance="D-003 2026-08-03"),
    _p("fail_closed_missing_qc", "quality", "bool", True,
       "Fail closed on missing QC",
       "A photo without mandatory QC fields is excluded rather than assumed "
       "good. Never disable for evidence runs.", impact="critical"),

    # ---------------- visibility -------------------------------------------
    _p("visibility_policy", "visibility", "choice", "intersection_fail_closed",
       "Visibility policy",
       "Only landmarks visible in BOTH photos may enter the residual. A union "
       "policy would compare invented geometry.",
       choices=("intersection_fail_closed", "intersection_soft", "union"),
       impact="critical"),
    _p("visibility_source", "visibility", "choice", "combined",
       "Visibility source",
       "combined means front-facing AND renderer-visible.",
       choices=("combined", "front_facing", "renderer"), impact="high"),
    _p("per_bin_anchor", "visibility", "bool", True,
       "Per-bin anchor subsets",
       "Use calibration-ranked landmark utility per pose bin when choosing "
       "alignment anchors, falling back to the global stable subset.",
       impact="high"),

    # ---------------- calibration ------------------------------------------
    _p("calibration_policy", "calibration", "choice",
       "equal_person_median_of_quantiles",
       "Calibration aggregation",
       "Per-person quantiles are computed first and then combined, so a "
       "person contributing many frames cannot dominate the noise floor.",
       choices=("equal_person_median_of_quantiles", "pooled_quantile",
                "equal_person_mean"),
       impact="critical"),
    _p("calibration_quantile", "calibration", "float", 0.95,
       "Calibration quantile",
       "Quantile of the same-person noise distribution used as the threshold.",
       minimum=0.5, maximum=0.9999, impact="critical"),
    _p("min_reference_persons", "calibration", "int", 3,
       "Min reference persons",
       "A pose/metric reference built from fewer people is marked sparse and "
       "the pairs relying on it become calibration_limited.",
       minimum=1, maximum=100, impact="critical"),
    _p("min_reference_pairs", "calibration", "int", 5,
       "Min reference pairs",
       "Minimum same-person pairs behind one reference.",
       minimum=1, maximum=10000, impact="high"),
    _p("min_zone_reference_pairs", "calibration", "int", 20,
       "Min zone reference pairs",
       "Minimum same-day pairs required before a per-zone noise reference may "
       "support a significance claim. Zone nulls rest on far less data than "
       "the global null, so they need a higher floor. Below this the zone is "
       "reported as insufficient_reference and yields no p-value. Exists "
       "because a 6-pair zone null produced a confident false positive on "
       "the project fixture.",
       minimum=2, maximum=10000, impact="critical"),
    _p("sigma_confidence_percentile", "calibration", "float", 84.0,
       "Conservative sigma percentile",
       "Scoring divides by this percentile of a bootstrap distribution of "
       "sigma rather than by the point estimate. An upper percentile makes "
       "the divisor larger and the significance smaller, which is the right "
       "direction to err when the scale itself is uncertain. Set to 50 for "
       "the plain point estimate.",
       unit="percentile", minimum=50.0, maximum=99.0, impact="critical"),
    _p("min_sigma_to_median_ratio", "calibration", "float", 0.05,
       "Min sigma/median ratio",
       "A reference whose sigma falls below this fraction of its own median "
       "is treated as a collapsed estimate, not a precise one, and refused. "
       "Guards the tiny-n MAD collapse that manufactures false significance.",
       minimum=0.0, maximum=1.0, impact="critical"),
    _p("stratified_references", "calibration", "bool", True,
       "Stratified references",
       "Build separate noise references per quality stratum when support "
       "allows, instead of inflating a single reference.", impact="high"),
    _p("leave_one_dataset_out", "calibration", "bool", True,
       "Leave-one-person-out sensitivity",
       "Refit the noise model without each calibration person to detect "
       "references that depend on a single subject.", impact="high"),
    _p("sensitivity_max_shift", "calibration", "float", 0.25,
       "Max stable threshold shift",
       "Relative threshold movement above which a reference is unstable.",
       minimum=0.0, maximum=10.0, impact="high"),
    _p("subtract_angle_noise", "calibration", "bool", True,
       "Subtract differential angle noise",
       "Match each pair to same-person calibration pairs with a comparable "
       "angle delta and subtract that noise component.", impact="high"),
    _p("angle_noise_tolerance", "calibration", "float_list", [2.0, 1.0, 1.0],
       "Angle match tolerance (yaw, pitch, roll)",
       "How closely a calibration pair must match the measured pair angle "
       "delta to be usable for noise subtraction.",
       unit="deg", minimum=0.0, maximum=45.0, impact="high"),
    _p("yaw_range_guard", "calibration", "bool", True,
       "Guard calibration yaw range",
       "Mark a pair calibration_limited when either photo yaw falls outside "
       "the yaw range actually covered by calibration in that bin. Without "
       "this the model silently extrapolates.", impact="critical"),

    # ---------------- statistics -------------------------------------------
    _p("score_statistic", "statistics", "choice", "robust_z",
       "Score statistic",
       "robust_z uses median and MAD, so a few extreme calibration frames "
       "cannot inflate the noise floor.",
       choices=("robust_z", "z", "quantile_rank"), impact="critical"),
    _p("significance_z", "statistics", "float", 3.0,
       "Significance threshold",
       "Robust-z above which a point or metric counts as significant.",
       minimum=0.0, maximum=20.0, impact="critical"),
    _p("fdr_level", "statistics", "float", 0.05,
       "FDR level",
       "Benjamini-Hochberg false discovery rate for pair and zone testing.",
       minimum=0.0001, maximum=0.5, impact="critical"),
    _p("fdr_method", "statistics", "choice", "benjamini_hochberg",
       "Multiple-testing method",
       "benjamini_yekutieli is valid under arbitrary dependence and is the "
       "conservative choice when zones are correlated.",
       choices=("benjamini_hochberg", "benjamini_yekutieli", "bonferroni",
                "none"), impact="critical"),
    _p("min_significant_point_fraction", "statistics", "float", 0.05,
       "Min significant point fraction",
       "Fraction of calibrated landmarks that must be individually "
       "significant before a pair becomes a change candidate.",
       minimum=0.0, maximum=1.0, impact="high"),
    _p("min_coherent_motion_fraction", "statistics", "float", 0.5,
       "Min coherent motion fraction",
       "Share of significant points whose displacement vectors agree in "
       "direction. Incoherent motion is noise, not change.",
       minimum=0.0, maximum=1.0, impact="high"),
    _p("bootstrap_iterations", "statistics", "int", 2000,
       "Bootstrap iterations",
       "Resamples used for confidence intervals. 0 disables CIs.",
       minimum=0, maximum=100000, impact="low", breaks_resume=False),
    _p("noise_sigma_policy", "statistics", "choice", "explicit_sigma_only",
       "Noise sigma policy",
       "Only an explicitly measured per-photo coordinate sigma may widen a "
       "threshold. Never assume a default sigma.",
       choices=("explicit_sigma_only", "fallback_reprojection", "off"),
       impact="critical"),

    # ---------------- chronology -------------------------------------------
    _p("min_dated_records", "chronology", "int", 3,
       "Min dated records",
       "Below this the dataset has no usable time axis and every temporal "
       "detector is skipped with an explicit status, instead of returning "
       "empty results that look like no change.",
       minimum=2, maximum=1000, impact="critical"),
    _p("min_distinct_dates", "chronology", "int", 2,
       "Min distinct dates", "Minimum number of different capture dates.",
       minimum=2, maximum=1000, impact="critical"),
    _p("date_conflict_days", "chronology", "int", 3,
       "Date conflict window",
       "Disagreement larger than this between filename, EXIF and claimed date "
       "marks the pair date_provenance_limited.",
       unit="days", minimum=0, maximum=3650, impact="high"),
    _p("date_source_priority", "chronology", "str_list",
       ["filename", "exif", "claimed"],
       "Date source priority",
       "Filename first: Stage 1 accepts only strict YYYY_MM_DD[_N] names and "
       "deliberately does not trust EXIF.", impact="high"),
    _p("same_day_sigma_threshold", "chronology", "float", 12.0,
       "Same-day sigma threshold",
       "Two photos from the same day cannot show real change, so their "
       "residual defines an empirical noise ceiling.",
       minimum=0.0, maximum=100.0, impact="high"),
    _p("same_day_baseline_quantile", "chronology", "float", 0.99,
       "Same-day baseline quantile",
       "Quantile of the same-day residual distribution used as that ceiling.",
       minimum=0.5, maximum=1.0, impact="high"),
    _p("min_baseline_pairs", "chronology", "int", 5,
       "Min same-day pairs", "Support required before the ceiling is trusted.",
       minimum=1, maximum=1000, impact="medium"),
    _p("cusum_enabled", "chronology", "bool", True,
       "CUSUM drift detection",
       "Detect slow cumulative drift that no single adjacent pair reveals.",
       impact="medium"),
    _p("cusum_threshold", "chronology", "float", 5.0,
       "CUSUM threshold", "Cumulative sum alarm level in sigma units.",
       minimum=0.0, maximum=100.0, impact="medium"),
    _p("cross_bin_min_support", "chronology", "int", 2,
       "Cross-bin corroboration support",
       "Independent pose bins that must show the same event before it counts "
       "as corroborated. The strongest available guard against pose "
       "artefacts.",
       minimum=1, maximum=9, impact="critical"),
    _p("irreversible_min_years", "chronology", "float", 5.0,
       "Irreversible return: min span",
       "Minimum years between the outer photos of a return triplet.",
       unit="years", minimum=0.0, maximum=100.0, impact="medium"),
    _p("irreversible_similarity", "chronology", "float", 0.95,
       "Irreversible return: similarity",
       "How similar the outer photos must be. Not calibrated, diagnostic.",
       minimum=0.0, maximum=1.0, impact="medium"),
    _p("irreversible_divergence_ratio", "chronology", "float", 2.0,
       "Irreversible return: divergence ratio",
       "How far the middle photo must diverge relative to the outer pair.",
       minimum=1.0, maximum=100.0, impact="medium"),

    # ---------------- texture ----------------------------------------------
    _p("texture_enabled", "texture", "bool", True,
       "Texture channel enabled",
       "Texture is a supporting channel only. It never drives a primary "
       "geometric conclusion.", impact="medium", breaks_resume=False),
    _p("texture_patch_size", "texture", "int", 192,
       "Texture patch size", "Zone patch edge length in pixels.",
       unit="px", minimum=32, maximum=1024, impact="medium"),
    _p("lbp_bins", "texture", "int", 10,
       "LBP histogram bins", "Local binary pattern histogram resolution.",
       minimum=4, maximum=64, impact="low"),
    _p("glcm_levels", "texture", "int", 16,
       "GLCM levels", "Grey-level co-occurrence matrix quantisation.",
       minimum=4, maximum=256, impact="low"),

    # ---------------- mesh -------------------------------------------------
    _p("mesh_enabled", "mesh", "bool", True,
       "Dense mesh channel enabled",
       "Full 35709-vertex comparison. Expensive but zone-resolved.",
       impact="medium", breaks_resume=False),
    _p("mesh_min_visible_fraction", "mesh", "float", 0.4,
       "Min visible mesh fraction",
       "Fraction of a zone vertices that must be visible in both photos.",
       minimum=0.0, maximum=1.0, impact="high"),
    _p("mesh_zone_min_vertices", "mesh", "int", 50,
       "Min vertices per mesh zone",
       "Zones with fewer usable vertices report insufficient_support.",
       minimum=1, maximum=35709, impact="medium"),

    # ---------------- runtime ----------------------------------------------
    _p("random_seed", "runtime", "int", 20260101,
       "Random seed", "Seeds bootstrap and any stochastic step.",
       minimum=0, maximum=2147483647, impact="medium"),
    _p("checkpoint_every", "runtime", "int", 50,
       "Checkpoint every N pairs",
       "0 disables checkpointing. Checkpoints are keyed to a signature of the "
       "inputs plus the parameter hash, so a resume can never mix profiles.",
       minimum=0, maximum=100000, impact="low", breaks_resume=False),
    _p("fail_fast", "runtime", "bool", False,
       "Fail fast",
       "Abort on the first pair error instead of recording it and continuing.",
       impact="low", breaks_resume=False),
    _p("max_workers", "runtime", "int", 1,
       "Worker processes",
       "Pairs are independent so more than one is safe. Determinism is "
       "preserved by sorting results by pair id before writing.",
       minimum=1, maximum=64, impact="low", breaks_resume=False),
    _p("strict_contract", "runtime", "bool", True,
       "Strict Stage 1 contract",
       "Reject any Stage 1 record that violates the contract instead of "
       "patching it up. Off collects violations and continues (audit mode).",
       impact="critical"),
    _p("write_diagnostics", "runtime", "bool", True,
       "Write diagnostic artifacts",
       "Per-pair motion NPZ files and diagnostic reports.",
       impact="low", breaks_resume=False),
)



SPECS = SPECS_PART1 + SPECS_PART2
del SPECS_PART1, SPECS_PART2


BY_KEY: dict[str, ParamSpec] = {s.key: s for s in SPECS}

if len(BY_KEY) != len(SPECS):
    raise RuntimeError("duplicate parameter key in the Stage 2 registry")
if not {s.group for s in SPECS} <= {g for g, _ in GROUPS}:
    raise RuntimeError("parameter declared in an unknown group")


class ParamError(ValueError):
    """Raised when a profile fails validation."""


def _cross_checks(values: dict[str, Any]) -> list[str]:
    """Constraints that involve more than one parameter."""
    errors: list[str] = []
    if values["detection_confidence_low"] > values["detection_confidence_high"]:
        errors.append("detection_confidence_low must be <= detection_confidence_high")
    inflation = values["quality_inflation"]
    if len(inflation) != 3:
        errors.append("quality_inflation must be exactly [high, mixed, low]")
    elif not (inflation[0] <= inflation[1] <= inflation[2]):
        errors.append("quality_inflation must be non-decreasing: high <= mixed <= low")
    if len(values["angle_noise_tolerance"]) != 3:
        errors.append("angle_noise_tolerance must be [yaw, pitch, roll]")
    unknown = set(values["limited_bins"]) - set(contract.BIN_NAMES)
    if unknown:
        errors.append(f"limited_bins contains unknown pose bins: {sorted(unknown)}")
    if values["profile_sub_bin_max_yaw_gap_deg"] > values["profile_sub_bin_width_deg"]:
        errors.append(
            "profile_sub_bin_max_yaw_gap_deg must not exceed profile_sub_bin_width_deg"
        )
    if values["analysis_space"] in contract.DIAGNOSTIC_ONLY_SPACES:
        errors.append(f"analysis_space {values['analysis_space']!r} is diagnostic only")
    if values["align_estimate_scale"]:
        errors.append(
            "align_estimate_scale absorbs real volumetric change and is blocked "
            "for evidence runs"
        )
    return errors


@dataclass(frozen=True)
class Params:
    """An immutable, validated set of Stage 2 parameters."""

    values: dict[str, Any] = field(default_factory=dict)
    name: str = "default"
    notes: str = ""

    # -- construction ------------------------------------------------------
    @classmethod
    def defaults(cls, name: str = "default") -> "Params":
        return cls({s.key: s.default for s in SPECS}, name=name)

    @classmethod
    def from_dict(
        cls,
        raw: dict[str, Any],
        *,
        name: str = "custom",
        notes: str = "",
        strict: bool = True,
    ) -> "Params":
        """Build from a partial dict, filling any gap with the declared default."""
        values: dict[str, Any] = {s.key: s.default for s in SPECS}
        unknown = sorted(set(raw) - set(values))
        if unknown and strict:
            raise ParamError(f"unknown parameter keys: {unknown}")
        problems: list[str] = []
        for key, value in raw.items():
            spec = BY_KEY.get(key)
            if spec is None:
                continue
            try:
                coerced = spec.coerce(value)
            except (TypeError, ValueError) as exc:
                problems.append(f"{key}: cannot read {value!r} as {spec.kind} ({exc})")
                continue
            problems.extend(spec.validate(coerced))
            values[key] = coerced
        problems.extend(_cross_checks(values))
        if problems:
            raise ParamError("; ".join(problems))
        return cls(values, name=name, notes=notes)

    @classmethod
    def load(cls, path: Path) -> "Params":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema") != PARAMS_SCHEMA:
            raise ParamError(
                f"profile schema mismatch: {payload.get('schema')!r} != {PARAMS_SCHEMA!r}"
            )
        return cls.from_dict(
            payload.get("values") or {},
            name=payload.get("name") or Path(path).stem,
            notes=payload.get("notes") or "",
        )

    # -- access ------------------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        if key not in BY_KEY:
            raise KeyError(f"unknown Stage 2 parameter: {key}")
        return self.values[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def replace(self, **changes: Any) -> "Params":
        merged = dict(self.values)
        merged.update(changes)
        return Params.from_dict(merged, name=self.name, notes=self.notes)

    # -- derived values ----------------------------------------------------
    @property
    def max_pitch_gap_deg(self) -> float:
        return self["max_yaw_gap_deg"] / self["pitch_to_yaw_sensitivity"]

    @property
    def max_roll_gap_deg(self) -> float:
        return self["max_yaw_gap_deg"] / self["roll_to_yaw_sensitivity"]

    @property
    def quality_inflation_map(self) -> dict[str, float]:
        high, mixed, low = self["quality_inflation"]
        return {"high": high, "mixed": mixed, "low": low}

    @property
    def angle_tolerance_map(self) -> dict[str, float]:
        yaw, pitch, roll = self["angle_noise_tolerance"]
        return {"yaw": yaw, "pitch": pitch, "roll": roll}

    # -- identity ----------------------------------------------------------
    def hash(self) -> str:
        """Stable content hash, recorded in the run manifest and checkpoints."""
        blob = json.dumps(self.values, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def resume_hash(self) -> str:
        """Hash of only the parameters that invalidate an existing checkpoint."""
        subset = {k: v for k, v in self.values.items() if BY_KEY[k].breaks_resume}
        blob = json.dumps(subset, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": PARAMS_SCHEMA,
            "name": self.name,
            "notes": self.notes,
            "hash": self.hash(),
            "resume_hash": self.resume_hash(),
            "values": dict(self.values),
        }

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps(self.to_json(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
        return path

    def diff(self, other: "Params") -> dict[str, dict[str, Any]]:
        """Parameters that differ, with impact - used by the admin panel."""
        out: dict[str, dict[str, Any]] = {}
        for key in sorted(BY_KEY):
            mine, theirs = self.values.get(key), other.values.get(key)
            if mine != theirs:
                out[key] = {
                    "from": mine,
                    "to": theirs,
                    "impact": BY_KEY[key].impact,
                    "breaks_resume": BY_KEY[key].breaks_resume,
                    "title": BY_KEY[key].title,
                }
        return out

    def non_default(self) -> dict[str, Any]:
        return {k: v for k, v in self.values.items() if v != BY_KEY[k].default}


def registry_json() -> dict[str, Any]:
    """Machine-readable registry. The admin panel renders itself from this."""
    return {
        "schema": PARAMS_SCHEMA,
        "groups": [{"key": k, "title": t} for k, t in GROUPS],
        "params": [s.to_json() for s in SPECS],
        "pose_bins": list(contract.BIN_NAMES),
    }


BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "default": {},
    "strict_evidence": {
        "fdr_method": "benjamini_yekutieli",
        "fdr_level": 0.01,
        "significance_z": 3.5,
        "cross_bin_min_support": 3,
        "min_reference_persons": 5,
        "max_yaw_gap_deg": 4.0,
        "expression_policy": "exclude_any",
        "exclude_near_duplicates": True,
        "min_texture_quality": 0.5,
    },
    "exploratory": {
        "fdr_level": 0.10,
        "significance_z": 2.5,
        "cross_bin_min_support": 1,
        "max_yaw_gap_deg": 8.0,
        "expression_policy": "stratify",
        "pair_all_within_bin": True,
        "min_reference_persons": 2,
    },
    "fast_smoke": {
        "texture_enabled": False,
        "mesh_enabled": False,
        "bootstrap_iterations": 0,
        "max_pairs_per_bin": 20,
        "write_diagnostics": False,
        "checkpoint_every": 0,
    },
}


def builtin(name: str) -> Params:
    if name not in BUILTIN_PROFILES:
        raise ParamError(
            f"unknown built-in profile {name!r}; have {sorted(BUILTIN_PROFILES)}"
        )
    return Params.from_dict(BUILTIN_PROFILES[name], name=name)
