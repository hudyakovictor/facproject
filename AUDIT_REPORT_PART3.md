# Аудит facproject — Часть 3: Глубокий аудит всех непроверенных модулей

**Дата:** 2026-07-19  
**Аналитик:** Forensic Face & Skin Consistency Analyst  
**Область:** Все Python-модули, не проверенные в частях 1-2  

---

## Исправленные критические баги

### 🔴 BUG-3.1: `uv_zone_list` — потеря данных UV-геометрии в Stage2 (ИСПРАВЛЕНО)

**Файл:** `app6/stage2/engine.py:96`  
**Серьёзность:** CRITICAL — хронологическое сравнение морщин полностью терялось

В цикле по парам переменная `uv_zone_list` перезаписывалась на каждой итерации:
```python
uv_row, uv_zone_list = uv_geometry_pair(a, b, o, pid)
```
В итоге `uv_zone_list` содержала данные только последней пары, а `uv_geometry_zone_metrics.csv` содержал зоны только одной пары.

**Исправление:** Переменная переименована в `uv_zone_list_local`, результат добавляется в `uv_zone_list` через `.extend()`:
```python
uv_row, uv_zone_list_local = uv_geometry_pair(a, b, o, pid)
uv_zone_list.extend(uv_zone_list_local)
```

---

### 🔴 BUG-3.2: UV-геометрия не попадает в evidence packets (ИСПРАВЛЕНО)

**Файл:** `app6/stage2/evidence.py:packet_from_pair()`  
**Серьёзность:** HIGH — UV-метрики (ridge_density_delta, branch_count_delta и т.д.) не доходили до Stage3

`measurements` dict в `packet_from_pair()` включал метрики texture_image, texture_structure, mesh, но не включал UV-geometry метрики из нового модуля `uv_comparison.py`.

**Исправление:** Добавлены 7 ключей в measurements dict:
- `uv_geometry_status`
- `uv_common_zone_count`
- `uv_max_ridge_density_delta`
- `uv_mean_ridge_density_delta`
- `uv_max_branch_count_delta`
- `uv_max_total_length_delta`
- `uv_max_ridge_strength_delta`

---

## Найденные проблемы

### 🟠 BUG-3.3: `make_photo_id()` игнорирует `source_sha256` — риск коллизии

**Файл:** `app6/stage1/naming.py:53`  
**Серьёзность:** MEDIUM

```python
def make_photo_id(parsed: PhotoName, source_sha256: str) -> str:
    return parsed.canonical_stem
```

Параметр `source_sha256` принимается, но полностью игнорируется. Если два фото с одной датой имеют одинаковый `canonical_stem`, но разные источники, они получат одинаковый `photo_id` и перезапишут друг друга. В текущем датасете Путина фото с одинаковой датой имеют разные `sequence` (1, 2, 3...), что снижает риск, но баг остаётся латентным.

**Рекомендация:** Добавить хеш в ID: `return f"{parsed.canonical_stem}_{source_sha256[:8]}"`

---

### 🟠 BUG-3.4: `load_calibration()` — несогласованные имена полей

**Файл:** `app6/stage2/loaders.py:42` vs `:67`  
**Серьёзность:** MEDIUM

Для родного app6 формата: `z["ldm106_object_normalized"]`  
Для calibration_datasets формата: `z["ldm106_object_norm"]`  

Разные имена полей (`object_normalized` vs `object_norm`) — либо разные версии схемы Stage1, либо опечатка. Если формат `object_norm` не создаётся текущим Stage1, весь калибровочный путь через `calibration_datasets/` сломается с `KeyError`.

---

### 🟠 BUG-3.5: `masks.py` — флаг `fallback_used` вводит в заблуждение

**Файл:** `app6/stage1/masks.py:56`  
**Серьёзность:** LOW

Когда `back_resize_crop_img` выбрасывает исключение, код возвращает:
```python
meta["fallback_used"] = False
```
Но фоллбэка нет — маска просто `None`. Потребитель может подумать, что fallback работает, когда на самом деле проекция провалилась. Следует установить `fallback_used = True` или переименовать поле в `projection_failed = True`.

---

### 🟡 DEAD-3.1: `save_masks()` в masks.py никогда не вызывается

