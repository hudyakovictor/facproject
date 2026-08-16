# DEEPUTIN UI v5 — 70 КЛЮЧЕВЫХ АНАЛИЗОВ КОДА И ПОДРОБНЫЙ ПЛАН РЕАЛИЗАЦИИ

**Дата аудита:** 2026-08-06
**Статус:** Канонический инженерный план перехода `ui-v4` → `ui-v5`.
**Метод:** Все выводы сверены с фактическим кодом (`app6/`, `uv_module/`, `ui-v4/`, `ui-v5/`) и versioned schema — не с README и не с рендерами.
**Ключевой факт аудита:** `ui-v5/` уже существует как отдельный SPA (14 маршрутов, design system 80/100), но **не имеет API-слоя** (`shared/types.ts`, `shared/api.ts`, React Query, Zustand-сторов) и питается моками `mockData.ts`, в которых **pose bins названы неверно** (`FRONTAL/LEFT_15/...` вместо канонических 9 корзин бэкенда `left_profile…right_profile`). Это критический разрыв контракта, который план закрывает в первую очередь.

---

# ЧАСТЬ 1. 70 КЛЮЧЕВЫХ АНАЛИЗОВ КОДА (ВЕРИФИЦИРОВАНО)

7 блоков × 10 пунктов. Каждый пункт: **факт из кода** → **риск/значимость для UI v5** → **что делать в v5**.

## БЛОК A. Stage 1 — извлечение (`app6/stage1/`, `engine.py`, `info.json`, `texture.json`)

1. **`info.json` — 70+ top-level ключей, единый источник photo-контракта.** Фактическая структура (`schema_version, photo_id, source_relative_path, date, date_year, date_month, date_day, same_date_sequence, date_provenance, source_provenance, perceptual_dhash, near_duplicate_of, pose, chronology, camera, normalization, landmark_contract, mask, uv, quality_inputs, quality_summary, skin, reprojection, crop, files`). **→** В `shared/types.ts` тип `Stage1Info` обязан воспроизводить эти ключи 1:1, а не «облегчённую» выдумку.
2. **`chronology` — ключевые поля для таймлайна.** `pose_bin, canonical_yaw, applied_rotation/scale/center, alignment_quality, correction_*_deg, residual_*_deg, reprojection_p95, reprojection_rmse, expression_magnitude, jaw_open_degree, corner_lift_ioc, jaw_open_ratio, smile_detected, jaw_open_detected, pose_confidence, detection_confidence, face_area_ratio`. **→** Это поля для графиков «над фото» и для фильтров «улыбка/открытый рот/качество». Именно они передаются в Canvas-слои.
3. **`date_provenance` — строгая политика дат.** `{status, exif_date, delta_days, source_claimed_date, source_claimed_delta_days, conflict_sources}`; дата из имени `YYYY_MM_DD[_N]`, EXIF только corroboration. **→** На таймлайне фото-точка X(date) всегда из `date`; конфликт дат — отдельный `EventMarker`, а не перестановка точки.
4. **`files` — маппинг артефактов.** Ключи: `face_crop, thumbnail, face_mask, ldm106_raw, ldm106_aligned(deprecated), ldm106_chronology(recommended), ldm106_original, ldm134_raw, ldm134_chronology, ldm134_original, reconstruction, texture(skin_failure)`. **→** Inspector и Pair Analysis берут URL артефактов только из этого маппинга.
5. **`reconstruction.npz` — наборы координат.** `vertices_object, vertices_identity_only, vertices_object_normalized, vertices_bin_canonical, vertices_chronology_aligned, vertices_camera, vertices_image_224, normals_object, normals_posed, triangles, uv_coords, alpha_full, alpha_id, alpha_exp, alpha_alb, alpha_sh, angle_deg_pitch_yaw_roll, rotation_matrix, translation, canonical_rotation_row_matrix`. **→** Морфинг использует `vertices_object_normalized` (первичный канал) + `alpha_*` для диагностики; `.npz` грузится бинарно, не через JSON.
6. **`texture.json` — только статистика, не пиксели.** `{schema, photo_id, source:{face_mask_png, size, mask_pixels}, model:{panel_size:20, aggregation:"median_z_top20"}, quality:{score, status(high|medium|low|insufficient), metrics{q_noise_mad, q_grad_med, q_lap_med, q_contrast, q_exposure_clip, q_mask_coverage}}, authenticity:{score, status, raw_panel_score, thresholds{q95,q99}, z_scores, metrics}}`. **→** На странице фото — плитка-факт (не таблица). «Вероятность силикона» из ТЗ реализуется строго как `authenticity.status`, а не выдуманное число.
7. **`v12_features.py` — 21 базовый + 40 derived текстурных признаков.** `a_N_corr, bn_ent, cheek_rn_ent, color_cov_rg, dog1_kurt, fore_grad_p99_med, fore_red_std, grad_p95_med, grad_p99_med, gradsign_ent, lab_b_ent, lap_kurt, mottle_red_med, pore_cc_dens, pore_patch_cv, pore_patch_min_max, radial_shade_curve, radial_shade_slope, redness_ent, rn_ent, spec_cheek_over_fore`; стек `ery_stack_*`. **→** Это 21 слой графиков текстурных аномалий для Pair Analysis (metric selector), а не «текстура 0–1».
8. **Канонические pose bins (9) и выражение порогов.** `config.py`: `left_profile(-70), left_deep(-45), left_mid(-32.5), left_light(-17.5), frontal(0), right_light(17.5), right_mid(32.5), right_deep(45), right_profile(70)`; пороги мимики `EXPRESSION_CORNER_LIFT_THRESHOLD=0.005`, `EXPRESSION_JAW_OPEN_THRESHOLD=0.28`. **→** Всё в UI v5 обязано использовать ЭТИ строковые ключи корзин. Мок `FRONTAL/LEFT_15` — недопустим (блокер №1).
9. **Skin-слой (`skin`) и `skin_failure.json`.** `{state, contract:"skin-authenticity-v1", panel:"top20_z_median", texture_file:"texture.json", hard_stop, hard_stop_reason}`. **→** `null/skin_failure` ≠ «кожа в норме»; UI обязан показывать `no_data` бейдж.
10. **Таймлайн-индекс (`main_timeline.csv`).** Колонки: `photo_id, date, same_date_sequence, pose_bin, pitch, yaw, roll, source_filename, date_provenance_status, exif_date, date_delta_days, source_claimed_date, source_claimed_delta_days, date_conflict_sources, source_provenance_status, source_url, archive_url, perceptual_dhash, near_duplicate_of, geometry_status, segmentation_status, uv_status, combined_visible_fraction, skin_mask_coverage, uv_observed_coverage`. **→** Это лёгкий источник для начальной загрузки таймлайна (без .npz), годится для списка 1900 фото.

