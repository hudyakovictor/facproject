# CORRECTED CLAIMS — FOLLOW-UP NOTE (before PR)
## Что было неверно / завышено в первом аудите

---

## 1.1. Исправленные утверждения

### "scikit-image не интегрирован в app6"

**Статус:** Частично неверно. `app6/stage1/skin/texture/features.py` использует `cv2`, но `FFHQ-detect-face-wrinkles/app.py` и `face_parsing_extraction.py` используют `skimage`. `wrinkles/ffhq_adapter.py` использует `torch` + `skimage`-подобные операции. **Код `app6/` не импортирует `skimage` напрямую в `feature_registry` или `texture/features`**, но это не означает, что `skimage` отсутствует в пайплайне. Для `classic` (`frangi`/`meijering`/`skeletonize`) используется `cv2`, а не `skimage.filters.gabor`.

**Корректировка:** Убрать категоричное утверждение. Указать, что `scikit-image` используется в `FFHQ`-ветке (`FFHQ-detect-face-wrinkles/`), но `feature_registry` (`lbp`, `glcm`, `gabor`, `spectrum`, `wrinkles`) реализован через `cv2` без `skimage`.

---

### "38 зон = текущая истина анализа"

**Статус:** Неверно для `atlas/projection` (`A20`) / `S40` / `W14`. `ZONE_SPECS` (`skin_zone_atlas.py`) описывает 38 канонических зон (`F00`, `BR_L`, `BR_R`, `OR_L`, `OR_R`, `NBT`, `NW_L`, `NW_R`, `CB_L`, `CB_R`, `CS_L`, `CS_R`, `JW_L`, `JW_R`, `CH`, `LZ_L`, `LZ_R`, `LO_L`, `LO_R`, `JA_L`, `JA_R`, `TP_L`, `TP_R` + 13 `wrinkle_focus` + 2 `perioral`). Но `atlas_projection.npz` (`project_atlas`) возвращает `zone_id_a20` (20 зон) и `zone_id_s40` (40 субзон) на уровне треугольной сетки (`70789` треугольников, `A20` = `primary_triangle_zone`). `A01` в `A20` **не равно** `F00` из `ZONE_SPECS`. `W14` (14 морщинных фокусных зон) — это `wrinkle_bits_w14` в `atlas_projection.npz`, не связанное с `A20`.

**Корректировка:** Не смешивать `A20` (atlas projection) с `ZONE_SPECS` (канонические имена зон). Для анализа нужно использовать `zone_id_a20` (из `atlas_projection`) или `zone_id_s40`, но не `F00`/`BR_L` напрямую без маппинга. `W14` — отдельный уровень (`wrinkle_focus`), не пересекающийся с `A20` в `pair_comparison` (`compare_packages` использует `A20` для `common_surface`, `W14` для `wrinkle_matching`).

---

### "Проекция в целом верна, главная проблема только identity aggregator / ideal overlay"

**Статус:** Завышено. Главная проблема не только в отсутствии `individual_identity.py`. **Runtime-класс ошибок:** `visible-side geometry` (зона в `domain_mask`) ≠ `usable evidence` (`feature` `state` = `usable`). Для профилей (`left_profile`, `right_profile`) `pose_policy` (`pose_policy_v3_9bins.csv`) исключает ~50% зон (`exclude`, `0.0`), но `atlas_A20_overlay.png` (`previews.py`) всё ещё показывает эти зоны цветными (`domain_mask` их содержит). `quality_weight.png` показывает их чёрными (`quality_weight` = 0 из-за `pw` или `focus`/`projection`/`contamination`). `wrinkle_ridge_heatmap.png` показывает чёрную область (`ridge_prob` = 0 или `w14` не покрывает зону). **Это основной runtime-defect**, который не был доказан в первом аудите.

**Корректировка:** Перенести акцент с "отсутствия identity aggregator" на "geometry-without-evidence" (`P0-1` в новом аудите).

---

### "На profile боковые зоны exclude — всегда физически нормально"

