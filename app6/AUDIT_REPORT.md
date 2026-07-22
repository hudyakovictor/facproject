# DEEPUTIN app6 — Полный аудит системы
# Дата: 2026-07-22
# Приоритет: точность alignment для хронологии + исключение шумов от наклона головы

---

## 1. РЕЗЮМЕ ПРОБЛЕМ

### 1.1 Критические ошибки (влияют на научную достоверность)

| # | Модуль | Проблема | Влияние |
|---|--------|----------|---------|
| C1 | `geometry.py` → `row_rotation_matrix` | Canonical alignment корректирует только YAW, игнорируя pitch/roll вариации внутри одного pose bin | Шумы от наклона головы НЕ исключаются при сравнении фото внутри одного ракурса |
| C2 | `reconstruction.py` → `process` | `vertices_bin_canonical` строится из `vertices_object_normalized` (полная нормализация меша), что усредняет форму и сглаживает индивидуальные особенности | Потеря индивидуальных черт лица, невозможность различить разных людей |
| C3 | `stage1/engine.py` → `_one` | Ландмарки сохраняются в 5 разных системах координат без единой точки отсчета для хронологии | Данные из разных фото непригодны для прямого сравнения |
| C4 | `skin/projection.py` → `rasterize_surface` | Растеризация на CPU треугольник за треугольником — медленно и потенциально неточно на границах | Артефакты на границах треугольников в quality maps |

### 1.2 Существенные проблемы (влияют на эффективность)

| # | Модуль | Проблема | Влияние |
|---|--------|----------|---------|
| S1 | `assets.py` → `save_uv_and_mesh` | Создаётся 9+ файлов рендеров (uv_texture, uv_texture_beauty, mesh.obj, mesh.mtl, previews...) | Избыточные данные, путаница, лишнее место на диске |
| S2 | `skin/quality.py` → `quality_maps` | Дублирование quality_weight вычислений между physical и pose-weighted версиями | Путаница в том, какой weight используется для финального анализа |
| S3 | `stage1/quality_zones.py` | Полностью дублирующий модуль — forehead fallback больше не используется (есть skin pipeline) | Мёртвый код, создаёт файлы которые никто не читает |
| S4 | `skin/pipeline.py` → `build_skin_package` | Создаётся ~15 файлов на каждое фото, многие из которых — диагностические превью | Перегрузка файловой системы |

### 1.3 Архитектурные проблемы

| # | Проблема | Влияние |
|---|----------|---------|
| A1 | Нет единого контракта для "aligned landmarks для хронологии" | Stage2 использует `ldm134_aligned.csv` но не знает как именно они выровнены |
| A2 | Калибровочный датасет обрабатывается отдельно (run_calibration.py) | Дублирование кода, рассинхрон в версиях |
| A3 | Нет валидации что alignment действительно убрал pitch/roll шумы | Невозможно верить результатам хронологии |

---

## 2. ДЕТАЛЬНЫЙ АНАЛИЗ ПО МОДУЛЯМ

### 2.1 `stage1/geometry.py` — Alignment (КРИТИЧЕСКИЙ)

#### Текущая реализация:
```python
def classify_pose(yaw: float) -> tuple[str, float]:
    # 9 бинов по yaw, каждый с canonical_yaw
    # frontal: -10..10 → canonical 0
    # left_light: -25..-10 → canonical -17.5
    # и т.д.

def row_rotation_matrix(pitch_deg, yaw_deg, roll_deg):
    # Стандартная Euler rotation: Rz @ Ry @ Rx, транспонированная
    return (rz @ ry @ rx).T
```

#### Проблема C1: Неполная коррекция позы

Сейчас в `reconstruction.py`:
```python
canonical_rotation = row_rotation_matrix(0.0, canonical_yaw, 0.0)
canonical = (normalized @ canonical_rotation).astype(np.float32)
```

Это значит:
1. Меш нормализуется (центр + RMS scale)
2. Поворачивается только на canonical_yaw (pitch=0, roll=0)
3. **НО** реальное фото может иметь pitch=5°, roll=-3° внутри одного бина
4. Эти остаточные углы НЕ корректируются → шумы в сравнении

#### Что должно быть:

Для сравнения фото внутри одного pose bin нужно:
1. Нормализовать меш (центр + scale) — ✓ уже есть
2. Повернуть на **полную** разницу между реальной позой и канонической:
   - `delta_pitch = 0 - actual_pitch` (целевое pitch для всех = 0)
   - `delta_yaw = canonical_yaw - actual_yaw`
   - `delta_roll = 0 - actual_roll` (целевое roll для всех = 0)
3. Применить `row_rotation_matrix(delta_pitch, delta_yaw, delta_roll)`

Это обеспечит что ВСЕ фото внутри бина будут иметь одинаковую позу (0, canonical_yaw, 0).

#### Проблема C2: Чрезмерная нормализация

`normalize_mesh` использует RMS scale по ВСЕМУ мешу. Это усредняет форму.
Для хронологии важнее сохранить пропорции. Лучше использовать:
- Фиксированные анатомические точки для scale (например, межглазное расстояние)
- Или хотя бы сохранить исходный scale в метаданных