## БЛОК B. Stage 2 — парный анализ и evidence (`app6/stage2/`)

11. **`pair_metrics.csv` — 186 колонок (13 видимых + 173 скрытых).** Видимые: `pair_id, pair_index, pair_type, pose_bin, photo_a, photo_b, date_a, date_b, status, primary_robust_z, primary_calibration_p95, matched_calibration_sets, ...`. **→** Pair Analysis обязан читать готовый CSV из бэкенда, а не считать на клиенте.
12. **100-метричный реестр (`metric_registry.py`) — семейства.** `pair(15), quality(10), landmark(25), descriptor(10), mesh(20), texture(20, visualization_only)`. **→** Метрики на страницах выбираются из этого реестра; `texture_*` помечается как visualization_only и не участвует в evidence.
13. **Evidence state — 22 отображения status→evidence_state.** Ключевые: `within_noise, elevated_uncertain, coherent_jump_candidate, persistent_geometric_change, reversible_change_candidate, alpha_id_change_candidate, same_day_conflict_candidate, rate_change_candidate, persistent_rate_change_candidate, insufficient_visibility, insufficient_calibration, quality_limited, pose_leakage_limited, not_measurable`. **→** Это кандидаты маркеров на таймлайне. Reportable-состояния (`evidence.py:REPORTABLE_CHANGE_STATES`) — приоритетные аномалии.
14. **`EvidencePacket` — JSON для карточки маркера.** `{schema, pair_id, evidence_state, status, pair_type, pose_bin, photo_a, photo_b, date_a, date_b, primary_zone_or_family, calibration{...}, quality{...}, measurements{32 ключа}, alternative_explanations, source_files{16 ключей}}`. **→** Клик по маркеру на таймлайне открывает именно эту карточку (Rich Tooltip / drawer).
15. **`alternative_explanations` — обязательный скепсис.** Список до 16 строк (`filename_corroborating_date_conflict, perceptual_duplicate_cluster_dependence, source_chain_incomplete, low_or_missing_quality, unstable_or_sparse_calibration, expression_or_soft_tissue_influence, baseline_return_or_reversible_motion, ...`). **→** Каждый тревожный маркер раскрывает альтернативы — это требование ТЗ и AGENTS.
16. **Angle-noise compensation (`angle_noise.py`).** `COMPENSABLE_METRICS=(ldm106_rmse, ldm106_median, ldm106_p95, ldm134_rmse, ldm134_median, ldm134_p95, identity_only_ldm134_rmse)`; пороги `{yaw:2.0, pitch:1.0, roll:1.0}`; поля `{metric}_angle_compensated, {metric}_angle_noise`. **→** В Pair Analysis обе версии метрики (raw/compensated) показываются раздельно с бейджем.
17. **`same_day_gate.py` — конфликт одного дня.** Запись `SAME_DAY_IDENTITY_CONFLICT` с `robust_z, threshold_sigma=12.0, confidence(full|reduced), not_a_verdict:True`. **→** Маркер высшего приоритета (красный пульсирующий), с требованием ручного review.
18. **`irreversible_return.py` — A→B→A.** `IRREVERSIBLE_RETURN_ANOMALY` с `similarity_calibrated=False, gap_years, divergence_ratio, conservative_dates`. **→** Глобально важно: это НЕ доказательство «двойников», это кандидат. UI обязан держать формулировку «return candidate».
19. **`cross_bin_corroboration` — независимое подтверждение.** `cross_bin_support_pose_count, cross_bin_support_count, cross_bin_corroboration_status`. **→** Маркер «подтверждено из 2+ ракурсов» на таймлайне — один из самых ценных сигналов для журналиста.
20. **`pose_leakage.py` — диагностика утечки позы.** `{metric:{status: insufficient_data|no_strong_pose_dependence|weak_pose_dependence|pose_leakage_candidate, spearman_rho, linear_slope}}`; `pose_leakage_limited` только при `pose_distance>1.0`. **→** В Pair Analysis показывает бейдж `pose_leakage_limited`, а не молчаливый score.

## БЛОК C. Калибровка и статистика (`calibration.py`, `robustness.py`, `mesh_calibration.py`)

