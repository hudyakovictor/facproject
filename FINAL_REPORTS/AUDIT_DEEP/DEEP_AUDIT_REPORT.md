# ГЛУБОКИЙ АУДИТ: skin/atlas pipeline — только по коду
## Экспертный анализ face/skin pipeline для журналиста-расследователя
## Дата: 2026-07-21 | Ветка: arena/019f8451-facproject

---

## 1. ЦЕЛЬ АУДИТА (по вашему брифу)

Независимый разбор кодовой базы. Не «работает ли в целом», а **для каждого ракурса и каждой области видимой стороны**: что реально становится `usable evidence`, а что остаётся только в промежуточных/preview-слоях.

**Главный вопрос:** Можно ли доверять `zone/feature evidence` при сравнении двух фото **одного ракурса**?

**Проверяемая цепочка:**
```
mask → atlas/projection → pose/quality gates → features/wrinkles → pair comparison
```

---

## 2. КОНТРАКТЫ АРТЕФАКТОВ (SCHEMAS)

```python
SCHEMAS = {
    "manifest":"skin-manifest-v1",
    "surface":"skin-surface-observations-v1",
    "atlas":"skin-atlas-projection-v1",
    "quality":"skin-quality-v1",
    "features":"skin-features-v1",
    "wrinkles":"skin-wrinkles-v1",
    "material":"skin-material-evidence-v1",
    "pair":"skin-pair-v1",
}
```

### 2.1 Source of truth по слоям

| Слой | Файл/объект | Что является «истиной» в этом слое |
|---|---|---|
| **Geometry (маска)** | `face_mask.npz` (`mask_original`) | Пиксели, классифицированные как кожа (без фона, губ, бровей, глаз) |
| **Atlas projection** | `atlas_projection.npz` (`zone_id_a20`, `zone_id_s40`, `domain_mask`) | Треугольники mesh, попавшие в `skin_mask` и `visibility` |
| **Surface observations** | `surface_observations.npz` (`triangle_id`, `projection_confidence`) | Глубина, нормали, видимость для каждого треугольника |
| **Quality** | `quality_maps.npz` (`quality_weight`, `effective_resolution`) | Физика плотности пикселей (`projected_density_map` v4) + фокус + экспозиция + шум + JPEG + резкость |
| **Applicability** | `quality.json` (`applicability`) | Состояние `EvidenceState`: `usable` / `coarse_only` / `not_measurable` / `not_observed` |
| **Features (макро)** | `features/basic_macro.npz` | `zone_luminance_median`, `luminance_mad`, `luminance_iqr` |
| **Texture features** | `features/texture.npz` | 24 метрики: LBP, GLCM (6), Gabor, Spectrum (6), Structure, LoG, Pigmentation (6) |
| **Wrinkles (classical)** | `wrinkles/classical.npz` | `ridge_probability`, `skeleton`, `points` |
| **Wrinkles (FFHQ)** | `wrinkles/ffhq.npz` | `probability` от нейросетевого детектора |
| **Local features** | `features/local_candidates.npz` | Кандидаты точечных особенностей |
| **Pair comparison** | `pair_metrics.csv`, `zone_metrics.csv`, `evidence_packets.json` | Сравнение метрик для двух фото (`pair_index`, `days_delta`, `status`) |

### 2.2 Критическое замечание: domain определяется по-разному в разных модулях

- `projection.py` (`project_atlas`): `domain = valid & seg & skin_mask` (где `valid` = `tid >= 0`, `seg` = сегментация, `skin_mask` = маска кожи из атласа).
- `quality_maps`: `d` = `domain_mask` из `project_atlas`, но `qm['quality_weight'] *= pw` (pose weight) и `qm['quality_weight'] *= contamination_keep` (контаминация).
- `pipeline.py`: `w = (focus * exposure * proj * proc * ns * (~spec) * (~shadow) * d).astype(np.float32)` — здесь `d` — это тот же `domain_mask`, но `w` затем используется как `quality_weight`.
- `feature_registry`: `required_quality='macro_texture'` или `'wrinkles'` или `'meso_texture'` или `'pigmentation'`. Каждая семья имеет свои гейты (`micro_texture` требует `effective_resolution >= 1.2` и `min(W,H) >= 700`).
- `pair_comparison`: `common_surface()` использует `a['projection_confidence'] >= min_conf` (`min_conf=.2`). Если `projection_confidence` < 0.2, треугольник не входит в `common_surface`, даже если он в `domain_mask`.

**Вывод:** `domain_mask` (геометрия) ≠ `usable_surface` (пара). Треугольник может быть в маске, но не участвовать в сравнении из-за `projection_confidence` или `pose_compatible`.

---

## 3. ТРИ СЛОЯ: GEOMETRY → SUPPORT → EVIDENCE

Для каждого ракурса и каждой зоны (`A20`/`S40`/`W14`) нужно проверить три независимых уровня.

### 3.1 Определения

- **Geometry (слой 1):** Зона присутствует в `atlas_projection.npz` (`zone_id_a20` или `zone_id_s40` не `-1`). Треугольник в `triangle_id >= 0`.
- **Support (слой 2):** `quality_weight` > 0, `applicability` не `NOT_OBSERVED` или `NOT_MEASURABLE`, `pose_policy` даёт вес > 0 (`primary`/`support`/`limited`), `projection_confidence` >= 0.2.
- **Evidence (слой 3):** Для макро-текстуры (`macro_texture`): `effective_support` >= `min_support` (по умолчанию 100 в `extract_texture_features`), `state == 'usable'`. Для морщин (`wrinkles`): `ridge_probability` или `ffhq_prob` содержит ненулевые значения в зоне. Для дескрипторов (`descriptor`): `descriptor_status` не `not_measurable`.

### 3.2 Матрица: ракурс × область × слои

Проверено по коду (`pose_policy_v3_9bins.csv` для 9 ракурсов, `pipeline.py` для gates, `quality.py` для applicability, `feature_registry.py` для evidence gates).

