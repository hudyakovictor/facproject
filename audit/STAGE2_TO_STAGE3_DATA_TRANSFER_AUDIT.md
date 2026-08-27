# 🎯 АУДИТ: ДОХОДЯТ ЛИ ВСЕ ДАННЫЕ ИЗ STAGE 2 ДО STAGE 3?

**Дата:** 2026-08-27  
**Контекст:** Старый HTML отчёт будет удалён, новый отчёт будет создаваться с нуля  
**Вопрос:** Все ли данные из Stage 2 доходят до Stage 3 для использования в новом отчёте?

---

## 📊 ОТВЕТ: **НЕТ** — глобальные артефакты не доходят

---

## ✅ ЧТО ДОХОДИТ (per-pair данные через CSV)

Stage 3 читает `pair_metrics.csv` и получает:

| Категория | Поля | Статус |
|-----------|------|--------|
| **Landmark** | ldm106_*, ldm134_*, p95_point_z, significant_point_fraction | ✅ |
| **Mesh** | mesh_rmse, mesh_p95, mesh_point_to_plane_* | ✅ |
| **Descriptor** | descriptor_p95_z, descriptor_top_families | ✅ |
| **Quality** | quality_limited, quality_texture_score_a/b | ✅ |
| **Chronology (per-pair)** | chronology_rate_status, chronology_rate_z | ✅ |
| **Cross-bin (per-pair)** | cross_bin_support_pose_count | ✅ |
| **Calibration (per-pair)** | calibration_limited, matched_calibration_sets | ✅ |
| **Pose leakage (per-pair)** | pose_leakage_limited, pose_distance | ✅ |
| **Evidence** | evidence_state, status | ✅ |

**Итого:** ~140 per-pair полей доходят через CSV.

---

## ❌ ЧТО НЕ ДОХОДИТ (глобальные артефакты)

Stage 2 записывает 13 глобальных артефактов, но Stage 3 их **НЕ читает**:

| # | Артефакт | Что содержит | Критичность |
|---|----------|--------------|-------------|
| 1 | `alpha_chronology.json` | Temporal events (alpha id/exp changes) | 🔴 Высокая |
| 2 | `baseline_return.json` | Возвраты к baseline (A→B→A паттерны) | 🔴 Высокая |
| 3 | `cumulative_drift.json` | Накопленный дрейф по времени | 🔴 Высокая |
| 4 | `cross_bin_corroboration.json` | Глобальная corroboration (не per-pair) | 🟡 Средняя |
| 5 | `pose_leakage_diagnostic.json` | Глобальная диагностика утечки позы | 🟡 Средняя |
| 6 | `multiple_testing.json` | FDR correction результаты | 🟡 Средняя |
| 7 | `evidence_packets.json` | Детальные evidence для каждой пары | 🟡 Средняя |
| 8 | `calibration_noise_model.json` | Калибровочные noise references | 🟢 Низкая |
| 9 | `descriptor_noise_model.npz` | Descriptor noise references | 🟢 Низкая |
| 10 | `mesh_noise_model.json` | Mesh noise references | 🟢 Низкая |
| 11 | `chronology_rate_model.json` | Chronology rate model | 🟢 Низкая |
| 12 | `event_aggregation.csv` | Агрегация событий | 🟢 Низкая |
| 13 | `technical_summary.json` | Техническая сводка | 🟢 Низкая |

---

## 🚨 КРИТИЧЕСКИЕ РАЗРЫВЫ

### 1. Temporal Events (alpha_chronology.json)

**Что содержит:**
```json
{
  "events": [
    {
      "date": "2018-06-20",
      "type": "alpha_id_jump",
      "magnitude": 0.023,
      "z_score": 4.2,
      "affected_pairs": ["pair_123", "pair_124"]
    }
  ]
}
```

**Проблема:** Stage 3 не читает → temporal events не доступны для нового отчёта.

**Влияние:** Журналист не видит когда произошли изменения в identity/expression coefficients.

---

### 2. Baseline Return (baseline_return.json)