21. **`CalibrationModel.MAX_REUSE=3, REUSE_PENALTY=0.75`** — ограничение повторного использования калибровочных пар. **→** В UI показывает `matched_calibration_sets` и почему количество ограничено.
22. **Balanced reference + cluster bootstrap CI.** `reference(pose_bin, metric, stratum)` → `{count, ci_lo, ci_hi, ci_width, ci_naive_width, ci_underestimate_factor, n_clusters, method:"cluster_bootstrap_v1"}`; min 3 персоны. **→** Каждая метрика в UI показывает `calibration_p95` и `ci_*`, а не просто число.
23. **`robust_pair_distance` — trimmed metrics.** `{status:ok|insufficient_visibility, common, rmse, trimmed_rmse, median}`, trim 10%. **→** Поля для отображения «raw vs trimmed RMSE» в Pair Analysis.
24. **`pose_gap` и guard ≤2.5.** `_pose_distance` через `angles/[15,20,15]`. **→** Пары с `pose_distance>2.5` показываются как `pose_mismatch/limited` — карточка applicability.
25. **FDR-контроль (`fdr_control.py`, `multiple_testing.py`).** `pair_fdr{test_count, q}, zone_fdr`; канонический уровень 0.05. **→** `p/q` значения рядом с каждой метрикой; большие таблицы не нужны, нужен компактный `q≤0.05` badge.
26. **`expression_gate` — согласованность мимики.** `expression_gate_jaw_mismatch, expression_gate_smile_mismatch, expression_gate_jaw_degree_gap, expression_gate_confidence`. **→** Фильтр «исключить пары с рассогласованной мимикой» на странице Pair Analysis.
27. **Visibility gate.** `MIN_COMMON_134=30, MIN_COMMON_106=24, PRIOR_MIN_FRACTION=0.60`; `pair_visibility{common, required, accepted, reason}`. **→** applicability card показывает `common 106/134` до любых метрик.
28. **`landmark_policy.py` — Subset-91 и NaN-безопасность.** `subset_for_bin{indices, requested, effective, truncated, usable, sufficient, pose_index, status:"per_bin_v1"|"fallback_cross_bin"}`. **→** UI показывает, по какому подмножеству точек считалась метрика (91/106/134) и статус бин-специфичности.
29. **`mesh_calibration.py` + `mesh_zone_indices.json` — 23 зоны.** `PRIORITY_ZONES`; point-to-plane; `mesh_calibrated_elevated_count`. **→** Тепловые карты на морфинге строятся по зонам из этого индекса.
30. **`descriptors.py` — 13 локальных дескрипторов.** `NAMES=(centroid_dx, centroid_dy, centroid_dz, span_lateral, span_vertical, span_depth, bbox_area, bbox_volume, radial_dispersion, plane_residual, normal_angle, curvature, planarity)`; `DescriptorNoiseModel`; статусы `descriptor_jump_candidate/within_descriptor_noise/descriptor_uncertain`. **→** Ещё 13 графиков для анализа «смены формы в целом», отличаются от point-wise RMSE.

## БЛОК D. Хронология и временной ряд (`temporal_axis.py`, `chronology.py`, `baseline_return.py`, `alpha_chronology.py`)

31. **Temporal axis — условно доступна.** `TEMPORAL_AXIS_SCHEMA`; если нет валидированной оси времени — `skipped_no_temporal_axis`. **→** UI должен показывать «временная ось не валидирована», а не рисовать вымышленную кривую старения.
32. **Change points (`change_points.json`).** Детекторы временных скачков. **→** Границы «эпох» на таймлайне (IntervalBand), клик → карточка детектора.
33. **`baseline_return.py` — возврат к базовой линии.** `baseline_return_opposite_fraction, baseline_return_median_cosine, baseline_return_magnitude_ratio`. **→** Маркер возврата (свойство, которое ТЗ называет A→B→A) отображается с мягкой формулировкой.
34. **`alpha_chronology.py` — хронология identity-параметров.** `alpha_id_l2, alpha_exp_l2, alpha_id_robust_z, alpha_exp_robust_z`; `alpha_id_jump_candidate → alpha_id_change_candidate`. **→** Геометрический канал «смена identity-параметра» — отдельная линия на таймлайне.
35. **`chronology_rate_model` — скорость изменений.** `chronology_rate_status, chronology_rate_z, biological_rate_z`. **→** Фильтр «физиологически невероятная скорость» — один из сильнейших сигналов для расследования.
36. **`same_day` vs соседние даты.** `days_delta` в каждой паре. **→** Ось X таймлайна — реальный день, пары соединяются bridge между точками.
37. **Era-разметка API (`api/ui_fields.py`).** `ERA_BOUNDS`: 1999–2007, 2008–2013, 2014–2019, 2020–2026; `era_for(iso_date)`, `normalized_t(iso_date, first, last)`. **→** UI-фильтр по 4 эпохам использует ЭТУ функцию бэкенда, не локальную.
38. **`research_timeline.py` — готовая модель таймлайна.** `RESEARCH_TIMELINE_SCHEMA`; по одному фото на `photo_b` соседних пар; маппинг evidence→fuzzy: `within_noise→CONSISTENT, ... SUSPICIOUS_TEXTURE, GEOMETRIC_MISMATCH`; `bayesian_projection_available:false`. **→** Это готовый лёгкий endpoint для таймлайна; Baye's-проекция H0/H1/H2 отображается только если `bayesian_projection_available:true`.
39. **`stage1_timeline.py` — инвентарь Stage 1.** `build_stage1_inventory` из `main_timeline.csv`. **→** Второй лёгкий источник фото-точек.
40. **`pair_planner.py` — детерминированный план пар.** adjacent + cross-bins внутри pose bin. **→** UI показывает, какие пары запланированы/посчитаны в активном ракурсе.