```
Ракурс: frontal (yaw ≈ 0°, bin 0)

Geometry:
- F00 (лоб): A01 → в domain (frontal zone primary)
- BR_L / BR_R: A02/A03 → в domain
- OR_L / OR_R: A04/A05 → в domain
- NBT: A06 → в domain
- NW_L / NW_R: A09/A10 → в domain
- CB_L / CB_R: A11/A12? (в зависимости от маппинга) → в domain
- CS_L / CS_R: в domain
- JW_L / JW_R: в domain
- CH: A15 → в domain
- LZ_L / LZ_R, LO_L / LO_R, JA_L / JA_R: в domain
- TP_L / TP_R: в domain

Support (по CSV, bin 0 = primary для frontal):
- Все A01-A20: weight 1.0 или 0.6 (для некоторых subzone S40)
- Quality: `focus` > 0.12 (иначе `NOT_MEASURABLE`), `projection` > 0.2 (иначе `NOT_MEASURABLE` или `COARSE_ONLY`)
- Applicability (`quality.py`): для `macro_texture` — `usable` или `coarse_only`; для `micro_texture` — требуется `effective_resolution_median >= 1.2` и `min(W,H) >= 700`

Evidence:
- `features/basic_macro.npz`: для каждой зоны A01-A20 — `state` либо `usable`, либо `not_measurable` (если `n < 100` или `focus < 0.12` или `projection < 0.2`)
- `features/texture.npz`: `values` — 24 метрики; если `ap['micro_texture']['state']` не `usable` или `coarse_only`, значения на позициях 10+ (`microrelief`) = `NaN`
- `wrinkles/classical.npz`: `ridge_probability` — для зон с `domain_mask` > 0; если `w14` (wrinkle bits) не покрывает зону, `ridge` в этой области = 0
- `wrinkles/ffhq.npz`: `probability` — предсказание FFHQ; если `ffstate == 'not_run_weights_unavailable'`, файл содержит нули или отсутствует
- `pair_metrics.csv`: для пары фото — `status` зависит от `ldm106_rmse`/`ldm134_rmse`, `mesh_rmse`, `texture_image_max_*`, `descriptor_*` — но НЕ от `zone-level skin fingerprint`

Критическое наблюдение для frontal:
- Все 20 зон A20 присутствуют в `domain_mask`.
- `applicability` для `macro_texture` обычно `usable` или `coarse_only`.
- НО: `micro_texture` (`local_feature_matching`, `material_optics`) может быть `NOT_MEASURABLE` для зон с низким `effective_resolution` (< 1.2).
- `feature_registry.py`: `local_mad` (microrelief) регистрируется с `expected_range` `(0, None)` — это может давать ложную «стабильность» при `NaN` или очень низких значениях.

Ракурс: left_profile (yaw ≈ -70°, bin -60)

Geometry (по CSV, bin -60):
- A01 (F00 — лоб): weight 0.0 → EXCLUDE в domain? Нет — `domain_mask` зависит от `primary_triangle_zone` и `segmentation`. Но `pose_policy.weights()` возвращает 0.0 для A01 при -60. В `pipeline.py` (`build_skin_package`): `pw, pm = policy.weights(p['zone_id_a20'], pose.get('yaw',0))` — `pw` применяется к `quality_weight` (`qm['quality_weight'] *= pw`) и `effective_resolution` (`qm['effective_resolution'] *= np.sqrt(pw)`).

Это означает: для A01 при left_profile (`pw = 0.0`):
- `quality_weight` для этой зоны = 0
- `effective_resolution` = 0
- `applicability` (`quality.py`): `effective_support` = 0 → `NOT_OBSERVED` или `NOT_MEASURABLE`
- `features/basic_macro.npz`: `state` = `not_measurable` (если `support < min_support` или `pixels < 100`)
- `wrinkles`: `w14` (wrinkle bits) для A01 при -60 — нужно проверить, но `pose_policy` не влияет напрямую на `w14` в `projection.py`, только через `domain_mask`.

Support (по CSV, bin -60):
- A01: 0.0 (исключена)
- A02: 1.0 (первичная)
- A03: 0.0? Нет — A03 (`BR_R`?) — по CSV: -60 → 1.0, 60 → 0.0. Для left_profile (-60): A03 = 1.0.
- A04: 0.0 (исключена)
- A05: 1.0 (первичная)
- A06: 0.0 (исключена)
- A07: 1.0 (первичная)
- A08: 1.0 (первичная)
- A09: 0.0 (исключена)
- A10: 1.0 (первичная)
- A11: 0.0 (исключена)
- A12: 1.0 (первичная)
- A13: 0.0 (исключена)
- A14: 1.0 (первичная)
- A15: 0.0 (исключена)
- A16: 1.0 (первичная)
- A17: 0.0 (исключена)
- A18: 1.0 (первичная)
- A19: 1.0 (первичная)
- A20: 1.0 (первичная)

Важно: `A01` (лоб) исключена для left_profile! `A03` (правая бровь?) — первичная для left_profile. `A05` (правая орбита?) — первичная.

Это странно: для left_profile (лицо смотрит влево, показывая правую сторону анатомически?) — но `+yaw exposes anatomical-left`. То есть отрицательный yaw (-60) раскрывает анатомически ПРАВУЮ сторону. Поэтому для left_profile видны правые зоны (`BR_R`, `OR_R`, `NW_R`, `CB_R`, `CS_R`, `JW_R`, `JA_R` и т.д.), а левые (`BR_L`, `OR_L` и т.д.) исключены или ограничены.

Это объясняет наблюдение пользователя: «на правой щеке как-будто исключены» для profile. Но в зависимости от того, какой именно profile (`left_profile` или `right_profile`), разные стороны исключаются.

Evidence для left_profile:
- `A01` (лоб): `NOT_OBSERVED` или `NOT_MEASURABLE` (из-за `pw=0`). `basic_macro` не содержит записи для A01 или содержит с `state='not_measurable'` и `values=NaN`.
- `A02` (левая бровь?): `usable` или `coarse_only`.
- `A03` (правая бровь?): `usable`.
- `A04` (левая орбита?): `NOT_OBSERVED`.
- `A05` (правая орбита?): `usable`.
- `A06` (нос): `NOT_OBSERVED`.
- `A07` (левая носовая крыло?): `usable`.
- `A08` (правая носовая крыло?): `usable`.
- `A09` (левая щека?): `NOT_OBSERVED`.
- `A10` (правая скула?): `usable`.
- `A11` (левая мягкая щека?): `NOT_OBSERVED`.
- `A12` (правая мягкая щека?): `usable`.
- `A13` (левая челюсть?): `NOT_OBSERVED`.
- `A14` (правая челюсть?): `usable`.
- `A15` (подбородок): `NOT_OBSERVED`.
- `A16` (левая связка?): `usable`.
- `A17` (правая связка?): `NOT_OBSERVED`.
- `A18` (левая орбитальная связка?): `usable`.
- `A19` (правая орбитальная связка?): `usable`.
- `A20` (левая/правая углы челюсти?): `usable`.

Это означает, что для `left_profile` (~50% зон) `basic_macro` содержит `usable`, но остальные (`NOT_OBSERVED` или `NOT_MEASURABLE`) не участвуют в сравнении пар (`pair_metrics.csv`), потому что `compare_packages()` использует `common_surface()` — зоны с `NOT_OBSERVED` просто не попадают в `common_surface`.

**Критический вывод:** Для `left_profile` или `right_profile` около 50% зон `A20` исключаются из `evidence`. `pair_comparison` (`compare_packages`) работает только с `common_surface()` — то есть сравнивает только те зоны, которые видны в ОБОИХ фото. Если для `left_profile` фото A видит зоны A02, A03, A05, A07, A08, A10, A12, A14, A16, A18, A19, A20 — а фото B (`right_profile`) видит совершенно другой набор (A01, A02, A04, A06, A07, A08, A09, A11, A13, A15, A16, A17, A18, A19, A20 по CSV?) — `common_surface` будет очень маленьким или нулевым.

Но это не ошибка — это физическая реальность профиля. Ошибка может быть в том, что `pair_comparison` не делает `INSUFFICIENT_EVIDENCE` явно для таких случаев, или что `metric_catalog` (`build_metric_catalog`) считает метрики «активными» даже при очень низком `pair_coverage_fraction`.

---

## 4. PREVIEW VS NUMERIC TRUTH (проверка расхождений)

### 4.1 Как генерируются preview

`previews.py`:
```python
def save_previews(root,bgr,A,mask,quality):
    colors = ...
    layer = bgr.copy()
    for i in range(20): layer[A==i] = colors[i]
    overlay = np.where(mask[...,None], cv2.addWeighted(bgr,.55,layer,.45,0), bgr)
    cv2.imwrite(str(root/'atlas_A20_overlay.png'), overlay)
    q = np.clip(quality*255, 0, 255).astype(np.uint8)
    heat = cv2.applyColorMap(q, cv2.COLORMAP_TURBO)
    cv2.imwrite(str(root/'quality_weight.png'), np.where(mask[...,None], heat, 0))
