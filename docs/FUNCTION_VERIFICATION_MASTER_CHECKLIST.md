# Function Verification Master Checklist

> Permanent control document for gradual strict closure of every data-bearing production function. The canonical full records are in `docs/function_verification_master_checklist.json`.

## Status workflow and strict closure policy

`NOT_REVIEWED → IN_PROGRESS → FAILED | BLOCKED_EXTERNAL | CLOSED_BASIC → CLOSED_STRONG`.

`CLOSED_STRONG` requires, for the individual function: direct positive oracle; negative/fail-closed test; boundary/property/metamorphic test; downstream consumer/handoff assertion; schema/finite/null semantics; deterministic evidence; and a committed/present regression test. **A green aggregate suite alone does not close a function.** Never promote without recorded evidence in JSON.

<!-- BEGIN GENERATED: function-checklist -->
## Dashboard

| Metric | Count |
|---|---:|
| Total data-bearing | 567 |
| CLOSED_STRONG | 17 |
| CLOSED_BASIC | 203 |
| IN_PROGRESS | 0 |
| FAILED | 0 |
| BLOCKED_EXTERNAL | 2 |
| NOT_REVIEWED | 345 |
| Critical remaining | 150 |
| High remaining | 89 |

**Recommended next batch:** `PKG-001`.

## Executable packages

Run in listed dependency order. Commands are templates: replace `{targeted_test_paths}` with tests created/mapped for that package.

### PKG-001 — Input, provenance, dates, duplicates

- **Status:** `CLOSED_STRONG`; **functions:** 17; **prerequisites:** none
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [x] | `app6/archive_adapter.py::group_by_person_pose` | high | CLOSED_STRONG | 0 |
| [x] | `app6/archive_adapter.py::load_archive_records` | medium | CLOSED_STRONG | 0 |
| [x] | `app6/archive_adapter.py::safe_extract_archive` | medium | CLOSED_STRONG | 0 |
| [x] | `app6/archive_adapter.py::with_synthetic_dates` | medium | CLOSED_STRONG | 0 |
| [x] | `app6/stage1/input_provenance.py::_parse_exif_date` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage1/input_provenance.py::build_date_provenance` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage1/input_provenance.py::decode_oriented` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage1/provenance_ledger.py::hamming_distance` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage1/provenance_ledger.py::load_provenance_sidecar` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage1/provenance_ledger.py::perceptual_dhash` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage2/date_provenance.py::_delta_days` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage2/date_provenance.py::parse_filename_date` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage2/date_provenance.py::resolve_date` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage2/same_day_gate.py::_robust_scale` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage2/same_day_gate.py::check_same_day_conflict` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage2/same_day_gate.py::same_day_summary` | high | CLOSED_STRONG | 0 |
| [x] | `app6/stage2/temporal_axis.py::temporal_status` | medium | CLOSED_STRONG | 0 |

### PKG-002 — Image decoding and orientation

- **Status:** `NOT_REVIEWED`; **functions:** 21; **prerequisites:** PKG-001
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/photo_fields.py::_bool` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/photo_fields.py::_num` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/photo_fields.py::fields_from_info` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/photo_fields.py::load_info` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/photo_fields.py::merge_photo_fields` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/photo_fields.py::scan_stage1_records` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage1/authenticity/extract.py::_authenticity_status` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/extract.py::_load_face_mask_rgba` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/extract.py::_load_json` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/extract.py::_panel_score` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/authenticity/extract.py::_quality_score` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/authenticity/extract.py::build_texture_package` | high | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/authenticity/extract.py::extract_quality_metrics` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/utils.py::atomic_json` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/utils.py::digest_file` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/utils.py::digest_json` | medium | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/utils.py::digest_paths` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/utils.py::json_ready` | medium | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/utils.py::runtime_versions` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/utils.py::runtime_versions.version` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/utils.py::write_csv` | medium | NOT_REVIEWED | 6 |

### PKG-003 — Stage1 geometry, pose, naming

- **Status:** `NOT_REVIEWED`; **functions:** 14; **prerequisites:** PKG-002
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage1/geometry.py::classify_pose` | high | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/geometry.py::compute_chronology_alignment` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/geometry.py::full_pose_correction_matrix` | high | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/geometry.py::nearest_canonical_yaw` | medium | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/geometry.py::normalize_mesh` | high | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/geometry.py::normalize_mesh_landmark_anchored` | high | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/geometry.py::pack_mask` | medium | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/geometry.py::reprojection_stats` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/geometry.py::row_rotation_matrix` | medium | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/geometry.py::to_original_image` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/geometry.py::unpack_mask` | medium | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/naming.py::make_nonchronological_photo_name` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/naming.py::make_photo_id` | medium | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/naming.py::parse_photo_name` | medium | CLOSED_BASIC | 4 |

