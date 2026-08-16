# Реестр экспериментальных результатов

## Датасет калибровки

943 кадра, 7 персон, 9 bins. Bin counts: profiles 187/188, frontal 186, light 69/77, mid 63/68, deep 49/56. Partial R²: pose 46.1%, bin 7.1%, identity 5.5%, quality 3.2%, expression 1.0%.

## Gap degradation

AUC по gap bands: 0–2° 0.989; 2–4° 0.976; 4–6° 0.948; 6–8° 0.930; 8–12° 0.882; 12–20° 0.742; >20° 0.495. Chron gap sweep: 0.9866@2° → 0.8371@20°.

## Scenario truth

Raw: step ARI 0.962/FPR 0.036; return ARI 0.888/FPR 0.067; AABBAA return 0.881. Chronology: return ARI 0.477/FPR 0.173; AABBAA 0.429. Original irreversible-return detector fired on AABBAA and NULL; patch adds absolute divergence floor.

## 300 simulations

300/300, errors 0. Negative control AUC mean 0.4988, max 0.5045. Strong screeners: E1/E5/E6 ci_lo 0.9855; A1 raw ci_lo 0.9817, ARI 0.673, cost 0.112. Weak: alpha_id ci_lo 0.6768; hard >20° 0.7726; per-bin/per-landmark pose subtraction 0.8601.

Best package holdout: P3 raw+proc+subset91, cilo_min 0.9534, ARI 0.591, LOD 0.70, fpr_hold 0.029. Final combined candidate: raw+proc+subset91+gap6+qmin0.5 AUC 0.9916, ci_lo 0.9842, ARI 0.622.

## Robustness

Noise σ 0.002→0.010: raw AUC 0.9935→0.9886; proc 0.9915→0.9855; pose subtraction 0.9091→0.8606. Contamination 10% снижает TPR примерно до 0.51, 20% до 0.24. LOPO: proc sd 0.0038; raw4 AUC 0.9928/sd 0.0050/cilo_min 0.9735.

## Utility defect

`landmark_utility.npy` содержит NaN: по bins 34/18/4/2/0/1/3/8/22. Обычный `min` дал 53 точки вместо 91; utility weighting без sanitation снижал AUC до 0.6098. Первый 300-run с этим дефектом аннулирован и полностью пересчитан.