## БЛОК E. 3D, BFM, UV и морфинг (`app6/api/bfm_topology.py`, `uv_module/`, `FaceMesh3D.tsx`, `morphRenderer`)

41. **`bfm_topology.py` — настоящая BFM-геометрия без нейросети.** `BFMModel(mean_shape(35709,3), id_basis(35709,3,80), exp_basis(35709,3,64), triangles(70789,3), ldm106_indices, ldm134_indices, primary_triangle_zone, primary_zone_ids[A01..A20])`; `compute_shape` идентична `model/recon.py`. **→** Морфинг/3D-viewer строятся на этом; топология грузится один раз и кэшируется.
42. **SHA-256 guard BFM (`bfm_face_model.sha256`).** **→** Inspector показывает валидность модели; недоступность → честный `503`, не поддельный меш.
43. **Mesh endpoint LOD.** `/api/v1/photos/{photo_id}/mesh` c `lod 1–8` и `422` на нечисленные alpha. **→** Inspector грузит LOD по зуму; полный mesh — бинарно/GLB при разрешении.
44. **UV baker (`uv_baker.py`) — анализ vs beauty.** `UVBaker(uv_size=2048, super_sample=2)`, `bake_via_barycentric`; два канала: analysis (реальные пиксели) и beauty (симметрия+inpaint). **→** В Inspector вкладка «UV» обязана различать analysis/beauty — смешение запрещено.
45. **`uv_coherence.py` — риск деформации UV.** `{valid_pixels, usable, vertical_gradient_bias, gradient_direction_entropy_norm, laplacian_p95_norm, nose_strip_grad_asymmetry, uv_deformation_risk}` (веса 0.38/0.32/0.20/0.10). **→** Бейдж `uv_deformation_risk` на фото — защита от ложной трактовки текстурных различий.
46. **`uv_semantic.py` + `texture_zones_bfm35709_v3.npz` — 20 main / 40 sub / 14 focus зон.** `triangle_main_label, triangle_subzone_label, triangle_focus_mask(14), triangle_skin_mask`. **→** Тепловые карты и клик по зоне используют эти маски треугольников.
47. **`inpaint_blend.py` — границы сшивки.** `_symmetry_fill`, `_local_color_correct`, `cv2.inpaint TELEA` — только для beauty. **→** Анализ «границы маски» идёт по analysis-каналу; UI маркирует beauty как производный канал.
48. **`delight.py` — SH-разложение и альбедо.** `compute_shading_uv(normals_uv, alpha_sh)`, `albedo_from_texture(tex, shading)`. **→** Альбедо-карта — диагностическая вкладка Inspector; не используется как identity-канал (policy).
49. **`analysis.py` — `UVAnalysisBundle`.** `{uv_texture, visible_mask, analytic_mask, confidence_map, is_original_mask, coverage_ratio, mean_confidence, original_ratio, usable_for_analysis}`; `build_analytic_uv_mask(min_confidence=0.15, require_original=True)`. **→** Вкладка «UV анализ» показывает именно бандл, с маской оригинальности.
50. **Frontend-3D (ui-v4 `landmarkRenderer`, ui-v5 `FaceMesh3D.tsx`).** В v4 был SVG-приближённый рендер; в v5 уже Three.js. **→** Требование: морфинг — GPU shader `mix(positionA, positionB, uMorphFactor)`, никаких React-пересчётов 35 709 вершин на кадр; capability-check WebGL2.

## БЛОК F. API-слой и контракты (`app6/api/`)

51. **36 endpoint'ов FastAPI.** GET: `health, timeline, photos, photos/{id}, photos/{id}/mesh, photos/{id}/image, photos/{id}/artifacts/{name}, photos/{id}/landmarks/{count}/{space}, photos/{id}/info_keys, photos/{id}/skin_zones, zones/catalog, calibration/noise_model, calibration/health, calibration/match, pairs/{a}/{b}/metrics, run/summary, run/artifacts/{name}, run/keys/{name}, report/summary, report/sections/{name}, jobs, jobs/{id}, system/health, settings`; POST: `photos/upload, compare, compare/full_mesh, compare/upload, calibration/subtract_noise, jobs, jobs/{id}/cancel, reviews, settings/reset, data/clear`; PUT `settings`; DELETE `photos/{id}`. **→** ui-v5 обязан собрать `shared/api.ts` на этих endpoint'ах (OpenAPI snapshot → TS).
52. **Все ответы несут `not_a_verdict:True` и `source_mode:"research"`.** **→** Глобальная маркировка в статус-баре и экспорте.
53. **`settings.py` — versioned настройки.** `SETTINGS_SCHEMA="deeputin-api-settings-v1.1"`; `threshold_mode:"diagnostic_only"`; heatmap stops `{stop_blue_cyan:.25, stop_cyan_green:.50, stop_green_red:.75, stop_saturated_red:1.0, max_residual_reference:.12}`; `landmark_shift:{tolerance:.02, suspect:.05, calibrated:False}`; thresholds `{confidence_min:.5, quality_min:.35, geometry_zone_delta_limit:.018, texture_zone_delta_limit:.04, expression_smile:.92, expression_jaw_open:.28}`. **→** Ползунки на страницах (таймлайн/морфинг/hypotheses) читают и пишут ЭТУ схему; `threshold_mode:"calibrated"` отклоняется без `landmark_shift.calibrated`.
54. **`key_catalog.py` — 289 ключей.** Категории A–I: 162 pair_metrics + 36 manifest + 73 info.json + 14 artifacts. **→** Command palette/поиск по ключам и «где это поле?» строится на каталоге.
55. **`system_health.py`.** `REQUIRED_MODEL_ASSETS`; `{schema, dependencies, resources, gpu, model_assets{required,missing,ready}, bfm_geometry_available, calibration_dataset_present}`. **→** Панель системного здоровья (Overview) читает этот endpoint; «blocked» — честно, не фиктивный успех.
56. **`jobs.py` — statuses `queued|running|complete|blocked|failed|cancelled`.** **→** Прогресс-панель; при отсутствии весов — `blocked`, UI не выдаёт успех.
57. **`review.py` — append-only `manual_qa.jsonl`.** `decisions: approve|reject|needs_recrop|select_face`; требует `{photo_id, decision, reviewer}`. **→** Воркфлоу ручного QA из Inspector.
58. **`compare.py` / `compare_records`.** Возвращает `{schema, status, metrics, zones, diagnostics, not_a_verdict}`; статусы `measured/pose_mismatch/residual_pose_mismatch/insufficient_visibility`. **→** Pair Analysis: он-лайн сравнение произвольных A/B (включая загруженные) — но загруженные фото не попадают в базу.
59. **Ограничение: `pairs/{a}/{b}/metrics` 404 вне одного pose bin.** **→** UI обязан проверять совпадение pose bin ДО вызова и показывать причину.
60. **`report.py` — закрытый `REPORT_SECTIONS`; withheld `texture_*`/`uv_*`.** **→** Публичные отчёты не содержат текстурных каналов; UI помнит `withheld_column_prefixes`.

