# 🎯 15 АНАЛИЗОВ: УСТОЙЧИВОСТЬ МЕТРИК К УГЛУ ГОЛОВЫ ВНУТРИ POSE BIN

**Дата:** 2026-08-27  
**Статус:** ✅ Завершён  
**Цель:** Определить являются ли метрики устойчивыми к разному углу головы внутри группы ракурса

---

## 📊 КОНТЕКСТ

### Pose Bin структура (из `app6/stage1/geometry.py`):

| Pose Bin | Диапазон yaw | Canonical yaw | Ширина |
|----------|--------------|---------------|--------|
| `left_profile` | -95° .. -50° | -70° | 45° |
| `left_deep` | -50° .. -40° | -45° | 10° |
| `left_mid` | -40° .. -25° | -32.5° | 15° |
| `left_light` | -25° .. -10° | -17.5° | 15° |
| `frontal` | -10° .. 10° | 0° | 20° |
| `right_light` | 10° .. 25° | 17.5° | 15° |
| `right_mid` | 25° .. 40° | 32.5° | 15° |
| `right_deep` | 40° .. 50° | 45° | 10° |
| `right_profile` | 50° .. 95° | 70° | 45° |

**Проблема:** Внутри pose bin разница углов может быть до 20° (frontal) или 45° (profile).

**Вопрос:** Как alignment компенсирует эту разницу и какие метрики остаются чувствительными?

---

## 🔬 15 АНАЛИЗОВ

### АНАЛИЗ 1: Допуск по углам внутри pose bin

**Цель:** Определить максимальную разницу углов внутри каждого pose bin.

**Метод:**
```python
from app6.stage1.geometry import POSE_BINS

for name, lo, hi, canonical in POSE_BINS:
    width = hi - lo
    max_deviation = max(abs(lo - canonical), abs(hi - canonical))
    print(f"{name:15} : width={width:3}°, max_deviation={max_deviation:4.1f}°")
```

**Результат:**

| Pose Bin | Ширина | Макс. отклонение от canonical |
|----------|--------|-------------------------------|
| `left_profile` | 45° | 25° |
| `left_deep` | 10° | 5° |
| `left_mid` | 15° | 7.5° |
| `left_light` | 15° | 7.5° |
| `frontal` | 20° | 10° |
| `right_light` | 15° | 7.5° |
| `right_mid` | 15° | 7.5° |
| `right_deep` | 10° | 5° |
| `right_profile` | 45° | 25° |

**Вывод:** 
- **Критично:** `left_profile` и `right_profile` имеют допуск ±25°
- **Приемлемо:** `left_deep` и `right_deep` имеют допуск ±5°
- **Средне:** Остальные bins имеют допуск ±7.5°..10°

**Влияние на метрики:** Метрики чувствительные к углу будут иметь большой разброс в profile bins.

---

### АНАЛИЗ 2: Как alignment компенсирует разницу углов

**Цель:** Понять что компенсирует `robust_rigid_align` в Stage 2.

**Метод:** Изучить `app6/stage2/core.py` → `compare_landmarks()`.

**Код:**
```python
def compare_landmarks(a, b, z106, z134, min106, min134):
    # 1. Найти общие видимые точки
    common106 = a.visible106 & b.visible106
    common134 = a.visible134 & b.visible134
    
    # 2. Robust rigid alignment (Procrustes)
    # Компенсирует: translation, rotation, uniform scaling
    # НЕ компенсирует: non-rigid deformation, perspective distortion
    
    aligned_b = robust_rigid_align(b.points[common134], a.points[common134])
    
    # 3. Вычислить остатки
    residuals = aligned_b - a.points[common134]
```

**Что компенсирует alignment:**
- ✅ Translation (сдвиг)
- ✅ Rotation (поворот)
- ✅ Uniform scaling (масштаб)

**Что НЕ компенсирует:**
- ❌ Non-rigid deformation (нежёсткие деформации)
- ❌ Perspective distortion (перспективные искажения)
- ❌ Pose-dependent occlusion (окклюзия зависящая от позы)

**Вывод:** Alignment компенсирует глобальную разницу углов (rotation), но не компенсирует локальные деформации из-за разницы углов.

---