### PKG-004 — Reconstruction, assets, masks, visibility

- **Status:** `NOT_REVIEWED`; **functions:** 22; **prerequisites:** PKG-003
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage1/assets.py::_bbox` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/assets.py::_letterbox` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/assets.py::_write_obj` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/assets.py::save_face_mask` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/assets.py::save_image_assets` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/assets.py::save_semantic_channels` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/assets.py::save_uv_and_mesh` | high | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/assets.py::technical_quality` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/masks.py::build_mask_bundle` | medium | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionBundle.landmark_arrays` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionEngine.__init__` | critical | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionEngine._check_assets` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionEngine._np` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionEngine._resolve_device` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionEngine.cleanup` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionEngine.process` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionEngine.process.capture_alpha` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/reconstruction.py::ReconstructionEngine.process.renderer_forward` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas.py::_boundary_safe_mask` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas.py::_pose_weight` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas.py::_render_overlay` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas.py::_tri_px` | medium | NOT_REVIEWED | 6 |

### PKG-005 — Reconstruction, assets, masks, visibility

- **Status:** `NOT_REVIEWED`; **functions:** 22; **prerequisites:** PKG-004
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage1/skin_zone_atlas.py::_uv_to_original` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas.py::_zone_colors` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas.py::build_atlas_json` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas.py::build_pose_policy` | high | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas.py::build_triangle_zone_map` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/skin_zone_atlas.py::generate_canonical_atlas` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas.py::load_canonical_atlas` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas.py::project_atlas_to_photo` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas.py::render_atlas_png` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas.py::write_pose_policy_csv` | high | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas.py::zone_names` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::_boundary_safe_mask` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::_uv_to_original` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::_zone_colors` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::build_primary_triangle_zone` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::export_contract` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::load_canonical_atlas` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::points_in_polygon` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::project_atlas_to_photo` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::triangle_centroids_uv` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::validate_definitions` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/skin_zone_atlas_final.py::zone_role_for_pose` | high | CLOSED_BASIC | 4 |

### PKG-006 — Stage1 storage, schema, manifest

- **Status:** `NOT_REVIEWED`; **functions:** 23; **prerequisites:** PKG-005
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/run_calibration_re_extract.py::run_stage1` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/run_stage1.py::build_parser` | critical | CLOSED_BASIC | 3 |
| [ ] | `app6/run_stage1.py::main` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/authenticity/albedo_analysis.py::_fallback` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/albedo_analysis.py::_rgb_to_hsv` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/albedo_analysis.py::albedo_spectral_analysis` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/authenticity/fft_analysis.py::_fallback` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/fft_analysis.py::fft_regularity_analysis` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/lbp_analysis.py::_fallback` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/lbp_analysis.py::_manual_lbp` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/lbp_analysis.py::lbp_complexity_analysis` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/authenticity/v12_features.py::_entropy` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/v12_features.py::_load_recipe` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/v12_features.py::_pct` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/v12_features.py::_std` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/v12_features.py::derive_v12_metrics` | high | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/authenticity/v12_features.py::extract_v12_bases` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/authenticity/v12_features.py::extract_v12_bases.roi` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/authenticity/v12_features.py::extract_v12_panel` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/config.py::Stage1Config.__post_init__` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/config.py::Stage1Config.extraction_payload` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/config.py::Stage1Config.public_dict` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/engine.py::Stage1Engine.__init__` | critical | CLOSED_BASIC | 3 |

### PKG-007 — Stage1 storage, schema, manifest

