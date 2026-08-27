# 🎯 ФИНАЛЬНЫЙ АНАЛИЗ: КОНЕЧНЫЕ ТОЧКИ 100 МЕТРИК

**Дата:** 2026-08-27  
**Статус:** ✅ Завершён  
**Объём:** 100 метрик из metric_registry → проверка полного пути до журналиста

---

## 📊 РЕЗУЛЬТАТ

### Текущее состояние:

| Этап | Метрик | Процент |
|------|--------|---------|
| Вычисляется в Stage 2 | 100/100 | 100% ✅ |
| Сохраняется в pair_metrics.csv | 45/100 | 45% ❌ |
| Доходит до timeline (Stage 3) | 4/100 | 4% ❌ |
| Доходит до change_points | 6/100 | 6% ❌ |
| Показывается в HTML таблице | 4/100 | 4% ❌ |
| WITHHELD (texture, не публикуется) | 20/100 | 20% ✅ |
| **Имеет конечную точку** | **28/100** | **28%** ❌ |

### Проблема:

**72 из 100 метрик вычисляются, но не доходят до журналиста.**

Только **8 метрик** (без texture) показываются в финальном отчёте:
- `p95_point_z` — timeline + change_points + HTML
- `coherent_motion_fraction` — timeline + change_points
- `expression_influence` — timeline
- `days_delta` — timeline + change_points + HTML
- `significant_point_fraction` — change_points + HTML
- `descriptor_top_families` — HTML
- `cross_bin_support_pose_count` — change_points
- `chronology_rate_z` — change_points

---

## 🚨 ДВА ТИПА РАЗРЫВОВ

### Разрыв 1: Сохраняются в CSV, но НЕ показываются (37 метрик)

Эти метрики вычисляются, сохраняются в pair_metrics.csv, но Stage 3 их не берёт.

#### PAIR (12 метрик):
| # | Метрика | CSV | Timeline | Change Points | HTML |
|---|---------|-----|----------|---------------|------|
| 1 | `pair_index` | ✅ | ❌ | ❌ | ❌ |
| 2 | `same_day` | ✅ | ❌ | ❌ | ❌ |
| 3 | `pose_distance` | ✅ | ❌ | ❌ | ❌ |
| 4 | `common_visible106` | ✅ | ❌ | ❌ | ❌ |
| 5 | `common_visible134` | ✅ | ❌ | ❌ | ❌ |
| 6 | `coverage106` | ✅ | ❌ | ❌ | ❌ |
| 7 | `coverage134` | ✅ | ❌ | ❌ | ❌ |
| 8 | `matched_calibration_sets` | ✅ | ❌ | ❌ | ❌ |
| 9 | `primary_robust_z` | ✅ | ❌ | ❌ | ❌ |
| 10 | `primary_calibration_p95` | ✅ | ❌ | ❌ | ❌ |
| 11 | `cross_bin_independent_source_count` | ✅ | ❌ | ❌ | ❌ |
| 12 | `biological_rate_z` | ✅ | ❌ | ❌ | ❌ |

#### QUALITY (6 метрик):
| # | Метрика | CSV | Timeline | Change Points | HTML |
|---|---------|-----|----------|---------------|------|
| 13 | `quality_texture_score_a` | ✅ | ❌ | ❌ | ❌ |
| 14 | `quality_texture_score_b` | ✅ | ❌ | ❌ | ❌ |
| 15 | `quality_zone_pair_limited` | ✅ | ❌ | ❌ | ❌ |
| 16 | `quality_limited` | ✅ | ❌ | ❌ | ❌ |
| 17 | `forehead_wrinkle_supported_a` | ✅ | ❌ | ❌ | ❌ |
| 18 | `forehead_wrinkle_supported_b` | ✅ | ❌ | ❌ | ❌ |

#### LANDMARK (15 метрик):
| # | Метрика | CSV | Timeline | Change Points | HTML |
|---|---------|-----|----------|---------------|------|
| 19 | `ldm106_rmse` | ✅ | ❌ | ❌ | ❌ |
| 20 | `ldm106_median` | ✅ | ❌ | ❌ | ❌ |
| 21 | `ldm106_p95` | ✅ | ❌ | ❌ | ❌ |
| 22 | `ldm106_max` | ✅ | ❌ | ❌ | ❌ |
| 23 | `ldm134_rmse` | ✅ | ❌ | ❌ | ❌ |
| 24 | `ldm134_median` | ✅ | ❌ | ❌ | ❌ |
| 25 | `ldm134_p95` | ✅ | ❌ | ❌ | ❌ |
| 26 | `ldm134_max` | ✅ | ❌ | ❌ | ❌ |
| 27 | `identity_only_ldm134_rmse` | ✅ | ❌ | ❌ | ❌ |
| 28 | `identity_only_motion_rmse` | ✅ | ❌ | ❌ | ❌ |
| 29 | `ldm106_anchor_count` | ✅ | ❌ | ❌ | ❌ |
| 30 | `ldm134_anchor_count` | ✅ | ❌ | ❌ | ❌ |
| 31 | `ldm134_alignment_trimmed_count` | ✅ | ❌ | ❌ | ❌ |
| 32 | `significant_point_count` | ✅ | ❌ | ❌ | ❌ |
| 33 | `median_point_z` | ✅ | ❌ | ❌ | ❌ |

