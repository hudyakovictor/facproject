# Протокол калибровки

## Состав

Семь разных людей, девять неизменных pose bins. Нулевая модель строится **внутри человека и bin**, затем лица получают равный вес. Кадры одной видеосерии не считаются независимыми людьми.

## Pair selection

Тот же axis gate, что в основном анализе: yaw ≤6°, pitch ≤2°, roll ≤5°. Visibility intersection; quality ≥0.5. Не смешивать raw и chronology coordinates. Pair offsets должны покрывать соседние и более дальние кадры без доминирования длинной серии.

## Contamination hardening

Симуляция показала: 10% contamination снижает TPR примерно 0.96→0.51, 20% →0.24. Поэтому:

- референс формируется из person-level summaries;
- порог использует lower-tail/trimmed policy, максимум 20% contamination;
- каждая персона проходит leave-one-person-out;
- подозрительная персона/серия не удаляется молча: формируется sensitivity report;
- threshold release запрещён при сильной зависимости от одной персоны.

## Utility artifact

`landmark_utility.npy` может содержать NaN для невидимых профильных точек. Использовать `sanitize_utility`, затем conservative cross-bin score. `stable_subset(...,91)` обязан возвращать ровно 91 уникальный индекс. Хеш utility artifact входит в config/artifact manifest.

## Acceptance

Минимум: 7 persons; все 9 bins; LOPO sd желательно ≤0.005 для primary package; cilo_min ≥0.95; negative control около 0.5; profile bins отдельно маркируются limited, если effective person-pairs недостаточно.
