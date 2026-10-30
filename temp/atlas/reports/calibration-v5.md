# Калибровка v5: решение по `euclid + calibrated`

Итерация 5. `configs/runtime.yaml` не менялся: heatmap `euclid + none`, график `euclid + none + none`. Геометрия, морф-пайплайн и поворотная ветка не тронуты. Значения считает только `server.heat.compute_heat_values`; второй формулы в браузере нет.

## 1. Вердикт

**НЕ включать euclid + calibrated.** Не выполнены условия 3 (LOTRO mid_deep), 4 (round-trip не измеряется), 5 (веса нестабильны).

`euclid + calibrated` остаётся флагом в конфиге, `weights-v4.json` не подключён. Heatmap и график дефолтов не менялись.

## 2. Таблица гейтов (§3)

| # | условие | значение | источник | статус |
|---|---|---|---|---|
| 1 | Нижняя граница CI ΔAUC > 0 на 10 людях | CI [0.0084, 0.0206], ΔAUC 0.0145 | шаг 1 | прошёл |
| 2 | LOPO: минимум ΔAUC не хуже −0.02 | min Δ -0.0036 (7), -0.0095 (10); побед 6/7, 7/10 | шаг 2 | прошёл |
| 3 | LOTRO: 4 из 4, mid_deep не хуже −0.005 | CI-положительных семейств 0/4; mid_deep ΔAUC -0.014 (порог −0.005) | шаг 1 | не прошёл |
| 4 | Серия frontal → profile → frontal возвращается в допуск 10% | не измеряется: в корпусе нет ни одной серии «туда и обратно» | шаг 4 | не измеряется |
| 5 | Гейт весов пройден | медиана \|Δw\| 34.7% (порог 10%), на границах clip 10.0% (порог 1%), ΔAUC>0 5/5 | шаг 6 | не прошёл |
| 6 | Паритет API и harness = 0, config_switch проходит | all_pass True; raw_kept True, display_changed True, metric_changed True, restored True | chart_parity.py | прошёл |

## 3. Числа по шагам

### Шаг 1. Bootstrap CI ΔAUC (`reports/calibration/bootstrap-v5.json`)

Ресемплинг по людям, seed 42, 2000 повторов. Кандидат `euclid + calibrated` против baseline `euclid + none`.

| срез | within | between | AUC none | AUC calibrated | ΔAUC | 95% CI | низ CI > 0 |
|---|---|---|---|---|---|---|---|
| 10 людей | 564 | 7808 | 0.7289 | 0.7434 | 0.0145 | [0.0084, 0.0206] | да |
| 7 размеченных | 454 | 4635 | 0.7527 | 0.7731 | 0.0204 | [0.0125, 0.0285] | да |

LOTRO-семейства (профиль переодевается без семейства):

| семейство | within | ΔAUC точка | 95% CI | низ CI > 0 | точка ≥ −0.005 |
|---|---|---|---|---|---|
| frontal_light | 17 | 0.0315 | [-0.0342, 0.1329] | нет | да |
| light_mid | 22 | 0.0171 | [-0.0186, 0.0597] | нет | да |
| mid_deep | 17 | -0.0140 | [-0.0439, 0.0191] | нет | нет |
| deep_profile | 48 | 0.0075 | [-0.0206, 0.0437] | нет | да |

Гейты шага 1: CI>0 на 10 людях — да; семейств с CI>0 — 0/4; mid_deep точка ≥ −0.005 — нет. Кросс-проверка AUC против sklearn: max|Δ| = 0.0.

![bootstrap ΔAUC](figures/v5-bootstrap-auc.png)

### Шаг 2. LOPO без предсказанных поз (`reports/calibration/lopo-v5.json`)

| метрика | побед (7) | побед (10) | min ΔAUC (7) | min ΔAUC (10) |
|---|---|---|---|---|
| weighted_euclid | 6/7 | 7/10 | -0.0036 | -0.0095 |

Гейт: `weighted_euclid` ≥5/7 и min ΔAUC не хуже −0.02 — пройден. На 7 размеченных weighted_euclid заметно стабильнее, чем на 10 (мин ΔAUC -0.0036 против -0.0095): просадка на 10 людях объясняется шумом предсказанных поз wild-людей. Шаг 3 (разметка person_9/10/11) релевантен.

### Шаг 3. Ручные yaw-метки (`reports/calibration/pose-labels-v5.json`)

56 кадров (person_9/10/11), валидных 48, invalid_pose 8. Порог `invalid_pose`: LABEL_MISMATCH 90.0°, yaw_limit 95.0° (источник: calibration_v3.LABEL_MISMATCH / YAW_LIMIT (текущий конфиг харнесса)). Медиана |метка − предсказание| на валидных 1.6°, p90 14.3°. Источник поз переключён `predicted → manual+yaw`.

Причины invalid_pose:
- label_mismatch: |35 - -89| = 124 > 90
- non_face: съёмка со спины, лица нет
- non_face: субъект отвернут, фронтальной составляющей лица нет
- non_face: бронзовая статуя, не живое лицо
- non_face: в кадре только другие люди, субъекта нет
- non_face: обложка книги с миниатюрным фото
- label_mismatch: |-55 - 79| = 134 > 90
- non_face: кинопостер, на постере другие актёры

### Шаг 4. Серия frontal → profile → frontal

**Не измеряется.** фронт→профиль→фронт в корпусе отсутствует: все видеосерии монотонные развёртки; снять новые кадры нельзя. Медианный фильтр не включался (он роняет чувствительность с 1.00 до 0.50).

### Шаг 5. Фронтальный гейт (`reports/calibration/frontal-gate-v5.json`)

