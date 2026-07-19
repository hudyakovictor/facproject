# АУДИТ facproject — Часть 4: Глубокий аудит непроверенных модулей

**Дата:** 2026-07-19  
**Аналитик:** Forensic Face & Skin Consistency Analyst  
**Версия:** uv_module 3.3.0 / deeputin-stage2-v1.3

---

## Исправленные критические баги

### 1. `make_photo_id()` — риск коллизии photo_id
**Файл:** `app6/stage1/naming.py:53`  
**Проблема:** Функция `make_photo_id()` полностью игнорировала `source_sha256`, возвращая только `canonical_stem` (напр. `2000_01_15`). Два фото из разных источников на одну дату получали одинаковый `photo_id`.  
**Исправление:** Добавлено включение первых 8 символов SHA-256 в ID: `2000_01_15__a1b2c3d4`.

### 2. `load_calibration()` — несовместимые имена полей landmarks
**Файл:** `app6/stage2/loaders.py:42,67`  
**Проблема:** Native app6 формат использует `ldm106_object_normalized`, а формат calibration_datasets — `ldm106_object_norm`. Прямой доступ через `z["field"]` вызывал KeyError для одного из форматов.  
**Исправление:** Обратный совместимый доступ через `z.get("ldm106_object_normalized", z.get("ldm106_object_norm"))` + аналогично для ldm134. Добавлена валидация после загрузки.

### 3. `3ddfav3/model/recon.py` — модульный импорт UVTextureGenerator
**Файл:** `3ddfav3/model/recon.py:8`  
**Проблема:** `from util.uv_texture_generator import UVTextureGenerator` на уровне модуля крашил весь `recon.py` если DEPRECATED модуль отсутствует или содержит ошибки. facproject использует `extractTex=False`, поэтому импорт никогда не нужен.  
**Исправление:** Убран module-level импорт, добавлен ленивый `from util.uv_texture_generator import UVTextureGenerator` внутри блока `if args.extractTex`.

### 4. `3ddfav3/model/recon.py` — `process_uv()` мутирует входной массив
**Файл:** `3ddfav3/model/recon.py:31`  
**Проблема:** Функция модифицирует `uv_coords` in-place, что может приводить к багам при повторном использовании оригинального массива.  
**Исправление:** Добавлен `uv_coords = uv_coords.copy()` в начале функции.

### 5. `3ddfav3/model/recon.py` — default texture_size=1024
**Файл:** `3ddfav3/model/recon.py:232`  
**Проблема:** `getattr(args, 'texture_size', 1024)` — превышен лимит 1000px.  
**Исправление:** Изменено на `getattr(args, 'texture_size', 1000)`.

### 6. `masks.py` — вводящий в заблуждение `fallback_used` флаг
**Файл:** `app6/stage1/masks.py:56`  
**Проблема:** При падении `back_resize_crop_img()` устанавливался `fallback_used = False`, хотя фоллбэка не существует — маска просто None.  
**Исправление:** Изменено на `fallback_used = True` с комментарием "projection failed; using 224px masks only".

### 7. `masks.py` — мёртвый код `save_masks()`
**Файл:** `app6/stage1/masks.py`  
**Проблема:** Функция `save_masks()` никогда не вызывается из `engine.py` — используется `save_face_mask()` и `save_semantic_channels()`.  
**Исправление:** Удалена.

### 8. `symmetry.py` — мёртвое вычисление sigma
**Файл:** `uv_module/symmetry.py:130-132`  
**Проблема:** `lvl_sigma = sigma * (S / (S / (2 ** lvl)))` немедленно перезаписывалось `lvl_sigma = max(1.0, sigma * (2.0 ** lvl))`. Первое вычисление упрощается до `sigma * 2**lvl`, что совпадает со вторым — но код содержал мёртвую строку.  
**Исправление:** Удалена мёртвая строка, добавлен комментарий explaining scaling logic.

### 9. `ui/server.py` — doctor check путь к assets
**Файл:** `ui/server.py:_doctor_payload()`  
**Проблема:** Проверял только `3ddfav3/assets/`, который не существует на многих конфигурациях.  
**Исправление:** Проверяются оба кандидата: `3ddfav3/assets/` и `assets/`.

### 10. Stage3 — UV geometry данные не отображались
**Файл:** `app6/stage3/engine.py`  
**Проблема:** Evidence packets содержат UV geometry метрики (добавлены в Part 3), но Stage3 HTML-отчёт не имел секции для их визуализации. Narrative не упоминал UV анализ.  
**Исправление:** Добавлена секция "UV-геометрия кожи" с таблицей по зонам (ridge_density_delta, branch_count_delta, total_length_delta, ridge_strength_delta). Добавлен narrative пункт о UV-анализе. Schema обновлена до v1.4.

### 11. `pose_analysis.py` — добавлена deprecation
**Файл:** `uv_module/pose_analysis.py`  
**Проблема:** Модуль дублирует `skin_analysis.py`, но не был помечен как устаревший.  
**Исправление:** Добавлен DEPRECATED warning в docstring + `warnings.warn()` при вызове `analyze_pose_zones()`.

