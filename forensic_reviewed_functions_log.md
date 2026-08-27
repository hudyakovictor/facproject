# Лог проверенных функций — forensic-аудит DEEPUTIN app6

- Сгенерировано: 2026-08-25T20:21:12Z
- Официальный чеклист **не изменялся**
- Функций всего: **567**
- Просмотрено в этом чате: **567** (все package function IDs)
- Официально CLOSED_STRONG: **17** (только исходный PKG-001)
- Официально NOT_REVIEWED: **345**
- Официально CLOSED_BASIC: **203**
- BLOCKED_EXTERNAL: **2**
- Новых CLOSED_STRONG в этом чате: **0**
- Реальные фото / E2E: **0%**
- Терминология: **Skin-authenticity**

## Итерации чата
- Итерация 1: inventory + unittest baseline + PKG-001
- Итерация 2: PKG-002–004 Stage1 decode/geometry/masks
- Итерация 3: PKG-005–007 atlas/engine/validator
- Итерация 4: PKG-008–010 calibration
- Итерация 5: PKG-011–014 pairs/anchors/gates
- Итерация 6: PKG-015–016 descriptors/mesh/texture
- Итерация 7: PKG-017–019 stats/FDR/chronology
- Итерация 8: PKG-020–023 evidence/export/stage2b/stage3
- Итерация 9: PKG-024–030 API/jobs/security/integrity + H01–H11
- Итерация 10: security/archive/date provenance + ledger/matrix
- Итерация 11: Stage1 previously-unreviewed authenticity/_one
- Итерация 12: Stage1 remaining run/face_mask/naming/masks
- Итерация 13: Stage2 texture_image/structure/core leftovers
- Итерация 14: Stage2 motion/quality_gate/expression/primary/landmark
- Итерация 15: Stage2 chronology/descriptors/planner/calibration/mesh/FDR tails

## Пакеты
| Пакет | Офиц. статус | Функций | Глубина аудита | Итерация | Заметка |
|---|---|---:|---|---:|---|
| PKG-001 | CLOSED_STRONG | 17 | CLOSED_STRONG_OFFICIAL | 1 | единственный пакет со статусом CLOSED_STRONG в исходном чеклисте |
| PKG-002 | NOT_REVIEWED | 21 | DEEP_STATIC_SYNTHETIC | 2 | decode/fields/ICC/nonfinite |
| PKG-003 | NOT_REVIEWED | 14 | DEEP_STATIC_SYNTHETIC | 2 | geometry/naming/reconstruction |
| PKG-004 | NOT_REVIEWED | 22 | DEEP_STATIC_SYNTHETIC | 2 | masks/assets/authenticity extract |
| PKG-005 | NOT_REVIEWED | 22 | DEEP_STATIC_SYNTHETIC | 3 | skin-zone atlas v1/v4, NOT WIRED |
| PKG-006 | NOT_REVIEWED | 23 | DEEP_STATIC | 3 | stale quality_summary |
| PKG-007 | NOT_REVIEWED | 22 | DEEP_STATIC | 3 | complete without atlas |
| PKG-008 | NOT_REVIEWED | 19 | DEEP_STATIC_SYNTHETIC | 4 | personal vs population |
| PKG-009 | NOT_REVIEWED | 19 | DEEP_STATIC_SYNTHETIC | 4 | health/match/reuse |
| PKG-010 | NOT_REVIEWED | 19 | DEEP_STATIC_SYNTHETIC | 4 | mesh cal / LOPO / tolerance |
| PKG-011 | NOT_REVIEWED | 16 | DEEP_STATIC_SYNTHETIC | 5 | pairs/anchors |
| PKG-012 | NOT_REVIEWED | 16 | DEEP_STATIC_SYNTHETIC | 5 | alignment |
| PKG-013 | NOT_REVIEWED | 16 | DEEP_STATIC_SYNTHETIC | 5 | gates ignored |
| PKG-014 | NOT_REVIEWED | 16 | DEEP_STATIC_SYNTHETIC | 5 | planner/first-frame |
| PKG-015 | NOT_REVIEWED | 19 | DEEP_STATIC_SYNTHETIC | 6 | descriptors |
| PKG-016 | NOT_REVIEWED | 19 | DEEP_STATIC_SYNTHETIC | 6 | mesh/texture |
| PKG-017 | NOT_REVIEWED | 15 | DEEP_STATIC_SYNTHETIC | 7 | ESS/bootstrap |
| PKG-018 | NOT_REVIEWED | 15 | DEEP_STATIC_SYNTHETIC | 7 | FDR diagnostic-only |
| PKG-019 | NOT_REVIEWED | 23 | DEEP_STATIC_SYNTHETIC | 7 | temporal branch inverted |
| PKG-020 | NOT_REVIEWED | 21 | DEEP_STATIC_SYNTHETIC | 8 | evidence/leads/private hypothesis |
| PKG-021 | NOT_REVIEWED | 25 | DEEP_STATIC_SYNTHETIC | 8 | export/manifest/snapshot |
| PKG-022 | NOT_REVIEWED | 13 | DEEP_STATIC_SYNTHETIC | 8 | Stage2B/report API |
| PKG-023 | NOT_REVIEWED | 13 | DEEP_STATIC_SYNTHETIC | 8 | Stage3/public safety |
| PKG-024 | NOT_REVIEWED | 15 | DEEP_STATIC_SYNTHETIC | 9 | BFM/jobs |
| PKG-025 | NOT_REVIEWED | 14 | DEEP_STATIC_SYNTHETIC | 9 | settings/runners |
| PKG-026 | NOT_REVIEWED | 25 | DEEP_STATIC_SYNTHETIC | 9 | timeline/pair metrics |
| PKG-027 | NOT_REVIEWED | 22 | DEEP_STATIC_SYNTHETIC | 9 | API storage/compare |
| PKG-028 | NOT_REVIEWED | 22 | DEEP_STATIC_SYNTHETIC | 9 | API endpoints |
| PKG-029 | NOT_REVIEWED | 22 | DEEP_STATIC_SYNTHETIC | 9 | preflight/checkpoint pickle |
| PKG-030 | NOT_REVIEWED | 22 | DEEP_STATIC_SYNTHETIC | 9 | integrity/validation/loaders |