#### DESCRIPTOR (4 метрики):
| # | Метрика | CSV | Timeline | Change Points | HTML |
|---|---------|-----|----------|---------------|------|
| 34 | `descriptor_significant_fraction` | ✅ | ❌ | ❌ | ❌ |
| 35 | `descriptor_landmark_fraction` | ✅ | ❌ | ❌ | ❌ |
| 36 | `descriptor_p95_z` | ✅ | ❌ | ❌ | ❌ |
| 37 | `descriptor_top_counts` | ✅ | ❌ | ❌ | ❌ |

---

### Разрыв 2: НЕ сохраняются в CSV (35 метрик)

Эти метрики вычисляются, но не попадают в pair_metrics.csv.

#### QUALITY (3 метрики):
| # | Метрика | Статус |
|---|---------|--------|
| 38 | `quality_zone_common_count` | ❌ Не в CSV |
| 39 | `quality_zone_usable_common_count` | ❌ Не в CSV |
| 40 | `quality_zone_usable_common` | ❌ Не в CSV |

#### LANDMARK (6 метрик):
| # | Метрика | Статус |
|---|---------|--------|
| 41 | `alignment106_trimmed_count` | ❌ Не в CSV |
| 42 | `alignment134_residual_before_median` | ❌ Не в CSV |
| 43 | `alignment134_residual_after_median` | ❌ Не в CSV |
| 44 | `alpha_id_l2` | ❌ Не в CSV |
| 45 | `alpha_exp_l2` | ❌ Не в CSV |
| 46 | `alpha_id_robust_z` | ❌ Не в CSV |
| 47 | `alpha_exp_robust_z` | ❌ Не в CSV |

#### DESCRIPTOR (5 метрик):
| # | Метрика | Статус |
|---|---------|--------|
| 48 | `baseline_return_opposite_fraction` | ❌ Не в CSV |
| 49 | `baseline_return_median_cosine` | ❌ Не в CSV |
| 50 | `baseline_return_magnitude_ratio` | ❌ Не в CSV |
| 51 | `baseline_return_common_vector_count` | ❌ Не в CSV |
| 52 | `cross_bin_support_count` | ❌ Не в CSV |

#### MESH (20 метрик):
| # | Метрика | Статус |
|---|---------|--------|
| 53 | `mesh_common_vertex_count` | ❌ Не в CSV |
| 54 | `mesh_visible_fraction` | ❌ Не в CSV |
| 55 | `mesh_rmse` | ❌ Не в CSV |
| 56 | `mesh_median` | ❌ Не в CSV |
| 57 | `mesh_p95` | ❌ Не в CSV |
| 58 | `mesh_fit_vertex_count` | ❌ Не в CSV |
| 59 | `mesh_point_to_plane_rmse` | ❌ Не в CSV |
| 60 | `mesh_point_to_plane_median` | ❌ Не в CSV |
| 61 | `mesh_point_to_plane_p95` | ❌ Не в CSV |
| 62 | `mesh_point_to_plane_signed_median` | ❌ Не в CSV |
| 63 | `mesh_alignment_residual_before_median` | ❌ Не в CSV |
| 64 | `mesh_alignment_residual_after_median` | ❌ Не в CSV |
| 65 | `mesh_anatomical_zone_count` | ❌ Не в CSV |
| 66 | `mesh_anchor_fraction` | ❌ Не в CSV |
| 67 | `mesh_alignment_trimmed_count` | ❌ Не в CSV |
| 68 | `mesh_max_robust_z` | ❌ Не в CSV |
| 69 | `mesh_calibrated_elevated_count` | ❌ Не в CSV |
| 70 | `mesh_calibrated_metric_count` | ❌ Не в CSV |
| 71 | `mesh_shape_linearity` | ❌ Не в CSV |
| 72 | `mesh_shape_planarity` | ❌ Не в CSV |

---

## ✅ ИМЕЮТ КОНЕЧНУЮ ТОЧКУ (8 метрик)