- **Status:** `NOT_REVIEWED`; **functions:** 22; **prerequisites:** PKG-006
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage1/engine.py::Stage1Engine._index_row` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/engine.py::Stage1Engine._one` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/engine.py::Stage1Engine._one._compute_landmark_confidence` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/engine.py::Stage1Engine._photo_name` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/engine.py::Stage1Engine._relative` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/engine.py::Stage1Engine.run` | critical | CLOSED_BASIC | 3 |
| [ ] | `app6/stage1/engine.py::_landmark_rows` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/engine.py::_landmark_rows_2d` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/engine.py::_utc` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/engine.py::discover_input_photos` | critical | CLOSED_BASIC | 2 |
| [ ] | `app6/stage1/status_logger.py::_update_audit_status` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/status_logger.py::close_function` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/status_logger.py::log_blocker` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/status_logger.py::log_status` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/status_logger.py::print_status_summary` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/storage.py::atomic_photo_directory` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/storage.py::clean_incomplete` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/storage.py::write_failure` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/validator.py::_csv_check` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage1/validator.py::_resolve_topology` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage1/validator.py::is_resumable` | medium | NOT_REVIEWED | 5 |
| [ ] | `app6/stage1/validator.py::validate_photo` | medium | NOT_REVIEWED | 5 |

### PKG-008 — Calibration loading and balance

- **Status:** `NOT_REVIEWED`; **functions:** 19; **prerequisites:** PKG-007
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/calibration.py::_bucket_confidence` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/calibration.py::find_matching_calibration_frames` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/calibration.py::find_matching_calibration_frames._distance` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/calibration.py::load_calibration_health` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/noise_calibration.py::angle_delta_for` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/noise_calibration.py::apply_noise_subtraction` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/noise_calibration.py::build_noise_index` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/noise_calibration.py::noise_coverage_report` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/noise_calibration.py::resolve_tolerance` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::_calibration_records` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_calibration_root` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::calibration_health` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::calibration_match` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::calibration_noise_model` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::calibration_subtract_noise` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/build_calibration_index.py::main` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/calibration_index.py::_identity` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/calibration_index.py::_relative` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/calibration_index.py::build_calibration_index` | critical | NOT_REVIEWED | 7 |

### PKG-009 — Calibration loading and balance