### 2.2 `stage1/reconstruction.py` — 3DDFA обёртка

#### Что делает правильно:
- Один проход сети (нет двойного inference)
- Корректный capture alpha и renderer visibility
- Правильная комбинация front_facing & renderer_visible

#### Проблема C3: Множественные системы координат

Сохраняется:
- `vertices_object` — исходная реконструкция
- `vertices_identity_only` — только identity (без экспрессии)
- `vertices_object_normalized` — нормализованный
- `vertices_bin_canonical` — canonical pose
- `vertices_camera` — camera space
- `vertices_image_224` — 224x224 image plane

Для хронологии нужна **одна** система:
- `vertices_identity_only` + canonical pose + сохранённый scale/center
- ИЛИ `vertices_bin_canonical` но с полной коррекцией позы

#### Что нужно исправить:
1. Добавить `vertices_chronology_aligned` — с полной коррекцией pitch/yaw/roll
2. Сохранить `chronology_pose_correction` — какой rotation matrix был применён
3. Убрать дублирующие сохранения

### 2.3 `stage1/engine.py` — Главный пайплайн

#### Проблема: Нет единого контракта для хронологии

Сейчас `info.json` содержит:
```json
{
  "pose": {"pitch": ..., "yaw": ..., "roll": ..., "pose_bin": ..., "canonical_yaw": ...},
  "landmark_contract": {
    "raw": "object identity+expression",
    "aligned": "full-mesh RMS normalized then pose-bin canonical yaw"
  }
}
```

Но НЕ содержит:
- Какой именно rotation matrix был применён
- Какой scale factor был использован
- Какие ландмарки видимы для данного ракурса

#### Что нужно добавить:
```json
{
  "chronology": {
    "alignment_method": "full_pose_correction_v1",
    "applied_rotation": [[...], [...], [...]],
    "applied_scale": 1.234,
    "applied_center": [x, y, z],
    "target_pose": [0, canonical_yaw, 0],
    "actual_pose": [pitch, yaw, roll],
    "visible_landmarks_134": [true, false, ...],
    "pose_bin_overlap": 0.85
  }
}
```

### 2.4 `stage1/masks.py` — Маски кожи

#### Что делает правильно:
- Корректная семантическая маска из 8 каналов
- Исключение глаз, бровей, губ
- Проекция обратно в оригинальное изображение через `back_resize_crop_img`
- Safety dilation для предотвращения утечки

#### Потенциальная проблема:
- `soft >= 0.50` для hard mask — жёсткий порог, может быть слишком строгим для границ кожи
- Но для хронологии это даже лучше (стабильнее)

### 2.5 `stage1/skin/projection.py` — Растеризация

#### Проблема C4: CPU растеризация

```python
for fi, t in enumerate(f):  # 70789 треугольников!
    # ... растеризация каждого треугольника
```

Это:
- Очень медленно (минуты на фото)
- Потенциально неточно на границах (z-buffer конфликты)
- Не параллелизуется

#### Решение:
- Оставить как есть для v1 (работает корректно)
- Для v2 — перенести на GPU или использовать оптимизированный numpy

### 2.6 `stage1/skin/pipeline.py` — Skin Analysis

#### Что делает правильно:
- Использует `face_mask.npz` (mask_original) — НЕ UV текстуру
- Корректная проекция атласа на фото
- Soft pose policy (не убирает evidence полностью)
- Разделение physical quality и pose prior

#### Проблема S4: Избыточные файлы

На каждое фото создаётся:
- `surface_observations.npz` — ✓ нужно для анализа
- `atlas_projection.npz` — ✓ нужно
- `quality_maps.npz` — ✓ нужно
- `features/basic_macro.npz` — ✓ нужно
- `features/texture.npz` — ✓ нужно
- `features/local_candidates.npz` — ✓ нужно
- `features/local_candidates.json` — ✓ нужно
- `wrinkles/classical.npz` — ✓ нужно
- `wrinkles/ffhq.npz` — ✓ нужно (если веса есть)
- `wrinkles/summary.json` — ✓ нужно
- `material/evidence.json` — ✓ нужно
- `sensitivity/degradation.json` — ✓ нужно
- `photometric_branches.npz` — ✓ нужно
- `contamination_maps.npz` — ✓ нужно (если face parsing есть)
- `patch_index.npz` — ✓ нужно
- `previews/` — 5-6 PNG файлов (избыточно)
- `quality.json` — ✓ нужно
- `manifest.json` — ✓ нужно

Итого: ~20+ файлов на фото. Для 1700 фото = 34000+ файлов.

#### Что можно сократить:
- `previews/` — оставить только 1-2 ключевых, остальное убрать
- `quality_weight_raw_mesh.png` — диагностический, не нужен для анализа

### 2.7 `stage1/quality_zones.py` — Дублирующий модуль (МЁРТВЫЙ КОД)

Этот модуль:
- Создаёт forehead fallback zones
- НЕ используется в основном пайплайне (есть skin pipeline)
- Создаёт файлы `quality.json` и `quality_zones.npz` которые конфликтуют с skin pipeline

