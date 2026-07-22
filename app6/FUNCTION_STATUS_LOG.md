# FUNCTION STATUS LOG — app6

> ⚙️ СГЕНЕРИРОВАНО АВТОМАТИЧЕСКИ: `python -m app6.scripts.build_function_status_log`.
> Ручные правки будут перезаписаны. Декларативный аудит — в `STATUS_AUDIT.py`,
> правила статусов — в `CONVENTIONS.py`, рантайм-флоу — в `stage1/status_logger.py`.

## Поток статусов

```
🔴 need_testing → ✅ complete → 🚪 closed
дополнительно: ⚠️ in_progress · 🚫 blocked · ❌ error · 🔬 experimental · 🗑️ deprecated
```

## Покрытие: 243/524 функций имеют статус-маркеры (46.4%)

| Модуль | Функция | Строка | Статус(ы) | Роли |
|---|---|---:|---|---|
| `app6/STATUS_AUDIT.py` | `print_audit_summary` | 321 | — | 📤 |
| `app6/run_calibration.py` | `main` | 13 | — | 🚪 |
| `app6/run_private_hypotheses.py` | `main` | 14 | — | 🚪 |
| `app6/run_stage1.py` | `build_parser` | 51 | — | 🏭 |
| `app6/run_stage1.py` | `main` | 69 | — | 🚪 |
| `app6/run_stage2.py` | `main` | 14 | — | 🚪 |
| `app6/run_stage2b.py` | `main` | 13 | — | 🚪 |
| `app6/run_stage3.py` | `main` | 13 | — | 🚪 |
| `app6/scripts/audit_100_metric_pipeline.py` | `_write_csv` 🔒 | 26 | — | — |
| `app6/scripts/audit_100_metric_pipeline.py` | `_source_corpus` 🔒 | 33 | — | — |
| `app6/scripts/audit_100_metric_pipeline.py` | `run_audit` | 38 | — | — |
| `app6/scripts/build_function_status_log.py` | `_is_own` 🔒 | 24 | — | — |
| `app6/scripts/build_function_status_log.py` | `scan` | 30 | — | — |
| `app6/scripts/build_function_status_log.py` | `fmt_status` | 68 | — | — |
| `app6/scripts/build_function_status_log.py` | `main` | 77 | — | — |
| `app6/scripts/check_geometry_vs_evidence.py` | `load_mask` | 25 | — | — |
| `app6/scripts/check_geometry_vs_evidence.py` | `analyze_pkg` | 38 | — | — |
| `app6/scripts/check_geometry_vs_evidence.py` | `main` | 105 | — | — |
| `app6/scripts/fetch_external_assets.py` | `sha` | 17 | — | — |
| `app6/scripts/fetch_external_assets.py` | `main` | 23 | — | — |
| `app6/scripts/preflight_skin_v3.py` | `main` | 15 | — | — |
| `app6/scripts/preflight_skin_v3.py` | `add` | 17 | — | — |
| `app6/scripts/release_gate_skin.py` | `main` | 11 | — | — |
| `app6/scripts/release_gate_skin.py` | `add` | 13 | — | — |
| `app6/scripts/render_skin_zone_atlas.py` | `main` | 30 | — | — |
| `app6/stage1/assets.py` | `_bbox` 🔒 | 27 | — | — |
| `app6/stage1/assets.py` | `_letterbox` 🔒 | 41 | — | — |
| `app6/stage1/assets.py` | `save_image_assets` | 53 | log: need_testing | — |
| `app6/stage1/assets.py` | `technical_quality` | 73 | log: need_testing | — |
| `app6/stage1/assets.py` | `save_uv_and_mesh` | 97 | log: need_testing | — |
| `app6/stage1/assets.py` | `_write_obj` 🔒 | 190 | — | — |
| `app6/stage1/assets.py` | `save_face_mask` | 204 | log: need_testing; ⚠️ IN PROGRESS | 🎯 🔗 💡 🚨 |
| `app6/stage1/assets.py` | `save_semantic_channels` | 304 | log: need_testing | — |
| `app6/stage1/config.py` | `extraction_payload` | 47 | — | 📤 |
| `app6/stage1/config.py` | `public_dict` | 60 | — | 📤 |
| `app6/stage1/engine.py` | `_utc` 🔒 | 40 | — | — |
| `app6/stage1/engine.py` | `_landmark_rows` 🔒 | 44 | log: need_testing | 📊 |
| `app6/stage1/engine.py` | `__init__` 🔒 | 67 | — | — |
| `app6/stage1/engine.py` | `run` | 89 | log: complete | — |
| `app6/stage1/engine.py` | `_one` 🔒 | 166 | log: need_testing; ⚠️ IN PROGRESS | 🎯 🔗 💡 🚨 |
| `app6/stage1/engine.py` | `_relative` 🔒 | 490 | — | — |
| `app6/stage1/engine.py` | `_index_row` 🔒 | 497 | — | — |
| `app6/stage1/engine.py` | `_compute_landmark_confidence` 🔒 | 260 | — | 📊 |
| `app6/stage1/geometry.py` | `classify_pose` | 20 | log: complete; ⚠️ IN PROGRESS | 💡 📊 |
| `app6/stage1/geometry.py` | `nearest_canonical_yaw` | 44 | log: in_progress; ⚠️ IN PROGRESS | 📊 |
| `app6/stage1/geometry.py` | `row_rotation_matrix` | 69 | log: complete | — |
| `app6/stage1/geometry.py` | `full_pose_correction_matrix` | 79 | log: complete | — |
| `app6/stage1/geometry.py` | `normalize_mesh` | 113 | log: complete | — |
| `app6/stage1/geometry.py` | `normalize_mesh_landmark_anchored` | 129 | log: need_testing | — |
| `app6/stage1/geometry.py` | `compute_chronology_alignment` | 169 | log: complete | — |
| `app6/stage1/geometry.py` | `to_original_image` | 224 | log: in_progress; ⚠️ IN PROGRESS | 🎯 🔗 💡 |
| `app6/stage1/geometry.py` | `reprojection_stats` | 242 | log: need_testing | — |
| `app6/stage1/geometry.py` | `pack_mask` | 255 | log: complete | — |
| `app6/stage1/geometry.py` | `unpack_mask` | 260 | log: complete | — |
| `app6/stage1/masks.py` | `build_mask_bundle` | 36 | log: complete; ⚠️ IN PROGRESS | 🎯 🔗 💡 🚨 |
| `app6/stage1/naming.py` | `parse_photo_name` | 32 | log: complete | — |
| `app6/stage1/naming.py` | `make_photo_id` | 64 | log: complete | — |
| `app6/stage1/quality_zones.py` | `_utc` 🔒 | 25 | — | — |
| `app6/stage1/quality_zones.py` | `_pack_masks` 🔒 | 29 | — | — |
| `app6/stage1/quality_zones.py` | `_mask_bbox` 🔒 | 35 | — | — |
| `app6/stage1/quality_zones.py` | `_erode` 🔒 | 44 | — | — |
| `app6/stage1/quality_zones.py` | `_to_face_space` 🔒 | 51 | — | — |
| `app6/stage1/quality_zones.py` | `_texture_stats` 🔒 | 70 | — | — |
| `app6/stage1/quality_zones.py` | `_forehead_fallback_zones` 🔒 | 110 | — | — |
| `app6/stage1/quality_zones.py` | `build_quality_files` | 181 | log: deprecated | — |
| `app6/stage1/reconstruction.py` | `landmark_arrays` | 67 | log: complete | — |
| `app6/stage1/reconstruction.py` | `__init__` 🔒 | 87 | — | — |
| `app6/stage1/reconstruction.py` | `_resolve_device` 🔒 | 114 | — | — |
| `app6/stage1/reconstruction.py` | `_check_assets` 🔒 | 132 | — | — |
| `app6/stage1/reconstruction.py` | `_np` 🔒 | 141 | — | — |
| `app6/stage1/reconstruction.py` | `process` | 147 | log: need_testing; ⚠️ IN PROGRESS | 🎯 🔗 💡 🚨 |
| `app6/stage1/reconstruction.py` | `cleanup` | 356 | log: need_testing | — |
| `app6/stage1/reconstruction.py` | `capture_alpha` | 206 | — | 🔄 |
| `app6/stage1/reconstruction.py` | `renderer_forward` | 214 | — | 🔄 |
| `app6/stage1/skin/atlas_registry.py` | `__init__` 🔒 | 11 | — | — |
| `app6/stage1/skin/atlas_registry.py` | `_sha` 🔒 | 15 | — | — |
| `app6/stage1/skin/atlas_registry.py` | `verify_topology` | 18 | ✅ VERIFIED | — |
| `app6/stage1/skin/atlas_registry.py` | `validate` | 23 | ✅ VERIFIED | — |
| `app6/stage1/skin/atlas_registry.py` | `describe` | 31 | — | 📤 |
| `app6/stage1/skin/batch.py` | `_to_original` 🔒 | 45 | — | — |
| `app6/stage1/skin/batch.py` | `__init__` 🔒 | 12 | — | — |
| `app6/stage1/skin/batch.py` | `run` | 14 | — | 🚪 |
| `app6/stage1/skin/config_loader.py` | `load_config` | 8 | — | ⚙️ |
| `app6/stage1/skin/config_loader.py` | `merge` | 11 | — | 🔀 |
| `app6/stage1/skin/contamination.py` | `__init__` 🔒 | 11 | — | — |
| `app6/stage1/skin/contamination.py` | `_load` 🔒 | 15 | — | — |
| `app6/stage1/skin/contamination.py` | `predict` | 26 | 🔬 EXPERIMENTAL | — |
| `app6/stage1/skin/contamination.py` | `metadata` | 32 | — | 📤 |
| `app6/stage1/skin/contracts.py` | `require_schema` | 37 | — | 🚨 |
| `app6/stage1/skin/contracts.py` | `validate_missing` | 41 | ✅ VERIFIED | — |
| `app6/stage1/skin/contracts.py` | `to_dict` | 27 | — | 📤 |
| `app6/stage1/skin/contracts.py` | `to_dict` | 33 | — | 📤 |
| `app6/stage1/skin/feature_registry.py` | `register` | 12 | — | 📝 📝 |
| `app6/stage1/skin/feature_registry.py` | `export_registry` | 22 | — | 📤 |
| `app6/stage1/skin/input_provenance.py` | `decode_oriented` | 10 | ✅ VERIFIED | — |
| `app6/stage1/skin/local_features/detector.py` | `detect` | 11 | log: complete | — |
| `app6/stage1/skin/manifest.py` | `decoded_sha256` | 12 | — | 📊 |
| `app6/stage1/skin/manifest.py` | `create_manifest` | 14 | — | 🏭 |
| `app6/stage1/skin/manifest.py` | `finalize_manifest` | 17 | — | 🎯 |
| `app6/stage1/skin/material/evidence.py` | `_between` 🔒 | 8 | — | — |
| `app6/stage1/skin/material/evidence.py` | `_median` 🔒 | 15 | — | — |
| `app6/stage1/skin/material/evidence.py` | `build` | 18 | log: experimental | — |
| `app6/stage1/skin/migrations.py` | `require_current` | 7 | — | 🚨 |
| `app6/stage1/skin/migrations.py` | `migrate` | 10 | — | 🔄 |
| `app6/stage1/skin/patch_registry.py` | `build_patch_registry` | 8 | — | 🏭 |
| `app6/stage1/skin/patch_sampler.py` | `connected_components` | 9 | — | 🔢 |
| `app6/stage1/skin/patch_sampler.py` | `sample_zone_patches` | 12 | log: complete | — |
| `app6/stage1/skin/photometric.py` | `branches` | 7 | log: complete | — |
| `app6/stage1/skin/pipeline.py` | `_resolve_pose_policy_csv` 🔒 | 37 | — | — |
| `app6/stage1/skin/pipeline.py` | `build_skin_package` | 52 | log: complete; ⚠️ IN PROGRESS | 🎯 🔗 💡 🚨 |
| `app6/stage1/skin/pipeline.py` | `focus` | 366 | — | 💡 |
| `app6/stage1/skin/pose_policy.py` | `yaw_to_bin` | 32 | — | 📊 |
| `app6/stage1/skin/pose_policy.py` | `__init__` 🔒 | 40 | — | — |
| `app6/stage1/skin/pose_policy.py` | `_build_default` 🔒 | 85 | — | — |
| `app6/stage1/skin/pose_policy.py` | `get` | 127 | — | 🔍 |
| `app6/stage1/skin/pose_policy.py` | `_selected_center` 🔒 | 131 | — | — |
| `app6/stage1/skin/pose_policy.py` | `weights` | 138 | — | 📊 |
| `app6/stage1/skin/pose_policy.py` | `soft_evidence_weights` | 173 | — | 📊 |
| `app6/stage1/skin/pose_policy.py` | `is_compatible` | 234 | ✅ VERIFIED | — |
| `app6/stage1/skin/pose_policy.py` | `common_observed_gate` | 256 | — | 🚧 |
| `app6/stage1/skin/pose_policy.py` | `pose_delta_gate` | 268 | — | — |
| `app6/stage1/skin/previews.py` | `_zone_colors` 🔒 | 11 | — | — |
| `app6/stage1/skin/previews.py` | `_atlas_overlay` 🔒 | 18 | — | — |
| `app6/stage1/skin/previews.py` | `_smooth_map` 🔒 | 27 | — | — |
| `app6/stage1/skin/previews.py` | `save_previews` | 45 | log: complete | — |
| `app6/stage1/skin/previews.py` | `save_wrinkle_overlay` | 84 | log: complete | — |
| `app6/stage1/skin/projection.py` | `rasterize_surface` | 46 | log: in_progress | — |
| `app6/stage1/skin/projection.py` | `project_atlas` | 179 | log: complete | — |
| `app6/stage1/skin/quality.py` | `_robust01` 🔒 | 21 | — | — |
| `app6/stage1/skin/quality.py` | `_jpeg_block_energy` 🔒 | 27 | — | — |
| `app6/stage1/skin/quality.py` | `_projected_scale_from_triangle_id` 🔒 | 38 | — | — |
| `app6/stage1/skin/quality.py` | `_edge_width_estimator` 🔒 | 49 | — | — |
| `app6/stage1/skin/quality.py` | `_local_dynamic_range` 🔒 | 59 | — | — |
| `app6/stage1/skin/quality.py` | `_sanitize_density` 🔒 | 66 | — | — |
| `app6/stage1/skin/quality.py` | `quality_maps` | 94 | log: complete | — |
| `app6/stage1/skin/quality.py` | `applicability` | 202 | log: complete | — |
| `app6/stage1/skin/quality.py` | `per_zone_applicability` | 277 | log: complete | — |
| `app6/stage1/skin/quality.py` | `_med` 🔒 | 205 | — | — |
| `app6/stage1/skin/run_manager.py` | `__init__` 🔒 | 10 | — | — |
| `app6/stage1/skin/run_manager.py` | `initialize` | 12 | — | 🏭 |
| `app6/stage1/skin/run_manager.py` | `finalize` | 18 | — | 🔒 |
| `app6/stage1/skin/run_manager.py` | `assert_mutable` | 24 | — | 🚨 |
| `app6/stage1/skin/sensitivity/degradation.py` | `variants` | 9 | — | 🏭 |
| `app6/stage1/skin/sensitivity/degradation.py` | `benchmark` | 17 | log: complete | — |
| `app6/stage1/skin/serialization.py` | `sha256_file` | 12 | — | 📊 |
| `app6/stage1/skin/serialization.py` | `canonical_hash` | 27 | — | 📊 |
| `app6/stage1/skin/serialization.py` | `atomic_json` | 29 | — | 🎯 |
| `app6/stage1/skin/serialization.py` | `atomic_npz` | 37 | — | 🎯 |
| `app6/stage1/skin/serialization.py` | `inventory` | 47 | — | 📤 |
| `app6/stage1/skin/serialization.py` | `validate_npz_no_pickle` | 50 | — | 🚨 |
| `app6/stage1/skin/serialization.py` | `default` | 19 | — | 🔄 |
| `app6/stage1/skin/surface_geometry.py` | `__init__` 🔒 | 10 | — | — |
| `app6/stage1/skin/surface_geometry.py` | `adjacency` | 19 | — | — |
| `app6/stage1/skin/surface_geometry.py` | `distance` | 28 | — | 🔢 |
| `app6/stage1/skin/surface_geometry.py` | `vertex_normals` | 48 | — | 🔢 |
| `app6/stage1/skin/surface_geometry.py` | `tangent_frames` | 53 | — | 🔢 |
| `app6/stage1/skin/surface_geometry.py` | `transport_local` | 56 | 🔬 EXPERIMENTAL | — |
| `app6/stage1/skin/surface_geometry.py` | `transport_roundtrip_error` | 60 | — | 📊 |
| `app6/stage1/skin/surface_geometry.py` | `metadata` | 63 | — | 📤 |
| `app6/stage1/skin/texture/basic.py` | `_weighted_quantile` 🔒 | 9 | — | — |
| `app6/stage1/skin/texture/basic.py` | `extract_basic` | 18 | log: complete | — |
| `app6/stage1/skin/texture/features.py` | `_lbp` 🔒 | 35 | — | — |
| `app6/stage1/skin/texture/features.py` | `_glcm_full` 🔒 | 46 | — | — |
| `app6/stage1/skin/texture/features.py` | `_spectral_full` 🔒 | 95 | — | — |
| `app6/stage1/skin/texture/features.py` | `extract_texture_features` | 157 | log: complete | — |
| `app6/stage1/skin/wrinkles/classical.py` | `response_map_scale_adaptive` | 29 | — | 📊 |
| `app6/stage1/skin/wrinkles/classical.py` | `response_map` | 71 | — | 🔄 |
| `app6/stage1/skin/wrinkles/classical.py` | `_branch_paths` 🔒 | 90 | — | — |
| `app6/stage1/skin/wrinkles/classical.py` | `detect` | 106 | log: complete | — |
| `app6/stage1/skin/wrinkles/ffhq_adapter.py` | `__init__` 🔒 | 12 | — | — |
| `app6/stage1/skin/wrinkles/ffhq_adapter.py` | `_load` 🔒 | 17 | — | — |
| `app6/stage1/skin/wrinkles/ffhq_adapter.py` | `_load_parser` 🔒 | 23 | — | — |
| `app6/stage1/skin/wrinkles/ffhq_adapter.py` | `_skin_mask` 🔒 | 34 | — | — |
| `app6/stage1/skin/wrinkles/ffhq_adapter.py` | `predict` | 42 | 🔬 EXPERIMENTAL | — |
| `app6/stage1/skin/wrinkles/ffhq_adapter.py` | `metadata` | 51 | — | 📤 |
| `app6/stage1/skin_zone_atlas.py` | `build_triangle_zone_map` | 193 | ⚠️ IN PROGRESS | — |
| `app6/stage1/skin_zone_atlas.py` | `_zone_colors` 🔒 | 218 | — | — |
| `app6/stage1/skin_zone_atlas.py` | `_tri_px` 🔒 | 229 | — | — |
| `app6/stage1/skin_zone_atlas.py` | `render_atlas_png` | 243 | — | 📤 |
| `app6/stage1/skin_zone_atlas.py` | `_pose_weight` 🔒 | 275 | — | — |
| `app6/stage1/skin_zone_atlas.py` | `build_pose_policy` | 295 | — | 🏭 |
| `app6/stage1/skin_zone_atlas.py` | `build_atlas_json` | 303 | — | 📤 |
| `app6/stage1/skin_zone_atlas.py` | `generate_canonical_atlas` | 333 | — | 🏭 |
| `app6/stage1/skin_zone_atlas.py` | `write_pose_policy_csv` | 390 | — | 📤 |
| `app6/stage1/skin_zone_atlas.py` | `load_canonical_atlas` | 399 | ✅ VERIFIED | — |
| `app6/stage1/skin_zone_atlas.py` | `_boundary_safe_mask` 🔒 | 416 | — | — |
| `app6/stage1/skin_zone_atlas.py` | `_uv_to_original` 🔒 | 422 | — | — |
| `app6/stage1/skin_zone_atlas.py` | `project_atlas_to_photo` | 435 | — | 🎯 |
| `app6/stage1/skin_zone_atlas.py` | `_render_overlay` 🔒 | 602 | — | — |
| `app6/stage1/skin_zone_atlas.py` | `zone_names` | 619 | — | 📤 |
| `app6/stage1/skin_zone_atlas_final.py` | `validate_definitions` | 143 | ✅ VERIFIED | — |
| `app6/stage1/skin_zone_atlas_final.py` | `triangle_centroids_uv` | 161 | — | 🔢 |
| `app6/stage1/skin_zone_atlas_final.py` | `points_in_polygon` | 168 | — | 🔢 |
| `app6/stage1/skin_zone_atlas_final.py` | `build_primary_triangle_zone` | 177 | — | 🎯 |
| `app6/stage1/skin_zone_atlas_final.py` | `zone_role_for_pose` | 197 | — | 📊 |
| `app6/stage1/skin_zone_atlas_final.py` | `export_contract` | 213 | — | 📤 |
| `app6/stage1/skin_zone_atlas_final.py` | `load_canonical_atlas` | 238 | ✅ VERIFIED | — |
| `app6/stage1/skin_zone_atlas_final.py` | `_boundary_safe_mask` 🔒 | 265 | — | — |
| `app6/stage1/skin_zone_atlas_final.py` | `_uv_to_original` 🔒 | 270 | — | — |
| `app6/stage1/skin_zone_atlas_final.py` | `_zone_colors` 🔒 | 278 | — | — |
| `app6/stage1/skin_zone_atlas_final.py` | `project_atlas_to_photo` | 289 | — | 🎯 |
| `app6/stage1/status_logger.py` | `log_status` | 52 | — | 🎯 |
| `app6/stage1/status_logger.py` | `log_need_testing` | 86 | — | — |
| `app6/stage1/status_logger.py` | `log_complete` | 91 | — | — |
| `app6/stage1/status_logger.py` | `close_function` | 97 | — | 🔒 |
| `app6/stage1/status_logger.py` | `_update_audit_status` 🔒 | 109 | — | — |
| `app6/stage1/status_logger.py` | `log_blocker` | 130 | — | — |
| `app6/stage1/status_logger.py` | `log_warning` | 139 | ⚠️ IN PROGRESS | — |
| `app6/stage1/status_logger.py` | `status_warning` | 144 | — | — |
| `app6/stage1/status_logger.py` | `log_error` | 151 | ❌ KNOWN ISSUE | — |
| `app6/stage1/status_logger.py` | `log_experimental` | 157 | 🔬 EXPERIMENTAL | — |
| `app6/stage1/status_logger.py` | `mark_verified` | 168 | ✅ VERIFIED | — |
| `app6/stage1/status_logger.py` | `mark_closed` | 172 | — | 🚪 |
| `app6/stage1/status_logger.py` | `is_verified` | 178 | — | 🔍 |
| `app6/stage1/status_logger.py` | `is_closed` | 182 | — | 🔍 |
| `app6/stage1/status_logger.py` | `print_status_summary` | 188 | — | 📤 |
| `app6/stage1/storage.py` | `atomic_photo_directory` | 20 | log: complete | — |
| `app6/stage1/storage.py` | `clean_incomplete` | 47 | log: complete | — |
| `app6/stage1/storage.py` | `write_failure` | 58 | log: complete | — |
| `app6/stage1/utils.py` | `sha256_file` | 24 | log: need_testing | — |
| `app6/stage1/utils.py` | `sha256_json` | 33 | log: need_testing | — |
| `app6/stage1/utils.py` | `sha256_paths` | 39 | log: need_testing | — |
| `app6/stage1/utils.py` | `json_ready` | 54 | — | 🔄 |
| `app6/stage1/utils.py` | `atomic_json` | 73 | log: need_testing | — |
| `app6/stage1/utils.py` | `write_csv` | 81 | log: need_testing | — |
| `app6/stage1/utils.py` | `runtime_versions` | 96 | log: need_testing | — |
| `app6/stage1/utils.py` | `version` | 99 | — | 📤 |
| `app6/stage1/validator.py` | `_resolve_topology` 🔒 | 33 | — | — |
| `app6/stage1/validator.py` | `_csv_check` 🔒 | 91 | — | — |
| `app6/stage1/validator.py` | `validate_photo` | 104 | log: complete | — |
| `app6/stage1/validator.py` | `is_resumable` | 320 | log: need_testing | — |
| `app6/stage2/alpha_chronology.py` | `apply_alpha_chronology` | 18 | log: complete | — |
| `app6/stage2/anchor_policy.py` | `stable_anchor_mask` | 14 | log: complete | — |
| `app6/stage2/anchor_policy.py` | `stable_anchor_indices` | 50 | log: complete | — |
| `app6/stage2/baseline_return.py` | `_load_vectors` 🔒 | 26 | — | — |
| `app6/stage2/baseline_return.py` | `_reversal_stats` 🔒 | 40 | — | — |
| `app6/stage2/baseline_return.py` | `apply_baseline_return` | 60 | log: complete | — |
| `app6/stage2/calibration.py` | `__init__` 🔒 | 18 | — | — |
| `app6/stage2/calibration.py` | `_pose_distance` 🔒 | 27 | — | — |
| `app6/stage2/calibration.py` | `_build_references` 🔒 | 30 | — | — |
| `app6/stage2/calibration.py` | `_nearest` 🔒 | 46 | — | — |
| `app6/stage2/calibration.py` | `matched_null` | 57 | — | 📊 |
| `app6/stage2/calibration.py` | `reference` | 72 | — | 📊 |
| `app6/stage2/calibration.py` | `consistency_check` | 75 | ⚠️ IN PROGRESS | 📊 |
| `app6/stage2/calibration.py` | `score` | 50 | — | 📊 |
| `app6/stage2/calibration_sensitivity.py` | `leave_one_dataset_sensitivity` | 25 | — | 📊 |
| `app6/stage2/chronology.py` | `_days` 🔒 | 13 | — | — |
| `app6/stage2/chronology.py` | `_robust` 🔒 | 20 | — | — |
| `app6/stage2/chronology.py` | `apply_chronology_rate_flags` | 25 | log: in_progress; ⚠️ IN PROGRESS | 🎯 💡 |
| `app6/stage2/chronology.py` | `apply_biological_rate_flags` | 99 | log: deprecated; 🗑️ DEPRECATED | — |
| `app6/stage2/core.py` | `_rigid_align` 🔒 | 56 | — | — |
| `app6/stage2/core.py` | `robust_rigid_align` | 70 | — | 🎯 |
| `app6/stage2/core.py` | `_stats` 🔒 | 129 | — | — |
| `app6/stage2/core.py` | `compare_landmarks` | 138 | log: complete; ⚠️ IN PROGRESS | 🎯 🔗 💡 🚨 |
| `app6/stage2/core.py` | `build_coordinate_zone_map` | 243 | log: complete | — |
| `app6/stage2/core.py` | `robust_reference` | 259 | log: complete | — |
| `app6/stage2/core.py` | `calibrated_score` | 269 | log: complete | 📊 |
| `app6/stage2/core.py` | `zone_weighted_score` | 303 | log: complete | 📊 |
| `app6/stage2/core.py` | `_alpha_l2` 🔒 | 197 | — | — |
| `app6/stage2/corroboration.py` | `_date` 🔒 | 25 | — | — |
| `app6/stage2/corroboration.py` | `apply_cross_bin_corroboration` | 32 | log: complete | — |
| `app6/stage2/corroboration.py` | `aggregate_events` | 93 | log: complete | — |
| `app6/stage2/descriptors.py` | `_neighbors` 🔒 | 14 | — | — |
| `app6/stage2/descriptors.py` | `_one` 🔒 | 18 | — | — |
| `app6/stage2/descriptors.py` | `local_pair_descriptors` | 25 | log: complete | — |
| `app6/stage2/descriptors.py` | `__init__` 🔒 | 44 | — | — |
| `app6/stage2/descriptors.py` | `_pd` 🔒 | 46 | — | — |
| `app6/stage2/descriptors.py` | `_build` 🔒 | 47 | — | — |
| `app6/stage2/descriptors.py` | `score` | 65 | — | 📊 |
| `app6/stage2/engine.py` | `utc` | 48 | — | 🔄 |
| `app6/stage2/engine.py` | `payload` | 54 | — | 🏭 |
| `app6/stage2/engine.py` | `__post_init__` 🔒 | 56 | — | — |
| `app6/stage2/engine.py` | `__init__` 🔒 | 61 | — | — |
| `app6/stage2/engine.py` | `run` | 62 | log: complete; ⚠️ IN PROGRESS | 🎯 🔗 💡 🚨 |
| `app6/stage2/engine.py` | `_persistence` 🔒 | 300 | — | — |
| `app6/stage2/evidence.py` | `evidence_state` | 37 | log: complete | — |
| `app6/stage2/evidence.py` | `alternative_reasons` | 44 | log: complete | — |
| `app6/stage2/evidence.py` | `packet_from_pair` | 99 | log: complete | — |
| `app6/stage2/evidence.py` | `to_dict` | 95 | — | 📤 |
| `app6/stage2/generate_mesh_zones.py` | `generate_zones` | 77 | — | 🏭 |
| `app6/stage2/generate_mesh_zones.py` | `main` | 127 | — | 🚪 |
| `app6/stage2/leads.py` | `_date` 🔒 | 13 | — | — |
| `app6/stage2/leads.py` | `_load` 🔒 | 17 | — | — |
| `app6/stage2/leads.py` | `load_leads` | 23 | log: complete | — |
| `app6/stage2/leads.py` | `pair_leads` | 82 | log: complete | — |
| `app6/stage2/leads.py` | `add` | 31 | — | 📝 📝 |
| `app6/stage2/loaders.py` | `_rows` 🔒 | 19 | — | — |
| `app6/stage2/loaders.py` | `load_main` | 24 | log: complete; ⚠️ IN PROGRESS | 🎯 🔗 💡 🚨 |
| `app6/stage2/loaders.py` | `_read_landmark_csv` 🔒 | 108 | — | — |
| `app6/stage2/loaders.py` | `_missing_alpha` 🔒 | 124 | — | — |
| `app6/stage2/loaders.py` | `load_calibration_from_sidecar` | 129 | log: complete | — |
| `app6/stage2/loaders.py` | `load_calibration` | 185 | log: complete | — |
| `app6/stage2/mesh_calibration.py` | `_pose_distance` 🔒 | 29 | — | — |
| `app6/stage2/mesh_calibration.py` | `_mesh_metrics` 🔒 | 33 | — | — |
| `app6/stage2/mesh_calibration.py` | `__init__` 🔒 | 90 | — | — |
| `app6/stage2/mesh_calibration.py` | `_build` 🔒 | 95 | — | — |
| `app6/stage2/mesh_calibration.py` | `to_json` | 136 | — | 📤 |
| `app6/stage2/mesh_calibration.py` | `score` | 149 | — | 📊 |
| `app6/stage2/mesh_dense.py` | `_resolve_mesh_count` 🔒 | 31 | — | — |
| `app6/stage2/mesh_dense.py` | `load_anatomical_zones` | 64 | — | — |
| `app6/stage2/mesh_dense.py` | `_normalize` 🔒 | 79 | — | — |
| `app6/stage2/mesh_dense.py` | `_load_mesh` 🔒 | 89 | — | — |
| `app6/stage2/mesh_dense.py` | `_subsample` 🔒 | 123 | — | — |
| `app6/stage2/mesh_dense.py` | `_zone_labels` 🔒 | 131 | — | — |
| `app6/stage2/mesh_dense.py` | `_shape_descriptor` 🔒 | 140 | — | — |
| `app6/stage2/mesh_dense.py` | `dense_mesh_pair` | 164 | log: complete | — |
| `app6/stage2/metric_registry.py` | `validate_registry` | 72 | ✅ VERIFIED | — |
| `app6/stage2/metric_registry.py` | `_usable` 🔒 | 84 | — | — |
| `app6/stage2/metric_registry.py` | `metric_channel` | 92 | log: complete | — |
| `app6/stage2/metric_registry.py` | `build_metric_catalog` | 98 | log: complete | — |
| `app6/stage2/motion.py` | `pose_motion_support` | 25 | — | 🚧 |
| `app6/stage2/motion.py` | `aligned_point_motion` | 35 | log: complete; ⚠️ IN PROGRESS | 🎯 🔗 💡 |
| `app6/stage2/motion.py` | `__init__` 🔒 | 77 | — | — |
| `app6/stage2/motion.py` | `_pose_distance` 🔒 | 80 | — | — |
| `app6/stage2/motion.py` | `_build` 🔒 | 81 | — | — |
| `app6/stage2/motion.py` | `score` | 102 | — | 📊 |
| `app6/stage2/motion.py` | `landmark_stability_score` | 122 | ⚠️ IN PROGRESS | 📊 |
| `app6/stage2/motion.py` | `_coherence` 🔒 | 161 | — | — |
| `app6/stage2/multiple_testing.py` | `_p_from_z` 🔒 | 14 | — | — |
| `app6/stage2/multiple_testing.py` | `_bh_qvalues` 🔒 | 22 | — | — |
| `app6/stage2/multiple_testing.py` | `apply_pair_fdr` | 37 | log: complete | — |
| `app6/stage2/multiple_testing.py` | `apply_zone_fdr` | 68 | log: complete | — |
| `app6/stage2/pose_leakage.py` | `_finite_pairs` 🔒 | 22 | — | — |
| `app6/stage2/pose_leakage.py` | `pose_leakage_diagnostic` | 36 | log: complete | — |
| `app6/stage2/postprocess_reports.py` | `_num` 🔒 | 33 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_manual_review_queue` 🔒 | 41 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_public_safety` 🔒 | 74 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_degraded_modules` 🔒 | 92 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_mesh_shape_summary` 🔒 | 115 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_texture_summary` 🔒 | 135 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_status_summary` 🔒 | 149 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_gate_report` 🔒 | 156 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_artifact_index` 🔒 | 176 | — | — |
| `app6/stage2/postprocess_reports.py` | `_write_stage3_input_summary` 🔒 | 186 | — | — |
| `app6/stage2/postprocess_reports.py` | `write_postprocess_reports` | 198 | log: complete | — |
| `app6/stage2/private_hypothesis.py` | `_utc` 🔒 | 60 | — | — |
| `app6/stage2/private_hypothesis.py` | `_sha256` 🔒 | 64 | — | — |
| `app6/stage2/private_hypothesis.py` | `_extract_records` 🔒 | 72 | — | — |
| `app6/stage2/private_hypothesis.py` | `_read_csv` 🔒 | 96 | — | — |
| `app6/stage2/private_hypothesis.py` | `_candidate_keys` 🔒 | 103 | — | — |
| `app6/stage2/private_hypothesis.py` | `_retest_record` 🔒 | 120 | — | — |
| `app6/stage2/private_hypothesis.py` | `walk` | 106 | — | 🔍 |
| `app6/stage2/private_hypothesis.py` | `__init__` 🔒 | 154 | — | — |
| `app6/stage2/private_hypothesis.py` | `run` | 157 | — | 🚪 |
| `app6/stage2/quality_integration.py` | `load_quality_zone_summary` | 17 | ✅ VERIFIED | — |
| `app6/stage2/quality_integration.py` | `pair_quality_zone_overlap` | 84 | log: complete | — |
| `app6/stage2/skin/applicability.py` | `common_surface` | 7 | — | 📊 |
| `app6/stage2/skin/calibration.py` | `load_records` | 13 | — | 🔄 |
| `app6/stage2/skin/calibration.py` | `load_profile` | 18 | — | 🔄 |
| `app6/stage2/skin/calibration.py` | `_group_id` 🔒 | 22 | — | — |
| `app6/stage2/skin/calibration.py` | `_split` 🔒 | 33 | — | — |
| `app6/stage2/skin/calibration.py` | `calibrate` | 61 | — | 📊 |
| `app6/stage2/skin/calibration.py` | `freeze_calibration` | 105 | — | 🔒 |
| `app6/stage2/skin/chronology.py` | `circular_line_distance_deg` | 11 | — | 🔢 |
| `app6/stage2/skin/chronology.py` | `match_branches` | 17 | — | 📊 |
| `app6/stage2/skin/chronology.py` | `analyze_records` | 35 | — | 📊 |
| `app6/stage2/skin/chronology.py` | `load_records` | 52 | — | 🔄 |
| `app6/stage2/skin/chronology.py` | `_date_value` 🔒 | 73 | — | — |
| `app6/stage2/skin/chronology.py` | `analyze_temporal_observations` | 81 | 🔬 EXPERIMENTAL | — |
| `app6/stage2/skin/dataset.py` | `validate_skin_dataset` | 9 | — | 🚨 |
| `app6/stage2/skin/engine.py` | `_angles_from_info_or_quality` 🔒 | 17 | — | — |
| `app6/stage2/skin/engine.py` | `__init__` 🔒 | 34 | — | — |
| `app6/stage2/skin/engine.py` | `_calibrate_pair` 🔒 | 39 | — | — |
| `app6/stage2/skin/engine.py` | `run` | 55 | — | 🚪 |
| `app6/stage2/skin/loader.py` | `__init__` 🔒 | 12 | — | — |
| `app6/stage2/skin/loader.py` | `npz` | 21 | — | 🔄 |
| `app6/stage2/skin/loader.py` | `json` | 23 | — | 🔄 |
| `app6/stage2/skin/loader.py` | `atlas` | 25 | — | 🔄 |
| `app6/stage2/skin/loader.py` | `surface` | 27 | — | 🔄 |
| `app6/stage2/skin/loader.py` | `quality` | 29 | — | 🔄 |
| `app6/stage2/skin/local_feature_matching.py` | `match_local_features` | 10 | — | 📊 |
| `app6/stage2/skin/material_model.py` | `evaluate_material` | 8 | — | 📊 |
| `app6/stage2/skin/package_calibration.py` | `_records` 🔒 | 10 | — | — |
| `app6/stage2/skin/package_calibration.py` | `build_package_calibration` | 23 | — | 🎯 |
| `app6/stage2/skin/pair_comparison.py` | `_pose_angles` 🔒 | 19 | — | — |
| `app6/stage2/skin/pair_comparison.py` | `_count_usable_zones` 🔒 | 32 | — | — |
| `app6/stage2/skin/pair_comparison.py` | `compare_packages` | 48 | — | 🎯 |
| `app6/stage2/skin/quality_matching.py` | `degradation_family` | 21 | 🔬 EXPERIMENTAL | — |
| `app6/stage2/skin/quality_matching.py` | `_texture_distance_for_waveform` 🔒 | 46 | — | — |
| `app6/stage2/skin/quality_matching.py` | `compare_sensitivity_packages` | 61 | — | 📊 |
| `app6/stage2/skin/quality_matching.py` | `to_dict` | 72 | — | 📤 |
| `app6/stage2/skin/symmetry.py` | `texture_symmetry` | 8 | — | 📊 |
| `app6/stage2/skin/texture_comparison.py` | `compare_texture` | 9 | — | 📊 |
| `app6/stage2/skin/uncertainty.py` | `bootstrap_interval` | 7 | — | 📊 |
| `app6/stage2/skin/wrinkle_matching.py` | `_poly_points` 🔒 | 20 | — | — |
| `app6/stage2/skin/wrinkle_matching.py` | `_resample_surface` 🔒 | 33 | — | — |
| `app6/stage2/skin/wrinkle_matching.py` | `_robust_hausdorff` 🔒 | 44 | — | — |
| `app6/stage2/skin/wrinkle_matching.py` | `match_wrinkle_packages` | 53 | 🔬 EXPERIMENTAL | — |
| `app6/stage2/technical_summary.py` | `build_technical_summary` | 14 | log: complete | — |
| `app6/stage2/texture_image.py` | `_unpack_mask` 🔒 | 30 | — | — |
| `app6/stage2/texture_image.py` | `_image_path` 🔒 | 36 | — | — |
| `app6/stage2/texture_image.py` | `_load_face_mask_texture` 🔒 | 53 | — | — |
| `app6/stage2/texture_image.py` | `_load_texture` 🔒 | 95 | — | — |
| `app6/stage2/texture_image.py` | `_lbp_histogram` 🔒 | 144 | — | — |
| `app6/stage2/texture_image.py` | `_glcm_stats` 🔒 | 176 | — | — |
| `app6/stage2/texture_image.py` | `_frequency_ratio` 🔒 | 226 | — | — |
| `app6/stage2/texture_image.py` | `_erode_roi` 🔒 | 244 | — | — |
| `app6/stage2/texture_image.py` | `_entropy` 🔒 | 256 | — | — |
| `app6/stage2/texture_image.py` | `_gabor_profile` 🔒 | 266 | — | — |
| `app6/stage2/texture_image.py` | `_patch_profile` 🔒 | 281 | — | — |
| `app6/stage2/texture_image.py` | `_stats` 🔒 | 305 | — | — |
| `app6/stage2/texture_image.py` | `texture_pair_deltas` | 333 | log: in_progress; ⚠️ IN PROGRESS | 🎯 💡 |
| `app6/stage2/texture_pair.py` | `summarize_texture_pairs` | 14 | log: complete | — |
| `app6/stage2/texture_structure.py` | `_patch` 🔒 | 17 | — | — |
| `app6/stage2/texture_structure.py` | `register_patches` | 38 | — | 🏭 |
| `app6/stage2/texture_structure.py` | `_ssim` 🔒 | 72 | — | — |
| `app6/stage2/texture_structure.py` | `_ridge_probability` 🔒 | 84 | — | — |
| `app6/stage2/texture_structure.py` | `_skeleton` 🔒 | 111 | — | — |
| `app6/stage2/texture_structure.py` | `_skeleton_metrics` 🔒 | 124 | — | — |
| `app6/stage2/texture_structure.py` | `compare_zone_structure` | 146 | log: complete | — |
| `app6/stage2/uv_comparison.py` | `uv_geometry_pair` | 16 | log: in_progress | — |
| `app6/stage2b/engine.py` | `utc` | 32 | — | 🔄 |
| `app6/stage2b/engine.py` | `payload` | 44 | — | 🏭 |
| `app6/stage2b/engine.py` | `__init__` 🔒 | 53 | — | — |
| `app6/stage2b/engine.py` | `run` | 57 | — | 🚪 |
| `app6/stage3/engine.py` | `rows` | 19 | — | 📤 |
| `app6/stage3/engine.py` | `num` | 22 | — | 🔄 |
| `app6/stage3/engine.py` | `__init__` 🔒 | 26 | — | — |
| `app6/stage3/engine.py` | `run` | 27 | log: complete | — |
| `app6/stage3/engine.py` | `_html` 🔒 | 63 | — | — |
| `app6/stage3/skin/engine.py` | `__init__` 🔒 | 10 | — | — |
| `app6/stage3/skin/engine.py` | `run` | 12 | — | 🚪 |
| `app6/stage3/skin/morphing_contract.py` | `build_morph_contract` | 9 | — | 📜 |
| `app6/stage3/skin/report.py` | `validate_language` | 10 | — | 🚨 |
| `app6/stage3/skin/report.py` | `render_report` | 14 | — | 📤 |
| `app6/tests/test_chronology.py` | `test_short_interval_jump_gets_flagged` | 7 | — | — |
| `app6/tests/test_descriptors.py` | `rec` | 8 | — | — |
| `app6/tests/test_descriptors.py` | `test_all_metric_families_are_finite` | 11 | — | — |
| `app6/tests/test_geometry.py` | `test_rotation_is_orthonormal` | 12 | — | — |
| `app6/tests/test_geometry.py` | `test_yaw_roundtrip` | 17 | — | — |
| `app6/tests/test_geometry.py` | `test_normalization` | 22 | — | — |
| `app6/tests/test_geometry.py` | `test_packbits_roundtrip_non_multiple_of_eight` | 30 | — | — |
| `app6/tests/test_geometry_vs_evidence.py` | `_write_csv` 🔒 | 18 | — | — |
| `app6/tests/test_geometry_vs_evidence.py` | `test_missing_csv_raises` | 33 | — | — |
| `app6/tests/test_geometry_vs_evidence.py` | `test_soft_evidence_boosts_exclude_when_observed` | 37 | — | — |
| `app6/tests/test_geometry_vs_evidence.py` | `test_density_not_hard_clipped_to_100` | 57 | — | — |
| `app6/tests/test_geometry_vs_evidence.py` | `test_per_zone_geometry_without_evidence_flag` | 65 | — | — |
| `app6/tests/test_geometry_vs_evidence.py` | `test_preview_writes_usable_overlay` | 75 | — | — |
| `app6/tests/test_geometry_vs_evidence.py` | `test_pose_delta_gate` | 89 | — | — |
| `app6/tests/test_leads.py` | `test_archive_is_coverage_not_ground_truth` | 8 | — | — |
| `app6/tests/test_masks.py` | `test_channel_contract` | 15 | — | — |
| `app6/tests/test_masks.py` | `test_skin_plus_nose_and_feature_exclusion` | 19 | — | — |
| `app6/tests/test_masks.py` | `test_projection_failure_never_resizes` | 28 | — | — |
| `app6/tests/test_metric_registry.py` | `test_exactly_100_unique_canonical_names` | 13 | — | — |
| `app6/tests/test_metric_registry.py` | `test_missing_and_profile_disabled_are_explicit` | 19 | — | — |
| `app6/tests/test_metric_registry.py` | `test_all_registered_metrics_reach_evidence_channel` | 26 | — | — |
| `app6/tests/test_naming.py` | `test_plain_date_has_sequence_one` | 12 | — | — |
| `app6/tests/test_naming.py` | `test_explicit_sequence` | 17 | — | — |
| `app6/tests/test_naming.py` | `test_copy_suffix_in_parentheses` | 20 | — | — |
| `app6/tests/test_naming.py` | `test_copy_suffix_with_underscore` | 25 | — | — |
| `app6/tests/test_naming.py` | `test_invalid_names_rejected` | 29 | — | — |
| `app6/tests/test_naming.py` | `test_different_sha256_gives_different_photo_id` | 34 | — | — |
| `app6/tests/test_naming.py` | `test_no_sha256_falls_back_to_stem` | 44 | — | — |
| `app6/tests/test_naming.py` | `test_same_photo_id_for_different_copy_suffix_same_hash` | 50 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `reference` | 24 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_evidence_jump_is_not_persistent` | 29 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_chronology_date_missing_not_eff_one` | 36 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_alpha_l2_nan_when_missing` | 67 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_alpha_chronology_skips_nan` | 101 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_fdr_is_diagnostic_only` | 107 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_profile_support_gate` | 115 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_glcm_uses_masked_pairs_not_median_fill` | 120 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_texture_face_mask_fallback` | 133 | — | — |
| `app6/tests/test_p0_forensic_fixes.py` | `test_sidecar_loader_on_archive_sample` | 154 | — | — |
| `app6/tests/test_pose_correction.py` | `test_correction_is_orthonormal` | 24 | — | — |
| `app6/tests/test_pose_correction.py` | `test_correction_direction_yaw` | 41 | — | — |
| `app6/tests/test_pose_correction.py` | `test_correction_magnitude` | 61 | — | — |
| `app6/tests/test_pose_correction.py` | `test_roundtrip_correction` | 77 | — | — |
| `app6/tests/test_pose_correction.py` | `test_chronology_alignment_produces_finite` | 89 | — | — |
| `app6/tests/test_pose_correction.py` | `test_chronology_alignment_preserves_shape` | 103 | — | — |
| `app6/tests/test_pose_correction.py` | `test_all_pose_bins` | 125 | — | — |
| `app6/tests/test_pose_leakage.py` | `test_pose_correlated_metric_is_flagged` | 11 | — | — |
| `app6/tests/test_pose_leakage.py` | `test_small_sample_is_not_overinterpreted` | 20 | — | — |
| `app6/tests/test_private_hypothesis.py` | `test_lossless_import_and_current_retest_are_separated` | 15 | — | — |
| `app6/tests/test_robust_and_corroboration.py` | `test_trimmed_alignment_resists_local_outlier` | 13 | — | — |
| `app6/tests/test_robust_and_corroboration.py` | `test_independent_pose_support_is_secondary` | 26 | — | — |
| `app6/tests/test_skin_architecture.py` | `test_stage2_skin_never_imports_reconstruction` | 6 | — | — |
| `app6/tests/test_skin_architecture.py` | `test_uv_generator_has_single_public_render` | 15 | — | — |
| `app6/tests/test_skin_architecture.py` | `test_skin_pipeline_consumes_existing_face_mask` | 17 | — | — |
| `app6/tests/test_skin_architecture.py` | `test_skin_extractors_do_not_import_uv_module` | 19 | — | — |
| `app6/tests/test_skin_calibration.py` | `branch` | 10 | — | — |
| `app6/tests/test_skin_calibration.py` | `zone` | 13 | — | — |
| `app6/tests/test_skin_calibration.py` | `records` | 19 | — | — |
| `app6/tests/test_skin_calibration.py` | `test_calibration_builds_held_out_profile` | 31 | — | — |
| `app6/tests/test_skin_calibration.py` | `test_profile_is_applied_to_main_chronology` | 40 | — | — |
| `app6/tests/test_skin_dataset_gate.py` | `test_capture_event_leakage_is_rejected` | 7 | — | — |
| `app6/tests/test_skin_native_analysis.py` | `test_features` | 10 | — | — |
| `app6/tests/test_skin_native_analysis.py` | `test_mask_limits_wrinkles` | 12 | — | — |
| `app6/tests/test_skin_native_analysis.py` | `test_blur_reduces_effective_resolution` | 14 | — | — |
| `app6/tests/test_skin_native_analysis.py` | `test_pose_policy` | 16 | — | — |
| `app6/tests/test_skin_reviewed_fixes.py` | `test_calibration_never_splits_capture_group` | 10 | — | — |
| `app6/tests/test_skin_reviewed_fixes.py` | `test_temporal_model_keeps_pose_separate` | 19 | — | — |
| `app6/tests/test_skin_reviewed_fixes.py` | `test_wrinkle_paths_are_not_pca_resorted` | 30 | — | — |
| `app6/tests/test_skin_reviewed_fixes.py` | `test_ffhq_uses_safe_weights_loading` | 34 | — | — |
| `app6/tests/test_skin_run_contracts.py` | `test_config_merge_hash_is_deterministic` | 9 | — | — |
| `app6/tests/test_skin_run_contracts.py` | `test_unknown_schema_fails_loud` | 12 | — | — |
| `app6/tests/test_skin_run_contracts.py` | `test_run_freeze_prevents_mutation` | 15 | — | — |
| `app6/tests/test_skin_v3_foundation.py` | `test_background_barycentric_and_zbuffer` | 14 | — | — |
| `app6/tests/test_skin_v3_foundation.py` | `test_no_zero_missing_sentinel` | 16 | — | — |
| `app6/tests/test_skin_v3_foundation.py` | `test_npz_no_pickle` | 18 | — | — |
| `app6/tests/test_skin_v3_foundation.py` | `test_exif_orientation_is_explicit` | 22 | — | — |
| `app6/tests/test_skin_v3_foundation.py` | `test_atlas_fails_loud_on_wrong_topology` | 26 | — | — |
| `app6/tests/test_skin_v3_foundation.py` | `test_atlas_projection_parent_and_w14_bits` | 29 | — | — |
| `app6/tests/test_skin_v3_foundation.py` | `test_basic_texture_missing_is_nan_not_zero` | 31 | — | — |
| `app6/tests/test_skin_v3_foundation.py` | `test_tangent_frame_orthonormal` | 33 | — | — |
| `app6/tests/test_storage.py` | `test_failed_write_is_not_published` | 13 | — | — |
| `app6/tests/test_storage.py` | `test_success_is_published` | 23 | — | — |
| `app6/tests/test_storage.py` | `test_cleanup_incomplete` | 30 | — | — |
| `app6/tests/test_texture_image.py` | `test_lbp_glcm_frequency_features_are_reported` | 14 | — | — |
| `app6/tests/test_texture_structure.py` | `_fixture` 🔒 | 14 | — | — |
| `app6/tests/test_texture_structure.py` | `test_registered_structure_is_measured` | 22 | — | — |
| `app6/tests/test_texture_structure.py` | `test_excessive_shift_is_rejected` | 32 | — | — |
| `app6/tests/test_uv_module.py` | `setUp` | 6 | — | — |
| `app6/tests/test_uv_module.py` | `test_single_render_and_provenance` | 8 | — | — |
| `app6/tests/test_uv_module.py` | `test_resolution_guard` | 10 | — | — |
| `app6/tests/test_validator.py` | `_csv` 🔒 | 19 | — | — |
| `app6/tests/test_validator.py` | `_fixture` 🔒 | 27 | — | — |
| `app6/tests/test_validator.py` | `test_valid_fixture` | 65 | — | — |
| `app6/tests/test_validator.py` | `test_corrupt_visibility_is_rejected` | 70 | — | — |
| `app6/tests/test_wrinkle_zones.py` | `setUpClass` | 10 | — | — |
| `app6/tests/test_wrinkle_zones.py` | `test_layer_contract` | 11 | — | — |
| `app6/tests/test_wrinkle_zones.py` | `test_q_cores_are_nested` | 13 | — | — |
| `app6/tests/test_wrinkle_zones.py` | `test_branch_matching_is_spatial_orientation_and_length_aware` | 14 | — | — |
| `app6/tests/test_wrinkle_zones.py` | `test_chronology_separates_pose` | 16 | — | — |

## Как добавлять статус функции

1. В коде: `log_status("func_name", "need_testing", detail)` в начале тела функции
   (ПОСЛЕ docstring — иначе docstring теряется для help()/IDE).
2. Комментарием рядом с def по системе CONVENTIONS (✅/⚠️/❌/🔬/🗑️ + роли 🎯/🔗/…).
3. Обновить декларативный блок в `STATUS_AUDIT.py`.
4. Перегенерировать эту страницу (см. заголовок).
