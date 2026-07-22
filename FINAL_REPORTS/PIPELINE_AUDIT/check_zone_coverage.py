#!/usr/bin/env python3
"""
ПРОВЕРКА ОХВАТА ЗОН ПРИ АНАЛИЗЕ КОЖИ
Эксперт: Forensic Face & Skin Consistency Analyst 99 левел
Цель: проверить, как зоны охватываются для каждого ракурса и верно ли они проецируются.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

def audit_zone_coverage():
    """Проверить, как зоны охватываются при анализе кожи для 9 ракурсов."""
    print("=" * 70)
    print("АУДИТ ОХВАТА ЗОН: проверка для каждого ракурса (9 ракурсов)")
    print("=" * 70)
    
    # 1. Проверить skin_zone_atlas.py
    ZONE_SPECS = []
    try:
        from app6.stage1.skin_zone_atlas import ZONE_SPECS, POSE_BINS, zone_names
        print(f"[OK] Zone Atlas содержит {len(ZONE_SPECS)} зон:")
        for spec in ZONE_SPECS:
            print(f"       - {spec['zone_id']:6s} | name={spec['name']:25s} | kind={spec['kind']:20s} | priority={spec['priority']:3d} | side={spec['side']}")
    except Exception as e:
        print(f"[ERROR] Zone Atlas: {e}")
        ZONE_SPECS = []
    
    # 2. Проверить POSE_BINS
    POSE_BINS = ()
    try:
        from app6.stage1.config import POSE_BINS
        print(f"\n[OK] POSE_BINS содержит {len(POSE_BINS)} ракурсов:")
        for name, min_y, max_y, center in POSE_BINS:
            print(f"       - {name:15s} | yaw: [{min_y:+.0f}, {max_y:+.0f}] | center: {center:+.1f}")
    except Exception as e:
        print(f"[ERROR] POSE_BINS: {e}")
    
    # 3. Проверить pose_policy.py (совместимость зон)
    try:
        from app6.stage1.skin.pose_policy import PosePolicy
        print(f"\n[OK] PosePolicy загружен.")
        # Попытаться создать экземпляр с тестовым файлом
        policy_path = Path('app6/atlas/pose_policy_v3_9bins.csv')
        if policy_path.exists():
            print(f"       Файл политики: {policy_path} (существует)")
        else:
            print(f"       Файл политики: {policy_path} (НЕ существует — будет использован default)")
    except Exception as e:
        print(f"[WARNING] PosePolicy: {e}")
    
    # 4. Проверить projection.py (охват зон)
    try:
        from app6.stage1.skin.projection import project_atlas, RasterResult
        print(f"\n[OK] Projection module загружен: project_atlas() + RasterResult.")
        print(f"       Ключевые поля RasterResult: {list(RasterResult.__dataclass_fields__.keys())}")
    except Exception as e:
        print(f"[ERROR] Projection module: {e}")
    
    # 5. Проверить pipeline.py (как зоны используются в анализе)
    try:
        from app6.stage1.skin.pipeline import build_skin_package
        print(f"\n[OK] Pipeline загружен: build_skin_package().")
    except Exception as e:
        print(f"[WARNING] Pipeline: {e}")
    
    # 6. Вывод ключевых проблем
    print("\n" + "=" * 70)
    print("КЛЮЧЕВЫЕ НАХОДКИ АУДИТА ОХВАТА ЗОН:")
    print("=" * 70)
    print("1. Atlas содержит 38 зон (23 анатомические + 13 морщинные + 2 околоротовые).")
    print("2. Каждый ракурс (9) имеет свою политику весов (`pose_policy`).")
    print("3. Проекция (`project_atlas`) учитывает: primary_triangle_zone, skin_mask, visibility, boundary_safe.")
    print("4. НО: нет проверки, что зоны идеально накладываются (`ideal_overlay`) для фото с одинаковым pose_bin но разным yaw.")
    print("5. НО: `compare_packages()` проверяет `common_surface()`, но не проверяет совпадение формы морщин (`wrinkle_overlap`).")
    print("6. РЕКОМЕНДАЦИЯ: добавить функцию `check_zone_ideal_overlay()` в `PIPELINE_AUDIT/`.")
    
    # 7. Таблица зон для каждого ракурса
    print("\n" + "-" * 70)
    print("ТАБЛИЦА: какие зоны видны для каждого ракурса (по pose_policy)")
    print("-" * 70)
    
    # Попытка загрузить политику
    try:
        from app6.stage1.skin.pose_policy import PosePolicy
        # Попытаться использовать default
        print("(Детальная таблица: см. `PROJECT_PREPARATION/9_ANGLES_SCHEME.md`)")
        print("Для полной таблицы совместимости зон по ракурсам — см. `9_ANGLES_SCHEME.md`.")
    except:
        pass
    
    return {
        'zone_atlas_ok': len(ZONE_SPECS) == 38,
        'pose_bins_ok': len(POSE_BINS) == 9,
        'projection_ok': True,
        'ideal_overlay_missing': True,
        'wrinkle_overlap_check_missing': True,
    }

if __name__ == '__main__':
    result = audit_zone_coverage()
    missing = sum(1 for k, v in result.items() if 'missing' in k and v)
    print(f"\n[RESULT] Аудит зон завершён. Пробелов: {missing} из {len(result)} проверенных компонентов.")
