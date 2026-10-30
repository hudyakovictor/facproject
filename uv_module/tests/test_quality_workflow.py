import json
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from uv_module.annotations import import_annotations, repeat_agreement
from uv_module import quality_pipeline
from uv_module.diagnostic_report import write_json
from uv_module.hd_uv_generator import HDUVConfig
from uv_module.normal_reference import METRICS, fit_reference, score_reference
from uv_module.quality_classifier import allowed_features, choose_threshold, training_readiness
from uv_module.stability import processing_variant
from uv_module.warp_metrics import region_summary, visible_photo_metrics


def test_identifiers_dates_material_and_labels_never_become_features():
    columns = ["sample_id", "person_id", "filename_code", "capture_date", "material_presence", "target", "quality_label_current",
               "pose_yaw_deg", "source_density_median", "face_resolution_px"]
    assert allowed_features(columns) == ["pose_yaw_deg", "source_density_median", "face_resolution_px"]


def test_classifier_refuses_legacy_reference_labels_as_current_truth():
    manifest = pd.DataFrame({"sample_id": ["s"], "quality_label_reference": ["normal"]})
    features = pd.DataFrame({"sample_id": ["s"], "generation_id": ["g"], "pose_yaw_deg": [0.0]})
    readiness, table = training_readiness(manifest, features, "g")
    assert not readiness["ready"] and table is None


def test_false_alarm_threshold_is_not_automatically_half_and_small_validation_is_not_certified():
    labels = np.array([0, 0, 0, 0, 1, 1, 1])
    scores = np.array([0.1, 0.2, 0.3, 0.8, 0.7, 0.9, 0.95])
    threshold, report = choose_threshold(labels, scores, maximum_fpr=0.05)
    assert threshold > 0.8
    assert report["validation_false_alarms"] == 0
    assert not report["deployment_ready_for_fpr_budget"]
    assert report["fpr_upper_one_sided95"] > 0.5


def synthetic_reference():
    records = [{"sample_id": f"s{i}", "partition": "train", "generation_id": "g", "label_current_verified": True,
                "pose_detail": [0, 10, np.log(500)], "metrics": {key: np.array([1, 2, 3]) * (1 + i / 100) for key in METRICS}}
               for i in range(6)]
    differences = {key: [np.array([0.01, 0.02, 0.03]), np.array([0.02, 0.01, 0.01])] for key in METRICS}
    return records, differences


def test_normal_reference_is_training_only_and_requires_measured_repeat_floor():
    records, differences = synthetic_reference()
    reference = fit_reference(records, differences, "g")
    assert reference["status"] == "fitted"
    records[0]["partition"] = "test"
    with pytest.raises(ValueError, match="training"):
        fit_reference(records, differences, "g")
    records[0]["partition"] = "train"
    assert fit_reference(records, {}, "g")["status"] == "insufficient_data"


def test_normal_reference_abstains_outside_pose_and_detail_support():
    records, differences = synthetic_reference()
    reference = fit_reference(records, differences, "g")
    metrics = records[0]["metrics"]
    score = score_reference(reference, metrics, [0, 10, np.log(500)])
    assert "deviation" in score
    unsupported = score_reference(reference, metrics, [60, 40, np.log(50)])
    assert unsupported["status"] == "insufficient_data"


def test_controlled_crop_and_resolution_return_to_original_pixel_centres():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    cropped, matrix = processing_variant(image, "small_offset_crop")
    assert cropped.shape[:2] == (100, 98)
    assert matrix @ [0, 0, 1] == pytest.approx([2, 0, 1])
    resized, matrix = processing_variant(image, "reduced_resolution_jpeg")
    assert resized.shape[:2] == (75, 75)
    assert matrix @ [0, 0, 1] == pytest.approx([1 / 6, 1 / 6, 1])