**Решение**: Полностью удалить или пометить как deprecated.

### 2.8 `stage2/engine.py` — Анализ

#### Что делает правильно:
- Разделение по pose bins
- Calibration noise model
- Multiple testing correction
- Chronology rate flags
- Cross-bin corroboration

#### Проблема: Использует `ldm134_aligned.csv`

Сейчас stage2 читает aligned landmarks из stage1. Но:
- Не знает как именно они выровнены
- Не может верить что pitch/roll корректно скорректированы
- Нет валидации качества alignment

### 2.9 `stage3/engine.py` — Отчёт

Генерирует HTML отчёт. В целом корректно, но:
- Зависит от качества stage2
- Не показывает alignment quality metrics

---

## 3. ПЛАН ИСПРАВЛЕНИЙ

### Фаза 1: Критические исправления Alignment (C1, C2, C3)

#### Шаг 1.1: Исправить `geometry.py`
- [ ] Добавить `full_pose_correction_matrix(actual_pose, target_pose)`
- [ ] Сохранять delta rotation в метаданных
- [ ] Добавить валидацию что correction ортогонален

#### Шаг 1.2: Исправить `reconstruction.py`
- [ ] Вычислять `vertices_chronology_aligned` с полной коррекцией
- [ ] Сохранять `chronology_rotation_matrix` и `chronology_scale`
- [ ] Добавить `visible_landmarks_mask` для каждого ракурса

#### Шаг 1.3: Исправить `engine.py`
- [ ] Добавить `chronology` секцию в info.json
- [ ] Сохранять aligned landmarks в отдельный CSV с метаданными alignment
- [ ] Добавить валидацию что alignment убрал pitch/roll

### Фаза 2: Удаление дублирования и избыточности (S1-S4)

#### Шаг 2.1: Удалить `quality_zones.py`
- [ ] Пометить как deprecated
- [ ] Убрать вызовы из engine.py
- [ ] Удалить создаваемые файлы

#### Шаг 2.2: Сократить рендеры в `assets.py`
- [ ] Оставить только `uv_texture.png` (1 шт для визуализации)
- [ ] Убрать `uv_texture_beauty.png`
- [ ] Убрать `mesh.obj` / `mesh.mtl` (или сделать опциональными)
- [ ] Убрать диагностические превью из skin pipeline

#### Шаг 2.3: Упростить `skin/pipeline.py`
- [ ] Сократить previews до 1-2 ключевых
- [ ] Убрать `quality_weight_raw_mesh.png`
- [ ] Сделать создание превью опциональным

### Фаза 3: Архитектурные улучшения (A1-A3)

#### Шаг 3.1: Единый контракт для хронологии
- [ ] Определить JSON schema для `chronology` секции
- [ ] Документировать формат aligned landmarks
- [ ] Добавить валидацию в stage2

#### Шаг 3.2: Унифицировать калибровку
- [ ] Убрать отдельный `run_calibration.py`
- [ ] Сделать так что калибровочные фото обрабатываются тем же stage1
- [ ] Различать их только по пути/папке

#### Шаг 3.3: Валидация alignment
- [ ] Добавить метрику "alignment quality" в info.json
- [ ] Показать распределение residual pose после коррекции
- [ ] В stage2 — фильтровать пары с плохим alignment

### Фаза 4: Оптимизация (потом)

#### Шаг 4.1: GPU растеризация
#### Шаг 4.2: Параллельная обработка
#### Шаг 4.3: Кэширование промежуточных результатов

---

## 4. ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После исправлений:
1. **Alignment**: Все фото внутри pose bin будут иметь идентичную позу (0, canonical_yaw, 0)
2. **Шумы**: Pitch/roll вариации будут исключены из сравнения
3. **Хронология**: Данные из разных фото будут пригодны для прямого сравнения
4. **Файлы**: Сокращение с 20+ до ~12 файлов на фото
5. **Код**: Удаление дублирующих модулей, единый контракт

---

## 5. РИСКИ и ОГРАНИЧЕНИЯ

1. **Полная коррекция позы может сгладить форму**: Если pitch/roll большой, rotation может исказить форму. Нужен баланс.
2. **3DDFA точность**: Модель может давать неточные углы для extreme poses (>50° yaw)
3. **Canonical yaw для бинов**: Среднее значение бина может быть неоптимальным для конкретного фото
4. **Scale normalization**: RMS scale по всему мешу может маскировать реальные изменения формы

---

## 6. ПОРОЯДОК РАБОТЫ

### Неделя 1: Критические исправления
- День 1-2: Исправить alignment (geometry.py, reconstruction.py)
- День 3: Добавить chronology контракт (engine.py)
- День 4: Тестирование на калибровочных фото
- День 5: Валидация результатов

### Неделя 2: Очистка и оптимизация
- День 1-2: Удалить дублирующий код
- День 3: Сократить рендеры
- День 4: Унифицировать калибровку
- День 5: Документация

### Неделя 3: Валидация и тестирование
- Полный прогон на калибровочном датасете
- Сравнение до/после исправлений
- Настройка параметров
