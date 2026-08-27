# Анализ потока данных: что генерируется, что теряется, что не подходит журналисту

**Дата:** 2026-08-27
**Объект:** Stage 2 → Stage 2B → Stage 3 → API → UI → Журналист

---

## 1. ПОЛНАЯ КАРТА АРТЕФАКТОВ (что генерируется после Stage 1)

### Stage 2 генерирует ~40 файлов:

| # | Файл | Размер | Доходит до Stage 3? | Доходит до журналиста? |
|---|------|--------|---------------------|----------------------|
| 1 | `pair_metrics.csv` | 186-222 столбца | ✅ Частично | ⚠️ Сырые таблицы |
| 2 | `zone_metrics.csv` | per-zone RMSE | ✅ Да | ⚠️ Сырые таблицы |
| 3 | `change_points.json` | кандидаты изменений | ✅ Да | ⚠️ Технический формат |
| 4 | `analysis_manifest.json` | метаданные прогона | ✅ Да | ❌ Не читается |
| 5 | `analysis_validation.json` | контракт | ✅ Да (проверка) | ❌ Не виден |
| 6 | `evidence_packets.json` | полные evidence | ✅ Частично | ❌ Не видны |
| 7 | `calibration_noise_model.json` | вся null-модель | ❌ Нет | ❌ Полностью потерян |
| 8 | `calibration_sensitivity.json` | LOPO sensitivity | ❌ Нет | ❌ Полностью потерян |
| 9 | `calibration_consistency.json` | consistency check | ❌ Нет | ❌ Полностью потерян |
| 10 | `mesh_noise_model.json` | mesh noise | ❌ Нет | ❌ Полностью потерян |
| 11 | `alpha_chronology.json` | alpha drift | ❌ Нет | ❌ Полностью потерян |
| 12 | `baseline_return.json` | returns A→B→A | ❌ Нет | ❌ Полностью потерян |
| 13 | `cumulative_drift.json` | CUSUM drift | ❌ Нет | ❌ Полностью потерян |
| 14 | `cross_bin_corroboration.json` | cross-bin support | ❌ Нет | ❌ Полностью потерян |
| 15 | `event_aggregation.csv` | aggregated events | ❌ Нет | ❌ Полностью потерян |
| 16 | `pose_leakage_diagnostic.json` | pose leakage | ❌ Нет | ❌ Полностью потерян |
| 17 | `multiple_testing.json` | FDR details | ❌ Нет | ❌ Полностью потерян |
| 18 | `metric_catalog.json` | 13+ families | ✅ Да | ❌ Технический |
| 19 | `manual_review_queue.csv` | priority queue | ❌ Нет | ❌ Полностью потерян |
| 20 | `public_safety_report.json` | forbidden terms | ❌ Нет | ❌ Полностью потерян |
| 21 | `degraded_modules.json` | what's degraded | ❌ Нет | ❌ Полностью потерян |
| 22 | `mesh_shape_summary.csv` | mesh shapes | ❌ Нет | ❌ Полностью потерян |
| 23 | `texture_summary.json` | texture stats | ❌ Нет | ❌ Полностью потерян |
| 24 | `status_summary.csv` | status distribution | ❌ Нет | ❌ Полностью потерян |
| 25 | `gate_report.json` | readiness gates | ❌ Нет | ❌ Полностью потерян |
| 26 | `stage3_input_summary.json` | top pairs | ❌ Нет | ❌ Полностью потерян |
| 27 | `skipped_pairs.csv` | excluded pairs | ❌ Нет | ❌ Полностью потерян |
| 28 | `quality_zone_pair_coverage.csv` | quality zones | ❌ Нет | ❌ Полностью потерян |
| 29 | `texture_pair_metrics.csv` | texture pairs | ❌ Нет | ❌ Полностью потерян |
| 30 | `texture_zone_metrics.csv` | texture zones | ❌ Нет | ❌ Полностью потерян |
| 31 | `mesh_pair_metrics.csv` | mesh pairs | ❌ Нет | ❌ Полностью потерян |
| 32 | `zone_map.json` | zone mapping | ❌ Нет | ❌ Полностью потерян |
| 33 | `lead_registry.json` | prior leads | ✅ Да | ⚠️ Технический |
| 34 | `lead_coverage.csv` | lead coverage | ❌ Нет | ❌ Полностью потерян |
| 35 | `technical_summary.json` | tech summary | ❌ Нет | ❌ Полностью потерян |
| 36 | `photo_analysis/*.json` | per-photo data | ❌ Нет | ❌ Полностью потерян |
| 37 | `chronology_rate_model.json` | rate refs | ❌ Нет | ❌ Полностью потерян |
| 38 | `evidence_chain_manifest.json` | chain manifest | ❌ Нет | ❌ Полностью потерян |
| 39 | `artifact_index.json` | file index | ❌ Нет | ❌ Полностью потерян |
| 40 | `*_motion.npz` (per-pair) | 134-point vectors | ✅ Да (top 40) | ⚠️ SVG визуализация |