def test_disputed_blind_repeat_labels_are_not_confident_training_examples(tmp_path):
    manifest = pd.DataFrame({"sample_id": ["s"], "source_sha256": ["source"], "quality_label_current": [None],
                             "label_status": ["pending"], "region_annotations_json": ["[]"]})
    annotation = {"sample_id": "s", "source_sha256": "source", "generation_id": "g", "observer_id": "observer", "manual": True,
                  "round": "round1", "blind_to_prior": False, "quality_label_current": "normal", "regions": [],
                  "material_presence": True}
    first = tmp_path / "round1.json"
    first.write_text(json.dumps(annotation))
    updated, report = import_annotations(manifest, [first])
    assert report["accepted"] == 1 and report["material_fields_imported"] is False
    annotation.update(round="round2_blind", blind_to_prior=True, quality_label_current="distorted")
    second = tmp_path / "round2.json"
    second.write_text(json.dumps(annotation))
    updated, _ = import_annotations(updated, [second])
    assert updated.loc[0, "label_status"] == "disputed"
    assert not updated.loc[0, "label_current_verified"]
    assert updated.loc[0, "quality_label_current"] is None
    assert repeat_agreement([first], [second])["status"] == "insufficient_data"


@pytest.fixture
def checkpoint_pipeline(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    source.write_bytes(b"frozen synthetic source")
    source_hash = quality_pipeline.sha256(source)
    row = pd.Series({"sample_id": "s0", "partition": "train", "original_path": str(source),
                     "source_sha256": source_hash, "quality_label_reference": "normal", "reference_uv_path": "legacy.png",
                     "label_generation_id": "g", "label_status": "pending", "region_annotations_json": "[]",
                     "manual_contours_json": "{}"})
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    raw = image.astype(np.float32)
    mask = np.ones((8, 8), dtype=bool)
    recon = {"vertices": np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float),
             "vertices_2d": np.array([[0, 0], [7, 0], [0, 7]], dtype=float),
             "triangles": np.array([[0, 1, 2]]), "uv_coords": np.array([[0, 0], [1, 0], [0, 1]]),
             "angles_deg": np.zeros(3)}
    metadata = {"source_sha256": source_hash, "original_coordinate_definition": "synthetic original pixels",
                "oriented_image_size": [8, 8]}
    provenance = {"triangle_id": np.zeros((8, 8), dtype=int), "observed_fraction": mask.astype(float),
                  "external_occlusion": np.full((8, 8), -1), "measurement_suitable": ~mask,
                  "beauty_method": np.ones((8, 8), dtype=int)}
    warp = {"anisotropy_uv_photo": np.ones(1)}
    aux = {"uv_texture_raw": raw, "provenance": provenance, "visibility_buffers": {},
           "triangle_warp_metrics": warp, "raw_sampling_interpolation": "bilinear"}
    generator = SimpleNamespace(generate=Mock(return_value=(raw, raw, mask, mask.astype(float), aux)))
    monkeypatch.setattr(quality_pipeline, "reconstruct_for_uv", lambda *_: (image, recon, metadata))
    monkeypatch.setattr(quality_pipeline, "HDUVTextureGenerator", lambda *_: generator)
    monkeypatch.setattr(quality_pipeline, "independent_landmarks", Mock(side_effect=RuntimeError("synthetic fixture")))
    monkeypatch.setattr(quality_pipeline, "build_regions", lambda *_: (np.zeros(1), {}, {}))
    monkeypatch.setattr(quality_pipeline, "region_summary", lambda *_: {})
    monkeypatch.setattr(quality_pipeline, "texture_diagnostics", lambda *_: {})
    monkeypatch.setattr(quality_pipeline, "frame_features", lambda *_: {"pose_pitch_deg": 0.0, "source_density_median": 1.5})
    monkeypatch.setattr(quality_pipeline, "save_viewer", lambda path, *_: path.write_text("synthetic viewer"))
    monkeypatch.setattr(quality_pipeline, "save_diagnostic_png", lambda path, *_: path.write_bytes(b"synthetic diagnostic"))

    def export(directory, *_):
        directory = quality_pipeline.Path(directory)
        np.savez_compressed(directory / "sample_raw_float.npz", texture=raw)
        np.savez_compressed(directory / "sample_provenance.npz", **provenance)
        np.savez_compressed(directory / "sample_warp_metrics.npz", **warp)

    monkeypatch.setattr(quality_pipeline, "UVIOExporter", lambda **_: SimpleNamespace(save_all=export))
    config = HDUVConfig(uv_size=8, super_sample=1, collect_provenance=True, device="cpu")
    return SimpleNamespace(row=row, config=config, output=tmp_path / "runs/g", study_dir=tmp_path,
                           source=source, generator=generator)


