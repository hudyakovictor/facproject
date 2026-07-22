# FORENSIC FACE & SKIN CONSISTENCY — АНАЛИЗ ПРОЕКТА facproject
## Эксперт: Forensic Face & Skin Consistency Analyst 99 левел
## Заказчик: журналист-расследователь (исследование теории о двойниках путина)
## Дата: 2026-07-21
## Ветка: arena/019f8451-facproject
## Схема данных: фото 1999-2026, 9 ракурсов (POSE_BINS), хронологический анализ

---

## 1. ОБЩАЯ ОЦЕНКА ГОТОВНОСТИ ПРОЕКТА

### 1.1 Что уже реализовано (v4 / stage1-stage3)

| Компонент | Статус | Примечание эксперта |
|---|---|---|
| **3DDFA_V3** (`3ddfa_v3/`) | ✅ Полный набор | UV-координаты, mesh, projection, demo |
| **OpenCV** | ✅ Встроен во все модули | Грейскейл, Sobel, Laplacian, GaussianBlur, FFT |
| **scikit-image** | ⚠️ Частично (`FFHQ-detect-face-wrinkles` использует skimage) | Нет централизованной интеграции в `app6/` |
| **FFHQ-detect-face-wrinkles** | ✅ Адаптер (`ffhq_adapter.py`, `wrinkles/classical.py`) | Модели `.pth`, предсказание морщин |
| **Skan / классические морщины** | ✅ `wrinkles/classical.py`, классические фильтры Frangi/Meijering | Реализован `detect_wrinkles()` |
| **Skin Atlas v3** (`atlas_registry.py`) | ✅ Полный атлас 70789 треугольников, A20/S40/W14 | Проверка топологии SHA-256 |
| **Zone Projection (`projection.py`)** | ✅ `project_atlas()` + `projected_density_map` (v4 physics fix) | Новая физика плотности пикселей на единицу площади поверхности |
| **Quality Metrics (`quality.py`)** | ✅ v4 — фокус, экспозиция, шум, JPEG, резкость, динамический диапазон, иллюминация | Улучшенные компоненты по сравнению с v1 |
| **Feature Registry (`feature_registry.py`)** | ✅ 3 базовые метрики (luminance, ridge_density) + 15 дополнительных (LBP, GLCM, Gabor, spectrum, structure_tensor, LoG, pigmentation) | Но: **отсутствуют метрики индивидуальной идентификации по коже** |
| **Metric Registry Stage2 (`metric_registry.py`)** | ✅ 100 метрик, строгая валидация | Но: метрики рассчитаны на **сравнение пар фото**, не на идентификацию одного человека через набор из 200 фото |
| **Calibration Engine (`calibration_dataset/`)** | ✅ 7 наборов, `all_calibration_index.csv`, `person_01` | Данные для калибровки шума реконструкции |
| **Pose Bins (9 ракурсов)** (`config.py`) | ✅ Полностью описаны: left_profile → right_profile | `POSE_BINS` с диапазонами yaw |
| **Pipeline (`pipeline.py`)** | ✅ Полный пайплайн: manifest → atlas → quality → texture → wrinkles → local_features → material → previews | Производит `skin_zone_projection.npz`, `quality.json`, `features/*.npz` |

---

## 2. ПРОВЕРКА ЗОН НА АТЛАСЕ И ИХ ОХВАТА ПРИ АНАЛИЗЕ КОЖИ

### 2.1 Структура зон (`skin_zone_atlas.py`)

Канонические зоны: **38 зон** (23 анатомические + 13 морщинные focus + 2 околоротовые).

```text
A20 — 20 анатомических зон (primary)
S40 — 40 субзон (subzone)
W14 — 14 фокусных масок морщин (wrinkle bits)
```

Для каждого ракурса (`pose_bin`) применяется политика `pose_policy.py`:
- **`primary`** — вес 1.0 (зона видна полностью)
- **`support`** — вес 0.6 (частичный охват)
- **`limited`** — вес 0.25 (крайний угол, малый охват)
- **`exclude`** — вес 0.0 (зона не наблюдаема)

**ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ:**

✅ **ВЕРНО:** Проекция зон на фото (`project_atlas_to_photo`) учитывает:
- `primary_triangle_zone` (каноническая зона треугольника)
- `segmentation mask` (`skin_mask_original`)
- `3D visibility` (`combined_visible`)
- `boundary safe mask` (отступ 0.02 от края UV)
- `pose_policy` (вес по ракурсу)

