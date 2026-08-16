# Валидированный метод продольного сравнения

## Зафиксированная конфигурация

- 9 неизменяемых yaw bins: left/right profile, deep, mid, light и frontal.
- Primary coordinates: `ldm134_object_normalized` / `ldm106_object_normalized`.
- Pair alignment: iteratively trimmed Kabsch, trim 15%, без scale.
- Pair gate внутри одного bin: yaw gap ≤6°, pitch gap ≤2°, roll gap ≤5°.
- Минимум общих точек: 30 для LDM134, 24 для LDM106.
- Минимальная alignment quality: 0.5.
- Рекомендуемый descriptor package: Procrustes/local shape + stable subset91.
- Secondary channels: alpha, texture, mesh zones; они не заменяют primary geometry.

## Почему raw, а не chronology-aligned

DCRD показал, что pose объясняет 46.1% вариации, identity — 5.5%. Chronology correction при больших угловых разрывах усиливает остаток: AUC падает 0.9866 при 2° до 0.8371 при 20°. Raw держит AUC около 0.99, LOPO стабильнее и лучше распознаёт возврат AABBAA: 0.881 против 0.429. Поэтому full-pose chronology остаётся диагностическим каналом, но не primary identity-shape channel.

## Выбранный operating point

Комплексная конфигурация `raw + proc + subset91 + gap6 + qmin0.5` дала AUC 0.9916, нижнюю границу 0.9842, ARI 0.622, FPR 0.166, cost 0.708, LOD 0.82σ. Для строгого subset анализа вариант yaw/pitch separation с pitch ≤2° дал AUC 0.9931 и ci_lo 0.9858.

## Запрещённые упрощения

- Не сравнивать разные pose bins в primary score.
- Не принимать `aligned` или `chronology` за raw.
- Не использовать hard reject «всё >20°» как единственный pose control.
- Не вычитать позу единым `const` после измерения: это хрупко и снижает AUC.
- Не вычислять utility через обычный `min` при NaN.
- Не считать тысячи frame-pairs независимыми наблюдениями.
- Не использовать alpha_id как единственный identity descriptor: ci_lo 0.6768.

## Интерпретация

Отчёт должен разделять measurement, calibration status, applicability, corroboration и human interpretation. Статус candidate не является утверждением о личности, причине изменения, маске, операции или болезни.
