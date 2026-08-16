# Тестирование и критерии приёмки

## Уровни

1. Unit: naming, EXIF date, hashes, pose gap, utility NaN, Kabsch, thresholds, FDR.
2. Contract: NPZ/CSV/info consistency, stable field names, API schemas.
3. Scenario truth: NULL, AABBAA, AABBBB, ABABAB, step, return, flicker, drift, low quality, pose false-positive.
4. Calibration: 5–6 person combinations на каждый сценарий; LOPO 7 folds.
5. End-to-end: Stage 1→2→3→API→UI→print/export.
6. Determinism: два прогона, одинаковые входы/хеши, одинаковые canonical artifacts.

## Обязательные gates

- `python -m compileall -q app6`.
- `python -m unittest app6.test_module.test_round5_patches -v` → 7/7.
- Полный pytest/branch coverage после установки dev dependencies.
- `npm ci && npm test -- --run && npm run build` на Linux.
- Negative-control AUC 0.45–0.55.
- NULL return FPR = 0 в golden scenarios.
- Public report forbidden-term scan = pass.
- API golden files и UI snapshots совпадают.

## Известное состояние архива

В среде аудита `pytest` отсутствовал. Вложенный `ui/node_modules` был собран не для Linux: отсутствовал `@rollup/rollup-linux-x64-gnu`. Поэтому полный старый suite не объявляется пройденным; перед release нужен чистый dependency install.
