# Аудит предизвлечённой геометрической калибровки

**Дата:** 2026-08-03 · **вход:** `calibration_dataset/person_*/frame_*/` · **режим:** только landmark CSV + `info.json`, без повторного inference.

## Статус и границы вывода

В дереве найдены **943 complete-записи**, 7 персон и все 9 нормативных ракурсов. Это достаточный материал для **экспериментальной проверки поведения 3D landmarks и сценариев**, но не для выпуска production-порогов: в нём нет исходных изображений, проверяемой цепочки источников, свежего `main_timeline.csv`, NPZ с параметрами модели и независимых субъектов. Поэтому результаты ниже не являются выводом о чьей-либо личности и не должны подменять перекалибровку Stage 1.

Добавлен воспроизводимый инструмент:

```bash
python tools/audit_preextracted_calibration.py \
  --input calibration_dataset --output /tmp/calibration_audit.json
```

Он нормализует `ldm134_raw.csv` ровно один раз по `info.normalization`, сохраняет раздельными raw/aligned/chronology пространства, применяет действующий axis-specific pose gate, строит зависимые same-person и balanced different-person контрольные пары. AUC — описательная вероятность ранжирования, **не** независимая accuracy.

## Покрытие

| Ракурс | кадров | персон | same/different измеримых пар raw |
|---|---:|---:|---:|
| left_profile | 187 | 7 | 15 / 2 |
| left_deep | 49 | 7 | 30 / 26 |
| left_mid | 63 | 7 | 28 / 30 |
| left_light | 69 | 7 | 30 / 51 |
| frontal | 186 | 7 | 30 / 157 |
| right_light | 77 | 7 | 30 / 76 |
| right_mid | 68 | 7 | 29 / 28 |
| right_deep | 56 | 7 | 26 / 1 |
| right_profile | 188 | 7 | 22 / 16 |

У каждого человека есть хотя бы один кадр в каждом bin. Однако баланс крайне неоднороден: например, у person_05 всего 3 left-profile, у person_03 — 2 right-deep, а у person_01 — 3 left-deep. В profile/deep контролях мало прошедших межперсональных пар из-за строгого pose gate. Эти bins нельзя использовать для численного порога без стратифицированного добора.

## Описательный тест разделимости

Внутри одного pose bin сравнивались только пары, прошедшие yaw/pitch/roll gate; расстояние — RMS LDM134 после trimmed Kabsch без scale. Raw same/different median и AUC:

| Ракурс | same median | different median | AUC |
|---|---:|---:|---:|
| left_profile | .00335 | .04391 | 1.000* |
| left_deep | .00362 | .03328 | 1.000 |
| left_mid | .00472 | .03111 | 1.000 |
| left_light | .00456 | .03530 | .943 |
| frontal | .00281 | .02960 | .999 |
| right_light | .00521 | .03822 | .964 |
| right_mid | .00507 | .01202 | .924 |
| right_deep | .00373 | .03968 | 1.000* |
| right_profile | .00422 | .04036 | 1.000* |

`*` — не интерпретировать как доказательство: different-pair n ≤16 (в right-deep n=1). Наиболее информативные для первого regression-пула: frontal, left/right light, left/right mid и left_deep; для profile/deep нужны подбины и добор пар.

При Kabsch raw и aligned дали практически одинаковые числа — ожидаемый результат, поскольку rigid alignment устраняет саму жёсткую поворотную часть canonical transform. Chronology-координаты иногда меняют ранжирование; они полезны только как диагностическая ветка, не как primary identity score.

## Что тестировать далее

1. Зафиксировать этот набор как `exploratory_preextracted_v1` и не смешивать с production calibration.
2. Для каждого bin выбрать кадры по **позе**, а не по имени: canonical (|yaw−центр|≤3°), light/edge (≥8°), с отдельной таблицей pitch/roll/expression/visibility.
3. Для каждого человека сравнить edge→canonical с near-canonical→near-canonical. Проверять не «улучшил ли поворот лицо», а растут ли residual и доля невидимых точек; результат стратифицировать по bin.
4. Провести leave-one-person-out: порог и ranking строятся на шести людях, тестируются на седьмом. Все кадры одной видеосерии остаются одним кластером.
5. Выпустить сценарные fixtures S01–S08 в каждом достаточном bin (включая AABBAA, ABABAB, isolated B), с синтетическими датами только для порядка. Expected result — measurement status/граница события, не «вердикт личности».
6. Перед основным архивом повторить extraction из исходных фото, сформировать provenance sidecar, quality strata и новую калибровку. Затем выполнить Stage 1 → Stage 2 → Stage 3 → API → UI/export golden run.
