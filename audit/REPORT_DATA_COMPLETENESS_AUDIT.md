# 🎯 АУДИТ: ДОХОДЯТ ЛИ ВСЕ ДАННЫЕ ДО ЖУРНАЛИСТА ПО ЭТАПАМ?

**Дата:** 2026-08-27  
**Статус:** ✅ Завершён  
**Ответ:** **НЕТ** — на каждом этапе теряются данные

---

## 📊 РЕЗУЛЬТАТ

| Этап | Сейчас | Подходит | Потеряно | Статус |
|------|--------|----------|----------|--------|
| Timeline | 9 полей | 24 поля | **15 полей** | ❌ 37% |
| Change points | 16 полей | 21 поле | **5 полей** | ❌ 76% |
| HTML таблица | 11 колонок | 18 колонок | **7 колонок** | ❌ 61% |
| HTML change points | 8 колонок | 14 колонок | **6 колонок** | ❌ 57% |
| Narrative | 6 параграфов о методе | per-pair тезисы | **полностью** | ❌ |
| Motion maps | 134 точки | 134 точки | 0 | ✅ |
| Summary cards | 4 карточки | 4 карточки | 0 | ✅ |
| Provenance cards | 3 карточки | 3 карточки | 0 | ✅ |

---

## 🚨 ЭТАП 1: TIMELINE (37% данных)

### Сейчас отдаёт (9 полей):
```python
{
    'date', 'photo_a', 'photo_b', 'status',
    'p95_point_z', 'coherence', 'expression_influence', 'days_delta',
    'pose_bin'  # для фильтрации
}
```

### Потеряно (15 полей):

| # | Поле | Зачем нужно журналисту |
|---|------|----------------------|
| 1 | `mesh_rmse` | 3D-поверхность: насколько изменилась геометрия |
| 2 | `mesh_p95` | 3D-поверхность: худший случай |
| 3 | `mesh_point_to_plane_rmse` | 3D-поверхность: отклонение от плоскости |
| 4 | `descriptor_p95_z` | Локальные признаки: сила изменения |
| 5 | `descriptor_significant_fraction` | Локальные признаки: доля изменённых зон |
| 6 | `chronology_rate_status` | Темп: аномально быстрый скачок? |
| 7 | `chronology_rate_z` | Темп: z-score скорости |
| 8 | `cumulative_drift_status` | Дрейф: накопленное изменение |
| 9 | `baseline_return` | Возврат: вернулось ли к исходному? |
| 10 | `cross_bin_support_pose_count` | Подтверждение: сколько ракурсов подтверждают |
| 11 | `matched_calibration_sets` | Калибровка: сколько наборов совпало |
| 12 | `calibration_limited` | Качество: калибровка ограничена? |
| 13 | `pose_leakage_limited` | Качество: утечка позы? |
| 14 | `pose_distance` | Качество: разница углов |
| 15 | `quality_limited` | Качество: качество ограничено? |

### Почему это критично:

Журналист видит только **p95_point_z** (одну метрику из 3 каналов: landmark + mesh + descriptor). Это как смотреть на температуру, игнорируя давление и пульс.

---

## 🚨 ЭТАП 2: CHANGE POINTS (76% данных)

### Сейчас отдаёт (16 полей):
```python
{
    'pair_id', 'pair_type', 'pose_bin', 'date', 'photo_a', 'photo_b',
    'status', 'measurement_status', 'evidence_state',
    'p95_point_z', 'significant_point_fraction', 'coherent_motion_fraction',
    'days_delta', 'chronology_rate_status', 'chronology_rate_z',
    'cross_bin_corroboration_status', 'cross_bin_support_pose_count'
}
```

### Потеряно (5 полей):

| # | Поле | Зачем нужно журналисту |
|---|------|----------------------|
| 1 | `mesh_rmse` | 3D-поверхность в кандидатах |
| 2 | `mesh_p95` | 3D-поверхность: худший случай |
| 3 | `mesh_point_to_plane_rmse` | 3D: отклонение от плоскости |
| 4 | `descriptor_p95_z` | Локальные признаки в кандидатах |
| 5 | `descriptor_top_families` | Какие именно признаки изменились |

### Дополнительно нужны:

| # | Поле | Зачем |
|---|------|-------|
| 6 | `alternative_explanations` | Что ещё может объяснять изменение |
| 7 | `identity_only_motion_rmse` | Движение без мимики |
| 8 | `expression_influence` | Влияние мимики |
| 9 | `baseline_return` | Возврат к исходному |
| 10 | `pose_distance` | Разница углов |
| 11 | `pose_leakage_limited` | Утечка позы |
| 12 | `calibration_limited` | Качество калибровки |
| 13 | `confidence_level` | Уверенность: low/medium/high |

---

## 🚨 ЭТАП 3: HTML ТАБЛИЦА (61% данных)