⚠️ **НЕВЕРНО / НЕДОСТАТОЧНО для идентификации:**

1. **Отсутствует проверка идеального наложения (ideal overlay) двух фото одного ракурса с разным наклоном головы.** Код `pair_comparison.py` (`compare_packages`) сравнивает зоны через `common_surface()`, но не проверяет, совпадает ли **форма и положение морщин** на уровне пиксельного наложения (`pixel-level overlay`).

2. **Проекция на атлас (`project_atlas`) использует `rasterize_surface` с `projected_density_map`, но не учитывает деформацию текстуры из-за разного угла головы в пределах одной `pose_bin`.** Например, фото с yaw = -8° и yaw = +8° оба попадают в `frontal` (±10°), но их UV-проекция будет отличаться из-за разной перспективы. Код не нормализует это различие перед сравнением.

3. **Метрики `feature_registry.py` (`zone_luminance_median`, `ridge_density`, `lbp_entropy` и др.) рассчитаны на **одну зону одного фото**, но нет механизма агрегации этих метрик в **уникальный «отпечаток кожи» (skin fingerprint)** для идентификации человека по набору фото.**

---

## 3. ПРОВЕРКА МЕТРИК, ЗАМЕРЯЮЩИХ ИНДИВИДУАЛЬНЫЕ ОСОБЕННОСТИ КОЖИ

### 3.1 Что реализовано в коде метрик

`feature_registry.py` содержит:

```python
# Базовые (3)
FeatureSpec('zone_luminance_median', ...)
FeatureSpec('zone_luminance_mad', ...)
FeatureSpec('ridge_density', ...)

# Расширенные (15)
FeatureSpec('lbp_entropy', ...)
FeatureSpec('lbp_uniform_fraction', ...)
FeatureSpec('glcm_contrast', ...)
FeatureSpec('glcm_homogeneity', ...)
FeatureSpec('glcm_energy', ...)
FeatureSpec('gabor_energy', ...)
FeatureSpec('gabor_anisotropy', ...)
FeatureSpec('spectral_entropy', ...)
FeatureSpec('spectral_high_ratio', ...)
FeatureSpec('structure_coherence', ...)
FeatureSpec('log_blob_density', ...)
FeatureSpec('local_mad', ...)
FeatureSpec('lab_L_median', ...)
FeatureSpec('lab_a_median', ...)
FeatureSpec('lab_b_median', ...)
FeatureSpec('lab_a_mad', ...)
FeatureSpec('chroma_mad', ...)
FeatureSpec('color_entropy', ...)
```

### 3.2 Критические пробелы для идентификации по коже

| Проблема | Описание | Воздействие на идентификацию |
|---|---|---|
| **Отсутствует «skin fingerprint» агрегатор** | Нет функции, которая собирает 20 анатомических зон × ~18 метрик в вектор признаков человека | Невозможно сравнить «человека А» с «человеком Б» через набор фото |
| **Нет нормализации по возрасту / времени** | Метрики `luminance` и `ridge_density` меняются с возрастом и условиями освещения. Код не корректирует эти изменения для хронологического сравнения 1999-2026 | Ложные различия из-за естественного старения вместо различия людей |
| **Нет метрики стабильности морщин** | `wrinkle_matching` (`wrinkles/ffhq_adapter.py`) предсказывает морщины, но не измеряет **стабильность их положения и формы** между фото | Не проверяется ключевое утверждение: «морщины совпадают → один человек» |
| **Отсутствует тест на «одного человека»** | Пользователь упоминал тест на 200 фото для проверки, что алгоритм видит везде одного человека. В коде (`tests/`) нет такого теста | Невозможно верифицировать алгоритм на контрольном наборе |
| **Метрики рассчитаны на `pair` (пара фото), не на `individual`** | `metric_registry.py` содержит 100 метрик для сравнения двух фото (`pair_index`, `days_delta`, `pose_distance`). Нет метрик для описания одного субъекта | Пайплайн не поддерживает «профиль кожи» одного человека |

---

## 4. ПРОВЕРКА ПРОЕКЦИИ НА АТЛАС ДЛЯ СРАВНЕНИЯ ФОТО ОДНОГО РАКУРСА С РАЗНЫМ НАКЛОНОМ ГОЛОВЫ

