# АУДИТОРСКИЙ ОТЧЁТ v3.3 — ЧАСТЬ 2: Глубокий аудит app6/stage2, stage2b, stage3, 3ddfav3, UI

## Статус: КРИТИЧЕСКИЕ ПРОБЛЕМЫ НАЙДЕНЫ

---

## 1. 3ddfav3/util/uv_texture_generator.py — МЁРТВЫЙ КОД

### Проблема: 399 строк кода, который КОНФЛИКТУЕТ с uv_module

Этот файл — **старый UV texture generator** от 3DDFA_V3, использующий:
- `torch` (GPU-зависимый, не работает на M1 CPU)
- `scipy.ndimage` 
- Renderer-based подход (per-vertex colors → UV rasterization)

**Критическая проблема:** Этот файл делает **противоположное** тому, что делает `uv_module/generator.py`:

| Старый (3ddfav3/util/uv_texture_generator.py) | Новый (uv_module/generator.py) |
|---|---|
| Per-vertex colors → renderer → UV | Per-texel inverse mapping → cv2.remap |
| Убивает детали между вершинами | Сохраняет все детали из фото |
| Зависит от torch + GPU renderer | Чистый numpy + OpenCV (M1) |
| CLAHE + unsharp mask на АНАЛИТИЧЕСКОЙ текстуре | Аналитическая текстура БЕЗ изменений |
| `_enhance_texture_details()` вызывается **3 раза** | Enhancement только для morph текстуры |
| `_mirror_texture()` — примитивный flip с gradient blend | Multi-band Laplacian pyramid + LAB match |
| `texture_size=1024` (превышает limit 1000) | `uv_size <= 1000` (forensic limit) |

**Вердикт:** Этот файл **никогда не должен использоваться**. Он полностью заменён `uv_module`.

---

## 2. app6/stage2/engine.py — ГИГАНТСКИЙ МЕТОД

### Проблема: Stage2Engine.run() — 100+ строк в одном методе

Это самый большой и сложный файл проекта (166 строк в `run()`). Он делает:
1. Загрузку 10+ файлов конфигурации
2. Построение моделей шума (landmark, mesh, descriptor)
3. Цикл по парам с 10+ вычислениями на пару
4. Пост-обработку (FDR, chronology, corroboration, pose leakage)
5. Запись 30+ файлов

**Ошибки и проблемы:**

### BUG S2-1: `descriptor_score` вызывается с 3 аргументами, но метод ожидает `pose, a, b`

```python
# В engine.py:
descriptor_score = descriptor_model.score(a.pose_bin, a, b)
```

Это выглядит правильно, но нужно проверить — в descriptors.py метод `score()` действительно принимает `(pose, a, b)`. ✅ OK

### BUG S2-2: `_persistence()` модифицирует `status` в `rows` ПОСЛЕ того как данные уже записаны

```python
# В engine.py, _persistence():
if r['status']=='coherent_jump_candidate' and any(...):
    r['status']='persistent_geometric_change'
```

Это вызывается **до** записи в CSV, но **после** того как `evidence_state` уже вычислен для некоторых строк. Нужно проверить порядок.

**На самом деле:** `_persistence()` вызывается до `evidence_state` перепроверки, так что это OK. ✅

### PROBLEM S2-3: Отсутствие UV-текстурных метрик в Stage2

Stage2 engine вызывает:
- `texture_pair_deltas()` — image-space LBP/GLCM/Gabor
- `dense_mesh_pair()` — 3D mesh residual
- `aligned_point_motion()` — landmark motion

Но **НЕ вызывает** `uv_module/skin_analysis.py` для UV-пространственного анализа!
UV-анализ делается только на stage1 (в `assets.py`), но результаты не попадают
в Stage2 попарное сравнение.

**Это критический пробел:** морщины и микрорельеф кожи не сравниваются
хронологически, хотя данные для этого уже генерируются в stage1.

---

## 3. app6/stage2/core.py — Проблемы с robust_rigid_align

### PROBLEM S2-4: Kabsch alignment без масштаба

`_rigid_align()` и `robust_rigid_align()` намеренно **не оценивают масштаб**.
Это правильно для face comparison (разные люди могут иметь разные размеры
лица), но может быть проблемой если фото разного разрешения.

Проверка: `aligned = src @ rotation + translation` — да, scale не оценивается.
Это **правильное** решение для forensic pipeline. ✅

### PROBLEM S2-5: `_stats()` не защищён от пустого массива

```python
def _stats(distance: np.ndarray) -> dict[str, float]:
    return {
        "max": float(np.max(distance)),
    }
```

Если `distance` пустой, `np.max()` выбросит ValueError. Но это защищено
выше по стеку проверкой `common106.sum() < min_points106`. ✅ OK

---

## 4. app6/stage2/mesh_dense.py — Проблемы с anatomical zones

### BUG S2-6: `load_anatomical_zones()` загружает из JSON, которого нет

```python
ZONE_INDEX_PATH = Path(__file__).with_name("mesh_zone_indices.json")
```

Этот файл `mesh_zone_indices.json` **не существует** в репозитории!
`load_anatomical_zones()` вернёт `{}` и код упадёт в fallback
(`coordinate_grid_fallback_v1`), который делит вершины на 9 зон
по квантилям X/Y координат.

Это не критично (fallback работает), но **координатные зоны — не анатомические**.
Для forensic анализа лица нужны zones: forehead, nose bridge, cheeks, jaw и т.д.

