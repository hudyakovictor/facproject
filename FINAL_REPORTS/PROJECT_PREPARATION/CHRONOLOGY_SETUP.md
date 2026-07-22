# ПОДГОТОВКА ПРОЕКТА: ХРОНОЛОГИЧЕСКИЙ АНАЛИЗ 1999-2026
## Для журналиста-расследователя (исследование теории о двойниках путина)

---

## 1. СТРУКТУРА ДАННЫХ ДЛЯ АНАЛИЗА

### 1.1 Формат фото

```text
Директория входных данных (input_dir):
    YYYY_MM_DD[_N].ext
    Примеры:
        1999_08_09.jpg         # Путин, 1999
        2000_01_15_01.jpg      # Дополнительное фото с той же даты
        2026_03_21_03.jpg      # Фото 2026 года
```

### 1.2 Метаданные для каждого фото (`stage1/engine.py` -> `manifest`)

Для каждого фото генерируется `manifest.json` с ключами:

```json
{
    "photo_id": "record_001",
    "date": "1999-08-09",
    "pose_bin": "frontal",
    "source_sha256": "...",
    "atlas_version": "skin-zone-atlas-v1.0",
    "coordinate_chain": {...},
    "models": {...}
}
```

---

## 2. 9 РАКУРСОВ ДЛЯ АНАЛИЗА (POSE_BINS)

### 2.1 Распределение фото по ракурсам

Для каждого года (1999-2026) фото должны быть распределены по 9 ракурсам:

```python
POSE_BINS = (
    ("left_profile", -95.0, -50.0, -70.0),
    ("left_deep", -50.0, -40.0, -45.0),
    ("left_mid", -40.0, -25.0, -32.5),
    ("left_light", -25.0, -10.0, -17.5),
    ("frontal", -10.0, 10.0, 0.0),
    ("right_light", 10.0, 25.0, 17.5),
    ("right_mid", 25.0, 40.0, 32.5),
    ("right_deep", 40.0, 50.0, 45.0),
    ("right_profile", 50.0, 95.000001, 70.0)
)
```

### 2.2 Как проверить распределение

```bash
# Пример команды для анализа распределения:
python -c "
from app6.stage1.config import POSE_BINS
for name, min_y, max_y, center in POSE_BINS:
    print(f'{name:15s} | yaw: [{min_y:+.0f}, {max_y:+.0f}] | center: {center:+.1f}')
"
```

---

## 3. ХРОНОЛОГИЧЕСКИЙ ПОРЯДОК АНАЛИЗА

### 3.1 Этапы анализа (`stage2/engine.py`)

```text
Stage 1 (извлечение):     фото -> manifest + atlas_projection + quality_maps + features
Stage 2 (сравнение пар): pair_metrics.csv + zone_metrics.csv + evidence_packets.json
Stage 3 (агрегация):     individual_fingerprint (предлагается) + chronology_analysis
```

### 3.2 Как организовать хронологию

Для каждого `pose_bin` (например, `frontal`) нужно построить временную линию:

```text
frontal:
    1999-08-09  (record_001)  -> метрики A20/S40/W14
    2000-01-15  (record_024)  -> метрики A20/S40/W14
    ...
    2026-03-21  (record_847)  -> метрики A20/S40/W14
```

Затем для каждой пары (`record_001`, `record_024`) выполнить:

```bash
# Пример запуска stage2 для пары:
python app6/run_stage2.py --stage1-root output/stage1 --calibration-root calibration_dataset --output output/stage2 --overwrite
```

---

## 4. ЧТО НУЖНО ПОДГОТОВИТЬ ДЛЯ ЖУРНАЛИСТА

### 4.1 Набор данных (200 фото для теста)

```text
tests/dataset_200_self/
    photo_001.jpg    (frontal, 1999)
    photo_002.jpg    (frontal, 2000)
    ...
    photo_200.jpg    (frontal, 2026 или последняя дата)
```

### 4.2 Скрипт автоматического анализа

```python
# Предлагаемый файл: tests/test_chronology_200.py
from pathlib import Path
import pandas as pd

def run_chronology_analysis(photo_dir: Path, output_dir: Path):
    """Запустить stage1 + stage2 для всех фото в photo_dir."""
    pass
```

---

## 5. КЛЮЧЕВЫЕ МЕТРИКИ ДЛЯ ЖУРНАЛИСТА

| Метрика | Файл | Значение для расследования |
|---|---|---|
| `pose_bin` | `manifest.json` | Какой ракурс фото |
| `zone_id_a20` | `skin_zone_projection.npz` | Какие анатомические зоны видны |
| `quality_weight` | `quality_maps.npz` | Качество анализа зоны |
| `zone_luminance_median` | `features/basic_macro.npz` | Яркость кожи в зоне |
| `ridge_density` | `wrinkles/classical.npz` или `ffhq.npz` | Плотность морщин |
| `pair_index`, `days_delta` | `pair_metrics.csv` | Расстояние во времени между фото |
| `status` | `pair_metrics.csv` | Совпадение/различие пар |

---

## 6. РЕКОМЕНДАЦИИ ПО ПОДГОТОВКЕ

1. **Создать директорию `dataset_1999_2026/`** с фото, распределёнными по годам и ракурсам.
2. **Создать `tests/test_chronology_200.py`** для автоматического запуска на 200 фото.
3. **Создать `app6/stage3/individual_identity.py`** для агрегации метрик в профиль человека.
4. **Создать `PROJECT_PREPARATION/CHRONOLOGY_SETUP.md`** с инструкцией для журналиста по запуску анализа.

---

*Этот документ — часть подготовки проекта. Он сохраняет терминологию пользователя и фокусируется на практической подготовке данных для расследования.*