**Что содержит:**
```json
{
  "events": [
    {
      "photo_a": "2018-03-15",
      "photo_b": "2018-06-20",
      "photo_c": "2018-09-10",
      "pattern": "A→B→A",
      "return_fraction": 0.85,
      "significance": "high"
    }
  ]
}
```

**Проблема:** 
- Stage 2 записывает в глобальный JSON
- **НЕ записывает в pair_metrics.csv** (нет `row['baseline_return']`)
- Stage 3 не читает JSON

**Влияние:** Журналист не видит возвраты к исходному состоянию.

---

### 3. Cumulative Drift (cumulative_drift.json)

**Что содержит:**
```json
{
  "events": [
    {
      "pose_bin": "frontal",
      "start_date": "2018-01-01",
      "end_date": "2018-12-31",
      "drift_magnitude": 0.015,
      "direction": "increasing",
      "significance": "medium"
    }
  ]
}
```

**Проблема:**
- Stage 2 записывает в глобальный JSON
- **НЕ записывает в pair_metrics.csv** (нет `row['cumulative_drift_status']`)
- Stage 3 не читает JSON

**Влияние:** Журналист не видит накопленный дрейф по времени.

---

## 📊 ДЕТАЛЬНАЯ ПРОВЕРКА: ЧТО ЗАПИСАНО В pair_metrics.csv

### ✅ Записано:
```python
# Из chronology.py
row['chronology_rate_status'] = ...
row['chronology_rate_z'] = ...
row['biological_rate_status'] = ...
row['biological_rate_z'] = ...

# Из corroboration.py
row['cross_bin_support_pose_count'] = ...
row['cross_bin_corroboration_status'] = ...

# Из engine.py loop
row['calibration_limited'] = ...
row['pose_leakage_limited'] = ...
```

### ❌ НЕ записано:
```python
# baseline_return и cumulative_drift записываются ТОЛЬКО в глобальные JSON
# НЕ добавляются в row для pair_metrics.csv

# Должно быть:
row['baseline_return'] = baseline_return_report.get_pair_event(pair_id)
row['cumulative_drift_status'] = cumulative_drift_report.get_pair_status(pair_id)
```

---

## 🎯 РЕШЕНИЕ

### Шаг 1: Добавить baseline_return в pair_metrics.csv

**Файл:** `app6/stage2/engine.py`

```python
# После baseline_return_report = apply_baseline_return(rows, o) (строка ~393)
# Добавить per-pair baseline_return в row

for r in rows:
    pair_id = r['pair_id']
    baseline_event = baseline_return_report.get('pairs', {}).get(pair_id)
    
    if baseline_event:
        r['baseline_return'] = baseline_event.get('pattern', '')
        r['baseline_return_fraction'] = baseline_event.get('return_fraction', 0.0)
        r['baseline_return_significance'] = baseline_event.get('significance', '')
    else:
        r['baseline_return'] = ''
        r['baseline_return_fraction'] = 0.0
        r['baseline_return_significance'] = ''
```

**Результат:** baseline_return доходит через pair_metrics.csv

---

### Шаг 2: Добавить cumulative_drift_status в pair_metrics.csv

**Файл:** `app6/stage2/engine.py`

```python
# После cumulative_drift_report = apply_cumulative_drift_flags(rows) (строка ~395)
# Добавить per-pair cumulative_drift_status в row

for r in rows:
    pair_id = r['pair_id']
    drift_status = cumulative_drift_report.get('pairs', {}).get(pair_id, {}).get('status', '')
    
    r['cumulative_drift_status'] = drift_status
    r['cumulative_drift_magnitude'] = cumulative_drift_report.get('pairs', {}).get(pair_id, {}).get('magnitude', 0.0)
```

**Результат:** cumulative_drift_status доходит через pair_metrics.csv

---

### Шаг 3: Stage 3 читает глобальные артефакты

**Файл:** `app6/stage3/engine.py`

