#!/usr/bin/env python
"""Fifty frozen geometry hypotheses; dataset-group research, not face recognition."""
from __future__ import annotations

import argparse
import ast
import html
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import QhullError
from threadpoolctl import threadpool_limits

from app9.validation import frontal_separability as audit

ROOT = audit.ROOT
EPS = 1e-10
GRID = np.linspace(0.05, 0.95, 19)
MP_UP = ((33, 246, 161, 160, 159, 158, 157, 173, 133),
         (263, 466, 388, 387, 386, 385, 384, 398, 362))
MP_LO = ((33, 7, 163, 144, 145, 153, 154, 155, 133),
         (263, 249, 390, 373, 374, 380, 381, 382, 362))
MP_BU = ((70, 63, 105, 66, 107), (300, 293, 334, 296, 336))
MP_BL = ((46, 53, 52, 65, 55), (276, 283, 282, 295, 285))
D_UP = (tuple(range(11, 22)), tuple(range(33, 44)))
D_LO = (tuple(range(0, 11)), tuple(range(22, 33)))
D_BU = (tuple(range(44, 51)), tuple(range(57, 64)))
D_BL = (tuple(range(51, 57)), tuple(range(64, 70)))
NOSE_LOOP = (4, 45, 220, 115, 48, 64, 98, 97, 2, 326, 327, 294, 278, 344, 440, 275)


def divide(a: float, b: float) -> float:
    return float(a / b) if np.isfinite(a) and np.isfinite(b) and abs(b) > EPS else math.nan


def norm(vector: np.ndarray) -> float:
    return float(np.linalg.norm(vector))


def triangle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    a, b, c = np.asarray(a)[:2], np.asarray(b)[:2], np.asarray(c)[:2]
    ab, ac = b - a, c - a
    return float(abs(ab[0] * ac[1] - ab[1] * ac[0]) / 2)


def polygon_area(points: np.ndarray) -> float:
    points = np.asarray(points)[:, :2]
    return float(abs(np.sum(points[:, 0] * np.roll(points[:, 1], -1)
                            - points[:, 1] * np.roll(points[:, 0], -1))) / 2)


def angle(a: np.ndarray, vertex: np.ndarray, b: np.ndarray) -> float:
    x, y = a - vertex, b - vertex
    cosine = divide(float(x @ y), norm(x) * norm(y))
    return float(np.degrees(np.arccos(np.clip(cosine, -1, 1)))) if np.isfinite(cosine) else math.nan