**Файл:** `app6/stage1/masks.py:60-76`  
**Серьёзность:** LOW — мёртвый код

Функция `save_masks()` определена, но никогда не вызывается из `engine.py`. Вместо неё используются `save_face_mask()` и `save_semantic_channels()`. Функция сохраняет только `semantic_channels.npz` без `skin_mask_*.png`.

---

### 🟡 DEAD-3.2: `3ddfav3/model/recon.py` — импорт UVTextureGenerator на уровне модуля

**Файл:** `3ddfav3/model/recon.py:8`  
**Серьёзность:** MEDIUM

```python
from util.uv_texture_generator import UVTextureGenerator
```

Этот импорт выполняется при загрузке модуля, хотя `extractTex=False` в facproject pipeline. Если `uv_texture_generator.py` содержит ошибку или несовместимую зависимость, он крашнет весь `recon.py` даже при неиспользовании. Помечен как DEPRECATED.

**Рекомендация:** Перенести импорт внутрь `__init__` блока `if args.extractTex`.

---

### 🟡 DEAD-3.3: `_gaussian_alpha_pyramid()` — избыточный расчёт sigma

**Файл:** `uv_module/symmetry.py:130-132`  
**Серьёзность:** TRIVIAL

```python
lvl_sigma = sigma * (S / (S / (2 ** lvl)))  # Это упрощается до sigma * 2**lvl
lvl_sigma = max(1.0, sigma * (2.0 ** lvl))  # Сразу перезаписывается
```

Первая строка вычисляет значение, которое немедленно перезаписывается второй. Не баг (результат верный), но мёртвый код.

---

### 🟡 DEAD-3.4: `pose_analysis.py` дублирует `skin_analysis.py`

**Файл:** `uv_module/pose_analysis.py`  
**Серьёзность:** MEDIUM — архитектурная путаница

Оба модуля выполняют UV-zone анализ морщин:
- `pose_analysis.py::analyze_pose_zones()` — использует `wrinkle_graph_features()` из `metrics.py`
- `skin_analysis.py::SkinAnalyzer.analyze_full()` — использует Frangi + skan через `generator.py`

Из `assets.py` вызываются **оба**: `extract_texture_forensics()` (которая вызывает SkinAnalyzer) и `analyze_pose_zones()`. Это означает, что UV-анализ морщин выполняется дважды с разными пайплайнами и результаты записываются в разные JSON файлы (`texture_forensics.json` vs `wrinkle_zones.json`). Stage2 `uv_comparison.py` загружает из `texture_forensics.json` (приоритет) с фоллбэком на `wrinkle_zones.json`.

**Рекомендация:** Унифицировать: `analyze_pose_zones()` должен делегировать в `SkinAnalyzer`, а не дублировать логику.

---

### 🟡 HARDCODED-3.1: `MESH_COUNT = 35709` в двух файлах

**Файлы:** `app6/stage1/validator.py:23`, `app6/stage2/mesh_dense.py:12`  
**Серьёзность:** LOW

Хардкод `MESH_COUNT = 35709` и `TRIANGLE_COUNT = 70789`. При смене BFM модели или использовании другого количества вершин всё сломается. Следует читать из `face_model.npy` или `reconstruction.npz`.

---

### 🟡 STUB-3.1: `texture_pair.py` — заглушка без реального сравнения текстур

**Файл:** `app6/stage2/texture_pair.py`  
**Серьёзность:** MEDIUM — функциональный пробел

`summarize_texture_pairs()` проверяет только readiness quality-зон, но не вычисляет реальные текстурные различия (LBP χ², GLCM контраст, Laplacian delta и т.д.). Реальное сравнение текстур делается в `texture_image.py` и `texture_structure.py`. Роль этого модуля — просто заполнять метрики `texture_pair_status` и `usable_texture_zone_count` в pair_metrics.csv.

---

### 🟡 mesh_zone_indices.json — качество зон

**Файл:** `app6/stage2/mesh_zone_indices.json`  
**Серьёзность:** LOW

