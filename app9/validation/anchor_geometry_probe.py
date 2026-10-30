#!/usr/bin/env python
"""Test geodesic/curvature/spherical/anchor-distance singles on full identity meshes."""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from threadpoolctl import threadpool_limits

from app9.validation import anchor_mesh_features as geometry
from app9.validation import frontal_separability as audit
from app9.validation import hypotheses50 as study

ROOT = audit.ROOT


def load_foundation(args):
    frame, metadata, coverage = audit.load_frame(args)
    previous_names = sorted(metadata)
    prior_report = json.loads((ROOT / "app9/validation/report/hypotheses50/results.json").read_text(encoding="utf-8"))
    current_cache_hashes = {path.name: audit.sha256(path) for path in sorted(args.cache.glob("*.npz"))}
    if current_cache_hashes != prior_report["provenance"]["cache_sha256"]:
        raise ValueError("the anchor study must use the same landmark snapshot as the fifty-hypothesis study")
    prior = pd.read_csv(ROOT / "app9/validation/report/hypotheses50/photo_hypotheses.csv")
    ids = [f"H{index:02}" for index in range(1, 51)]
    prior = prior[["group", "filename", "sha256", *ids]].rename(columns={"sha256": "prior_source_sha256"})
    frame = frame.merge(prior, on=["group", "filename"], validate="one_to_one")
    if len(frame) != 257 or not frame.sha256.eq(frame.prior_source_sha256).all():
        raise ValueError("the anchor study must match the verified257-photo source snapshot")
    frame["source_path"] = [str(args.photos / group / name) for group, name in zip(frame.group, frame.filename, strict=True)]
    return frame.copy(), metadata, previous_names, ids, coverage


def consensus_parameters(train: pd.DataFrame, full: pd.DataFrame, definitions: dict, scores: dict,
                         reference: str) -> tuple[pd.Series, dict]:
    selected, parameters = {}, {}
    for family in geometry.FAMILIES:
        candidates = [name for name in definitions if definitions[name]["family"] == family]
        chosen = min(candidates, key=lambda name: (-scores[name], name))
        pair = train[[chosen, reference]].dropna()
        scale = audit.robust_mad(pair[chosen].to_numpy())
        if not np.isfinite(scale) or scale <= geometry.EPS or len(pair) < 8:
            return pd.Series(np.nan, index=full.index), {"available": False, "reason": f"invalid train scale for {family}"}
        centre = float(pair[chosen].median())
        rho = float(spearmanr(pair[chosen], pair[reference]).statistic)
        if not np.isfinite(rho):
            return pd.Series(np.nan, index=full.index), {"available": False, "reason": f"undefined train correlation for {family}"}
        sign = 1 if rho >= 0 else -1
        selected[family] = np.clip(sign * (full[chosen] - centre) / scale, -5, 5)
        parameters[family] = {"metric": chosen, "median": centre, "mad": scale, "sign": sign,
                              "rho_to_reference_train": rho, "training_score": scores[chosen]}
    values = pd.DataFrame(selected).mean(axis=1, skipna=False)
    return values, {"available": True, "parameters": parameters, "weight": 0.25,
                    "selection": "one metric per family using early-month robustness only",
                    "scaling": "early-date median/MAD, polarity by early correlation to reference, z clipped[-5,5]"}


def write_html(path: Path, report: dict):
    def number(value):
        return f"{value:.3f}" if value is not None and np.isfinite(value) else "n/a"

    rows = []
    for name in sorted(report["metrics"], key=lambda key: (
            -report["metrics"][key]["training_score"] if report["metrics"][key]["training_score"] is not None else math.inf, key)):
        row = report["metrics"][name]
        cells = [name, row["definition"]["family"], number(row["training_score"]),
                 number(row["cohorts"]["test"]["worst_auc"]), number(row["delta_old"]), number(row["delta_H23"]),
                 " to ".join(number(value) for value in row["bootstrap_H23"]["delta_ci95"]),
                 number(row["cohorts"]["neutral"]["worst_auc"]), number(row["cohorts"]["strict"]["worst_auc"]),
                 number(row["cohorts"]["pose_adjusted_test"]["worst_auc"]),
                 str(row["association"]["p_bonferroni_family"]), row["diagnostics"]["status"],
                 row["definition"]["description"]]
        rows.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")
    headers = ("Single descriptor", "Family", "Early robustness", "Later worst AUC", "Delta old", "Delta H23",
               "Delta H23 95% CI", "Neutral AUC", "Strict AUC", "Pose-adjusted AUC", "Association p corrected", "Outcome", "Definition")
    text = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orbital and Glabellar Anchor Geometry</title><style>