def row_interpolation(u: np.ndarray, values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    order = np.argsort(u)
    unique, inverse = np.unique(u[order], return_inverse=True)
    sorted_values = np.asarray(values)[order]
    means = np.array([sorted_values[inverse == index].mean(axis=0) for index in range(len(unique))])
    if means.ndim == 1:
        return np.interp(grid, unique, means)
    return np.column_stack([np.interp(grid, unique, means[:, column]) for column in range(means.shape[1])])


def eye_profile(points: np.ndarray, upper: tuple[int, ...], lower: tuple[int, ...]) -> dict:
    up, lo = points[list(upper), :2], points[list(lower), :2]
    origin, end = (up[0] + lo[0]) / 2, (up[-1] + lo[-1]) / 2
    width = norm(end - origin)
    if width <= EPS:
        raise ValueError("degenerate eye chord")
    axis = (end - origin) / width
    normal = np.array([-axis[1], axis[0]])
    if (lo.mean(axis=0) - up.mean(axis=0)) @ normal < 0:
        normal *= -1
    upper_u, lower_u = (up - origin) @ axis / width, (lo - origin) @ axis / width
    upper_y = row_interpolation(upper_u, (up - origin) @ normal / width, GRID)
    lower_y = row_interpolation(lower_u, (lo - origin) @ normal / width, GRID)
    gap = np.maximum(lower_y - upper_y, 0)
    total = float(gap.sum())
    if total <= EPS:
        raise ValueError("no measurable eye opening")
    mass = gap / total
    centre = float(GRID @ mass)
    variance = float(((GRID - centre) ** 2) @ mass)
    up_height, lo_height = np.maximum(-upper_y, 0), np.maximum(lower_y, 0)
    up_centre = divide(float(GRID @ up_height), float(up_height.sum()))
    lo_centre = divide(float(GRID @ lo_height), float(lo_height.sum()))
    log_x = np.log(4 * GRID * (1 - GRID))
    log_y = np.log(np.maximum(gap / gap.max(), EPS))
    coefficients = np.polynomial.polynomial.polyfit(GRID, gap / gap.mean(), 4)
    curvature = np.abs(np.polynomial.polynomial.polyval(
        GRID, np.polynomial.polynomial.polyder(coefficients, 2)))
    loop = np.concatenate((up, lo[::-1]))
    covariance = np.cov(loop.T, bias=True)
    anisotropy = divide((np.trace(covariance) ** 2 - 4 * np.linalg.det(covariance)), np.trace(covariance) ** 2)
    concordance = math.nan
    if np.std(up_height) > EPS and np.std(lo_height) > EPS:
        concordance = float(np.corrcoef(up_height, lo_height)[0, 1])
    return {
        "mean": float(gap.mean()), "q20": float(np.quantile(gap, 0.2)),
        "skew": divide(float(((GRID - centre) ** 3) @ mass), variance ** 1.5),
        "kurt": divide(float(((GRID - centre) ** 4) @ mass), variance ** 2) - 3,
        "upper_lower_var": divide(float(np.var(up_height)), float(np.var(lo_height))),
        "iqr": divide(float(np.quantile(gap, 0.75) - np.quantile(gap, 0.25)), float(gap.mean())),
        "shape_exponent": divide(float(log_x @ log_y), float(log_x @ log_x)),
        "peak_offset": up_centre - lo_centre, "profile_corr": concordance,
        "curvature_balance": divide(float(curvature[GRID < 0.4].sum()), float(curvature[GRID > 0.6].sum())),
        "concentration": divide(float(gap[GRID > 0.6].sum()), float(gap[GRID < 0.4].sum())),
        "flat_top": float(np.mean(gap >= 0.8 * gap.max())), "shape_anisotropy": anisotropy,
        "area": polygon_area(loop), "width": width, "centre": centre,
        "normalized_gap": gap / gap.mean(), "origin": origin, "axis": axis, "normal": normal,
        "upper_u": upper_u, "upper_y": (up - origin) @ normal / width,
    }


def binocular(profiles: list[dict], prefix: str) -> dict[str, float]:
    names = ("mean", "q20", "skew", "kurt", "upper_lower_var", "iqr", "shape_exponent",
             "peak_offset", "profile_corr", "curvature_balance", "concentration", "flat_top", "shape_anisotropy")
    result = {f"{prefix}_e_{name}": float(np.mean([profile[name] for profile in profiles])) for name in names}
    result[f"{prefix}_e_shape_mismatch"] = float(np.mean(np.abs(profiles[0]["normalized_gap"] - profiles[1]["normalized_gap"])))
    result[f"{prefix}_e_centroid_asym"] = abs(profiles[0]["centre"] - profiles[1]["centre"])
    means = [profile["mean"] for profile in profiles]
    result[f"{prefix}_e_harm"] = divide(2 * means[0] * means[1], sum(means))
    result[f"{prefix}_eye_area_sum"] = sum(profile["area"] for profile in profiles)
    return result


def canopy(points: np.ndarray, profile: dict, bu: tuple[int, ...], bl: tuple[int, ...], eu: tuple[int, ...],
           *, spatial: bool) -> dict:
    origin, axis, normal, width = (profile[key] for key in ("origin", "axis", "normal", "width"))
    rows = [points[list(indices)] for indices in (bu, bl, eu)]
    abscissas = [(row[:, :2] - origin) @ axis / width for row in rows]
    start = max(0.05, *(float(u.min()) for u in abscissas))
    stop = min(0.95, *(float(u.max()) for u in abscissas))
    if stop - start <= 0.2:
        return dict.fromkeys(("gap_gradient", "gap_curvature", "taper", "gap_median"), math.nan)
    grid = np.linspace(start, stop, 19)
    interpolated = [row_interpolation(u, row, grid) for u, row in zip(abscissas, rows, strict=True)]
    upper, lower, eyelid = interpolated
    if spatial:
        gap = np.linalg.norm(eyelid - lower, axis=1) / width
    else:
        gap = np.maximum((eyelid[:, :2] - lower[:, :2]) @ normal / width, 0)
    thickness = np.linalg.norm(upper - lower, axis=1) / width
    x = grid - grid.mean()
    coefficients = np.polynomial.polynomial.polyfit(x, gap, 2)
    return {"gap_gradient": divide(float(np.polynomial.polynomial.polyfit(x, gap, 1)[1]), float(gap.mean())),
            "gap_curvature": divide(float(coefficients[2]), float(gap.mean())),
            "taper": divide(float(np.polynomial.polynomial.polyfit(x, thickness, 1)[1]), float(thickness.mean())),
            "gap_median": float(np.median(gap)) * width}


def plane_warp(points: np.ndarray, width: float) -> float:
    centred = points - points.mean(axis=0)
    _, singular, vectors = np.linalg.svd(centred, full_matrices=False)
    # A small third singular value means planar, not invalid. Reject collinearity via s[1].
    if len(singular) < 3 or singular[1] <= EPS * max(singular[0], 1):
        return math.nan
    return divide(float(np.sqrt(np.mean((centred @ vectors[-1]) ** 2))), width)


def affine_ratios(points: np.ndarray) -> dict[str, float]:
    oa, ob, ia, ib, root, tip, base = (points[index, :2] for index in (33, 263, 133, 362, 168, 1, 2))
    return {
        "mp_affine_tip_base": divide(triangle(oa, ob, tip), triangle(oa, ob, base)),
        "mp_affine_tip_root": divide(triangle(ia, ib, tip), triangle(ia, ib, root)),
        "mp_affine_root_sides": divide(triangle(ia, root, tip) * triangle(ib, root, base),
                                       triangle(ia, root, base) * triangle(ib, root, tip)),
        "mp_affine_cantho_nasal": divide(triangle(oa, ia, root) * triangle(ob, ib, tip),
                                         triangle(oa, ia, tip) * triangle(ob, ib, root)),
    }


def primitive_values(mp478: np.ndarray, q106: np.ndarray, q134: np.ndarray, refs: np.ndarray,
                     brow_relief: float) -> dict[str, float]:
    mp_scale, d_scale = norm(mp478[468, :2] - mp478[473, :2]), norm(q106[104] - q106[105])
    if min(mp_scale, d_scale) <= EPS:
        raise ValueError("degenerate pupil spacing")
    mp = (np.asarray(mp478[:, :2], dtype=float) - (mp478[468, :2] + mp478[473, :2]) / 2) / mp_scale
    q, dense, ref = q106 / d_scale, q134 / d_scale, refs / d_scale
    mp_profiles = [eye_profile(mp, up, lo) for up, lo in zip(MP_UP, MP_LO, strict=True)]
    d_profiles = [eye_profile(dense, up, lo) for up, lo in zip(D_UP, D_LO, strict=True)]
    result = {**binocular(mp_profiles, "mp"), **binocular(d_profiles, "d"), **affine_ratios(mp)}
    mp_canopies = [canopy(mp, profile, bu, bl, up, spatial=False)
                   for profile, bu, bl, up in zip(mp_profiles, MP_BU, MP_BL, MP_UP, strict=True)]
    d_canopies = [canopy(dense, profile, bu, bl, up, spatial=True)
                  for profile, bu, bl, up in zip(d_profiles, D_BU, D_BL, D_UP, strict=True)]
    for key in ("gap_gradient", "gap_curvature", "taper", "gap_median"):
        result[f"mp_b_{key}"] = float(np.mean([row[key] for row in mp_canopies]))
    result["d_b_clearance_gradient"] = float(np.mean([row["gap_gradient"] for row in d_canopies]))
    tapers, wedges, warps = [], [], []
    for up, lo, bu, bl, profile in zip(D_UP, D_LO, D_BU, D_BL, d_profiles, strict=True):
        thickness = np.linalg.norm(dense[list(bu)[1:]] - dense[list(bl)], axis=1)
        tapers.append(divide(float(np.polyfit(np.linspace(-0.5, 0.5, 6), thickness, 1)[0]), float(thickness.mean())))
        upper, lower = dense[list(up)], dense[list(lo)]
        lateral = angle(upper[2] - upper[0], np.zeros(3), lower[2] - lower[0])
        medial = angle(upper[-3] - upper[-1], np.zeros(3), lower[-3] - lower[-1])
        wedges.append(lateral - medial)
        warps.append(plane_warp(np.concatenate((upper, lower)), profile["width"]))
    result.update({"d_b_taper": float(np.mean(tapers)), "d_b_relief": float(brow_relief),
                   "d_e_wedge_difference": float(np.mean(wedges)), "d_e_warp": float(np.mean(warps))})
    side_widths = [norm(q[a] - q[b]) for a, b in ((55, 65), (56, 64), (57, 63))]
    d_width, d_height = norm(q[58] - q[62]), norm(q[51] - q[60])
    d_triangle = triangle(q[51], q[58], q[62])
    d_arc = sum(norm(q[b] - q[a]) for a, b in zip((58, 59, 60, 61), (59, 60, 61, 62), strict=True))
    eye_y = float((q[74, 1] + q[83, 1]) / 2)
    result.update({"d_n_waist": divide(side_widths[1], (side_widths[0] + side_widths[2]) / 2),
                   "d_n_tip_angle": angle(q[51], q[54], q[60]), "d_n_wrap": divide(d_arc, d_width),
                   "d_n_aspect": divide(d_width, d_height),
                   "d_malar_y": divide(float(ref[[2, 3], 1].mean() - eye_y), float(q[60, 1] - eye_y)),
                   "d_malar_angle": float(np.mean([np.degrees(np.arctan2((ref[a] - ref[b])[2],
                                                                          abs((ref[a] - ref[b])[0])))
                                                   for a, b in ((2, 0), (3, 1))]))})
    mp_width, mp_height = norm(mp[98] - mp[327]), norm(mp[168] - mp[2])
    nose_points = mp[list(NOSE_LOOP)]
    covariance = np.cov(nose_points.T, bias=True)
    nose_anisotropy = divide(np.trace(covariance) ** 2 - 4 * np.linalg.det(covariance), np.trace(covariance) ** 2)
    nose_axis = mp[2] - mp[168]
    nose_axis /= norm(nose_axis)
    positions = [(mp[index] - mp[168]) @ nose_axis for index in (168, 197, 1, 2)]
    r, m, t, b = positions
    crossratio = divide((r - t) * (m - b), (r - b) * (m - t))
    result.update({"mp_n_width": mp_width, "mp_n_height": mp_height,
                   "mp_n_aspect": divide(mp_width, mp_height), "mp_inner_span": norm(mp[133] - mp[362]),
                   "mp_n_loop_area": polygon_area(nose_points), "mp_n_triangle_area": triangle(mp[168], mp[98], mp[327]),
                   "mp_n_shape_anisotropy": float(nose_anisotropy),
                   "mp_n_bridge_bend": angle(mp[168], mp[197], mp[1]), "mp_n_midline_crossratio": crossratio})
    result["mp_eye_nose_height"] = divide(result["mp_e_mean"], result["mp_n_aspect"])
    result["d_eye_nose_height"] = divide(result["d_e_mean"], result["d_n_aspect"])
    result["mp_eye_nose_area"] = divide(result["mp_eye_area_sum"], result["mp_n_triangle_area"])
    result["d_eye_nose_area"] = divide(result["d_eye_area_sum"], d_triangle)
    return result


def evaluate_formula(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return evaluate_formula(node.body, values)
    if isinstance(node, ast.Name) and node.id in values:
        return float(values[node.id])
    if isinstance(node, ast.Constant) and type(node.value) in (int, float) and np.isfinite(node.value):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        value = evaluate_formula(node.operand, values)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Sub | ast.Mult | ast.Div):
        a, b = evaluate_formula(node.left, values), evaluate_formula(node.right, values)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        return divide(a, b)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1 and not node.keywords:
        value = evaluate_formula(node.args[0], values)
        if node.func.id == "abs":
            return abs(value)
        if node.func.id == "sqrt":
            return math.sqrt(value) if np.isfinite(value) and value >= 0 else math.nan
        if node.func.id == "log":
            return math.log(value) if np.isfinite(value) and value > 0 else math.nan
    raise ValueError(f"unsupported or unknown formula expression: {ast.dump(node)}")


def load_catalogue(path: Path) -> tuple[dict, dict[str, ast.AST]]:
    catalogue = json.loads(path.read_text(encoding="utf-8"))
    hypotheses = catalogue["hypotheses"]
    expected = {f"H{index:02}" for index in range(1, 51)}
    if len(hypotheses) != 50 or {row["id"] for row in hypotheses} != expected:
        raise ValueError("the catalogue must contain H01..H50 exactly once")
    if any(type(row["priority"]) is not int or not 90 <= row["priority"] <= 100 for row in hypotheses):
        raise ValueError("priority scores must be integers from 90 to 100")
    if len({row["formula"] for row in hypotheses}) != 50:
        raise ValueError("duplicate formula strings")
    expressions = {row["id"]: ast.parse(row["formula"], mode="eval") for row in hypotheses}
    return catalogue, expressions


def load_cached_points(cache: Path) -> dict:
    result = {}
    for group in audit.GROUPS:
        with np.load(cache / f"mp_{group}.npz", allow_pickle=False) as archive:
            mp = {str(name): points.astype(float) for name, points in zip(archive["files"], archive["pts"], strict=True)}
        mesh = {}
        for part in sorted(cache.glob(f"lmk_{group}*.npz")):
            with np.load(part, allow_pickle=False) as archive:
                for name, q106, q134, refs in zip(archive["files"], archive["pts"], archive["pts134"],
                                                archive["refs"], strict=True):
                    if str(name) in mesh:
                        raise ValueError(f"duplicate landmark cache row: {group}/{name}")
                    mesh[str(name)] = (q106.astype(float), q134.astype(float), refs.astype(float))
        result[group] = {name: (points, *mesh[name]) for name, points in mp.items() if name in mesh}
    return result


def extract(args: argparse.Namespace) -> tuple[pd.DataFrame, dict, dict, dict, dict]:
    catalogue, expressions = load_catalogue(args.catalogue)
    frame, previous_meta, coverage = audit.load_frame(args)
    previous_names = sorted(previous_meta)
    points = load_cached_points(args.cache)
    records, errors = [], []
    for row in frame.to_dict("records"):
        group, name = row["group"], row["filename"]
        relief = (row["brow_ridge_depth_l_134"] + row["brow_ridge_depth_r_134"]) / 2
        try:
            primitives = primitive_values(*points[group][name], relief)
        except (ValueError, np.linalg.LinAlgError, QhullError) as exc:
            errors.append({"group": group, "filename": name, "error": str(exc)})
            primitives = {}
        values = {}
        for key, expression in expressions.items():
            try:
                values[key] = evaluate_formula(expression, primitives)
            except ValueError:
                if primitives:
                    raise
                values[key] = math.nan
        records.append({"group": group, "filename": name, **values,
                        **{f"primitive_{key}": value for key, value in primitives.items()}})
    computed = pd.DataFrame(records)
    frame = frame.merge(computed, on=["group", "filename"], validate="one_to_one").copy()
    args.out.mkdir(parents=True, exist_ok=True)
    identifiers = ["group", "filename", "date", "month", "train", "strict", "neutral", "sha256", *audit.POSE]
    frame[[*identifiers, *expressions]].to_csv(args.out / "photo_hypotheses.csv", index=False)
    primitive_columns = [column for column in computed if column.startswith("primitive_")]
    frame[[*identifiers, *primitive_columns]].to_csv(args.out / "primitives.csv", index=False)
    extraction = {"n_photos": len(frame), "n_hypotheses": len(expressions), "coverage": coverage, "errors": errors,
                  "previous_names": previous_names, "catalogue_sha256": audit.sha256(args.catalogue),
                  "finite_by_hypothesis": {key: int(np.isfinite(frame[key]).sum()) for key in expressions}}
    (args.out / "extraction.json").write_text(json.dumps(audit.clean_json(extraction), indent=2, allow_nan=False), encoding="utf-8")
    print(f"Computed {len(expressions)} frozen hypotheses for {len(frame)} photos; geometry errors: {len(errors)}", flush=True)
    return frame, catalogue, coverage, extraction, previous_meta


def weighted_auc_samples(a: np.ndarray, b: np.ndarray, wa: np.ndarray, wb: np.ndarray) -> np.ndarray:
    """Exact tie-aware AUC for many resamples, without materializing duplicate rows."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    finite_a, finite_b = np.isfinite(a), np.isfinite(b)
    a, b = a[finite_a], b[finite_b]
    weights_a, weights_b = wa[:, finite_a], wb[:, finite_b]
    comparisons = (a[:, None] > b[None, :]).astype(float) + 0.5 * (a[:, None] == b[None, :])
    numerator = np.sum((weights_a @ comparisons) * weights_b, axis=1)
    counts_a, counts_b = weights_a.sum(axis=1), weights_b.sum(axis=1)
    result = np.full(len(wa), np.nan)
    valid = (counts_a >= 3) & (counts_b >= 3)
    result[valid] = numerator[valid] / (counts_a[valid] * counts_b[valid])
    return result


def bootstrap_weights(frame: pd.DataFrame, count: int, rng: np.random.Generator) -> dict:
    weights = {}
    for group in audit.GROUPS:
        months = frame.loc[frame.group.eq(group), "month"].to_numpy()
        unique, inverse = np.unique(months, return_inverse=True)
        if not len(unique):
            raise ValueError(f"{group}: no month blocks for bootstrap")
        counts = rng.multinomial(len(unique), np.full(len(unique), 1 / len(unique)), size=count)
        weights[group] = counts[:, inverse].astype(float)
    return weights


def bootstrapped_pairs(frame: pd.DataFrame, name: str, signs: dict, weights: dict) -> np.ndarray:
    values = audit.values_by_group(frame, name)
    pairs = []
    for a, b in audit.PAIRS:
        sampled = weighted_auc_samples(values[a], values[b], weights[a], weights[b])
        pairs.append(sampled if signs[f"{a}~{b}"] == 1 else 1 - sampled)
    return np.column_stack(pairs)


def permutation_weights(labels: np.ndarray, count: int, rng: np.random.Generator) -> dict:
    # Every row gets its own permutation, preserving all three month-block counts.
    permuted = rng.permuted(np.tile(labels, (count, 1)), axis=1)
    return {group: (permuted == group).astype(float) for group in audit.GROUPS}


def permutation_association(months: pd.DataFrame, ids: list[str], signs: dict, count: int,
                            rng: np.random.Generator) -> dict:
    labels = months.group.to_numpy()
    weights = permutation_weights(labels, count, rng)
    null_by_hypothesis, observed = {}, {}
    maximum = np.full(count, -np.inf)
    for name in ids:
        values = months[name].to_numpy(dtype=float)
        pairs = []
        for a, b in audit.PAIRS:
            sampled = weighted_auc_samples(values, values, weights[a], weights[b])
            pairs.append(sampled if signs[name][f"{a}~{b}"] == 1 else 1 - sampled)
        null = np.column_stack(pairs).min(axis=1)
        null_by_hypothesis[name] = null
        maximum = np.fmax(maximum, null)
        observed[name] = audit.summarize(months, name, signs[name])["worst_auc"]
    result = {}
    for name in ids:
        valid = np.isfinite(null_by_hypothesis[name])
        null, statistic = null_by_hypothesis[name][valid], observed[name]
        joint = maximum[np.isfinite(maximum)]
        raw = (1 + int(np.sum(null >= statistic))) / (1 + len(null)) if len(null) and np.isfinite(statistic) else math.nan
        result[name] = {
            "observed_month_worst_auc": statistic, "n_valid_permutations": len(null),
            "p_raw": raw, "p_bonferroni50": min(1.0, raw * len(ids)) if np.isfinite(raw) else math.nan,
            "p_maxT_global_null": (1 + int(np.sum(joint >= statistic))) / (1 + len(joint))
            if len(joint) and np.isfinite(statistic) else math.nan,
        }
    return result


def cohort_tables(frame: pd.DataFrame, numeric: list[str]) -> dict[str, pd.DataFrame]:
    def dates(mask):
        return frame.loc[mask].groupby(["group", "date", "month", "train"])[numeric].median().reset_index()

    cohorts = {"all": dates(np.ones(len(frame), dtype=bool)), "neutral": dates(frame.neutral),
               "strict": dates(frame.strict), "strict_neutral": dates(frame.strict & frame.neutral)}
    cohorts["train"] = cohorts["all"].loc[cohorts["all"].train].copy()
    cohorts["test"] = cohorts["all"].loc[~cohorts["all"].train].copy()
    cohorts["train_neutral"] = cohorts["neutral"].loc[cohorts["neutral"].train].copy()
    cohorts["train_strict"] = cohorts["strict"].loc[cohorts["strict"].train].copy()
    cohorts["test_neutral"] = cohorts["neutral"].loc[~cohorts["neutral"].train].copy()
    return cohorts


def training_score(cohorts: dict, name: str, signs: dict) -> float:
    values = [audit.summarize(cohorts[key], name, signs)["worst_auc"] for key in ("train", "train_neutral", "train_strict")]
    return min(values) if np.isfinite(values).all() else -math.inf


def nearest_existing(train: pd.DataFrame, ids: list[str], previous: list[str]) -> dict:
    correlations = train[[*ids, *previous]].corr(method="spearman")
    result = {}
    for name in ids:
        candidates = correlations.loc[name, previous].dropna()
        if not len(candidates):
            result[name] = {"name": None, "rho": math.nan, "near_duplicate": False, "rank_equivalent": False}
            continue
        matched = candidates.abs().idxmax()
        rho = float(candidates[matched])
        result[name] = {"name": matched, "rho": rho, "near_duplicate": abs(rho) >= 0.95,
                        "rank_equivalent": abs(rho) >= 0.99999}
    return result


def confidence_intervals(samples: np.ndarray, benchmark: np.ndarray, families: int) -> dict:
    complete = np.isfinite(samples).all(axis=1) & np.isfinite(benchmark).all(axis=1)
    proposed, previous = samples[complete].min(axis=1), benchmark[complete].min(axis=1)
    difference = proposed - previous
    if len(difference) < 100:
        return {"n_valid": len(difference), "auc_ci95": [], "delta_ci95": [], "delta_ci_familywise_nominal95": []}
    return {"n_valid": len(difference), "auc_ci95": np.quantile(proposed, [0.025, 0.975]).tolist(),
            "delta_ci95": np.quantile(difference, [0.025, 0.975]).tolist(),
            "delta_ci_familywise_nominal95": np.quantile(difference, [0.025 / families, 1 - 0.025 / families]).tolist()}


def hypothesis_status(row: dict, family_size: int = 50) -> dict:
    failures = []
    for key, minimum in (("test", 0.70), ("neutral", 0.65), ("strict", 0.65), ("pose_adjusted_test", 0.65)):
        value = row["cohorts"][key]["worst_auc"]
        if not np.isfinite(value) or value < minimum:
            failures.append(f"{key} worst AUC below {minimum}")
    ci = row["bootstrap"]["auc_ci95"]
    if not ci or ci[0] < 0.55:
        failures.append("later-month lower AUC confidence bound below 0.55 or unavailable")
    p = row["association"]["p_bonferroni50"]
    if not np.isfinite(p) or p > 0.05:
        failures.append(f"monthly association does not pass Bonferroni{family_size} at 0.05")
    if any(ref["n_months"] < 5 for ref in row["cohorts"]["test"]["ref"].values()):
        failures.append("fewer than five later month blocks in a group")
    if row["nearest_existing"]["rank_equivalent"]:
        status = "rank_equivalent_existing"
    elif failures:
        status = "not_supported"
    elif row["delta_test_auc"] < 0.02:
        status = "robust_without_claimed_increment"
    else:
        corrected = row["bootstrap"]["delta_ci_familywise_nominal95"]
        supported = bool(corrected and corrected[0] >= 0.02)
        redundant = row["nearest_existing"]["near_duplicate"]
        status = ("supported_internal" if supported else "promising_unconfirmed_increment")
        if redundant:
            status += "_redundant"
    return {"status": status, "failures": failures,
            "population_validated": False, "empirical_score_is_not_accuracy": True}


def write_report(path: Path, report: dict) -> None:
    def number(value):
        return f"{value:.3f}" if value is not None and np.isfinite(value) else "n/a"

    rows, details = [], []
    hypotheses = sorted(report["hypotheses"].values(), key=lambda row: (
        -row["training_score"] if row["training_score"] is not None else math.inf, row["id"]))
    for row in hypotheses:
        interval = row["bootstrap"]["delta_ci95"]
        corrected = row["bootstrap"]["delta_ci_familywise_nominal95"]
        nearest = row["nearest_existing"]
        cells = [row["id"], row["title"], str(row["priority"]), number(row["training_score"]),
                 number(row["cohorts"]["test"]["worst_auc"]), number(row["delta_test_auc"]),
                 " to ".join(number(value) for value in interval),
                 " to ".join(number(value) for value in corrected),
                 number(row["cohorts"]["neutral"]["worst_auc"]), number(row["cohorts"]["strict"]["worst_auc"]),
                 f"{row['association']['p_bonferroni50']:.5f}" if row["association"]["p_bonferroni50"] is not None else "n/a",
                 f"{nearest['name']} ({number(nearest['rho'])})", row["diagnostics"]["status"]]
        rows.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")
        detail = {"formula": row["formula"], "rationale": row["rationale"], "risk": row["risk"],
                  "empirical_robustness_index": row["empirical_robustness_index"], "diagnostics": row["diagnostics"],
                  "later_pairs": row["cohorts"]["test"]["pairs"], "neutral_later_pairs": row["cohorts"]["test_neutral"]["pairs"],
                  "pose_slopes_fitted_on_train": row["pose_slopes"], "within_group_expression_rho": row["expression_correlation_train"]}
        details.append(f"<details id='{row['id']}'><summary>{row['id']}: {html.escape(row['title'])}</summary><pre>"
                       + html.escape(json.dumps(detail, ensure_ascii=False, indent=2)) + "</pre></details>")
    headers = ("ID", "Hypothesis", "Priority /100", "Early robustness", "Later worst AUC", "Delta to benchmark",
               "Delta 95% CI", "Delta nominal family CI", "Neutral AUC", "Strict AUC", "Association p Bonf50",
               "Nearest existing (rho)", "Outcome")
    text = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fifty New Frontal Geometry Hypotheses</title><style>
body{font:15px/1.5 system-ui,sans-serif;color:#17212b;background:#f8fafb;margin:24px auto;padding:0 18px;max-width:1650px}
table{border-collapse:collapse;background:white;font-size:12px}td,th{border:1px solid #cbd8df;padding:8px;text-align:left;vertical-align:top}
th{background:#dcebf1}.scroll{overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0f4;padding:12px}
details{margin:8px 0}summary{cursor:pointer}.notice{padding:14px;border-left:4px solid #b85e28;background:#fff4e8}li{margin:6px 0}
</style><h1>Fifty New Frontal Geometry Hypotheses</h1><p class="notice">Priority 90-98 is a subjective score assigned
before this batch, not a 90-98% success probability, identification accuracy or empirically verified quality.
Dataset labels come from folders; no identity or sensitive trait is inferred. Production definitions and bands are unchanged.</p>
<p>Every formula and its prior score remain in the frozen catalogue, including failures and duplicates.
Candidate rankings and AUC directions use early months only. Later months are reused internal validation, not an untouched external acquisition.
One observation is a date median; uncertainty resamples whole calendar months. All fifty claims are tested.</p>"""
    text += "<h2>Summary and Benchmark</h2><pre>" + html.escape(json.dumps({
        "counts": report["status_counts"], "benchmark": report["benchmark"], "catalogue_sha256": report["catalogue_sha256"]}, indent=2)) + "</pre>"
    text += """<p>Association p-values use permutations of later-month group labels, preserving group month counts.
Bonferroni50 is the primary association correction; maxT is also saved for the joint global null.
Neither test proves incremental improvement, anatomical truth or transfer to other people.
The paired-bootstrap difference intervals address improvement against the fixed benchmark.
Nominal simultaneous percentile intervals are approximate, especially with few month blocks.</p>"""
    text += "<h2>All 50 Results</h2><div class='scroll'><table><thead><tr>" + "".join(f"<th>{x}</th>" for x in headers)
    text += "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div><h2>Frozen Claims and Diagnostics</h2>" + "".join(details)
    text += "<h2>Geometry Definitions</h2><pre>" + html.escape(json.dumps(report["geometry_notes"], indent=2)) + "</pre>"
    text += "<h2>Limitations</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in report["limitations"]) + "</ul></html>"
    path.write_text(text, encoding="utf-8")


def validate(args: argparse.Namespace, frame: pd.DataFrame, catalogue: dict, coverage: dict,
             extraction: dict, previous_meta: dict) -> dict:
    ids = [row["id"] for row in catalogue["hypotheses"]]
    previous = sorted(previous_meta)
    numeric = [*previous, *ids, *audit.POSE, "jawOpen", "smile", "alpha_exp"]
    cohorts = cohort_tables(frame, numeric)
    all_signs = {name: audit.training_signs(cohorts["train"], name) for name in [*previous, *ids]}
    old_scores = {name: training_score(cohorts, name, all_signs[name]) for name in previous}
    benchmark_name = min(previous, key=lambda name: (-old_scores[name], name))
    benchmark = {"name": benchmark_name, "selection": "max minimum early all/neutral/strict worst-pair AUC over all previous259",
                 "training_score": old_scores[benchmark_name],
                 "test": audit.summarize(cohorts["test"], benchmark_name, all_signs[benchmark_name])}
    print(f"Training-only benchmark: {benchmark_name}, later worst AUC {benchmark['test']['worst_auc']:.4f}", flush=True)
    months = cohorts["test"].groupby(["group", "month", "train"], as_index=False)[numeric].median()
    nearest = nearest_existing(cohorts["train"], ids, previous)
    new_correlations = cohorts["train"][ids].corr(method="spearman")
    rng = np.random.default_rng(args.seed)
    weights = bootstrap_weights(cohorts["test"], args.bootstrap, rng)
    benchmark_samples = bootstrapped_pairs(cohorts["test"], benchmark_name, all_signs[benchmark_name], weights)
    hypotheses = {}
    for index, definition in enumerate(catalogue["hypotheses"]):
        name = definition["id"]
        signs = all_signs[name]
        stats = {key: audit.summarize(block, name, signs) for key, block in cohorts.items()}
        adjusted, beta = audit.pose_adjustment(cohorts["train"], cohorts["test"], name)
        stats["pose_adjusted_test"] = audit.summarize(adjusted, name, signs)
        samples = bootstrapped_pairs(cohorts["test"], name, signs, weights)
        score_values = [stats[key]["worst_auc"] for key in ("test", "neutral", "strict", "pose_adjusted_test")]
        siblings = new_correlations.loc[name].drop(index=name).dropna()
        closest = siblings.abs().idxmax() if len(siblings) else None
        hypotheses[name] = {**definition, "signs_from_early_months": signs, "cohorts": stats,
                            "training_score": training_score(cohorts, name, signs),
                            "empirical_robustness_index": 100 * min(score_values) if np.isfinite(score_values).all() else math.nan,
                            "delta_test_auc": stats["test"]["worst_auc"] - benchmark["test"]["worst_auc"],
                            "bootstrap": confidence_intervals(samples, benchmark_samples, len(ids)),
                            "nearest_existing": nearest[name],
                            "nearest_batch_hypothesis": {"id": closest, "rho": float(siblings[closest]) if closest else math.nan},
                            "pose_slopes": dict(zip(audit.POSE, beta, strict=True)),
                            "pose_correlation_train": audit.within_group_correlations(cohorts["train"], name, audit.POSE),
                            "expression_correlation_train": audit.within_group_correlations(cohorts["train"], name, ("jawOpen", "smile", "alpha_exp"))}
        if (index + 1) % 10 == 0:
            print(f"Bootstrap and nuisance diagnostics: {index + 1}/50", flush=True)
    print(f"Running {args.permutations} common month-block label permutations for all50", flush=True)
    associations = permutation_association(months, ids, all_signs, args.permutations, rng)
    for name in ids:
        hypotheses[name]["association"] = associations[name]
        hypotheses[name]["diagnostics"] = hypothesis_status(hypotheses[name])
    status_counts = {}
    for row in hypotheses.values():
        status = row["diagnostics"]["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    report = {
        "schema_version": "frontal-hypotheses50-results-v1", "deployment_ready": False,
        "catalogue": catalogue, "catalogue_sha256": extraction["catalogue_sha256"], "coverage": coverage,
        "extraction": extraction, "benchmark": benchmark, "status_counts": status_counts, "hypotheses": hypotheses,
        "protocol": {"train_fraction_months": args.train_fraction, "bootstrap_month_resamples": args.bootstrap,
                     "label_permutations": args.permutations, "seed": args.seed, "correction_family_size": 50,
                     "hypothesis_improvement_margin": 0.02, "orientation": "fixed from early dates, not reselected in bootstraps/permutations",
                     "association_unit": "later-month median of date medians", "bootstrap_unit": "calendar month clusters of date medians",
                     "primary_association_correction": "Bonferroni50; maxT conditional global-null comparison also reported"},
        "geometry_notes": {"MP_contour_source": "installed mediapipe/python/solutions/face_mesh_connections.py",
                           "MP_upper_lids": MP_UP, "MP_lower_lids": MP_LO, "MP_upper_brows": MP_BU, "MP_lower_brows": MP_BL,
                           "MP_nasal_loop": NOSE_LOOP, "MP_root_tip_base_alae": [168, 1, 2, [98, 327]],
                           "D_upper_lids": D_UP, "D_lower_lids": D_LO, "D_upper_brows": D_BU, "D_lower_brows": D_BL,
                           "D_nose_sidewall_pairs": [[55, 65], [56, 64], [57, 63]], "D_internal_nose_angle": [51, 54, 60],
                           "D_basal_nose_arc": [58, 59, 60, 61, 62],
                           "normalization": "Each source uses its own pupil/iris spacing; no raw MP/3D coordinate subtraction.",
                           "eye_frame": "lateral-to-medial chord; normal points upper-to-lower, fixing y-up/y-down and mirrored-side traps.",
                           "canopy_matching": "shared projected canthal abscissa, not unmatched point-by-point rows",
                           "plane_validity": "second singular value rejects collinearity; a valid planar loop has zero warping"},
        "provenance": {"catalogue_path": str(args.catalogue), "cache_path": str(args.cache),
                       "cache_sha256": {path.name: audit.sha256(path) for path in sorted(args.cache.glob("*.npz"))},
                       "code_sha256": {str(path.relative_to(ROOT)): audit.sha256(path) for path in (
                           Path(__file__), ROOT / "app9/validation/frontal_separability.py", ROOT / "morphing/backend/metric_registry.py")}},
        "limitations": [
            "Priority90-98 is subjective testing priority. It is not a calibrated posterior, success probability or empirical90% score.",
            "The same three groups and later months were seen in earlier research. This is an internal exploratory batch, not an untouched prospective test.",
            "Dates are supplied filename annotations. Calendar months only approximate independent acquisition sessions.",
            "Group-label permutations assume exchangeability of month blocks under the null. Different periods/cameras/lighting can violate that assumption.",
            "Association after Bonferroni50 or maxT does not establish incremental AUC improvement or anatomical causality.",
            "Paired percentile-bootstrap difference intervals, including Bonferroni nominal simultaneous intervals, are approximate with few month blocks and a nonsmooth worst-pair statistic.",
            "Only three groups; udmurt has13 neutral and5 strict-neutral photos. External generalization and90% empirical quality are not established.",
            "3DMM contours and mean-selected cheek vertices are inferred surface proxies, not measured orbital/bony anatomy.",
            "Eye opening, visible brow shape and iris placement depend on expression, gaze and grooming. Neutral flags are only blendshape thresholds.",
            "Ratios of2D areas are affine invariant mathematically; the projection of a rotating nonplanar3D face is not generally a2D affine warp.",
            "All50 frozen claims, failed tests and numerical/rank redundancies are retained. A new name is not evidence of new information.",
            "The benchmark was selected using early-month robustness only, not the best old feature discovered after looking at later-month AUC.",
            "No identities or sensitive traits are inferred. AUC is a dataset-label rank statistic, not a same/different-person verdict.",
        ],
    }
    report = audit.clean_json(report)
    flat = []
    for name, row in report["hypotheses"].items():
        interval, corrected = row["bootstrap"]["delta_ci95"], row["bootstrap"]["delta_ci_familywise_nominal95"]
        item = {"id": name, "title": row["title"], "priority": row["priority"], "family": row["family"], "formula": row["formula"],
                "training_score": row["training_score"], "empirical_robustness_index": row["empirical_robustness_index"],
                "delta_test_auc": row["delta_test_auc"], "delta_ci95_low": interval[0] if interval else None,
                "delta_ci95_high": interval[1] if interval else None, "delta_family_ci_low": corrected[0] if corrected else None,
                "delta_family_ci_high": corrected[1] if corrected else None, "p_raw": row["association"]["p_raw"],
                "p_bonferroni50": row["association"]["p_bonferroni50"], "p_maxT": row["association"]["p_maxT_global_null"],
                "nearest_existing": row["nearest_existing"]["name"], "nearest_existing_rho": row["nearest_existing"]["rho"],
                "nearest_batch": row["nearest_batch_hypothesis"]["id"], "nearest_batch_rho": row["nearest_batch_hypothesis"]["rho"],
                "status": row["diagnostics"]["status"], "failures": "; ".join(row["diagnostics"]["failures"])}
        for key, stats in row["cohorts"].items():
            item[f"{key}_worst_auc"] = stats["worst_auc"]
            item[f"{key}_min_gap_over_pair_mad"] = stats["min_gap_over_pair_mad"]
        flat.append(item)
    pd.DataFrame(flat).sort_values(["training_score", "id"], ascending=[False, True]).to_csv(args.out / "results.csv", index=False)
    (args.out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_report(args.out / "report.html", report)
    if audit.sha256(args.catalogue) != report["catalogue_sha256"]:
        raise RuntimeError("frozen catalogue changed during testing")
    print("Outcomes:", status_counts, flush=True)
    print("ID | priority | later worst AUC | delta to benchmark | outcome", flush=True)
    ordered = sorted(hypotheses.values(), key=lambda row: (-row["training_score"], row["id"]))
    for row in ordered[:15]:
        print(row["id"], row["priority"], round(row["cohorts"]["test"]["worst_auc"], 4),
              round(row["delta_test_auc"], 4), row["diagnostics"]["status"], flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, default=ROOT / "app9/validation/hypotheses50_catalog.json")
    parser.add_argument("--cache", type=Path, default=ROOT / ".runtime/frontal_separability")
    parser.add_argument("--photos", type=Path, default=Path("/Volumes/SDCARD/test_photos"))
    parser.add_argument("--angles-dir", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=ROOT / "app9/validation/report/hypotheses50")
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--bootstrap", type=int, default=20000)
    parser.add_argument("--permutations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20261027)
    args = parser.parse_args()
    if args.bootstrap < 1000 or args.permutations < 1000:
        parser.error("at least1000 bootstrap draws and1000 permutations are required")
    bands = ROOT / "morphing/backend/metric_bands.json"
    bands_hash, catalogue_hash = audit.sha256(bands), audit.sha256(args.catalogue)
    with threadpool_limits(limits=2, user_api="blas"):
        frame, catalogue, coverage, extraction, previous_meta = extract(args)
        if not args.extract_only:
            validate(args, frame, catalogue, coverage, extraction, previous_meta)
    if audit.sha256(bands) != bands_hash or audit.sha256(args.catalogue) != catalogue_hash:
        raise RuntimeError("production bands or frozen catalogue changed during the study")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