- **Status:** `NOT_REVIEWED`; **functions:** 19; **prerequisites:** PKG-008
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/run_calibration.py::main` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/run_calibration_re_extract.py::assign_synthetic_dates` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/run_calibration_re_extract.py::create_temp_symlinks` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/run_calibration_re_extract.py::load_index` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/run_calibration_re_extract.py::main` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/run_calibration_re_extract.py::reorganize_output` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/run_preflight.py::audit_calibration_index` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/angle_noise.py::angle_delta` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/angle_noise.py::build_calibration_pair_index` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/angle_noise.py::find_matching_calibration_pair` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/angle_noise.py::subtract_angle_noise` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel.__init__` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel._build_references` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel._collect_reference_values` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel._nearest` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel._nearest.score` | critical | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel._pose_distance` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel.consistency_check` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel.has_stratified_references` | critical | NOT_REVIEWED | 7 |

### PKG-010 — Calibration loading and balance

- **Status:** `NOT_REVIEWED`; **functions:** 19; **prerequisites:** PKG-009
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/calibration.py::CalibrationModel.matched_null` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel.reference` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel.references_excluding_dataset` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/calibration.py::CalibrationModel.reuse_report` | critical | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/calibration_sensitivity.py::leave_one_dataset_sensitivity` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/loaders.py::calibration_bin_coverage` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/loaders.py::load_calibration` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/loaders.py::load_calibration_from_sidecar` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/loaders.py::load_legacy_calibration_archive` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/mesh_calibration.py::MeshNoiseModel.__init__` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/mesh_calibration.py::MeshNoiseModel._build` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/mesh_calibration.py::MeshNoiseModel.score` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/mesh_calibration.py::MeshNoiseModel.to_json` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/mesh_calibration.py::_mesh_metrics` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/mesh_calibration.py::_pose_distance` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/tools/calibration_artifact_manifest.py::build` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/tools/calibration_artifact_manifest.py::digest` | critical | CLOSED_BASIC | 5 |
| [ ] | `app6/tools/calibration_artifact_manifest.py::main` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/tools/calibration_artifact_manifest.py::verify` | critical | CLOSED_BASIC | 4 |

### PKG-011 — Pair planning and anchors + Coordinate alignment and motion

- **Status:** `NOT_REVIEWED`; **functions:** 16; **prerequisites:** PKG-010
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/anchor_policy.py::per_bin_anchor_mask` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/anchor_policy.py::stable_anchor_indices` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/anchor_policy.py::stable_anchor_mask` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/hard_negative.py::evaluate` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/pair_planner.py::plan_pairs` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/pair_planner.py::plan_pairs.add` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/pair_row_patch.py::enrich_pair_row` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/landmark_policy.py::normalized_weights` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/landmark_policy.py::row_all_nan` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/landmark_policy.py::sanitize_utility` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/landmark_policy.py::stable_subset` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/landmark_policy.py::subset_for_bin` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/motion.py::PointNoiseModel.__init__` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/motion.py::PointNoiseModel._build` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/motion.py::PointNoiseModel._coherence` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/motion.py::PointNoiseModel._pose_distance` | high | NOT_REVIEWED | 7 |

### PKG-012 — Coordinate alignment and motion

- **Status:** `NOT_REVIEWED`; **functions:** 16; **prerequisites:** PKG-011
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/motion.py::PointNoiseModel.landmark_stability_score` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/motion.py::PointNoiseModel.score` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/motion.py::aligned_point_motion` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/motion.py::pose_motion_support` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/pose_leakage.py::_finite_pairs` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/pose_leakage.py::pose_leakage_diagnostic` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/pose_policy.py::_atlas_dir` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/pose_policy.py::applicable_zones` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/pose_policy.py::assert_canonical_yaw` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/pose_policy.py::load_pose_policy` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/pose_policy.py::policy_summary` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/pose_policy.py::profile_sub_bin` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/pose_policy.py::yaw_for_bin` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/pose_policy.py::zone_applicability` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/space_selection.py::assert_analysis_space` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/space_selection.py::space_manifest` | medium | CLOSED_BASIC | 5 |

### PKG-013 — Visibility and zones

- **Status:** `NOT_REVIEWED`; **functions:** 16; **prerequisites:** PKG-012
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/server.py::get_photo_skin_zones` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/skin_zones.py::_float_or_none` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/skin_zones.py::_load_atlas` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/skin_zones.py::_read_json` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/skin_zones.py::load_skin_zone_report` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/skin_zones.py::zone_catalog` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/generate_mesh_zones.py::generate_zones` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/generate_mesh_zones.py::main` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/primary_zones.py::_load_landmark_vertex_indices` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/primary_zones.py::_vertex_to_zone` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/primary_zones.py::build_anatomical_landmark_zone_map` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/primary_zones.py::expression_zone_policy` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/primary_zones.py::pair_expression_active` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/primary_zones.py::primary_zone_aggregate` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/visibility_gate.py::bin_visibility_prior` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/visibility_gate.py::pair_visibility` | high | CLOSED_BASIC | 4 |

### PKG-014 — Expression and quality gates

- **Status:** `NOT_REVIEWED`; **functions:** 16; **prerequisites:** PKG-013
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/analysis_policy.py::_atlas_dir` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/analysis_policy.py::load_pose_gate` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/analysis_policy.py::pose_gap` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/expression_pair_gate.py::expression_gate` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/expression_qc.py::_interocular` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/expression_qc.py::detect_expression` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/expression_qc.py::exclude_mimic_zones` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/expression_qc.py::expression_magnitude` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/quality_gate.py::compensate_quality_disparity` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/quality_gate.py::quality_gate_summary` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/quality_gate.py::resolution_quality_gate` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/quality_gate.py::resolution_ratio` | critical | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/quality_integration.py::load_quality_zone_summary` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/quality_integration.py::pair_quality_zone_overlap` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/quality_stratification.py::_stratum` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/quality_stratification.py::quality_gate` | critical | CLOSED_BASIC | 4 |

### PKG-015 — Descriptors, mesh, texture

- **Status:** `NOT_REVIEWED`; **functions:** 19; **prerequisites:** PKG-014
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/descriptors.py::DescriptorNoiseModel._build` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/descriptors.py::DescriptorNoiseModel._pd` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/descriptors.py::DescriptorNoiseModel.score` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/descriptors.py::_neighbors` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/descriptors.py::_one` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/descriptors.py::descriptor_pose_compatible` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/descriptors.py::local_pair_descriptors` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/mesh_dense.py::_load_mesh` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/mesh_dense.py::_normalize` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/mesh_dense.py::_shape_descriptor` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/mesh_dense.py::_subsample` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/mesh_dense.py::_zone_labels` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/mesh_dense.py::dense_mesh_pair` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/mesh_dense.py::load_anatomical_zones` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_texture_summary` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/texture_image.py::_entropy` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_image.py::_erode_roi` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_image.py::_frequency_ratio` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_image.py::_gabor_profile` | high | NOT_REVIEWED | 7 |

### PKG-016 — Descriptors, mesh, texture