---

## Глубокий аудит непроверенных модулей

### app6/stage2/core.py — ✅ Чист
- `robust_rigid_align()`: корректная итеративная Kabsch с trim. Логика выхода при < min_points правильная.
- `compare_landmarks()`: правильное использование stable_anchor_mask, корректная зональная статистика.
- `build_coordinate_zone_map()`: ограничение 200 записей — приемлемо для стабильных квантилей.
- `calibrated_score()`: MAD-based z-score с корректным 1.4826 scaling для consistency с normal distribution.

### app6/stage2/calibration.py — ✅ Чист
- `_nearest()`: корректный nearest-neighbor matching для matched_null.
- `matched_null()`: правильно использует независимые calibration datasets, не смешивает a и b.
- `_pose_distance()`: нормализация angles на [15, 20, 15] согласуется с motion.py и descriptors.py.

### app6/stage2/motion.py — ✅ Чист
- `PointNoiseModel._build()`: корректное построение same-person noise по offset=1,2 парам.
- `_coherence()`: разумная k-nearest neighbor согласованность. С `k=6` и порогом `cos > 0.25` — консервативно.
- `score()`: floor на MAD (0.25 * median MAD) предотвращает деление на ноль при нулевом шуме.

### app6/stage2/descriptors.py — ⚠️ Стиль
- Код максимально компактный (одна строка на операцию), но логически корректный.
- `DescriptorNoiseModel.score()`: правильная z-нормализация и top-5 descriptor family вывод.
- ⚠️ `local_pair_descriptors()` вычисляет 13 признаков на landmark через k=8 соседей — O(N*k) вычислений, но для 134 landmarks это быстро.

### app6/stage2/mesh_calibration.py — ✅ Чист
- `MeshNoiseModel._build()`: корректно строит p95/MAD reference по pose bin.
- `score()`: правильная калибровка mesh метрик с fallback на "insufficient_calibration".

### app6/stage2/alpha_chronology.py — ✅ Чист
- Корректно разделяет alpha_id (identity-shape) и alpha_exp (expression leakage).
- Логика `alpha_id_jump_candidate` и `expression_dominated` правильно упорядочена.

### app6/stage2/baseline_return.py — ✅ Чист
- A→B→C reversal detection: косинус, opposite_fraction, magnitude_ratio — разумные пороги.
- `_reversal_stats()`: корректно фильтрует zero-norm векторы.

### app6/stage2/corroboration.py — ✅ Чист
- Cross-bin corroboration: проверяет только adjacent пары, window_days=45.
- Корректно различает corroborated_multiple_pose_bins / corroborated_one_pose_bin.

### app6/stage2/pose_leakage.py — ✅ Чист
- Spearman без scipy (через rank correlation) — правильная реализация.
- Порог rho >= 0.45 для "pose_leakage_candidate" — консервативно.

### app6/stage2/multiple_testing.py — ✅ Чист
- BH FDR реализован корректно: step-up procedure с монотонизацией.
- `_p_from_z()`: erfc-based p-value от robust z — корректно.

### app6/stage2/postprocess_reports.py — ✅ Чист
- `FORBIDDEN_PUBLIC_TERMS`: содержит и русские, и английские термины.
- `_write_public_safety()`: сканирует `.lower()` всего evidence packet — грубо но безопасно.

### app6/stage2/private_hypothesis.py — ✅ Чист
- 17 hypothesis families определены корректно.
- `_candidate_keys()`: правильная рекурсивная walk по payload.
- `_retest_record()`: корректно проверяет current pair metrics на совпадение с legacy.

### app6/stage2/quality_integration.py — ✅ Чист
- `load_quality_zone_summary()`: правильная распаковка NPZ с fallback на defaults.
- `pair_quality_zone_overlap()`: корректный cross-photo zone comparison.

### app6/stage2/texture_image.py — ✅ Чист
- 361 строка качественного кода: LBP (numpy fallback + scikit-image), GLCM (numpy fallback + scikit-image), Gabor profile, patch-grid entropy.
- `_erode_roi()`: scale-aware erosion для устранения warp/hair артефактов.
- ⚠️ `texture_pair_deltas()` загружает полные изображения через `cv2.imread()` — может быть медленно для больших датасетов, но для ≤800x800px приемлемо.

### app6/stage2/texture_structure.py — ✅ Чист
- `register_patches()`: phase correlation + max_shift gate — правильная registration.
- `_ridge_probability()`: multi-scale Hessian ridge (3 sigma), dual polarity — качественная реализация.
- `_skeleton()`: cv2-based morphological skeletonization — медленно (256 итераций), но корректно.

### app6/stage2/metric_registry.py — ✅ Чист
- Точно 100 канонических метрик — проверено `if len(METRICS) != 100: raise RuntimeError`.
- `metric_channel()`: lossless projection — правильная реализация.

### app6/stage2/chronology.py — ✅ Чист
- `apply_chronology_rate_flags()`: time-weighted jump rate с sqrt(days) нормализацией.
- Backward compatibility: `biological_rate_z` alias.