### Stage 2B генерирует:
- Корроборация с prior leads
- Покрытие старыми зацепками
- (Не создаёт новых данных — только аннотации)

### Stage 3 генерирует 8 файлов:
- `report_sections/summary.json` — счётчики
- `report_sections/narrative.json` — 6 параграфов
- `report_sections/timelines.json` — per-bin SVG
- `report_sections/motion_maps.json` — top 40 пар
- `report_sections/change_points.json` — кандидаты
- `report_sections/zones.json` — зонные метрики
- `report_meta.json` — мета отчёта
- `report_validation.json` — валидация

---

## 2. ЧТО ТЕРЯЕТСЯ (32 из 40 файлов не доходят до журналиста)

### 2.1. Калибровочные данные (полностью потеряны для журналиста)
**Файлы:** `calibration_noise_model.json`, `calibration_sensitivity.json`, `calibration_consistency.json`, `mesh_noise_model.json`

**Что в них:**
- Полная null-модель шума: per-bin per-zone per-metric median/MAD/P95/P99
- LOPO sensitivity: как меняется результат при удалении одного человека
- Calibration consistency: все ли калибровочные лица — один человек
- 7 датасетов × 9 бинов × N метрик = сотни чисел

**Почему это важно для журналиста:**
Журналист не видит **«насколько надёжна норма»**. Если калибровка нестабильна (LOPO показывает большой разброс), все выводы становятся менее надёжными. Но журналист об этом не узнает.

**Что нужно:** Одна строка в карточке пары: *«Надёжность калибровки: высокая / средняя / низкая — на основе LOPO sensitivity»*

### 2.2. Временные анализы (полностью потеряны)
**Файлы:** `alpha_chronology.json`, `baseline_return.json`, `cumulative_drift.json`, `chronology_rate_model.json`, `event_aggregation.csv`

**Что в них:**
- Alpha drift: меняется ли alpha_id (BFM identity coefficients) во времени
- Baseline return: пары A→B→A (возврат к прежнему состоянию)
- CUSUM drift: постепенное накопление малых изменений
- Chronology rate: скорость изменений, same-day conflicts
- Event aggregation: агрегированные события

**Почему это важно для журналиста:**
Это **основной материал для расследования**: когда лицо начало меняться, были ли возвраты, накапливаются ли изменения. Но журналист получает только `chronology_rate_status` в pair_metrics.csv — без контекста, без истории, без агрегации.

**Что нужно:** Timeline narrative: *«С 2004 по 2007: 3 пары с rapid change. 2008: возврат к прежнему состоянию. С 2012: устойчивый сдвиг.»*

### 2.3. Cross-bin corroboration (полностью потеряна)
**Файл:** `cross_bin_corroboration.json`

**Что в нём:**
- Для каждого кандидата — в скольких других ракурсах виден тот же сигнал
- Independent source count
- Cross-bin support pose count

**Почему это важно для журналиста:**
**Это главный фильтр надёжности.** Сигнал в 1 ракурсе — слабо. В 3 ракурсах — сильно. Но журналист видит только `cross_bin_corroboration_status` — одну строку без деталей.

**Что нужно:** В карточке наблюдения: *«Подтверждено в 3 ракурсах: frontal, left_light, right_profile»*

### 2.4. Pose leakage diagnostic (полностью потерян)
**Файл:** `pose_leakage_diagnostic.json`

**Что в нём:**
- Корреляция pose_distance с каждой метрикой
- Flagged metrics (где корреляция > порога)
- Pose leakage limited pair count

**Почему это важно:**
Журналист не знает, какие «аномалии» могут быть просто разными ракурсами. Без этой информации легко сделать ложный вывод.

### 2.5. FDR и multiple testing (полностью потеряны)
**Файл:** `multiple_testing.json`

**Что в нём:**
- Test count, effective test count
- Dependence inflation factor
- Significant count per threshold
- Method description

**Почему это важно:**
Журналист не знает, сколько из «значимых» результатов — случайные находки из-за множественного тестирования.

