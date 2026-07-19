# Аудиторский отчёт Part 8: Глубокая перепроверка + критические исправления

**Дата:** 2026-07-19  
**Аудитор:** Forensic Face & Skin Consistency Analyst  
**Область:** Перепроверка ранее «✅» файлов + исправление оставшихся критических багов  

---

## Резюме

В этом раунде проведена:
1. Глубокая перепроверка 11 файлов, ранее помеченных как «✅» (без багов) — **подтверждено: чистый код**.
2. Исправление **5 новых багов** (3 критических, 2 средних).
3. Удаление **мертвого кода** (fat_face, 44 строки).
4. Общее число исправленных багов за всю историю аудита: **51**.

Все 55 тестов проходят после всех изменений.

---

## Перепроверенные файлы (без багов)

| Файл | Строк | Результат |
|------|-------|-----------|
| `uv_module/config.py` | 128 | ✅ Чисто — HDUVConfig dataclass с валидацией |
| `uv_module/rasterizer.py` | 161 | ✅ Чисто — UVRaster + barycentric + cache |
| `uv_module/symmetry.py` | 341 | ✅ Чисто — Laplacian pyramid blend + LAB match |
| `uv_module/visibility.py` | 156 | ✅ Чисто — angle weight + z-buffer + depth interpolation |
| `uv_module/chronology.py` | 153 | ✅ Чисто — match_branches + pose-aware pairing |
| `uv_module/zones.py` | 152 | ✅ Чисто — 13 ZoneSpec + POSE_POLICY для 9 pose |
| `uv_module/calibration.py` | 123 | ✅ Чисто — stratified holdout + load_records |
| `app6/stage2/texture_image.py` | 361 | ✅ Чисто — LBP/GLCM/Gabor/frequency per zone |
| `app6/stage1/quality_zones.py` | 314 | ✅ Чисто — forehead fallback для 9 poses |
| `app6/stage2/evidence.py` | 177 | ✅ Чисто — EvidencePacket + packet_from_pair() |
| `app6/stage2/texture_structure.py` | 181 | ✅ Чисто — phase correlation + ridges + SSIM |

---

## Исправленные баги (5 новых)

### BUG-49: Двойной UV-анализ в `app6/stage1/assets.py` (КРИТИЧЕСКИЙ)

**Проблема:** `save_uv_and_mesh()` вызывает `extract_texture_forensics()`, который уже **внутренне** вызывает `SkinAnalyzer.analyze_uv_geometry()` и сохраняет результат в `report["uv_geometry"]`. Сразу после этого `save_uv_and_mesh()` создаёт **новый** `SkinAnalyzer` и вызывает `analyze_uv_geometry()` **повторно** — полная дубликация Frangi + skeleton + skan вычислений.

**Следствие:** На MacBook M1 для одного фото UV-анализ запускается дважды, удваивая время обработки (Frangi на 4 sigma + skeleton + skan — одна из самых тяжёлых операций). Также в forensic_report записываются результаты первого вызова, а в wrinkle_report — второго, хотя данные идентичны.

**Исправление:** Извлечь `uv_geom` из `forensic_report["uv_geometry"]` (результат уже вычислен внутри `extract_texture_forensics()`). Фолбэк на явный вызов `SkinAnalyzer` только если `uv_geometry` отсутствует (когда skin_mask=None и расширенный two-space path не запускался).

```python
# ДО:
analyzer = SkinAnalyzer(cfg)
uv_geom = analyzer.analyze_uv_geometry(analysis, np.asarray(observed, bool), str(bundle.pose_bin))

# ПОСЛЕ:
uv_geom = forensic_report.get("uv_geometry")
if uv_geom is None:
    analyzer = SkinAnalyzer(cfg)
    uv_geom = analyzer.analyze_uv_geometry(analysis, np.asarray(observed, bool), str(bundle.pose_bin))
```

---

### BUG-50: Захардкоженный `35709` в `3ddfav3/model/recon.py` `forward()` (КРИТИЧЕСКИЙ)

**Проблема:** `visible_idx = torch.zeros(35709)` — магическое число, жёстко закодированное количество вершин BFM. Если модель face_model.npy изменится (другая топология, усечённый меш), `visible_idx` будет неправильного размера → IndexError или тихая потеря данных.