```

`save_wrinkle_overlay`:
```python
sk = np.asarray(skeleton, bool)
overlay = bgr.copy()
overlay[sk] = [0,0,255]
cv2.imwrite(str(root/'wrinkle_skeleton.png'), np.where(mask[...,None], overlay, bgr))
r = np.clip(ridge_prob*255, 0, 255).astype(np.uint8)
heat = cv2.applyColorMap(r, cv2.COLORMAP_TURBO)
cv2.imwrite(str(root/'wrinkle_ridge_heatmap.png'), np.where(mask[...,None], heat, 0))
```

**Расхождение:** `mask` в `previews.py` — это `domain_mask` из `project_atlas`. `quality` — это `qm['quality_weight']` (после применения `pw` и `contamination_keep`). `A` — это `p['zone_id_a20']`.

Но `domain_mask` (`p['domain_mask']`) включает только области, где `tid >= 0` И `seg` (skin mask) И `skin_mask` из атласа. Если зона (`A==i`) присутствует в `domain_mask`, но `quality_weight` для этой зоны = 0 (из-за `pose_policy` или низкого `focus`/`projection`), `atlas_A20_overlay.png` покажет зону ЦВЕТНЫМ (потому что `A==i`), но `quality_weight.png` покажет ЧЁРНЫЙ (или очень тёмный) для этой зоны.

Это означает: preview (`atlas_A20_overlay.png`) может показывать зону как «присутствующую» (она в `domain_mask`), но `quality_weight.png` покажет её как «неанализируемую» (quality = 0). Пользователь видит это как «зона исключена» в `quality_weight.png`, хотя в `atlas_A20_overlay.png` она видна.

**Это не ошибка — это правильное поведение.** Но это может создавать ложное впечатление для журналиста, который смотрит `atlas_A20_overlay.png` (зона видна!) и `quality_weight.png` (зона чёрная = исключена), но не понимает, почему.

### 4.2 Проверка для конкретного случая пользователя

Пользователь говорит: «на рендерах `wrinkle_ridge_heatmap.png` `quality_weight.png` многие зоны на правой щеке как-будто исключены».

Это может означать:
- `quality_weight.png`: правая щека (`CB_R` или `CS_R`) — чёрная или очень тёмная.
- `wrinkle_ridge_heatmap.png`: в области правой щеки нет красных/жёлтых точек (нет `ridge_prob` > 0).

Причины (по порядку вероятности):

1. **Profile angle (`left_profile` или `right_profile`):** `pose_policy` исключает правую или левую щеку (`A10` или `A12` с weight 0.0 для одного из профилей). `quality_weight` = 0 → `quality_weight.png` чёрный.
2. **`projection_confidence` < 0.2` в области:** Даже если зона в `domain_mask`, `projection_confidence` может быть низким из-за высокого угла (`incidence` близка к 0 или нормаль отклонена). `applicability` (`quality.py`) устанавливает `state = NOT_MEASURABLE`, но `domain_mask` всё ещё содержит зону. `quality_weight` = 0, но `atlas_A20_overlay.png` всё ещё показывает зону.
3. **`contamination_keep` = False:** `pipeline.py` (`build_skin_package`): `contamination_keep` вычисляется через `FaceParsingAdapter` (волосы, очки, внешняя окклюзия). Если правая щека покрыта волосами или очками (`contamination_keep = False`), `qm['quality_weight'] *= False` → 0. Но `domain_mask` не изменяется! `atlas_A20_overlay.png` всё ещё показывает зону.
4. **`wrinkle_ridge_heatmap.png`:** `ridge_prob` для зоны = 0, потому что `w14` (wrinkle bits) не покрывает эту зону в `project_atlas`. Или `detect_wrinkles()` (`wrinkles/classical.py`) не находит морщин в этой области из-за `quality_weight` = 0 или низкого фокуса.
5. **`FFHQ` (`wrinkles/ffhq.npz`):** `ffstate` = `'not_run_weights_unavailable'` или `'partial'` — модель не загружена или не предсказывает. `prob` = ноль или не записывается.

**Вывод для пользователя:** Если на `quality_weight.png` зона «исключена» (чёрная), но в `atlas_A20_overlay.png` она видна (цветная) — это **НЕ ошибка кода**, это **расхождение между geometry layer и support layer**. Но для журналиста это должно быть явно задокументировано в отчёте (например, через `quality.json` или `technical_summary.json`).

---

## 5. POSE-DEPENDENT LOGIC: ГДЕ ОБНУЛЕНИЕ, А ГДЕ ДЕГРАД

### 5.1 Как `pose_policy` влияет на каждый слой

```python
# pipeline.py (build_skin_package)
pw, pm = policy.weights(p['zone_id_a20'], pose.get('yaw', 0))
qm['pose_weight'] = pw
qm['quality_weight'] *= pw
qm['effective_resolution'] *= np.sqrt(np.clip(pw, 0.25, 1.0))
```

Это означает:
- Для зоны с `primary` (`pw = 1.0`): `quality_weight` без изменений, `effective_resolution` без изменений.
- Для `support` (`pw = 0.6`): `quality_weight` *= 0.6, `effective_resolution` *= sqrt(0.6) ≈ 0.77.
- Для `limited` (`pw = 0.25`): `quality_weight` *= 0.25, `effective_resolution` *= sqrt(0.25) = 0.5.
- Для `exclude` (`pw = 0.0`): `quality_weight` = 0, `effective_resolution` = 0.

**Проблема:** `applicability` (`quality.py`) использует `effective_resolution` и `quality_weight` для определения `EvidenceState`. Если `effective_resolution` = 0 (из-за `exclude`), `base['effective_resolution_median']` = 0, и для `micro_texture` (`fam in {'micro_texture','material_optics','local_feature_matching'}`) это сразу `NOT_MEASURABLE` (по условию `base['effective_resolution_median'] < 1.2`).

**Но для `macro_texture`:** `effective_resolution` используется только для `COARSE_ONLY` (если < 0.6). При 0 это `NOT_MEASURABLE`. То есть `exclude` в `pose_policy` приводит к `NOT_OBSERVED` или `NOT_MEASURABLE` в `applicability` — что корректно.

**Проблема в другом:** `pose_policy` не учитывает `pitch` или `roll`. Только `yaw` (`pose.get('yaw', 0)`). Если фото `frontal` (`yaw ≈ 0`), но с сильным `pitch` (наклон головы вверх/вниз) или `roll` (наклон вбок), `pose_policy` всё равно назначает `primary` для всех фронтальных зон. Но фактически `projection` (`rasterize_surface`) может иметь очень низкий `projection_confidence` или `visibility` для нижней или верхней части лица из-за `pitch`. `quality_weight` для этих зон будет низким или нулевым, но `pose_policy` всё ещё говорит `primary`.

Это приводит к **ложной уверенности** в `quality.json`: `pose_policy.per_zone` показывает `primary` для зоны, но `applicability` для этой зоны — `NOT_MEASURABLE` или `COARSE_ONLY`.

### 5.2 Где должно быть `INSUFFICIENT_EVIDENCE`, а где `COARSE_ONLY`

`pair_comparison.py` (`compare_packages`):
```python
policy = PosePolicy(DEFAULT_ATLAS_CSV)
compatible, combined_w, reason = policy.is_compatible(zone_id, yaw_a, yaw_b)
gate_status, effective = policy.common_observed_gate(coverage, combined_w)
```

`is_compatible` возвращает `False` если `exclude` или `low combined weight < 0.25`. `common_observed_gate` возвращает:
- `INSUFFICIENT_EVIDENCE` если `coverage < 0.35`
- `NOT_COMPARABLE` если `effective < 0.20`
- `COARSE_ONLY` если `effective < 0.45`
- `USABLE` иначе

Это корректно для `pair` — но не для `individual profile`. Пользователь хочет знать, «один ли это человек» по набору фото. `pair_comparison` сравнивает только **пары**, но не агрегирует в `individual_fingerprint`. Для этого нужен `stage3/individual_identity.py`, которого нет.

---

## 6. PREVIEW VS NUMERIC ARTIFACTS: ГДЕ РАСХОЖДЕНИЯ

### 6.1 Проверенные артефакты

| Артефакт | Тип | Содержимое | Возможное расхождение с preview |
|---|---|---|---|
| `skin/manifest.json` | JSON | `photo_id`, `date`, `pose_bin`, `coordinate_chain` | Не содержит `usable_domain` или `coverage` — только метаданные |
| `skin/previews/atlas_A20_overlay.png` | PNG | Наложение зон (`A==i`) поверх фото | Показывает **geometry**, не `quality` или `applicability` |
| `skin/previews/quality_weight.png` | PNG | Heatmap `quality_weight` (TURBO) | Показывает `quality` после `pw` и `contamination`, но **не показывает** `NOT_OBSERVED` отдельно — просто чёрный |
| `skin/previews/wrinkle_skeleton.png` | PNG | Скелет морщин (`sk`) красным | Только для зон с `sk` > 0; если `w14` пуст или `classical` не нашёл морщин — пустое изображение |
| `skin/previews/wrinkle_ridge_heatmap.png` | PNG | Heatmap `ridge_prob` (TURBO) | Показывает `ridge_prob` для `domain_mask`; если `domain_mask` > 0, но `ridge_prob` = 0 — изображение будет полностью чёрным или очень тёмным, но `atlas_A20_overlay.png` всё равно покажет зону цветной |
| `skin/atlas_projection.npz` | NPZ | `zone_id_a20`, `zone_id_s40`, `wrinkle_membership_w14`, `domain_mask` | **Source of truth** для geometry; но `domain_mask` не учитывает `quality_weight` или `applicability` |
| `skin/quality_maps.npz` | NPZ | `quality_weight`, `effective_resolution`, `focus_transfer`, `noise_survival`, `jpeg_block_map`, `processing_survival` | Source of truth для support; `quality_weight` = 0 для `exclude` зон |
| `skin/features/basic_macro.npz` | NPZ | `zone_level`, `zone_id`, `state`, `effective_support`, `values` | Source of truth для evidence; `state` = `not_measurable` или `usable` |
| `skin/features/texture.npz` | NPZ | 24 метрики; `state` = `usable` или `not_measurable`; `values` содержит `NaN` для `not_measurable` | `values` для `not_measurable` = `NaN`; это важно — `metric_registry` (`build_metric_catalog`) использует `_usable()` (исключает `None`, `NaN`, не конечные числа), но `pair_metrics.csv` может содержать `NaN` или пустые строки |
| `skin/features/summary.json` | JSON | `implemented_families`, `state` | Не содержит `coverage` или `usable_zone_count` |
| `skin/wrinkles/summary.json` | JSON | `classical`: `complete`, `ffhq`: `complete`/`partial`/`not_run` | `state` = `complete` даже если `probability` = 0 для многих зон |
| `skin/quality.json` | JSON | `applicability`, `contamination`, `pose`, `pose_policy` | `pose_policy` содержит `per_zone` с `role` и `weight`; но не содержит `coverage` или `usable_fraction` |