def test_resume_restores_feature_row_without_reconstruction_or_batch_table(checkpoint_pipeline):
    env = checkpoint_pipeline
    first, values = quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    assert not (env.output / "features.parquet").exists()
    resumed, resumed_values = quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    assert resumed == first
    assert resumed_values == values == resumed["features"]
    assert resumed["processing_status"] == "complete"
    assert env.generator.generate.call_count == 1


@pytest.mark.parametrize("damage", ["missing_features", "truncated_json", "wrong_generation", "wrong_sample_id",
                                    "wrong_feature_identity", "missing_artifact"])
def test_incomplete_or_mismatched_checkpoint_is_recomputed(checkpoint_pipeline, damage):
    env = checkpoint_pipeline
    diagnosis, _ = quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    path = env.output / "samples/s0/diagnosis.json"
    if damage == "truncated_json":
        path.write_text('{"')
    elif damage == "missing_artifact":
        (path.parent / "viewer.html").unlink()
    else:
        if damage == "missing_features":
            del diagnosis["features"]
        elif damage == "wrong_generation":
            diagnosis["generation_id"] = "other"
        elif damage == "wrong_sample_id":
            diagnosis["sample_id"] = "other"
        else:
            diagnosis["features"]["sample_id"] = "other"
        write_json(path, diagnosis)
    resumed, values = quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    assert values["sample_id"] == resumed["sample_id"] == "s0"
    assert env.generator.generate.call_count == 2


def test_resume_rechecks_frozen_source_before_using_cached_features(checkpoint_pipeline):
    env = checkpoint_pipeline
    quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    env.source.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="source hash differs"):
        quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    assert env.generator.generate.call_count == 1


def test_annotation_changes_invalidate_same_generation_checkpoint(checkpoint_pipeline):
    env = checkpoint_pipeline
    first, _ = quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    env.row.region_annotations_json = json.dumps([{"external_occlusion": 0, "uv_polygon": [[0, 0], [7, 0], [0, 7]]}])
    second, _ = quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    assert first["analysis_inputs_sha256"] != second["analysis_inputs_sha256"]
    assert env.generator.generate.call_count == 2


def test_missing_source_checkpoint_does_not_hide_a_restored_source(checkpoint_pipeline):
    env = checkpoint_pipeline
    original = env.source.read_bytes()
    env.source.unlink()
    missing, values = quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    assert values is None and missing["processing_status"] == "missing_source"
    env.source.write_bytes(original)
    restored, values = quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    assert values is not None and restored["processing_status"] == "complete"
    assert env.generator.generate.call_count == 1


def test_feature_failure_never_commits_a_completed_checkpoint(checkpoint_pipeline, monkeypatch):
    env = checkpoint_pipeline
    monkeypatch.setattr(quality_pipeline, "frame_features", Mock(side_effect=RuntimeError("feature failure")))
    with pytest.raises(RuntimeError, match="feature failure"):
        quality_pipeline.analyze_sample(env.row, env.config, "g", env.output, env.study_dir, None)
    assert not (env.output / "samples/s0/diagnosis.json").exists()