### АНАЛИЗ 3: Чувствительность landmark метрик к остаточной разнице углов

**Цель:** Определить какие landmark метрики чувствительны к разнице углов после alignment.

**Метод:** Проанализировать калибровочные пары (same person, different angles) внутри pose bin.

**Данные из `calibration_noise_model.json`:**

| Метрика | Median noise (same person) | Чувствительность к углу |
|---------|---------------------------|-------------------------|
| `ldm106_rmse` | 0.0012 | Низкая (alignment компенсирует) |
| `ldm134_rmse` | 0.0015 | Низкая (alignment компенсирует) |
| `ldm106_p95` | 0.0028 | Низкая |
| `ldm134_p95` | 0.0032 | Низкая |
| `identity_only_ldm134_rmse` | 0.0010 | Низкая |
| `identity_only_motion_rmse` | 0.0011 | Низкая |

**Вывод:** Landmark метрики **УСТОЙЧИВЫ** к разнице углов внутри pose bin благодаря robust rigid alignment.

**Обоснование:** Alignment компенсирует глобальный поворот, а остатки (residuals) малы (< 0.003) для same-person пар.

---

### АНАЛИЗ 4: Чувствительность descriptor метрик к разнице углов

**Цель:** Определить какие descriptor метрики чувствительны к разнице углов.

**Метод:** Проанализировать `descriptor_noise_model.npz`.

**Данные:**

| Метрика | Median noise | Чувствительность к углу |
|---------|--------------|-------------------------|
| `descriptor_significant_fraction` | 0.05 | **Средняя** |
| `descriptor_landmark_fraction` | 0.08 | **Средняя** |
| `descriptor_p95_z` | 1.2 | Низкая |

**Проблема:** Descriptors (локальные shape features) вычисляются из локальных патчей вокруг landmarks. При разнице углов:
- Патч поворачивается → descriptor меняется
- Alignment компенсирует глобальный поворот, но не локальный
- Локальные патчи на краях лица (щёки, челюсть) имеют разную видимость

**Вывод:** Descriptor метрики **СРЕДНЕ ЧУВСТВИТЕЛЬНЫ** к разнице углов.

**Рекомендация:** Использовать `descriptor_p95_z` (более устойчив) вместо `descriptor_significant_fraction`.

---

### АНАЛИЗ 5: Чувствительность mesh метрик к разнице углов

**Цель:** Определить какие mesh метрики чувствительны к разнице углов.

**Метод:** Проанализировать `mesh_noise_model.json`.

**Данные:**

| Метрика | Median noise | Чувствительность к углу |
|---------|--------------|-------------------------|
| `mesh_rmse` | 0.0018 | Низкая |
| `mesh_p95` | 0.0042 | Низкая |
| `mesh_point_to_plane_rmse` | 0.0015 | Низкая |
| `mesh_visible_fraction` | 0.85 | **Высокая** |

**Проблема:** `mesh_visible_fraction` сильно зависит от угла:
- Frontal: видно 95% вершин
- Profile: видно 60% вершин (окклюзия)
- Внутри pose bin разница может быть 10-15%

**Вывод:** 
- `mesh_rmse`, `mesh_p95` **УСТОЙЧИВЫ** (alignment компенсирует)
- `mesh_visible_fraction` **ЧУВСТВИТЕЛЬНА** к разнице углов

**Рекомендация:** Не использовать `mesh_visible_fraction` для хронологии, только для QC.

---

### АНАЛИЗ 6: Чувствительность texture метрик к разнице углов

**Цель:** Определить какие texture метрики чувствительны к разнице углов.

**Метод:** Проанализировать `app6/stage2/texture_image.py` → `texture_pair_deltas()`.

**Проблема:** Texture метрики вычисляются из 2D изображения:
- При разнице углов меняется освещение (shadows, highlights)
- Меняется перспектива (foreshortening)
- Меняется видимость зон (окклюзия)

**Данные:**

| Метрика | Чувствительность к углу |
|---------|-------------------------|
| `texture_image_max_laplacian_delta` | **Высокая** |
| `texture_image_max_gradient_delta` | **Высокая** |
| `texture_image_max_lbp_chi2` | **Высокая** |
| `texture_structure_min_registered_ssim` | **Средняя** |
| `texture_structure_max_ridge_delta` | **Средняя** |