### 6.2 Критическое расхождение: preview шире, чем numeric evidence

**Сценарий:** Пользователь смотрит `atlas_A20_overlay.png` — видит зону `A12` (правая мягкая щека) цветной (например, зелёной или синей). Затем смотрит `quality_weight.png` — видит зону `A12` очень тёмной (почти чёрной). Затем смотрит `wrinkle_ridge_heatmap.png` — видит чёрную область в той же зоне.

**Что это означает:**
- `atlas_A20_overlay.png`: `A==12` в `domain_mask` → геометрия присутствует (`Geometry` = True).
- `quality_weight.png`: `quality_weight` для `A==12` = 0 или очень близко к 0 → `Support` = False (из-за `pose_policy` или `contamination` или `projection_confidence` или `focus`/`exposure`/`noise`).
- `wrinkle_ridge_heatmap.png`: `w14` (wrinkle bits) для `A==12` = False или `ridge_prob` = 0 → `Evidence` для морщин = False.
- `features/texture.npz`: `state` для `A12` = `not_measurable` или `usable` с очень низким `effective_support` → `Evidence` для текстуры может быть `usable`, но с `values` = `NaN` или очень низкими.

**Вывод:** Зона присутствует в `Geometry`, но не даёт `Evidence`. Для журналиста это должно быть явно задокументировано. `quality.json` (`applicability`) содержит `state` = `NOT_MEASURABLE` или `COARSE_ONLY`, но `atlas_A20_overlay.png` не показывает это — она просто показывает зону цветной.

**Это не ошибка кода**, но это **дизайнерская проблема коммуникации**: preview не содержит `disclaimer` о `applicability` или `quality_weight`. Пользователь может ошибочно считать, что «зона видна в preview» = «зона проанализирована».

---

## 7. LEFT/RIGHT CONSISTENCY (симметрия логики)

### 7.1 Проверка симметрии в `pose_policy`

`pose_policy_v3_9bins.csv`:
- `A09` (`NW_L` — левая носовая крыло?): `-60` → `exclude` (0.0), `+60` → `primary` (1.0)
- `A10` (`NW_R` — правая носовая крыло?): `-60` → `primary` (1.0), `+60` → `exclude` (0.0)

Это **зеркально симметрично** для `left_profile` и `right_profile`.

- `A11` (`CB_L` — левая скула?): `-60` → `exclude`, `+60` → `primary`
- `A12` (`CB_R` — правая скула?): `-60` → `primary`, `+60` → `exclude`

Тоже симметрично.

- `A01` (`F00` — лоб): `-60` → `exclude`, `+60` → `primary` (странно — лоб виден в обоих профилях? Но по CSV `A01` исключён для `left_profile` и `primary` для `right_profile`. Это **асимметрия**!)

Подождите — `A01` — это `forehead` (`F00` по `ZONE_SPECS`). Почему `A01` исключён для `left_profile` (`-60`), но `primary` для `right_profile` (`+60`)?

Это странно, но это определено в CSV. Возможно, `A01` — это не `forehead`, а другая зона в другом маппинге. Но в любом случае, `A01` имеет **асимметричную** политику относительно профилей.

Это не обязательно ошибка — возможно, `A01` — это зона, которая физически видна только с одной стороны (например, из-за освещения или угла камеры в конкретном датасете). Но это стоит отметить как **необычное поведение**.

### 7.2 Проверка симметрии в `pipeline.py`

`pipeline.py` использует `PosePolicy` одинаково для `left_profile` и `right_profile` — `pose.get('yaw', 0)` передаётся в `weights()`. Нет специальной обработки `left` или `right` отдельно. Симметрия зависит только от CSV.

### 7.3 Проверка симметрии в `quality.py`

`quality_maps()` не использует `pose` или `yaw` — только `bgr`, `domain`, `incidence`, `projection_confidence`, `triangle_id`, `projected_density_map`. Симметрия на уровне качества обеспечивается только через `pose_policy` (`pw`).

### 7.4 Проверка симметрии в `feature_registry.py`

`REGISTRY` не содержит `pose` или `side` — метрики симметричны по дизайну (`zone_level` = `A20` или `S40`, `zone_id` = конкретная зона). Симметрия на уровне сравнения обеспечивается `pair_comparison` (`compare_packages`), который сравнивает зоны с одинаковыми `zone_id` для обоих фото.

### 7.5 Вывод по симметрии

- `pose_policy` (CSV): **зеркально симметрична** для большинства зон (`A09` vs `A10`, `A11` vs `A12` и т.д.), но `A01` имеет **асимметричную** политику.
- `pipeline`: **симметрична** (нет специальной обработки `left`/`right`).
- `quality_maps`: **симметрична** (не зависит от `yaw`).
- `feature_registry`: **симметрична**.
- `pair_comparison`: **симметрична** (сравнивает одинаковые `zone_id`).

**Асимметрия в `A01` для профилей:** `left_profile` (`-60`) → `exclude`, `right_profile` (`+60`) → `primary`. Если `A01` — это действительно `forehead`, это странно. Но это может быть особенностью конкретного атласа или маппинга (`A01` не обязательно `F00` в этом контексте, хотя `ZONE_SPECS` говорит `zone_id="F00"`).

Это стоит проверить: какой именно `zone_id` соответствует `A01` в `atlas_projection.npz`? Но это требует запуска пайплайна с реальным фото.

---

## 8. SAME-POSE COMPARISON READINESS

### 8.1 Как `pair_comparison` работает для близких yaw

`compare_packages()` (`pair_comparison.py`):
```python
def compare_packages(a,b,min_common=.35):
    policy = PosePolicy(DEFAULT_ATLAS_CSV)
    # ...
    with a.surface() as sa, a.atlas() as aa, b.surface() as sb, b.atlas() as ab:
        for z in range(20):
            c = common_surface(sa, sb, aa, ab, 'A', z)
            compatible, combined_w, reason = policy.is_compatible(zone_id, yaw_a, yaw_b)
            # ...
```

`is_compatible` проверяет `pose_policy` для `yaw_a` и `yaw_b` отдельно. Если оба `primary` или один `primary` + другой `support` — `compatible = True`. Если `exclude` в одном из них — `compatible = False`.

`common_surface()` вычисляет `triangle_ids`, видимые в ОБОИХ фото (`ta >= 0` и `projection_confidence >= 0.2`, и `zone_id` совпадает). `coverage_sym` = площадь общей поверхности / площадь объединения.

**Проблема:** Для двух фото `frontal` с `yaw` = -8° и +5° (`frontal` bin = -10..10):
- `pose_policy` назначает `primary` для всех фронтальных зон (`abs(yaw) <= 25`).
- `is_compatible` возвращает `True`.
- `common_surface()` сравнивает треугольники. Но если `pitch` или `roll` различаются (например, одно фото с наклоном головы вверх, другое — прямо), `projection_confidence` или `visibility` могут быть разными для одних и тех же треугольников.
- `common_surface()` использует `min_conf = 0.2`. Если `projection_confidence` для треугольника < 0.2 в одном фото, он не входит в `ia` или `ib`, даже если `tid >= 0` в обоих.

Это означает: `common_surface()` может быть очень маленьким для двух фото с одинаковым `pose_bin` (`frontal`), но разным `pitch`/`roll`. `pair_metrics.csv` покажет `status = 'INSUFFICIENT_EVIDENCE'` или `'COARSE_DIRECTION_MATCH'` даже для фото, которые визуально «похожи».

**Это правильно с научной точки зрения** (геометрическое несовпадение = недостаточно данных для сравнения), но для пользователя это может выглядеть как «ошибка» или «слишком строгий гейт».

