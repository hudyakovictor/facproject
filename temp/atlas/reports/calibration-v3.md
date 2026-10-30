# Калибровка v3 · normal + calibrated weighting

Вердикт: **3. weighting улучшает числа, но normal нестабилен по людям — только отчёты** (6/8 production-гейтов).

Baseline `vertices + euclid + none`; кандидат `vertices + normal + calibrated` в пространстве `center + IOD (eye-contour means ldm68 36:42/42:48)`. Геометрия и морф не меняются: калибровка влияет только на значения карты.

Корпус: 208 валидных кадров (210 всего), 7 человек, 453 пар для sigma, зазор 30.

## Данные

| персона | кадр | бин | yaw | причина |
|---|---|---|---|---|
| person_06 | 164 | right_profile | -102.5 | abs(yaw)=-102.5>95; label=right_profile yaw=67.1 vs -102.5 |
| person_06 | 170 | right_profile | -32.6 | label=right_profile yaw=71.2 vs -32.6 |

Кадры person_06/164, person_06/170 помечены `invalid_pose` и исключены из sigma, статистики и профиля весов. Первый отсечён по `abs(yaw) > 95` и по расхождению метки с предсказанием больше 90°, второй — только по расхождению (метка right_profile, предсказанный yaw −32.6°). Внутри пар их нет: утечек 0. Манифест: `reports/calibration/invalid-frames.json`.

Пары: within 454 (same-bin 5, cross-bin 449), between 4635.

| семейство переходов | within | between |
|---|---|---|
| deep_profile | 45 | 525 |
| frontal_light | 7 | 293 |
| light_mid | 15 | 175 |
| mid_deep | 14 | 154 |
| same_0 | 1 | 168 |
| same_1 | 6 | 123 |
| same_2 | 5 | 60 |
| same_3 | 10 | 91 |
| same_4 | 57 | 677 |
| skip_0_2 | 14 | 208 |
| skip_0_3 | 26 | 258 |
| skip_0_4 | 107 | 687 |
| skip_1_3 | 20 | 218 |
| skip_1_4 | 80 | 584 |
| skip_2_4 | 47 | 414 |

## Режимы heatmap

| режим | within μ | cross-bin μ | between μ | ratio | AUC | z>3 within | z>3 between |
|---|---|---|---|---|---|---|
| euclid | 0.05201 | 0.05239 | 0.06958 | 1.338 | 0.7527 | 0.1727 | 0.3768 |
| normal | 0.02244 | 0.02258 | 0.03445 | 1.535 | 0.7779 | 0.005 | 0.0715 |
| weighted_euclid | 0.04601 | 0.04635 | 0.06277 | 1.364 | 0.7731 | 0.1727 | 0.3768 |
| weighted_normal | 0.01943 | 0.01956 | 0.03056 | 1.573 | 0.8006 | 0.005 | 0.0715 |

Baseline и кандидат по разрезам. Абсолютные значения within/between несопоставимы между режимами (normal меняет единицы), поэтому изменение в процентах ниже — только масштаб; сравнимы ratio, AUC и z>3:

| разрез | baseline euclid | candidate weighted normal | изменение |
|---|---:|---:|---:|
| within overall | 0.05201 | 0.01943 | -62.6% |
| within cross-bin | 0.05239 | 0.01956 | -62.7% |
| between overall | 0.06958 | 0.03056 | -56.1% |
| ratio | 1.338 | 1.573 | +17.6% |
| AUC | 0.7527 | 0.8006 | +6.4% |
| z > 3 within | 0.1727 | 0.005 | -97.1% |
| z > 3 between | 0.3768 | 0.0715 | -81.0% |

Эффект только весов внутри одной метрики (единицы не меняются):

| сравнение | Δ within | Δ cross-bin | Δ between | ratio | AUC |
|---|---|---|---|---|---|
| normal → weighted normal | -13.4% | -13.4% | -11.3% | 1.535→1.573 | 0.7779→0.8006 |
| euclid → weighted euclid | -11.5% | -11.5% | -9.8% | 1.338→1.364 | 0.7527→0.7731 |

ΔAUC (weighted normal − euclid) = 0.0479 [0.0114; 0.0779], P(>0)=1.0 (парный bootstrap, 200 итераций).

ΔAUC (normal − euclid) = 0.0252 [-0.0074; 0.0549].

Разделение эффектов: переход euclid→normal меняет единицы (|d|→|d·n|), поэтому cross-bin μ падает на -56.9% уже без весов. Эффект самих весов считается внутри normal: within -13.4%, cross-bin -13.4%. ratio 1.338→1.573, AUC 0.7527→0.8006.

Поле направлений для normal — нормали среднего лица (`data/topology.json`), а не отдельные нормали каждого кадра. Иначе один и тот же переход получал разные значения в конце сегмента s и начале s+1 и карта рвалась на стыке: heat join 5.6e−2 вместо 0. Поэтому числа هنا считаются той же реализацией, что стоит в приложении, и немного отличаются от второй итерации.

## Leave-one-person-out