## Handoffs
- H01 `main photo→Stage1` offic=CLOSED_BASIC proposed=CLOSED_BASIC_ONLY
- H02 `Stage1 per-photo→timeline/index` offic=CLOSED_BASIC proposed=CLOSED_BASIC_ONLY
- H03 `Stage1→Stage2 loader` offic=CLOSED_BASIC proposed=CLOSED_BASIC_ONLY
- H04 `calibration→null model` offic=CLOSED_BASIC proposed=CLOSED_BASIC_ONLY
- H05 `pair planner→comparison` offic=CLOSED_BASIC proposed=CLOSED_BASIC_ONLY
- H06 `gates→metrics` offic=CLOSED_BASIC proposed=OPEN_INVARIANT_VIOLATION
- H07 `metrics→FDR` offic=CLOSED_BASIC proposed=OPEN_INVARIANT_VIOLATION
- H08 `FDR/chronology→candidate states/evidence` offic=CLOSED_BASIC proposed=OPEN_INVARIANT_VIOLATION
- H09 `Stage2→Stage2B` offic=CLOSED_BASIC proposed=OPEN_INVARIANT_VIOLATION
- H10 `Stage2→Stage3` offic=CLOSED_BASIC proposed=OPEN_INVARIANT_VIOLATION
- H11 `Stage3→API/UI` offic=CLOSED_BASIC proposed=OPEN_INVARIANT_VIOLATION