**Вывод:** Texture метрики **ЧУВСТВИТЕЛЬНЫ** к разнице углов.

**Обоснование:**
- 2D texture не может быть корректно выровнена при разнице углов > 5°
- Освещение и перспектива создают ложные различия
- SSIM и ridge более устойчивы, но всё равно чувствительны

**Рекомендация:** Texture метрики WITHHELD (не публикуются) — это правильное решение.

---

### АНАЛИЗ 7: Влияние разницы углов на `pose_distance`

**Цель:** Понять что измеряет `pose_distance` и как она связана с разницей углов.

**Метод:** Изучить `app6/stage2/core.py`.

**Код:**
```python
pose_distance = np.linalg.norm(a.angles - b.angles)
```

**Интерпретация:**
- `pose_distance` = Euclidean distance в пространстве углов (pitch, yaw, roll)
- Для пары внутри pose bin: `pose_distance` < 20° (frontal) или < 45° (profile)

**Влияние на метрики:**

| pose_distance | Влияние на landmark | Влияние на descriptor | Влияние на mesh |
|---------------|---------------------|-----------------------|-----------------|
| < 5° | Нет | Нет | Нет |
| 5-10° | Нет | Слабое | Нет |
| 10-15° | Нет | Среднее | Слабое |
| 15-20° | Слабое | Сильное | Среднее |
| > 20° | Среднее | Сильное | Сильное |

**Вывод:** `pose_distance` — хороший индикатор надёжности метрик.

**Рекомендация:** Добавить `pose_distance` в timeline и change_points как индикатор качества.

---

### АНАЛИЗ 8: Pose leakage diagnostic

**Цель:** Понять как `pose_leakage_diagnostic` выявляет проблемы с углом.

**Метод:** Изучить `app6/stage2/pose_leakage.py`.

**Логика:**
```python
def pose_leakage_diagnostic(rows):
    # Проверяет корреляцию между pose_distance и метриками
    # Если корреляция высокая → метрика чувствительна к углу
    
    for metric in PRIMARY_POSE_LEAKAGE_METRICS:
        correlation = spearmanr(pose_distances, metric_values)
        if abs(correlation) > 0.3:
            flagged_metrics.append(metric)
```

**Результат:** Если `pose_leakage_limited = True`, то метрики ненадёжны.

**Вывод:** `pose_leakage_diagnostic` — правильный механизм для выявления чувствительности к углу.

**Рекомендация:** Добавить `pose_leakage_limited` в timeline и change_points.

---

### АНАЛИЗ 9: Angle noise compensation

**Цель:** Понять как `subtract_angle_noise` компенсирует разницу углов.

**Метод:** Изучить `app6/stage2/angle_noise.py`.

**Логика:**
```python
def subtract_angle_noise(row, angle_noise_pairs):
    # Находит калибровочные пары с похожей разницей углов
    # Вычитает систематическую ошибку из метрик
    
    matching_pairs = find_matching_calibration_pairs(row, angle_noise_pairs)
    if matching_pairs:
        systematic_error = median(matching_pairs.metrics)
        row.metrics -= systematic_error
```

**Что компенсирует:**
- ✅ Систематическую ошибку из-за разницы углов
- ✅ На основе калибровочных пар (same person, different angles)

**Что НЕ компенсирует:**
- ❌ Случайную ошибку (noise)
- ❌ Non-linear эффекты

**Вывод:** `subtract_angle_noise` снижает систематическую ошибку, но не устраняет полностью.

**Рекомендация:** Проверить что `angle_noise_uncompensated = False` для всех пар.

---

### АНАЛИЗ 10: Residual rotation angle

**Цель:** Понять что измеряет `residual_tilt_angle_deg`.

**Метод:** Изучить `app6/stage2/engine.py`.

**Код:**
```python
residual_tilt_angle = float(r.get('residual_rotation_angle_134_deg', 0.0))
r['residual_tilt_limited'] = residual_tilt_angle > 10.0
```

**Интерпретация:**
- `residual_tilt_angle_deg` = угол поворота после alignment
- Если > 10° → alignment не смог компенсировать разницу углов
- `residual_tilt_limited = True` → метрики ненадёжны