- **Status:** `NOT_REVIEWED`; **functions:** 19; **prerequisites:** PKG-015
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/texture_image.py::_glcm_stats` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/texture_image.py::_image_path` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/texture_image.py::_lbp_histogram` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/texture_image.py::_load_face_mask_texture` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_image.py::_load_texture` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/texture_image.py::_patch_profile` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/texture_image.py::_stats` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/texture_image.py::_unpack_mask` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_image.py::pose_normalize_texture` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_image.py::texture_pair_deltas` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/texture_pair.py::summarize_texture_pairs` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/texture_structure.py::_patch` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_structure.py::_ridge_probability` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_structure.py::_skeleton` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_structure.py::_skeleton_metrics` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/texture_structure.py::_ssim` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/texture_structure.py::compare_zone_structure` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/texture_structure.py::register_patches` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/uv_comparison.py::compare_packages` | medium | CLOSED_BASIC | 5 |

### PKG-017 — Statistics, ESS, confidence intervals

- **Status:** `NOT_REVIEWED`; **functions:** 15; **prerequisites:** PKG-016
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/core.py::Record.__post_init__` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/core.py::_load_per_bin_artifacts` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/core.py::_rigid_align` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/core.py::_stats` | critical | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/core.py::build_coordinate_zone_map` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/core.py::calibrated_score` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/core.py::compare_landmarks` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/core.py::compare_landmarks._alpha_l2` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/core.py::measured_alignment_quality` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/core.py::robust_reference` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/core.py::robust_rigid_align` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/core.py::zone_weighted_score` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/metric_registry.py::_usable` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/metric_registry.py::build_metric_catalog` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/metric_registry.py::evidence_metric_channel` | critical | CLOSED_BASIC | 4 |

### PKG-018 — Statistics, ESS, confidence intervals

- **Status:** `NOT_REVIEWED`; **functions:** 15; **prerequisites:** PKG-017
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/metric_registry.py::metric_channel` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/metric_registry.py::validate_registry` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/robustness.py::balanced_person_threshold` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/robustness.py::balanced_reference` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/robustness.py::classify_sequence` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/robustness.py::cluster_bootstrap_ci` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/robustness.py::effective_sample_size` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/robustness.py::ensure_same_pose` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/robustness.py::kabsch_rmse` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/robustness.py::noise_adjusted_threshold` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/robustness.py::normalize_points` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/robustness.py::robust_pair_distance` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/robustness.py::robust_threshold` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/robustness.py::validate_landmarks` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/robustness.py::validate_serialized_record` | medium | NOT_REVIEWED | 6 |

### PKG-019 — FDR and multiple testing + Chronology, return, change

- **Status:** `NOT_REVIEWED`; **functions:** 23; **prerequisites:** PKG-018
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/fdr_control.py::apply_fdr` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/fdr_control.py::benjamini_hochberg` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/multiple_testing.py::_bh_qvalues` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/multiple_testing.py::_p_from_p95_z` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/multiple_testing.py::_p_from_z` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/multiple_testing.py::apply_pair_fdr` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/multiple_testing.py::apply_zone_fdr` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/alpha_chronology.py::apply_alpha_chronology` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/baseline_return.py::_load_vectors` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/baseline_return.py::_reversal_stats` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/baseline_return.py::apply_baseline_return` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/chronology.py::_days` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/chronology.py::_mark_chronology_excluded` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/chronology.py::_quality_exclusion_reason` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/chronology.py::_robust` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/chronology.py::apply_biological_rate_flags` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/chronology.py::apply_chronology_rate_flags` | critical | CLOSED_BASIC | 3 |
| [ ] | `app6/stage2/chronology.py::apply_cumulative_drift_flags` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/irreversible_return.py::_date_bounds` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/irreversible_return.py::_parse_date` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/irreversible_return.py::_similarity` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/irreversible_return.py::detect_irreversible_return` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/irreversible_return.py::summarize_returns` | medium | NOT_REVIEWED | 7 |

### PKG-020 — Evidence, candidates, corroboration

- **Status:** `NOT_REVIEWED`; **functions:** 21; **prerequisites:** PKG-019
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/corroboration.py::_date` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/corroboration.py::aggregate_events` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/corroboration.py::apply_cross_bin_corroboration` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/evidence.py::EvidencePacket.to_dict` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/evidence.py::alternative_reasons` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/evidence.py::evidence_state` | critical | CLOSED_BASIC | 3 |
| [ ] | `app6/stage2/evidence.py::is_reportable_change` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/evidence.py::packet_from_pair` | critical | CLOSED_BASIC | 3 |
| [ ] | `app6/stage2/leads.py::_date` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/leads.py::_load` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/leads.py::load_leads` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/leads.py::load_leads.add` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/leads.py::pair_leads` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/private_hypothesis.py::PrivateHypothesisEngine.run` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/private_hypothesis.py::_candidate_keys` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/private_hypothesis.py::_candidate_keys.walk` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/private_hypothesis.py::_digest` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/private_hypothesis.py::_extract_records` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/private_hypothesis.py::_read_csv` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/private_hypothesis.py::_retest_record` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/private_hypothesis.py::_utc` | medium | NOT_REVIEWED | 7 |