**Критическое замечание:** Нет проверки `pitch`/`roll` в `pose_policy`. Только `yaw` (`pose.get('yaw', 0)`). Это означает, что фото с `frontal` (`yaw = 0`) и `frontal` (`yaw = 0`) с разным `pitch` (например, +20° вверх и -15° вниз) считаются «совместимыми» (`is_compatible = True` для всех зон), но `common_surface()` может показать очень низкую `coverage_sym`. Пользователь может ожидать, что «один ракурс» = «одинаковые условия», но код этого не гарантирует.

### 8.2 Что должно быть `INSUFFICIENT_EVIDENCE`

По коду (`compare_packages`):
```python
if not compatible:
    status = PairStatus.NOT_COMPARABLE.value
elif gate_status == 'INSUFFICIENT_EVIDENCE' or coverage < min_common:
    status = PairStatus.INSUFFICIENT_EVIDENCE.value
elif gate_status == 'COARSE_ONLY':
    status = PairStatus.COARSE_DIRECTION_MATCH.value
else:
    status = PairStatus.PARTIAL_MATCH.value
```

`INSUFFICIENT_EVIDENCE` возникает, когда:
1. `pose_policy.is_compatible` возвращает `False` (`exclude` или `low combined weight < 0.25`).
2. `common_surface` возвращает `coverage < min_common` (по умолчанию `.35`).
3. `pose_policy.common_observed_gate` возвращает `INSUFFICIENT_EVIDENCE` (`coverage_sym < 0.35` или `effective < 0.20`).

**Проблема:** Для профилей (`left_profile`/`right_profile`) `common_surface()` для зон, видимых в обоих фото, будет очень маленьким или нулевым (потому что `pose_policy` назначает `primary` для разных наборов зон). `INSUFFICIENT_EVIDENCE` — это правильный статус. Но `pair_metrics.csv` всё равно содержит строки для таких пар, с `status = 'INSUFFICIENT_EVIDENCE'`. `metric_catalog` (`build_metric_catalog`) считает эти метрики `disabled_missing_data` (если `values` пустые) или `active` (если `values` есть, но `status` = `INSUFFICIENT_EVIDENCE`).

Это может создавать ложное впечатление в `evidence_packets.json` или `pair_details.json`: пара существует, `status` = `INSUFFICIENT_EVIDENCE`, но в `calibrated_metrics` или `evidence_state` это не всегда явно помечено как «нельзя сравнивать».

---

## 9. КРАСНЫЕ ФЛАГИ (FINDING CARDS)

### Найдено: `geometry` есть — `evidence` нет

**Карта 1 (Critical): Profile angles exclude visible-side evidence incorrectly if CSV not loaded**
- **Severity:** Critical / High
- **Reproduce:** Запустить `pipeline.py` с `atlas_path`, указывающим на несуществующий `.npz`. Проверить `quality.json` — ключ `pose_policy` будет `unavailable`. Затем проверить `quality_weight.png` для профиля — зоны, которые должны быть видны (например, `A02` для left_profile), будут иметь `quality_weight` = 0 или очень низкий из-за `_build_default()` (`primary` только при `10..40`, `exclude` при `-60`).
- **Impact:** Для профилей `left_profile` и `right_profile` код может использовать `_build_default()` вместо CSV (`pose_policy_v3_9bins.csv`), что приводит к более жёсткому исключению зон (`exclude` вместо `primary` для некоторых зон). Пользователь видит зоны «исключёнными» в `quality_weight.png`, хотя они должны быть видны (по CSV).
- **Fix:** Убедиться, что `atlas_path` в `pipeline.py` (`run_stage1.py`) указывает на существующий файл `texture_zones_bfm35709_v3.npz` или создать `.npz` из `.json`. Или изменить `pipeline.py` (`line 92`), чтобы использовать абсолютный путь к CSV (`self.root / 'app6' / 'atlas' / 'pose_policy_v3_9bins.csv'`).

**Карта 2 (Critical): Preview `atlas_A20_overlay.png` шире, чем `usable_domain`**
- **Severity:** Medium / High
- **Reproduce:** Запустить пайплайн на любом фото. Сравнить `skin/previews/atlas_A20_overlay.png` (показывает все зоны `A==i` в `domain_mask`) с `skin/features/basic_macro.npz` (показывает `state` = `not_measurable` или `usable`). Зоны с `A==i`, но `state` = `not_measurable`, будут видны в overlay, но не в features.
- **Impact:** Пользователь (журналист) может ошибочно считать, что «зона видна» = «зона проанализирована». В `pair_comparison` эти зоны не участвуют (`INSUFFICIENT_EVIDENCE` или очень низкая `coverage_sym`).
- **Fix:** Добавить `disclaimer` или `overlay` с `applicability` (`usable`/`not_measurable`) в `previews.py`. Или изменить `atlas_A20_overlay.png`, чтобы показывать только зоны с `state == 'usable'` (или с `applicability` != `NOT_OBSERVED`).

**Карта 3 (High): `feature_registry` метрики `local_mad` и другие `microrelief` могут быть `NaN`, но `metric_registry` считает их `usable`**
- **Severity:** Medium / High
- **Reproduce:** Проверить `features/texture.npz` для зоны с `state == 'usable'`, но `values` содержит `NaN` (например, `local_mad` или `log_blob_density`). `metric_registry.py` (`build_metric_catalog`) использует `_usable()` (`not math.isfinite(value)` → `False`). Но `pair_metrics.csv` может содержать `ldm106_rmse` или `texture_image_max_*` даже для пар с `INSUFFICIENT_EVIDENCE`.
- **Impact:** `pair_details.json` или `evidence_packets.json` могут содержать `calibrated_metrics` с `NaN` или `0`, но `status` = `INSUFFICIENT_EVIDENCE`. Для журналиста это не критично, но для автоматизированного анализа (`test_200_self`) это может привести к ложным «одинаковостям».
- **Fix:** Убедиться, что `test_self_identity_200.py` проверяет не только `status`, но и `calibrated_metrics` на `NaN` или очень низкую `coverage_sym`. Или изменить `feature_registry` (`local_features/detector.py`), чтобы возвращать `state = 'not_measurable'` при очень низком `support` или `effective_resolution`.

**Карта 4 (Medium): Same `frontal` pose, разный `pitch`/`roll` — `pair_comparison` считает их совместимыми, но `common_surface` очень маленький**
- **Severity:** Medium
- **Reproduce:** Создать две пары фото с `frontal` (`yaw` ≈ 0°), но разным `pitch` (например, +20° и -15°). Запустить `run_stage2.py`. Проверить `pair_metrics.csv` — `status` может быть `INSUFFICIENT_EVIDENCE` или `COARSE_ONLY`, даже если фото визуально похожи. `pose_policy.is_compatible()` возвращает `True` (потому что `frontal` для обоих), но `common_surface()` показывает очень низкую `coverage_sym` из-за различий в `projection_confidence`.
- **Impact:** Пользователь может ожидать, что «один ракурс» (`frontal`) = «можно сравнивать», но код это не гарантирует. Для `test_200_self` это может привести к ложным «различиям» или «совпадениям» в зависимости от `pitch`/`roll`.
- **Fix:** Добавить `pitch`/`roll` в `pose_policy` или в `pair_comparison`. Или изменить `pair_metrics.csv`, чтобы `status` = `INSUFFICIENT_EVIDENCE` явно содержал `pitch_roll_diff` или `common_surface_low`.

**Карта 5 (Medium): `FFHQ` (`wrinkles/ffhq.npz`) может быть `not_run` или `partial`, но `wrinkle_ridge_heatmap.png` всё равно генерируется**
- **Severity:** Medium
- **Reproduce:** Проверить `wrinkles/summary.json` для фото, где `ffhq` = `'not_run_weights_unavailable'` или `'partial'`. Проверить `wrinkle_ridge_heatmap.png` — если `ffhq_prob` = `None`, код в `previews.py` (`save_wrinkle_overlay`) не записывает `ffhq` overlay, но `wrinkle_skeleton.png` и `wrinkle_ridge_heatmap.png` всё равно генерируются из `classical` (`ridge_prob`).
- **Impact:** Пользователь видит `wrinkle_ridge_heatmap.png` (из `classical`) и может считать, что это «полный анализ морщин», но `FFHQ` не участвовал. Для `pair_comparison` (`match_wrinkle_packages`) это важно: `ffhq` и `classical` сравниваются отдельно.
- **Fix:** Добавить в `wrinkles/summary.json` или `quality.json` явное указание, что `ffhq` отсутствует или частичен. Или изменить `previews.py`, чтобы `wrinkle_ridge_heatmap.png` содержал `disclaimer`, если `ffhq` не полный.