def test_interrupted_batch_recovers_all_rows_and_counts_only_selected_samples(checkpoint_pipeline, monkeypatch):
    from morphing.backend import mp_worker
    env = checkpoint_pipeline
    second = env.row.copy()
    second.sample_id, second.partition = "s1", "validation"
    pd.DataFrame([env.row, second]).to_parquet(env.study_dir / "manifest.parquet", index=False)
    monkeypatch.setattr(quality_pipeline, "generation_lock", lambda *_: ("g", {}))
    client = SimpleNamespace(close=Mock())
    monkeypatch.setattr(mp_worker, "LandmarkerClient", lambda: client)
    args = SimpleNamespace(study_dir=env.study_dir, uv_size=8, super_sample=1,
                           partitions="train,validation", limit=0, stability_samples=0)
    analyze_sample = quality_pipeline.analyze_sample

    def interrupt(row, *rest):
        if row.sample_id == "s1":
            raise KeyboardInterrupt
        return analyze_sample(row, *rest)

    monkeypatch.setattr(quality_pipeline, "analyze_sample", interrupt)
    with pytest.raises(KeyboardInterrupt):
        quality_pipeline.analyze(args)
    assert not (env.output / "features.parquet").exists()
    assert (env.output / "samples/s0/diagnosis.json").is_file()
    monkeypatch.setattr(quality_pipeline, "analyze_sample", analyze_sample)
    quality_pipeline.analyze(args)
    table = pd.read_parquet(env.output / "features.parquet")
    assert set(table.sample_id) == {"s0", "s1"}
    assert not table.sample_id.duplicated().any()
    assert env.generator.generate.call_count == 2
    quality_pipeline.analyze(args)
    pd.testing.assert_frame_equal(table, pd.read_parquet(env.output / "features.parquet"))
    assert env.generator.generate.call_count == 2
    args.limit = 1
    quality_pipeline.analyze(args)
    summary = json.loads((env.output / "summary.json").read_text())
    assert summary["requested_samples"] == summary["completed_source_analyses"] == 1
    assert summary["source_or_processing_failures"] == 0
    assert len(pd.read_parquet(env.output / "features.parquet")) == 2
    args.limit = 0
    env.source.unlink()
    quality_pipeline.analyze(args)
    summary = json.loads((env.output / "summary.json").read_text())
    assert summary["completed_source_analyses"] == 0
    assert summary["missing_source_photographs"] == 2
    assert summary["processing_errors"] == 0
    assert pd.read_parquet(env.output / "features.parquet").empty


def test_closed_test_remains_locked_before_any_sample_is_processed(checkpoint_pipeline, monkeypatch):
    env = checkpoint_pipeline
    pd.DataFrame([env.row]).to_parquet(env.study_dir / "manifest.parquet", index=False)
    monkeypatch.setattr(quality_pipeline, "generation_lock", lambda *_: ("g", {}))
    args = SimpleNamespace(study_dir=env.study_dir, uv_size=8, super_sample=1, partitions="test", limit=0, stability_samples=0)
    with pytest.raises(ValueError, match="closed test cannot be inspected"):
        quality_pipeline.analyze(args)
    env.generator.generate.assert_not_called()
    assert not (env.study_dir / "test_release_lock.json").exists()