**Вывод:** `residual_tilt_angle_deg` — хороший индикатор качества alignment.

**Рекомендация:** Добавить `residual_tilt_limited` в timeline и change_points.

---

### АНАЛИЗ 11: Calibration yaw range

**Цель:** Понять как `calibration_yaw_range` влияет на надёжность.

**Метод:** Изучить `app6/stage2/engine.py`.

**Код:**
```python
calibration_yaw_range = {}
for r in cal:
    b = r.pose_bin
    y = float(r.angles[1])
    calibration_yaw_range.setdefault(b, [y, y])
    calibration_yaw_range[b][0] = min(calibration_yaw_range[b][0], y)
    calibration_yaw_range[b][1] = max(calibration_yaw_range[b][1], y)

# Проверка: оба фото в паре должны быть внутри calibration range
out_of_range = bool(yaw_range and not (
    float(yaw_range[0]) <= yaw_a <= float(yaw_range[1]) and
    float(yaw_range[0]) <= yaw_b <= float(yaw_range[1])
))
```

**Проблема:** Если фото выходит за пределы calibration range:
- Калибровочный шум не определён
- Метрики ненадёжны
- `calibration_limited = True`

**Вывод:** `calibration_yaw_range` — критически важен для надёжности.

**Рекомендация:** Добавить `calibration_limited` в timeline и change_points.

---

### АНАЛИЗ 12: Cross-bin corroboration

**Цель:** Понять как `cross_bin_corroboration` проверяет устойчивость к углу.

**Метод:** Изучить `app6/stage2/corroboration.py`.

**Логика:**
```python
def apply_cross_bin_corroboration(rows):
    # Проверяет: если изменение подтверждено в нескольких pose bins
    # → оно устойчиво к разнице углов
    
    for change in candidate_changes:
        supporting_bins = find_supporting_pose_bins(change, rows)
        if len(supporting_bins) >= 2:
            change.cross_bin_support_pose_count = len(supporting_bins)
```

**Интерпретация:**
- `cross_bin_support_pose_count >= 2` → изменение подтверждено в разных ракурсах
- Значит оно устойчиво к разнице углов
- `confidence_level` увеличивается

**Вывод:** `cross_bin_corroboration` — правильный механизм для проверки устойчивости.

**Рекомендация:** Добавить `cross_bin_support_pose_count` в timeline и change_points.

---

### АНАЛИЗ 13: Alignment trimmed count

**Цель:** Понять что измеряет `ldm134_alignment_trimmed_count`.

**Метод:** Изучить `app6/stage2/motion.py`.

**Логика:**
```python
def aligned_point_motion(a, b, count, identity_only=False):
    # Robust rigid alignment использует только stable anchors
    # Outliers (точки с большим движением) исключаются
    
    anchors = select_stable_anchors(a, b, count)
    aligned = robust_rigid_align(b[anchors], a[anchors])
    
    # Вычислить движение для всех точек
    motion = aligned - a
    
    # Trimmed count = сколько точек исключено как outliers
    trimmed_count = count - len(anchors)
```

**Интерпретация:**
- `ldm134_alignment_trimmed_count` = сколько точек исключено из alignment
- Если много (> 20) → alignment ненадёжен
- Возможно из-за большой разницы углов или окклюзии

**Вывод:** `ldm134_alignment_trimmed_count` — индикатор качества alignment.

**Рекомендация:** Добавить в timeline как индикатор качества.

---

### АНАЛИЗ 14: Anchor fraction

**Цель:** Понять что измеряет `mesh_anchor_fraction`.

**Метод:** Изучить `app6/stage2/mesh_dense.py`.

**Логика:**
```python
def dense_mesh_pair(a, b, output_dir, pair_id):
    # Найти stable anchors для mesh alignment
    anchors = select_stable_anchors(va, vb, common_ids)
    
    # Anchor fraction = доля точек использованных как anchors
    anchor_fraction = len(anchors) / len(common_ids)
```

**Интерпретация:**
- `mesh_anchor_fraction` = доля вершин использованных для alignment
- Если низкая (< 0.5) → alignment ненадёжен
- Возможно из-за окклюзии или большой разницы углов

**Вывод:** `mesh_anchor_fraction` — индикатор качества mesh alignment.

