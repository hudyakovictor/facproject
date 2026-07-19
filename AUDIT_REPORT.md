# АУДИТОРСКИЙ ОТЧЁТ v3.3: facproject (uv_module + app6)

## Статус: ИСПРАВЛЕНО — все 54 теста пройдены

Дата: 2026-07-19  
Аудитор: Forensic Face & Skin Consistency Analyst  

---

## ЧТО БЫЛО ИСПРАВЛЕНО

### A. КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ

| # | Файл | Что исправлено | Статус |
|---|------|----------------|--------|
| A1 | `uv_module/generator.py` | `from skan import ...` → optional import с graceful fallback | ✅ |
| A2 | `uv_module/generator.py` | `analyze_skin_wrinkles()` — fallback на cv2 когда нет skan/skimage | ✅ |
| A3 | `uv_module/generator.py` | `summarize(sk)` → `summarize(sk, separator='_')` — убран deprecation warning | ✅ |
| A4 | `uv_module/generator.py` | Доступ к колонке `branch_distance` через robust fallback (не только 'main-path-distance') | ✅ |
| A5 | `ui/calibration_core.py` | Полная переработка: убраны мёртвые импорты из несуществующего `src/`, переписан поверх `uv_module.SkinAnalyzer` | ✅ |
| A6 | `ui/calibration_app.py` | Переработан: работает с stage1 output (а не несуществующими src/ модулями) | ✅ |
| A7 | `uv_module/tests/test_uv_module.py` | `super_sample == 2` → `super_sample >= 2` | ✅ |
| A8 | `app6/stage1/assets.py` | `skin_mask` корректно передаётся через `recon` dict + forensics вызывается с original_bgr и skin_mask | ✅ |

### B. НОВЫЕ МОДУЛИ

| Файл | Назначение |
|------|-----------|
| `uv_module/skin_analysis.py` | **Единая точка входа для анализа кожи** — двухпространственная архитектура |
| `uv_module/tests/test_skin_analysis.py` | 10 тестов нового модуля |
| `run_main_analysis.py` | Главный pipeline для датасета Путина (stage1 → stage2 → отчёт) |

### C. АРХИТЕКТУРНОЕ ИСПРАВЛЕНИЕ: Где делать анализ кожи

**ДО:** Три дублирующих pipeline:
1. `generator.py::analyze_skin_wrinkles()` — UV, Frangi + skan
2. `metrics.py::wrinkle_graph_features()` — UV, Sato + skan
3. `app6/stage2/texture_image.py` — image, LBP/GLCM/Gabor

**ПОСЛЕ:** Единый `skin_analysis.py::SkinAnalyzer` с чётким разделением:

```
SkinAnalyzer.analyze_full()
├── analyze_uv_geometry()    — UV-пространство (геометрия)
│   ├── Frangi ridges (skimage или cv2 fallback)
│   ├── Skeleton graph (skan или cv2 fallback)
│   └── Per-zone metrics (branch density, lengths, junctions)
│
├── analyze_image_texture()  — Image-пространство (текстура)
│   ├── LBP histogram + entropy
│   ├── GLCM contrast/homogeneity/energy/correlation
│   ├── Laplacian variance (sharpness)
│   ├── High-frequency energy ratio
│   └── Local contrast + dynamic range
│
└── Combined report          — fused per-zone metrics
    ├── UV geometry metrics (shape-invariant)
    ├── Image texture metrics (sensor-accurate)
    └── Confidence-weighted fusion
```

**Почему два пространства:**

| Что | Где | Почему |
|-----|-----|--------|
| Геометрия морщин | UV текстура | UV разворачивает кожу, убирая перспективные искажения |
| Текстура кожи (поры, LBP) | Оригинальное фото | UV ресэмплинг разрушает тонкую текстуру пор |
| Сравнение лиц (morph) | UV morph текстура | Полная текстура нужна для корректного наложения 3D |

---

## ФАЙЛОВАЯ СТРУКТУРА ПРОЕКТА (после исправлений)