**Дополнительное место:** `self.v_parallel = - torch.ones(35709, ...)` в `__init__` — та же проблема.

**Исправление:** Заменить на `self.uv_coords.shape[0]` — реальное количество вершин из загруженной модели.

```python
# __init__:
self.v_parallel = - torch.ones(self.uv_coords.shape[0], device=self.device).type(torch.int64)

# forward():
visible_idx = torch.zeros(self.uv_coords.shape[0]).type(torch.int64).to(v3d.device)
```

---

### BUG-51: Мёртвый метод `fat_face()` в `large_model_infer.py` (СРЕДНИЙ)

**Проблема:** Метод `fat_face()` (44 строки) вызывает `spread_flow()` и `image_warp_grid1()`, которые **нигде не определены** — импорты закомментированы. Вызов этого метода гарантированно вызывает `NameError`. Метод никогда не вызывается из facproject.

**Исправление:** Удалён метод `fat_face()`, закомментированные импорты `spread_flow`/`image_warp_grid1`, и неиспользуемый `import time`.

---

### BUG-52: `Image.BICUBIC` deprecation в `3ddfav3/util/preprocess.py` (СРЕДНИЙ)

**Проблема:** Функция `back_resize_crop_img()` имеет параметр `resample_method = Image.BICUBIC`, хотя в начале файла уже определён `RESAMPLING_METHOD` с правильным вариантом (`PIL.Image.Resampling.BICUBIC` для новых версий Pillow, с фолбэком на `Image.BICUBIC`). Остальные функции в этом файле используют `RESAMPLING_METHOD`.

**Исправление:** `resample_method = Image.BICUBIC` → `resample_method = RESAMPLING_METHOD`.

---

### BUG-53: Мутация входного массива в `3ddfav3/util/preprocess.py:back_resize_ldms()` (НИЗКИЙ)

**Проблема:** Функция `back_resize_ldms()` модифицирует входной `ldms` in-place (`ldms[:, 0] = ...`, `ldms[:, 1] = ...`), что может быть неожиданным для вызывающего кода. Остальные похожие функции в этом файле (`process_uv()`) уже используют `.copy()`.

**Исправление:** Добавлена строка `ldms = ldms.copy()` в начале функции.

---

## Итоговая статистика по всем 8 раундам аудита

| Раунд | Исправлено багов | Критических |
|-------|-----------------|-------------|
| Part 1 | 9 | 3 |
| Part 2 | 4 | 2 |
| Part 3 | 8 | 3 |
| Part 4 | 5 | 2 |
| Part 5/6 | 7 | 3 |
| Part 7 | 13 | 5 |
| **Part 8** | **5** | **2** |
| **ИТОГО** | **51** | **20** |

---

## Оставшиеся известные ограничения

1. **`mesh_dense.py` MESH_COUNT dynamic resolution** — `_resolve_mesh_count()` ищет `reconstruction.npz` на диске; на чистой установке без данных фолбэчит на 35709. Это поведение задокументировано и не ломает работу.

2. **`mesh_zone_indices.json` качество** — chin=1 вершина, ligaments=2 вершины, nose_wing_L≡nose_bridge_tip overlap. `generate_mesh_zones.py` создан, но должен запускаться после Stage1. Задокументировано.

3. **`app6/stage2/texture_pair.py`** — stub-модуль, проверяет readiness, но не проводит реальное сравнение текстур. Задокументировано как «readiness only».

4. **`uv_module/skin_analysis.py::_image_zone_mask()`** — приближённое UV→image отображение через bbox grid. Работает для фронтальных поз, менее точно для профилей. Задокументировано.

5. **Нет E2E интеграционного теста** — все 55 тестов юнит-тесты. Задокументировано как технический долг.

---

## Файловые изменения

| Файл | Изменение |
|------|-----------|
| `app6/stage1/assets.py` | Устранён двойной UV-анализ (re-use `forensic_report["uv_geometry"]`) |
| `3ddfav3/model/recon.py` | `35709` → `self.uv_coords.shape[0]` (2 места) |
| `3ddfav3/face_box/facelandmark/large_model_infer.py` | Удалён `fat_face()`, мёртвые импорты, `import time` |
| `3ddfav3/util/preprocess.py` | `Image.BICUBIC` → `RESAMPLING_METHOD`; `ldms.copy()` |