body{font:15px/1.5 system-ui,sans-serif;max-width:1650px;margin:24px auto;padding:0 18px;color:#17212b;background:#f8fafb}
table{border-collapse:collapse;background:white;font-size:12px}td,th{padding:8px;border:1px solid #cbd8df;vertical-align:top;text-align:left}
th{background:#dcebf1}.scroll{overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0f4;padding:12px}
.notice{border-left:4px solid #b85e28;background:#fff4e8;padding:14px}li{margin:7px 0}
</style><h1>Orbital and Glabellar Anchor Geometry</h1>
<p class="notice">67 fixed single descriptors on full35,709-vertex identity meshes, plus one training-only equal-family consensus.
These are model surface proxies, not measured bony anatomy. No identities or sensitive traits are inferred; production bands are unchanged.</p>
<p>PRDL in the paper is Part Re-projection Distance Loss on2D semantic point sets and an image-grid anchor set.
Here min/mean/max3D distances to the glabella are labelled as an analogue, not the original PRDL loss.
Spherical features are partial-patch radial shape moments, never the model's alpha_sh illumination coefficients.</p>"""
    text += "<h2>Benchmarks and Counts</h2><pre>" + html.escape(json.dumps({
        "benchmarks": report["benchmarks"], "outcomes": report["status_counts"], "best_by_family": report["best_by_family"]}, indent=2)) + "</pre>"
    text += "<h2>All Singles and Consensus</h2><div class='scroll'><table><tr>" + "".join(f"<th>{item}</th>" for item in headers)
    text += "</tr>" + "".join(rows) + "</table></div><h2>Training-Only Combination</h2><pre>"
    text += html.escape(json.dumps(report["consensus_fit"], indent=2)) + "</pre><h2>Method Definitions</h2><pre>"
    text += html.escape(json.dumps(report["method_definitions"], indent=2)) + "</pre><h2>Limitations</h2><ul>"
    text += "".join(f"<li>{html.escape(item)}</li>" for item in report["limitations"]) + "</ul></html>"
    path.write_text(text, encoding="utf-8")


def run(args):
    bands = ROOT / "morphing/backend/metric_bands.json"
    bands_hash = audit.sha256(bands)
    frame, previous_meta, old_names, prior_ids, coverage = load_foundation(args)
    paths, manifest = geometry.ensure_mesh_cache(frame, args.mesh_cache, args.cache)
    if manifest["errors"] or len(paths) != len(frame):
        raise RuntimeError(f"full-mesh extraction incomplete: {manifest['errors']}")
    with np.load(manifest["topology_path"], allow_pickle=False) as topology:
        triangles, l106, l134 = topology["triangles"], topology["ldm106_indices"], topology["ldm134_indices"]
    records, quality, definitions, region_metadata = [], [], None, None
    for position, row in enumerate(frame.to_dict("records")):
        with np.load(paths[(row["group"], row["filename"])], allow_pickle=False) as cached:
            values, metadata = geometry.compute_anchor_features(cached["vertices"], triangles, l106, l134)
        if definitions is None:
            definitions = {name: dict(definition) for name, definition in metadata["features"].items()}
            region_metadata = metadata
        if set(values) != set(definitions):
            raise ValueError("the fixed descriptor catalogue changed across images")
        records.append({"group": row["group"], "filename": row["filename"], **values})
        quality.append({"group": row["group"], "filename": row["filename"], **metadata["quality"]})
        if (position + 1) % 20 == 0 or position + 1 == len(frame):
            print(f"Full-surface descriptors {position + 1}/{len(frame)}", flush=True)
    frame = frame.merge(pd.DataFrame(records), on=["group", "filename"], validate="one_to_one").copy()
    ids = list(definitions)
    previous = [*old_names, *prior_ids]
    numeric = [*previous, *ids, *audit.POSE, "jawOpen", "smile", "alpha_exp"]
    cohorts = study.cohort_tables(frame, numeric)
    signs = {name: audit.training_signs(cohorts["train"], name) for name in [*previous, *ids]}
    old_scores = {name: study.training_score(cohorts, name, signs[name]) for name in old_names}
    old_benchmark = min(old_names, key=lambda name: (-old_scores[name], name))
    scores = {name: study.training_score(cohorts, name, signs[name]) for name in ids}
    consensus, consensus_fit = consensus_parameters(cohorts["train"], frame, definitions, scores, old_benchmark)
    frame["anchor_consensus4"] = consensus
    definitions["anchor_consensus4"] = {"family": "consensus", "unit": "dimensionless",
                                         "description": "Equal mean of four training-selected, train-scaled family descriptors; no later-month fitting."}
    ids.append("anchor_consensus4")
    numeric.append("anchor_consensus4")
    cohorts = study.cohort_tables(frame, numeric)
    signs["anchor_consensus4"] = audit.training_signs(cohorts["train"], "anchor_consensus4")
    args.out.mkdir(parents=True, exist_ok=True)
    identifiers = ["group", "filename", "date", "month", "train", "neutral", "strict", "sha256"]
    frame[[*identifiers, *ids]].to_csv(args.out / "photo_metrics.csv", index=False)
    (args.out / "mesh_quality.json").write_text(json.dumps(audit.clean_json(quality), indent=2), encoding="utf-8")
    if args.features_only:
        return None
    nearest = study.nearest_existing(cohorts["train"], ids, previous)
    rng = np.random.default_rng(args.seed)
    weights = study.bootstrap_weights(cohorts["test"], args.bootstrap, rng)
    old_samples = study.bootstrapped_pairs(cohorts["test"], old_benchmark, signs[old_benchmark], weights)
    h23_samples = study.bootstrapped_pairs(cohorts["test"], "H23", signs["H23"], weights)
    old_test = audit.summarize(cohorts["test"], old_benchmark, signs[old_benchmark])
    h23_test = audit.summarize(cohorts["test"], "H23", signs["H23"])
    metrics = {}
    for position, name in enumerate(ids):
        stats = {key: audit.summarize(table, name, signs[name]) for key, table in cohorts.items()}
        adjusted, beta = audit.pose_adjustment(cohorts["train"], cohorts["test"], name)
        stats["pose_adjusted_test"] = audit.summarize(adjusted, name, signs[name])
        samples = study.bootstrapped_pairs(cohorts["test"], name, signs[name], weights)
        metrics[name] = {"definition": definitions[name], "training_score": study.training_score(cohorts, name, signs[name]),
                         "cohorts": stats, "delta_test_auc": stats["test"]["worst_auc"] - old_test["worst_auc"],
                         "delta_old": stats["test"]["worst_auc"] - old_test["worst_auc"],
                         "delta_H23": stats["test"]["worst_auc"] - h23_test["worst_auc"],
                         "bootstrap": study.confidence_intervals(samples, old_samples, len(ids)),
                         "bootstrap_H23": study.confidence_intervals(samples, h23_samples, len(ids)),
                         "nearest_existing": nearest[name], "pose_slopes_from_train": dict(zip(audit.POSE, beta, strict=True)),
                         "expression_correlation_train": audit.within_group_correlations(cohorts["train"], name, ("jawOpen", "smile", "alpha_exp"))}
        if (position + 1) % 10 == 0:
            print(f"Anchor uncertainty/pose diagnostics {position + 1}/{len(ids)}", flush=True)
    months = cohorts["test"].groupby(["group", "month", "train"])[numeric].median().reset_index()
    associations = study.permutation_association(months, ids, signs, args.permutations, rng)
    status_counts = {}
    for name, row in metrics.items():
        row["association"] = associations[name]
        row["diagnostics"] = study.hypothesis_status(row, family_size=len(ids))
        row["association"]["p_bonferroni_family"] = row["association"].pop("p_bonferroni50")
        status = row["diagnostics"]["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    best_by_family = {family: min([name for name in ids if definitions[name]["family"] == family],
                                  key=lambda name: (-metrics[name]["training_score"], name)) for family in geometry.FAMILIES}
    report = {"schema_version": "anchor-full-mesh-research-v1", "deployment_ready": False,
              "n_photos": len(frame), "n_singles": 67, "n_evaluated": len(ids), "coverage": coverage,
              "mesh_manifest": manifest, "region_metadata": region_metadata, "consensus_fit": consensus_fit,
              "metrics": metrics, "best_by_family": best_by_family, "status_counts": status_counts,
              "benchmarks": {"old_training_selected": {"name": old_benchmark, "test_worst_auc": old_test["worst_auc"]},
                             "previous_batch_H23": {"name": "H23", "test_worst_auc": h23_test["worst_auc"]}},
              "protocol": {"train_month_fraction": args.train_fraction, "bootstrap_month_samples": args.bootstrap,
                           "label_permutations": args.permutations, "family_size": len(ids), "seed": args.seed,
                           "single_selection": "all67 predefined; family leaders and consensus fitted using early dates only"},
              "method_definitions": {"geodesic": "Dijkstra on every real triangle edge of the full face mesh, not on a landmark-neighbour graph; continuous-geodesic upper bound",
                                     "section8": "The external section8 source was not provided or identified; no exact section-specific algorithm is claimed.",
                                     "curvature": "cotangent mean curvature magnitude and interior angle-deficit Gaussian curvature; barycentric-area-weighted patch quantiles",
                                     "shape_SH": "anchor-centred radial point-measure spherical moments l1..3 on partial surface patches; not the lighting alpha_sh parameters",
                                     "PRDL_original": "Part Re-projection Distance Loss:2D semantic point sets, fixed image-grid anchors, min/max/mean distance descriptors, squared target/prediction difference",
                                     "PRDL_tested_analogue": "min/area-weighted mean/max3D distances from orbital/brow surface patches to moving model glabella anchor; NOT original2D PRDL loss",
                                     "source_paper": "https://arxiv.org/html/2312.00311#S3.SS3", "lighting_source": "https://arxiv.org/html/2312.00311#S3.SS1"},
              "provenance": {"bands_sha256": bands_hash, "landmark_cache_sha256": {path.name: audit.sha256(path) for path in sorted(args.cache.glob("*.npz"))},
                             "code_sha256": {str(path.relative_to(ROOT)): audit.sha256(path) for path in (Path(__file__), ROOT / "app9/validation/anchor_mesh_features.py",
                                                                                                        ROOT / "app9/validation/hypotheses50.py")}},
              "limitations": ["All faces are3DMM reconstructions from frontal images, not independently scanned anatomical surfaces.",
                              "The five anchors are mean-template surface proxies. Orbital upper-lid/brow anchors do not locate actual bony orbital rims.",
                              "Geodesic values are edge-graph approximations; an exact continuous surface solver for the unspecified section8 is not tested.",
                              "Curvature and spherical moments can describe reconstruction priors/noise rather than real person-specific anatomy.",
                              "Original PRDL is a2D fitting loss. Ground-truth2D semantic masks and an original PRDL fitting comparison are unavailable; only an explicitly labelled3D descriptor analogue is tested.",
                              "Moving anatomical anchors and radius-defined surface patches differ from the paper's fixed image-grid anchors and semantic segmentation point sets.",
                              "The same dataset and later periods were previously explored. This is internal exploratory comparison, not independent prospective validation.",
                              "Month-label permutation exchangeability may fail due to capture period, camera, expression and source-processing confounding.",
                              "Bootstrap confidence intervals and nominal simultaneous percentile intervals are approximate with few month blocks.",
                              "No AUC is an identity probability, no sensitive trait is inferred, and no production metric band is changed."]}
    report = audit.clean_json(report)
    flat = []
    for name, row in report["metrics"].items():
        ci = row["bootstrap_H23"]["delta_ci95"]
        item = {"metric": name, "family": row["definition"]["family"], "training_score": row["training_score"],
                "delta_old": row["delta_old"], "delta_H23": row["delta_H23"],
                "delta_H23_ci_low": ci[0] if ci else None, "delta_H23_ci_high": ci[1] if ci else None,
                "p_bonferroni_family": row["association"]["p_bonferroni_family"], "p_maxT": row["association"]["p_maxT_global_null"],
                "nearest_existing": row["nearest_existing"]["name"], "nearest_rho": row["nearest_existing"]["rho"],
                "status": row["diagnostics"]["status"], "failures": "; ".join(row["diagnostics"]["failures"])}
        for key, stats in row["cohorts"].items():
            item[f"{key}_worst_auc"] = stats["worst_auc"]
        flat.append(item)
    pd.DataFrame(flat).sort_values("training_score", ascending=False).to_csv(args.out / "results.csv", index=False)
    (args.out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_html(args.out / "report.html", report)
    if audit.sha256(bands) != bands_hash:
        raise RuntimeError("production bands changed during the study")
    print("Anchor outcomes:", status_counts, flush=True)
    for family, name in best_by_family.items():
        row = report["metrics"][name]
        print(family, name, row["cohorts"]["test"]["worst_auc"], "delta_H23", row["delta_H23"], flush=True)
    print("Four-family consensus", report["metrics"]["anchor_consensus4"]["cohorts"]["test"]["worst_auc"], flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / ".runtime/frontal_separability")
    parser.add_argument("--mesh-cache", type=Path, default=ROOT / ".runtime/anchor_geometry")
    parser.add_argument("--photos", type=Path, default=Path("/Volumes/SDCARD/test_photos"))
    parser.add_argument("--angles-dir", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=ROOT / "app9/validation/report/anchor_geometry")
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--bootstrap", type=int, default=20000)
    parser.add_argument("--permutations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--features-only", action="store_true")
    args = parser.parse_args()
    if args.bootstrap < 1000 or args.permutations < 1000:
        parser.error("at least1000 bootstrap draws and1000 permutations required")
    with threadpool_limits(limits=2, user_api="blas"):
        run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
