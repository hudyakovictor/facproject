# DEEPUTIN — Довозка данных до отчёта (15 анализов)

**Дата:** 2026-08-27  
**Статус:** ✅ 15 анализов завершены  
**Цель:** Точно определить что добавить в Stage 3 для полноты и наглядности

---

## 🎯 ГЛАВНЫЙ ВЫВОД

Stage 3 отдаёт журналисту **8 полей в timeline + 15 в change_points + 10 колонок в таблице + 6 параграфов о методе**.

**Нужно добавить:**
- Timeline: +7 полей (mesh, descriptor, calibration, baseline_return, drift, alpha)
- Change points: +5 полей (alternatives, mesh, identity_only, baseline_return, confidence)
- Narrative: переделать из "о методе" в "о находках" (per-pair + per-epoch тезисы)
- Confidence: вычислять из 7 факторов (0-8 баллов → low/medium/high)

---

## 📋 РЕЗУЛЬТАТЫ 15 АНАЛИЗОВ

### БЛОК 1: Timeline расширение (анализы 1-5)

| # | Анализ | Текущее | Нужно добавить | Источник в pair_metrics |
|---|--------|---------|----------------|------------------------|
| 1 | **Temporal events** | ❌ Нет | baseline_return (bool), cumulative_drift_status, chronology_rate_status | ✅ Все есть в row |
| 2 | **Mesh кривая** | ❌ Нет | mesh_rmse, mesh_point_to_plane_rmse | ✅ mesh_row → row |
| 3 | **Texture кривая** | ❌ WITHHELD | texture_structure_min_registered_ssim, texture_structure_max_ridge_delta | ✅ texture_row → row |
| 4 | **Descriptor кривая** | ❌ Нет | descriptor_p95_z, descriptor_significant_fraction | ✅ Все есть в row |
| 5 | **Calibration coverage** | ❌ Нет | matched_calibration_sets, calibration_limited | ✅ Все есть в row |

**Текущий timeline (8 полей):**
```python
{'date', 'photo_a', 'photo_b', 'status', 'p95_point_z', 
 'coherence', 'expression_influence', 'days_delta'}
```

**Расширенный timeline (22 поля):**
```python
{'date', 'photo_a', 'photo_b', 'status', 'p95_point_z',
 'coherence', 'expression_influence', 'days_delta',
 # НОВОЕ — geometry layers:
 'mesh_rmse', 'descriptor_p95_z', 'descriptor_top_families',
 # НОВОЕ — temporal layers:
 'chronology_rate_status', 'chronology_rate_z',
 'baseline_return', 'cumulative_drift_status',
 # НОВОЕ — calibration/context:
 'matched_calibration_sets', 'calibration_limited',
 'cross_bin_support_pose_count', 'quality_limited',
 # НОВОЕ — texture (после pose normalization):
 'texture_registered_ssim', 'texture_ridge_delta',
 # НОВОЕ — confidence:
 'confidence_level'}
```

**Изменение в `app6/stage3/engine.py`:**
```python
timelines[pose] = sorted([{
    'date': r.get('date_b'),
    'photo_a': r.get('photo_a'),
    'photo_b': r.get('photo_b'),
    'status': r.get('status'),
    'p95_point_z': num(r.get('p95_point_z')),
    'coherence': num(r.get('coherent_motion_fraction')),
    'expression_influence': num(r.get('expression_influence')),
    'days_delta': num(r.get('days_delta', -1)),
    # ДОБАВИТЬ:
    'mesh_rmse': num(r.get('mesh_rmse')),
    'descriptor_p95_z': num(r.get('descriptor_p95_z')),
    'chronology_rate_status': r.get('chronology_rate_status', ''),
    'chronology_rate_z': num(r.get('chronology_rate_z')),
    'baseline_return': bool(r.get('baseline_return')),
    'cumulative_drift_status': r.get('cumulative_drift_status', ''),
    'matched_calibration_sets': num(r.get('matched_calibration_sets')),
    'calibration_limited': bool(r.get('calibration_limited')),
    'cross_bin_support': num(r.get('cross_bin_support_pose_count')),
    'confidence_level': r.get('confidence_level', ''),
} for r in adjacent if r.get('pose_bin') == pose], key=...)
```

---

### БЛОК 2: Change points расширение (анализы 6-9)