### PKG-021 — Stage2 export and manifest

- **Status:** `NOT_REVIEWED`; **functions:** 25; **prerequisites:** PKG-020
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/export.py::stable_fieldnames` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/export.py::validate_csv_headers` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/postprocess_reports.py::_num` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_artifact_index` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_degraded_modules` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_gate_report` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_manual_review_queue` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_mesh_shape_summary` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_public_safety` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_stage3_input_summary` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/postprocess_reports.py::_write_status_summary` | high | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/postprocess_reports.py::write_postprocess_reports` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/run_manifest.py::_sha256` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/run_manifest.py::artifact_hashes` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/run_manifest.py::build_manifest` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/snapshot_canonical.py::_near` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/snapshot_canonical.py::canonical_json` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/snapshot_canonical.py::canonical_snapshot` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/snapshot_canonical.py::compare_snapshots` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/snapshot_canonical.py::compare_snapshots._walk` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/snapshot_canonical.py::read_snapshot` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/snapshot_canonical.py::snapshot_category` | medium | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/snapshot_canonical.py::snapshot_file_roundtrip_is_deterministic` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/snapshot_canonical.py::write_snapshot` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/technical_summary.py::build_technical_summary` | medium | CLOSED_BASIC | 4 |

### PKG-022 — Stage2B + Stage3, reporting, public safety

- **Status:** `NOT_REVIEWED`; **functions:** 13; **prerequisites:** PKG-021
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/run_stage2b.py::build_parser` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/run_stage2b.py::main` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2b/engine.py::Stage2BConfig.__post_init__` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2b/engine.py::Stage2BConfig.payload` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2b/engine.py::Stage2BEngine.run` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2b/engine.py::utc` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/api/report.py::_read_report` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/report.py::_read_validation` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/report.py::_section_size` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/report.py::load_report_section` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/report.py::load_report_summary` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/report.py::report_available` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/server.py::_require_stage3` | critical | NOT_REVIEWED | 7 |

### PKG-023 — Stage3, reporting, public safety

- **Status:** `NOT_REVIEWED`; **functions:** 13; **prerequisites:** PKG-022
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/server.py::_stage3_root` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::system_health` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/system_health.py::_gpu_status` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/system_health.py::_optional_dependency_status` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/system_health.py::_resource_usage` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/system_health.py::build_system_health` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/run_stage3.py::main` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage3/engine.py::Stage3Config.__post_init__` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage3/engine.py::Stage3Engine._html` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage3/engine.py::Stage3Engine.run` | critical | CLOSED_BASIC | 3 |
| [ ] | `app6/stage3/engine.py::num` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage3/engine.py::public_pair_projection` | critical | NOT_REVIEWED | 5 |
| [ ] | `app6/stage3/engine.py::rows` | critical | CLOSED_BASIC | 2 |

### PKG-024 — API loaders, settings, jobs

- **Status:** `NOT_REVIEWED`; **functions:** 15; **prerequisites:** PKG-023
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/bfm_topology.py::BFMModel.compute_shape` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/bfm_topology.py::_convert_npy_to_safe_npz` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/bfm_topology.py::_extract_face_model_npy` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/bfm_topology.py::_load_raw_arrays` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/bfm_topology.py::is_bfm_available` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/bfm_topology.py::load_bfm_model` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::Job.to_dict` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::JobManager.__init__` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/jobs.py::JobManager.cancel` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/jobs.py::JobManager.get` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::JobManager.list_jobs` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::JobManager.submit` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::JobManager.submit._run` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/jobs.py::_check_stage1_dependencies` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::_utc` | high | NOT_REVIEWED | 7 |

### PKG-025 — API loaders, settings, jobs

- **Status:** `NOT_REVIEWED`; **functions:** 14; **prerequisites:** PKG-024
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/jobs.py::make_extract_runner` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::make_extract_runner._extract_runner` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::make_recompute_metrics_runner` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/jobs.py::make_recompute_metrics_runner._recompute_runner` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/key_catalog.py::categorize_manifest` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/key_catalog.py::categorize_pair_columns` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/key_catalog.py::categorize_stage1_info` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/key_catalog.py::category_for` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/key_catalog.py::coerce` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/settings.py::SettingsPayload.guard` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/settings.py::_deep_merge` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/settings.py::_settings_path` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/settings.py::load_settings` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/settings.py::save_settings` | high | NOT_REVIEWED | 7 |