## Подтверждённые дефекты (привязка к function id)
- `app6/stage2/evidence.py::evidence_state` — quality_limited does not downgrade within_noise; unknown->elevated_uncertain
- `app6/stage2/evidence.py::packet_from_pair` — None IDs become string None
- `app6/stage2/evidence.py::alternative_reasons` — TypeError on None comparisons
- `app6/stage2/private_hypothesis.py::_retest_record` — date-only retest match
- `app6/stage2/run_manifest.py::build_manifest` — ready=true with empty hashes
- `app6/stage2/snapshot_canonical.py::canonical_snapshot` — NaN equals missing
- `app6/stage2/snapshot_canonical.py::snapshot_category` — substring z misclassifies normalized_score
- `app6/stage2b/engine.py::Stage2BConfig.__post_init__` — parent output rmtree can delete source
- `app6/stage3/engine.py::Stage3Config.__post_init__` — parent output rmtree can delete source
- `app6/stage3/engine.py::public_pair_projection` — missing evidence_state -> elevated_uncertain
- `app6/api/report.py::report_available` — invalid Stage3 treated available
- `app6/api/server.py::delete_photo` — photo_id path traversal
- `app6/api/photo_fields.py::load_info` — photo_id path traversal
- `app6/api/photo_fields.py::fields_from_info` — valid 0 overwritten by or
- `app6/api/bfm_topology.py::_convert_npy_to_safe_npz` — trust-on-first-use pickle
- `app6/api/settings.py::SettingsPayload.guard` — forged calibrated mode
- `app6/api/research_timeline.py::build_research_timeline` — order-dependent fuzzy; siliconeProb leftover
- `app6/api/server.py::_stage2_root` — canonical dir bypasses complete-manifest
- `app6/stage2/engine.py::_read_checkpoint` — pickle.load before schema
- `app6/stage2/engine.py::_record_qc` — bool("False") is True
- `app6/stage2/engine.py::Stage2Engine.run` — temporal branch inverted
- `app6/stage2/date_provenance.py::resolve_date` — EXIF preferred over filename
- `app6/stage2/integrity.py::compute_dataset_hash` — ignores pose/angles when source_digest present
- `app6/scripts/fetch_external_assets.py::sha` — blake2b-16 vs required 64 hex
- `app6/schemas/__init__.py::schema_path` — directory traversal
- `app6/stage1/engine.py::Stage1Engine._one` — stale quality_summary; heuristic confidence
- `app6/stage1/engine.py::Stage1Engine.run` — near-dups not skipped; complete_with_errors
- `app6/stage1/assets.py::save_face_mask` — float 0/1 mask -> alpha 1; kills Skin-authenticity
- `app6/stage1/assets.py::technical_quality` — missing mask -> 0.0 not None
- `app6/stage1/authenticity/extract.py::extract_quality_metrics` — empty mask IndexError
- `app6/stage1/authenticity/extract.py::_authenticity_status` — NaN -> low_authenticity
- `app6/stage1/authenticity/extract.py::_quality_score` — {} -> (0.0, low, False)
- `app6/stage2/texture_image.py::texture_pair_deltas` — unusable zones inflate pair maxima; no pose norm
- `app6/stage2/core.py::calibrated_score` — MAD=0 -> z=1e8 elevated
- `app6/stage2/core.py::robust_reference` — empty -> zeros
- `app6/stage2/primary_zones.py::pair_expression_active` — string False -> True
- `app6/stage2/chronology.py::_quality_exclusion_reason` — string False -> excluded
- `app6/stage2/pair_planner.py::plan_pairs` — undated temporal pairs; first-frame baseline
- `app6/stage2/calibration.py::CalibrationModel.reference` — missing ref -> zeros; no stratum fallback
- `app6/stage2/calibration.py::CalibrationModel._nearest` — max_reuse not hard cap
- `app6/stage2/mesh_dense.py::_load_mesh` — missing vis = all-true MESH_COUNT; missing normals=0
- `app6/stage2/multiple_testing.py::apply_pair_fdr` — diagnostic-only; photo_count//2
- `app6/stage2/multiple_testing.py::apply_zone_fdr` — zone scalar z treated as single z
- `app6/stage2/temporal_axis.py::require_temporal_axis` — None when axis valid; engine inverted
- `app6/stage1/skin_zone_atlas.py::project_atlas_to_photo` — NOT WIRED; priority inverted
- `app6/run_stage1.py::main` — always exit 0
- `app6/api/jobs.py::JobManager.cancel` — ack True, runner may complete

## Все функции