С ручными метками шага 3 гейт стал измеримым (в v4 при зазоре 30 была 1 пара).

| зазор | пар | людей | euclid within | calibrated within | Δ | вывод |
|---|---|---|---|---|---|---|
| 30 | 22 | 10 | 0.07391 | 0.06455 | -12.7% | calibrated снижает within-разброс на фронтальных парах |
| 10 | 34 | 10 | 0.05176 | 0.04523 | -12.6% | calibrated снижает within-разброс на фронтальных парах |

### Шаг 6. Устойчивость весов (`reports/calibration/weights-stability-v5.json`)

5 разбиений пополам (seed 42). Медиана |Δw| 34.7% (порог 10%), вершин на границах clip 10.0% (порог 1%), ΔAUC>0 в 5/5 разбиений. Гейт не пройден → `weights-v4.json` неподключён.

| разбиение | медиана \|Δw\| | на границах clip % | ΔAUC B\|A | ΔAUC A\|B |
|---|---|---|---|---|
| 0 | 34.7% | 10.0% | 0.0135 | 0.0108 |
| 1 | 40.4% | 10.0% | 0.0057 | 0.0167 |
| 2 | 25.6% | 10.0% | 0.0180 | 0.0035 |
| 3 | 37.9% | 10.0% | 0.0129 | 0.0037 |
| 4 | 9.2% | 10.0% | 0.0254 | 0.0101 |

![устойчивость весов](figures/v5-weights-stability.png)

## 4. Проверки перед закрытием (§4)

| проверка | результат |
|---|---|
| тесты проекта | 64 passed, 2 failed (не зелёные, см. п. «не удалось») |
| └ test_metric_registry_pose_values | 23 == 3: registry.catalog() отдаёт 23 метрики 3ddfa_v3: metrics/tddfa_v3/archive_top20.py регистрирует 20 archive_* сверх трёх сетевых. Не зависит от корпуса и от итерации 5. |
| └ test_projection_seed_and_real_alpha | silhouette is None: в рабочем data/library.json 294 не-демо фото в 11 группах, silhouette считается при >1 группе. Тест рассчитан на чисто демо-библиотеку. Не зависит от гейтов калибровки. |
| chart_parity API==harness | max\|Δ\| = 0, all_pass True |
| config_switch | raw_kept True, display_changed True, metric_changed True, restored True |
| ключ кэша ряда | metric, weighting, temporal_filter, filter_window, profile_path, profile_mtime_ns (источник: server/app.py chart_config_signature() → lru chart_payload) |
| таймлайн data-testid | chart-track = 1, .metric-track:not(.chart-track) = 0 |
| скриншот | `reports/figures/v5-timeline-ui.png` |

## 5. Что изменилось против v4

- Появился CI для ΔAUC: на 10 людях нижняя граница 0.0084 > 0 (в v4 CI не считался) — блокер CI снят;
- ЛОТО-провал уточнён: mid_deep точка ΔAUC −0.0140 против −0.0175 в v4, порог −0.005 всё равно нарушен;
- Фронтальный гейт стал измерим (22 пары на 10 людях, −12.7%) после ручной разметки шага 3 (в v4 — 1 пара);
- Веса: медиана |Δw| 34.7% внутри корпуса против 27% между корпусами в v4 — стабильности по-прежнему нет.
- Хвост §6: добавлен экспорт ряда графика `GET /api/chart/series.csv` (тот же `chart_payload`,
  вторая формула в браузере не появилась); транзитные `web/.runtime/*.png` удалены.

## 6. Что не удалось проверить

| пункт | причина |
|---|---|
| Серия frontal → profile → frontal (шаг 4) | в корпусе нет маршрута туда-обратно; значение не возвращается — не измерено, а не «плохо» |
| Тесты проекта полностью зелёные (§4.1) | 2 падения предсуществующие: реестр метрик (23 против 3) и живая библиотека фото (silhouette). К итерации 5 не относятся |

## 7. Файлы

| файл | роль |
|---|---|
| `scripts/v5_corpus.py` | общая инфраструктура шагов 1,2,5,6: корпус, пары, bootstrap |
| `scripts/bootstrap_auc.py` | шаг 1: bootstrap CI ΔAUC + LOTRO-семейства |
| `scripts/lopo_v5.py` | шаг 2: LOPO на 7 размеченных и 10 людях |
| `scripts/pose_labels_v5.py` | шаг 3: ручные yaw-метки person_9/10/11, invalid_pose |
| `scripts/frontal_gate_v5.py` | шаг 5: фронтальный гейт при зазоре 30 и 10 |
| `scripts/weights_stability_v5.py` | шаг 6: устойчивость весов на половинах людей |
| `scripts/v5_bootstrap_figure.py` | рисунок v5-bootstrap-auc.png |
| `scripts/v5_report.py` | этот отчёт |
| `scripts/chart_parity.py` | §4.2–4.3: паритет API==harness, config_switch |
| `web/v5-timeline-check.mjs` | §4.5–4.6: проверка data-testid и скриншот |
| `server/app.py` | §4.4: chart_config_signature в ключе кэша; §6: GET /api/chart/series.csv |
| `web/src/components/Timeline.tsx` | §6: ссылка «График CSV» на /api/chart/series.csv (те же rows) |
| `configs/runtime.yaml` | дефолты heatmap и chart не менялись |

Рисунки: `figures/v5-bootstrap-auc.png`, `figures/v5-lopo-7vs10.png`, `figures/v5-weights-stability.png`, `figures/v5-timeline-ui.png`. `v5-series-roundtrip.png` не создан — шаг 4 не измеряется.
