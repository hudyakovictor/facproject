# СТРУКТУРА НАБОРА ДАННЫХ ДЛЯ РАССЛЕДОВАНИЯ
## Фото 1999-2026, 9 ракурсов, хронологический анализ

---

## 1. КОРНЕВАЯ ДИРЕКТОРИЯ НАБОРА

```text
facproject/
├── dataset_investigation/              # Основной набор для журналиста
│   ├── README.md                        # Описание набора
│   ├── structure.json                   # Метаданные структуры
│   └── photos/                          # Фото, распределённые по годам
│       ├── 1999/
│       │   ├── 1999_08_09_01.jpg         # frontal
│       │   ├── 1999_08_09_02.jpg         # left_light
│       │   └── ...
│       ├── 2000/
│       │   ├── 2000_01_15_01.jpg         # frontal
│       │   └── ...
│       ├── ...
│       ├── 2025/
│       └── 2026/
│           ├── 2026_03_21_01.jpg         # frontal
│           ├── 2026_03_21_02.jpg         # right_profile
│           └── ...
│
├── tests/
│   ├── dataset_200_self/                # Тест на 200 фото (план)
│   │   ├── README.md
│   │   ├── self_001.jpg                 # frontal
│   │   ├── ...
│   │   └── self_200.jpg                 # right_profile
│   └── test_self_identity_200.py        # Скрипт теста (предложение)
```

---

## 2. МЕТАДАННЫЕ ДЛЯ КАЖДОГО ФОТО (`structure.json`)

```json
{
    "project_name": "deeputin-face-skin-consistency-1999-2026",
    "schema_version": "investigation-v1.0",
    "subject": "double_theory_analysis",
    "date_range": ["1999-01-01", "2026-07-21"],
    "pose_bins": [
        "left_profile", "left_deep", "left_mid", "left_light",
        "frontal", "right_light", "right_mid", "right_deep", "right_profile"
    ],
    "expected_photo_count_per_year": 20,
    "expected_total": 540,
    "analysis_stages": ["stage1_extraction", "stage2_pair_comparison", "stage3_individual_profile"],
    "metrics_for_identification": [
        "zone_luminance_median",
        "ridge_density",
        "wrinkle_stability_score",
        "skin_fingerprint_vector"
    ],
    "notes": [
        "Фото распределены по 9 ракурсам (POSE_BINS).",
        "Анализ проводится в хронологическом порядке.",
        "Для каждого фото генерируется manifest с pose_bin, date, zone_coverage.",
        "Тест на 200 фото одного человека — отдельный набор (dataset_200_self)."
    ]
}
```

---

## 3. КАК ИСПОЛЬЗОВАТЬ ЭТУ СТРУКТУРУ

### 3.1 Для журналиста-расследователя

1. **Загрузить фото в `dataset_investigation/photos/YYYY/`** с именами в формате `YYYY_MM_DD_NN.jpg`.
2. **Запустить `run_stage1.py`** для извлечения метрик.
3. **Запустить `run_stage2.py`** для сравнения пар (хронологический порядок).
4. **Запустить `run_stage3.py`** (предлагается создать) для агрегации в профиль человека.
5. **Проанализировать `tests/dataset_200_self/`** для проверки идентичности.

### 3.2 Команды запуска

```bash
# Этап 1 — извлечение (для всего набора):
python app6/run_stage1.py \
    --project-root . \
    --input dataset_investigation/photos \
    --output dataset_investigation/stage1_output \
    --device cpu

# Этап 2 — сравнение пар (хронологический порядок):
python app6/run_stage2.py \
    --project-root . \
    --stage1-root dataset_investigation/stage1_output \
    --calibration-root calibration_dataset \
    --output dataset_investigation/stage2_output \
    --overwrite

# Этап 3 — агрегация профиля (предлагается):
# (файл app6/stage3/individual_identity.py — нужно создать)
```

---

## 4. ЧТО ОТСУТСТВУЕТ В ПРОЕКТЕ (ДЛЯ ПОДГОТОВКИ)

| Компонент | Статус | Действие |
|---|---|---|
| `dataset_investigation/` | ❌ Нет | Создать структуру и загрузить фото |
| `tests/dataset_200_self/` | ❌ Нет | Создать набор из 200 фото |
| `tests/test_self_identity_200.py` | ❌ Нет | Написать тест |
| `app6/stage3/individual_identity.py` | ❌ Нет | Создать агрегатор |
| `PROJECT_PREPARATION/DATASET_STRUCTURE.md` | ✅ Есть (этот файл) | — |
| `run_stage3.py` | ⚠️ Частично (`run_stage3.py` существует, но `individual_identity.py` нет) | Дополнить `stage3/` |

---

*Этот документ описывает структуру данных для будущего расследования. Он сохраняет терминологию пользователя и указывает на конкретные пробелы, которые нужно закрыть перед анализом набора 1999-2026.*