**Статус:** Частично неверно. `exclude` для **скрытой стороны** (`hidden side`) физически нормально. `exclude` для **видимой стороны** (`visible side`) — **не нормально**, пока не доказано, что область реально `NOT_OBSERVED`. Например, для `right_profile` (`yaw` ≈ +70°, bin `+60`): `A10` (`CB_R` — правая скула/щека?), `A12` (`CS_R`), `A14` (`JW_R`) получают `exclude` (`0.0`) в CSV. Но `atlas_projection` (`domain_mask`) всё ещё содержит эти зоны (геометрия проецируется). `quality_weight` = 0 (`pose_weight` = 0). `feature` = `not_measurable`. **Это `geometry` = yes, `support` = yes (`domain_mask` > 0), `evidence` = no** — `visible-side evidence absence`. Для `left_profile` (`-60`) наоборот: левые зоны (`A09`, `A11`, `A13`) исключены, правые (`A10`, `A12`, `A14`) — `primary`. Но `A01` (`F00`?) имеет **асимметричную** политику (`left_profile`: `exclude`, `right_profile`: `primary`). Это странно и требует проверки.

**Корректировка:** `exclude` для `hidden side` — нормально. `exclude` или `limited` для `visible side` — требует доказательства (`visibility` < порога, `projection_confidence` < 0.2, `contamination` = True) или изменения `pose_policy`.

---

### "Невозможно идентифицировать человека по текущим метрикам"

**Статус:** Завышено. `feature_registry` (`feature_registry.py`) содержит 18 метрик (`3` базовые + `15` расширенные). `metric_registry` (`metric_registry.py`) содержит `100` метрик для `pair_comparison`. `pipeline.py` (`build_skin_package`) генерирует `features/basic_macro.npz`, `features/texture.npz`, `wrinkles/classical.npz`, `wrinkles/ffhq.npz`, `features/local_candidates.npz`. **Это не "невозможно" — это "нет агрегирующего слоя" (`individual_fingerprint` / `identity_score`).** `test_200_self` отсутствует, но метрики существуют. `calibration_dataset` ограничен (`person_01`), но это не означает, что идентификация невозможна.

**Корректировка:** Указать разницу: `per-photo evidence` (`usable`) существует; `aggregation` (`individual fingerprint`, `same_person_probability`) отсутствует; `automated test` (`test_200_self`) отсутствует; `calibration` (`calibration_dataset`) ограничен.

---

### "projected_density_map — physics без numeric proof"

**Статус:** Верно и требует проверки. `projection.py` (`rasterize_surface`) возвращает `projected_density_map` = `cnt / sa` (количество пикселей на треугольник / площадь поверхности треугольника). `pipeline.py` (`build_skin_package`) передаёт `projected_density_map` в `quality_maps` (`quality_maps(bgr, domain, r.incidence, r.projection_confidence, r.triangle_id, projected_density_map=projected_density_map)`). `quality_maps` (`quality.py`) использует `projected_density_map` как `scale` (`projected_scale_px_sqrt`): `eff = scale * focus * np.sqrt(inc) * proc * ns`. Но нет теста, проверяющего, что `scale` варьируется с геометрией (например, для `frontal` vs `profile` или для разных расстояний камеры). `scale` может быть константой или заглушкой, если `triangle_surface_areas` (`tri_area`) рассчитаны некорректно или `surface_vertices` отсутствуют.

**Корректировка:** Добавить `check_density_map_sanity.py` (в `PIPELINE_AUDIT/`), который проверяет, что `projected_density_map` варьируется по `triangle_id` и не является константой для всех пикселей в `domain_mask`. Или задокументировать, что `projected_density_map` требует валидации (`assert` или `test`), прежде чем считаться `physics-corrected`.

---

## 1.2. Что было верно и остаётся

- Нет `individual_fingerprint` / `identity_score` (`stage3` отсутствует).
- Нет `test_200_self` (`tests/dataset_200_self/`, `tests/test_self_identity_200.py`).
- `same yaw-bin` (`frontal`) ≠ `same geometry` (`pitch`/`roll` не учитывается в `pose_policy` или `pair_comparison`).
- Нет `ideal overlay` / `geometric normalization` для `same pose bin` с разным `pitch`/`roll` (`compare_packages` использует `common_surface()` с `min_conf = 0.2`, но не проверяет `pitch_roll_diff`).
- `pipeline.py` (`line 92`) загружает `pose_policy` относительно `atlas_path` — риск `default` fallback.
- `preview` (`previews.py`) шире `usable_domain` — `atlas_A20_overlay.png` показывает `geometry`, `quality_weight.png` показывает `quality` = 0 для `exclude` зон, но нет `disclaimer` или `applicability` overlay.
- `pair_metrics.csv` (`metric_registry`) содержит `INSUFFICIENT_EVIDENCE` / `COARSE_ONLY` для `profile` или `low common_surface`, но `evidence_packets.json` или `technical_summary.json` не всегда подчёркивает это как `abstain`.
- `calibration_dataset` ограничен (`person_01` только).

---

## 1.3. Исправленные формулировки для PR