| человек | within пар | AUC euclid | AUC normal | AUC weighted euclid | AUC weighted normal |
|---|---|---|---|---|---|
| person_01 | 66 | 0.8445 | 0.888 | 0.8409 | 0.9007 |
| person_02 | 78 | 0.7831 | 0.6937 | 0.837 | 0.747 |
| person_03 | 55 | 0.8227 | 0.8358 | 0.8323 | 0.8454 |
| person_04 | 78 | 0.6505 | 0.7808 | 0.6571 | 0.7771 |
| person_05 | 55 | 0.8526 | 0.6846 | 0.9057 | 0.7363 |
| person_06 | 67 | 0.7152 | 0.7429 | 0.7317 | 0.7353 |
| person_07 | 55 | 0.7353 | 0.7787 | 0.7502 | 0.7702 |

Weighted normal выиграл у euclid на 5/7 людях, средний ΔAUC 0.0154, худший -0.1163. Normal: 5/7, средний ΔAUC 0.0001. Weighted euclid: 6/7, средний ΔAUC 0.0216, худший -0.0036. Провал weighted normal на двух людях наследуется от normal, а не от весов: weighted euclid на тех же людях остаётся выше baseline.

## Leave-one-transition-out

| семейство | within пар | within μ euclid | within μ normal | within μ weighted | Δ within (веса) | Δ within (метрика) | AUC euclid | AUC normal | AUC weighted |
|---|---|---|---|---|---|---|---|---|---|
| frontal_light | 7 | 0.03136 | 0.01194 | 0.01095 | -8.3% | -61.9% | 0.7845 | 0.8757 | 0.881 |
| light_mid | 15 | 0.04057 | 0.01791 | 0.01637 | -8.6% | -55.9% | 0.837 | 0.8316 | 0.8335 |
| mid_deep | 14 | 0.04547 | 0.02105 | 0.01865 | -11.4% | -53.7% | 0.7514 | 0.7922 | 0.8038 |
| deep_profile | 45 | 0.05006 | 0.02212 | 0.01941 | -12.3% | -55.8% | 0.7969 | 0.8303 | 0.8355 |

Weighted normal выиграл на 3/4 отложенных семействах, средний ΔAUC 0.046. Δ within в колонке «веса» сравнен с той же метрикой; «метрика» — переход euclid→normal без весов.

## Стабильность весов

sigma: min 0.012676, p05 0.012677, median 0.024589, p95 0.039997, max 0.039998; clip [0.012676, 0.039998] / normal [0.012914, 0.047833]. На нижней границе 5.0% вершин, на верхней 5.0%.

Профиль хранит по каждой вершине `vertex_stats`: `weight` (средний confidence = 1/clip(sigma), 25.0012…78.8862), `weight_mean` по среднему семейству, `sigma_std`, `sigma_min`, `sigma_max`, `source` (семейство с минимальной sigma) и `n_pairs`. Нулевых весов нет: диапазон ограничен clip.

| зона | вершин | sigma μ | weight μ | на границе снизу | на границе сверху | AUC euclid | AUC normal | AUC weighted normal | Δ within normal→wn |
|---|---|---|---|---|---|---|---|---|---|
| jaw | 17 | 0.039029 | 25.6798 | 0.0% | 70.6% | 0.6919 | 0.6943 | 0.6948 | -0.7% |
| brows | 10 | 0.019599 | 51.2036 | 0.0% | 0.0% | 0.8485 | 0.6961 | 0.701 | -3.6% |
| nose | 9 | 0.024353 | 42.5978 | 0.0% | 0.0% | 0.6178 | 0.6748 | 0.6889 | -7.4% |
| eyes | 12 | 0.013063 | 76.9017 | 75.0% | 0.0% | 0.608 | 0.5518 | 0.5552 | -5.0% |
| mouth | 20 | 0.033464 | 30.0516 | 0.0% | 0.0% | 0.6746 | 0.6509 | 0.6638 | -7.9% |

По семействам переходов: разброс sigma по вершинам 0.216 (p95 0.355), нестабильных вершин 0.0%. Источник минимума: {'light_mid': 44.4, 'mid_deep': 50.0, 'deep_profile': 1.2, 'same_depth': 4.4}. Отношение weights к глобальным: {'light_mid': 1.569, 'mid_deep': 1.528, 'deep_profile': 1.12, 'same_depth': 1.014}.

Наблюдений по семействам: {'light_mid': 14, 'mid_deep': 15, 'deep_profile': 33, 'same_depth': 89}. Профиль глобальный: отдельные ячейки person × pose_bin не строятся.

## Проверки перед включением

| проверка | значение | гейт |
|---|---|---|
| cross-bin within (веса) ≤ −10% | -13.4% | да |
| AUC не хуже baseline | 0.7527 → 0.8006 | да |
| bootstrap CI ΔAUC > 0 | +0.0479 | да |
| LOPO все люди | 5/7 | нет |
| LOTRO большинство | 3/4 | да |
| фронтальные пары | n=1 (нужно ≥10), -59.3% | нет |
| нет равномерной заливки | >vmax 0.0% | да |
| invalid_pose не в парах | утечек 0 | да |