## БЛОК G. Старый `ui-v4` и текущий `ui-v5` — что переносить, что выкинуть

61. **ui-v4 `shared/api.ts` — рабочие вызовы к backend.** 25+ функций, включая `timeline`, `compare`, `calibration/match`, `jobs`. **→** Адаптеры переносятся в v5 (`shared/api.ts`) без дизайн-слоя v4.
62. **ui-v4 `shared/types.ts` — каркас типов.** НО ключи моков v5 (`snr, boneRmse, textureIndex, clusterId, sha256, ipfsCid, earlyRefSimilarityPercent`) **не совпадают** с контрактами бэкенда (`primary_robust_z, mesh_rmse, texture_*, ...`). **→** Типы переписываются с нуля по верified schema (см. блок A/B/C).
63. **ui-v4 `morphRenderer.ts` / `landmarkRenderer.ts`** — рабочие рендеры A/B и точек. **→** Логику перенести, пересадить на Canvas/Three.js v5.
64. **ui-v4 `TimelineView.tsx` — архитектурная ошибка сайдбаров.** Широкие левый/правый сайдбары, 9 ракурсов одновременно. **→** В v5: один активный ракурс, 100% ширины, верхние раскрывающиеся меню — уже частично реализовано в `TimelinePage.tsx`.
65. **ui-v4 `FilterPanel.tsx` — фильтры в отдельной панели.** **→** В v5 фильтры — раскрывающиеся оверлеи поверх таймлайна с live-пересчётом.
66. **ui-v5 `mockData.ts` — ошибки контракта.** (а) pose bins `FRONTAL/LEFT_15/...` вместо канонических; (б) выдуманные поля `snr/ipfsCid/sha256`; (в) гипотезы с сущностями `putin/udmurt/vasilich`, которых **нет в бэкенд-леджере** (6223 записей ledger не содержат этих сущностей вообще — они есть только в mock и в статье 09). **→** Блокер №2: мок не может быть источником правды; нужен `shared/api.ts` + real schema; сущности гипотез — из реального формата `legacy_hypothesis_ledger.jsonl` (`{source, source_path, source_index, payload:{photo_id, primary_hypothesis, posterior, ...}}`).
67. **ui-v5 `HypothesisValidationPage.tsx` — типы плиток не соответствуют ledger.** **→** Переписать контракт плитки: источник→payload, ретра-статусы `pending_missing_current_data` из `hypothesis_retest_results.jsonl` (6223 записей, 0 ретрастировано), счётчики `legacy_photo_target_count, matched_pair_count, current_metric_name_hits`.
68. **ui-v5 маршруты уже есть (14)**, но страницы — render-accurate моки без запросов к API. **→** План: слой данных (React Query + api.ts) подкладывается под существующие компоненты; дизайн не переделывается, коннект данных заменяется.
69. **ui-v5 design system 80/100** — принят как фундамент (tokens, primitives, Radix). **→** Все новые страницы строятся на нём; P0-замечания из `UI_V5_DESIGN_SYSTEM_REVIEW.md` закрываются до этапа данных.
70. **Тесты.** v5: typecheck PASS, 17/17 vitest PASS, lint 97 ошибок (в основном неиспользуемые импорты), E2E без Chromium. **→** Перед релизом: исправить lint, добавить MSW-тесты для API-слоя, Playwright + axe как gate.

---

# ЧАСТЬ 2. КРИТИЧЕСКИЕ БЛОКЕРЫ (исправить первыми)

