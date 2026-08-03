# Ключи пайплайна без реализации в интерфейсе — топ-50

**Дата:** 2026-07-29
**Метод:** инвентаризация ключей на всех этапах (Stage 1 → 2 → 2B → 3) и
сверка с тем, что фактически доходит до API и рендерится в UI.

---

## Масштаб разрыва

| Источник | Ключей | Доходит до API | Видно в UI |
|---|---:|---:|---:|
| Stage 1 `info.json` | 180 | ~10 | ~8 |
| Stage 1 `quality.json` | 12 на зону | 12 | ✅ 12 |
| **Stage 2 `pair_metrics.csv`** | **186** | **10** | ~6 |
| Stage 2 артефакты (файлы) | 19 | 3 | 2 |
| Stage 2 `analysis_manifest.json` | 40 | ~8 | ~5 |
| Stage 3 отчёт | ~45 | 0 | 0 |

**Главный вывод:** 176 из 186 колонок Stage 2 не покидают диск. Пайплайн
считает статистику, калибровку и корроборацию, а интерфейс показывает
результат единственного канала — движения landmarks.

Крупнейшие «слепые зоны» по группам колонок: `mesh` (52), `texture` (15),
`quality` (10), `ldm134/ldm106` (14), `expression` (6), `descriptor` (6),
`cross_bin` (6), `mt` (FDR, 5), `alpha` (5), `lead` (5).

---

## Топ-50 доработок

Приоритет = научная ценность × риск ошибочной интерпретации без ключа ×
готовность данных.

### 🔴 P1 — статистическая достоверность (без этого выводы некорректны)

| # | Ключи | Где разместить |
|---|---|---|
| 1 | `mt_q_value`, `mt_p_approx`, `mt_significant_fdr10`, `mt_fdr10_diagnostic_flag`, `mt_role` | **Новый блок «Статзначимость»** в правой панели PairCompare. Сейчас аномалия показывается без поправки на множественные сравнения — при 1700 фото это тысячи пар, и часть «аномалий» ложные по построению |
| 2 | `primary_robust_z`, `primary_calibration_p95` | Туда же: рядом с сырым расхождением — калиброванный z и порог |
| 3 | `cross_bin_corroboration_status`, `cross_bin_support_count`, `cross_bin_support_pose_bins`, `cross_bin_independent_source_count`, `cross_bin_family_matched_count` | **Блок «Корроборация»** в PairCompare: подтверждается ли расхождение в других ракурсах. Ключевой barrier против ложных выводов |
| 4 | `calibration_limited`, `calibration_sensitivity_status`, `calibration_sensitivity.json` | Раздел «Калибровка» → карточка «Устойчивость»: не держится ли вывод на одной персоне |
| 5 | `pose_leakage_status`, `pose_leakage_flagged_metrics`, `pose_leakage_limited_pair_count` | **Баннер-предупреждение** в PairCompare: метрика коррелирует с позой, а не с личностью |
| 6 | `quality_limited`, `quality_zone_pair_limited`, `quality_status_a/b` | Значок «ограниченное качество» на карточке пары и в тултипе таймлайна |
| 7 | `expression_qc_status`, `expression_qc_exceeded`, `expression_magnitude_a/b`, `expression_qc_threshold` | Бейдж «мимика» рядом с фото A/B: ТЗ требует исключения зон при улыбке |
| 8 | `status`, `evidence_state` (полный словарь) | Легенда состояний в STATS; сейчас маппинг в `fuzzy` теряет градации |

### 🟠 P2 — mesh-канал (52 колонки, полностью невидим)

