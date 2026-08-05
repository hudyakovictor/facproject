# DEEPUTIN — roadmap узкоспециализированных методов

## 1. Итоговая рекомендация

Не добавлять десятки методов ради количества. Максимальную пользу дадут методы, которые отвечают на самые уязвимые вопросы проекта:

1. насколько стабильно сама система реконструирует одно и то же фото;
2. какая часть различия объясняется камерой, ракурсом, качеством и событием съёмки;
3. находится ли новая фотография внутри области калибровочной применимости;
4. сохраняется ли сигнал при альтернативных статистических методах;
5. не возник ли он из-за множественных проверок или корреляции кадров;
6. может ли независимый examiner воспроизвести наблюдение.

## 2. Приоритеты

| Метод | Польза | Приоритет | Решение |
|---|---:|---|---|
| Measurement System Analysis + perturbation bootstrap | 98/100 | P0 | внедрить |
| Negative controls + degradation stress tests | 98/100 | P0 | внедрить |
| Camera/perspective sensitivity simulation | 97/100 | P0 | внедрить |
| Hierarchical mixed-effects / variance components | 97/100 | P0 | внедрить |
| Event/source block bootstrap + ESS | 96/100 | P0 | внедрить |
| Applicability domain / OOD detection | 95/100 | P0 | внедрить |
| ACE-V-style morphological review + inter-rater reliability | 95/100 | P0 | внедрить как human corroboration |
| Hierarchical FDR / permutation max-statistic | 94/100 | P1 | внедрить |
| Change-point ensemble | 94/100 | P1 | внедрить |
| Recurrence plots / recurrence quantification | 93/100 | P1 | внедрить |
| Robust multivariate covariance scoring | 92/100 | P1 | внедрить |
| 3D surface differential descriptors | 87/100 | P1 | экспериментально |
| Score-based likelihood ratios | 88/100 при наличии данных | P2 | отдельное валидируемое исследование |
| Longitudinal aging GAM/GP | 85/100 при наличии cohort | P2 | отдельное исследование |
| Conformal abstention/prediction sets | 82/100 | P2 | после OOD/domain validation |
| Face embeddings | 78/100 | P2 | retrieval/secondary channel only |
| Image manipulation forensics | 72/100 | P2 | provenance/authentication only |

---

# 3. P0 — внедрить в первую очередь

## 3.1. Measurement System Analysis (MSA), Gage R&R и perturbation bootstrap

### Зачем

Главный неотвеченный вопрос: насколько результат меняется не из-за лица, а из-за detector/crop/reconstruction pipeline.

### Реализация

Для каждого calibration/test photo выполнить controlled repeats:

- сдвиг bounding box ±1–5%;
- изменение crop margin;
- downscale/upscale без super-resolution;
- JPEG recompression;
- небольшие brightness/gamma perturbations;
- landmark/camera perturbations в пределах measured uncertainty;
- два backbone/model release при наличии;
- повторный decode/orientation path.

Для каждого photo/point/zone получить:

- repeatability SD;
- reproducibility SD;
- per-point covariance;
- ICC;
- coefficient of variation, где применимо;
- limit of detection;
- failure probability;
- sensitivity curve.

### Артефакты

```text
reconstruction_repeatability.json
reconstruction_repeatability.npz
point_uncertainty_by_pose.npz
measurement_system_report.json
```

### Использование

- Stage 1 quality/applicability;
- pair uncertainty interval;
- calibration noise decomposition;
- UI uncertainty bands;
- исключение нестабильных points/zones.

### Почему это важнее нового score

Метод не пытается угадать идентичность. Он измеряет надёжность самого измерительного инструмента — именно это первым спросит технический рецензент.

---

## 3.2. Negative controls, hard negatives и degradation stress tests

### Наборы

- одно фото, повторно сохранённое;
- соседние кадры одного события;
- один человек при близкой позе;
- один человек при граничной позе;
- разные люди при максимально похожих pose/quality;
- look-alike hard negatives;
- controlled A-B-A scenarios;
- blur/JPEG/downscale/exposure/occlusion series.

### Проверки

- false positive rate;
- false negative rate;
- stability of candidate status;
- threshold sensitivity;
- rank stability;
- calibration transfer;
- point/zone failure map;
- source-domain effect.

### Обязательное правило

Любое улучшение метода должно одновременно показать:

```text
что стало лучше на целевом сценарии
и что не стало хуже на negative controls
```