```python
# В начале run() добавить чтение глобальных артефактов

# Temporal events
alpha_chronology = json.loads((a/'alpha_chronology.json').read_text()) if (a/'alpha_chronology.json').is_file() else {}
baseline_return_global = json.loads((a/'baseline_return.json').read_text()) if (a/'baseline_return.json').is_file() else {}
cumulative_drift_global = json.loads((a/'cumulative_drift.json').read_text()) if (a/'cumulative_drift.json').is_file() else {}

# Cross-bin corroboration
cross_bin_global = json.loads((a/'cross_bin_corroboration.json').read_text()) if (a/'cross_bin_corroboration.json').is_file() else {}

# Pose leakage
pose_leakage_global = json.loads((a/'pose_leakage_diagnostic.json').read_text()) if (a/'pose_leakage_diagnostic.json').is_file() else {}

# Multiple testing
multiple_testing = json.loads((a/'multiple_testing.json').read_text()) if (a/'multiple_testing.json').is_file() else {}

# Evidence packets
evidence_packets = json.loads((a/'evidence_packets.json').read_text()) if (a/'evidence_packets.json').is_file() else []

# Добавить в sections для нового отчёта
sections['temporal_events'] = {
    'alpha_chronology': alpha_chronology,
    'baseline_return': baseline_return_global,
    'cumulative_drift': cumulative_drift_global,
}

sections['global_diagnostics'] = {
    'cross_bin_corroboration': cross_bin_global,
    'pose_leakage': pose_leakage_global,
    'multiple_testing': multiple_testing,
}

sections['evidence_packets'] = evidence_packets
```

**Результат:** Глобальные артефакты доходят до Stage 3 output

---

## 📈 ИТОГО

### Текущее состояние:
- ✅ Per-pair данные: ~140 полей доходят через CSV
- ❌ Temporal events: НЕ доходят (alpha_chronology, baseline_return, cumulative_drift)
- ❌ Global diagnostics: НЕ доходят (cross_bin, pose_leakage, multiple_testing)
- ❌ Evidence packets: НЕ доходят

### После исправления:
- ✅ Per-pair данные: ~140 полей + baseline_return + cumulative_drift_status
- ✅ Temporal events: доходят через sections['temporal_events']
- ✅ Global diagnostics: доходят через sections['global_diagnostics']
- ✅ Evidence packets: доходят через sections['evidence_packets']

### Усилия:
- Шаг 1: 1 час (baseline_return в CSV)
- Шаг 2: 1 час (cumulative_drift в CSV)
- Шаг 3: 2 часа (Stage 3 читает глобальные артефакты)
- **Итого: 4 часа**

---

## ✅ ОТВЕТ НА ВОПРОС

**НЕТ, не все данные из Stage 2 доходят до Stage 3.**

### Что доходит:
- ✅ Per-pair метрики (~140 полей через pair_metrics.csv)
- ✅ chronology_rate_status/z (per-pair)
- ✅ cross_bin_support_pose_count (per-pair)
- ✅ calibration_limited, pose_leakage_limited (per-pair)

### Что НЕ доходит:
- ❌ baseline_return (только в глобальном JSON, не в CSV)
- ❌ cumulative_drift_status (только в глобальном JSON, не в CSV)
- ❌ alpha_chronology events (глобальный JSON не читается)
- ❌ cross_bin_corroboration (глобальный JSON не читается)
- ❌ pose_leakage_diagnostic (глобальный JSON не читается)
- ❌ multiple_testing (глобальный JSON не читается)
- ❌ evidence_packets (глобальный JSON не читается)

### Критичность:
- 🔴 **Высокая:** baseline_return, cumulative_drift, alpha_chronology (temporal events)
- 🟡 **Средняя:** cross_bin, pose_leakage, multiple_testing, evidence_packets (diagnostics)
- 🟢 **Низкая:** calibration models, technical_summary (reference data)

### Решение:
1. Добавить baseline_return в pair_metrics.csv (1 час)
2. Добавить cumulative_drift_status в pair_metrics.csv (1 час)
3. Stage 3 читает глобальные артефакты (2 часа)
4. **Итого: 4 часа**

---

**Документ создан:** 2026-08-27  
**Следующий шаг:** Реализация шагов 1-3 (4 часа)