| # | Метрика | Timeline | Change Points | HTML |
|---|---------|----------|---------------|------|
| 1 | `p95_point_z` | ✅ | ✅ | ✅ |
| 2 | `coherent_motion_fraction` | ✅ (как coherence) | ✅ | ❌ |
| 3 | `expression_influence` | ✅ | ❌ | ❌ |
| 4 | `days_delta` | ✅ | ✅ | ✅ |
| 5 | `significant_point_fraction` | ❌ | ✅ | ✅ |
| 6 | `descriptor_top_families` | ❌ | ❌ | ✅ |
| 7 | `cross_bin_support_pose_count` | ❌ | ✅ | ❌ |
| 8 | `chronology_rate_z` | ❌ | ✅ | ❌ |

---

## 🎯 РЕКОМЕНДАЦИИ

### Приоритет P0: Timeline расширение (критично для журналиста)

**Текущее состояние:** 4 метрики  
**Цель:** 22 метрики (+18)

**Добавить в `app6/stage3/engine.py`:**

```python
timelines[pose] = sorted([{
    # Существующие (4):
    'date': r.get('date_b'),
    'photo_a': r.get('photo_a'),
    'photo_b': r.get('photo_b'),
    'status': r.get('status'),
    'p95_point_z': num(r.get('p95_point_z')),
    'coherence': num(r.get('coherent_motion_fraction')),
    'expression_influence': num(r.get('expression_influence')),
    'days_delta': num(r.get('days_delta', -1)),
    
    # ДОБАВИТЬ (14):
    'mesh_rmse': num(r.get('mesh_rmse')),
    'descriptor_p95_z': num(r.get('descriptor_p95_z')),
    'chronology_rate_status': r.get('chronology_rate_status'),
    'chronology_rate_z': num(r.get('chronology_rate_z')),
    'baseline_return': r.get('baseline_return'),
    'cumulative_drift_status': r.get('cumulative_drift_status'),
    'matched_calibration_sets': num(r.get('matched_calibration_sets')),
    'calibration_limited': r.get('calibration_limited'),
    'cross_bin_support': num(r.get('cross_bin_support_pose_count')),
    'quality_limited': r.get('quality_limited'),
    'texture_registered_ssim': num(r.get('texture_structure_min_registered_ssim')),
    'texture_ridge_delta': num(r.get('texture_structure_max_ridge_delta')),
    'confidence_level': r.get('confidence_level'),
} for r in adjacent if r.get('pose_bin') == pose], key=lambda x: (x['date'] or ''))
```

**Усилия:** 1 день  
**Влияние:** Timeline показывает 22 поля вместо 8

---

### Приоритет P1: Change points расширение

**Текущее состояние:** 6 метрик  
**Цель:** 25 метрик (+19)

**Добавить в `app6/stage2/engine.py`:**

```python
changes = [{
    # Существующие (6):
    'pair_id': r['pair_id'],
    'pair_type': r['pair_type'],
    'pose_bin': r['pose_bin'],
    'date': r['date_b'],
    'photo_a': r['photo_a'],
    'photo_b': r['photo_b'],
    'status': r.get('evidence_state', ''),
    'measurement_status': r['status'],
    'evidence_state': r.get('evidence_state', ''),
    'p95_point_z': r.get('p95_point_z', 0),
    'significant_point_fraction': r.get('significant_point_fraction', 0),
    'coherent_motion_fraction': r.get('coherent_motion_fraction', 0),
    'days_delta': r.get('days_delta', -1),
    'chronology_rate_status': r.get('chronology_rate_status', ''),
    'chronology_rate_z': r.get('chronology_rate_z', 0.0),
    'cross_bin_corroboration_status': r.get('cross_bin_corroboration_status', ''),
    'cross_bin_support_pose_count': r.get('cross_bin_support_pose_count', 0),
    
    # ДОБАВИТЬ (10):
    'alternative_explanations': r.get('alternative_explanations'),
    'mesh_rmse': num(r.get('mesh_rmse')),
    'mesh_point_to_plane_rmse': num(r.get('mesh_point_to_plane_rmse')),
    'identity_only_motion_rmse': num(r.get('identity_only_motion_rmse')),
    'expression_influence': num(r.get('expression_influence')),
    'baseline_return': r.get('baseline_return'),
    'baseline_return_opposite_fraction': num(r.get('baseline_return_opposite_fraction')),
    'descriptor_top_families': r.get('descriptor_top_families'),
    'texture_registered_ssim': num(r.get('texture_structure_min_registered_ssim')),
    'confidence_level': r.get('confidence_level'),
} for r in rows if is_reportable_change(r)]
```

**Усилия:** 1 день  
**Влияние:** Change points показывают 25 полей вместо 15

---

### Приоритет P2: Исправить сохранение mesh в pair_metrics.csv

**Проблема:** Все 20 mesh метрик не сохраняются в pair_metrics.csv.

**Причина:** `dense_mesh_pair()` возвращает dict с mesh метриками, но они не включаются в основной row dict через `**mesh_row`.

**Проверка:** В `app6/stage2/engine.py` строка ~350 есть `**mesh_row`, но mesh_dense.py может не возвращать все ключи.

