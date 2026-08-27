# 🎯 РЕШЕНИЕ: Descriptor метрики и чувствительность к углу

**Дата:** 2026-08-27  
**Статус:** ✅ Решение принято  
**Вопрос:** Что делать с 3 descriptor метриками средне чувствительными к углу?

---

## 📊 ПРОБЛЕМА

Три descriptor метрики средне чувствительны к разнице углов внутри pose bin:

| Метрика | Чувствительность | Причина |
|---------|------------------|---------|
| `descriptor_significant_fraction` | Средняя | Локальные патчи поворачиваются |
| `descriptor_landmark_fraction` | Средняя | Окклюзия при повороте |
| `cross_bin_support_count` | **НЕ чувствительна** | Мета-метрика (количество bins) |

---

## 🔬 АНАЛИЗ КАЖДОЙ МЕТРИКИ

### 1. descriptor_significant_fraction

**Формула:**
```python
descriptor_significant_fraction = ds.get('significant_cell_fraction', 0.0)
# Доля descriptor cells с значимым изменением (z > threshold)
```

**Чувствительность к углу:**
- Descriptors вычисляются из локальных патчей вокруг landmarks
- При повороте головы патч поворачивается → descriptor меняется
- Alignment компенсирует глобальный поворот, но не локальные деформации
- При `pose_distance > 15°` чувствительность увеличивается

**Можно ли исправить?**
- ❌ Нормализация нестабильна (требует калибровки на каждый pose bin)
- ✅ Можно использовать с предупреждением

**Решение:**
- ✅ **Включить в timeline** с предупреждением
- ✅ **Включить в change_points** с предупреждением
- ✅ Добавить `descriptor_angle_warning` если `pose_distance > 15°`

**Код:**
```python
# В timeline (Stage 3):
'descriptor_significant_fraction': num(r.get('descriptor_significant_fraction')),
'descriptor_angle_warning': bool(num(r.get('pose_distance', 0)) > 15.0),
```

---

### 2. descriptor_landmark_fraction

**Формула:**
```python
descriptor_landmark_fraction = ds.get('significant_landmark_fraction', 0.0)
# Доля landmarks с измеренным descriptor (не окклюдированы)
```

**Чувствительность к углу:**
- При повороте головы некоторые landmarks окклюдируются
- Frontal: видно ~134 landmarks
- Profile: видно ~80 landmarks
- Это QC метрика, не измеряет изменение

**Можно ли исправить?**
- ❌ Окклюзия неустранима (физическое ограничение)
- ✅ Можно использовать как QC флаг

**Решение:**
- ❌ **НЕ включать в timeline** (не измеряет изменение)
- ❌ **НЕ включать в change_points** (не измеряет изменение)
- ✅ **Использовать для QC**: если `descriptor_landmark_fraction < 0.5` → `descriptor_quality_limited`

**Код:**
```python
# В engine.py (Stage 2) после descriptor_score:
if ds.get('significant_landmark_fraction', 0) < 0.5:
    row['descriptor_quality_limited'] = True
    row['descriptor_quality_reason'] = 'insufficient_landmarks'
else:
    row['descriptor_quality_limited'] = False
    row['descriptor_quality_reason'] = ''
```

---

### 3. cross_bin_support_count

**Формула:**
```python
cross_bin_support_count = len(supports)
# Количество pose bins подтверждающих изменение
```

**Чувствительность к углу:**
- **НЕ чувствительна** — это мета-метрика
- Измеряет: сколько разных ракурсов подтверждают изменение
- Наоборот: это **индикатор устойчивости к углу**

**Решение:**
- ✅ **Включить в timeline** как индикатор надёжности
- ✅ **Включить в change_points** как индикатор надёжности
- ✅ Использовать в `confidence_level` формуле

**Код:**
```python
# В timeline (Stage 3):
'cross_bin_support': num(r.get('cross_bin_support_pose_count')),

# В confidence_level формуле:
if num(row.get('cross_bin_support_pose_count'), 0) >= 2:
    score += 2  # Подтверждено в нескольких ракурсах
```

---

## ✅ ИТОГОВОЕ РЕШЕНИЕ