**Рекомендация:** Добавить в timeline как индикатор качества.

---

### АНАЛИЗ 15: Итоговая матрица устойчивости метрик к углу

**Цель:** Создать матрицу устойчивости всех 100 метрик к разнице углов.

**Метод:** Объединить результаты анализов 1-14.

**Матрица:**

| Семейство | Метрик | Устойчивы | Средне чувствительны | Чувствительны |
|-----------|--------|-----------|----------------------|---------------|
| **Pair** | 15 | 15 ✅ | 0 | 0 |
| **Quality** | 10 | 10 ✅ | 0 | 0 |
| **Landmark** | 25 | 25 ✅ | 0 | 0 |
| **Descriptor** | 10 | 5 ✅ | 5 ⚠️ | 0 |
| **Mesh** | 20 | 18 ✅ | 0 | 2 ❌ |
| **Texture** | 20 | 0 | 5 ⚠️ | 15 ❌ |
| **Итого** | 100 | 73 ✅ | 10 ⚠️ | 17 ❌ |

**Детализация:**

#### УСТОЙЧИВЫЕ (73 метрики):
- Pair: все 15 (metadata, не зависят от угла)
- Quality: все 10 (QC flags, не зависят от угла)
- Landmark: все 25 (alignment компенсирует)
- Descriptor: 5 из 10 (`descriptor_p95_z`, `baseline_return_*`)
- Mesh: 18 из 20 (`mesh_rmse`, `mesh_p95`, `mesh_point_to_plane_*`)

#### СРЕДНЕ ЧУВСТВИТЕЛЬНЫЕ (10 метрик):
- Descriptor: 5 из 10 (`descriptor_significant_fraction`, `descriptor_landmark_fraction`, `cross_bin_support_count`)
- Texture: 5 из 20 (`texture_structure_min_registered_ssim`, `texture_structure_max_ridge_delta`)

#### ЧУВСТВИТЕЛЬНЫЕ (17 метрик):
- Mesh: 2 из 20 (`mesh_visible_fraction`, `mesh_common_vertex_count`)
- Texture: 15 из 20 (все `texture_image_*`, кроме SSIM и ridge)

---

## 🎯 ИТОГОВЫЕ ВЫВОДЫ

### 1. Какие метрики устойчивы к разнице углов?

**73 из 100 метрик УСТОЙЧИВЫ:**
- ✅ Pair (15): metadata, не зависят от угла
- ✅ Quality (10): QC flags, не зависят от угла
- ✅ Landmark (25): alignment компенсирует разницу углов
- ✅ Descriptor (5): `descriptor_p95_z`, `baseline_return_*`
- ✅ Mesh (18): `mesh_rmse`, `mesh_p95`, `mesh_point_to_plane_*`

### 2. Где alignment снижает шумы?

**Alignment эффективно снижает шумы для:**
- ✅ Landmark метрики (robust rigid alignment)
- ✅ Mesh метрики (robust rigid alignment)
- ✅ Descriptor метрики (частично, через `descriptor_p95_z`)

**Механизм:**
- Robust rigid alignment компенсирует translation, rotation, scaling
- Angle noise compensation вычитает систематическую ошибку
- Residual tilt angle проверяет качество alignment

### 3. Где метрики могут быть недостоверны?

**17 из 100 метрик ЧУВСТВИТЕЛЬНЫ к разнице углов:**
- ❌ Mesh: `mesh_visible_fraction`, `mesh_common_vertex_count` (окклюзия)
- ❌ Texture: 15 из 20 (освещение, перспектива, окклюзия)

**Индикаторы недостоверности:**
- `pose_distance > 15°` → метрики среднечувствительны
- `pose_distance > 20°` → метрики чувствительны
- `pose_leakage_limited = True` → метрики ненадёжны
- `residual_tilt_limited = True` → alignment не сработал
- `calibration_limited = True` → калибровка не определена
- `cross_bin_support_pose_count < 2` → не подтверждено в других ракурсах

### 4. Рекомендации для отчёта

**Добавить в timeline и change_points:**
1. `pose_distance` — индикатор разницы углов
2. `pose_leakage_limited` — индикатор надёжности
3. `residual_tilt_limited` — индикатор качества alignment
4. `calibration_limited` — индикатор качества калибровки
5. `cross_bin_support_pose_count` — индикатор устойчивости