| # | Анализ | Текущее | Нужно добавить |
|---|--------|---------|----------------|
| 6 | **Alternatives** | ❌ Нет | `alternative_explanations` (список строк из evidence.py) |
| 7 | **Mesh** | ❌ Нет | mesh_rmse, mesh_point_to_plane_rmse, mesh_max_robust_z |
| 8 | **Identity-only** | ❌ Нет | identity_only_motion_rmse, expression_influence |
| 9 | **Baseline return** | ❌ Нет | baseline_return_opposite_fraction, baseline_return_median_cosine |

**Текущие change_points (15 полей):**
```python
{'pair_id', 'pair_type', 'pose_bin', 'date', 'photo_a', 'photo_b',
 'status', 'measurement_status', 'evidence_state',
 'p95_point_z', 'significant_point_fraction', 'coherent_motion_fraction',
 'days_delta', 'chronology_rate_status', 'chronology_rate_z',
 'cross_bin_corroboration_status', 'cross_bin_support_pose_count'}
```

**Расширенные change_points (25 полей):**
```python
# ... текущие 15 +
'alternative_explanations': alternative_reasons(r),  # список строк
'mesh_rmse': r.get('mesh_rmse'),
'mesh_point_to_plane_rmse': r.get('mesh_point_to_plane_rmse'),
'identity_only_motion_rmse': r.get('identity_only_motion_rmse'),
'expression_influence': r.get('expression_influence'),
'baseline_return': r.get('baseline_return'),
'baseline_return_opposite_fraction': r.get('baseline_return_opposite_fraction'),
'descriptor_top_families': r.get('descriptor_top_families'),
'confidence_level': r.get('confidence_level'),
```

---

### БЛОК 3: Narrative трансформация (анализы 10-12)

| # | Анализ | Текущее | Нужно |
|---|--------|---------|-------|
| 10 | **Narrative** | 6 параграфов о МЕТОДЕ | Per-pair + per-epoch тезисы о НАХОДКАХ |
| 11 | **Per-pair тезисы** | ❌ Нет | 3-шаговый текст для каждого candidate |
| 12 | **Epoch/thread** | event_aggregation.csv есть, но не в Stage 3 | Добавить в sections |

**Текущий narrative (о методе):**
```
1. "Исследование охватывает N фотографий..."
2. "Для каждой пары движение 134 точек сопоставлено..."
3. "Архив прежних зацепок содержит..."
4. "Помимо движения точек проверяются 13 семейств..."
5. "Найдено N пар с аномальным темпом..."
6. "Ни один статус не доказывает подмену..."
```

**Новый narrative (о находках):**
```
1. "Масштаб" — N фото, M пар, K кандидатов (оставить)
2. "Сильнейшие сигналы" — топ-5 кандидатов с тезисами
3. "Хронология" — эпохи с трендами и всплесками  
4. "Подтверждения" — cross-bin, persistence
5. "Ограничения" — quality/calibration/pose проблемы
6. "Граница вывода" — (оставить)
```

**Per-pair тезис (3 шага):**
```python
def pair_thesis(r: dict) -> dict:
    # Шаг 1: Что видно
    sig_pct = f"{float(r.get('significant_point_fraction', 0)) * 100:.0f}"
    p95 = f"{float(r.get('p95_point_z', 0)):.1f}"
    step1 = f"Между {r['photo_a']} и {r['photo_b']} "
    step1 += f"{sig_pct}% точек сместились согласованно (сила {p95}σ)."
    
    # Шаг 2: Что подтверждает/ослабляет
    cross = int(r.get('cross_bin_support_pose_count', 0))
    step2 = f"Подтверждено в {cross} ракурсах. " if cross >= 2 else ""
    if r.get('quality_limited'):
        step2 += "Качество ограничено. "
    if r.get('calibration_limited'):
        step2 += "Калибровка недостаточна. "
    
    # Шаг 3: Итог
    conf = r.get('confidence_level', 'low')
    step3 = f"Уверенность: {conf}."
    
    return {'step1': step1, 'step2': step2, 'step3': step3}
```

---

### БЛОК 4: Confidence level (анализы 13-15)

| # | Анализ | Результат |
|---|--------|-----------|
| 13 | **Данные** | Все 7 факторов есть в pair_metrics |
| 14 | **UI** | Нет в текущем UI spec — нужно добавить |
| 15 | **Формула** | 0-8 баллов → low/medium/high |