| # | Блокер | Где | Что сделать |
|---|---|---|---|
| B1 | Нет `shared/types.ts` + `shared/api.ts` в ui-v5 | `ui-v5/ui-v5/src/shared/` | Создать типы по verified schema (блок A/B), `api.ts` по 36 endpoint'ам, OpenAPI snapshot → TS |
| B2 | Pose bins мока не совпадают с каноном | `mockData.ts` | Заменить на `left_profile…right_profile`; мок допускается только как fixture с пометкой |
| B3 | Выдуманные поля мока (`snr, boneRmse, ipfsCid, sha256, clusterId`) | `mockData.ts`, все страницы | Заменить на поля бэкенда (`primary_robust_z, mesh_rmse, date, pose_bin, ...`); выдуманные — только в tests/fixtures |
| B4 | Гипотезы: сущностей `putin/udmurt/vasilich` нет в ledger | `HypothesisValidationPage` | Контракт плитки = реальный формат `legacy_hypothesis_ledger.jsonl`; сущности — только как журналистская аннотация/слой группировки, не как факт бэкенда |
| B5 | lint 97 ошибок | ui-v5 | Почистить неиспользуемые импорты перед коннектом данных |
| B6 | E2E без Chromium | playwright | Решить загрузку браузера или явно пометить external prerequisite |

---

# ЧАСТЬ 3. ПОДРОБНЫЙ ПЛАН РЕАЛИЗАЦИИ (ЭТАПЫ И ИТЕРАЦИИ)

Общий принцип: **контракты → слой данных → страницы → интеракции → верификация**. Дизайн-каркас v5 уже принят, поэтому этапы идут не «с нуля», а «коннект реальных данных под принятый UI».

## Этап 0. Контракты и типы (0% → 12%)
- **0.1** Сгенерировать TS-типы из OpenAPI snapshot корневого API (`app6/api`). Проверить runtime-validation для критичных payload.
- **0.2** Написать `shared/types.ts`: `Stage1Info`, `TextureInfo`, `PhotoPoint`, `PairMeasurement`, `EventMarker`, `IntervalBand`, `RunProfile`, `EvidencePacket`, `CalibrationReference`, `HypothesisLedgerRecord`, `ClusteringRun`. Каждое поле — из verified schema, с комментарием источника.
- **0.3** Контракт-тесты: `npx tsx`-скрипт сравнивает типы с реальным JSON артефактов (`info.json`, `pair_metrics.csv`, `evidence_packets.json`).
- **Acceptance:** typecheck PASS; ни одно поле не «выдумано» (код-ревью по списку B3).

## Этап 1. API-слой и query-хуки (12% → 22%)
- **1.1** `shared/api.ts`: клиент на 36 endpoint'ах (fetch wrapper, AbortController, gzip, HTTP Range для mesh).
- **1.2** React Query hooks: `useTimeline`, `usePhotos`, `usePhoto(id)`, `useMesh(id, lod)`, `usePairMetrics(a,b)`, `useCalibrationHealth`, `useRunSummary`, `useJobs`, `useSystemHealth`, `useReport`, `useSettings`. Кэш-ключи включают run/profile/schema/pose/viewport.
- **1.3** Обработка состояний: loading / error / empty / limited / null (null ≠ 0). Каждый hook возвращает явные `status` и `reason`.
- **1.4** Zustand-сторы (transient workspace): `useTimelineViewport` (range, zoom, activePose), `useABStore` (A/B pins), `useLayerStore` (видимые слои), `useThresholdStore` (display-пороги, отдельно от scientific).
- **Acceptance:** vitest + MSW на 6 ключевых хуках; error-state snapshot-тесты.

## Этап 2. Главный таймлайн (22% → 40%)
- **2.1** Данные: `useTimeline` → массив PhotoPoint + PairMeasurement + EventMarker + IntervalBand (4 типа сущностей, раздельных).
- **2.2** Temporal transform: `epochDay(date)` → X; один источник для всех слоёв.
- **2.3** Canvas-слои над photo row: pose(yaw/pitch/roll), quality, geometry (LDM106/134, mesh), chronology rate, alpha-id, texture diagnostics (только applicable). Canvas 2D + модульные d3-*; НЕ SVG на тысячи точек.
- **2.4** Photo row чуть ниже центра: virtualized DOM-миниатюры (viewport + overscan 20), zoom-dependent LOD.
- **2.5** Маркеры под photo row: change_point, persistent_change, return, same_day_conflict, provenance, quality/calibration limited, cross-bin corroboration, review flag. Клик → EvidenceCard (drawer) с alternative_explanations.
- **2.6** Годы внизу; `ERA_BOUNDS` из бэкенда; плотность-навигатор.
- **2.7** Верхние раскрывающиеся меню: Ракурс (9 корзин из канона), Метрики, Фильтры, Находки, Сравнение (A/B), Вид, Поиск. Без сайдбаров.
- **2.8** Live-оверлеи порогов поверх таймлайна: качество, улыбка, открытый рот, pose gap — пересчёт в реальном времени (display-only).
- **2.9** A/B на таймлайне: клик→A, клик→B, bridge A→B, недопустимая пара (разные bins) показывает причину.
- **2.10** Zoom/pan: wheel (anchor), Shift+wheel pan, brush, Fit; URL хранит range+pose+run.
- **Acceptance:** 1900 фото < 30ms на pan/zoom; один фото = один X (тест инварианта); null рвёт линию; инварианты SKILL §6.

## Этап 3. Фильтры и Analysis Profiles (40% → 48%)
- **3.1** View Filter (display-only, без изменения Stage 1): дата/эра, pose, качество, мимика, provenance, дубликаты, texture applicability.
- **3.2** Analysis Profile (versioned, для будущего Stage 2): «предпросмотр до применения», журнал diff, freeze/lock, оценка пар/runtime.
- **3.3** Live-гистограммы под каждым threshold-слайдером: распределение, текущий cut, before/after count, warning малого N.
- **3.4** Filter chain inspector: для исключённого фото список причин (`quality 0.31 < 0.50`, `smile_detected=true`, ...), каждая ведёт к control.
- **Acceptance:** view-фильтр не мутирует научные артефакты (контракт-тест); profile имеет digest.