## Preview / export

Единый helper `server.heat.compute_heat_values`: max|preview − export| = 0.00e+00 до colorize, допуск 1e-6 — пройден. Проверено режимов: 24.

HTTP-смоук на живых эндпоинтах: `/api/photos/{id}/heat` — 200, count 35709, vmax 4.0; `/api/photos/{id}/preview` — 200, PNG есть. `configs/runtime.yaml` по умолчанию: euclid + none.

Режим включается только конфигом: без параметров `metric`/`weighting` эндпоинт отдаёт euclid/none, после правки `configs/runtime.yaml` — normal/calibrated (vmax 4.0), после возврата — снова baseline. Интерфейс получает этот же блок через `/api/runtime` при загрузке.

Примеры карты из `GET /api/photos/{id}/preview` (4 режима и общая панель `v3-preview-modes.png`): `v3-preview-euclid.png`, `v3-preview-normal.png`, `v3-preview-weighted_euclid.png`, `v3-preview-weighted_normal.png`.

## 10-кадровая цепочка

Сегментов 9, join jump 0.00e+00, heat join 0.00e+00, максимальный скачок цвета на стыке 0.00e+00; цветовая непрерывность в норме.

Полный маршрут и отдельные сегменты дают одинаковые значения: да.

## Что включать

По умолчанию остаётся `euclid` + `none` (`configs/runtime.yaml`). Переключение режима — только в конфиге, без правки кода:

```yaml
heatmap:
  metric: normal          # или euclid
  weighting: calibrated   # или none
  calibration_profile: reports/calibration/weights.json
```

| режим | LOPO | что показывает | рекомендация |
|---|---|---|---|
| euclid / none | — | baseline, единицы IOD | оставить default |
| normal / none | 5/7 | AUC +0.025, CI накрывает 0 | не включать как default |
| euclid / calibrated | 6/7, худший −0.004 | стабильное снижение шума | первый кандидат на включение |
| normal / calibrated | 5/7, худший −0.116 | лучший AUC 0.8006, но наследует провал normal | только отчёты |

Веса сами по себе устойчивы: `euclid + calibrated` выигрывает на 6/7 людях и нигде не опускается ниже baseline больше чем на 0.004. Нестабильность приходит от метрики normal на двух людях (person_02, person_05), поэтому production-включение связки `normal + calibrated` без расширения корпуса не обосновано.

## Файлы

- `reports/calibration/v3-modes.png` — Четыре режима на одной паре: euclid · normal · weighted euclid · weighted normal
- `reports/calibration/v3-weights.png` — sigma euclid и sigma normal после clip (p05…p95)
- `reports/calibration/v3-lopo.png` — LOPO по людям
- `reports/calibration/v3-lotro.png` — LOTRO по семействам переходов
- `reports/calibration/v3-regions.png` — Изменение within по зонам лица
- `reports/calibration/v3-chain.png` — карта на четырёх сегментах цепочки
- `reports/calibration/v3-preview-euclid.png` — preview-эндпоинт, euclid
- `reports/calibration/v3-preview-modes.png` — preview-эндпоинт, modes
- `reports/calibration/v3-preview-normal.png` — preview-эндпоинт, normal
- `reports/calibration/v3-preview-weighted_euclid.png` — preview-эндпоинт, weighted_euclid
- `reports/calibration/v3-preview-weighted_normal.png` — preview-эндпоинт, weighted_normal
- `reports/calibration/v3-preview.json` — какая пара кадров на примерах
- `reports/calibration/weights.json` — профиль весов (sigma, sigma_normal, clip, стабильность)
- `reports/calibration/invalid-frames.json` — invalid_pose
- `reports/calibration/v3-parity.json` — preview/export/browser
- `reports/calibration/v3-chain.json` — 10-кадровая цепочка
- `reports/calibration-v3.json` — все числа
- `server/heat.py` — единый helper; `server/app.py`, `server/rendering.py` — его вызовы
- `GET /api/photos/{id}/heat` — base64 float32 start/end для браузера
- `web/src/heat.ts`, `web/src/components/Viewer.tsx`, `web/src/components/CPUPreview.tsx`, `web/src/types.ts`, `web/src/store.ts` — браузер берёт значения с backend
- `configs/runtime.yaml` — блок `heatmap` (по умолчанию `euclid` / `none`)
- `scripts/calibration_v3.py` — harness; `scripts/heat_parity.py`, `scripts/heat_chain.py`, `scripts/heat_previews.py` — паритет, стыки, PNG-примеры

## Ограничения

Корпус — 7 человек и 210 кадров; расширить его в этой итерации не удалось: индекс `all_calibration_index.csv` содержит только эти семь записей, дополнительные каталоги person_09/10/11 не размечены по позам. Отдельных профилей на person × pose_bin нет: same-bin пар всего 5, поэтому профиль глобальный, а переходы проверяются через LOTRO.