### Важное ограничение

Super-resolution не использовать как evidence preprocessing. Исследование LR для realistic surveillance scenarios показало ухудшение Cllr после CodeFormer, несмотря на визуальное «улучшение» изображения [источник: https://pubmed.ncbi.nlm.nih.gov/38487302/].

---

## 3.3. Camera/perspective/lens sensitivity simulation

### Проблема

Даже при одинаковом лице относительные пропорции 2D/реконструированной геометрии меняются из-за:

- focal length;
- camera-to-subject distance;
- viewpoint;
- pitch/yaw/roll;
- lens distortion;
- crop;
- aspect ratio.

FISWG запрещает photo-anthropometry как самостоятельный facial comparison method и разрешает superimposition только как дополнение к morphological analysis при сопоставимом viewpoint [источник: https://fiswg.org/fiswg_facial_comparison_overview_and_methodology_guidelines_V1.0_20191025.pdf].

### Реализация

Использовать сохранённую 3D-модель одного calibration face:

1. задать сетку camera parameters;
2. синтетически проецировать одну и ту же форму;
3. пропустить через тот же measurement path;
4. измерить leakage каждой metric;
5. построить per-pose sensitivity surface;
6. определить safe/limited regions.

### Артефакты

```text
camera_sensitivity_grid.npz
pose_metric_leakage.json
metric_safe_domain.json
```

### Результат

Вместо утверждения «мы выровняли ракурс» публиковать измеренный ответ:

> При изменении yaw на X°, pitch на Y° и focal scenario Z эта метрика менялась в пределах …; рассматриваемая пара находится внутри/вне проверенного диапазона.

---

## 3.4. Hierarchical mixed-effects model / variance components

### Зачем

Тысячи pair rows не являются тысячами независимых наблюдений. Вариация имеет уровни:

- person;
- capture event;
- source/video;
- photo;
- pose;
- quality;
- date/era;
- point/zone;
- algorithm/model release.

### Модель

Для metric residual:

```text
residual ~ pose + quality + age_gap + source_domain
         + (1 | person)
         + (1 | capture_event)
         + (1 | source)
         + (1 | photo)
```

Возможны random slopes по pose/quality при достаточном N.

### Выходы

- variance components;
- intraclass correlation;
- adjusted uncertainty;
- person/event/source effective units;
- conditional residuals;
- prediction interval;
- unsupported strata.

### Польза

- устраняет pseudo-replication;
- показывает, где источник/событие доминирует над предполагаемым shape signal;
- даёт технически сильное объяснение calibration.

---

## 3.5. Cluster/block bootstrap, permutation и Effective Sample Size

### Единица resampling

Не отдельная pair row, а:

- person;
- person-pair;
- capture event;
- source cluster;
- временной block.

### Методы

- cluster bootstrap;
- moving/block bootstrap;
- leave-one-source-out;
- leave-one-event-out;
- permutation внутри допустимых pose/quality strata;
- effective sample size.

### Отчёт

Показывать одновременно:

```text
raw pair count
unique photos
unique capture events
unique sources
effective N
bootstrap CI
```

### Release gate

Если вывод исчезает при исключении одного source/event, он не может называться устойчивым.

---

## 3.6. Applicability Domain / Out-of-Distribution detection

### Вопрос

Похожа ли анализируемая фотография по pose/quality/source conditions на данные, по которым калибровалась система?

### Методы

- robust Mahalanobis distance в quality/pose feature space;
- k-nearest calibration coverage;
- density ratio;
- one-class model на calibration conditions;
- per-pose convex hull/ellipsoid;
- source-domain embedding distance;
- later: Mondrian conformal calibration по pose/quality strata.

### Выход

```text
inside_calibration_domain
near_boundary
out_of_domain
not_measurable
```

### Правило

Out-of-domain фотография не получает усиленный candidate status, даже если raw residual велик.

### UI

- domain coverage badge;
- nearest calibration frames;
- distance to support boundary;
- reason OOD;
- expected additional data.

---

## 3.7. ACE-V-style morphological review и FISWG feature taxonomy

### Почему нужно

FISWG рекомендует систематический feature-by-feature morphological analysis и прямо запрещает photo-anthropometry для facial comparison [источник: https://fiswg.org/fiswg_facial_comparison_overview_and_methodology_guidelines_V1.0_20191025.pdf]. Современный обзор также описывает morphological analysis с ACE-V как основной manual forensic workflow, при этом подчёркивает зависимость от качества и условий изображения [источник: https://www.mdpi.com/2079-7737/10/12/1269].

### Роль в проекте

Не заменяет автоматический Stage 2 и не «подтверждает» его автоматически. Это независимый human corroboration channel.

### Этапы

1. **Analysis:** качество каждого изображения, visible features, limitations.
2. **Comparison:** систематическое feature-by-feature comparison.
3. **Evaluation:** observation-based support/limited/inconclusive.
4. **Verification:** второй независимый reviewer.

### Feature checklist

Только разрешённая область проекта:

- forehead/brow region;
- orbital/periocular morphology;
- nasal root/bridge/tip/alae;
- zygomatic/cheek contour;
- philtrum/lips с expression limitation;
- chin/jaw contour;
- scars/marks только при достаточном качестве;
- overall composition.

Уши/шея исключаются, если это принято scope проекта.

### Inter-rater statistics

- Cohen/weighted kappa;
- Gwet AC1 при сильном imbalance;
- ICC для continuous ratings;
- disagreement rate;
- adjudication rate;
- examiner-specific calibration.

### UI

Отдельный blind review checklist; auto metrics скрыты до фиксации observation.

---

# 4. P1 — высокая дополнительная ценность

## 4.1. Robust multivariate scoring с учётом корреляции

### Вместо

- ручного суммирования десятков z;
- независимого умножения channels;
- arbitrary weights.

### Использовать

- shrinkage covariance (Ledoit–Wolf);
- robust Minimum Covariance Determinant;
- robust Mahalanobis distance;
- PCA/whitening только на calibration split;
- sparse/regularized discriminant diagnostics;
- per-pose/per-quality models.

### Требования

- nested cross-validation;
- holdout person/source;
- covariance uncertainty;
- condition number;
- no double counting LDM/mesh/descriptors;
- output remains evidence score, not identity probability.

---

## 4.2. Hierarchical FDR и permutation max-statistic

### Проблема

Сейчас проверяются:

- pairs;
- points;
- zones;
- descriptors;
- poses;
- chronology events.

Один плоский BH может быть либо слишком мягким, либо слишком консервативным.

### Схема

```text
family/pose gate
  → pair gate
    → point/zone gate
```

Методы:

- hierarchical BH;
- grouped FDR;
- Benjamini–Bogomolov selective inference;
- Westfall–Young maxT/block permutation для correlated features;
- report number of tested/selected families.

### UI

Показывать raw p, q, family q, selected family и calibrated point count.

---

## 4.3. Ensemble change-point detection

Не полагаться на один detector.

### Методы

- PELT;
- robust Wild Binary Segmentation;
- kernel change-point;
- energy-distance/nonparametric change-point;
- CUSUM/MEWMA;
- existing persistence/rate logic.

Robust nonparametric multivariate change-point methods с PELT/WBS полезны при heavy tails и outliers [источник: https://www.sciencedirect.com/science/article/abs/pii/S2452306223000734].

### Consensus

Boundary получает:

- methods supporting;
- date interval, не ложную точную дату;
- block-bootstrap stability;
- pose/source support;
- sensitivity to penalty/window;
- review state.

### Статус

```text
single_method_signal
multi_method_candidate
stable_consensus_boundary
unstable_boundary
```

---

## 4.4. Recurrence Plot / Recurrence Quantification Analysis

### Почему особенно полезно

Проект ищет:

- A→B→A;
- повторное возвращение к прежней форме;
- чередование состояний;
- циклические clusters.

### Реализация

1. построить calibrated pairwise distance matrix внутри pose bin;
2. threshold взять из same-person null;
3. построить recurrence matrix;
4. искать diagonal/vertical structures;
5. объединить с chronology и source blocks.

### Метрики

- recurrence rate;
- determinism;
- laminarity;
- recurrence time;
- return strength;
- alternation frequency;
- baseline fan/anchor.

### UI

- recurrence plot;
- click cell → Pair Analysis;
- selected timeline period;
- threshold sensitivity;
- no identity label.

---

## 4.5. Statistical Process Control: Hotelling T², MEWMA, robust CUSUM

### Роль

Обнаруживать небольшие согласованные сдвиги нескольких correlated metrics, которые по отдельности ниже threshold.

### Применение

- calibration establishes in-control state;
- quality/pose matched strata;
- MEWMA for gradual drift;
- Hotelling T² for multivariate excursions;
- robust CUSUM for heavy tails;
- block-calibrated control limits.

### Ограничение

Процесс старения не стационарен. Нельзя использовать постоянную baseline без age/trend adjustment.

---

## 4.6. 3D surface differential geometry

Secondary channels:

- signed normal displacement;
- point-to-plane residual;
- mean/Gaussian curvature;
- shape index;
- curvedness;
- geodesic distances;
- local surface area/volume;
- thin-plate spline bending energy;
- symmetry relative to estimated midsagittal plane.

### Правила

- rigid alignment first;
- non-rigid warp не должен поглотить искомое различие;
- per-zone visibility;
- same-person calibration;
- correlated channels grouped;
- no direct statement «измерена кость» по monocular reconstruction.

---

# 5. P2 — только после дополнительных datasets

## 5.1. Score-Based Likelihood Ratio (SLR)

### Почему это сильнее fuzzy Bayes

LR отвечает не «какова вероятность гипотезы», а:

```text
насколько наблюдаемый score вероятнее при same-source,
чем при different-source
```

Исследования automated face comparison используют same/different score distributions, calibration и Cllr; качество и pose matching существенно влияют на результат [источник: https://www.sciencedirect.com/science/article/abs/pii/S037907382200069X]. LR framework требует representative same-source/different-source data и validation; сам similarity score не является LR [источник: https://pmc.ncbi.nlm.nih.gov/articles/PMC7383913/].

### Необходимые данные

- many identities;
- same-source pairs;
- different-source pairs;
- pose/quality/source matching;
- person/source-disjoint split;
- independent external test;
- enough tail observations.

### Calibration/validation

- logistic regression calibration;
- KDE only with bandwidth/tail control;
- PAV for diagnostics, not naive production overfit;
- Cllr/Cllrmin;
- Tippett plots;
- ECE plots;
- misleading evidence rates;
- ELUB/shrinkage extreme LR;
- prior sensitivity only for posterior odds, not LR itself.

### Scope

- сначала geometry H0 vs H2;
- H1 synthetic/material отдельно и только при representative dataset;
- experimental/internal до external validation.

---

## 5.2. Longitudinal aging corridor: GAM/GP/mixed effects

### Метод

- Generalized Additive Mixed Model;
- Gaussian Process trajectory;
- functional data analysis;
- age-varying coefficient model;
- separate stable/soft-tissue components.

3D aging studies используют geometric morphometrics на реальных 3D scans; например, исследование 88 лиц применяло 585 landmarks/semilandmarks и моделировало sex-specific aging trajectories [источник: https://pubmed.ncbi.nlm.nih.gov/31189026/]. Это подчёркивает необходимость отдельного normative 3D cohort, а не вывода нормы из исследуемой последовательности.

### Требования

- male longitudinal/reference cohort соответствующего возраста;
- real 3D scans желательно;
- body weight/health/source covariates;
- age interval coverage;
- external validation;
- prediction intervals;
- no medical diagnosis.

### Выход

```text
inside normative corridor
outside corridor but quality limited
outside validated age domain
persistent residual candidate
```

Не использовать формулировку «биологически невозможно» без validated bound.

---

## 5.3. Conformal prediction / selective abstention

### Польза

- prediction set вместо одного label;
- controlled marginal coverage при exchangeability;
- abstain на трудных кадрах;
- Mondrian conformal по pose/quality strata;
- risk-control selection.

Conformal prediction исследовался для face recognition как способ выдавать prediction sets и calibrated confidence при условии exchangeability [источник: https://link.springer.com/article/10.1007/s10994-018-5756-7].

### Ограничение

Исторические фото и современные digital images не exchangeable. До domain-shift validation conformal guarantee нельзя переносить автоматически.

### Правильный output

```text
compatible evidence states = {within_noise, inconclusive}
abstain = true
```

а не identity probability.

---

## 5.4. Face embeddings как secondary retrieval channel

Варианты:

- ArcFace;
- AdaFace;
- QMagFace/MagFace;
- quality-aware embedding.

Использование:

- nearest-neighbor retrieval;
- hard-negative discovery;
- pair prioritization;
- independent score for future SLR.

Не использовать:

- как final verdict;
- без domain/age/pose evaluation;
- без threshold calibration;
- для fusion с geometry как независимого evidence без correlation study.

---

## 5.5. Image manipulation/provenance forensics

Методы:

- JPEG quantization/grid analysis;
- double compression;
- CFA/demosaicing consistency;
- PRNU при доступных originals;
- Noiseprint-like source residual;
- copy-move/splice detection;
- metadata/container consistency.

Роль:

```text
image/source manipulation diagnostic
```

Не роль:

```text
наличие силиконового материала
или идентичность человека
```

Сильная recompression/social-media processing может уничтожать signal; нужен abstention.

---

# 6. ISO/FISWG/ENFSI alignment

## FISWG

- systematic morphological feature comparison;
- photoanthropometry не использовать для facial comparison;
- superimposition только как вспомогательный инструмент;
- quality/viewpoint limitations обязательны.

## ISO/IEC 29794-5:2025

Стандарт описывает single-image face quality и прямо не устанавливает требования к сравнению пар/последовательностей; его quality components полезны как gates/covariates, но не являются evidence score [источник: https://www.iso.org/standard/81005.html].

## ENFSI-style evaluative reporting

- strength of evidence, не categorical identity claim;
- LR только после representative validation;
- examiner oversight;
- proficiency/black-box tests;
- limitations and alternatives.

---

# 7. Методы, которые не стоит добавлять

1. Fuzzy-Bayesian posterior H0/H1/H2.
2. Dempster–Shafer fusion без independent mass calibration.
3. Наивное перемножение geometry/mesh/embedding/texture scores.
4. Один universal identity score.
5. 2D photoanthropometry как доказательство.
6. Superimposition при несопоставимом viewpoint.
7. Generic deepfake detector как material detector.
8. Super-resolution перед evidence measurement.
9. Unsupervised cluster → имя/личность.
10. HMM states → «люди» без labels/validation.
11. Aging GAN как нормативная модель старения.
12. Ручные веса, настроенные после просмотра timeline.
13. Порог «биологически невозможно» без longitudinal reference cohort.
14. Black-box model без reproducibility/holdout.
15. Большое число новых correlated metrics без hierarchical testing.

---

# 8. Оптимальный порядок реализации

## Пакет A — максимальная отдача

1. MSA/perturbation bootstrap.
2. Degradation/negative-control harness.
3. Camera/pose sensitivity grid.
4. Mixed-effects variance components.
5. Block bootstrap/ESS.
6. OOD/applicability domain.
7. ACE-V blind morphological review + inter-rater stats.

## Пакет B — хронология

8. Robust multivariate score.
9. Hierarchical FDR/permutation.
10. Change-point ensemble.
11. Recurrence analysis.
12. MEWMA/robust CUSUM.

## Пакет C — после новых данных

13. SLR H0 vs H2 experimental study.
14. Normative aging GAM/GP.
15. Conformal abstention.
16. Embedding retrieval/hard negatives.
17. Image-authentication diagnostics.

---

# 9. Новые UI-разделы/виджеты

## Measurement Reliability

- repeatability per photo/point/zone;
- perturbation preview;
- ICC/LOD;
- unstable regions;
- model/backbone disagreement.

## Applicability Domain

- inside/boundary/OOD;
- nearest calibration samples;
- pose/quality/source support;
- requested missing data.

## Method Consensus

- detectors supporting change boundary;
- stability interval;
- block-bootstrap frequency;
- sensitivity matrix.

## Recurrence Matrix

- date × date heatmap;
- return/alternation markers;
- click → Pair Analysis;
- threshold sensitivity.

## Morphological Review

- ACE-V phases;
- blind feature checklist;
- second reviewer;
- kappa/AC1/ICC;
- disagreement/adjudication.

## Experimental LR Lab

Только при готовых datasets:

- same/different distributions;
- Cllr/Cllrmin;
- Tippett/ECE/DET;
- misleading evidence;
- tail bounds;
- calibration/holdout/domain breakdown;
- `experimental—not public`.

---

# 10. Итог

Наиболее сильное улучшение проекта — не ещё один identity classifier, а **измерение неопределённости, области применимости и устойчивости вывода**.

Первые семь методов должны сделать возможным ответ на вопрос технического скептика:

> Если взять то же фото, немного изменить crop/качество/камеру, исключить один источник, другой pose bin или одну calibration person — останется ли наблюдение?

Только сигнал, переживший эти проверки и независимый human review, имеет смысл поднимать в публикационный claims ledger.
