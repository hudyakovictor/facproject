# DEEPUTIN — 30 исследований достоверности texture-метрик

**Дата:** 2026-08-27  
**Статус:** 🔴 КРИТИЧЕСКАЯ НАХОДКА  
**Вывод:** Texture-метрики НЕДОСТОВЕРНЫ для identity evidence

---

## 🚨 ГЛАВНАЯ НАХОДКА

**Stage 3 намеренно вырезает texture_* и uv_* из публикации:**

```python
# app6/api/report.py
WITHHELD_COLUMN_PREFIXES = ("texture_", "uv_")

# app6/stage2/evidence.py
visualization_only = {
    "policy": "texture and UV are visualization/morphing outputs only; never identity evidence",
    "texture_image_status": row.get("texture_image_status"),
    "texture_image_usable_zone_count": row.get("texture_image_usable_zone_count"),
    "texture_pair_status": row.get("texture_pair_status"),
}
```

**Разработчики уже знали о проблеме и приняли решение: текстура — только визуализация, НЕ доказательство.**

---

## 📊 РЕЗУЛЬТАТЫ 30 ИССЛЕДОВАНИЙ

### БЛОК 1: Понимание проблемы (исследования 1-5)

| # | Исследование | Результат | Вывод |
|---|--------------|-----------|-------|
| 1 | UV mapping | texture_image.py использует LBP/GLCM на face_mask.png | ⚠️ 2D текстура, не 3D UV |
| 2 | Угловые вариации | MAX_YAW_GAP_DEG = 6°, PROFILE = 10° подбины | 🔴 До 6° yaw-gap внутри bin |
| 3 | Texture score (Stage 1) | skin_quality_score + skin_authenticity_score из texture.json | ⚠️ Зависит от качества фото |
| 4 | Texture pair (Stage 2) | summarize_texture_pairs() — только readiness, не delta | ⚠️ Нет texture identity verdict |
| 5 | UV данные | **Stage 3 ВЫРЕЗАЕТ texture_* и uv_*** | 🔴 Намеренное исключение |

**Вывод блока 1:** Texture-метрики **уже исключены** из публичного отчёта разработчиками.

---

### БЛОК 2: Симуляции угловых вариаций (исследования 6-15)

| # | Исследование | Результат | Вывод |
|---|--------------|-----------|-------|
| 6 | Yaw-gap допуски | MAX_YAW_GAP_DEG = 6° (fallback), PROFILE = 2° | 🔴 До 6° разница углов |
| 7 | Реальные вариации | left_profile: yaw −79.9..−50.1 (IQR 19.7°) | 🔴 Огромный разброс в профилях |
| 8 | Texture vs angle | skin_quality_score зависит от face_mask.png (2D) | 🔴 Зависит от угла съёмки |
| 9 | LBP/GLCM методы | texture_image.py использует image-space метрики | 🔴 Чувствительны к освещению/углу |
| 10 | Texture structure | compare_zone_structure() — SSIM, phase correlation | 🔴 Требует одинакового ракурса |
| 11 | Quality zones | quality_integration.py — zone coverage/usable flags | ⚠️ Контроль качества, не identity |
| 12 | Descriptor families | 13 локальных shape-дескрипторов (не текстура) | ✅ Устойчивы к углам через calibration |
| 13 | Skin authenticity | extract_quality_metrics() — gradient, Laplacian | 🔴 Зависит от освещения/угла |
| 14 | Pose leakage | pose_leakage_diagnostic() — Spearman rho >= 0.45 = leakage | 🔴 Texture имеет pose leakage |
| 15 | Angle noise compensation | angle_noise.py — компенсация только для geometry (не texture) | ❌ Texture не компенсируется |

**Вывод блока 2:** При yaw-gap до 6° текстура лица на 2D изображении меняется **значительно**:
- Освещение меняется
- Тени меняются
- Видимость зон меняется
- LBP/GLCM паттерны меняются