def test_json_checkpoint_replace_failure_keeps_previous_record(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / "checkpoint.json"
    write_json(path, {"complete": True})
    monkeypatch.setattr(Path, "replace", Mock(side_effect=OSError("interrupted replace")))
    with pytest.raises(OSError, match="interrupted replace"):
        write_json(path, {"complete": False})
    assert json.loads(path.read_text()) == {"complete": True}


def test_visibility_mask_keeps_intrinsic_geometry_and_excludes_hidden_photo_statistics():
    metrics = {"anisotropy_3d_uv": np.array([1.0, 2.0, 3.0]),
               "anisotropy_uv_photo": np.array([1.0, 2.0, 999.0]), "density_uv_photo": np.array([1.0, 2.0, 999.0]),
               "area_surface": np.ones(3), "valid_uv_photo": np.ones(3, dtype=bool)}
    visible = np.array([True, True, False])
    masked = visible_photo_metrics(metrics, visible)
    np.testing.assert_equal(masked["anisotropy_3d_uv"], metrics["anisotropy_3d_uv"])
    assert np.isnan(masked["anisotropy_uv_photo"][2])
    assert metrics["anisotropy_uv_photo"][2] == 999
    rows = region_summary({**metrics, "triangle_visible": visible}, np.zeros(3, dtype=int), ["region"], np.zeros((3, 3), dtype=int))
    assert rows["region"]["anisotropy_uv_photo"]["p95"] == 2
    assert rows["region"]["anisotropy_3d_uv"]["p95"] == 3
    assert rows["region"]["invalid_surface_fraction"] == 0
    with pytest.raises(ValueError, match="visibility must match"):
        visible_photo_metrics(metrics, np.ones(2, dtype=bool))


def test_normal_reference_never_scores_invisible_photo_triangles():
    records, differences = synthetic_reference()
    reference = fit_reference(records, differences, "g")
    metrics = {**records[0]["metrics"], "triangle_visible": np.array([True, False, True])}
    score = score_reference(reference, metrics, [0, 10, np.log(500)])
    assert np.isfinite(score["deviation"]["anisotropy_3d_uv"]).all()
    for key in ("anisotropy_uv_photo", "density_uv_photo"):
        assert np.isnan(score["deviation"][key][1])
        assert np.isfinite(score["deviation"][key][[0, 2]]).all()


@pytest.mark.parametrize("with_visibility", [True, False])
def test_repeat_photo_floors_use_only_common_visible_triangles(tmp_path, monkeypatch, with_visibility):
    from uv_module import hd_uv_generator, stability
    recon = {"vertices_object": np.zeros((5, 3)), "vertices_2d": np.zeros((5, 2)), "uv_coords": np.zeros((5, 2)),
             "triangles": np.array([[0, 1, 2], [0, 2, 3], [0, 3, 4]])}
    base = {key: np.array([1.0, 2.0, 3.0]) for key in METRICS}
    base["area_surface"] = np.ones(3)
    variants = [{**{key: base[key] * 1.1 for key in METRICS}, "area_surface": np.ones(3)} for _ in range(3)]
    monkeypatch.setattr(stability, "triangle_warp_metrics", Mock(side_effect=[base, *variants]))
    monkeypatch.setattr(stability, "reconstruct_for_uv", lambda *_: (None, recon.copy(), {}))
    raw = np.zeros((8, 8, 3), dtype=np.float32)
    observed = np.ones((8, 8), dtype=bool)
    generator = SimpleNamespace(generate=lambda *_: (None, None, observed, None,
                                {"uv_texture_raw": raw, "tri_visibility": np.array([1.0, 0.0, 1.0])}))
    monkeypatch.setattr(hd_uv_generator, "HDUVTextureGenerator", lambda *_: generator)
    reports, differences, metrics = stability.geometry_repeats(np.zeros((100, 100, 3), dtype=np.uint8), recon, 8,
        tmp_path / "repeats", tmp_path / "cache", generator_config=object() if with_visibility else None,
        base_raw=raw, base_observed=observed, base_triangle_visible=np.array([True, True, False]) if with_visibility else None)
    assert len(reports) == len(metrics) == 3
    for delta in differences["anisotropy_3d_uv"]:
        assert np.isfinite(delta).all()
    for key in ("anisotropy_uv_photo", "density_uv_photo"):
        for delta in differences[key]:
            if with_visibility:
                assert delta[0] == pytest.approx(np.log(1.1))
                assert np.isnan(delta[[1, 2]]).all()
            else:
                assert np.isnan(delta).all()
        if with_visibility:
            for preset in stability.PRESETS:
                with np.load(tmp_path / "repeats" / (preset + "_raw_uv.npz")) as stored:
                    assert np.isnan(stored[key][~stored["triangle_visible"]]).all()
