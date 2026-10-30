#!/usr/bin/env python
"""Cache-only, worst-pair audit of frontal geometry; never writes production bands.

Run from the workspace root with:
    .venv/bin/python -B -m app9.validation.frontal_separability \
        --cache .runtime/frontal_separability --fresh-checks 3

Group names are supplied dataset labels, not identities inferred from photographs.
Candidate selection uses early calendar months only. Later months, neutral frames,
strict pose filtering, and train-only nuisance adjustment are reported separately.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import itertools
import json
import math
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.stats import rankdata, spearmanr

from app9.validation import metric_shortlist as ms
from morphing.backend import metric_registry as registry

ROOT = Path(__file__).resolve().parents[2]
GROUPS = ("put", "udmurt", "vas")
PAIRS = tuple(itertools.combinations(GROUPS, 2))
POSE = ("yaw_deg", "pitch_deg", "roll_deg")
BILATERAL = {
    "bilateral_brow_ridge_depth_134": ("brow_ridge_depth_l_134", "brow_ridge_depth_r_134"),
    "bilateral_fissure_area_134": ("fissure_area_l_134", "fissure_area_r_134"),
    "bilateral_lid_depth_spread_134": ("lid_margin_depth_spread_l_134", "lid_margin_depth_spread_r_134"),
    "bilateral_lateral_canthus_relief_134": ("lateral_canthus_relief_l_134", "lateral_canthus_relief_r_134"),
    "bilateral_brow_glabella_relief_134": (
        "brow_medial_to_glabella_relief_l_134", "brow_medial_to_glabella_relief_r_134"),
    "bilateral_eye_aperture_mp": (
        "eye_aperture_left_over_eye_width_mp", "eye_aperture_right_over_eye_width_mp"),
}


def frontal_mask(frame: pd.DataFrame, *, strict: bool = False) -> pd.Series:
    finite = np.isfinite(frame[list(POSE)].to_numpy(dtype=float)).all(axis=1)
    mask = frame.status.eq("ok") & frame.pose_bin.eq("frontal") & frame.yaw_deg.abs().le(10) & finite
    if strict:
        mask &= frame.yaw_deg.abs().le(5) & frame.roll_deg.abs().le(5) & frame.pitch_deg.abs().le(20)
    return mask


def neutral_flags(scores: dict[str, float]) -> tuple[bool, bool]:
    known = all(key in scores and np.isfinite(scores[key]) for key in ms.EXPR_MAX)
    return known, known and all(scores[key] <= limit for key, limit in ms.EXPR_MAX.items())


def chronological_split(frame: pd.DataFrame, fraction: float) -> pd.Series:
    if not 0 < fraction < 1:
        raise ValueError("train fraction must be between zero and one")
    train = pd.Series(False, index=frame.index)
    for group in GROUPS:
        mask = frame.group.eq(group)
        months = sorted(frame.loc[mask, "month"].unique())
        if len(months) < 2:
            raise ValueError(f"{group}: at least two calendar months are required")
        cut = max(1, min(len(months) - 1, math.floor(len(months) * fraction)))
        train.loc[mask] = frame.loc[mask, "month"].isin(months[:cut])
    return train


def raw_auc(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    n, m = len(a), len(b)
    if n < 3 or m < 3:
        return math.nan
    ranks = rankdata(np.concatenate((a, b)), method="average")
    return float((ranks[:n].sum() - n * (n + 1) / 2) / (n * m))


def robust_mad(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(1.4826 * np.median(np.abs(values - np.median(values)))) if len(values) >= 3 else math.nan


def balanced_mad(groups: dict[str, np.ndarray]) -> float:
    scales = [robust_mad(groups[group]) for group in GROUPS]
    return float(np.mean(scales)) if np.isfinite(scales).all() else math.nan


def values_by_group(frame: pd.DataFrame, name: str) -> dict[str, np.ndarray]:
    return {group: frame.loc[frame.group.eq(group), name].to_numpy(dtype=float) for group in GROUPS}


def training_signs(frame: pd.DataFrame, name: str) -> dict[str, int]:
    groups = values_by_group(frame, name)
    return {f"{a}~{b}": (1 if raw_auc(groups[a], groups[b]) >= 0.5 else -1) for a, b in PAIRS}


def summarize(frame: pd.DataFrame, name: str, signs: dict[str, int]) -> dict:
    groups = values_by_group(frame, name)
    refs = {}
    for group, values in groups.items():
        valid = values[np.isfinite(values)]
        refs[group] = {
            "n_dates": len(valid),
            "n_months": int(frame.loc[frame.group.eq(group) & frame[name].notna(), "month"].nunique()),
            "median": float(np.median(valid)) if len(valid) else math.nan,
            "mad": robust_mad(valid),
            "p10_p90": np.quantile(valid, [0.1, 0.9]).tolist() if len(valid) else [],
        }
    pairs = {}
    for a, b in PAIRS:
        key = f"{a}~{b}"
        auc = raw_auc(groups[a], groups[b])
        noise = (refs[a]["mad"] + refs[b]["mad"]) / 2
        gap = abs(refs[a]["median"] - refs[b]["median"])
        pairs[key] = {
            "auc": auc if signs[key] == 1 else 1 - auc,
            "gap_over_pair_mad": gap / noise if noise > 1e-12 else math.nan,
        }
    aucs = [pair["auc"] for pair in pairs.values()]
    gaps = [pair["gap_over_pair_mad"] for pair in pairs.values()]
    return {
        "ref": refs,
        "balanced_mad": balanced_mad(groups),
        "pairs": pairs,
        "worst_auc": min(aucs) if np.isfinite(aucs).all() else math.nan,
        "mean_auc": float(np.mean(aucs)) if np.isfinite(aucs).all() else math.nan,
        "min_gap_over_pair_mad": min(gaps) if np.isfinite(gaps).all() else math.nan,
    }


def within_group_correlations(frame: pd.DataFrame, name: str, keys: tuple[str, ...]) -> dict:
    result = {}
    for group in GROUPS:
        block = frame.loc[frame.group.eq(group)]
        for key in keys:
            a, b = block[name].to_numpy(dtype=float), block[key].to_numpy(dtype=float)
            mask = np.isfinite(a) & np.isfinite(b)
            rho = math.nan
            if mask.sum() >= 8 and len(np.unique(a[mask])) >= 3 and len(np.unique(b[mask])) >= 3:
                rho = float(spearmanr(a[mask], b[mask]).statistic)
            result[f"{group}:{key}"] = {"rho": rho, "n": int(mask.sum())}
    finite = [abs(row["rho"]) for row in result.values() if np.isfinite(row["rho"])]
    return {"max_abs_rho": max(finite) if finite else math.nan, "details": result}


def pose_adjustment(train: pd.DataFrame, target: pd.DataFrame, name: str) -> tuple[pd.DataFrame, list[float]]:
    valid = train.dropna(subset=[name, *POSE]).copy()
    x, y = valid[list(POSE)].to_numpy(dtype=float), valid[name].to_numpy(dtype=float)
    if len(valid) < 12 or any((valid.group == group).sum() < 3 for group in GROUPS):
        adjusted = target.copy()
        adjusted[name] = np.nan
        return adjusted, [math.nan] * len(POSE)
    centered_x, centered_y = x.copy(), y.copy()
    weights = np.zeros(len(valid))
    for group in GROUPS:
        mask = valid.group.eq(group).to_numpy()
        centered_x[mask] -= x[mask].mean(axis=0)
        centered_y[mask] -= y[mask].mean()
        weights[mask] = 1 / mask.sum()
    root_w = np.sqrt(weights)
    beta = np.linalg.lstsq(centered_x * root_w[:, None], centered_y * root_w, rcond=None)[0]
    adjusted = target.copy()
    # Remove only shared pose slopes, not group intercepts. Fit never sees target values.
    adjusted[name] = target[name] - (target[list(POSE)].to_numpy() - x.mean(axis=0)) @ beta
    return adjusted, beta.tolist()


def month_bootstrap_indices(frame: pd.DataFrame, count: int, rng: np.random.Generator) -> dict:
    draws = {}
    for group in GROUPS:
        months = frame.loc[frame.group.eq(group), "month"].to_numpy()
        blocks = [np.flatnonzero(months == month) for month in sorted(set(months))]
        if not blocks:
            draws[group] = [np.array([], dtype=int)] * count
            continue
        draws[group] = [np.concatenate([blocks[i] for i in rng.integers(len(blocks), size=len(blocks))])
                        for _ in range(count)]
    return draws


def bootstrap_auc(frame: pd.DataFrame, name: str, signs: dict[str, int], draws: dict) -> dict:
    groups = values_by_group(frame, name)
    count = len(draws[GROUPS[0]])
    samples = np.full((count, len(PAIRS)), np.nan)
    for repeat in range(count):
        for column, (a, b) in enumerate(PAIRS):
            auc = raw_auc(groups[a][draws[a][repeat]], groups[b][draws[b][repeat]])
            samples[repeat, column] = auc if signs[f"{a}~{b}"] == 1 else 1 - auc
    complete = samples[np.isfinite(samples).all(axis=1)]
    return {
        "n_valid": len(complete),
        "worst_auc_ci95": np.quantile(complete.min(axis=1), [0.025, 0.975]).tolist()
        if len(complete) >= 100 else [],
        "pair_auc_ci95": {f"{a}~{b}": np.quantile(complete[:, i], [0.025, 0.975]).tolist()
                          if len(complete) >= 100 else [] for i, (a, b) in enumerate(PAIRS)},
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_frame(args: argparse.Namespace) -> tuple[pd.DataFrame, dict, dict]:
    rows, values, expr = ms.load_values(args.cache)
    frames, coverage = [], {}
    names = sorted({name for group in values.values() for name in group})
    metadata = {name: {**registry.meta(name), "description": registry.describe(name)} for name in names}
    for group in GROUPS:
        if group not in rows:
            raise ValueError(f"missing cached group: {group}")
        angle_path = args.angles_dir / f"{group}_angles.csv"
        angles = pd.read_csv(angle_path)
        if angles.filename.duplicated().any():
            raise ValueError(f"duplicate CSV filenames in {angle_path}")
        eligible = angles.loc[frontal_mask(angles)].copy()
        feature_frame = pd.DataFrame(values[group])
        feature_frame["filename"] = rows[group]
        feature_frame["jawOpen"] = expr[group]["jawOpen"]
        feature_frame["smile"] = expr[group]["smile"]
        feature_frame["alpha_exp"] = expr[group]["alpha_exp"]
        merged = eligible.merge(feature_frame, on="filename", how="left", validate="one_to_one", indicator=True)
        missing = merged.loc[merged._merge.ne("both"), "filename"].tolist()
        if missing:
            raise ValueError(f"{group}: eligible photos missing from landmark caches: {missing}")
        merged = merged.drop(columns="_merge")
        with np.load(args.cache / f"mp_{group}.npz", allow_pickle=False) as archive:
            keys = archive["expr_keys"].astype(str).tolist()
            scores = {str(name): dict(zip(keys, row.tolist(), strict=True))
                      for name, row in zip(archive["files"], archive["expr"], strict=True)}
        flags = [neutral_flags(scores.get(name, {})) for name in merged.filename]
        merged["neutral_known"] = [known for known, _ in flags]
        merged["neutral"] = [neutral for _, neutral in flags]
        merged["group"] = group
        dates = pd.to_datetime(merged.filename.str[:10], format="%Y_%m_%d", errors="coerce")
        invalid_dates = merged.loc[dates.isna(), "filename"].tolist()
        if invalid_dates:
            raise ValueError(f"{group}: invalid chronology in filenames: {invalid_dates}")
        merged["date"] = dates.dt.strftime("%Y-%m-%d")
        merged["month"] = dates.dt.strftime("%Y-%m")
        merged["strict"] = frontal_mask(merged, strict=True)
        missing_photos, hashes, sizes = [], [], []
        for name in merged.filename:
            if Path(name).name != name:
                raise ValueError(f"unsafe CSV filename: {name}")
            path = args.photos / group / name
            if not path.is_file():
                missing_photos.append(name)
                continue
            hashes.append(sha256(path))
            sizes.append(path.stat().st_size)
        if missing_photos:
            raise ValueError(f"{group}: original photos missing: {missing_photos}")
        merged["sha256"] = hashes
        merged["source_bytes"] = sizes
        frames.append(merged)
        coverage[group] = {"angle_rows": len(angles), "frontal_photos": len(merged),
                           "strict_photos": int(merged.strict.sum()), "neutral_photos": int(merged.neutral.sum()),
                           "strict_neutral_photos": int((merged.strict & merged.neutral).sum()),
                           "unknown_expression_photos": int((~merged.neutral_known).sum()),
                           "frontal_pitch_median": float(merged.pitch_deg.median()),
                           "frontal_roll_over_10": int(merged.roll_deg.abs().gt(10).sum()),
                           "frontal_pitch_over_20": int(merged.pitch_deg.abs().gt(20).sum()),
                           "csv_sha256": sha256(angle_path)}
    frame = pd.concat(frames, ignore_index=True)
    frame["train"] = chronological_split(frame, args.train_fraction)
    for name, (left, right) in BILATERAL.items():
        if left not in names or right not in names:
            raise ValueError(f"missing bilateral components: {left}, {right}")
        frame[name] = (frame[left] + frame[right]) / 2
        metadata[name] = {**registry.meta(left), "group": "bilateral_research",
                          "source": "bilateral arithmetic mean; not in production",
                          "description": f"0.5 * ({left} + {right})", "components": [left, right]}
    for group in GROUPS:
        block = frame.loc[frame.group.eq(group)]
        coverage[group].update({"dates": block.date.nunique(), "months": block.month.nunique(),
                                "date_range": [block.date.min(), block.date.max()],
                                "train_photos": int(block.train.sum()), "test_photos": int((~block.train).sum()),
                                "train_months": sorted(block.loc[block.train, "month"].unique()),
                                "test_months": sorted(block.loc[~block.train, "month"].unique())})
    return frame, metadata, coverage


def audit_bands(frame: pd.DataFrame, bands: dict) -> dict:
    audit = {}
    for name, old in bands["metrics"].items():
        deviations, refs, counts = [], {}, {}
        for group in GROUPS:
            block = frame.loc[frame.group.eq(group)]
            values = block[name].to_numpy(dtype=float)
            finite = np.isfinite(values)
            valid = values[finite]
            deviations.append(valid - np.median(valid))
            neutral = block.neutral.to_numpy() & finite
            selected = values[neutral] if neutral.sum() >= 5 else valid
            refs[group] = float(np.median(selected))
            counts[group] = len(selected)
        pooled = robust_mad(np.concatenate(deviations))
        current = old["frontal"]
        ref_deltas = {group: refs[group] - current["ref"][group]["median"] for group in GROUPS}
        audit[name] = {
            "trusted_means_pose_stable": old["trusted"], "stored_min_gap": current["min_gap"],
            "stored_signal_cross": current["signal_cross"], "stored_band": current["mad_pooled"],
            "recomputed_band": pooled, "reference_deltas": ref_deltas, "reference_counts": counts,
            "reproduced_to_rounding": abs(pooled - current["mad_pooled"]) <= 0.000051
            and all(abs(delta) <= 0.000051 for delta in ref_deltas.values())
            and all(counts[group] == current["ref"][group]["n"] for group in GROUPS),
            "weakest_stored_pair": min(current["pairs"], key=current["pairs"].get),
        }
    return audit


def compare_reference_cache(cache: Path, reference: Path) -> dict:
    result = {}
    for group in GROUPS:
        points = {}
        for label, store in (("current", cache), ("reference", reference)):
            points[label] = {}
            for prefix in ("lmk", "mp"):
                collected = {}
                for part in sorted(store.glob(f"{prefix}_{group}*.npz")):
                    with np.load(part, allow_pickle=False) as archive:
                        for name, values in zip(archive["files"], archive["pts"], strict=True):
                            if str(name) in collected:
                                raise ValueError(f"duplicate {prefix} cache row: {group}/{name}")
                            collected[str(name)] = values
                points[label][prefix] = collected
        compared = {}
        for prefix, tolerance in (("lmk", 0.00002), ("mp", 0.05)):
            current, previous = points["current"][prefix], points["reference"][prefix]
            shared = sorted(set(current) & set(previous))
            errors = {name: float(np.max(np.abs(current[name] - previous[name]))) for name in shared}
            compared[prefix] = {
                "n_shared": len(shared), "n_current_only": len(set(current) - set(previous)),
                "max_abs_error": max(errors.values()) if errors else math.nan,
                "tolerance": tolerance, "units": "RMS-106" if prefix == "lmk" else "pixels",
                "changed": {name: value for name, value in errors.items() if value > tolerance},
            }
        result[group] = compared
    return result


def fresh_geometry_checks(frame: pd.DataFrame, cache: Path, per_group: int) -> list[dict]:
    if not per_group:
        return []
    import torch

    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh
    from morphing.backend.mp_worker import LandmarkerClient, resolve_asset

    torch.set_num_threads(2)
    results = []
    client = LandmarkerClient()
    # MediaPipe and torch crash when initialized in the same interpreter here.
    try:
        for group in GROUPS:
            names = sorted(frame.loc[frame.group.eq(group), "filename"])
            indices = np.linspace(0, len(names) - 1, min(per_group, len(names))).astype(int)
            with np.load(cache / f"mp_{group}.npz", allow_pickle=False) as archive:
                mp_cached = {str(name): points for name, points in zip(archive["files"], archive["pts"], strict=True)}
            cached = {}
            for part in sorted(cache.glob(f"lmk_{group}*.npz")):
                with np.load(part, allow_pickle=False) as archive:
                    for name, p106, p134, refs in zip(archive["files"], archive["pts"], archive["pts134"],
                                                    archive["refs"], strict=True):
                        cached[str(name)] = (p106, p134, refs)
            for index in indices:
                name = names[index]
                source = frame.loc[frame.group.eq(group) & frame.filename.eq(name), "source_path"].iloc[0]
                row = {"group": group, "filename": name, "mp_model_path": str(resolve_asset()),
                       "mp_pixel_tolerance": 0.05, "ldm_rms_tolerance": 0.00002}
                try:
                    detected = client.detect(Path(source).read_bytes())
                    fresh_mp = detected["points"]
                    row["mp_max_abs_pixel_error"] = float(np.max(np.abs(fresh_mp - mp_cached[name])))
                    recon = reconstruct_image(Path(source), device="cpu")
                    if recon is None:
                        raise ValueError("fresh 3DDFA reconstruction failed")
                    mesh, fresh106, _ = align_identity_mesh(recon)
                    fresh134 = mesh[np.asarray(recon["ldm134_indices"], dtype=int)]
                    fresh_refs = mesh[list(registry.ANAT_VERTS)]
                    row["ldm_max_abs_errors"] = [float(np.max(np.abs(a - b))) for a, b in
                                                 zip((fresh106, fresh134, fresh_refs), cached[name], strict=True)]
                    row["matches"] = row["mp_max_abs_pixel_error"] <= row["mp_pixel_tolerance"] \
                        and max(row["ldm_max_abs_errors"]) <= row["ldm_rms_tolerance"]
                except Exception as exc:
                    row["error"] = f"{type(exc).__name__}: {exc}"
                    row["matches"] = False
                results.append(row)
                print(f"fresh geometry {group}/{name}: {row}", flush=True)
    finally:
        client.close()
    return results


def training_shortlist(metrics: dict, train: pd.DataFrame, limit: int) -> list[str]:
    ordered = sorted(metrics, key=lambda name: (
        -metrics[name]["training_score"] if np.isfinite(metrics[name]["training_score"]) else math.inf, name))
    chosen = []
    for name in ordered:
        row = metrics[name]
        if not np.isfinite(row["training_score"]) or row["training_score"] < 0.65 or row["meta"]["framework"] == "cross":
            continue
        duplicate = None
        for previous in chosen:
            pair = train[[name, previous]].dropna()
            if len(pair) >= 8 and pair[name].nunique() >= 3 and pair[previous].nunique() >= 3:
                rho = float(spearmanr(pair[name], pair[previous]).statistic)
                if abs(rho) >= 0.95:
                    duplicate = {"metric": previous, "rho": rho}
                    break
        row["near_duplicate_in_training"] = duplicate
        if duplicate is None:
            chosen.append(name)
            if len(chosen) == limit:
                break
    return chosen


def followup_diagnostics(row: dict) -> dict:
    cohorts = row["cohorts"]
    limits = {"test": 0.70, "neutral": 0.65, "strict": 0.65, "pose_adjusted_test": 0.65}
    failures = []
    for key, minimum in limits.items():
        value = cohorts[key]["worst_auc"]
        if not np.isfinite(value) or value < minimum:
            failures.append(f"{key}: worst AUC below {minimum}")
    ci = row["test_bootstrap"]["worst_auc_ci95"]
    if len(ci) != 2 or ci[0] < 0.55:
        failures.append("later-month bootstrap lower bound below 0.55 or unavailable")
    if any(ref["n_months"] < 5 for ref in cohorts["test"]["ref"].values()):
        failures.append("fewer than five later-month blocks in a group")
    risks = []
    if row["meta"].get("expression_sensitive"):
        risks.append("expression-sensitive: calm, unblinking frontal frames only")
    if row["meta"].get("uses_z"):
        risks.append("uses inferred MediaPipe depth; not a purely visible 2D measurement")
    if row["meta"]["framework"] == "3ddfa":
        risks.append("3DMM-inferred geometry, not an anatomical ground-truth measurement")
    return {"passes_exploratory_checks": not failures, "failures": failures, "risks": risks}


def clean_json(value):
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [clean_json(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        return round(float(value), 7) if np.isfinite(value) else None
    return value


def write_html(path: Path, report: dict) -> None:
    def number(value):
        return f"{value:.3f}" if value is not None and np.isfinite(value) else "n/a"

    def table(names):
        body = []
        for name in names:
            row = report["metrics"][name]
            ci = row.get("test_bootstrap", {}).get("worst_auc_ci95", [])
            diagnostic = row.get("followup_diagnostics")
            status = "not selected" if diagnostic is None else (
                "frontal follow-up only" if diagnostic["passes_exploratory_checks"] else "; ".join(diagnostic["failures"]))
            cells = (
                name, row["meta"]["framework"], number(row["training_score"]),
                number(row["cohorts"]["test"]["worst_auc"]),
                " - ".join(number(x) for x in ci) if ci else "n/a",
                number(row["cohorts"]["neutral"]["worst_auc"]),
                number(row["cohorts"]["strict"]["worst_auc"]),
                number(row["cohorts"]["pose_adjusted_test"]["worst_auc"]),
                status,
                row["meta"]["description"])
            body.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>")
        headers = ("Metric", "Framework", "Train robustness score", "Later-month worst AUC", "95% month bootstrap",
                   "Neutral worst AUC", "Strict worst AUC", "Pose-adjusted later AUC", "Diagnostic Status", "Definition")
        return "<div class='scroll'><table><thead><tr>" + "".join(f"<th>{x}</th>" for x in headers) + \
               "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"

    coverage = "<pre>" + html.escape(json.dumps(report["coverage"], ensure_ascii=False, indent=2)) + "</pre>"
    warnings = "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in report["limitations"]) + "</ul>"
    current = sorted(report["current_band_audit"], key=lambda name: -(report["metrics"][name]["cohorts"]["test"]["worst_auc"] or 0))
    text = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Frontal metric separability audit</title><style>
body{font:15px/1.5 system-ui,sans-serif;margin:24px auto;padding:0 18px;max-width:1600px;color:#17212b;background:#f8fafb}
h1,h2{color:#123c51}table{border-collapse:collapse;background:white;width:100%;font-size:13px}
td,th{padding:9px;border:1px solid #ccd8df;text-align:left;vertical-align:top}th{background:#dceaf0}
.scroll{overflow-x:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0f4;padding:14px}
.notice{border-left:4px solid #bc6428;padding:12px;background:#fff4e6}li{margin:7px 0}
</style><h1>Frontal Geometry: Worst-Pair Separability</h1>
<p class="notice">Research only. Group labels come from folders. This analysis does not identify people,
validate identities, or establish anatomical ground truth. Production metric_bands.json is unchanged.</p>
<p>AUC is a rank comparison, not an identity probability. 0.5 means no rank separation; values below 0.5
mean the direction learned in early months reversed. Every displayed AUC uses training-only directions.
One observation is a date median. Confidence intervals resample calendar months, not dependent image pairs.</p>
<h2>Training-Only Shortlist</h2><p>Ranked by the minimum training AUC across all, neutral and strict cohorts,
then deduplicated at |Spearman rho| &gt;= 0.95 using training data. Cross-framework ratios are excluded.
The shortlist is exploratory, not approved for deployment.</p>"""
    text += "<p>Frozen training list below includes failures: nothing is silently removed after looking at later months. " \
            "Follow-up flags are heuristic diagnostics, not independent confirmation or deployment approval.</p>"
    text += table(report["training_shortlist"])
    text += "<h2>Frontal Follow-Up Candidates</h2>" + table(report["frontal_followup_candidates"])
    ranges = []
    for name in report["frontal_followup_candidates"]:
        row = report["metrics"][name]
        cells = [name]
        for group in GROUPS:
            ref = row["cohorts"]["all"]["ref"][group]
            span = " - ".join(number(value) for value in ref["p10_p90"])
            cells.append(f"{number(ref['median'])} [{span}]")
        risks = row["followup_diagnostics"]["risks"]
        cells.append("; ".join(risks) or "frontal only; external validation still required")
        ranges.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")
    text += "<p>All-frame date medians [10th - 90th percentile], in each definition's native units. " \
            "The ranges still overlap; these are not reliable single-image identity markers.</p>" \
            "<div class='scroll'><table><tr><th>Metric</th><th>put</th><th>udmurt</th><th>vas</th><th>Risks</th></tr>" \
            + "".join(ranges) + "</table></div>"
    text += "<h2>Current 30 Metrics</h2><p>trusted=true in the input means prior pose stability, not separation of all three groups.</p>" + table(current)
    reference_ok = sum(item["reproduced_to_rounding"] for item in report["reference_band_audit"].values())
    fresh_ok = sum(item["reproduced_to_rounding"] for item in report["current_band_audit"].values())
    weak = sum(item["stored_min_gap"] < 1 for item in report["current_band_audit"].values())
    text += f"<h2>Input Bands Audit</h2><p>{reference_ok}/30 rows reproduce with the previous cache; " \
            f"{fresh_ok}/30 reproduce to four-decimal rounding with freshly extracted geometry. " \
            f"{weak}/30 stored closest-pair gaps are smaller than one noise band. " \
            "Small numerical differences are not by themselves formula bugs.</p>"
    text += "<p>Unit clarification: ratios are dimensionless, angles are degrees, and lengths in " \
            "the normalized model are RMS-106 coordinates. The band calculator uses scaled MAD " \
            "(1.4826 times raw median absolute deviation), not raw MAD.</p>"
    audit_rows = []
    for name in sorted(current, key=lambda key: report["current_band_audit"][key]["stored_min_gap"]):
        item = report["current_band_audit"][name]
        cells = [name, str(item["trusted_means_pose_stable"]), item["weakest_stored_pair"],
                 number(item["stored_min_gap"]), str(item["stored_band"]), str(item["recomputed_band"]),
                 number(max(abs(value) for value in item["reference_deltas"].values()) / item["stored_band"])]
        audit_rows.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")
    text += "<div class='scroll'><table><tr><th>Metric</th><th>Prior pose stability</th><th>Closest stored pair</th>" \
            "<th>Stored gap / MAD</th><th>Stored band</th><th>Fresh band</th><th>Max reference shift / stored band</th></tr>" \
            + "".join(audit_rows) + "</table></div>"
    differences = {group: {key: {"compared": item["n_shared"], "changed": len(item["changed"]),
                               "max_abs_error": item["max_abs_error"], "units": item["units"]}
                           for key, item in block.items()}
                   for group, block in report["reference_cache_comparison"].items()}
    text += "<h2>Extraction Reproducibility</h2><p>The previous cache did not bind source hashes; " \
            "the cause of old/fresh differences cannot be established from filenames. " \
            "Current source hashes and nine repeated fresh checks are saved in analysis.json.</p><pre>" \
            + html.escape(json.dumps(differences, indent=2)) + "</pre>"
    text += "<h2>Pair Weighting</h2><p>Old all-pairs pooling weights groups quadratically. " \
            "This audit uses date medians and equal-weight pair summaries instead.</p><pre>" \
            + html.escape(json.dumps(report["old_same_pair_weights"], indent=2)) + "</pre>"
    text += "<h2>Coverage and Chronological Blocks</h2>" + coverage
    text += "<h2>Limitations</h2>" + warnings + "</html>"
    path.write_text(text, encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    bands_digest = sha256(args.bands)
    bands = json.loads(args.bands.read_text(encoding="utf-8"))
    frame, metadata, coverage = load_frame(args)
    frame["source_path"] = [str(args.photos / group / name) for group, name in zip(frame.group, frame.filename, strict=True)]
    feature_names = sorted(metadata)
    missing = set(bands["metrics"]) - set(feature_names)
    if missing:
        raise ValueError(f"bands contain unknown metrics: {sorted(missing)}")
    numeric = [*feature_names, *POSE, "jawOpen", "smile", "alpha_exp"]

    def dates(mask):
        return frame.loc[mask].groupby(["group", "date", "month", "train"], as_index=False)[numeric].median()

    cohorts = {"all": dates(np.ones(len(frame), dtype=bool)), "neutral": dates(frame.neutral),
               "strict": dates(frame.strict), "strict_neutral": dates(frame.strict & frame.neutral)}
    cohorts["train"] = cohorts["all"].loc[cohorts["all"].train].copy()
    cohorts["test"] = cohorts["all"].loc[~cohorts["all"].train].copy()
    cohorts["train_neutral"] = cohorts["neutral"].loc[cohorts["neutral"].train].copy()
    cohorts["train_strict"] = cohorts["strict"].loc[cohorts["strict"].train].copy()
    metrics = {}
    for name in feature_names:
        signs = training_signs(cohorts["train"], name)
        summaries = {key: summarize(block, name, signs) for key, block in cohorts.items()}
        adjusted, beta = pose_adjustment(cohorts["train"], cohorts["test"], name)
        summaries["pose_adjusted_test"] = summarize(adjusted, name, signs)
        scores = [summaries[key]["worst_auc"] for key in ("train", "train_neutral", "train_strict")]
        metrics[name] = {
            "meta": metadata[name], "current": name in bands["metrics"], "signs_from_train": signs,
            "cohorts": summaries, "training_score": min(scores) if np.isfinite(scores).all() else math.nan,
            "pose_slopes_from_train": dict(zip(POSE, beta, strict=True)),
            "pose_correlation_train": within_group_correlations(cohorts["train"], name, POSE),
            "expression_correlation_train": within_group_correlations(cohorts["train"], name, ("jawOpen", "smile", "alpha_exp")),
        }
    shortlist = training_shortlist(metrics, cohorts["train"], args.shortlist_size)
    rng = np.random.default_rng(args.seed)
    draws = month_bootstrap_indices(cohorts["test"], args.bootstrap, rng)
    for name in sorted(set(bands["metrics"]) | set(shortlist)):
        metrics[name]["test_bootstrap"] = bootstrap_auc(cohorts["test"], name, metrics[name]["signs_from_train"], draws)
    for name in shortlist:
        metrics[name]["followup_diagnostics"] = followup_diagnostics(metrics[name])
    reference_args = argparse.Namespace(**{**vars(args), "cache": args.reference_cache})
    reference_frame, _, _ = load_frame(reference_args)
    report = {
        "schema_version": "frontal-separability-research-v1", "deployment_ready": False,
        "group_labels": list(GROUPS), "coverage": coverage, "n_candidates": len(metrics),
        "n_registry_candidates": len(metrics) - len(BILATERAL), "training_shortlist": shortlist,
        "frontal_followup_candidates": [name for name in shortlist if metrics[name]["followup_diagnostics"]["passes_exploratory_checks"]],
        "old_same_pair_weights": {group: coverage[group]["frontal_photos"] * (coverage[group]["frontal_photos"] - 1) // 2
                                  for group in GROUPS},
        "protocol": {"frontal": "status=ok, pose_bin=frontal, |yaw|<=10 degrees",
                     "strict": "frontal and |yaw|<=5, |roll|<=5, |pitch|<=20 degrees",
                     "neutral": ms.EXPR_MAX, "unit_of_observation": "median per group and calendar date",
                     "train_fraction_of_months": args.train_fraction, "bootstrap_month_draws": args.bootstrap,
                     "seed": args.seed, "signs": "early months only, fixed in all evaluations",
                     "shortlist_score": "min worst-pair AUC over train, train-neutral and train-strict",
                     "minimum_training_score": 0.65, "near_duplicate_rho": 0.95,
                     "followup_diagnostics": "heuristic: test AUC>=0.70, lower CI>=0.55, neutral/strict/pose-adjusted AUC>=0.65, >=5 test months/group",
                     "band_scale": "1.4826 * median absolute deviation; equal mean of three group MADs",
                     "units": "ratios dimensionless; angles degrees; normalized model lengths RMS-106 coordinates"},
        "cohort_dates": {key: {group: int(block.group.eq(group).sum()) for group in GROUPS} for key, block in cohorts.items()},
        "current_band_audit": audit_bands(frame, bands), "metrics": metrics,
        "reference_band_audit": audit_bands(reference_frame, bands),
        "reference_cache_comparison": compare_reference_cache(args.cache, args.reference_cache),
        "fresh_geometry_checks": fresh_geometry_checks(frame, args.cache, args.fresh_checks),
        "provenance": {"bands_path": str(args.bands), "bands_sha256": bands_digest, "photos_path": str(args.photos),
                       "cache_path": str(args.cache), "cache_source_binding": "filenames; original extraction has no photo hashes",
                       "reference_cache_path": str(args.reference_cache),
                       "reference_cache_sha256": {path.name: sha256(path) for path in sorted(args.reference_cache.glob("*.npz"))},
                       "cache_sha256": {path.name: sha256(path) for path in sorted(args.cache.glob("*.npz"))},
                       "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in (
                           Path(__file__), ROOT / "app9/validation/metric_shortlist.py", ROOT / "morphing/backend/metric_registry.py",
                           ROOT / "morphing/backend/aligner.py", ROOT / "morphing/backend/mp_worker.py",
                           ROOT / "app8/reconstruction.py", ROOT / "app8/imaging.py", ROOT / "app8/geometry.py")},
                       "reconstruction_assets_sha256": {
                           name: sha256(ROOT / "3ddfa_v3/assets" / name) for name in (
                               "face_model.npy", "net_recon.pth", "retinaface_resnet50_2020-07-20_old_torch.pth",
                               "large_base_net.pth", "similarity_Lm3D_all.mat")
                           if (ROOT / "3ddfa_v3/assets" / name).is_file()},
                       "python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
                       "scipy": scipy.__version__, "torch": version("torch"), "mediapipe": version("mediapipe"),
                       "pillow": version("pillow"), "mp_model_sha256": sha256(ms.MP_ASSET),
                       "fresh_check_device": "cpu", "fresh_check_torch_threads": 2},
        "limitations": [
            "Only three supplied groups. Labels are metadata; no identity or ethnicity is inferred or verified.",
            "Capture-date distributions differ, with incomplete temporal overlap. Age, camera, lighting and source processing remain confounded with group effects.",
            "3DDFA depth is inferred from a single image. Stable reconstruction is not proof of anatomical measurement accuracy.",
            "The source CSV's pitch convention is model-based. Strict filtering is a sensitivity test, not ground-truth pose annotation.",
            "Neutral and strict-neutral samples in udmurt are small. Missing expression scores are unknown, never neutral.",
            "Date/month blocks approximate sessions; true session IDs and an independent new acquisition are unavailable.",
            "Dates come from filename prefixes supplied with the dataset, not independently verified capture timestamps.",
            "The same dataset was used in earlier metric searches. Temporal evaluation is internal, not an untouched external test.",
            "259 definitions were explored. Bootstrap intervals are unadjusted descriptive intervals, not familywise significance claims.",
            "Pose adjustment is diagnostic: shared linear slopes fitted within groups using early months only; no guarantee of transfer.",
            "Bilateral means are six simple research candidates, not new approved production definitions.",
            "Frontal follow-up flags are post-selection heuristic diagnostics. They are not an independent test or universal quality thresholds.",
            "The old cache has no original photo hashes. Current hashes and sampled fresh checks improve traceability, not full historical provenance.",
            "Balanced MADs describe date medians, not single-photo production thresholds. Do not copy them into metric_bands.json.",
            "AUC describes rank separation on these groups, not an identity probability or a same/different-person verdict.",
        ],
    }
    report = clean_json(report)
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_columns = ["group", "filename", "date", "month", "train", "strict", "neutral", "neutral_known",
                        *POSE, "jawOpen", "smile", "alpha_exp", "sha256", "source_bytes", "source_path"]
    frame[manifest_columns].to_csv(args.out / "source_manifest.csv", index=False)
    frame[[*manifest_columns, *feature_names]].to_csv(args.out / "photo_metrics.csv", index=False)
    flat = []
    for name, row in report["metrics"].items():
        item = {"metric": name, "framework": row["meta"]["framework"], "current": row["current"],
                "shortlisted": name in shortlist, "training_score": row["training_score"],
                "frontal_followup": name in report["frontal_followup_candidates"],
                "expression_rho_train_max": row["expression_correlation_train"]["max_abs_rho"],
                "pose_rho_train_max": row["pose_correlation_train"]["max_abs_rho"]}
        for key, stats in row["cohorts"].items():
            item.update({f"{key}_{field}": stats[field] for field in ("worst_auc", "mean_auc", "min_gap_over_pair_mad", "balanced_mad")})
            item.update({f"{key}_auc_{pair}": stats["pairs"][pair]["auc"] for pair in stats["pairs"]})
        ci = row.get("test_bootstrap", {}).get("worst_auc_ci95", [])
        item.update({"test_ci_low": ci[0] if ci else None, "test_ci_high": ci[1] if ci else None})
        flat.append(item)
    pd.DataFrame(flat).sort_values("training_score", ascending=False).to_csv(args.out / "metrics.csv", index=False)
    (args.out / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_html(args.out / "report.html", report)
    if sha256(args.bands) != bands_digest:
        raise RuntimeError("production bands changed during the analysis")
    print(f"Analyzed {len(frame)} photos, {len(metrics)} candidates; output: {args.out}")
    print("Training shortlist: metric | train score | later-month worst AUC | 95% CI")
    for name in shortlist:
        row = report["metrics"][name]
        print(name, row["training_score"], row["cohorts"]["test"]["worst_auc"], row["test_bootstrap"]["worst_auc_ci95"])
    print("Stored bands reproduced:", sum(row["reproduced_to_rounding"] for row in report["current_band_audit"].values()),
          "/", len(bands["metrics"]))
    print("Exploratory frontal follow-up:", report["frontal_followup_candidates"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=Path, default=Path("/Volumes/SDCARD/test_photos"))
    parser.add_argument("--angles-dir", type=Path, default=ROOT)
    parser.add_argument("--cache", type=Path, default=ROOT / ".runtime/metric_shortlist")
    parser.add_argument("--reference-cache", type=Path, default=ROOT / ".runtime/metric_shortlist")
    parser.add_argument("--bands", type=Path, default=ROOT / "morphing/backend/metric_bands.json")
    parser.add_argument("--out", type=Path, default=ROOT / "app9/validation/report/frontal_separability")
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--shortlist-size", type=int, default=10)
    parser.add_argument("--fresh-checks", type=int, default=0, help="fresh MP and 3DDFA source checks per group")
    args = parser.parse_args()
    if args.bootstrap < 100 or args.shortlist_size < 1 or args.fresh_checks < 0:
        parser.error("bootstrap>=100, shortlist-size>=1 and fresh-checks>=0 are required")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