### app6/stage2/leads.py — ✅ Чист
- `load_leads()`: правильная агрегация из legacy archive (5 JSON файлов).
- `pair_leads()`: корректный cross-match по date_a/date_b.

### app6/stage2/technical_summary.py — ✅ Чист
- Простая агрегация — нет вычислительных багов.

### uv_module/rasterizer.py — ✅ Чист
- `build_uv_raster()`: O(#triangles) fillConvexPy — правильная реализация.
- `interpolate_vertex_attribute()`: барицентрическая интерполяция — математически корректна.
- Кэширование через layout hash — правильная стратегия.

### uv_module/visibility.py — ✅ Чист
- `compute_visibility()`: v3.2 coverage-scaled tolerance — оригинальная и корректная реализация.
- `_auto_depth_sign()`: auto-detection направления depth — правильная эвристика.
- Barycentric-interpolated depth вместо constant-per-triangle — значительное улучшение v1/v2.

### uv_module/zones.py — ✅ Чист
- 13 канонических wrinkle zones с 9-pose policy — полная и консистентная с app6/stage1/config.py.
- `zone_vertex_masks()`: box-based UV test — простой и корректный.

### uv_module/calibration.py — ✅ Чист
- `_stratified_holdout()`: детерминированный 80/20 split — правильный подход.
- `calibrate()`: корректная проверка reliable_model_count >= 3.

### uv_module/chronology.py — ✅ Чист
- `match_branches()`: greedy matching с centroid/orientation/length tolerance — разумная эвристика.
- `load_records()`: гибкая загрузка (dir/json/jsonl) — правильная реализация.

### uv_module/metrics.py — ✅ Чист (backward compat)
- `wrinkle_graph_features()`: использует `summarize(sk, separator="_")` (исправлено в Part 1).
- `texture_detail_report()`: правильный Laplacian + GLCM + LBP fallback.

### 3ddfav3/util/io.py — ✅ Чист
- `back_resize_crop_img()`: корректная paste+resize операция.
- `align_img()`: 5-point POS alignment — стандартная реализация.

### 3ddfav3/util/preprocess.py — ⚠️ Дублирование с io.py
- Содержит копию `back_resize_crop_img()` и `back_resize_ldms()`.
- Это intentional — каждый модуль является self-contained.
- ⚠️ `label_colormap()` с hardcoded 9-label cmap — работает для текущих 8 сегментов + background.

---

## Архитектурные наблюдения

### Двухпространственный анализ кожи — полностью интегрирован
1. **UV-space** (Frangi + skan): `uv_module/skin_analysis.py` → `uv_module/forensics.py` → `app6/stage1/assets.py` → `app6/stage2/uv_comparison.py` → `app6/stage2/engine.py` → `app6/stage2/evidence.py` → `app6/stage3/engine.py`
2. **Image-space** (LBP/GLCM): `app6/stage2/texture_image.py` → `app6/stage2/engine.py` → `app6/stage2/evidence.py` → `app6/stage3/engine.py`

### Консистентность метрик
- 100 канонических метрик в `metric_registry.py` — все путь от Stage2 row → evidence packet → metric_catalog → Stage3 data.
- UV geometry метрики (7 ключей) добавлены в evidence packets (Part 3) и теперь визуализируются в Stage3 (Part 4).

### Калибровка
- 7 калибровочных моделей: `CalibrationModel` (landmark), `PointNoiseModel` (point motion), `DescriptorNoiseModel` (local shape), `MeshNoiseModel` (dense mesh), `CalibrationSensitivity` (leave-one-out), + alpha_id/alpha_exp, + chronology rate.
- Все модели используют одинаковый `_pose_distance()` с нормализацией [15, 20, 15].

---

## Оставшиеся проблемы (не блокирующие)

| # | Файл | Проблема | Критичность |
|---|------|----------|-------------|
| 1 | `app6/stage2/mesh_dense.py` | `MESH_COUNT = 35709` hardcoded | Низкая — face_model.npy стабильна |
| 2 | `app6/stage1/validator.py` | `MESH_COUNT = 35709` hardcoded | Низкая — тот же аргумент |
| 3 | `app6/stage2/mesh_zone_indices.json` | chin=1 vert, ligaments=2 vert, nose_wing_L≡nose_bridge_tip overlap | Средняя — зоны тихо дропаются |
| 4 | `app6/stage2/texture_pair.py` | Stub — проверяет readiness, не делает сравнение | Низкая — реальная работа в texture_image.py |
| 5 | `uv_module/pose_analysis.py` | Дублирует skin_analysis.py (DEPRECATED в Part 4) | Низкая — backward compat |
| 6 | Нет end-to-end интеграционного теста | Все тесты — unit | Средняя |

---

## Итого: Часть 4

**Исправлено багов:** 11  
**Новых модулей:** 0 (только фиксы существующих)  
**Проверено модулей:** 24 (все оставшиеся stage2, stage3, uv_module, 3ddfav3, ui)  
**Критических багов найдено:** 4 (naming.py collision, loaders.py KeyError, recon.py crash, masks.py misleading flag)  
**Все критические баги исправлены.**