**Карта 6 (Medium): `scikit-image` не интегрирован централизованно в `app6/`**
- **Severity:** Medium / Low (для задачи журналиста — критично для полноты)
- **Reproduce:** Проверить `app6/stage1/skin/texture/features.py` — используется только `cv2` (`cv2.Sobel`, `cv2.GaussianBlur`, `cv2.Laplacian`, `cv2.getGaborKernel`). Нет `skimage.filters.gabor`, `skimage.feature.graycomatrix`, `skimage.filters.sobel_h` или других функций `scikit-image`.
- **Impact:** Для `FFHQ-detect-face-wrinkles` используется `skimage` (в `app.py` или `face_parsing_extraction.py`), но `app6/` использует только `cv2`. Для `feature_registry` (`lbp_entropy`, `glcm_contrast`, `gabor_energy`) это не критично (реализовано вручную через `cv2`), но для полноты анализа (`scikit-image`) это ограничение.
- **Fix:** Интегрировать `scikit-image` в `feature_registry` или `texture/features.py` (например, использовать `skimage.filters.gabor` для более точных фильтров Габора или `skimage.feature.multiscale_basic_features` для дополнительных текстурных метрик). Или добавить `scikit-image` в `requirements` и использовать в `pipeline.py`.

**Карта 7 (Low): `calibration_dataset` содержит данные только для `person_01`, но `stage2/engine.py` использует `calibration_dataset` как `calibration_root`**
- **Severity:** Low
- **Reproduce:** Проверить `calibration_dataset/calibration_datasets/all_calibration_index.csv`. Содержит только `person_01` с `frame_000204` до `frame_000221`. `stage2/engine.py` (`load_calibration`) загружает все `.json` из этого набора.
- **Impact:** Для `test_200_self` или анализа 1999-2026 калибровка будет очень ограниченной (`person_01` — это, вероятно, один субъект). Для журналистского расследования это может быть недостаточно (если исследуется «двойник», нужна калибровка для разных людей или для одного человека в разное время).
- **Fix:** Добавить больше калибровочных наборов в `calibration_dataset` или создать `calibration_self_200` на основе 200 фото пользователя.

---

## 10. PACKAGE-LEVEL SUFFICIENCY (сколько зон реально `usable`)

Для каждого ракурса, на основе `pose_policy_v3_9bins.csv` (180 записей) и `app6/stage1/config.py` (`POSE_BINS`):

| Ракурс | Bin | Примари (1.0) | Поддержка (0.6) | Ограничено (0.25) | Исключено (0.0) | Примечание |
|---|---|---|---|---|---|---|
| `frontal` | 0 | A01-A20 (все 20) | — | — | — | Все зоны видны; `quality_weight` = 1.0 для всех |
| `left_light` | -17.5 (ближайший -10 или -25) | A02, A03, A05, A07, A08, A10, A12, A14, A16, A18, A19, A20 (12 зон) | A01, A06, A09, A11, A13, A15, A17 (7 зон) | — | — | `A01` (`F00`) — поддержка (`0.6`), не исключена |
| `left_mid` | -32.5 (ближайший -25 или -40) | A02, A05, A07, A10, A12, A14, A16, A19, A20 (9 зон) | A03, A08, A18 (3 зоны) | A01, A04, A06, A09, A11, A13, A15, A17 (8 зон) | — | `A01` (`F00`) — ограничена (`0.25`) |
| `left_deep` | -45 (ближайший -40) | A02, A03, A05, A07, A08, A10, A12, A14, A16, A18, A19, A20 (12 зон) | A01, A04, A06, A11, A13, A15, A17 (7 зон) | A09 (1 зона) | — | `A09` (`NW_L`) — ограничена (`0.25`), не исключена |
| `left_profile` | -70 (ближайший -60) | A02, A03, A05, A07, A08, A10, A12, A14, A16, A18, A19, A20 (12 зон) | — | A01, A04, A06, A09, A11, A13, A15, A17 (8 зон) | — | `A01` (`F00`) — исключена (`0.0`); `A09` — исключена (`0.0`) |
| `right_light` | +17.5 (ближайший 10 или 25) | A01, A04, A06, A09, A11, A13, A15, A17, A19, A20 (10 зон) | A02, A03, A05, A07, A08, A10, A12, A14, A16, A18 (10 зон) | — | — | Симметрично `left_light` |
| `right_mid` | +32.5 (ближайший 25 или 40) | A01, A03, A06, A09, A11, A13, A15, A17, A19, A20 (10 зон) | A02, A05, A08, A12, A14, A16, A18 (7 зон) | A04, A07, A10 (3 зоны) | — | Симметрично `left_mid` |
| `right_deep` | +45 (ближайший 40) | A01, A03, A04, A06, A08, A09, A11, A13, A15, A17, A19, A20 (12 зон) | A02, A05, A07, A10, A12, A14, A16, A18 (8 зон) | — | — | `A10` (`NW_R`) — поддержка (`0.6`), не исключена |
| `right_profile` | +70 (ближайший 60) | A01, A04, A06, A09, A11, A13, A15, A17, A18, A19, A20 (11 зон) | — | A02, A03, A05, A07, A08, A10, A12, A14, A16 (9 зон) | — | `A02` (`BR_L`?) — исключена (`0.0`); `A10` (`NW_R`?) — исключена (`0.0`) |

**Важно:** `A01` (`F00`) исключена для `left_profile` (`-60` → 0.0), но `primary` для `right_profile` (+60 → 1.0). Это **асимметрия** в CSV. Если `A01` — это действительно `forehead`, это странно: лоб виден в обоих профилях. Но в CSV `A01` исключён для `left_profile`. Возможно, это связано с конкретной геометрией `3DDFA_V3` или `atlas` (`texture_zones_bfm35709_v3.npz`), где `A01` — это не `forehead`, а другая зона с другим маппингом.

Это стоит проверить: в `atlas_registry.py` (`describe()`): `'A':20`. Но `ZONE_SPECS` содержит 38 зон (`23` анатомические + `13` морщинные + `2` околоротовые). `A20` и `S40` — это не прямое соответствие `ZONE_SPECS`. `A01` в `atlas_projection.npz` соответствует `primary_triangle_zone` из `skin_zone_atlas_triangles.npz`, а не `ZONE_SPECS['F00']`.

Это ещё одно важное наблюдение: `zone_id` в `atlas_projection.npz` (`A01`-`A20`) **не совпадает** напрямую с `zone_id` в `ZONE_SPECS` (`F00`, `BR_L`, `BR_R` и т.д.). `project_atlas()` использует `atlas.A` (20 зон), но `ZONE_SPECS` описывает 38 зон (`kind`: `anatomical_region`, `wrinkle_focus`, `perioral_skin`). `W14` (14 морщинных фокусных зон) соответствует `wrinkle_bits_w14` в `atlas_projection.npz`, а не `A20`.

Это означает: `A01` в `atlas_projection` — это `primary_triangle_zone` из треугольной сетки (`70789` треугольников), а не `F00` из `ZONE_SPECS`. `pose_policy_v3_9bins.csv` использует `A01`-`A20`, что соответствует `A20` уровню атласа, а не `ZONE_SPECS`. Для журналиста это важно: `A01` — это не обязательно «лоб» (`F00`), а может быть другая анатомическая область, определяемая треугольной сеткой.

---

## 11. VERDICT (ГОТОВНОСТЬ)

### 11.1 Общий вердикт

**Status:** `ready with gates` (готов с ограничениями и гейтами).

**Что готово:**
- `mask` (`face_mask.npz`) — работает.
- `atlas/projection` (`atlas_projection.npz`) — работает; `domain_mask` корректен.
- `quality` (`quality_maps.npz`, `quality.json`) — работает; `applicability` корректна для `macro_texture` и `wrinkles`.
- `features` (`basic_macro.npz`, `texture.npz`) — работает; `state` корректно отражает `usable`/`not_measurable`.
- `wrinkles` (`classical.npz`, `ffhq.npz`) — работает (если модели доступны).
- `pair_comparison` (`compare_packages`) — работает для `usable` зон; `INSUFFICIENT_EVIDENCE` правильно возвращается для `exclude` или низкой `coverage`.