**Исправление:** Проверить что `dense_mesh_pair()` возвращает все 20 mesh метрик в dict.

**Усилия:** 2 часа  
**Влияние:** 20 mesh метрик сохраняются в CSV

---

### Приоритет P3: Исправить сохранение descriptor в pair_metrics.csv

**Проблема:** 5 descriptor метрик не сохраняются.

**Исправление в `app6/stage2/engine.py`:**

```python
# После baseline_return_report = apply_baseline_return(rows, o)
# Добавить в row update:
for r in rows:
    baseline_data = baseline_return_report.get('pairs', {}).get(r['pair_id'], {})
    r.update({
        'baseline_return_opposite_fraction': baseline_data.get('opposite_fraction'),
        'baseline_return_median_cosine': baseline_data.get('median_cosine'),
        'baseline_return_magnitude_ratio': baseline_data.get('magnitude_ratio'),
        'baseline_return_common_vector_count': baseline_data.get('common_vector_count'),
    })
```

**Усилия:** 1 час  
**Влияние:** 4 descriptor метрики сохраняются

---

### Приоритет P4: Исправить сохранение alpha в pair_metrics.csv

**Проблема:** 4 alpha метрики не сохраняются.

**Исправление:** Проверить что `compare_landmarks()` возвращает alpha_id_l2, alpha_exp_l2, alpha_id_robust_z, alpha_exp_robust_z в c.metrics dict.

**Усилия:** 1 час  
**Влияние:** 4 alpha метрики сохраняются

---

### Приоритет P5: Добавить confidence_level

**Формула (из REPORT_ENRICHMENT_15_ANALYSES.md):**

```python
def compute_confidence_level(row):
    score = 0
    
    # Кросс-бин поддержка (макс +2)
    if num(row.get('cross_bin_support_pose_count'), 0) >= 2:
        score += 2
    
    # Персистентность (макс +2)
    if row.get('status') == 'persistent_geometric_change':
        score += 2
    
    # Качество (макс +1)
    if not row.get('quality_limited'):
        score += 1
    
    # Калибровка (макс +1)
    if not row.get('calibration_limited'):
        score += 1
    
    # Pose leakage (макс +1)
    if not row.get('pose_leakage_limited'):
        score += 1
    
    # Хронология (макс +1)
    if row.get('chronology_rate_status') == 'within_expected':
        score += 1
    
    # Итог: 0-8 баллов → low/medium/high
    if score <= 2:
        return 'low'
    elif score <= 5:
        return 'medium'
    else:
        return 'high'
```

**Добавить в `app6/stage2/engine.py`:**

```python
for r in rows:
    r['confidence_level'] = compute_confidence_level(r)
```

**Усилия:** 2 часа  
**Влияние:** Новая метрика для timeline + change_points + HTML

---

## 📈 ИТОГОВЫЙ ПЛАН

| Приоритет | Что | Усилия | Влияние |
|-----------|-----|--------|---------|
| **P0** | Timeline +14 полей | 1 день | +14 в timeline |
| **P1** | Change points +10 полей | 1 день | +10 в change_points |
| **P2** | Mesh сохранение | 2 часа | +20 сохраняются |
| **P3** | Descriptor сохранение | 1 час | +4 сохраняются |
| **P4** | Alpha сохранение | 1 час | +4 сохраняются |
| **P5** | Confidence level | 2 часа | +1 новая метрика |
| | **Итого** | **3 дня** | **53 метрики довезены** |

---

## ✅ ЗАКЛЮЧЕНИЕ

### Текущее состояние:
- ✅ 100/100 метрик вычисляются
- ❌ 45/100 сохраняются в pair_metrics.csv
- ❌ 4/100 доходят до timeline
- ❌ 6/100 доходят до change_points
- ❌ 4/100 показываются в HTML
- ✅ 20/100 texture корректно WITHHELD
- **Итого: 8/100 имеют конечную точку (без texture)**

### После исправлений:
- ✅ 100/100 метрик вычисляются
- ✅ 80/100 сохраняются в pair_metrics.csv (+35)
- ✅ 18/100 доходят до timeline (+14)
- ✅ 16/100 доходят до change_points (+10)
- ✅ 4/100 показываются в HTML (без изменений)
- ✅ 20/100 texture корректно WITHHELD
- **Итого: 58/100 имеют конечную точку (+50)**

### Результат:
**50 из 72 потерянных метрик довезены до журналиста за 3 дня.**

Оставшиеся 22 метрики — это детализация (ldm106_*, ldm134_median/max, quality_zone_*, baseline_return_*, cross_bin_support_count, alpha_*), которые могут быть добавлены в расширенный отчёт для аналитиков или использованы для внутренних расчётов.

---

**Документ создан:** 2026-08-27  
**Следующий шаг:** Реализация P0-P5 (3 дня)
