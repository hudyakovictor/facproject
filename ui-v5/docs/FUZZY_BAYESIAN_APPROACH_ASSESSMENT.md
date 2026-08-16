# Оценка байесовской логико-вероятностной модели нечёткого вывода для DEEPUTIN

**Рассматриваемая работа:** Г. И. Кожомбердиева, «Байесовская логико-вероятностная модель нечеткого вывода», 2019 — [PDF](https://scm.etu.ru/assets/files/2019/scm2019/papers/1/035.pdf).

## 1. Краткий вывод

| Вариант применения | Оценка |
|---|---:|
| Primary engine объективного forensic-вывода | **33/100** |
| Прямой вывод процентов H0/H1/H2 как вероятностей | **20–25/100** |
| Внутренний explainable rule/triage layer без слова «вероятность» | **58/100 как есть** |
| Гипотетический secondary layer после независимой калибровки | **76/100**, но избыточен относительно прямых evidence rules |
| Понятное объяснение уже рассчитанных evidence states без fuzzy-Bayes | **90/100** и предпочтительно |

**Архитектурное решение D-011:** метод статьи не включать в production pipeline — ни как primary evidence, ни как отдельный fuzzy-Bayesian rule-support слой. Даже в ограниченной роли он дублирует существующие evidence states и добавляет субъективные membership functions/weights. Понятные объяснения и review priority строить прямыми детерминированными правилами поверх raw measurements, calibration, FDR, applicability, limitations и human review. Настоящий Bayesian inference рассматривать только как отдельное будущее исследование на labeled hypothesis datasets.

---

## 2. Что предлагает статья

Метод:

1. задаёт входные лингвистические переменные и функции принадлежности;
2. преобразует чёткие значения в степени принадлежности нечётким множествам;
3. интерпретирует степени принадлежности как субъективные вероятности;
4. преобразует правила `И/ИЛИ/НЕ` в вероятностные функции;
5. использует результаты как `P(e|H)`;
6. нормирует их формулой Байеса, обычно с равномерными priors;
7. дефаззифицирует posterior-like distribution в итоговое число.

В статье подход демонстрируется на учебной задаче определения размера чаевых. Сравнения на forensic/biometric datasets, out-of-domain validation, proper scoring rules, calibration curves или error-rate study не приводятся.

---

## 3. Сильные стороны

1. Простая вычислительная реализация.
2. Понятные правила вида `ЕСЛИ → ТО`.
3. Легко показать, какие правила сработали.
4. Можно объединить несколько качественных состояний.
5. Удобно для human-readable categories.
6. Хорошо работает как triage/decision-support interface.
7. Правила можно version/hash/audit.
8. Легко выполнять what-if/sensitivity по thresholds.
9. Не требует большого training set для самого rule engine.
10. Подходит для генерации понятного объяснения уже установленных измерительных статусов.

---

## 4. Главные методологические проблемы

## 4.1. Степень принадлежности не является вероятностью

Статья сама цитирует различие Заде между совместимостью и вероятностью, но затем предлагает трактовать membership как субъективную Bayesian probability. Это допустимо как экспертная мера уверенности, но не превращает число в эмпирически откалиброванную вероятность события.

Следствие для проекта:

```text
membership(H2)=0.74
```

не означает:

```text
вероятность разных людей = 74%
```

Если показать это публике как вероятность, получится ложная точность.

## 4.2. Нельзя получить likelihood без данных соответствующей гипотезы

Для настоящего Bayes posterior нужны распределения:

```text
p(evidence | H0)
p(evidence | H1)
p(evidence | H2)
```

Same-person calibration оценивает часть `H0`-вариативности. Но она сама по себе не оценивает:

- разнообразие разных людей для H2;
- реалистичные маски/накладки/грим/редактирование для H1;
- перенос между историческими и современными источниками.

Без независимых labeled datasets `P(e|H1)` и `P(e|H2)` будут экспертными правилами, а не измеренными likelihoods.

## 4.3. Равномерные priors не являются нейтральностью

Принятие `P(H_i)=1/N` упрощает формулу, но для forensic hypothesis это сильное допущение. Равные priors могут радикально менять posterior и не имеют автоматического эмпирического обоснования.

Если priors неизвестны, правильнее показывать:

- likelihood ratio/Bayes factor;
- posterior в диапазоне priors;
- sensitivity curve;
- либо не публиковать posterior вообще.

## 4.4. Коррелированные метрики будут посчитаны несколько раз

Геометрические признаки лица сильно коррелированы:

- соседние landmarks;
- LDM106 и LDM134;
- mesh и landmark geometry;
- несколько descriptors одной области;
- соседние кадры;
- фотографии одного события/источника.

Операции вида `P(A∧B)=P(A)P(B)` требуют условий независимости, которые здесь обычно не выполняются. Наивное умножение correlated evidence создаст чрезмерную уверенность.

## 4.5. Функции принадлежности и веса легко подогнать

Результат зависит от:

- формы membership functions;
- границ `низкий/средний/высокий`;
- rule weights;
- выбора AND/OR;
- priors;
- defuzzification.

Если эти параметры устанавливаются после просмотра основного результата, возникает circular tuning и confirmation bias.

## 4.6. Итоговое число скрывает конфликт доказательств

Defuzzification сворачивает распределение в одно число. Для журналистского расследования важнее сохранить:

- geometry support;
- texture applicability;
- provenance limitation;
- pose/quality confounders;
- contradictory channels;
- missing data;
- reviewer disagreement.

Один итоговый score создаёт иллюзию завершённости.

## 4.7. Не решаются ключевые статистические задачи проекта

Метод статьи сам по себе не обеспечивает:

- control multiple testing/FDR;
- cluster bootstrap/ESS;
- temporal dependence;
- LOPO;
- contamination sensitivity;
- domain shift;
- confidence intervals;
- calibration reliability;
- negative controls;
- holdout evaluation.

---

## 5. Оценка по 19 факторам

| Фактор | Primary engine | Secondary calibrated layer | Комментарий |
|---|---:|---:|---|
| Теоретическая релевантность | 55 | 75 | Подходит для rule support, слабее для probabilistic forensic inference |
| Эмпирическая валидация статьи | 15 | 65 | В статье только toy example; проект должен валидировать самостоятельно |
| Калибровка вероятностей | 20 | 40 | Membership нельзя называть posterior probability |
| Корреляция evidence | 10 | 55 | Нужны blocks/independence policy, не наивное умножение |
| Неопределённость | 30 | 70 | Можно добавить intervals/sensitivity, но это не часть базового метода |
| Measurement noise | 20 | 80 | Secondary слой может использовать уже откалиброванные Stage 2 states |
| Pose/quality/expression | 15 | 80 | Только если поступают из существующих applicability gates |
| Temporal dependence | 10 | 65 | Rule layer может читать chronology events, но не заменяет rate model |
| Multiple testing | 5 | 60 | FDR должен оставаться до rule layer |
| Calibration transfer | 10 | 65 | Требует holdout/domain tests |
| Интерпретируемость | 85 | 95 | Главная сильная сторона |
| Аудитируемость | 70 | 95 | Rules/memberships/weights можно versioned и раскрывать |
| Sensitivity analysis | 35 | 90 | Легко реализовать what-if grid |
| Устойчивость к ручной подгонке | 20 | 75 | Нужны freeze/holdout/monotonic constraints |
| Воспроизводимость | 65 | 95 | При фиксированных правилах и manifest |
| Вычислительная эффективность | 90 | 90 | Очень дешёвый расчёт |
| Forensic validity | 20 | 60 | Только support/triage, не identity posterior |
| Безопасность публичной коммуникации | 25 | 90 | Хороша при labels «степень поддержки», опасна при labels «вероятность» |
| Совместимость с текущим pipeline | 35 | 90 | После Stage 2 — да; вместо Stage 2 — нет |

---

## 6. Где метод можно использовать

## 6.1. Review priority

Пример:

```text
ЕСЛИ
  pair applicable
  И calibration coverage достаточна
  И geometry state persistent candidate
  И provenance не конфликтует
ТО
  review_priority = high
```

Результат:

```text
Высокий приоритет ручной проверки
```

а не:

```text
Вероятность подмены 87%
```

## 6.2. Понятные категории UI

Из empirically calibrated states:

- within expected variation;
- elevated but uncertain;
- persistent candidate;
- limited by quality;
- insufficient calibration;
- contradictory evidence;
- requires source review.

## 6.3. Генерация объяснений

Rule engine может создавать тезис:

> Карточка поднята в очереди проверки, потому что геометрическое изменение повторяется в соседних датах, при этом пара прошла pose gate. Сила формулировки ограничена неполной калибровкой правого профиля.

## 6.4. Sensitivity laboratory

Показывать:

- какие rules fired;
- membership ranges;
- изменение результата при допустимом смещении thresholds;
- stability region;
- fragile/invariant conclusion.

## 6.5. Publication glossary

Использовать для перевода technical states на понятный язык, сохраняя рядом raw metric, calibration и evidence ref.

---

## 7. Где метод применять нельзя

1. Финальная вероятность H0/H1/H2.
2. Вероятность «один/разные люди» без labeled benchmark.
3. Вероятность маски/синтетического материала без representative labeled dataset.
4. Замена empirical calibration.
5. Замена FDR.
6. Замена clustering stability.
7. Автоматический public verdict.
8. Формирование priors из публикаций, слухов или private hypotheses.
9. Умножение всех geometry/texture metrics как независимых.
10. Настройка membership functions на основном архиве после просмотра событий.

---

## 8. Безопасная архитектура интеграции

```text
Stage 1 measurements
        ↓
Stage 2 applicability + calibration + FDR + evidence states
        ↓
Rule-support layer (optional, internal)
        ↓
review priority + explanation + sensitivity
        ↓
human review/adjudication
        ↓
Stage 3 claim with evidence refs and limitations
```

Rule layer не меняет:

- raw metric;
- evidence state;
- FDR;
- calibration;
- reportable gate;
- private/public boundary.

## Рекомендуемые названия

Использовать:

- `rule_support`;
- `compatibility_degree`;
- `review_priority`;
- `explanation_state`;
- `linguistic_summary`.

Не использовать:

- `posterior_probability`;
- `identity_probability`;
- `probability_of_double`;
- `confidence_person_is_different`.

---

## 9. Требования к membership functions

1. Строятся из independent calibration/holdout, а не на глаз.
2. Versioned per metric/pose/quality stratum.
3. Monotonic там, где это методологически ожидается.
4. Missing data имеет отдельное состояние, не membership 0.
5. Limited applicability блокирует усиление результата.
6. Каждая функция публикует:
   - unit;
   - low/high knots;
   - source sample;
   - effective N;
   - uncertainty;
   - release version.
7. Проводится sensitivity grid.
8. Rule weights freeze до main-run review.
9. Любая ручная правка создаёт новый profile/version.
10. Holdout проверяет stability и false-positive pressure.

---

## 10. Что требуется для настоящего Bayesian inference

Если проекту в будущем нужен именно posterior, необходим другой уровень валидации:

1. независимый same-person dataset;
2. независимый different-person dataset с pose/quality matching;
3. representative synthetic-material/manipulation dataset для соответствующей гипотезы;
4. subject/source-disjoint train/calibration/test split;
5. multivariate dependence model;
6. hierarchical effects person/capture/source/pose/era;
7. likelihood ratios/Bayes factors;
8. explicit prior ranges;
9. posterior sensitivity to priors;
10. reliability plots;
11. Brier score/log loss;
12. posterior predictive checks;
13. external validation;
14. documented abstention region;
15. independent methodological review.

Пока этих данных нет, объективнее публиковать calibrated evidence states, likelihood-like summaries и ограничения, а не posterior percentages.

---

## 11. Итоговое решение

**Итоговое решение: не использовать этот подход в production DEEPUTIN.**

Его сильная сторона — понятные правила — уже достигается более простым и проверяемым способом:

```text
versioned evidence state + explicit limitations + deterministic explanation rule
```

Без преобразования membership в псевдовероятность, без равномерных priors и без дополнительной дефаззификации. Такой прямой слой проще тестировать, объяснять, версионировать и защищать перед техническими рецензентами.

Для review priority использовать обычную таблицу прозрачных правил над уже откалиброванными состояниями. Для будущего настоящего Bayesian inference нужен отдельный labeled benchmark и полноценная валидация likelihoods/priors/dependence. Добавление fuzzy-Bayesian слоя сейчас увеличит сложность и поверхность критики, но не добавит новых измерительных данных.