**Формула confidence_level:**
```python
def compute_confidence(row: dict) -> str:
    score = 0
    
    # Cross-bin corroboration (max +2)
    cross = int(row.get('cross_bin_support_pose_count', 0) or 0)
    if cross >= 2: score += 2
    elif cross >= 1: score += 1
    
    # Persistence (max +2)
    if row.get('status') == 'persistent_geometric_change': score += 2
    elif row.get('status') == 'coherent_jump_candidate': score += 1
    
    # Data quality (max +3)
    if not row.get('quality_limited'): score += 1
    if not row.get('calibration_limited'): score += 1
    if not row.get('pose_leakage_limited'): score += 1
    
    # Temporal consistency (max +1)
    rate = str(row.get('chronology_rate_status', ''))
    if rate == 'within_expected_rate': score += 1
    
    # Маппинг
    if score >= 6: return "high"
    if score >= 3: return "medium"
    return "low"
```

**Где вычислять:**
- В `app6/stage2/engine.py` — после определения status, перед записью в row
- Результат: `row['confidence_level']` = "low" | "medium" | "high"

**Где показывать:**
- Timeline: цвет точки (зелёный/жёлтый/красный)
- Change points: бейдж рядом со статусом
- HTML таблица: дополнительная колонка
- Narrative: "N кандидатов с высокой уверенностью"

---

## 📊 ИТОГОВАЯ КАРТА: что добавить в Stage 3

### Timeline: 8 → 22 поля (+14)

| # | Поле | Тип | Слой |
|---|------|-----|------|
| 1-8 | текущие | — | Геометрия |
| 9 | mesh_rmse | float | Геометрия |
| 10 | descriptor_p95_z | float | Геометрия |
| 11 | descriptor_top_families | string | Геометрия |
| 12 | chronology_rate_status | string | Хронология |
| 13 | chronology_rate_z | float | Хронология |
| 14 | baseline_return | bool | Хронология |
| 15 | cumulative_drift_status | string | Хронология |
| 16 | matched_calibration_sets | int | Контекст |
| 17 | calibration_limited | bool | Контекст |
| 18 | cross_bin_support | int | Контекст |
| 19 | quality_limited | bool | Контекст |
| 20 | texture_registered_ssim | float | Текстура |
| 21 | texture_ridge_delta | float | Текстура |
| 22 | confidence_level | string | Итог |

### Change points: 15 → 25 полей (+10)

| # | Поле | Тип |
|---|------|-----|
| 16 | alternative_explanations | list[str] |
| 17 | mesh_rmse | float |
| 18 | mesh_point_to_plane_rmse | float |
| 19 | identity_only_motion_rmse | float |
| 20 | expression_influence | float |
| 21 | baseline_return | bool |
| 22 | baseline_return_opposite_fraction | float |
| 23 | descriptor_top_families | string |
| 24 | texture_registered_ssim | float |
| 25 | confidence_level | string |

### Narrative: 6 общих → per-pair + per-epoch

| # | Было | Стало |
|---|------|-------|
| 1 | "N фотографий..." | "N фотографий, M пар, K кандидатов" (оставить) |
| 2 | "134 точек сопоставлено..." | **Топ-5 кандидатов с per-pair тезисами** |
| 3 | "Архив зацепок..." | **Эпохи: тренды, всплески, возвраты** |
| 4 | "13 семейств shape..." | **Подтверждения: cross-bin, persistence** |
| 5 | "N пар с аномальным темпом..." | **Ограничения: quality/calibration/pose** |
| 6 | "Не доказывает подмену..." | "Граница вывода" (оставить) |

### Confidence level: новый канал

```
Формула: 7 факторов → 0-8 баллов → low/medium/high
Вычисление: app6/stage2/engine.py (после status)
Показ: timeline + change_points + HTML + narrative
```

---

## 🔧 ПЛАН РЕАЛИЗАЦИИ

### P0: Добавить в timeline (+14 полей)
**Файл:** `app6/stage3/engine.py` — `timelines[pose]`  
**Усилия:** 1 день

### P0: Вычислить confidence_level  
**Файл:** `app6/stage2/engine.py` — после status determination  
**Усилия:** 1 день

### P1: Расширить change_points (+10 полей)
**Файл:** `app6/stage2/engine.py` — `changes=[...]`  
**Усилия:** 1 день

### P1: Переделать narrative
**Файл:** `app6/stage3/engine.py` — `narrative=[...]`  
**Усилия:** 2-3 дня

### P2: Добавить epoch/thread в sections
**Файл:** `app6/stage3/engine.py` — `sections['epochs']`  
**Усилия:** 1-2 дня

**Итого: 6-8 дней**