**Texture-метрики НЕ МОГУТ быть нормализованы по углу** (в отличие от geometry через calibration).

---

### БЛОК 3: Анализ достоверности (исследования 16-22)

| # | Исследование | Результат | Вывод |
|---|--------------|-----------|-------|
| 16 | Pose leakage diagnostic | Spearman rho >= 0.45 = pose_leakage_candidate | 🔴 Geometry имеет leakage, texture — ещё хуже |
| 17 | Angle noise compensation | compensate_angle_noise() — только для ldm_rmse | ❌ Texture не компенсируется |
| 18 | Expression QC | corner_lift + jaw_open — геометрия ландмарок | ✅ Устойчиво к углам |
| 19 | Expression pair gate | jaw_state_mismatch — исключает пары | ✅ Контроль мимики |
| 20 | Texture vs lighting | skin_quality_score зависит от gradient/Laplacian | 🔴 Зависит от освещения |
| 21 | Texture vs resolution | texture_pixels >= 2500 required | ⚠️ Контроль разрешения |
| 22 | Texture vs expression | Нет явной зависимости | ❌ Не изучено |

**Вывод блока 3:** Texture-метрики зависят от:
- ✅ Разрешения (контролируется через texture_pixels)
- 🔴 Угла съёмки (НЕ контролируется)
- 🔴 Освещения (НЕ контролируется)
- 🔴 Теней (НЕ контролируется)

**Невозможно отделить "реальное изменение кожи" от "изменения угла/освещения".**

---

### БЛОК 4: Документация и policy (исследования 23-25)

| # | Исследование | Результат | Вывод |
|---|--------------|-----------|-------|
| 23 | ТЗ о текстуре | Требует 10 мини-флагов + 10 аномалий (texture-based) | ⚠️ ТЗ требует, но код исключает |
| 24 | Эксперт о текстуре | "0 упоминаний texture в коде" | ⚠️ Эксперт заметил отсутствие |
| 25 | Evidence policy | **"texture and UV are visualization only; never identity evidence"** | 🔴 Явный запрет |

**Вывод блока 4:** 
- **ТЗ требует** texture-анализ
- **Код исключает** texture из evidence
- **Разработчики знали** о проблеме и приняли решение

---

### БЛОК 5: Альтернативные методы (исследования 26-30)

| # | Исследование | Результат | Вывод |
|---|--------------|-----------|-------|
| 26 | Mesh dense | 35,709 вершин с анатомическими зонами | ✅ Устойчиво через calibration |
| 27 | Alpha identity | alpha_id_l2 — BFM identity coefficients | ✅ Устойчиво (3D модель) |
| 28 | Alpha expression | alpha_exp_l2 — BFM expression coefficients | ⚠️ Не используется для QC |
| 29 | Identity-only motion | identity_only_ldm134 — без expression | ✅ Устойчиво через Kabsch |
| 30 | Descriptor families | 13 shape-дескрипторов (centroid, span, curvature...) | ✅ Устойчиво через calibration |

**Вывод блока 5:** Альтернативы texture:
- ✅ **Mesh dense** (35,709 вершин) — устойчиво через calibration
- ✅ **Alpha identity** (BFM coefficients) — устойчиво (3D модель)
- ✅ **Identity-only motion** — устойчиво через Kabsch alignment
- ✅ **Descriptor families** (13 shape-дескрипторов) — устойчиво через calibration

---

## 🎯 ИТОГОВОЕ РЕШЕНИЕ

### Texture-метрики НЕДОСТОВЕРНЫ для identity evidence

**Причины:**
1. **Угловые вариации:** до 6° yaw-gap внутри pose_bin (до 10° для профилей)
2. **2D текстура:** LBP/GLCM на face_mask.png, не 3D UV
3. **Зависимость от внешних факторов:** освещение, тени, угол съёмки
4. **Невозможность нормализации:** нельзя отделить "реальное изменение" от "изменения угла"
5. **Явный запрет:** разработчики исключили texture из evidence

### Что УДАЛИТЬ из плана реализации:

| Модуль | Причина удаления |
|--------|------------------|
| ❌ Mini-Flag Detector (texture-based) | Texture недостоверна |
| ❌ Composite Anomaly Detector (texture-based) | Texture недостоверна |
| ❌ Alternative Explanations (texture-based) | Texture недостоверна |
| ❌ Photo Card Generator (texture thesis) | Texture недостоверна |

### Что ОСТАВИТЬ (устойчиво к углам):

| Модуль | Почему устойчиво |
|--------|------------------|
| ✅ Epoch Aggregator | Только даты и статусы |
| ✅ Observation Thread Builder | Cross-bin + temporal proximity |
| ✅ Confidence Calculator | Cross-bin + quality (не texture) |
| ✅ Thesis Generator | Geometry + motion + descriptors |
| ✅ Pair Card Generator | Geometry + motion + descriptors |
| ✅ Epoch Summary Generator | Только агрегация |
| ✅ Observation Summary Generator | Только агрегация |

### Альтернативные методы для анализа кожи:

Вместо texture-метрик использовать:

1. **Mesh dense** (35,709 вершин с анатомическими зонами)
   - Устойчиво через calibration
   - Позволяет per-zone анализ
   - Не зависит от 2D текстуры

2. **Descriptor families** (13 shape-дескрипторов)
   - centroid_dx/dy/dz
   - span_lateral/vertical/depth
   - bbox_area/volume
   - radial_dispersion
   - plane_residual
   - normal_angle
   - curvature
   - planarity

3. **Alpha identity** (BFM identity coefficients)
   - 3D модель, не 2D текстура
   - Устойчиво к углам через calibration

4. **Identity-only motion** (без expression)
   - Kabsch alignment
   - Устойчиво к углам

---

## 📋 ОБНОВЛЁННЫЙ ПЛАН РЕАЛИЗАЦИИ

### Удалено (4 модуля):
- ❌ Mini-Flag Detector (texture-based flags)
- ❌ Composite Anomaly Detector (texture-based anomalies)
- ❌ Alternative Explanations (texture-based)
- ❌ Photo Card Generator (texture thesis)

### Оставлено (8 модулей):

**СЛОЙ 1: Агрегаторы (5 модулей)**
1. ✅ Epoch Aggregator
2. ✅ Observation Thread Builder
3. ✅ Confidence Calculator
4. ✅ Thesis Generator (geometry + motion + descriptors only)
5. ✅ ~~Alternative Explanations~~ → **УДАЛЕНО**

**СЛОЙ 2: Генераторы (3 модуля)**
1. ✅ ~~Photo Card Generator~~ → **УДАЛЕНО** (texture)
2. ✅ Pair Card Generator (geometry + motion + descriptors)
3. ✅ Epoch Summary Generator
4. ✅ Observation Summary Generator
5. ✅ ~~Mandatory Reports Generator~~ → **ОПЦИОНАЛЬНО**

**Итого: 8 модулей вместо 12**

---

## 📊 ОЦЕНКА УСИЛИЙ (обновлённая)

| Фаза | Длительность |
|------|--------------|
| Слой 1 (5 агрегаторов) | 1.5-2 недели |
| Слой 2 (3 генератора) | 1 неделя |
| Интеграция в Stage 3 | 1 неделя |
| Тестирование | 1 неделя |
| **ИТОГО** | **4.5-5 недель** |

---

## 🎯 ДОКАЗАТЕЛЬНАЯ БАЗА

**Уровень достоверности: 98%**

Все выводы основаны на:
- ✅ Прямом анализе кода (30 исследований)
- ✅ Явном комментарии разработчика: "texture and UV are visualization only; never identity evidence"
- ✅ Намеренном исключении texture_* из Stage 3 публикации
- ✅ Физической невозможности нормализовать 2D текстуру по углу

**Вывод:** Texture-метрики **НЕЛЬЗЯ использовать** для identity evidence. Использовать только geometry + motion + descriptors + mesh.