| # | Ключи | Где разместить |
|---|---|---|
| 9 | `mesh_status`, `mesh_evidence_level` | **Новая вкладка «MESH»** в PairCompare рядом с «Точки» |
| 10 | `mesh_rmse`, `mesh_median`, `mesh_p95` + `*_robust_z`, `*_calibrated_status` | Таблица там же: сырое / калиброванное / статус |
| 11 | `mesh_point_to_plane_rmse/median/p95/signed_median` | Отдельная строка: point-to-plane точнее point-to-point для поверхностей |
| 12 | `mesh_anatomical_zone_count`, `mesh_zone_source`, `zone_map.json` | Зонная раскладка меша (уже есть `primary_triangle_zone` в API) |
| 13 | `mesh_visible_fraction`, `mesh_common_vertex_count`, `mesh_fit_vertex_count` | Строка покрытия: на скольких вершинах построено сравнение |
| 14 | `mesh_alignment_policy`, `mesh_alignment_trimmed_count`, `mesh_alignment_residual_before/after_median` | Дополнить существующую панель «Диагностика выравнивания» |
| 15 | `mesh_anchor_policy`, `mesh_anchor_fraction` | Туда же |
| 16 | `mesh_calibration_status`, `mesh_calibrated_metric_count`, `mesh_calibrated_elevated_count`, `mesh_max_robust_z` | Сводка калибровки меша в блоке «Статзначимость» |
| 17 | `mesh_space_a/b` | Провенанс: в каком пространстве сравнивались формы |
| 18 | `mesh_noise_model.json` | Раздел «Калибровка» → рядом с моделью углового шума |

### 🟡 P3 — текстура и дескрипторы

| # | Ключи | Где разместить |
|---|---|---|
| 19 | `texture_image_status`, `texture_image_zone_count`, `texture_image_usable_zone_count` | **Вкладка «Текстура»** в PairCompare (не новый анализ — чтение готовых) |
| 20 | `texture_image_max_lbp_chi2`, `max_glcm_contrast_delta`, `max_high_frequency_delta`, `max_entropy_delta`, `max_gabor_delta`, `max_laplacian_delta`, `max_gradient_delta` | Таблица там же — 7 независимых текстурных каналов |
| 21 | `texture_structure_registered_zone_count`, `max_ridge_delta`, `min_registered_ssim` | Секция «Структура кожи» |
| 22 | `texture_image_backend`, `texture_image_schema` | Провенанс внизу вкладки |
| 23 | `descriptor_status`, `descriptor_significant_fraction`, `descriptor_landmark_fraction`, `descriptor_p95_z` | Блок «Дескрипторы формы»: 13 локальных семейств из ТЗ |
| 24 | `descriptor_top_families`, `descriptor_top_counts` | Топ-семейств с наибольшим расхождением |
| 25 | `forehead_wrinkle_supported_a/b` | Бейдж применимости лобных морщин к паре |

### 🟢 P4 — хронология и события

| # | Ключи | Где разместить |
|---|---|---|
| 26 | `chronology_rate_z`, `chronology_rate_status`, `chronology_rate_reason` | Тултип точки таймлайна: скорость изменения с оценкой |
| 27 | `biological_rate_z`, `biological_rate_status`, `biological_reason` | Туда же — биологическая правдоподобность темпа |
| 28 | `change_points.json` (`change_count`, магнитуда, дата) | **Слой на таймлайне**: вертикальные метки точек перелома |
| 29 | `alpha_chronology.json`, `alpha_chronology_event_count` | Дорожка alpha-хронологии рядом с геометрией |
| 30 | `cumulative_drift.json` | Дорожка накопленного дрейфа (флаг уже есть, значений нет) |
| 31 | `baseline_return.json` (детали, не только годы) | Раскрытие маркера возврата: какие метрики откатились |
| 32 | `alpha_id_l2`, `alpha_exp_l2`, `identity_only_ldm134_rmse`, `identity_only_motion_rmse` | Блок «Идентичность vs мимика» — разделение каналов |
| 33 | `alpha_exp_status`, `alpha_exp_robust_z`, `alpha_exp_calibration_p95` | Туда же |

### 🔵 P5 — провенанс и воспроизводимость

| # | Ключи | Где разместить |
|---|---|---|
| 34 | `source_sha256`, `source_filename`, `source_relative_path` | **Попап «Провенанс»** по клику на ID фото |
| 35 | `code_hash`, `config_hash`, `model_hash`, `schema_version` | Туда же: воспроизводимость прогона |
| 36 | `extraction_timestamp`, `created_at_utc`, `elapsed_seconds` | Туда же |
| 37 | `source_digest_a/b`, `source_group_a/b` | Провенанс пары в PairCompare |
| 38 | `stage1_manifest_digest`, `artifact_hashes` | Раздел «Данные» → целостность артефактов |
| 39 | `same_date_sequence` | Бейдж «несколько кадров за день» на таймлайне |
| 40 | `pair_id`, `pair_index`, `pair_type` | Заголовок карточки сравнения |