### Сейчас показывает (11 колонок):
```
Дата B | Ракурс | Тип | Фото A → B | Дни | Точек выше шума | 
P95 point z | Локальные признаки | Темп | Статус
```

### Потеряно (7 колонок):

| # | Колонка | Зачем |
|---|---------|-------|
| 1 | `mesh_rmse` | 3D-поверхность |
| 2 | `descriptor_p95_z` | Сила локальных признаков |
| 3 | `pose_distance` | Разница углов |
| 4 | `chronology_rate_status` | Темп |
| 5 | `matched_calibration_sets` | Покрытие калибровкой |
| 6 | `cross_bin_support_pose_count` | Подтверждение в ракурсах |
| 7 | `coherent_motion_fraction` | Согласованность движения |

---

## 🚨 ЭТАП 4: NARRATIVE (полностью переделать)

### Сейчас:
```
1. "Исследование охватывает N фотографий..."
2. "Для каждой пары движение 134 точек сопоставлено..."
3. "Архив прежних зацепок содержит..."
4. "Помимо движения точек проверяются 13 локальных семейств..."
5. "Найдено N соседних пар с аномальным темпом..."
6. "Ни один статус сам по себе не доказывает..."
```

**Проблема:** Все 6 параграфов — о **МЕТОДЕ**, не о **НАХОДКАХ**.

### Должно быть:
```
1. "Между фото A (2018-03-15) и B (2018-06-20) 43% точек сместились 
   согласованно (p95 z = 4.2). Это выше калибровочного шума в 4.2 раза."

2. "Изменение подтверждено в 3 ракурсах (frontal, left_light, right_light).
   3D-поверхность показывает mesh_rmse = 0.0028 (z = 3.8)."

3. "Локальные признаки: descriptor_p95_z = 3.1, топ-семейства: 
   jaw_contour, cheekbone_left, brow_ridge."

4. "Уверенность: HIGH (cross_bin=3, persistent=yes, quality=ok, 
   calibration=ok, chronology=normal)."
```

---

## ✅ ЭТАПЫ БЕЗ РАЗРЫВОВ

### Motion maps: ✅ полностью
- 134 точки с z-score, dx, dy, magnitude, significant
- Визуализация работает корректно

### Summary cards: ✅ полностью
- Фотографии, Сравнения, Кандидаты, Calibration

### Provenance cards: ✅ полностью
- Конфликты дат, Near-duplicates, Неполная цепочка

---

## 📋 ПЛАН ИСПРАВЛЕНИЯ

### Приоритет P0: Timeline (1 день)

**Файл:** `app6/stage3/engine.py`

```python
timelines[pose] = sorted([{
    # Существующие (8):
    'date': r.get('date_b'),
    'photo_a': r.get('photo_a'),
    'photo_b': r.get('photo_b'),
    'status': r.get('status'),
    'p95_point_z': num(r.get('p95_point_z')),
    'coherence': num(r.get('coherent_motion_fraction')),
    'expression_influence': num(r.get('expression_influence')),
    'days_delta': num(r.get('days_delta', -1)),
    
    # ДОБАВИТЬ mesh (3):
    'mesh_rmse': num(r.get('mesh_rmse')),
    'mesh_p95': num(r.get('mesh_p95')),
    'mesh_point_to_plane_rmse': num(r.get('mesh_point_to_plane_rmse')),
    
    # ДОБАВИТЬ descriptor (2):
    'descriptor_p95_z': num(r.get('descriptor_p95_z')),
    'descriptor_significant_fraction': num(r.get('descriptor_significant_fraction')),
    
    # ДОБАВИТЬ chronology (4):
    'chronology_rate_status': r.get('chronology_rate_status'),
    'chronology_rate_z': num(r.get('chronology_rate_z')),
    'cumulative_drift_status': r.get('cumulative_drift_status'),
    'baseline_return': r.get('baseline_return'),
    
    # ДОБАВИТЬ corroboration (1):
    'cross_bin_support': num(r.get('cross_bin_support_pose_count')),
    
    # ДОБАВИТЬ quality (5):
    'matched_calibration_sets': num(r.get('matched_calibration_sets')),
    'calibration_limited': r.get('calibration_limited'),
    'pose_leakage_limited': r.get('pose_leakage_limited'),
    'pose_distance': num(r.get('pose_distance')),
    'quality_limited': r.get('quality_limited'),
} for r in adjacent if r.get('pose_bin') == pose], key=lambda x: (x['date'] or ''))
```

**Результат:** 8 → 23 поля (+15)

---

### Приоритет P1: Change points (1 день)

**Файл:** `app6/stage2/engine.py`