| function_id | official | proposed | package | iter | depth | defect |
|---|---|---|---|---:|---|---|
| `app6/__init__.py::__getattr__` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/bfm_topology.py::BFMModel.compute_shape` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/bfm_topology.py::_convert_npy_to_safe_npz` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC | trust-on-first-use pickle |
| `app6/api/bfm_topology.py::_extract_face_model_npy` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/bfm_topology.py::_load_raw_arrays` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/bfm_topology.py::is_bfm_available` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/bfm_topology.py::load_bfm_model` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/calibration.py::_bucket_confidence` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/calibration.py::find_matching_calibration_frames` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/calibration.py::find_matching_calibration_frames._distance` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/calibration.py::load_calibration_health` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/compare.py::compare_records` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/compare.py::full_mesh_compare` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::Job.to_dict` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::JobManager.__init__` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::JobManager.cancel` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC | ack True, runner may complete |
| `app6/api/jobs.py::JobManager.get` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::JobManager.list_jobs` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::JobManager.submit` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::JobManager.submit._run` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::_check_stage1_dependencies` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::_utc` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-024 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::make_extract_runner` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::make_extract_runner._extract_runner` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::make_recompute_metrics_runner` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/jobs.py::make_recompute_metrics_runner._recompute_runner` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/key_catalog.py::categorize_manifest` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/key_catalog.py::categorize_pair_columns` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/key_catalog.py::categorize_stage1_info` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/key_catalog.py::category_for` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/key_catalog.py::coerce` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/noise_calibration.py::angle_delta_for` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/noise_calibration.py::apply_noise_subtraction` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/noise_calibration.py::build_noise_index` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/noise_calibration.py::noise_coverage_report` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/noise_calibration.py::resolve_tolerance` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/pair_metrics.py::_count_leaves` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/pair_metrics.py::_read_pairs` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/pair_metrics.py::find_pair_row` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/pair_metrics.py::list_stage2_artifacts` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/pair_metrics.py::load_pair_metrics` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/pair_metrics.py::load_run_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/pair_metrics.py::load_stage1_info` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/pair_metrics.py::load_stage2_artifact` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/photo_fields.py::_bool` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/photo_fields.py::_num` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/photo_fields.py::fields_from_info` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC | valid 0 overwritten by or |
| `app6/api/photo_fields.py::load_info` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC | photo_id path traversal |
| `app6/api/photo_fields.py::merge_photo_fields` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/photo_fields.py::scan_stage1_records` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/report.py::_read_report` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/report.py::_read_validation` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/report.py::_section_size` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/report.py::load_report_section` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/report.py::load_report_summary` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/report.py::report_available` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC | invalid Stage3 treated available |
| `app6/api/research_timeline.py::_date_to_ms` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/research_timeline.py::_num` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/research_timeline.py::build_research_timeline` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC | order-dependent fuzzy; siliconeProb leftover |
| `app6/api/research_timeline.py::build_research_timeline._ensure_photo` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/research_timeline.py::build_research_timeline._optional_num` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/review.py::append_review` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_cached_main_records` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_calibration_records` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_calibration_root` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_main_record` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_main_records` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_manifest_sort_key` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_path_with_file` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_require_removable_output` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_require_stage1` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_require_stage2` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_require_stage3` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_safe_record_file` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_stage1_root` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_stage2_manifest` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_stage2_root` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC | canonical dir bypasses complete-manifest |
| `app6/api/server.py::_stage3_root` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_storage_root` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_upload_image_decodes` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_upload_signature_matches` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::_uploads_root` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::calibration_health` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::calibration_match` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::calibration_noise_model` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::calibration_subtract_noise` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::cancel_job` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::clear_data` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::compare_pair` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::compare_pair_full_mesh` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::compare_with_upload` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-027 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::create_review` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::delete_photo` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC | photo_id path traversal |
| `app6/api/server.py::get_job` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_pair_metrics` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_photo` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_photo_artifact` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_photo_full_mesh` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_photo_image` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_photo_info_keys` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_photo_landmarks` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_photo_skin_zones` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_report_section` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_report_section_artifact` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_report_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_run_artifact` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_run_key_alias` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_run_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_settings` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_timeline` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::get_ui_artifact` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::health` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::list_jobs` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::list_photos` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::put_settings` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-028 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::reset_settings` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::submit_job` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::system_health` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::unhandled_exception_handler` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::upload_photo` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/server.py::zones_catalog` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/settings.py::SettingsPayload.guard` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC | forged calibrated mode |
| `app6/api/settings.py::_deep_merge` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/settings.py::_settings_path` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/settings.py::load_settings` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/settings.py::save_settings` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-025 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/skin_zones.py::_float_or_none` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/skin_zones.py::_load_atlas` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/skin_zones.py::_read_json` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/skin_zones.py::load_skin_zone_report` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/skin_zones.py::zone_catalog` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/stage1_timeline.py::_date_to_ms` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/stage1_timeline.py::_float` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/stage1_timeline.py::build_stage1_inventory` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/system_health.py::_gpu_status` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/system_health.py::_optional_dependency_status` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/system_health.py::_resource_usage` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/system_health.py::build_system_health` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/ui_fields.py::bone_score` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/ui_fields.py::era_for` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/ui_fields.py::normalized_t` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/ui_fields.py::principal_coords` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/api/ui_fields.py::validate_ui_row` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-026 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/archive_adapter.py::group_by_person_pose` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/archive_adapter.py::load_archive_records` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/archive_adapter.py::safe_extract_archive` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/archive_adapter.py::with_synthetic_dates` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/build_calibration_index.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/calibration_index.py::_identity` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/calibration_index.py::_relative` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/calibration_index.py::build_calibration_index` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-008 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_calibration.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_calibration_re_extract.py::assign_synthetic_dates` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_calibration_re_extract.py::create_temp_symlinks` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_calibration_re_extract.py::load_index` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_calibration_re_extract.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_calibration_re_extract.py::reorganize_output` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_calibration_re_extract.py::run_stage1` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 3 | DEEP_STATIC |  |
| `app6/run_preflight.py::audit_calibration_index` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_preflight.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_scenario_planner.py::build_plan` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_scenario_planner.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_stage1.py::build_parser` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 3 | DEEP_STATIC |  |
| `app6/run_stage1.py::main` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-006 | 3 | DEEP_STATIC | always exit 0 |
| `app6/run_stage2.py::build_parser` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_stage2.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_stage2b.py::build_parser` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_stage2b.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/run_stage3.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/schemas/__init__.py::schema_path` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC | directory traversal |
| `app6/scripts/fetch_external_assets.py::main` | BLOCKED_EXTERNAL | BLOCKED_EXTERNAL | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/scripts/fetch_external_assets.py::sha` | BLOCKED_EXTERNAL | OPEN_DEFECT_DO_NOT_CLOSE | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC | blake2b-16 vs required 64 hex |
| `app6/stage1/__init__.py::__getattr__` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/assets.py::_bbox` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/assets.py::_letterbox` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/assets.py::_write_obj` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/assets.py::save_face_mask` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC | float 0/1 mask -> alpha 1; kills Skin-authenticity |
| `app6/stage1/assets.py::save_image_assets` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/assets.py::save_semantic_channels` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/assets.py::save_uv_and_mesh` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/assets.py::technical_quality` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC | missing mask -> 0.0 not None |
| `app6/stage1/authenticity/albedo_analysis.py::_fallback` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/albedo_analysis.py::_rgb_to_hsv` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/albedo_analysis.py::albedo_spectral_analysis` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/extract.py::_authenticity_status` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-002 | 10 | DEEP_STATIC_SYNTHETIC | NaN -> low_authenticity |
| `app6/stage1/authenticity/extract.py::_load_face_mask_rgba` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/extract.py::_load_json` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/extract.py::_panel_score` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/extract.py::_quality_score` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-002 | 10 | DEEP_STATIC_SYNTHETIC | {} -> (0.0, low, False) |
| `app6/stage1/authenticity/extract.py::build_texture_package` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/extract.py::extract_quality_metrics` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-002 | 10 | DEEP_STATIC_SYNTHETIC | empty mask IndexError |
| `app6/stage1/authenticity/fft_analysis.py::_fallback` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/fft_analysis.py::fft_regularity_analysis` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/lbp_analysis.py::_fallback` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/lbp_analysis.py::_manual_lbp` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/lbp_analysis.py::lbp_complexity_analysis` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/v12_features.py::_entropy` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/v12_features.py::_load_recipe` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/v12_features.py::_pct` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/v12_features.py::_std` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/v12_features.py::derive_v12_metrics` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/v12_features.py::extract_v12_bases` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/v12_features.py::extract_v12_bases.roi` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/authenticity/v12_features.py::extract_v12_panel` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/config.py::Stage1Config.__post_init__` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 3 | DEEP_STATIC |  |
| `app6/stage1/config.py::Stage1Config.extraction_payload` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 3 | DEEP_STATIC |  |
| `app6/stage1/config.py::Stage1Config.public_dict` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 3 | DEEP_STATIC |  |
| `app6/stage1/engine.py::Stage1Engine.__init__` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-006 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/engine.py::Stage1Engine._index_row` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/engine.py::Stage1Engine._one` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC | stale quality_summary; heuristic confidence |
| `app6/stage1/engine.py::Stage1Engine._one._compute_landmark_confidence` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/engine.py::Stage1Engine._photo_name` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/engine.py::Stage1Engine._relative` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/engine.py::Stage1Engine.run` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC | near-dups not skipped; complete_with_errors |
| `app6/stage1/engine.py::_landmark_rows` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/engine.py::_landmark_rows_2d` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/engine.py::_utc` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/engine.py::discover_input_photos` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 10 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::classify_pose` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::compute_chronology_alignment` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::full_pose_correction_matrix` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::nearest_canonical_yaw` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::normalize_mesh` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::normalize_mesh_landmark_anchored` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::pack_mask` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::reprojection_stats` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::row_rotation_matrix` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::to_original_image` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/geometry.py::unpack_mask` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/input_provenance.py::_parse_exif_date` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage1/input_provenance.py::build_date_provenance` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage1/input_provenance.py::decode_oriented` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage1/masks.py::build_mask_bundle` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/naming.py::make_nonchronological_photo_name` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/naming.py::make_photo_id` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/naming.py::parse_photo_name` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-003 | 11 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/provenance_ledger.py::hamming_distance` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage1/provenance_ledger.py::load_provenance_sidecar` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage1/provenance_ledger.py::perceptual_dhash` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage1/reconstruction.py::ReconstructionBundle.landmark_arrays` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/reconstruction.py::ReconstructionEngine.__init__` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/reconstruction.py::ReconstructionEngine._check_assets` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/reconstruction.py::ReconstructionEngine._np` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/reconstruction.py::ReconstructionEngine._resolve_device` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/reconstruction.py::ReconstructionEngine.cleanup` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/reconstruction.py::ReconstructionEngine.process` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/reconstruction.py::ReconstructionEngine.process.capture_alpha` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/reconstruction.py::ReconstructionEngine.process.renderer_forward` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::_boundary_safe_mask` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::_pose_weight` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::_render_overlay` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::_tri_px` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-004 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::_uv_to_original` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::_zone_colors` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::build_atlas_json` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::build_pose_policy` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::build_triangle_zone_map` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::generate_canonical_atlas` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::load_canonical_atlas` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::project_atlas_to_photo` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC | NOT WIRED; priority inverted |
| `app6/stage1/skin_zone_atlas.py::render_atlas_png` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::write_pose_policy_csv` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas.py::zone_names` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::_boundary_safe_mask` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::_uv_to_original` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::_zone_colors` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::build_primary_triangle_zone` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::export_contract` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::load_canonical_atlas` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::points_in_polygon` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::project_atlas_to_photo` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::triangle_centroids_uv` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::validate_definitions` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/skin_zone_atlas_final.py::zone_role_for_pose` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-005 | 3 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/status_logger.py::_update_audit_status` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/status_logger.py::close_function` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/status_logger.py::log_blocker` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/status_logger.py::log_status` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/status_logger.py::print_status_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/storage.py::atomic_photo_directory` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/storage.py::clean_incomplete` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/storage.py::write_failure` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/utils.py::atomic_json` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/utils.py::digest_file` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/utils.py::digest_json` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/utils.py::digest_paths` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/utils.py::json_ready` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/utils.py::runtime_versions` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/utils.py::runtime_versions.version` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/utils.py::write_csv` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-002 | 2 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage1/validator.py::_csv_check` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/validator.py::_resolve_topology` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/validator.py::is_resumable` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage1/validator.py::validate_photo` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-007 | 3 | DEEP_STATIC |  |
| `app6/stage2/__init__.py::__getattr__` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/alpha_chronology.py::apply_alpha_chronology` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/analysis_policy.py::_atlas_dir` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/analysis_policy.py::load_pose_gate` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/analysis_policy.py::pose_gap` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/anchor_policy.py::per_bin_anchor_mask` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/anchor_policy.py::stable_anchor_indices` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/anchor_policy.py::stable_anchor_mask` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/angle_noise.py::angle_delta` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/angle_noise.py::build_calibration_pair_index` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/angle_noise.py::find_matching_calibration_pair` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/angle_noise.py::subtract_angle_noise` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/baseline_return.py::_load_vectors` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/baseline_return.py::_reversal_stats` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/baseline_return.py::apply_baseline_return` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel.__init__` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel._build_references` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel._collect_reference_values` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel._nearest` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-009 | 15 | DEEP_STATIC_SYNTHETIC | max_reuse not hard cap |
| `app6/stage2/calibration.py::CalibrationModel._nearest.score` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel._pose_distance` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel.consistency_check` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel.has_stratified_references` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-009 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel.matched_null` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel.reference` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC | missing ref -> zeros; no stratum fallback |
| `app6/stage2/calibration.py::CalibrationModel.references_excluding_dataset` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration.py::CalibrationModel.reuse_report` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/calibration_sensitivity.py::leave_one_dataset_sensitivity` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/chronology.py::_days` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/chronology.py::_mark_chronology_excluded` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/chronology.py::_quality_exclusion_reason` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-019 | 14 | DEEP_STATIC_SYNTHETIC | string False -> excluded |
| `app6/stage2/chronology.py::_robust` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/chronology.py::apply_biological_rate_flags` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/chronology.py::apply_chronology_rate_flags` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/chronology.py::apply_cumulative_drift_flags` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::Record.__post_init__` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::_load_per_bin_artifacts` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::_rigid_align` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::_stats` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::build_coordinate_zone_map` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::calibrated_score` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC | MAD=0 -> z=1e8 elevated |
| `app6/stage2/core.py::compare_landmarks` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::compare_landmarks._alpha_l2` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::measured_alignment_quality` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::robust_reference` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC | empty -> zeros |
| `app6/stage2/core.py::robust_rigid_align` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/core.py::zone_weighted_score` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/corroboration.py::_date` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/corroboration.py::aggregate_events` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/corroboration.py::apply_cross_bin_corroboration` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/date_provenance.py::_delta_days` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage2/date_provenance.py::parse_filename_date` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage2/date_provenance.py::resolve_date` | CLOSED_STRONG | OPEN_DEFECT_DO_NOT_CLOSE | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL | EXIF preferred over filename |
| `app6/stage2/descriptors.py::DescriptorNoiseModel._build` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/descriptors.py::DescriptorNoiseModel._pd` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/descriptors.py::DescriptorNoiseModel.score` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/descriptors.py::_neighbors` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/descriptors.py::_one` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/descriptors.py::descriptor_pose_compatible` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/descriptors.py::local_pair_descriptors` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/engine.py::Stage2Config.__post_init__` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/engine.py::Stage2Config.payload` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/engine.py::Stage2Engine._persistence` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/engine.py::Stage2Engine.run` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC | temporal branch inverted |
| `app6/stage2/engine.py::_atomic_npz` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/engine.py::_pair_qc_decision` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/engine.py::_read_checkpoint` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-029 | 9 | DEEP_STATIC_SYNTHETIC | pickle.load before schema |
| `app6/stage2/engine.py::_record_qc` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC | bool("False") is True |
| `app6/stage2/engine.py::_write_checkpoint` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/engine.py::utc` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/evidence.py::EvidencePacket.to_dict` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/evidence.py::alternative_reasons` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC | TypeError on None comparisons |
| `app6/stage2/evidence.py::evidence_state` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC | quality_limited does not downgrade within_noise; unknown->elevated_uncertain |
| `app6/stage2/evidence.py::is_reportable_change` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/evidence.py::packet_from_pair` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC | None IDs become string None |
| `app6/stage2/export.py::stable_fieldnames` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/export.py::validate_csv_headers` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/expression_pair_gate.py::expression_gate` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/expression_qc.py::_interocular` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/expression_qc.py::detect_expression` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/expression_qc.py::exclude_mimic_zones` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/expression_qc.py::expression_magnitude` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/fdr_control.py::apply_fdr` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/fdr_control.py::benjamini_hochberg` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/generate_mesh_zones.py::generate_zones` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/generate_mesh_zones.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/golden_fixture.py::_deltat_days` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/golden_fixture.py::_scenario_metrics` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/golden_fixture.py::build_golden_snapshot_data` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/golden_fixture.py::golden_canonical` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/golden_fixture.py::write_golden_snapshot` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/hard_negative.py::evaluate` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/integrity.py::compute_code_hash` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/integrity.py::compute_dataset_hash` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC | ignores pose/angles when source_digest present |
| `app6/stage2/integrity.py::verify_integrity_hashes` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/irreversible_return.py::_date_bounds` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/irreversible_return.py::_parse_date` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/irreversible_return.py::_similarity` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/irreversible_return.py::detect_irreversible_return` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/irreversible_return.py::summarize_returns` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/landmark_policy.py::normalized_weights` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/landmark_policy.py::row_all_nan` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/landmark_policy.py::sanitize_utility` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/landmark_policy.py::stable_subset` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/landmark_policy.py::subset_for_bin` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/leads.py::_date` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/leads.py::_load` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/leads.py::load_leads` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/leads.py::load_leads.add` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/leads.py::pair_leads` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/legacy_bridge.py::bridge_coverage` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/legacy_bridge.py::build_retest_target` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/legacy_bridge.py::normalize_photo_id` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/legacy_bridge.py::normalize_pose_bin` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::_missing_alpha` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::_read_landmark_csv` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::_required_npz_array` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::_rows` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::calibration_bin_coverage` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::load_calibration` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::load_calibration_from_sidecar` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::load_legacy_calibration_archive` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/loaders.py::load_main` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_calibration.py::MeshNoiseModel.__init__` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_calibration.py::MeshNoiseModel._build` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_calibration.py::MeshNoiseModel.score` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_calibration.py::MeshNoiseModel.to_json` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_calibration.py::_mesh_metrics` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_calibration.py::_pose_distance` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_dense.py::_load_mesh` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-015 | 15 | DEEP_STATIC_SYNTHETIC | missing vis = all-true MESH_COUNT; missing normals=0 |
| `app6/stage2/mesh_dense.py::_normalize` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_dense.py::_shape_descriptor` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_dense.py::_subsample` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_dense.py::_zone_labels` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_dense.py::dense_mesh_pair` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/mesh_dense.py::load_anatomical_zones` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/metric_registry.py::_usable` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/metric_registry.py::build_metric_catalog` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/metric_registry.py::evidence_metric_channel` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-017 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/metric_registry.py::metric_channel` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/metric_registry.py::validate_registry` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/motion.py::PointNoiseModel.__init__` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/motion.py::PointNoiseModel._build` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/motion.py::PointNoiseModel._coherence` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/motion.py::PointNoiseModel._pose_distance` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/motion.py::PointNoiseModel.landmark_stability_score` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/motion.py::PointNoiseModel.score` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/motion.py::aligned_point_motion` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/motion.py::pose_motion_support` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/multiple_testing.py::_bh_qvalues` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/multiple_testing.py::_p_from_p95_z` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/multiple_testing.py::_p_from_z` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-019 | 15 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/multiple_testing.py::apply_pair_fdr` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-019 | 15 | DEEP_STATIC_SYNTHETIC | diagnostic-only; photo_count//2 |
| `app6/stage2/multiple_testing.py::apply_zone_fdr` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-019 | 15 | DEEP_STATIC_SYNTHETIC | zone scalar z treated as single z |
| `app6/stage2/pair_planner.py::plan_pairs` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-011 | 14 | DEEP_STATIC_SYNTHETIC | undated temporal pairs; first-frame baseline |
| `app6/stage2/pair_planner.py::plan_pairs.add` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pair_row_patch.py::enrich_pair_row` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-011 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_leakage.py::_finite_pairs` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_leakage.py::pose_leakage_diagnostic` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_policy.py::_atlas_dir` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_policy.py::applicable_zones` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_policy.py::assert_canonical_yaw` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_policy.py::load_pose_policy` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_policy.py::policy_summary` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_policy.py::profile_sub_bin` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_policy.py::yaw_for_bin` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/pose_policy.py::zone_applicability` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_num` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_artifact_index` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_degraded_modules` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_gate_report` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_manual_review_queue` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_mesh_shape_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_public_safety` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_stage3_input_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_status_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::_write_texture_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 6 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/postprocess_reports.py::write_postprocess_reports` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/primary_zones.py::_load_landmark_vertex_indices` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/primary_zones.py::_vertex_to_zone` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/primary_zones.py::build_anatomical_landmark_zone_map` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/primary_zones.py::expression_zone_policy` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/primary_zones.py::pair_expression_active` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-013 | 13 | DEEP_STATIC_SYNTHETIC | string False -> True |
| `app6/stage2/primary_zones.py::primary_zone_aggregate` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/private_hypothesis.py::PrivateHypothesisEngine.run` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/private_hypothesis.py::_candidate_keys` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/private_hypothesis.py::_candidate_keys.walk` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/private_hypothesis.py::_digest` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/private_hypothesis.py::_extract_records` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/private_hypothesis.py::_read_csv` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/private_hypothesis.py::_retest_record` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC | date-only retest match |
| `app6/stage2/private_hypothesis.py::_utc` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-020 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/quality_gate.py::compensate_quality_disparity` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/quality_gate.py::quality_gate_summary` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/quality_gate.py::resolution_quality_gate` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/quality_gate.py::resolution_ratio` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 13 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/quality_integration.py::load_quality_zone_summary` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/quality_integration.py::pair_quality_zone_overlap` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/quality_stratification.py::_stratum` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/quality_stratification.py::quality_gate` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-014 | 14 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::balanced_person_threshold` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::balanced_reference` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::classify_sequence` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::cluster_bootstrap_ci` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::effective_sample_size` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::ensure_same_pose` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::kabsch_rmse` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::noise_adjusted_threshold` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::normalize_points` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::robust_pair_distance` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::robust_threshold` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::validate_landmarks` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/robustness.py::validate_serialized_record` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-018 | 7 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/run_manifest.py::_sha256` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/run_manifest.py::artifact_hashes` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/run_manifest.py::build_manifest` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC | ready=true with empty hashes |
| `app6/stage2/same_day_gate.py::_robust_scale` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage2/same_day_gate.py::check_same_day_conflict` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage2/same_day_gate.py::same_day_summary` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage2/snapshot_canonical.py::_near` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/snapshot_canonical.py::canonical_json` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/snapshot_canonical.py::canonical_snapshot` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC | NaN equals missing |
| `app6/stage2/snapshot_canonical.py::compare_snapshots` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/snapshot_canonical.py::compare_snapshots._walk` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/snapshot_canonical.py::read_snapshot` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/snapshot_canonical.py::snapshot_category` | CLOSED_BASIC | OPEN_DEFECT_DO_NOT_CLOSE | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC | substring z misclassifies normalized_score |
| `app6/stage2/snapshot_canonical.py::snapshot_file_roundtrip_is_deterministic` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/snapshot_canonical.py::write_snapshot` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/space_selection.py::assert_analysis_space` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/space_selection.py::space_manifest` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-012 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/technical_summary.py::build_technical_summary` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-021 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/temporal_axis.py::temporal_status` | CLOSED_STRONG | CLOSED_STRONG | PKG-001 | 1 | CLOSED_STRONG_OFFICIAL |  |
| `app6/stage2/texture_image.py::_entropy` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_erode_roi` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_frequency_ratio` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_gabor_profile` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-015 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_glcm_stats` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_image_path` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_lbp_histogram` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_load_face_mask_texture` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_load_texture` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_patch_profile` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_stats` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::_unpack_mask` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::pose_normalize_texture` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_image.py::texture_pair_deltas` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC | unusable zones inflate pair maxima; no pose norm |
| `app6/stage2/texture_pair.py::summarize_texture_pairs` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 6 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_structure.py::_patch` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_structure.py::_ridge_probability` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_structure.py::_skeleton` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_structure.py::_skeleton_metrics` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_structure.py::_ssim` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_structure.py::compare_zone_structure` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/texture_structure.py::register_patches` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 12 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/uv_comparison.py::compare_packages` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-016 | 6 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/validation.py::_as_bool` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/validation.py::validate_analysis_contract` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-030 | 9 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/visibility_gate.py::bin_visibility_prior` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2/visibility_gate.py::pair_visibility` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-013 | 5 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2b/engine.py::Stage2BConfig.__post_init__` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC | parent output rmtree can delete source |
| `app6/stage2b/engine.py::Stage2BConfig.payload` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2b/engine.py::Stage2BEngine.run` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage2b/engine.py::utc` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-022 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage3/engine.py::Stage3Config.__post_init__` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC | parent output rmtree can delete source |
| `app6/stage3/engine.py::Stage3Engine._html` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage3/engine.py::Stage3Engine.run` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage3/engine.py::num` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/stage3/engine.py::public_pair_projection` | NOT_REVIEWED | OPEN_DEFECT_DO_NOT_CLOSE | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC | missing evidence_state -> elevated_uncertain |
| `app6/stage3/engine.py::rows` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-023 | 8 | DEEP_STATIC_SYNTHETIC |  |
| `app6/tools/calibration_artifact_manifest.py::build` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/tools/calibration_artifact_manifest.py::digest` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/tools/calibration_artifact_manifest.py::main` | NOT_REVIEWED | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
| `app6/tools/calibration_artifact_manifest.py::verify` | CLOSED_BASIC | NOT_CLOSED_DEFECTS_OR_INCOMPLETE_CRITERIA | PKG-010 | 4 | DEEP_STATIC_SYNTHETIC |  |