### ⚪ P6 — качество кадра (Stage 1, 180 ключей)

| # | Ключи | Где разместить |
|---|---|---|
| 41 | `quality_inputs.*` (10: laplacian_variance, tenengrad_mean, gradient_anisotropy, noise_residual_mean, face_bbox_*, skin_mask_coverage, uv_observed_coverage, combined_visible_fraction) | **Раскрывающийся блок «Параметры кадра»** в LeftPanel |
| 42 | `mask.*` (10: policy, status, fallback_used, hard/soft_area_fraction, channel_area_fraction по 8 каналам) | Туда же, секция «Маски» |
| 43 | `uv.*` (11: observed_coverage, valid_coverage, mean_confidence_observed, synthetic_policy, status…) | Туда же, секция «UV» |
| 44 | `reprojection.ldm106_224/ldm134_224` | Метрика точности реконструкции в LeftPanel |
| 45 | `crop.*` (bbox_original, crop_source, letterbox.*) | Секция «Кроп» — понять, что попало в анализ |
| 46 | `camera.*` (focal, principal_point, projection, render_size, camera_distance) | Провенанс камеры |
| 47 | `normalization.*` (method, center, scale) | Провенанс нормализации |
| 48 | `pose.canonical_yaw` + отклонение от bin | Уточнение позы в тултипе (yaw/pitch/roll уже есть) |

### ⚫ P7 — сводки и отчёт

| # | Ключи | Где разместить |
|---|---|---|
| 49 | `technical_summary.json` целиком (status_counts, evidence_state_counts, *_limited_pair_count, manifest_core, public_safety) | **Новая страница «Сводка прогона»** или блок в STATS — готовый техотчёт, который сейчас нигде не виден |
| 50 | `limitations`, `skipped_pair_counts`, `missing_mandatory_qc_record_count`, `evidence_packet_count`, `metric_catalog.json` | Блок «Ограничения прогона» в STATS: что НЕ измерено и почему |

---

## Рекомендуемый порядок

**Шаг 1 — расширить контракт API.** Сейчас `research_timeline.py` читает
10 колонок из 186. Пока это не изменится, любая UI-работа упрётся в
отсутствие данных. Минимум: пробросить группы `mt_*`, `cross_bin_*`,
`quality_*`, `expression_*`, `pose_leakage_*`.

**Шаг 2 — блок «Статзначимость» (№1–8).** Наибольшая ценность на единицу
работы: без FDR-поправки и корроборации интерфейс показывает аномалии,
часть которых ложные по построению. Это прямой риск неверного вывода в
расследовании.

**Шаг 3 — вкладка MESH (№9–18).** 52 колонки — самая крупная невидимая
группа; данные уже считаются.

**Шаг 4 — блоки «Параметры кадра» и «Провенанс» (№34–48).** Механическая
работа, закрывает 180 ключей Stage 1 двумя раскрывающимися панелями.

---

## Оговорки

* Числа по Stage 2 получены на `app6/test_data/S04_fdr_stress_A_p05_v00`
  (эталонный вывод в репозитории). На реальном прогоне набор колонок тот же —
  он задаётся кодом `export.py`, а не данными.
* Stage 2B (`private_hypothesis`) намеренно исключён: `AGENTS.md` определяет
  его как приватный слой, который «не является источником фактов» и не должен
  создавать публичный вывод.
* Stage 3 (~45 ключей) не имеет ни одного API-эндпоинта. Это отдельная
  задача: отчёт формируется как самостоятельный HTML/JSON и в интерфейс
  сейчас не интегрирован вовсе.
* Часть ключей — служебные (`files.*`, `motion_file`, `mesh_file`): в списке
  они не как «показать пользователю», а как источник для загрузки артефактов.