| Метрика | Timeline | Change Points | QC | Индикатор |
|---------|----------|---------------|-----|-----------|
| `descriptor_significant_fraction` | ✅ + warning | ✅ + warning | — | — |
| `descriptor_landmark_fraction` | ❌ | ❌ | ✅ | — |
| `cross_bin_support_count` | ✅ | ✅ | — | ✅ Надёжность |

---

## 📋 РЕАЛИЗАЦИЯ

### Шаг 1: Добавить descriptor_angle_warning в timeline

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
    
    # ДОБАВИТЬ descriptor с warning (2):
    'descriptor_significant_fraction': num(r.get('descriptor_significant_fraction')),
    'descriptor_angle_warning': bool(num(r.get('pose_distance', 0)) > 15.0),
} for r in adjacent if r.get('pose_bin') == pose], key=lambda x: (x['date'] or ''))
```

---

### Шаг 2: Добавить descriptor_quality_limited в engine.py

**Файл:** `app6/stage2/engine.py`

```python
# После descriptor_score = descriptor_model.score(...) (строка ~350)
ds = descriptor_score['summary']

# Добавить QC флаг
if ds.get('significant_landmark_fraction', 0) < 0.5:
    descriptor_quality_limited = True
    descriptor_quality_reason = 'insufficient_landmarks'
else:
    descriptor_quality_limited = False
    descriptor_quality_reason = ''

# Добавить в row
row = {
    # ... существующие поля ...
    'descriptor_quality_limited': descriptor_quality_limited,
    'descriptor_quality_reason': descriptor_quality_reason,
}
```

---

### Шаг 3: Добавить cross_bin_support в timeline

**Файл:** `app6/stage3/engine.py`

```python
timelines[pose] = sorted([{
    # ... существующие поля ...
    
    # ДОБАВИТЬ cross_bin_support (1):
    'cross_bin_support': num(r.get('cross_bin_support_pose_count')),
} for r in adjacent if r.get('pose_bin') == pose], key=lambda x: (x['date'] or ''))
```

---

### Шаг 4: Использовать cross_bin_support в confidence_level

**Файл:** `app6/stage2/engine.py`

```python
def compute_confidence_level(row):
    score = 0
    
    # Cross-bin support (макс +2)
    if num(row.get('cross_bin_support_pose_count'), 0) >= 2:
        score += 2
    
    # ... остальные факторы ...
    
    return 'low' if score <= 2 else ('medium' if score <= 5 else 'high')
```

---

## 🎯 ОБҮРУНТОВАНИЕ

### Почему descriptor_significant_fraction включаем с warning:

1. **Измеряет реальное изменение** — если descriptor значимо изменился, это сигнал
2. **Чувствительность умеренная** — при `pose_distance < 15°` надёжна
3. **Warning информирует** — журналист видит когда метрика может быть ненадёжна

### Почему descriptor_landmark_fraction исключаем:

1. **QC метрика** — измеряет качество данных, не изменение
2. **Чувствительна к окклюзии** — не отражает реальные изменения
3. **Дублирует информацию** — `descriptor_quality_limited` более понятен

### Почему cross_bin_support_count включаем:

1. **НЕ чувствительна к углу** — мета-метрика
2. **Индикатор надёжности** — подтверждение в нескольких ракурсах
3. **Критична для confidence_level** — увеличивает уверенность

---

## ✅ ЗАКЛЮЧЕНИЕ

### Итоговое решение:

| Метрика | Решение | Обоснование |
|---------|---------|-------------|
| `descriptor_significant_fraction` | ✅ Включить + warning | Измеряет изменение, warning для pose_distance > 15° |
| `descriptor_landmark_fraction` | ❌ Исключить | QC метрика, чувствительна к окклюзии |
| `cross_bin_support_count` | ✅ Включить | Индикатор надёжности, не чувствительна |

### Усилия:
- Шаг 1: 30 минут (timeline + warning)
- Шаг 2: 30 минут (QC флаг)
- Шаг 3: 15 минут (timeline + cross_bin)
- Шаг 4: 15 минут (confidence_level)
- **Итого: 1.5 часа**

---

**Решение принято:** 2026-08-27  
**Следующий шаг:** Реализация (1.5 часа)