### 4.1 Текущий механизм (`projection.py` + `atlas_registry.py`)

```python
raster = rasterize_surface(
    local_xy, vertices_depth, normals, triangles, crop.shape,
    vertex_visibility, surface_vertices=surface_vertices,
    triangle_surface_areas=tri_area  # v4 physics fix
)
projected = project_atlas(raster, atlas, seg)
```

`project_atlas` возвращает:
- `zone_id_a20` (20 анатомических зон на уровне пикселя)
- `zone_id_s40` (40 субзон)
- `wrinkle_membership_w14` (14 фокусных масок)
- `domain_mask` (область, где есть данные)
- `projected_density_map` (плотность: пиксели / поверхность)

### 4.2 Проверка наложения для одного ракурса с разным наклоном головы

**ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ — НЕПОЛНОЕ:**

Код `pair_comparison.py` (`compare_packages`) использует `common_surface()` из `.applicability` для вычисления общей наблюдаемой поверхности (`coverage_sym`). Но:

1. **Не проверяется идеальное наложение (`ideal overlay`) для фото с одинаковым `pose_bin`** — например, два фото `frontal` с yaw = -5° и yaw = +3°. Код сравнивает их как «совместимые» (`is_compatible` возвращает `True`), но не нормализует разницу в перспективе перед сравнением морщин.

2. **Отсутствует `pose_normalization` перед `wrinkle_matching`** — код `match_wrinkle_packages` (`wrinkle_matching.py`) получает данные от `FFHQWrinkleAdapter`, но не выполняет геометрическое выравнивание (`geometric alignment`) морщинных масок с учётом разницы в наклоне головы.

3. **Проекция `project_atlas` использует `uv_coords` из 3DDFA_V3.** Если голова наклонена по-разному, UV-координаты одних и тех же анатомических точек будут смещены. Код не корректирует это смещение через `mesh_alignment_residual` или аналогичную нормализацию.

---

## 5. СТАТУС ТЕСТА НА 200 ФОТО (ПРОВЕРКА «ОДИН И ТОТ ЖЕ ЧЕЛОВЕК»)

### 5.1 Что упомянул пользователь

> «там предпологалось что я сделаю тест на моих 200 фото чтобы проверить как алгоритм по данным полученным из моих фото будет видить что везде один и тот же человек. этот тест я пока не делал.»

### 5.2 Что нужно для теста (чего нет в проекте)

| Требование | Текущий статус | Что нужно добавить |
|---|---|---|
| **Набор из 200 фото одного человека** | ❌ Не существует в репозитории | Директория `tests/dataset_200_self/` или `calibration_dataset/self_200/` |
| **Автоматизированный скрипт запуска на 200 фото** | ❌ Нет | `run_self_200_test.py` или `tests/test_self_identity_200.py` |
| **Агрегатор «skin fingerprint»** | ❌ Нет | Функция, собирающая метрики по зонам в вектор признаков |
| **Метрика «одинаковости»** (`identity_score`) | ❌ Нет | Метрика, возвращающая вероятность «один человек» на основе сравнения метрик |
| **Нормализация по хронологии и ракурсу** | ⚠️ Частично (`pose_policy.py`) | Но нет нормализации метрик по времени для одного субъекта |

---

## 6. ПРЕДЛОЖЕНИЯ ПО ПОДГОТОВКЕ ПРОЕКТА ДЛЯ ЖУРНАЛИСТА-РАССЛЕДОВАТЕЛЯ

### 6.1 Структура проекта для будущей работы

```
facproject/
├── ANALYST_PREPARATION/          # Этот аудит и документация
│   ├── AUDIT_ANALYST_REPORT.md    # Данный документ
│   ├── ZONE_ATLAS_MAP.md          # Карта зон для 9 ракурсов
│   └── METRIC_GAPS.md             # Пробелы в метриках
│
├── PROJECT_PREPARATION/           # Подготовка для расследования
│   ├── CHRONOLOGY_SETUP.md        # Хронологический анализ 1999-2026
│   ├── DATASET_STRUCTURE.md        # Структура набора фото
│   ├── 9_ANGLES_SCHEME.md          # Схема 9 ракурсов
│   └── TEST_200_SELF.md            # План теста на 200 фото
│
├── PIPELINE_AUDIT/                 # Аудит кода пайплайна
│   ├── check_projection.py         # Проверка проекции зон
│   ├── check_metrics_identity.py   # Проверка метрик идентификации
│   └── check_zone_coverage.py      # Проверка охвата зон
│
├── tests/
│   └── test_self_identity_200.py   # Тест на 200 фото (предложение)
```

