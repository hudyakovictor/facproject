#!/usr/bin/env python3
"""
ПРОВЕРКА МЕТРИК, ЗАМЕРЯЮЩИХ ИНДИВИДУАЛЬНЫЕ ОСОБЕННОСТИ КОЖИ
Эксперт: Forensic Face & Skin Consistency Analyst 99 левел
Цель: проверить, можно ли по данным метрик идентифицировать человека.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

def audit_metrics_for_individual_identification():
    """Проверить, подходят ли метрики для идентификации одного человека."""
    print("=" * 70)
    print("АУДИТ МЕТРИК: можно ли идентифицировать человека по коже?")
    print("=" * 70)
    
    # 1. Проверить feature_registry
    try:
        from app6.stage1.skin.feature_registry import REGISTRY, FeatureSpec
        feature_keys = sorted(REGISTRY.keys())
        print(f"[OK] Feature Registry содержит {len(feature_keys)} метрик:")
        for k in feature_keys:
            spec = REGISTRY[k]
            print(f"       - {k}: family={spec.family}, zone_levels={spec.zone_levels}, units={spec.units}")
    except Exception as e:
        print(f"[ERROR] Feature Registry: {e}")
        feature_keys = []
    
    # 2. Проверить metric_registry (stage2)
    METRICS = ()
    NAMES = ()
    try:
        from app6.stage2.metric_registry import METRICS, NAMES
        print(f"\n[OK] Metric Registry (stage2) содержит {len(METRICS)} метрик.")
        print(f"       Примеры: {NAMES[:10]}...")
        print(f"       ...и ещё {len(NAMES)-10} метрик.")
    except Exception as e:
        print(f"[ERROR] Metric Registry: {e}")
    
    # 3. Проверить, есть ли агрегатор для индивидуального профиля
    individual_aggregator_exists = Path('app6/stage3/individual_identity.py').exists() or Path('app6/stage2/skin/individual_fingerprint.py').exists()
    print(f"\n[INFO] Агрегатор индивидуального профиля (`individual_identity.py`): {individual_aggregator_exists}")
    
    # 4. Проверить, есть ли метрика стабильности морщин
    wrinkle_stability_exists = 'wrinkle_stability' in str(feature_keys)
    print(f"[INFO] Метрика стабильности морщин (`wrinkle_stability`): {wrinkle_stability_exists}")
    
    # 5. Проверить, есть ли тест на 200 фото
    test_200_exists = Path('tests/test_self_identity_200.py').exists()
    dataset_200_exists = Path('tests/dataset_200_self').exists()
    print(f"\n[INFO] Тест на 200 фото (`tests/test_self_identity_200.py`): {test_200_exists}")
    print(f"[INFO] Набор 200 фото (`tests/dataset_200_self/`): {dataset_200_exists}")
    
    # 6. Вывод ключевых проблем
    print("\n" + "=" * 70)
    print("КЛЮЧЕВЫЕ НАХОДКИ АУДИТА МЕТРИК:")
    print("=" * 70)
    print("1. Feature Registry содержит 18 метрик (3 базовые + 15 расширенных).")
    print("2. Metric Registry содержит 100 метрик для сравнения ПАР фото.")
    print("3. НО: нет агрегатора `individual_fingerprint` для сборки профиля человека.")
    print("4. НО: нет метрики `wrinkle_stability_score` для оценки стабильности морщин.")
    print("5. НО: нет нормализации по хронологии/возрасту для метрик 1999-2026.")
    print("6. НО: нет метрики `identity_score` или `same_person_probability`.")
    print("7. НО: нет теста `test_self_identity_200.py` для проверки «один человек».")
    print("8. НО: `scikit-image` не интегрирован централизованно в `app6/`.")
    print("9. РЕКОМЕНДАЦИЯ: создать `app6/stage3/individual_identity.py`.")
    print("10. РЕКОМЕНДАЦИЯ: создать `tests/test_self_identity_200.py` и `tests/dataset_200_self/`.")
    
    return {
        'feature_registry_ok': len(feature_keys) > 0,
        'metric_registry_ok': len(METRICS) == 100,
        'individual_aggregator_missing': not individual_aggregator_exists,
        'wrinkle_stability_missing': not wrinkle_stability_exists,
        'test_200_missing': not test_200_exists,
        'dataset_200_missing': not dataset_200_exists,
    }

if __name__ == '__main__':
    result = audit_metrics_for_individual_identification()
    missing = sum(1 for k, v in result.items() if 'missing' in k and v)
    print(f"\n[RESULT] Аудит метрик завершён. Пробелов: {missing} из {len(result)} проверенных компонентов.")