## Этап 4. Инспектор фото (48% → 56%)
- **4.1** Split view: слева original/face_crop/mask/zones/LDM/visibility с zoom/pan/opacity; справа 3D-панель.
- **4.2** 3D-панель с вкладками-чекбоксами: mesh only / texture only / mesh+texture / wireframe / LDM106 / LDM134 / visibility / zones / neutral-expression. Three.js, LOD 1–8, orbit/zoom.
- **4.3** Compact Facts (не таблицы): pose, quality status, expression flags, reprojection, visible counts, artifact completeness, provenance status, authenticity.status — плитки 6–8 шт.
- **4.4** Tabs: Summary / Geometry / Texture / Provenance / Artifacts / Raw. В Texture — texture.json факты + UV (analysis/beauty различие) + albedo/FFT/LBP по факту извлечения.
- **4.5** Manual QA: approve/reject/needs_recrop + reviewer identity → POST `/api/v1/reviews`.
- **Acceptance:** всё из артефактов; 3D падает → честный 503; нет больших JSON-таблиц в дефолтном виде.

## Этап 5. Pair Analysis (56% → 66%)
- **5.1** Header A/B + applicability card (same bin, углы, common 106/134, calibration coverage, quality, expression, provenance).
- **5.2** Range selector (полный период → brush-зум 2009–2012 и т.п.).
- **5.3** 4-рядная virtualized лента миниатюр ~40×40, слайдер размера 40→96px, 1–6 рядов.
- **5.4** После выбора A: A-relative tint (зелёный 20% / красный 20% / amber), всегда с числом+формой, с указанием metric и calibration state; пересчёт в Web Worker.
- **5.5** Основной A/B canvas: side-by-side / overlay / blink / split / landmarks / vectors / zone heatmap.
- **5.6** Metrics: raw и angle-compensated версии, calibrated p95/CI, q(FDR), support count, status, альтернативные объяснения.
- **5.7** Landmark settings прямо на странице: LDM106/134, raw space, векторы, номера точек, region selection, thresholds, gradient, размер/прозрачность.
- **5.8** Early-reference: подбор reference-кадров раннего периода (1999–2005), сравнение A→ref и B→ref, selection rationale, без автоматического identity-вывода.
- **Acceptance:** UI не считает scientific score; красный ≠ «другой человек»; экспорт карточки пары с claim/run/schema.

## Этап 6. Морфинг / 3D хронология (66% → 74%)
- **6.1** GPU-морфинг: topology раз, positions A/B в Float32, shader mix, uniform morphFactor; WebGL2 capability-check + context-loss recovery.
- **6.2** Temporal scrubber: ручной горизонтальный ползунок (главный), snap к реальным фото, play — вторичная мелкая кнопка, speed/loop опционально.
- **6.3** Range zoom: 1999–2026 → brush → 2009–2012 без смены страницы; история zoom.
- **6.4** Layer-чекбоксы (независимые): mesh, texture, wireframe, heatmap, LDM106, LDM134, vectors, visible-only, excluded-expression zones, neutral/original, A/B split.
- **6.5** Heatmap settings overlay прямо над моделью: max reference, color stops (stop_blue_cyan .25 / cyan_green .50 / green_red .75 / saturated 1.0), sharpness, calibrated/diagnostic source, log/linear, clamp.
- **6.6** Light/texture: A/B lighting transition, brightness/contrast (display-only), texture opacity, albedo/raw, предупреждение о разных photometric условиях.
- **6.7** Anchor sequence: хронологические миниатюры-якоря, качество/provenance, excluded-якоря видны но не интерполируются.
- **6.8** Экспорт: PNG кадра, side-by-side, 10s loop/video, GLB, legend; метаданные claim/run; интерполированный кадр не экспортируется как измерение.
- **Acceptance:** scrub 60fps на M1 (измерено); нет React-пересчёта вершин; context-loss безопасен.

## Этап 7. Кластеризация (74% → 82%)
- **7.1** Backend: новый endpoint `/api/v1/clustering` (или артефакт) — HDBSCAN, versioned feature space, membership/outlier/stability, sensitivity runs. UI НЕ считает кластеры.
- **7.2** Режим «Хронология» (основной): кластеры-дорожки C1…Cn на полной шкале 1999–2026, фото-точки по датам, transition lines, regime bands, boundary confidence.
- **7.3** Фильтры: pose (одна корзина) / все 9; period; feature family; normalize; algorithm+params; seed; exclusions.
- **7.4** Boundary detector controls: persistence window, min support, membership threshold, transition confidence, cross-pose agreement, merge gap, sensitivity preview.
- **7.5** Embedding-режим (secondary): UMAP-проекция, оси помечены «проекция», lasso, cluster inspector.
- **7.6** Cloud-режим (presentation only, с бейджем «не временная шкала»).
- **7.7** Обязательная маркировка `КЛАСТЕР — ТЕХНИЧЕСКАЯ ГРУППА, НЕ ИДЕНТИФИКАЦИЯ ЛИЧНОСТИ`.
- **Acceptance:** cluster ≠ identity; переход из кластера в pair analysis сохраняет photo IDs и run ID; параметры versioned.