**Решение:** Нужно создать `mesh_zone_indices.json` с реальными анатомическими
зонами BFM/3DDFA модели (35709 вершин).

### PROBLEM S2-7: `MESH_COUNT = 35709` захардкожен

Если модель изменится (другая версия 3DDFA), это число будет неправильным.
Лучше брать из `reconstruction.npz`.

---

## 5. app6/stage2/mesh_calibration.py — OK, но есть ограничения

### PROBLEM S2-8: MeshNoiseModel требует калибровочные данные

Если `calibration_root` не содержит реконструкций mesh, `MeshNoiseModel`
вернёт `status: "unavailable"` и все mesh-метрики будут `uncalibrated`.
Это ожидаемое поведение, но для датасета Путина нужно убедиться,
что калибровка включает полные реконструкции.

---

## 6. app6/stage1/quality_zones.py — Только forehead зоны

### PROBLEM S2-9: Только 3 зоны (forehead_L/C/R) и только для 3 поз

```python
if pose_bin not in {"frontal", "left_light", "right_light"}:
    status.append("unsupported_pose")
```

**9 ракурсов датасета**, но quality zones работают только для 3!
Для `left_mid`, `left_deep`, `left_profile`, `right_mid`, `right_deep`,
`right_profile` — зоны не создаются.

Это критический пробел: боковые ракурсы составляют 6 из 9 поз,
но quality gates для них отсутствуют.

**Решение:** Расширить `_forehead_fallback_zones()` для всех 9 поз,
или лучше — перейти на mesh-projected зоны.

---

## 7. app6/stage3/engine.py — HTML с inline JavaScript

### PROBLEM S2-10: 51-строчный метод с HTML шаблоном в Python

`Stage3Engine._html()` содержит огромный HTML+CSS+JS шаблон (более 200 строк)
прямо в Python коде. Это работает, но:
- Невозможно редактировать шаблон отдельно
- Нет подсветки синтаксиса
- Нет hot-reload при разработке

Не критично, но затрудняет сопровождение.

### BUG S2-11: `num()` не обрабатывает строки

```python
def num(v,default=0.0):
 try:return float(v)
 except:return default
```

Если `v` — строка типа `"0.5"` → OK. Но если `v = ""` (пустая строка из CSV) →
`float("")` → ValueError → default. Это правильное поведение. ✅

### PROBLEM S2-12: Stage3 не использует UV-анализ кожи

Stage3 отображает:
- Landmark motion maps
- Chronology timelines
- Change points
- Status summaries

Но **не отображает** результаты UV skin analysis (морщины, текстура, поры).
Это потому что эти данные не передаются из Stage2.

---

## 8. ui/server.py — Неполная реализация

### PROBLEM S2-13: server.py ссылается на `3ddfav3/assets/`

```python
assets={x:(PROJECT/'3ddfav3/assets'/x).is_file() for x in [...]}
```

Но в репозитории папка называется `3ddfav3` без подпапки `assets`.
Веса модели лежат в другом месте. Doctor check всегда fails.

---

## 9. КРИТИЧЕСКИЙ АРХИТЕКТУРНЫЙ ПРОБЕЛ: UV Skin Analysis не попадает в Stage2

Это **самая важная проблема** обнаруженная в этом аудите:

```
Текущий поток данных:

  Фото → Stage1 → assets.py
                     ├── UV analytic texture ✅
                     ├── UV morph texture ✅  
                     ├── SkinAnalyzer.analyze_full() ✅
                     │    ├── UV geometry metrics ✅
                     │    └── Image texture metrics ✅
                     ├── texture_forensics.json ✅
                     └── wrinkle_zones.json ✅
                           
  Stage1 → Stage2 → engine.py
                      ├── texture_pair_deltas() ← image-space only!
                      ├── dense_mesh_pair() ← 3D mesh only!
                      ├── aligned_point_motion() ← landmarks only!
                      └── ❌ NO UV GEOMETRY COMPARISON
                          
  Stage2 → Stage3 → report
                      ├── Landmark motion maps ✅
                      ├── Chronology timelines ✅
                      └── ❌ NO WRINKLE/MICRO-RELIEF COMPARISON
```

**UV-геометрия морщин (Frangi + skan) анализируется на Stage1,
но РЕЗУЛЬТАТЫ НЕ ПОПАДАЮТ в попарное сравнение Stage2!**

Это значит, что хронологическое сравнение морщин (которое является
ключевым для теории о двойниках) **полностью отсутствует** в pipeline.

---

## 10. ПЛАН ИСПРАВЛЕНИЙ (ЧАСТЬ 2)

### Приоритет 1: Передача UV-метрик в Stage2

1. В `assets.py` — сохранить UV geometry metrics в `reconstruction.npz`
2. В `loaders.py` — загрузить UV metrics в Record
3. В `stage2/uv_comparison.py` (НОВЫЙ) — сравнить UV metrics между парами
4. В `engine.py` — вызвать UV comparison

### Приоритет 2: Anatomical mesh zones

5. Создать `mesh_zone_indices.json` с 23 зонами BFM

### Приоритет 3: Quality zones для всех 9 поз

6. Расширить `_forehead_fallback_zones()` для left_mid, left_deep, left_profile,
   right_mid, right_deep, right_profile

### Приоритет 4: UI/Doctor fixes

7. Исправить path в server.py
8. Удалить или задокументировать 3ddfav3/util/uv_texture_generator.py