### 2.6. Manual review queue (полностью потерян)
**Файл:** `manual_review_queue.csv`

**Что в нём:**
- Все кандидаты, отсортированные по приоритету ручной проверки
- Priority score на основе p95_z, mesh_z, baseline_return, quality
- Review reason

**Почему это важно:**
**Это готовая очередь работы для журналиста.** Но она теряется между Stage 2 и Stage 3.

### 2.7. Skipped pairs (полностью потеряны)
**Файл:** `skipped_pairs.csv`

**Что в нём:**
- Пары которые были запланированы, но не измерены
- Причины: pose_mismatch, insufficient_visibility, expression_gate

**Почему это важно:**
Журналист видит «найдено 18 кандидатов», но не видит что 4503 пары не были измерены из-за недостаточной калибровки. «Мало кандидатов ≠ мало изменений».

### 2.8. Photo analysis (полностью потерян)
**Файлы:** `photo_analysis/*.json` (per-photo)

**Что в них:**
- Для каждого фото: date, pose_bin, related pairs
- Связи между фото и парами

**Почему это важно:**
Это **карточка фото** — то что ТЗ прямо требует как «Уровень 2». Данные есть, но не доходят.

### 2.9. Evidence packets (частично теряются)
**Файл:** `evidence_packets.json`

**Что в них:**
- Полная структура evidence для каждой пары
- Alternative explanations
- Source files (motion_file, source_digest, source_url)
- Registered metric channel

**Что доходит до Stage 3:**
Stage 3 читает только `evidence_state` из pair_metrics.csv. Полный evidence packet не передаётся в отчёт.

---

## 3. ЧТО ДОХОДИТ, НО В НЕПРАВИЛЬНОМ ФОРМАТЕ

### 3.1. pair_metrics.csv — 186-222 столбца
**Проблема:** Журналист получает огромную таблицу с техническими полями:
`p95_point_z`, `significant_point_fraction`, `coherent_motion_fraction`, `calibrated_point_count`, `mt_p_approx`, `mt_q_value`, `mesh_rmse`, `mesh_p95`, `mesh_point_to_plane_rmse`, `descriptor_top_families`, `chronology_rate_z`, `biological_rate_status`...

**Что нужно журналисту:**
- Одно число: уровень уверенности (low/medium/high)
- Одна фраза: что изменилось
- Один список: чем это объясняется ещё

### 3.2. Narrative — 6 общих параграфов о методе
**Проблема:** Все 6 параграфов — о методе, не о конкретных находках:
1. «Исследование охватывает N фотографий»
2. «Для каждой пары движение 134 точек сопоставлено с...»
3. «Архив прежних зацепок содержит...»
4. «Помимо движения точек проверяются 13 локальных семейств...»
5. «Найдено N соседних пар с аномальным темпом...»
6. «Ни один статус не доказывает подмену...»

**Что нужно журналисту:**
- Narrative по эпохам
- Narrative по конкретным наблюдениям
- Narrative по конкретным парам

### 3.3. Timelines — SVG per-bin без контекста
**Проблема:** График показывает p95_point_z по времени, но:
- Нет калибровочного статуса пары
- Нет уровней уверенности
- Нет аннотаций
- Нет событий/эпох

### 3.4. Change points — технический формат
**Проблема:** Каждый change point содержит:
`pair_id, pair_type, pose_bin, date, photo_a, photo_b, status, p95_point_z, significant_point_fraction, coherent_motion_fraction, days_delta, chronology_rate_status, chronology_rate_z, cross_bin_corroboration_status, cross_bin_support_pose_count`

**Что нужно журналисту:**
*«2007-03-15: скуловая область сместилась вверх-наружу. Сигнал выше шума в 4.2 раза. Подтверждён в 2 ракурсах. Уверенность: средняя.»*

---

## 4. ЧТО UI ПОКАЗЫВАЛ, НО ЖУРНАЛИСТУ НЕ НУЖНО

### 4.1. Raw landmark coordinates
API: `/photos/{id}/landmarks/{count}/{space}`
UI: 3D viewer с точками
**Журналисту:** Не нужны координаты, нужно описание изменения

### 4.2. Full mesh data
API: `/photos/{id}/mesh`, `/compare/full_mesh`
UI: 3D mesh viewer
**Журналисту:** Не нужны 35709 вершин, нужны зоны лица

### 4.3. Per-zone raw RMSE
Stage 2: `zone_metrics.csv` с raw RMSE по зонам
**Журналисту:** Не нужен RMSE=0.0046, нужно *«переносица шире на 2мм»*