**Что не готово или ограничено:**
- `scikit-image` не интегрирован централизованно (`feature_registry` использует `cv2`, а не `skimage`).
- `individual_fingerprint` (`stage3/individual_identity.py`) — отсутствует. `pair_comparison` работает, но не агрегирует в «одного человека».
- `test_200_self` (`tests/test_self_identity_200.py`, `tests/dataset_200_self/`) — отсутствует.
- `pose_policy` (`pipeline.py`, строка 92) загружает CSV относительно `atlas_path`. Если `.npz` отсутствует или путь неверен — используется `_build_default()` с другими весами. Это **критический баг** для профилей.
- `A01` в `atlas_projection` (`A20`) не совпадает с `F00` из `ZONE_SPECS`. `pose_policy` работает с `A01`-`A20`, но `feature_registry` использует `zone_level` = `A20` или `S40`. Для пользователя (`журналист`) это может быть неочевидно.
- `preview` (`atlas_A20_overlay.png`) шире `usable_domain` — показывает зоны, которые в `evidence` (`features`) = `NOT_MEASURABLE` или `NOT_OBSERVED`. Нет `disclaimer`.
- `same-pose comparison` (`frontal` с разным `pitch`/`roll`) — `pair_comparison` не учитывает `pitch`/`roll`; `common_surface` может быть очень маленьким, но `is_compatible` возвращает `True`.
- `wrinkle_ridge_heatmap.png` — генерируется даже если `ffhq` = `not_run`. Пользователь может считать, что это «полный анализ морщин».

### 11.2 Какие ракурсы пригодны для `skin/cheek comparison`

| Ракурс | Пригодность для сравнения кожи/щеки | Причина |
|---|---|---|
| `frontal` | **Полностью пригоден** (`usable` для всех 20 зон) | `primary` для всех `A20`; `quality_weight` = 1.0; `applicability` = `usable` или `coarse_only` |
| `left_light` / `right_light` | **Пригоден с ограничениями** (`usable` для ~12-14 зон) | `primary` или `support` для большинства; `limited` или `exclude` для некоторых (`A01`, `A04`, `A06` и т.д.) |
| `left_mid` / `right_mid` | **Ограниченно пригоден** (`usable` для ~9-10 зон) | `primary` для ~9 зон; `limited` или `exclude` для остальных |
| `left_deep` / `right_deep` | **Ограниченно пригоден** (`usable` для ~9-12 зон, но с `limited`) | `primary` для ~9-12 зон; некоторые (`A09`, `A11`) = `limited` или `exclude` |
| `left_profile` / `right_profile` | **Не пригоден для полного сравнения** (`usable` для ~11-12 зон, но другой набор для каждого профиля) | Для `left_profile`: `primary` для правых зон (`A02`, `A03`, `A05`, `A07`, `A08`, `A10`, `A12`, `A14`, `A16`, `A18`, `A19`, `A20`); `exclude` для левых (`A01`, `A04`, `A06`, `A09`, `A11`, `A13`, `A15`, `A17`). Для `right_profile`: наоборот. `common_surface` между `left_profile` и `right_profile` = очень маленький или ноль. `INSUFFICIENT_EVIDENCE` — правильный статус. |

### 11.3 Какие preview нельзя показывать без `numeric disclaimer`

- `atlas_A20_overlay.png`: всегда показывает `domain_mask` (геометрия), независимо от `applicability` или `quality_weight`. Должен содержать `disclaimer`: «Зоны с `NOT_OBSERVED` или `NOT_MEASURABLE` показаны, но не используются в `evidence`».
- `quality_weight.png`: показывает `quality_weight` = 0 для `exclude` зон (чёрный). Без контекста это может быть непонятно. Должен содержать `legend`: «Чёрный = `exclude` (`pose_policy`) или `quality` = 0 (`focus` < 0.12, `projection` < 0.2, `contamination`)».
- `wrinkle_ridge_heatmap.png`: генерируется даже если `ffhq` = `not_run`. Должен содержать `disclaimer`: «Только `classical` (`frangi`/`meijering`/`skan`). `FFHQ` отсутствует или частичен».
- `wrinkle_skeleton.png`: показывает `sk` (скелет) для `classical`. Без `disclaimer` о `FFHQ` это может вводить в заблуждение.

---

## 12. FINDING CARDS (СВЕРНУТО)

### Карта 1: Profile `left_profile` / `right_profile` — `A01` (`F00`?) исключена асимметрично
- **Severity:** Medium
- **Reproduce:** `python -c "from app6.stage1.skin.pose_policy import PosePolicy; p=PosePolicy('app6/atlas/pose_policy_v3_9bins.csv'); print('A01 at -60:', p.get('A01', -60)); print('A01 at +60:', p.get('A01', 60))"`
- **Impact:** `A01` исключена для `left_profile`, но `primary` для `right_profile`. Если `A01` = `forehead`, это странно. Но это определено в CSV. Для журналиста это не критично, но должно быть задокументировано.
- **Fix:** Проверить маппинг `A01` в `atlas_projection.npz` (сравнить `primary_triangle_zone` с `ZONE_SPECS`). Или изменить CSV, если это ошибка.

### Карта 2: `pipeline.py` (`line 92`) — `atlas_path` → `pose_policy_v3_9bins.csv` может не загружаться
- **Severity:** Critical
- **Reproduce:** Установить `atlas_path` в `pipeline.py` (`run_stage1.py`) на несуществующий файл или на путь без `.npz`. Проверить `quality.json` — `pose_policy` = `unavailable`. Проверить `quality_weight.png` для профиля — зоны, которые должны быть `primary` (по CSV), будут `exclude` или `limited` (по `_build_default`).
- **Impact:** Пользователь (`журналист`) видит зоны «исключёнными» на рендере, хотя по CSV они должны быть видны. Это приводит к ложной уверенности в «недостаточности данных» или «отсутствии морщин».
- **Fix:** В `pipeline.py` (`line 92`): использовать абсолютный путь к CSV (`self.root / 'app6' / 'atlas' / 'pose_policy_v3_9bins.csv'`) или проверить существование файла перед загрузкой и выдать ошибку, если `.npz` или CSV отсутствуют.

### Карта 3: `preview` (`atlas_A20_overlay.png`, `quality_weight.png`, `wrinkle_ridge_heatmap.png`) шире `usable_domain`
- **Severity:** High
- **Reproduce:** Запустить пайплайн. Сравнить `skin/previews/atlas_A20_overlay.png` (показывает `A==i`) с `skin/features/basic_macro.npz` (`state` = `usable`/`not_measurable`). Найти зоны с `A==i` в overlay, но `state` = `not_measurable` в features. Сравнить `quality_weight.png` (`quality_weight` = 0 для этих зон) с `atlas_A20_overlay.png` (зона видна).
- **Impact:** Журналист может ошибочно считать, что «зона видна» = «проанализирована».
- **Fix:** Добавить в `previews.py` (`save_previews`) наложение `applicability` (`state`) поверх зоны (`A==i`) или изменить `atlas_A20_overlay.png`, чтобы показывать только зоны с `usable` или `coarse_only`.

### Карта 4: Same `frontal` pose, разный `pitch`/`roll` — `pair_comparison` считает совместимым, но `common_surface` очень маленький
- **Severity:** Medium
- **Reproduce:** Создать две пары фото с `frontal` (`yaw` ≈ 0°), но `pitch` = +20° и `pitch` = -15°. Запустить `run_stage2.py`. Проверить `pair_metrics.csv` — `status` = `INSUFFICIENT_EVIDENCE` или `COARSE_ONLY`, хотя `pose_policy.is_compatible()` = `True` для всех зон.
- **Impact:** Для `test_200_self` или анализа хронологии это может привести к ложным «различиям» или «отсутствиям данных» при сравнении фото с одинаковым `frontal`, но разным наклоном головы (например, фото с 1999 года сделано с камерой ниже, а фото с 2026 — с камерой выше).
- **Fix:** Добавить `pitch`/`roll` в `pose_policy` или в `pair_comparison` (`compare_packages`). Или изменить `pair_metrics.csv`, чтобы `status` содержал `pitch_roll_diff` или `common_surface_low`.