### PKG-026 — API compare, review, timeline

- **Status:** `NOT_REVIEWED`; **functions:** 25; **prerequisites:** PKG-025
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/compare.py::compare_records` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/compare.py::full_mesh_compare` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/pair_metrics.py::_count_leaves` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/pair_metrics.py::_read_pairs` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/pair_metrics.py::find_pair_row` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/pair_metrics.py::list_stage2_artifacts` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/pair_metrics.py::load_pair_metrics` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/pair_metrics.py::load_run_summary` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/pair_metrics.py::load_stage1_info` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/pair_metrics.py::load_stage2_artifact` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/research_timeline.py::_date_to_ms` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/research_timeline.py::_num` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/research_timeline.py::build_research_timeline` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/research_timeline.py::build_research_timeline._ensure_photo` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/research_timeline.py::build_research_timeline._optional_num` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/review.py::append_review` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::get_pair_metrics` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/stage1_timeline.py::_date_to_ms` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/stage1_timeline.py::_float` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/api/stage1_timeline.py::build_stage1_inventory` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/ui_fields.py::bone_score` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/ui_fields.py::era_for` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/ui_fields.py::normalized_t` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/ui_fields.py::principal_coords` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/api/ui_fields.py::validate_ui_row` | high | CLOSED_BASIC | 4 |

### PKG-027 — Cross-stage handoffs, determinism, resume, security

- **Status:** `NOT_REVIEWED`; **functions:** 22; **prerequisites:** PKG-026
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/__init__.py::__getattr__` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_cached_main_records` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_main_record` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::_main_records` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_manifest_sort_key` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_path_with_file` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_require_removable_output` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::_require_stage1` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_require_stage2` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_safe_record_file` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_stage1_root` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::_stage2_manifest` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_stage2_root` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::_storage_root` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::_upload_image_decodes` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_upload_signature_matches` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::_uploads_root` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::cancel_job` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::clear_data` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::compare_pair` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::compare_pair_full_mesh` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::compare_with_upload` | critical | NOT_REVIEWED | 7 |

### PKG-028 — Cross-stage handoffs, determinism, resume, security

- **Status:** `NOT_REVIEWED`; **functions:** 22; **prerequisites:** PKG-027
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/server.py::create_review` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::delete_photo` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_job` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_photo` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_photo_artifact` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_photo_full_mesh` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_photo_image` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_photo_info_keys` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_photo_landmarks` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_report_section` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_report_section_artifact` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_report_summary` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_run_artifact` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_run_key_alias` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_run_summary` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_settings` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_timeline` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::get_ui_artifact` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::health` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/api/server.py::list_jobs` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::list_photos` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::put_settings` | critical | NOT_REVIEWED | 7 |

### PKG-029 — Cross-stage handoffs, determinism, resume, security

- **Status:** `NOT_REVIEWED`; **functions:** 22; **prerequisites:** PKG-028
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/api/server.py::reset_settings` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::submit_job` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::unhandled_exception_handler` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::upload_photo` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/api/server.py::zones_catalog` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/run_preflight.py::main` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/run_scenario_planner.py::build_plan` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/run_scenario_planner.py::main` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/run_stage2.py::build_parser` | critical | CLOSED_BASIC | 5 |
| [ ] | `app6/run_stage2.py::main` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/schemas/__init__.py::schema_path` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/scripts/fetch_external_assets.py::main` | medium | BLOCKED_EXTERNAL | 7 |
| [ ] | `app6/scripts/fetch_external_assets.py::sha` | medium | BLOCKED_EXTERNAL | 7 |
| [ ] | `app6/stage1/__init__.py::__getattr__` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/__init__.py::__getattr__` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/engine.py::Stage2Config.__post_init__` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/engine.py::Stage2Config.payload` | critical | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/engine.py::Stage2Engine._persistence` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/engine.py::Stage2Engine.run` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/engine.py::_atomic_npz` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/engine.py::_pair_qc_decision` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/engine.py::_read_checkpoint` | critical | NOT_REVIEWED | 6 |

### PKG-030 — Cross-stage handoffs, determinism, resume, security

- **Status:** `NOT_REVIEWED`; **functions:** 22; **prerequisites:** PKG-029
- **Command:** `python3 -m pytest -q {targeted_test_paths} --maxfail=1`
- **Fixture:** Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.
- **Expected artifacts:** pytest result/log; oracle outputs or hashes; handoff/schema assertions; regression test path
- **Closure:** Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.

