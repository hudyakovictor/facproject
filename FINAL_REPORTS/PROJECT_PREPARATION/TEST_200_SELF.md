# ПЛАН ТЕСТА НА 200 ФОТО ОДНОГО ЧЕЛОВЕКА
## Для проверки: «алгоритм видит везде одного и того же человека»

---

## 1. ЦЕЛЬ ТЕСТА

> «Проверить, как алгоритм по данным, полученным из моих фото, будет видеть, что везде один и тот же человек.»

**Что это означает технически:**
- У нас есть 200 фото **одного человека** (например, журналиста или субъекта расследования).
- Фото сделаны в разное время, с разными ракурсами (`pose_bin`), при разных условиях освещения.
- Алгоритм должен построить для каждого фото метрики (`feature_registry.py`) и показать, что они **стабильны** и **не различаются** больше, чем ожидаемый шум (`calibration_dataset/` предоставляет данные для оценки шума).

---

## 2. СТРУКТУРА НАБОРА ДАННЫХ

```text
tests/dataset_200_self/
    self_001.jpg     (frontal, 1999-08-09)     # или любая дата
    self_002.jpg     (frontal, 1999-08-09)
    ...
    self_050.jpg     (frontal, 2026-03-21)
    self_051.jpg     (left_profile, 2005-01-15)
    ...
    self_200.jpg     (right_profile, 2026-03-21)
```

### 2.1 Распределение по ракурсам (пример)

```python
# Примерное распределение для 200 фото:
DISTRIBUTION = {
    'frontal': 60,        # ~30%
    'left_light': 25,     # ~12.5%
    'right_light': 25,    # ~12.5%
    'left_mid': 20,       # ~10%
    'right_mid': 20,      # ~10%
    'left_deep': 15,      # ~7.5%
    'right_deep': 15,     # ~7.5%
    'left_profile': 10,   # ~5%
    'right_profile': 10,  # ~5%
}
```

---

## 3. ЧТО НУЖНО ПРОВЕРИТЬ

### 3.1 Стабильность метрик по зонам (`feature_registry.py`)

Для каждой зоны (`A20`) нужно проверить:

```python
# Пример метрик для проверки:
METRICS_TO_CHECK = [
    'zone_luminance_median',   # Должна быть стабильна в пределах шума
    'zone_luminance_mad',      # Должна быть стабильна
    'ridge_density',           # Должна быть стабильна для морщинных зон
    'lbp_entropy',             # Текстура
    'glcm_contrast',           # Текстура
    'gabor_energy',            # Морщины
    'spectral_entropy',        # Спектр
    'structure_coherence',     # Структура
    'log_blob_density',        # Микрорельеф
    'local_mad',               # Локальное отклонение
]
```

### 3.2 Как оценить стабильность

```python
# Предлагаемый код для теста:
import numpy as np

def evaluate_stability(feature_values: list[float]) -> dict:
    values = np.array(feature_values, dtype=np.float32)
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))  # Median Absolute Deviation
    p95 = float(np.percentile(values, 95))
    min_val = float(np.min(values))
    max_val = float(np.max(values))
    
    return {
        'median': median,
        'mad': mad,
        'p95': p95,
        'range': max_val - min_val,
        'stability_score': 1.0 - min(1.0, mad / (median + 1e-6)),  # Чем ближе к 1, тем стабильнее
    }
```

---

## 4. ЧТО ДОЛЖНО БЫТЬ В РЕЗУЛЬТАТЕ ТЕСТА

### 4.1 Ожидаемый результат для «одного человека»

```json
{
    "test_name": "self_identity_200",
    "subject": "self",
    "photo_count": 200,
    "date_range": ["1999-08-09", "2026-03-21"],
    "pose_bins_covered": ["frontal", "left_profile", ...],
    "stability_results": {
        "zone_F00_luminance_median": {
            "median": 0.42,
            "mad": 0.03,
            "stability_score": 0.93
        },
        "zone_F00_ridge_density": {
            "median": 1.25,
            "mad": 0.12,
            "stability_score": 0.90
        }
    },
    "conclusion": "Метрики стабильны в пределах ожидаемого шума. Алгоритм подтверждает: один и тот же человек."
}
```

### 4.2 Если метрики НЕ стабильны

Это может означать:
1. **Ошибка в коде метрик** (`feature_registry.py` или `pipeline.py`).
2. **Неправильная нормализация** — не учтены различия в освещении или ракурсе.
3. **На самом деле фото принадлежат разным людям** — это было бы важным открытием для расследования.

---

## 5. ПРЕДЛАГАЕМЫЙ ФАЙЛ ТЕСТА

```python
# Файл: tests/test_self_identity_200.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app6.stage1.config import Stage1Config
from app6.stage1.engine import Stage1Engine

def test_self_identity_200():
    """Запустить анализ 200 фото одного человека."""
    input_dir = Path('tests/dataset_200_self')
    output_dir = Path('tests/output_self_200')
    
    cfg = Stage1Config(
        project_root=Path('.').resolve(),
        input_dir=input_dir,
        output_dir=output_dir,
        device='cpu'
    )
    
    # Запустить stage1 для всех фото
    Stage1Engine(cfg).run()
    
    # Затем проанализировать стабильность метрик
    # (предлагается добавить функцию в app6/stage3/individual_identity.py)
    
    assert output_dir.exists(), "Тест не прошёл: не найден выходной каталог"
```

---

## 6. ЧТО НУЖНО ДЛЯ ЗАПУСКА ТЕСТА (ЧЕГО НЕТ В ПРОЕКТЕ)

| Компонент | Статус | Что нужно сделать |
|---|---|---|
| `tests/dataset_200_self/` | ❌ Нет | Создать набор из 200 фото |
| `tests/test_self_identity_200.py` | ❌ Нет | Написать тестовый скрипт |
| `app6/stage3/individual_identity.py` | ❌ Нет | Добавить агрегатор метрик |
| `tests/output_self_200/` | ❌ Нет | Будет создан автоматически |

---

*Этот документ — план теста, который пользователь упомянул как невыполненный. Он сохраняет оригинальную формулировку («алгоритм видит везде одного человека») и предлагает конкретную реализацию.*