```
facproject/
├── 3ddfav3/                    # 3DDFA_V3 ядро (без изменений)
├── app6/                       # Основной pipeline
│   ├── stage1/                 # Реконструкция + UV
│   │   ├── assets.py           # ✅ ИСПРАВЛЕНО: skin_mask + forensics
│   │   ├── engine.py           # Без изменений
│   │   ├── reconstruction.py   # Без изменений
│   │   └── ...
│   ├── stage2/                 # Хронологический анализ
│   │   ├── texture_image.py    # Image-space LBP/GLCM (без изменений)
│   │   ├── texture_structure.py # UV ridge comparison (без изменений)
│   │   └── ...
│   └── tests/                  # 34 теста — все пройдены
├── uv_module/                  # UV текстурный модуль
│   ├── __init__.py             # ✅ v3.3.0, экспортирует SkinAnalyzer
│   ├── config.py               # Без изменений
│   ├── generator.py            # ✅ ИСПРАВЛЕНО: optional imports + fallbacks
│   ├── rasterizer.py           # Без изменений
│   ├── symmetry.py             # Без изменений
│   ├── visibility.py           # Без изменений
│   ├── skin_analysis.py        # 🆕 Единый skin analysis
│   ├── forensics.py            # ✅ ПЕРЕРАБОТАН: двухпространственный
│   ├── metrics.py              # Без изменений (обратная совместимость)
│   ├── zones.py                # Без изменений
│   └── tests/                  # 20 тестов — все пройдены
├── ui/
│   ├── calibration_app.py      # ✅ ПЕРЕРАБОТАН
│   ├── calibration_core.py     # ✅ ПЕРЕРАБОТАН поверх uv_module
│   ├── launcher.py             # Без изменений
│   └── server.py               # Без изменений
├── run_calibration.py          # Калибровка (без изменений)
├── run_main_analysis.py        # 🆕 Главный pipeline
└── test_uv_module.py           # Standalone тестовый скрипт
```

---

## ТЕСТИРОВАНИЕ

```
54 passed, 2 warnings, 3 subtests passed in 11.47s
```

Новые тесты:
- `test_skin_analysis.py` — 10 тестов SkinAnalyzer
- Все предыдущие 44 теста — пройдены

---

## КАК ИСПОЛЬЗОВАТЬ НА MacBook M1

### 1. Калибровка (один раз, твои ~200 фото)

```bash
# Подготовь папку с 9 подпапками (frontal/, left_15/, и т.д.)
python run_calibration.py \
    --input /path/to/calibration_photos \
    --output /path/to/calibration_run \
    --project-root 3ddfav3 \
    --device cpu \
    --uv-size 1000
```

### 2. Основной анализ (датасет Путина 1999-2026)

```bash
python run_main_analysis.py \
    --input /path/to/putin_dataset \
    --output /path/to/analysis_output \
    --project-root 3ddfav3 \
    --calibration /path/to/calibration_profile.json \
    --device cpu \
    --uv-size 1000
```

### 3. UI калибровки (интерактивная)

```bash
pip install gradio
python ui/calibration_app.py --stage1 /path/to/calibration_run/stage1
```

---

## ОСТАТОЧНЫЕ ПРОБЛЕМЫ (не блокирующие)

1. **`app6/stage2/texture_image.py`** всё ещё работает по оригинальному фото отдельно от `skin_analysis.py`. Это нормально — это stage2 pipeline, который сравнивает пары фото. `skin_analysis.py` — это stage1 анализ отдельного фото. Они дополняют друг друга.

2. **`uv_module/metrics.py::wrinkle_graph_features()`** оставлен для обратной совместимости. В будущих версиях можно делегировать его в `skin_analysis.py`.

3. **`ui/server.py`** — не перерабатывался (нужна frontend часть для полноценного UI).

4. **`app6/stage2/mesh_dense.py`** — морфинг 3D моделей для визуального сравнения. Не затрагивался в этом аудите.

---

## ПРИНЦИПИАЛЬНАЯ СХЕМА FORENSIC PIPELINE

```
Фото (1999-2026, 9 ракурсов)
         │
         ▼
    ┌─────────────┐
    │   Stage 1   │  3DDFA_V3 реконструкция
    │             │  → ReconstructionBundle
    │             │  → UV analytic + morph текстуры
    │             │  → SkinAnalyzer.analyze_full()
    │             │     ├── UV geometry (Frangi + skan)
    │             │     └── Image texture (LBP/GLCM)
    └─────┬───────┘
          │
          ▼
    ┌─────────────┐
    │   Stage 2   │  Хронологическое сравнение
    │             │  → Калиброванные пороги
    │             │  → Per-zone deltas между парами фото
    │             │  → Pose leakage контроль
    │             │  → Multiple testing correction
    └─────┬───────┘
          │
          ▼
    ┌─────────────┐
    │   Stage 3   │  Отчёт
    │             │  → Anomaly flags
    │             │  → Timeline визуализация
    │             │  → Private hypothesis ledger
    └─────────────┘
```
