# app10 — калибровка на одном человеке (частичная выборка)

Единицы: RMS106, vertices_identity_only, align_identity_mesh. Без двойного поворота.

## Шум внутри бина
- frontal (n=32): mean 0.02975, median 0.02704
- left_light (n=16): mean 0.02770, median 0.02817
- left_mid (n=19): mean 0.02783, median 0.02617
- right_light (n=3): 0.03438
- right_mid (n=2): 0.02238
- right_profile (n=6): 0.04121
- left/right_profile (n=2): ~0.04933

## Фронтал vs ракурс
- frontal vs left_light: ~0.033 (очень близко к шуму фронтала)
- frontal vs right_light: ~0.043
- frontal vs left_mid/right_light_mid: ~0.041
- frontal vs deep: ~0.051–0.064
- frontal vs profile: ~0.074–0.081

## Вывод
Внутри бина шум ~0.027–0.029. Смещение при небольшом повороте (light/mid) сопоставимо с шумом или чуть выше; при профильных уже существенно выше. Для исключения шумов нормализации/ракурса: сравнивать только в согласованном бин-позе, использовать бин-специфичные пороги, при |yaw|>~25–35° и сильном смещении помечать как "extrapolated"/"неопределённо".