## Этап 8. Валидация гипотез (82% → 89%)
- **8.1** Изоляция: PRIVATE-шапка, read-only legacy source, no public export, audit identity, blind labels.
- **8.2** Контракт: чтение `legacy_hypothesis_ledger.jsonl` + `hypothesis_retest_results.jsonl` в реальном формате; статусы `supported/contradicted/inconclusive/not_applicable/pending` (не «VERIFIED/REFUTED» из мока).
- **8.3** 3 сущности (`putin/udmurt/vasilich`) — как **журналистская аннотация/слой группировки** поверх ledger, а не как бэкенд-факт; сущности можно скрыть в blind review.
- **8.4** 3 блока плиток (отличия P от U/V, отличия U и V, попарные признаки); каждая плитка: hypothesis ID, zone, legacy-диапазон, текущий диапазон, coverage N/M, статус, uncertainty, source.
- **8.5** Панели калибровки порогов (критично): global + per-pose + per-feature shift X/Y/Z, range width, per-entity блоки, reset; всё — sensitivity-профиль, не подгонка под максимум agreement; каждая правка → audit.
- **8.6** Наложение данных основного датасета: плитки подсвечиваются зелёным/красным оверлеем с процентом совпадения + всегда числом/формой.
- **8.7** Agreement curve: shift/scale vs supported/contradicted; train/holdout раздельно; CI.
- **8.8** Экспорт private (JSON/CSV/PDF) с водяным знаком, без попадания в public.
- **Acceptance:** данные гипотез не влияют на blind Stage 2 и public Stage 3 (тест границы); покрытие ≥90 плиток; все диапазоны калибруемы.

## Этап 9. Калибровка и системное здоровье (89% → 93%)
- **9.1** Health summary: persons/photos/9 bins, complete/low/medium/high references, LOPO, contamination, negative control, release signature.
- **9.2** Coverage matrix person × pose bin (клик → inspect).
- **9.3** Noise distributions per metric/pose: median/MAD/p95/p99/effective N/CI/outliers.
- **9.4** LOPO-таблица, contamination simulation, unstable bins.
- **9.5** Pair matching explorer: подбор калибровочных пар для main пары, замена, rationale, raw vs adjusted.
- **9.6** Overview/System health: readiness header, pipeline diagram, quality distribution, pose coverage, findings summary.
- **Acceptance:** всё из `/api/v1/calibration/*` и `/api/v1/system/health`; честный `blocked`.

## Этап 10. Публикации, аудит, монетизация (93% → 98%)
- **10.1** Publications: claims ledger (claim→evidence→limitation→review), journalist voice controls, skeptic panel, public lint, translation RU/EN, figures/storyboards.
- **10.2** Reports: технический/внутренний/публичный режимы; export JSON/CSV/HTML/PDF/evidence bundle; withheld-каналы.
- **10.3** Audit log: все действия пользователя append-only; integrity-проверка Stage 1 (dataset/code/model/config hashes).
- **10.4** Монетизация/блокчейн: пайплайн генерации артефактов (1900 NFT-карточек + пары + loop морфинга); proof-of-existence через hash+manifest+signature; тяжёлые данные off-chain (IPFS/Arweave) с versioning/access control; НЕ публиковать оригинальные фото/векторы/geometry on-chain без правовой оценки. Коллаж 9 экранов — из `docs/final/nft_blockchain_9screens_collage.jpg`.
- **10.5** Воронка: открытый канал (бесплатные графики/превью/статьи) → закрытый платный канал (подписка: 3D-морфинг, 90+ гипотез, LOPO, PDF) → NFT-артефакты. Полная схема — `docs/PUBLICATION_PIPELINE.md`.
- **Acceptance:** private/public границы (тест утечки гипотез в public bundle); lint блокирует overclaim.

## Этап 11. Верификация, полировка, релиз (98% → 100%)
- **11.1** Исправить lint (97) → 0; typecheck; vitest+RTL+MSW (API-слой, инварианты таймлайна); Playwright E2E + axe.
- **11.2** Perf-гейт: controls <100ms; pan/zoom ≥30fps M1; morph scrub 60fps; ≤viewport+overscan thumbnails; memory leak check при навигации.
- **11.3** Доступность: keyboard path, focus-return, prefers-reduced-motion, non-color status, contrast, 200% zoom, screen-reader summary для Canvas/WebGL.
- **11.4** 25-факторный self-score (SKILL §5) ≥98/100; никаких P0.
- **11.5** Обновить README/AGENTS-разделы/schema/decision records; финальный отчёт по Definition of Done (AGENTS §19).

---

## МАТРИЦА ЗАВИСИМОСТЕЙ И ПРИОРИТЕТОВ

```
Этап 0,1 (контракты+API)   ──► Этап 2 (таймлайн) ──► Этап 3 (фильтры) ──► Этап 5,6 (pair+morphing)
        │                                                        │
        └──────────────► Этап 4 (inspector) ─────────────────────┘
                                                       │
                                        Этап 7 (кластеризация) ──► Этап 8 (гипотезы)
                                                       │
                                        Этап 9 (калибровка/здоровье) ──► Этап 10 (публикации/монетизация)
                                                       │
                                        Этап 11 (верификация/релиз) ◄──────────────────────────────┘
```

**Приоритет критичности:** B1→B2→B3 (контракты) > Этап 2 (таймлайн — ядро) > Этапы 5–6 (второй уровень) > 7–10 (расширения). Функциональный каркас v5 уже есть — план реализует «наполнение реальными данными» и закрывает разрывы контракта до любого масштабирования.

**Внешние предусловия (не блокеры кода):** веса нейросети 3DDFA_V3 (`net_recon.pth`, `large_base_net.pth`, `retinaface_*.pth`) и реальный фотоархив 1999–2026. Без них API честно показывает `blocked`/`source_mode:"demo"`; интерфейс строится и тестируется на fixture-данных с явными пометками `synthetic / not research data`.