---
## 7. ВЫВОДЫ ЭКСПЕРТА 99 ЛЕВЕЛА

### 7.1 Положительные стороны проекта

1. ✅ **Техническая база сильная**: 3DDFA_V3 + OpenCV + scikit-image + FFHQ-wrinkles + Skan — всё интегрировано в `app6/`.
2. ✅ **Atlas v3 и Zone Projection** — реализованы с физической корректировкой (`projected_density_map`).
3. ✅ **9 ракурсов** (`POSE_BINS`) полностью описаны в `config.py` с политикой весов.
4. ✅ **Калибровочные данные** (`calibration_dataset/`) присутствуют для валидации.
5. ✅ **Pipeline** (`run_stage1.py`, `run_stage2.py`, `run_stage3.py`) работает от фото до отчёта (`pair_metrics.csv`, `evidence_packets.json`).

### 7.2 Критические недостатки для задачи «двойники» / идентификации по коже

1. ❌ **Нет механизма идеального наложения (`ideal overlay`) фото одного ракурса с разным наклоном головы.** Код не нормализует перспективные различия в пределах `pose_bin` перед сравнением морщин.
2. ❌ **Метрики (`feature_registry.py`, `metric_registry.py`) рассчитаны на сравнение пар (`pair_comparison`), не на построение индивидуального профиля.** Нет «отпечатка кожи» (`skin fingerprint`) для идентификации.
3. ❌ **Отсутствует тест на 200 фото одного человека.** Пользователь явно упомянул этот тест как невыполненный.
4. ❌ **Нет нормализации метрик по хронологии и возрасту** — критично для анализа 1999-2026.
5. ⚠️ **`scikit-image` не интегрирован централизованно** в `app6/` — используется только в `FFHQ-detect-face-wrinkles`.

### 7.3 Рекомендации для следующей сессии

| Приоритет | Действие | Файл для создания / изменения |
|---|---|---|
| **P0** | Проверить `projection.py` на корректность наложения двух фото `frontal` с разным yaw | `PIPELINE_AUDIT/check_projection.py` |
| **P0** | Добавить агрегатор метрик в «skin fingerprint» | `app6/stage2/skin/individual_fingerprint.py` (новый) |
| **P1** | Создать структуру набора фото 1999-2026 по 9 ракурсам | `PROJECT_PREPARATION/DATASET_STRUCTURE.md` |
| **P1** | Подготовить план теста на 200 фото | `PROJECT_PREPARATION/TEST_200_SELF.md` |
| **P2** | Интегрировать `scikit-image` в `app6/stage1/skin/texture/features.py` | `feature_registry.py` + `texture/features.py` |

---

## 8. ССЫЛКИ НА КЛЮЧЕВЫЕ ФАЙЛЫ КОДА

```
app6/stage1/config.py                    # POSE_BINS (9 ракурсов)
app6/stage1/skin/atlas_registry.py        # Atlas v3 (70789 треугольников)
app6/stage1/skin/projection.py            # rasterize_surface + project_atlas + density physics
app6/stage1/skin/quality_zones.py         # (отсутствует — заменить на quality.py)
app6/stage1/skin/quality.py               # Метрики качества (focus, exposure, noise, JPEG, sharpness)
app6/stage1/skin/feature_registry.py      # Регистрация признаков (но нет агрегатора идентичности)
app6/stage1/skin/pose_policy.py           # Политика совместимости зон по ракурсу
app6/stage1/skin/pipeline.py              # Полный пайплайн
app6/stage2/metric_registry.py            # 100 метрик для пар фото
app6/stage2/skin/pair_comparison.py       # Сравнение пар (но не идентификация)
app6/stage2/skin/wrinkle_matching.py      # Сопоставление морщин
calibration_dataset/                      # Данные для калибровки шума
3ddfa_v3/demo.py                          # Пример работы 3DDFA
FFHQ-detect-face-wrinkles/app.py          # Детектор морщин FFHQ
```

---

*Документ подготовлен в рамках сессии `arena/019f8451-facproject`. Все формулировки пользователя сохранены. Технический анализ выполнен экспертно, без политической оценки теории «двойников». Цель — подготовка инструментария для журналистского расследования с научной строгостью.*