| Done | Function ID | Risk | Current status | Missing strong evidence |
|---|---|---|---|---:|
| [ ] | `app6/stage2/engine.py::_record_qc` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/engine.py::_write_checkpoint` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/engine.py::utc` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/golden_fixture.py::_deltat_days` | medium | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/golden_fixture.py::_scenario_metrics` | high | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/golden_fixture.py::build_golden_snapshot_data` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/golden_fixture.py::golden_canonical` | medium | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/golden_fixture.py::write_golden_snapshot` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/integrity.py::compute_code_hash` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/integrity.py::compute_dataset_hash` | high | CLOSED_BASIC | 3 |
| [ ] | `app6/stage2/integrity.py::verify_integrity_hashes` | high | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/legacy_bridge.py::bridge_coverage` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/legacy_bridge.py::build_retest_target` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/legacy_bridge.py::normalize_photo_id` | medium | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/legacy_bridge.py::normalize_pose_bin` | high | CLOSED_BASIC | 5 |
| [ ] | `app6/stage2/loaders.py::_missing_alpha` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/loaders.py::_read_landmark_csv` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/loaders.py::_required_npz_array` | critical | NOT_REVIEWED | 6 |
| [ ] | `app6/stage2/loaders.py::_rows` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/loaders.py::load_main` | critical | CLOSED_BASIC | 4 |
| [ ] | `app6/stage2/validation.py::_as_bool` | critical | NOT_REVIEWED | 7 |
| [ ] | `app6/stage2/validation.py::validate_analysis_contract` | critical | CLOSED_BASIC | 4 |

## BLOCKED_EXTERNAL

- `app6/scripts/fetch_external_assets.py::main` — Depends on external/model or unavailable calibrated artifact; no rerun integration evidence
- `app6/scripts/fetch_external_assets.py::sha` — Depends on external/model or unavailable calibrated artifact; no rerun integration evidence

## Arithmetic and integrity

- Production callables: 585
- Data-bearing: 567 = CLOSED_STRONG + CLOSED_BASIC + IN_PROGRESS + FAILED + BLOCKED_EXTERNAL + NOT_REVIEWED.
- Unique IDs: 567; exactly-one-package assignments: 567.
- Register SHA-256: `edecc93e1830758e8dc241d645c74300a8cca01336d8f042e0907cc4b1bfb359`

<!-- END GENERATED: function-checklist -->

## Update procedure

1. Before a batch, record baseline commit/worktree state and source/fixture hashes in the ledger.
2. Mark the package/functions `IN_PROGRESS` in JSON; run the package command with immutable fixtures.
3. For failures: identify root cause → fix production code → add focused regression. Do not weaken an oracle.
4. Update each function record: evidence links/state, missing evidence, last run/date, result, blocker, notes and status.
5. Run `python3 scripts/update_function_checklist.py`; it validates uniqueness, arithmetic, statuses and exactly-one batch membership, then refreshes generated Markdown.
6. Run full regression, record result, then run `python3 scripts/update_function_checklist.py --check`.
7. Commit JSON, Markdown, tests and any production fix together. Append a ledger row; never rewrite historical rows.

Bootstrap only (if canonical JSON is absent):

```bash
python3 scripts/update_function_checklist.py --source-register /Volumes/SDCARD/storage/function-closure-cleanup/function_register.json
python3 scripts/update_function_checklist.py --check
```

## Progress Ledger

<!-- BEGIN MANUAL: progress-ledger (append-only) -->
| UTC date | Batch | Baseline commit/state | Input/fixture hashes | Command | Result | Production fix | Regression/evidence | Operator/notes |
|---|---|---|---|---|---|---|---|---|
| YYYY-MM-DDTHH:MM:SSZ | PKG-NNN | commit + clean/dirty | sha256:… | `…` | PASS/FAIL/BLOCKED | paths/commit or none | test paths/artifacts | append only |
| PKG-001 run | PKG-001 | `be0c80dbbbbd9b448029f039cb17f21f00f503e8` + dirty unrelated state preserved | register `edecc93e…359`; baseline in artifact | targeted + full regressions | PASS: 17/17 CLOSED_STRONG | provenance/date/robust-scale fixes | `/Volumes/SDCARD/storage/function-verification-runs/PKG-001/` | autonomous strict verification |
<!-- END MANUAL: progress-ledger -->
