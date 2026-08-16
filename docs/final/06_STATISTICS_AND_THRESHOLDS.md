# Статистика и пороги

## Единица независимости

Frame-pairs коррелированы. В отчёте одновременно показывать raw pair count и effective units: person, person-pair, capture event, source cluster. Confidence intervals строить cluster bootstrap, а не bootstrap строк.

## FDR

Канонический уровень 0.05. `p95_point_z` — порядковая статистика по m точкам, не одиночный normal z. В pair row обязательно `calibrated_point_count`; если m<20, результат диагностический и limited. FDR не превращает candidate в identity verdict.

## Пороги

Порог обучается только на calibration split. Основной датасет не используется для tuning. Рекомендуется lower CI bound и holdout FPR. Для same-day baseline применяется lower80 contamination-hardened policy.

## Return/trend

A→B→A требует не только отношения divergence, но и абсолютного `min_mid_divergence=0.03`, иначе почти стабильный NULL удовлетворяет отношению из-за малого знаменателя. Return подтверждается distance-based detector + trend/CUSUM и независимым pose bin.

## Mandatory reports

AUC + CI, TPR, FPR, ARI, return score, LOD, retained fraction/cost, LOPO mean/sd/min-CI, noise sensitivity, contamination curve, negative control, holdout breakdown. Не публиковать одну AUC без operating point и exclusions.
