#!/usr/bin/env python
"""Reproducible UV quality analysis, with a locked test and no material diagnosis."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .contour_validation import check_manual_contours, independent_landmarks, validate_contours
from .diagnostic_report import json_value, save_batch_index, save_diagnostic_png, save_viewer, write_json
from .distortion_features import texture_diagnostics
from .hd_uv_generator import HDUVConfig, HDUVTextureGenerator
from .quality_regions import NAMES, build_regions
from .reconstruction_adapter import ROOT, reconstruct_for_uv, sha256
from .uvio import UVIOExporter
from .warp_metrics import region_summary, visible_photo_metrics


def generation_lock(config: HDUVConfig, study_dir: Path) -> tuple[str, dict]:
    from morphing.backend.mp_worker import resolve_asset
    baseline = json.loads((study_dir / "baseline_lock.json").read_text())
    assets = ROOT / "3ddfa_v3/assets"
    actual_weights = {name: sha256(assets / name) for name in baseline["weights_sha256"]}
    if actual_weights != baseline["weights_sha256"]:
        raise ValueError("reconstruction weights changed; a new explicit baseline is required")
    source = {str(path.relative_to(ROOT)): sha256(path) for path in sorted((ROOT / "uv_module").glob("*.py"))}
    versions = {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "pandas", "pyarrow", "scikit-learn", "Pillow", "torch", "mediapipe")}
    lock = {"schema_version": "uv-quality-generation-v1", "prechange_commit": baseline["git_commit"],
            "generator_config": asdict(config), "source_sha256": source, "weights_sha256": actual_weights,
            "independent_contour_model_sha256": sha256(resolve_asset()), "library_versions": versions,
            "opencv_runtime": cv2.__version__, "split_lock_sha256": sha256(study_dir / "split_lock.json"),
            "reconstruction": {"device": "cpu", "threads": 2, "image_decode": "EXIF-oriented original pixels"},
            "label_policy": "old UV labels are reference annotations, not automatic verified labels of regenerated UV; no material target"}
    identity = hashlib.sha256(json.dumps(lock, sort_keys=True).encode()).hexdigest()[:20]
    return identity, lock


def frame_features(metadata, recon, contours, regions, texture, provenance, original):
    features = {"pose_pitch_deg": float(recon["angles_deg"][0]), "pose_yaw_deg": float(recon["angles_deg"][1]),
                "pose_roll_deg": float(recon["angles_deg"][2]), "face_resolution_px": contours.get("normalization_pixels"),
                "observed_fraction": float(provenance["observed_fraction"].mean()),
                "measurement_suitable_fraction": float(provenance["measurement_suitable"].mean()),
                "source_density_median": float(np.nanmedian(provenance["source_density"]))}
    gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
    box = contours.get("observed_face_bbox")
    if box:
        x0, y0, x1, y1 = box
        features["face_resolution_px"] = float(np.sqrt(max(x1 - x0, 0) * max(y1 - y0, 0)))
        cropped = gray[max(0, int(y0)):min(gray.shape[0], int(np.ceil(y1))), max(0, int(x0)):min(gray.shape[1], int(np.ceil(x1)))]
    else:
        cropped = gray
    features["source_sharpness"] = float(cv2.Laplacian(cropped, cv2.CV_32F).var()) if cropped.size else None
    for zone, metrics in regions.items():
        features[f"{zone}_invalid_surface_fraction"] = metrics["invalid_surface_fraction"]
        for kind in ("anisotropy_3d_uv", "anisotropy_uv_photo", "density_uv_photo"):
            for statistic in ("median", "iqr", "p95"):
                features[f"{zone}_{kind}_{statistic}"] = metrics[kind][statistic]
    for zone, metrics in contours.items():
        if isinstance(metrics, dict):
            for key in ("median_error_normalized", "p95_error_normalized", "median_abs_error_px", "p95_abs_error_px"):
                if key in metrics:
                    features[f"contour_{zone}_{key}"] = metrics[key]
    for zone, metrics in texture.items():
        for name in ("transport_gradient_residual_median", "transport_color_residual_median"):
            features[f"texture_transport_{zone}_{name}"] = metrics[name]
    return features


def analyze_sample(row, config, generation_id, output, study_dir, client):
    sample_dir = output / "samples" / row.sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    source = Path(row.original_path) if isinstance(row.original_path, str) else None
    source_available = source is not None and source.is_file()
    source_hash = sha256(source) if source_available else None
    if source_available and source_hash != row.source_sha256:
        raise ValueError("original source hash differs from the frozen manifest")
    inputs = {key: getattr(row, key, None) for key in (
        "original_path", "source_sha256", "partition", "quality_label_reference", "reference_uv_path",
        "label_generation_id", "label_status", "region_annotations_json", "manual_contours_json")}
    inputs["available_source_sha256"] = source_hash
    inputs_hash = hashlib.sha256(json.dumps(json_value(inputs), sort_keys=True).encode()).hexdigest()
    existing = sample_dir / "diagnosis.json"
    if existing.is_file():
        try:
            prior = json.loads(existing.read_text())
        except (OSError, ValueError):
            prior = None
        if (isinstance(prior, dict) and prior.get("generation_id") == generation_id
                and prior.get("sample_id") == row.sample_id and prior.get("analysis_inputs_sha256") == inputs_hash):
            values = prior.get("features")
            artifacts = ("viewer.html", "diagnostic.png", "reconstruction.npz", "visibility.npz",
                         "sample_raw_float.npz", "sample_provenance.npz", "sample_warp_metrics.npz")
            if (prior.get("processing_status") == "complete" and isinstance(values, dict)
                    and values.get("sample_id") == row.sample_id and values.get("partition") == row.partition
                    and values.get("generation_id") == generation_id
                    and all((sample_dir / name).is_file() for name in artifacts)):
                return prior, values
            if not source_available and prior.get("processing_status") == "missing_source":
                return prior, None
    if not source_available:
        result = {"sample_id": row.sample_id, "partition": row.partition, "status": "insufficient_data",
                  "reason": "original source photograph is missing", "generation_id": generation_id,
                  "analysis_inputs_sha256": inputs_hash, "processing_status": "missing_source"}
        write_json(sample_dir / "diagnosis.json", result)
        return result, None
    image, recon, reconstruction_meta = reconstruct_for_uv(Path(row.original_path), study_dir / "reconstruction_cache")
    if reconstruction_meta["source_sha256"] != row.source_sha256:
        raise ValueError("original source hash differs from the frozen manifest")
    recon["projection_space"] = "original"
    annotation_generation = getattr(row, "label_generation_id", None)
    if annotation_generation == generation_id and row.label_status != "disputed" and isinstance(getattr(row, "region_annotations_json", None), str):
        external = np.full((config.uv_size, config.uv_size), -1, dtype=np.int8)
        for annotation in json.loads(row.region_annotations_json):
            value = annotation.get("external_occlusion", -1)
            polygon = np.asarray(annotation.get("uv_polygon", []), dtype=float)
            if value in (0, 1) and polygon.ndim == 2 and polygon.shape[1] == 2 and len(polygon) >= 3:
                stamp = np.zeros(external.shape, dtype=np.uint8)
                cv2.fillPoly(stamp, [np.rint(polygon).astype(np.int32)], 1)
                external[stamp > 0] = value
        recon["external_occlusion_uv"] = external
    generator = HDUVTextureGenerator(config)
    analysis, beauty, mask, confidence, aux = generator.generate(image, recon)
    raw, provenance = aux["uv_texture_raw"], aux["provenance"]
    independent, contours = None, {"manual_validation_status": "unavailable"}
    try:
        independent = independent_landmarks(image, client)
        contours = validate_contours(recon, independent, aux["visibility_buffers"])
        manual_json = getattr(row, "manual_contours_json", None)
        if isinstance(manual_json, str) and manual_json != "{}":
            contours["manual_comparison"] = check_manual_contours(json.loads(manual_json), independent)
        comparison_model = np.asarray(contours["model_contour_points"])
        comparison_target = np.asarray(contours["observed_contour_points"])
        distances, indices = cKDTree(comparison_model).query(recon["vertices_2d"])
        vertex_errors = np.linalg.norm(comparison_model - comparison_target, axis=1)[indices]
        vertex_errors[distances > 0.03 * contours["normalization_pixels"]] = np.nan
        triangle_values = vertex_errors[recon["triangles"]]
        triangle_counts = np.isfinite(triangle_values).sum(axis=1)
        triangle_errors = np.divide(np.nansum(triangle_values, axis=1), triangle_counts,
                                    out=np.full(len(triangle_counts), np.nan), where=triangle_counts > 0)
        mapped = provenance["triangle_id"] >= 0
        error_map = np.full(mask.shape, np.nan, dtype=np.float32)
        error_map[mapped] = triangle_errors[provenance["triangle_id"][mapped]]
        provenance["contour_error_px"] = error_map
    except Exception as exc:
        contours["independent_method_error"] = f"{type(exc).__name__}: {exc}"
    triangle_regions, region_masks, region_meta = build_regions(recon["uv_coords"], recon["triangles"], config.uv_size,
                                                               ROOT / "3ddfa_v3/assets/face_model.npy")
    warp = aux["triangle_warp_metrics"]
    summaries = region_summary(warp, triangle_regions, NAMES, recon["triangles"])
    texture = texture_diagnostics(image, raw, provenance, warp, region_masks)
    np.savez_compressed(sample_dir / "reconstruction.npz", **{key: value for key, value in recon.items() if isinstance(value, np.ndarray)})
    np.savez_compressed(sample_dir / "visibility.npz", **{key: value for key, value in aux["visibility_buffers"].items() if isinstance(value, np.ndarray)})
    UVIOExporter(save_auxiliary=True).save_all(str(sample_dir), "sample", recon["vertices"], recon["triangles"], recon["uv_coords"],
                                              analysis, beauty, mask, confidence, aux)
    metadata = {**reconstruction_meta, "sample_id": row.sample_id, "generation_id": generation_id,
                "generator_config": asdict(config), "region_definitions": region_meta,
                "source_texture_detail": "density/scales are source-pixels per UV-texel; not millimetres",
                "sampling_interpolation": aux["raw_sampling_interpolation"]}
    public_metadata = {key: metadata[key] for key in ("sample_id", "source_sha256", "generation_id", "generator_config",
                                                      "original_coordinate_definition", "oriented_image_size", "sampling_interpolation")}
    viewer = sample_dir / "viewer.html"
    save_viewer(viewer, image, raw, beauty, recon, provenance, warp, public_metadata, aux["visibility_buffers"], independent)
    anisotropy = np.full(mask.shape, np.nan)
    mapped = provenance["triangle_id"] >= 0
    anisotropy[mapped] = warp["anisotropy_uv_photo"][provenance["triangle_id"][mapped]]
    save_diagnostic_png(sample_dir / "diagnostic.png", image, raw, beauty, provenance, anisotropy, recon, independent)
    result = {"sample_id": row.sample_id, "partition": row.partition, "generation_id": generation_id,
              "analysis_inputs_sha256": inputs_hash, "processing_status": "complete",
              "status": "insufficient_data", "reason": "current-generation labels, manual contour validation and external-occlusion assessment are pending",
              "quality_score": None, "probability": None, "material_inference": False,
              "old_quality_label_reference": row.quality_label_reference, "old_reference_uv_path": row.reference_uv_path,
              "old_label_is_not_current_ground_truth": True, "regions": summaries, "independent_contours": contours,
              "texture": texture, "provenance_summary": {"observed_fraction": float(mask.mean()),
                  "external_occlusion_unknown_fraction": float(np.mean(provenance["external_occlusion"] == -1)),
                  "measurement_suitable_fraction": float(provenance["measurement_suitable"].mean()),
                  "synthetic_visual_fraction": float(np.mean(provenance["beauty_method"] >= 3))},
              "viewer_relative": str(viewer.relative_to(output)), "metadata": metadata}
    features = json_value(frame_features(metadata, recon, contours, summaries, texture, provenance, image))
    features.update({"sample_id": row.sample_id, "partition": row.partition, "generation_id": generation_id})
    result["features"] = features
    # Commit the report and its feature row together, after all artifacts are saved.
    write_json(sample_dir / "diagnosis.json", result)
    return result, features


def reference_and_sensitivity(manifest, output, config, generation_id, study_dir, sample_count):
    from .normal_reference import fit_reference, score_reference
    from .stability import geometry_repeats
    from .warp_metrics import largest_connected_anomaly, triangle_warp_metrics
    candidates = manifest[manifest.partition.eq("train") & manifest.quality_label_reference.eq("normal") & manifest.original_path.notna()]
    training, repeat_differences, repeats_by_sample, reports = [], {}, {}, []
    for _, row in candidates.iterrows():
        diagnosis_path = output / "samples" / row.sample_id / "diagnosis.json"
        if not diagnosis_path.is_file():
            continue
        diagnosis = json.loads(diagnosis_path.read_text())
        if "regions" not in diagnosis:
            continue
        image, recon, _ = reconstruct_for_uv(Path(row.original_path), study_dir / "reconstruction_cache")
        metrics = triangle_warp_metrics(recon["vertices_object"], recon["triangles"], recon["uv_coords"], recon["vertices_2d"], config.uv_size)
        with np.load(output / "samples" / row.sample_id / "sample_warp_metrics.npz") as stored:
            visible = stored["triangle_visible"]
        metrics = visible_photo_metrics(metrics, visible)
        face_scale = diagnosis["independent_contours"].get("normalization_pixels")
        if not face_scale:
            continue
        pose = [float(recon["angles_deg"][1]), float(recon["angles_deg"][0]), float(np.log(face_scale))]
        training.append({"sample_id": row.sample_id, "partition": "train", "generation_id": generation_id, "pose_detail": pose,
                         "metrics": metrics, "label_current_verified": False})
        if len(reports) < sample_count:
            with np.load(output / "samples" / row.sample_id / "sample_raw_float.npz") as stored:
                base_raw = stored["texture"]
            with np.load(output / "samples" / row.sample_id / "sample_provenance.npz") as stored:
                base_observed = stored["observed_fraction"] > 0
            summary, differences, variant_metrics = geometry_repeats(image, recon, config.uv_size,
                 output / "stability" / row.sample_id, study_dir / "reconstruction_cache",
                 generator_config=config, base_raw=base_raw, base_observed=base_observed, base_triangle_visible=visible)
            reports.append({"sample_id": row.sample_id, "runs": summary})
            repeats_by_sample[row.sample_id] = variant_metrics
            for key, arrays in differences.items():
                repeat_differences.setdefault(key, []).extend(arrays)
    reference = fit_reference(training, repeat_differences, generation_id, provisional=True)
    info = {key: value for key, value in reference.items() if key not in ("metrics", "floors")}
    info["reference_labels"] = "legacy normal UV selection; provisional, not verified after regeneration"
    if reference["status"] in ("fitted", "provisional_reference"):
        arrays = {f"values_{key}": value for key, value in reference["metrics"].items()}
        arrays.update({f"floor_{key}": value for key, value in reference["floors"].items()})
        np.savez_compressed(output / "normal_reference.npz", **arrays)
    write_json(output / "normal_reference.json", info)
    write_json(output / "stability.json", {"scope": "specific pipeline input sensitivity; not full uncertainty", "samples": reports})
    for _, row in manifest[manifest.partition.isin(["train", "validation"]) & manifest.original_path.notna()].iterrows():
        path = output / "samples" / row.sample_id / "diagnosis.json"
        if not path.exists():
            continue
        diagnosis = json.loads(path.read_text())
        if "regions" not in diagnosis:
            continue
        _, recon, _ = reconstruct_for_uv(Path(row.original_path), study_dir / "reconstruction_cache")
        scale = diagnosis["independent_contours"].get("normalization_pixels")
        if not scale:
            continue
        metrics = triangle_warp_metrics(recon["vertices_object"], recon["triangles"], recon["uv_coords"], recon["vertices_2d"], config.uv_size)
        with np.load(path.parent / "sample_warp_metrics.npz") as stored:
            metrics = visible_photo_metrics(metrics, stored["triangle_visible"])
        score = score_reference(reference, metrics, [float(recon["angles_deg"][1]), float(recon["angles_deg"][0]), float(np.log(scale))])
        if "deviation" in score:
            np.savez_compressed(path.parent / "normal_deviation.npz", **score["deviation"])
            selected = np.any(np.stack([np.abs(values) > 3 for values in score["deviation"].values()]), axis=0)
            summary = {"status": score["status"], "support_samples": score["support_samples"],
                       "candidate_triangle_fraction": float(selected.mean()),
                        "largest_connected_candidate_area": largest_connected_anomaly(recon["triangles"], selected, metrics["area_surface"]),
                        "photo_metric_scope": "visible triangles only; intrinsic surface deviations are a separate modeled quantity",
                       "not_a_confirmed_defect": True}
            if row.sample_id in repeats_by_sample:
                overlaps = []
                for variant in repeats_by_sample[row.sample_id]:
                    variant_score = score_reference(reference, variant, [float(recon["angles_deg"][1]), float(recon["angles_deg"][0]), float(np.log(scale))])
                    if "deviation" in variant_score:
                        variant_selected = np.any(np.stack([np.abs(values) > 3 for values in variant_score["deviation"].values()]), axis=0)
                        union, intersection = selected | variant_selected, selected & variant_selected
                        overlaps.append(float(metrics["area_surface"][intersection].sum() / max(metrics["area_surface"][union].sum(), 1e-12)))
                summary["candidate_map_repeat_overlap"] = overlaps
            write_json(path.parent / "normal_deviation_summary.json", summary)


def analyze(args):
    from morphing.backend.mp_worker import LandmarkerClient
    manifest = pd.read_parquet(args.study_dir / "manifest.parquet")
    config = HDUVConfig(uv_size=args.uv_size, super_sample=args.super_sample, collect_provenance=True, device="cpu")
    generation_id, lock = generation_lock(config, args.study_dir)
    output = args.study_dir / "runs" / generation_id
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "run_lock.json", lock)
    partitions = set(args.partitions.split(","))
    if "test" in partitions:
        release = args.study_dir / "test_release_lock.json"
        if not release.is_file() or json.loads(release.read_text()).get("generation_id") != generation_id:
            raise ValueError("closed test cannot be inspected before an explicit matching release lock")
        lock_release = json.loads(release.read_text())
        model_file = output / "classifier/quality_model.joblib"
        if not model_file.exists() or sha256(model_file) != lock_release["model_sha256"]:
            raise ValueError("model changed after the closed-test release freeze")
    selected = manifest[manifest.partition.isin(partitions)]
    if args.limit:
        selected = selected.head(args.limit)
    results, features = [], []
    existing_features = output / "features.parquet"
    client = LandmarkerClient()
    try:
        for position, (_, row) in enumerate(selected.iterrows()):
            try:
                diagnosis, values = analyze_sample(row, config, generation_id, output, args.study_dir, client)
            except Exception as exc:
                diagnosis = {"sample_id": row.sample_id, "partition": row.partition, "generation_id": generation_id,
                             "status": "insufficient_data", "processing_status": "error",
                             "reason": f"{type(exc).__name__}: {exc}"}
                sample_dir = output / "samples" / row.sample_id
                sample_dir.mkdir(parents=True, exist_ok=True)
                write_json(sample_dir / "diagnosis.json", diagnosis)
                values = None
            results.append(diagnosis)
            if values:
                features.append(values)
            print(f"UV quality {position + 1}/{len(selected)}: {row.sample_id} {diagnosis['status']}", flush=True)
    finally:
        client.close()
    if features or existing_features.is_file():
        table = pd.DataFrame(features)
        if existing_features.is_file():
            previous = pd.read_parquet(existing_features)
            previous = previous[previous.generation_id.eq(generation_id) & ~previous.sample_id.isin(selected.sample_id)]
            table = pd.concat((previous, table), ignore_index=True)
        table = table.drop_duplicates("sample_id", keep="last")
        temporary = output / ".features.parquet.tmp"
        table.to_parquet(temporary, index=False)
        temporary.replace(existing_features)
        temporary = output / ".features.csv.tmp"
        table.to_csv(temporary, index=False)
        temporary.replace(output / "features.csv")
    if args.stability_samples:
        reference_and_sensitivity(manifest, output, config, generation_id, args.study_dir, args.stability_samples)
    summary = {"generation_id": generation_id, "manifest_samples": len(manifest), "requested_samples": len(selected),
                "completed_source_analyses": len(features), "source_or_processing_failures": len(selected) - len(features),
                "missing_source_photographs": sum(row.get("processing_status") == "missing_source" for row in results),
                "processing_errors": sum(row.get("processing_status") == "error" for row in results),
               "closed_test_evaluated": "test" in partitions, "validated_current_labels": 0,
               "classifier_ready": False, "probabilities_calibrated": False,
               "blockers": ["current labels must be reviewed after technical fixes", "manual independent-contour ground truth missing",
                            "external occlusion unknown", "closed test kept untouched"],
               "baseline_lock": str(args.study_dir / "baseline_lock.json")}
    write_json(output / "summary.json", summary)
    save_batch_index(output / "report.html", results, summary)
    write_json(args.study_dir / "latest_run.json", {"generation_id": generation_id, "output": str(output.resolve())})
    print(json.dumps(json_value(summary), indent=2), flush=True)
    return 0


def annotation_action(args):
    from .annotations import import_annotations, repeat_agreement
    manifest_path = args.study_dir / "manifest.parquet"
    manifest = pd.read_parquet(manifest_path)
    if args.action == "agreement":
        first = sorted(args.annotations.glob("*.json"))
        second = sorted(args.annotations_second.glob("*.json"))
        report = repeat_agreement(first, second)
    else:
        manifest, report = import_annotations(manifest, sorted(args.annotations.glob("*.json")))
        manifest.to_parquet(manifest_path, index=False)
        manifest.to_csv(args.study_dir / "manifest.csv", index=False)
    write_json(args.study_dir / (args.action + ".json"), report)
    print(json.dumps(json_value(report), indent=2))
    return 0


def classifier_action(args):
    from .quality_classifier import evaluate_closed_test, train_quality
    latest = json.loads((args.study_dir / "latest_run.json").read_text())
    output = Path(latest["output"])
    manifest = pd.read_parquet(args.study_dir / "manifest.parquet")
    if args.action == "freeze-test":
        model_path = output / "classifier/model.json"
        if not model_path.exists():
            raise ValueError("no validated model and threshold are available to freeze")
        model = json.loads(model_path.read_text())
        model_binary = output / "classifier/quality_model.joblib"
        if sha256(model_binary) != model["model_sha256"]:
            raise ValueError("model binary does not match the validated model record")
        run_lock = json.loads((output / "run_lock.json").read_text())
        actual_id, _ = generation_lock(HDUVConfig(**run_lock["generator_config"]), args.study_dir)
        if actual_id != latest["generation_id"]:
            raise ValueError("feature generator changed after validation; closed test remains locked")
        target = args.study_dir / "test_release_lock.json"
        frozen = {"generation_id": latest["generation_id"], "model_sha256": model["model_sha256"], "threshold": model["threshold"]}
        if target.exists() and json.loads(target.read_text()) != frozen:
            raise ValueError("closed test is already released to another frozen configuration")
        write_json(target, frozen)
        return 0
    features = pd.read_parquet(output / "features.parquet")
    if args.action == "train":
        report = train_quality(manifest, features, output / "classifier", latest["generation_id"])
    else:
        report = evaluate_closed_test(manifest, features, output / "classifier")
    print(json.dumps(json_value(report), indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, default=Path(".runtime/uv_quality"))
    parser.add_argument("--uv-size", type=int, default=1024)
    parser.add_argument("--super-sample", type=int, default=1)
    parser.add_argument("--partitions", default="train,validation")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--stability-samples", type=int, default=0)
    parser.add_argument("--action", choices=["analyze", "train", "evaluate-test", "freeze-test", "import-annotations", "agreement"], default="analyze")
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--annotations-second", type=Path)
    args = parser.parse_args()
    if args.action in ("import-annotations", "agreement"):
        if args.annotations is None or (args.action == "agreement" and args.annotations_second is None):
            parser.error("annotation directories required")
        return annotation_action(args)
    if args.action in ("train", "evaluate-test", "freeze-test"):
        return classifier_action(args)
    return analyze(args)


if __name__ == "__main__":
    raise SystemExit(main())
