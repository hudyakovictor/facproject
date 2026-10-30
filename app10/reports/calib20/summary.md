# app10 — калибровка на одном человеке (первые 20 кадров)

Единицы: RMS106 (morphing.backend.aligner.normalize_ldm106), сравнение vertices_identity_only после align_identity_mesh.

## Внутри бина (один человек)
- frontal (n=10): mean_within_bin=0.02945, median_within_bin=0.02733, std=0.00986
- left_profile (n=2): ~0.04933
- right_light/mid/profile (n=2): 0.022–0.026

## Фронтал vs другие
- frontal vs right_light: mean 0.0349 (близко к шуму фронтала)
- frontal vs right_mid: ~0.0597
- frontal vs left_mid: ~0.0376
- frontal vs right_deep: ~0.0647
- frontal vs left/right_profile: ~0.075–0.081

## Вывод
Шум внутри бина ~0.027–0.029 в RMS106. Смещение от ракурса растёт с отклонением; при сильном повороте разница одного человека между ракурсами становится сопоставима с межличностными границами из app9 — именно это и надо исключать при анализе. Рекомендуется сравнивать в одном бин-позе, либо калибровать пороги по бину и маркировать extrapolated при |yaw|>25°.