**Было:** «scikit-image не интегрирован в app6» → **Стало:** «`feature_registry` (`lbp`, `glcm`, `gabor`, `spectrum`, `wrinkles`) реализован через `cv2` (`texture/features.py`). `FFHQ-detect-face-wrinkles/` использует `skimage` (`app.py`, `face_parsing_extraction.py`). Для полноты `scikit-image` можно интегрировать в `texture/features.py` (`skimage.filters.gabor` или `skimage.feature.multiscale_basic_features`), но это не критический `runtime` дефект».

**Было:** «38 зон = текущая истина анализа» → **Стало:** «`ZONE_SPECS` (`skin_zone_atlas.py`) описывает 38 канонических зон (`F00`...`JA_R` + 13 `wrinkle_focus` + 2 `perioral`). `atlas_projection.npz` (`project_atlas`) возвращает `A20` (20 зон) и `S40` (40 субзон) на уровне `primary_triangle_zone` треугольной сетки (`70789` треугольников). `W14` (`wrinkle_bits_w14`) — отдельный уровень (`wrinkle_focus`). `pose_policy_v3_9bins.csv` использует `A01`-`A20`, не `F00`/`BR_L`. Для анализа нужно сопоставлять `zone_id_a20` (`A20`) или `zone_id_s40` (`S40`) с `ZONE_SPECS`, но не считать их прямым соответствием».

**Было:** «Проекция в целом верна, главная проблема только identity aggregator» → **Стало:** «`projection.py` (`rasterize_surface`, `project_atlas`) возвращает `domain_mask`, `zone_id_a20`, `projected_density_map`. Но `visible-side geometry` (`domain_mask` > 0) ≠ `usable evidence` (`feature` `state` = `usable`). Для `profile` (`left_profile`/`right_profile`) `pose_policy` (`pose_policy_v3_9bins.csv`) исключает ~50% зон (`exclude`, `0.0`), но `atlas_A20_overlay.png` (`previews.py`) показывает их как присутствующие. `quality_weight.png` показывает их как `0` (`black`). `wrinkle_ridge_heatmap.png` показывает `0` или очень низкую `ridge_prob`. `features/basic_macro.npz` показывает `state` = `not_measurable` (`support` = 0 или `pixels` < 100). Это основной `runtime` дефект (`P0-1`), не `product gap`».

**Было:** «На profile боковые зоны exclude — всегда физически нормально» → **Стало:** «`exclude` для `hidden side` (`left_profile`: левые зоны `A01`-`A06`, `A09`, `A11`, `A13`, `A15`, `A17`; `right_profile`: правые зоны `A03`, `A05`, `A07`, `A08`, `A10`, `A12`, `A14`, `A16`) — физически нормально. `exclude` или очень низкий `quality_weight` (`0.25` или `0.0`) для `visible side` (`left_profile`: правые зоны `A02`, `A03`, `A05`, `A07`, `A08`, `A10`, `A12`, `A14`, `A16`, `A18`, `A19`, `A20`; но `A01` (`F00`?) исключена для `left_profile` — это странно) — требует доказательства (`visibility` < порога, `projection_confidence` < 0.2, `contamination` = `True`) или изменения `pose_policy`».

**Было:** «Невозможно идентифицировать человека» → **Стало:** «`feature_registry` (`basic_macro`, `texture`) содержит `usable` метрики (`luminance`, `ridge_density`, `lbp_entropy`, `glcm_contrast` и т.д.). `metric_registry` (`100` метрик) рассчитан на `pair_comparison` (`pair_metrics.csv`). Нет `individual_fingerprint` (`stage3` отсутствует), нет `test_200_self` (`tests/dataset_200_self/` отсутствует), нет `calibration` для 200 фото (`calibration_dataset` ограничен `person_01`). Это `product gap`, не `runtime` невозможность».

**Было:** «projected_density_map — physics без numeric proof» → **Стало:** «`projected_density_map` (`projection.py`) = `cnt / sa` (`screen pixels` / `triangle surface area`). `pipeline.py` передаёт его в `quality_maps` (`quality_maps(...)` с `projected_density_map`). `quality_maps` использует его как `scale` (`projected_scale_px_sqrt`). Но нет `test` или `assert`, проверяющего, что `scale` варьируется с геометрией (`frontal` vs `profile`) или расстоянием (`surface_vertices`/`triangles`). Без этого поле может быть константой или заглушкой. `P1-6`: добавить `check_density_map_sanity.py`».

---

## 4. Матрица `pose × region class × geometry × evidence`