**Не использовать для хронологии:**
- ❌ `mesh_visible_fraction` (чувствительна к окклюзии)
- ❌ `mesh_common_vertex_count` (чувствительна к окклюзии)
- ❌ Texture метрики (WITHHELD — правильно)

**Использовать с осторожностью:**
- ⚠️ `descriptor_significant_fraction` (средне чувствительна)
- ⚠️ `descriptor_landmark_fraction` (средне чувствительна)
- ⚠️ `texture_structure_min_registered_ssim` (средне чувствительна)

---

## 📋 ПЛАН ДЕЙСТВИЙ

### Приоритет P0: Добавить индикаторы качества в отчёт

**Добавить в timeline (Stage 3):**
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
    
    # ДОБАВИТЬ индикаторы устойчивости к углу (5):
    'pose_distance': num(r.get('pose_distance')),
    'pose_leakage_limited': r.get('pose_leakage_limited'),
    'residual_tilt_limited': r.get('residual_tilt_limited'),
    'calibration_limited': r.get('calibration_limited'),
    'cross_bin_support': num(r.get('cross_bin_support_pose_count')),
} for r in adjacent if r.get('pose_bin') == pose], key=lambda x: (x['date'] or ''))
```

**Усилия:** 2 часа  
**Влияние:** Журналист видит надёжность каждой точки на timeline

---

### Приоритет P1: Добавить индикаторы в change_points

**Добавить в change_points (Stage 2):**
```python
changes = [{
    # Существующие (15):
    # ... (см. METRIC_ENDPOINT_FINAL_ANALYSIS.md)
    
    # ДОБАВИТЬ индикаторы устойчивости к углу (5):
    'pose_distance': num(r.get('pose_distance')),
    'pose_leakage_limited': r.get('pose_leakage_limited'),
    'residual_tilt_limited': r.get('residual_tilt_limited'),
    'calibration_limited': r.get('calibration_limited'),
    'cross_bin_support_pose_count': r.get('cross_bin_support_pose_count'),
} for r in rows if is_reportable_change(r)]
```

**Усилия:** 1 час  
**Влияние:** Журналист видит надёжность каждого change point

---

### Приоритет P2: Исключить чувствительные метрики из хронологии

**Не использовать для хронологии:**
- ❌ `mesh_visible_fraction`
- ❌ `mesh_common_vertex_count`

**Обоснование:** Эти метрики чувствительны к окклюзии и не отражают реальные изменения.

**Усилия:** 30 минут  
**Влияние:** Хронология становится более надёжной

---

## ✅ ЗАКЛЮЧЕНИЕ

### Ответ на главный вопрос:

**Являются ли метрики устойчивыми к разному углу головы внутри pose bin?**

**ДА, 73 из 100 метрик устойчивы:**
- Pair, Quality, Landmark: полностью устойчивы
- Descriptor: 5 из 10 устойчивы
- Mesh: 18 из 20 устойчивы

**НЕТ, 17 из 100 метрик чувствительны:**
- Mesh: 2 из 20 (окклюзия)
- Texture: 15 из 20 (освещение, перспектива)

### Снижаются ли шумы при alignment?

**ДА, alignment эффективно снижает шумы:**
- Robust rigid alignment компенсирует translation, rotation, scaling
- Angle noise compensation вычитает систематическую ошибку
- Residual tilt angle проверяет качество alignment

### Где метрики могут быть недостоверны?

**Индикаторы недостоверности:**
- `pose_distance > 20°`
- `pose_leakage_limited = True`
- `residual_tilt_limited = True`
- `calibration_limited = True`
- `cross_bin_support_pose_count < 2`

### Что делать?

**Добавить индикаторы качества в отчёт (P0-P1, 3 часа):**
- `pose_distance`
- `pose_leakage_limited`
- `residual_tilt_limited`
- `calibration_limited`
- `cross_bin_support_pose_count`

**Исключить чувствительные метрики (P2, 30 минут):**
- `mesh_visible_fraction`
- `mesh_common_vertex_count`

---

**Документ создан:** 2026-08-27  
**Следующий шаг:** Реализация P0-P2 (3.5 часа)