```python
changes = [{
    # Существующие (17):
    # ... (все текущие поля)
    
    # ДОБАВИТЬ mesh (3):
    'mesh_rmse': num(r.get('mesh_rmse')),
    'mesh_p95': num(r.get('mesh_p95')),
    'mesh_point_to_plane_rmse': num(r.get('mesh_point_to_plane_rmse')),
    
    # ДОБАВИТЬ descriptor (3):
    'descriptor_p95_z': num(r.get('descriptor_p95_z')),
    'descriptor_significant_fraction': num(r.get('descriptor_significant_fraction')),
    'descriptor_top_families': r.get('descriptor_top_families'),
    
    # ДОБАВИТЬ identity/expression (2):
    'identity_only_motion_rmse': num(r.get('identity_only_motion_rmse')),
    'expression_influence': num(r.get('expression_influence')),
    
    # ДОБАВИТЬ chronology (2):
    'baseline_return': r.get('baseline_return'),
    'cumulative_drift_status': r.get('cumulative_drift_status'),
    
    # ДОБАВИТЬ quality (3):
    'pose_distance': num(r.get('pose_distance')),
    'pose_leakage_limited': r.get('pose_leakage_limited'),
    'calibration_limited': r.get('calibration_limited'),
    
    # ДОБАВИТЬ итог (1):
    'confidence_level': r.get('confidence_level'),
} for r in rows if is_reportable_change(r)]
```

**Результат:** 17 → 31 поле (+14)

---

### Приоритет P2: HTML таблица (2 часа)

**Файл:** `app6/stage3/engine.py` (HTML template)

Добавить 7 колонок:
```html
<tr>
    <th>Дата B</th>
    <th>Ракурс</th>
    <th>Тип</th>
    <th>Фото A → B</th>
    <th>Дни</th>
    <th>Углы</th>          <!-- pose_distance -->
    <th>Точек выше шума</th>
    <th>P95 point z</th>
    <th>Mesh RMSE</th>     <!-- mesh_rmse -->
    <th>Descriptor z</th>  <!-- descriptor_p95_z -->
    <th>Локальные признаки</th>
    <th>Подтверждение</th>  <!-- cross_bin_support -->
    <th>Калибровка</th>     <!-- matched_calibration_sets -->
    <th>Темп</th>
    <th>Статус</th>
</tr>
```

**Результат:** 10 → 15 колонок (+5)

---

### Приоритет P3: Narrative (2-3 дня)

**Файл:** `app6/stage3/engine.py`

Полностью переделать narrative из "о методе" в "о находках":

```python
# Per-pair тезисы для топ-5 кандидатов
narrative = []
for cp in changes[:5]:
    thesis = build_pair_thesis(cp)
    narrative.append(thesis)

# Per-epoch структура
for epoch in epochs:
    summary = build_epoch_summary(epoch, rows)
    narrative.append(summary)
```

**Результат:** 6 общих параграфов → per-pair + per-epoch тезисы

---

### Приоритет P4: Confidence level (2 часа)

**Файл:** `app6/stage2/engine.py`

```python
def compute_confidence_level(row):
    score = 0
    if num(row.get('cross_bin_support_pose_count'), 0) >= 2: score += 2
    if row.get('status') == 'persistent_geometric_change': score += 2
    if not row.get('quality_limited'): score += 1
    if not row.get('calibration_limited'): score += 1
    if not row.get('pose_leakage_limited'): score += 1
    if row.get('chronology_rate_status') == 'within_expected': score += 1
    
    return 'low' if score <= 2 else ('medium' if score <= 5 else 'high')

for r in rows:
    r['confidence_level'] = compute_confidence_level(r)
```

**Результат:** Новая метрика confidence_level для всех этапов

---

## 📈 ИТОГО

| Приоритет | Что | Усилия | Результат |
|-----------|-----|--------|-----------|
| **P0** | Timeline +15 полей | 1 день | 37% → 96% |
| **P1** | Change points +14 полей | 1 день | 76% → 100% |
| **P2** | HTML таблица +5 колонок | 2 часа | 61% → 89% |
| **P3** | Narrative переработка | 2-3 дня | ❌ → ✅ |
| **P4** | Confidence level | 2 часа | Новая метрика |
| | **Итого** | **5-6 дней** | **Все данные доходят** |

---

## ✅ ОТВЕТ НА ВОПРОС

**НЕТ, не все данные доходят до журналиста по этапам.**

| Этап | Потеряно | Критичность |
|------|----------|-------------|
| Timeline | 15 из 24 полей | 🔴 Критично |
| Change points | 14 из 31 поля | 🟡 Важно |
| HTML таблица | 7 из 18 колонок | 🟡 Важно |
| Narrative | Полностью | 🔴 Критично |
| Motion maps | 0 | ✅ OK |

**После реализации P0-P4:** Все подходящие данные доходят до журналиста.

---

**Документ создан:** 2026-08-27  
**Следующий шаг:** Реализация P0-P4 (5-6 дней)