Создан как текстовая таблица в `DEEP_AUDIT_REPORT.md` (раздел 8). Кратко:

- `frontal`: `Geometry` = 20/20 (`A20`), `Support` = 20/20 (`primary`/`support`), `Evidence` = 20/20 (`usable` или `coarse_only` для `macro_texture`; `micro_texture` может быть `NOT_MEASURABLE` для зон с `effective_resolution` < 1.2).
- `left_profile`: `Geometry` = 20/20 (все зоны в `domain_mask`), `Support` = 12/20 (`primary`: `A02`, `A03`, `A05`, `A07`, `A08`, `A10`, `A12`, `A14`, `A16`, `A18`, `A19`, `A20`; `exclude`: `A01`, `A04`, `A06`, `A09`, `A11`, `A13`, `A15`, `A17`), `Evidence` = ~12/20 (`usable` для `primary`, `NOT_MEASURABLE` для `exclude`).
- `right_profile`: `Geometry` = 20/20, `Support` = 11/20 (`primary`: `A01`, `A04`, `A06`, `A09`, `A11`, `A13`, `A15`, `A17`, `A18`, `A19`, `A20`; `exclude`: `A02`, `A03`, `A05`, `A07`, `A08`, `A10`, `A12`, `A14`, `A16`).
- `left_light` (`-17.5`, bin `-25` или `-10`): `Support` = 12-14/20 (`primary` или `support` для большинства; `limited` или `exclude` для некоторых).
- `left_deep` (`-45`, bin `-40`): `Support` = 9-12/20 (`primary` для ~9-12; `limited` или `exclude` для остальных).

**Критическое наблюдение (`P0-1`):** Для `profile` (`left_profile`/`right_profile`) `visible side` (`primary` зоны) имеет `Geometry` = yes, `Support` = yes (`quality_weight` > 0, `applicability` = `usable`), `Evidence` = `usable` (`feature` `state` = `usable`). `hidden side` (`exclude` зоны) имеет `Geometry` = yes (`domain_mask` содержит зону), `Support` = no (`quality_weight` = 0, `pose_weight` = 0), `Evidence` = `NOT_OBSERVED` или `NOT_MEASURABLE` (`feature` `state`). Это правильно для `hidden side`, но `preview` (`atlas_A20_overlay.png`) не различает `usable` и `NOT_OBSERVED` — это `P0-2` (preview false confidence).

---

## 5. Что сдано в репозиторий (`arena/019f8451-facproject`)

- `ANALYST_PREPARATION/AUDIT_ANALYST_REPORT.md` (исправлено в `DEEP_AUDIT_REPORT.md` — полный пересмотр claims с кодовыми ссылками).
- `ANALYST_PREPARATION/METRIC_GAPS.md` (оставлено; уточнено: `feature_registry` содержит `usable` метрики, но нет `aggregation`/`fingerprint`).
- `ANALYST_PREPARATION/ZONE_ATLAS_MAP.md` (оставлено; добавлено замечание о `A20` ≠ `ZONE_SPECS` напрямую).
- `PIPELINE_AUDIT/check_projection.py` (оставлено; исправлено для работы без `numpy`/`cv2`).
- `PIPELINE_AUDIT/check_metrics_identity.py` (оставлено; исправлено для работы с `feature_keys` и `METRICS` без прямого импорта).
- `PIPELINE_AUDIT/check_zone_coverage.py` (оставлено; исправлено для `ZONE_SPECS` и `POSE_BINS`).
- `PIPELINE_AUDIT/check_profile_zones.py` (**новый** — полная диагностика `pose_policy_v3_9bins.csv` vs `_build_default()` для всех 9 ракурсов с таблицей `A01`-`A20`).
- `PROJECT_PREPARATION/TEST_200_SELF.md` (оставлено; добавлено замечание о `calibration` ограничении).
- `PROJECT_PREPARATION/DATASET_STRUCTURE.md` (оставлено).
- `PROJECT_PREPARATION/CHRONOLOGY_SETUP.md` (оставлено).
- `PROJECT_PREPARATION/9_ANGLES_SCHEME.md` (оставлено).
- `AUDIT_DEEP/DEEP_AUDIT_REPORT.md` (**новый** — полный аудит `geometry` vs `support` vs `evidence` для каждого ракурса; карта `pose × region class × layer`; `preview` vs `numeric`; `left/right` симметрия; `same-pose` readiness; `finding cards` с `severity` и `fix direction`).

---

## 6. Определение готовности (`DoD` для PR)

PR принимается, если:

1. `DEEP_AUDIT_REPORT.md` присутствует в репозитории (или его ключевые разделы перенесены в `docs/` или `audit/`).
2. `PIPELINE_AUDIT/check_profile_zones.py` запускается (`python`) и выводит таблицу `A01`-`A20` для `-60` и `+60`.
3. `check_geometry_vs_evidence.py` (если добавлен) запускается и возвращает матрицу `geometry`/`support`/`evidence` для тестового фото (`frontal`, `left_profile`, `right_profile`).
4. `check_preview_vs_numeric.py` (если добавлен) сравнивает `previews/atlas_A20_overlay.png` с `features/basic_macro.npz` (`state`) и находит расхождения (`geometry yes`, `evidence no`).
5. `check_pose_policy_load.py` (если добавлен) проверяет, что `PosePolicy` загружает CSV (`pose_policy_v3_9bins.csv`) и не использует `_build_default()` (проверка через `policy.rows` или `policy.get('A01', 0)`).
6. `pipeline.py` (`line 92`) исправлен или задокументирован: либо абсолютный путь к CSV, либо `assert` на существование `.npz` + CSV.
7. `previews.py` содержит `disclaimer` или `usable_evidence` overlay (`atlas_A20_overlay_usable.png` или изменение `atlas_A20_overlay.png` для отображения только `usable` зон).
8. `quality.json` содержит `pose_policy` (`available`/`unavailable`) и `applicability` для каждой зоны (`A20` или `S40`) с `state` (`usable`/`coarse_only`/`not_measurable`/`not_observed`).
9. `feature_registry` (`feature_registry.py`) содержит `local_mad` с `state` = `not_measurable` при `support` < `min_support` или `pixels` < 128 (`texture/features.py` уже содержит эту логику, но нужно убедиться, что `basic_macro` (`extract_basic`) использует тот же `min_support`).
10. `compare_packages` (`pair_comparison.py`) содержит `pitch_roll_diff` или `common_surface_low` в `status` или `reason`, или `INSUFFICIENT_EVIDENCE` явно содержит `pose_policy` или `common_observed_gate` причину.

---

## 7. Заключение

Этот `DEEP_AUDIT_REPORT.md` не повторяет `wishlist` первого аудита (`identity aggregator`, `self-200`, `scikit-image` как `must-have`). Он фокусируется на `runtime` `evidence-path` (`geometry` → `support` → `evidence`) для каждого ракурса (`frontal`, `left_light`, `left_deep`, `left_profile`, `right_light`, `right_deep`, `right_profile`).

**Главный `runtime` defect:** `visible-side geometry` (зона в `domain_mask`) без `usable evidence` (`feature` `state` = `not_measurable` или `quality_weight` = 0). Это происходит из-за:
- `pose_policy` (`exclude` или `limited` для `visible side` — проверено для `A01` в `left_profile`: `exclude` `0.0`);
- `pipeline.py` (`line 92`) — риск `_build_default()` вместо CSV (`check_profile_zones.py` показывает разницу);
- `quality_weight` = 0 из-за `pw` (`pose_weight`) или `contamination_keep` или `focus`/`projection` (`quality.py`);
- `preview` (`previews.py`) не различает `geometry` и `evidence` (`P0-2`).

**Исправленные claims первого аудита:**
- `scikit-image`: используется в `FFHQ` (`FFHQ-detect-face-wrinkles/app.py`), но не в `feature_registry` (`cv2` только).
- `38 зон`: `ZONE_SPECS` (`F00`...`JA_R`) ≠ `A20` (`atlas_projection`). `W14` (`wrinkle_bits_w14`) ≠ `A20`.
- `Проекция`: `projected_density_map` требует `sanity test` (`P1-6`), прежде чем считать `physics-corrected`.
- `Profile`: `exclude` для `hidden side` — нормально; для `visible side` — требует доказательства (`visibility` < порога или `projection_confidence` < 0.2) или изменения `pose_policy`.
- `Identity`: `usable` метрики существуют (`feature_registry`); отсутствует `aggregation` (`individual_fingerprint`) и `test` (`self-200`).

**Что сдано в `arena/019f8451-facproject`:**
- `AUDIT_DEEP/DEEP_AUDIT_REPORT.md`
- `PIPELINE_AUDIT/check_profile_zones.py`
- Исправленные `ANALYST_PREPARATION/` (корректировка `scikit-image`, `38 зон`, `profile`, `identity`).

**Что нужно сделать в PR (по `DoD`):** `test` + `fix gate` + `preview disclaimer` + `same-pose pitch/roll protection` + `density sanity`.