### 4.4. Calibration noise model details
API: `/calibration/noise_model`
**Журналисту:** Не нужны per-bin per-zone median/MAD, нужна одна строка надёжности

### 4.5. Texture/UV данные
Stage 2: `texture_pair_metrics.csv`, `texture_zone_metrics.csv`
**Журналисту:** Correctly excluded из Stage 3 (политика). Но UI показывал.

### 4.6. Technical quality scores
`alignment_quality`, `reprojection_p95`, `detection_confidence`
**Журналисту:** Не нужны числа, нужен статус *«качество фото: хорошее/среднее/плохое»*

---

## 5. API ЭНДПОИНТЫ КОТОРЫЕ НЕ ИСПОЛЬЗУЮТСЯ В ОТЧЁТЕ

| Эндпоинт | Данные | Почему потерян |
|----------|--------|---------------|
| `/calibration/health` | Health of calibration | Stage 3 не читает |
| `/calibration/match` | Matching calibration frames | Stage 3 не читает |
| `/calibration/subtract_noise` | Noise-compensated metrics | Результат не сохраняется |
| `/compare` | On-demand pair comparison | Stage 3 использует pre-computed |
| `/compare/full_mesh` | Full mesh comparison | Stage 3 не использует |
| `/photos/{id}/skin_zones` | Skin zone analysis | Stage 3 не читает |
| `/zones/catalog` | Zone catalog (21 zones) | Stage 3 не использует |
| `/review` | Manual review decisions | Нет связи с Stage 3 |

---

## 6. СВОДКА: РАЗРЫВ МЕЖДУ ДАННЫМИ И ЖУРНАЛИСТОМ

### Данные которые ЕСТЬ но НЕ доходят (32 файла):
- 4 калибровочных файла → потеряна надёжность нормы
- 5 временных файлов → потеряна хронология изменений
- 1 cross-bin файл → потеряна корроборация
- 1 pose leakage файл → потеряна защита от артефактов ракурса
- 1 FDR файл → потерян контроль ложных открытий
- 1 review queue → потерян приоритет работы
- 1 skipped pairs → потеряна полнота покрытия
- N photo analysis → потеряны карточки фото
- Остальное: texture, mesh, quality, status summaries

### Данные которые доходят но БЕСПОЛЕЗНЫ в текущем формате:
- pair_metrics.csv: 186+ столбцов → нужна агрегация в тезисы
- zone_metrics.csv: raw RMSE → нужны анатомические описания
- change_points.json: технические поля → нужны narrative блоки
- timelines: SVG без контекста → нужны аннотированные эпохи
- narrative: 6 общих параграфов → нужны per-observation тезисы

### Данные которые НУЖНЫ журналисту но НЕ СУЩЕСТВУЮТ:
- Карточка эпохи с трендами/всплесками/опровержениями
- Карточка фото с одной строкой вывода
- Карточка пары с 3-шаговым текстом
- Сквозное наблюдение с ID и биографией
- Уровень уверенности (5-уровневая шкала)
- Список обязательных альтернативных объяснений
- Список задач для ручной проверки

---

## 7. ВЫВОД: ЧТО НУЖНО ПОСТРОИТЬ

**Мост между Stage 2 и журналистом — это НЕ новый Stage 3, а трансформатор данных:**

```
Stage 2 (40 файлов) → ТРАНСФОРМАТОР → Журналистский каркас
                    ↓
         ┌─────────────────────────────────┐
         │ 1. Агрегатор калибровки          │
         │    → «надёжность: высокая»       │
         │                                  │
         │ 2. Агрегатор времени             │
         │    → эпохи, тренды, возвраты     │
         │                                  │
         │ 3. Агрегатор corroboration       │
         │    → «подтверждено в 3 ракурсах» │
         │                                  │
         │ 4. Генератор наблюдений          │
         │    → НАБЛ-001 с биографией       │
         │                                  │
         │ 5. Генератор тезисов             │
         │    → 3-шаговый текст пары        │
         │                                  │
         │ 6. Генератор уверенности         │
         │    → 5-уровневая шкала           │
         │                                  │
         │ 7. Генератор альтернатив         │
         │    → обязательный список         │
         └─────────────────────────────────┘
```

Этот трансформатор читает все 40 файлов Stage 2 и производит 4 уровня отчёта по ТЗ:
- Уровень 0: Базовая линия
- Уровень 1: Эпохи
- Уровень 2: Карточки фото
- Уровень 3: Карточки пар + наблюдения
