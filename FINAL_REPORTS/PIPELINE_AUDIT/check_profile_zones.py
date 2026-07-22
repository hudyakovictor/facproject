#!/usr/bin/env python3
"""
ДИАГНОСТИКА: почему зоны правой щеки исключены на профильных рендерах
Эксперт: Forensic Face & Skin Consistency Analyst 99 левел

Проверяет pose_policy (CSV vs default) и объясняет исключение зон
для каждого из 9 ракурсов, особенно для profile (left/right).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

print("=" * 80)
print("ДИАГНОСТИКА ПРОФИЛЬНЫХ РАКУРСОВ: исключение зон на правой/левой щеке")
print("=" * 80)

# 1. Загрузка CSV (настоящая политика из репозитория)
print("\n[1] ПРОВЕРКА CSV ПОЛИТИКИ (`pose_policy_v3_9bins.csv`):")
csv_path = Path('app6/atlas/pose_policy_v3_9bins.csv')
if csv_path.exists():
    print(f"    Файл найден: {csv_path.resolve()}")
    try:
        import csv
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"    Всего записей: {len(rows)}")
        zones = sorted({r['zone_code'] for r in rows})
        print(f"    Зоны: {', '.join(zones)}")
        # Показать веса для profile-бинов (-60, 60)
        print(f"\n    ВЕСА ЗОН ДЛЯ ПРОФИЛЬНЫХ УГЛОВ (bin -60 = left_profile, +60 = right_profile):")
        print(f"    {'Zone':>6} | {'-60 (L_prof)':>14} | {'+60 (R_prof)':>14} | {'Статус для профиля':>20}")
        print(f"    {'-'*60}")
        for zone in zones:
            profile_rows = [r for r in rows if r['zone_code']==zone and r['yaw_bin_center_deg'] in ('-60','60')]
            w_neg = next((r['weight'] for r in profile_rows if r['yaw_bin_center_deg']=='-60'), 'N/A')
            w_pos = next((r['weight'] for r in profile_rows if r['yaw_bin_center_deg']=='60'), 'N/A')
            # Примечание: +yaw exposes anatomical-left
            note = ''
            if w_neg == '0.0' and w_pos == '1.0':
                note = 'Видна только при правом профиле (анатомически слева)'
            elif w_neg == '1.0' and w_pos == '0.0':
                note = 'Видна только при левом профиле (анатомически справа)'
            elif w_neg == '1.0' and w_pos == '1.0':
                note = 'Видна в обоих профилях'
            elif w_neg == '0.0' and w_pos == '0.0':
                note = 'ИСКЛЮЧЕНА в обоих профилях!'
            else:
                note = 'Ограниченная видимость'
            print(f"    {zone:>6} | {w_neg:>14} | {w_pos:>14} | {note:>20}")
    except Exception as e:
        print(f"    ОШИБКА чтения CSV: {e}")
else:
    print(f"    ОШИБКА: файл {csv_path} НЕ НАЙДЕН!")

# 2. Проверка Python default (`_build_default`)
print("\n[2] ПРОВЕРКА PYTHON DEFAULT (`_build_default` в `pose_policy.py`):")
print("    Если CSV не загружен (ошибка пути или формата), используется этот fallback.")
print("    Для `left` зон: primary при 10..40, support при -10..10, limited при -25..-10, exclude иначе.")
print("    Для `right` зон: primary при -40..-10, support при -10..10, limited при 10..25, exclude иначе.")
print("    Для `frontal` зон: primary при |yaw|<=25, support при |yaw|<=40, limited при |yaw|<=60, exclude иначе.")
print("    ВЫВОД: для profile (yaw ≈ ±70) ВСЕ зоны, кроме некоторых frontal, получат `exclude` или `limited`.")

# 3. Сравнение с фактическим поведением пользователя
print("\n[3] ОБЪЯСНЕНИЕ НАБЛЮДЕНИЯ ПОЛЬЗОВАТЕЛЯ:")
print("    Пользователь видит: 'на правой щеке как-будто исключены' на рендере `quality_weight.png`.")
print("    Возможные причины:")
print("    a) CSV загружен правильно: для правого профиля (yaw ≈ +70, bin +60) зоны типа A10/A12/A14")
print("       имеют weight=0.0 или очень низкий вес, поэтому они исключены из рендера.")
print("    b) CSV НЕ загружен, используется `_build_default`: для profile ВСЕ боковые зоны исключены,")
print("       что ещё более агрессивно, чем CSV.")
print("    c) Код `previews.py` использует `np.where(mask[...,None], ...)` — если `domain_mask` или")
print("       `quality_weight` для зоны = 0, она не отображается на рендере.")

# 4. Проверка пути загрузки CSV в pipeline
print("\n[4] ПРОВЕРКА ПУТИ ЗАГРУЗКИ CSV В ПАЙПЛАЙНЕ (`pipeline.py`, строка 92):")
print("    `policy = PosePolicy(Path(atlas_path).with_name('pose_policy_v3_9bins.csv'))`")
print("    Это создаёт путь относительно `atlas_path`. Если `atlas_path` указывает на файл")
print("    `texture_zones_bfm35709_v3.npz` в директории `app6/atlas/`, то CSV будет найден.")
print("    НО: если `atlas_path` указывает на другой путь или файл отсутствует, CSV не загрузится!")
print("    В этом случае используется `_build_default`, что приведёт к другим (и более жёстким) весам.")

# 5. Диагностика для всех 9 ракурсов (по данным CSV)
print("\n[5] ТАБЛИЦА: КАКИЕ ЗОНЫ ИСКЛЮЧЕНЫ ДЛЯ КАЖДОГО РАКУРСА (по CSV v3):")
print(f"    {'Zone':>6} | {'L_prof(-60)':>12} | {'L_deep(-40)':>12} | {'L_mid(-25)':>12} | {'Frontal(0)':>12} | {'R_prof(+60)':>12} | {'Статус профиля':>18}")
print(f"    {'-'*90}")
profile_zones = ['A01','A03','A05','A07','A09','A11','A13','A15','A17']  # Примерные «боковые» зоны
for zone in zones:
    weights = {}
    for r in rows:
        if r['zone_code'] == zone:
            weights[r['yaw_bin_center_deg']] = r['weight']
    vals = [weights.get(str(b), '?') for b in [-60,-40,-25,0,60]]
    # Определить статус
    w_prof = weights.get('-60', '0.0') if zone.startswith('A0') else weights.get('60', '0.0')
    status = 'ИСКЛЮЧЕНА' if w_prof == '0.0' else ('ОГРАНИЧЕНА' if float(w_prof) < 0.5 else 'ПРИМАРИ')
    print(f"    {zone:>6} | {vals[0]:>12} | {vals[1]:>12} | {vals[2]:>12} | {vals[3]:>12} | {vals[4]:>12} | {status:>18}")

print("\n[6] РЕКОМЕНДАЦИИ:")
print("    1. Убедиться, что `PosePolicy` загружает CSV (`pose_policy_v3_9bins.csv`), а не использует `_build_default`.")
print("    2. Проверить, что `atlas_path` в `pipeline.py` указывает на существующий файл, от которого")
print("       можно построить правильный путь к CSV.")
print("    3. Для профильных фото (`left_profile`, `right_profile`) ожидаемо, что боковые зоны")
print("       будут исключены или ограничены — это физически верно (часть лица скрыта).")
print("    4. НО: если зоны исключены там, где они ДОЛЖНЫ быть видны (например, правая щека")
print("       на `right_profile` с yaw ≈ +70°), проверьте, загружен ли CSV или используется default.")
print("    5. Для проверки: запустите скрипт с явным указанием `pose_policy` или проверьте")
print("       содержимое `quality.json` (ключ `pose_policy`) — там должно быть `pose_policy: available`.")