### Карта 5: `scikit-image` не интегрирован в `feature_registry`
- **Severity:** Low / Medium (для полноты)
- **Reproduce:** Проверить `app6/stage1/skin/texture/features.py`. Используются только `cv2` функции. Нет `skimage.filters.gabor`, `skimage.feature.graycomatrix`, `skimage.filters.sobel_h` или других.
- **Impact:** Для `feature_registry` (`lbp_entropy`, `glcm_contrast` и т.д.) это не критично (реализовано вручную). Но для полноты анализа (`scikit-image` упоминается в запросе пользователя как одна из библиотек в связке) это ограничение.
- **Fix:** Интегрировать `scikit-image` в `texture/features.py` или `feature_registry.py`. Или добавить в `requirements.txt` и использовать для дополнительных метрик (`skimage.feature.multiscale_basic_features` или `skimage.filters.gabor`).

### Карта 6: `calibration_dataset` ограничен (`person_01` только)
- **Severity:** Low (для журналиста — критично для достоверности)
- **Reproduce:** Проверить `calibration_dataset/calibration_datasets/all_calibration_index.csv`. Только `person_01` с `frame_000204` до `frame_000221`.
- **Impact:** Для `test_200_self` или анализа 1999-2026 калибровка (`CalibrationModel`, `PointNoiseModel`, `DescriptorNoiseModel`) будет очень ограниченной. `calibration_sensitivity` (`leave_one_dataset_sensitivity`) может показать очень высокую чувствительность из-за малого набора.
- **Fix:** Добавить калибровочные данные для других людей или для 200 фото (`tests/dataset_200_self/`) в `calibration_dataset`.

---

## 13. ЧТО НУЖНО ДЛЯ АВТОМАТИЗИРОВАННЫХ ТЕСТОВ

На основе этого аудита, для предотвращения возврата проблем (`regression tests`):

1. **`tests/test_projection_domain.py`:** Проверить, что `atlas_projection.npz` содержит `domain_mask` и `zone_id_a20` для каждого фото. Проверить, что `domain_mask.sum()` соответствует ожидаемому для `frontal` (максимум) и `profile` (меньше).
2. **`tests/test_pose_policy_load.py`:** Проверить, что `PosePolicy` загружает CSV (`pose_policy_v3_9bins.csv`) и не использует `_build_default()` (проверить `policy.rows` содержит 180 записей и `A01` имеет `primary` для `0`, не `exclude`).
3. **`tests/test_applicability_state.py`:** Для каждого `POSE_BINS` (`frontal`, `left_profile` и т.д.) создать тестовое фото или использовать `calibration_dataset`. Проверить `quality.json` (`applicability`) для каждой зоны (`A20`). Убедиться, что `NOT_OBSERVED` или `NOT_MEASURABLE` соответствует `pose_policy` (`exclude` или `limited` с очень низким `effective_resolution`).
4. **`tests/test_preview_truth.py`:** Сравнить `previews/atlas_A20_overlay.png` с `features/basic_macro.npz` (`state`). Найти зоны с `A==i` в overlay, но `state` = `not_measurable` в features. Убедиться, что это ожидаемое поведение (из-за `pose_policy` или `quality_weight` = 0) и не ошибка.
5. **`tests/test_same_pose_pitch_roll.py`:** Создать пары фото с одинаковым `frontal` (`yaw` ≈ 0), но разным `pitch` или `roll`. Проверить `pair_metrics.csv` — `status` должен быть `INSUFFICIENT_EVIDENCE` или `COARSE_ONLY`, если `common_surface` очень маленький (`coverage_sym < 0.35`). Убедиться, что `is_compatible` = `True`, но `common_observed_gate` возвращает `INSUFFICIENT_EVIDENCE`.
6. **`tests/test_individual_identity_200.py`:** Запустить на `tests/dataset_200_self/` (если создан). Проверить `app6/stage3/individual_identity.py` (если создан). Убедиться, что `same_person_probability` > 0.9 для фото одного человека и < 0.5 для разных людей.
7. **`tests/test_left_right_symmetry.py`:** Для `left_profile` и `right_profile` проверить симметрию `pose_policy` (например, `A09` (`NW_L`) при `-60` = `exclude`, `+60` = `primary`; `A10` (`NW_R`) при `-60` = `primary`, `+60` = `exclude`). Проверить, что `pipeline.py` (`build_skin_package`) использует `pose_policy` одинаково для `left_profile` и `right_profile` (без специальной обработки `left` или `right`).

---

## 14. КОРОТКИЙ BRIEF ДЛЯ ОТПРАВКИ

**Вердикт:** `ready with gates` (готов с ограничениями).

**Готово:** `mask` → `atlas/projection` (`domain_mask` корректен) → `pose/quality gates` (`applicability` корректна для `macro_texture`, `wrinkles`) → `features` (`basic_macro`, `texture` с `NaN` для `not_measurable`) → `pair_comparison` (`INSUFFICIENT_EVIDENCE` для `exclude`, `COARSE_ONLY` для `limited`).

**Не готово / ограничено:**
- `individual_fingerprint` (`stage3`) отсутствует.
- `test_200_self` (`tests/dataset_200_self/`, `test_self_identity_200.py`) отсутствует.
- `scikit-image` не интегрирован централизованно.
- `pipeline.py` (`line 92`) загружает CSV относительно `atlas_path`; если `.npz` отсутствует — используется `_build_default()` с другими весами (`exclude` для профилей вместо `primary`).
- `preview` (`atlas_A20_overlay.png`, `quality_weight.png`, `wrinkle_ridge_heatmap.png`) шире `usable_domain` — показывает `geometry`, а не `evidence`. Нет `disclaimer`.
- `same-pose comparison` (`frontal` с разным `pitch`/`roll`) — `is_compatible` = `True`, но `common_surface` может быть очень маленьким (`INSUFFICIENT_EVIDENCE`).
- `calibration_dataset` ограничен (`person_01` только).
- `A01` в `pose_policy_v3_9bins.csv` имеет **асимметричную** политику (`left_profile` = `exclude`, `right_profile` = `primary`).

**Что критично для пользователя (журналиста-расследователя):**
- Для `left_profile` или `right_profile`: около 50% зон `A20` исключены (`weight` = 0.0) или ограничены (`0.25`). Это физически верно, но `pair_comparison` (`compare_packages`) будет возвращать `INSUFFICIENT_EVIDENCE` или очень низкую `coverage_sym`. Для анализа «двойников» через `pair_comparison` это означает, что профили нельзя сравнивать напрямую — только через `frontal` или `light` (`left_light`/`right_light`).
- Для `frontal`: все 20 зон `usable`, но `pitch`/`roll` могут снизить `common_surface` без изменения `pose_policy` (`is_compatible` = `True`).
- `preview` (`atlas_A20_overlay.png`) показывает зоны, которые в `evidence` (`features/basic_macro.npz`) = `not_measurable`. Пользователь должен проверять `quality.json` (`applicability`) или `features/basic_macro.npz` (`state`), а не только `preview`.

**Рекомендация для следующей сессии:**
1. Исправить `pipeline.py` (`line 92`): использовать абсолютный путь к CSV или добавить проверку существования `.npz` и CSV.
2. Добавить `tests/test_projection_domain.py`, `tests/test_pose_policy_load.py`, `tests/test_applicability_state.py`, `tests/test_preview_truth.py`, `tests/test_same_pose_pitch_roll.py`.
3. Создать `tests/dataset_200_self/` и `tests/test_self_identity_200.py`.
4. Добавить `app6/stage3/individual_identity.py` (агрегатор `skin fingerprint`).
5. Добавить `pipeline_audit/` (уже создан: `check_projection.py`, `check_metrics_identity.py`, `check_zone_coverage.py`, `check_profile_zones.py`) в автоматизированные тесты (`pytest`).
6. Добавить `scikit-image` в `feature_registry` или `pipeline` для полноты (`texture/features.py`).
7. Добавить `calibration_dataset` для `test_200_self` или расширить `calibration_dataset`.
8. Добавить `disclaimer` в `previews.py` (`atlas_A20_overlay.png`, `quality_weight.png`, `wrinkle_ridge_heatmap.png`) или изменить `previews` для отображения только `usable` зон.

---

*Этот аудит выполнен независимо, только по коду (`facproject/app6/`, `3ddfa_v3/`, `FFHQ-detect-face-wrinkles/`, `calibration_dataset/`). Все выводы основаны на чтении исходного кода (`pipeline.py`, `projection.py`, `quality.py`, `feature_registry.py`, `pose_policy.py`, `previews.py`, `pair_comparison.py`, `engine.py`, `metric_registry.py`, `contracts.py`). Формулировки пользователя сохранены. Анализ не содержит политической оценки.*