Файл существует (создан после Part 2 аудита), содержит 23 зоны. Проблемы:
- `chin`: 1 вершина (33838) — недостаточно для статистики
- `ligament_zygomatic_L/R`: 2 вершины — тоже слишком мало
- `nose_wing_L` и `nose_bridge_tip` полностью перекрывают друг друга (одинаковые вершины)
- `cheek_soft_L/R`: 2 вершины — слишком мало

`mesh_dense.py` требует минимум 40 вершин на зону (`min_zone_vertices = 40`), поэтому эти зоны будут отброшены как `insufficient_visibility`. Зоны с малым числом вершин не вредят, но и не помогают.

---

## Архитектурные наблюдения

### Полная схема пайплайна (подтверждена кодом)

```
Фото → Stage1 (3DDFA reconstruction + UV + SkinAnalyzer) 
     → Stage2 (хронологические пары с калибровкой)
       ├── compare_landmarks()      → ldm106/134 residuals, zones
       ├── aligned_point_motion()   → per-landmark motion vectors  
       ├── dense_mesh_pair()        → dense mesh residual + anatomical zones
       ├── texture_pair_deltas()    → image-space LBP/GLCM/Laplacian
       ├── uv_geometry_pair()       → UV wrinkle ridge/skeleton deltas
       ├── apply_alpha_chronology() → alpha_id/alpha_exp signals
       ├── apply_baseline_return()  → A→B→C reversal detection
       ├── apply_chronology_rate()  → temporal rate flags
       ├── apply_cross_bin()        → cross-pose corroboration
       └── packet_from_pair()       → evidence packet → Stage3
     → Stage2B (private corroboration against prior leads)
     → Stage3 (HTML report)
```

### Ключевые архитектурные решения (подтверждены)

1. **Двухпространственный анализ кожи** — UV-space (Frangi+skan, pose-invariant) и Image-space (LBP/GLCM, sensor-accurate) — правильно, UV-ресемплинг разрушает поры
2. **Iteratively trimmed Kabsch alignment** — Robust rigid alignment без масштаба — правильно, масштаб бы «впитал» размерные различия в трансформ
3. **Benjamini-Hochberg FDR** на z-score приближениях — консервативно, но корректно для множественного тестирования
4. **Public safety** — `FORBIDDEN_PUBLIC_TERMS` блокирует термины «двойник», «подмена» и т.д. из evidence packets — правильно для форензического отчёта
5. **Separate analysis vs morph textures** — analysis=только реальные пиксели, morph=Laplacian pyramid blend — правильно, forensic purity

### Новые находки в 3ddfav3/model/recon.py

- **Line 8:** `from util.uv_texture_generator import UVTextureGenerator` — импорт dead-code модуля на уровне модуля
- **Line 232:** `texture_size = getattr(args, 'texture_size', 1024)` — default 1024 превышает лимит 1000px
- **extractTex path:** Не используется в facproject (args.extractTex=False), но latent dependency
- **`process_uv()` line 31:** Мутирует входной массив `uv_coords[:,0]` и `uv_coords[:,1]` in-place — может быть источником багов если массив используется повторно

---

## Сводка по всем трём частям аудита

| Категория | Часть 1 | Часть 2 | Часть 3 | Итого |
|-----------|---------|---------|---------|-------|
| CRITICAL | 3 | 1 | 2 (исправлены) | 6 |
| HIGH | 2 | 2 | 0 | 4 |
| MEDIUM | 4 | 3 | 4 | 11 |
| LOW | 3 | 2 | 4 | 9 |
| TRIVIAL | 0 | 0 | 1 | 1 |
| DEPRECATED/DEAD | 1 | 1 | 3 | 5 |

### Статус исправлений

- ✅ `uv_zone_list` accumulation bug — ИСПРАВЛЕНО
- ✅ UV metrics in evidence packets — ИСПРАВЛЕНО  
- ✅ `uv_texture_generator.py` — помечен DEPRECATED
- ⬜ `make_photo_id()` collision risk — требуется решение
- ⬜ `load_calibration()` inconsistent field names — требуется решение
- ⬜ `recon.py` module-level UVTextureGenerator import — требуется ленивый импорт
- ⬜ `pose_analysis.py` дублирование skin_analysis.py — требуется унификация
- ⬜ Stage3 engine — не отображает UV geometry results — требуется обновление
- ⬜ End-to-end integration test — отсутствует
