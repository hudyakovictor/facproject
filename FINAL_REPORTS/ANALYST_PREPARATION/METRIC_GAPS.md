# ПРОБЕЛЫ В МЕТРИКАХ ДЛЯ ИДЕНТИФИКАЦИИ ПО КОЖЕ
## Анализ `feature_registry.py` и `metric_registry.py`

---

## 1. ЧТО РЕАЛИЗОВАНО

### 1.1 Feature Registry (`app6/stage1/skin/feature_registry.py`)

```python
# Базовые метрики (3):
- zone_luminance_median (A20, S40) — медианная яркость зоны
- zone_luminance_mad (A20, S40) — медианное абсолютное отклонение яркости
- ridge_density (W14) — плотность морщинных хребтов

# Расширенные метрики (15 семей):
- LBP (lbp_entropy, lbp_uniform_fraction)
- GLCM (glcm_contrast, glcm_homogeneity, glcm_energy)
- Gabor (gabor_energy, gabor_anisotropy)
- Spectrum (spectral_entropy, spectral_high_ratio)
- Structure (structure_coherence)
- Microrelief (log_blob_density, local_mad)
- Pigmentation (lab_L_median, lab_a_median, lab_b_median, lab_a_mad, chroma_mad, color_entropy)
```

### 1.2 Metric Registry (`app6/stage2/metric_registry.py`)

```python
# 100 метрик для сравнения ПАР фото:
- pair (metadata пары)
- quality (оценка качества)
- landmark (LDL-106, LDM-134 — геометрия лица)
- descriptor (дескрипторы)
- mesh (3D mesh)
- texture (текстура кожи и морщин)
```

---

## 2. ЧЕГО НЕТ (КРИТИЧЕСКИЕ ПРОБЕЛЫ)

### 2.1 Нет «отпечатка кожи» (`skin fingerprint` или `individual profile`)

**Проблема:** Код рассчитан на сравнение **двух фото** (`pair`), но не на описание **одного человека** через набор фото.

**Что нужно:**

```python
# Пример: функция для построения профиля человека из 200 фото
from app6.stage1.skin.feature_registry import REGISTRY

def build_individual_fingerprint(photo_features_list: list[dict]) -> np.ndarray:
    """
    photo_features_list: список словарей с ключами:
        - photo_id
        - pose_bin
        - date
        - zone_features: dict[str, float]  # метрики по зонам A20/S40
    
    Возвращает: вектор признаков (feature_vector) для идентификации.
    """
    # 1. Нормализовать по pose_bin (применить pose_policy вес)
    # 2. Нормализовать по дате (корректировать возрастные изменения)
    # 3. Агрегировать метрики по зонам (медиана, MAD, IQR)
    # 4. Вернуть уникальный вектор признаков
    pass
```

### 2.2 Нет метрики стабильности морщин (`wrinkle_stability_score`)

**Проблема:** `wrinkles/ffhq_adapter.py` и `wrinkles/classical.py` предсказывают морщины, но не измеряют, насколько стабильно их положение и форма между фото.

**Что нужно:**

```python
def measure_wrinkle_stability(wrinkle_mask_a, wrinkle_mask_b) -> float:
    """
    Измерить, насколько совпадают формы и позиции морщин
    между двумя фото (после геометрической нормализации).
    
    Возвращает: значение от 0 (разные люди) до 1 (идеальное совпадение).
    """
    pass
```

### 2.3 Нет нормализации по хронологии (`chronology_normalization`)

**Проблема:** Анализ 1999-2026 требует учёта естественного старения. Код `alpha_chronology.py` (`stage2/alpha_chronology.py`) работает с временными интервалами, но не корректирует метрики кожи под возрастные изменения.

**Что нужно:**

```python
# В stage2/chronology.py или новом файле:
def normalize_skin_metrics_for_age(feature_vector: np.ndarray, age_years: float) -> np.ndarray:
    """Корректировать метрики яркости, плотности морщин и пигментации под возраст."""
    pass
```

### 2.4 Нет метрики «одинаковости» (`identity_score` или `same_person_probability`)

**Проблема:** Пользователь упомянул тест на 200 фото для проверки, что алгоритм видит везде одного человека. Но в коде нет метрики, которая бы возвращала вероятность «один человек» на основе метрик.

**Что нужно:**

```python
# Новый файл: app6/stage3/individual_identity.py
def compute_identity_score(individual_profile: np.ndarray, comparison_profile: np.ndarray) -> dict:
    """
    Вычислить вероятность, что два профиля принадлежат одному человеку.
    Учитывает:
    - Сходство метрик кожи (luminance, texture, wrinkles)
    - Совместимость по ракурсу (pose_policy)
    - Хронологическую дистанцию
    
    Возвращает словарь с ключами:
        - 'same_person_probability': float (0..1)
        - 'confidence_interval': tuple[float, float]
        - 'primary_evidence_zones': list[str]  # зоны с наибольшим вкладом
    """
    pass
```

---

## 3. КАК ЭТО ВЛИЯЕТ НА ЗАДАЧУ «ДВОЙНИКИ»

Для журналиста-расследователя, исследующего теорию о двойниках, критично иметь:

1. **Объективную метрику «одинаковости»** — не «похоже», а «вероятность 0.95, что это один человек».
2. **Устойчивость к разным углам головы** — фото с yaw = -8° и yaw = +5° должны давать одинаковый профиль.
3. **Учёт времени** — метрики 1999 года должны быть сопоставимы с метриками 2026 года через коррекцию возраста.
4. **Прозрачность доказательств** — для каждой зоны (`A20`/`S40`) нужно видеть вклад в общий вывод.

**Текущий код `app6/` не предоставляет ничего из этого.**

---

## 4. РЕКОМЕНДАЦИИ ПО ЗАКРЫТИЮ ПРОБЕЛОВ

| Пробел | Приоритет | Файлы для изменения / создания |
|---|---|---|
| Агрегатор «skin fingerprint» | P0 | `app6/stage2/skin/individual_fingerprint.py` (новый) |
| Метрика стабильности морщин | P0 | `app6/stage2/skin/wrinkle_matching.py` (расширить) |
| Нормализация по хронологии/возрасту | P1 | `app6/stage2/chronology.py` или новый `skin_age_normalization.py` |
| Метрика `identity_score` | P1 | `app6/stage3/individual_identity.py` (новый) |
| Тест на 200 фото одного человека | P1 | `tests/test_self_identity_200.py` (новый) |
| Интеграция `scikit-image` | P2 | `app6/stage1/skin/texture/features.py` (расширить) |

---

*Документ подготовлен в рамках подготовки проекта `facproject` для журналистского расследования. Сохранена терминология пользователя. Анализ выполнен экспертно.*
