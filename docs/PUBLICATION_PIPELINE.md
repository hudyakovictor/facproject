# DEEPUTIN — публикационный pipeline для четырёх аудиторий

Текущая 25-факторная оценка реализации: [`PUBLICATION_PIPELINE_25_FACTOR_REVIEW.md`](PUBLICATION_PIPELINE_25_FACTOR_REVIEW.md).

Пример plain-language статьи о специализированных методах: [`examples/METHODS_ARTICLE_PUBLIC_DRAFT_RU.md`](examples/METHODS_ARTICLE_PUBLIC_DRAFT_RU.md).

## 1. Цель

Результат анализа должен быть проверяем одновременно четырьмя аудиториями:

1. **широкая аудитория** — понимает ход анализа без знания computer vision;
2. **технические специалисты** — видят coordinate spaces, gates, calibration, статистику, версии и воспроизводимость;
3. **скептические рецензенты** — получают сильнейшие альтернативные объяснения и условия, при которых тезис должен быть ослаблен или отозван;
4. **AI/machine reviewers** — получают структурированный claims ledger, evidence pointers, assumptions и challenge register.

Задача не в риторическом убеждении любой ценой. Доверие достигается прозрачностью, воспроизводимостью, разделением наблюдения и интерпретации, демонстрацией отрицательных контролей и возможностью опровергнуть тезис.

## 2. Проверка текущей реализации

До добавления publication drafts Stage 3 создавал:

- `report_data.json`;
- один HTML-отчёт;
- шесть коротких narrative bullets;
- timeline/motion maps;
- pair/change tables;
- provenance counters;
- public-safety boundary.

### Что было сильным

- Stage 3 принимал только валидированный Stage 2;
- reportable change gate;
- `measurement_status` и `evidence_state` разделялись;
- provenance, calibration count и limitations сохранялись;
- HTML напоминал, что результат не является verdict;
- JSON оставался source of truth.

### Чего не хватало

- полноценного объяснения метода простым языком;
- технического appendix с claim-to-artifact trace;
- отдельного документа для скептической проверки;
- machine-readable claims ledger;
- редакционного черновика результата;
- protocol для независимых демонстрационных примеров;
- denominator/coverage рядом с каждой публичной цифрой;
- явных условий falsification/withdrawal;
- синхронизации общего и технического текста;
- human review state на каждом потенциально сильном тезисе.

Шесть hardcoded bullets недостаточны для публикации уровня крупного международного СМИ.

## 3. Новый поток Stage 2 → Stage 3

```text
Stage 2 measurements
      ↓
journalist_handoff.json
      ↓
Stage 3 report_data + validated public projection
      ↓
drafts/publication_bundle.json
      ├── plain-language method draft
      ├── technical appendix
      ├── result story draft
      ├── skeptic Q&A
      ├── independent demonstration protocol
      ├── claims ledger
      └── machine review packet
```

Все файлы детерминированы, не требуют LLM и не добавляют измерения. LLM или журналист может редактировать текст позже, но не имеет права усиливать `candidate` без нового evidence/review record.

## 4. Stage 2 handoff

`journalist_handoff.json` содержит:

- pair/adjacent/candidate counts;
- limited counts с явным знаменателем;
- candidate cards;
- photo/pair/date/pose/status;
- calibrated point count и calibration coverage;
- альтернативные объяснения;
- ссылки на `pair_metrics.csv`, `change_points.json`, `evidence_packets.json`;
- editorial rules;
- `draft=true`, `not_a_verdict=true`, `human_review_required=true`.

Это не статья. Это структурированный диалог технического специалиста с журналистом.

## 5. Stage 3 draft package

Stage 3 создаёт `drafts/`:

| Файл | Аудитория/роль |
|---|---|
| `README.md` | порядок чтения и review boundary |
| `01_METHOD_EXPLAINER_PUBLIC.md` | широкая аудитория; независим от результата |
| `02_METHOD_TECHNICAL_APPENDIX.md` | CV/statistics/forensic специалисты |
| `03_RESULTS_STORY_DRAFT.md` | журналист + технический редактор |
| `04_SKEPTIC_QA.md` | скептики, reviewers, fact-checkers |
| `05_EXAMPLE_DEMONSTRATION_PROTOCOL.md` | независимая серия понятных примеров |
| `publication_bundle.json` | единый source текстовых слоёв |
| `claims_ledger.json` | claim → evidence → limitation → review |
| `machine_review_packet.json` | AI/static review input |
| `glossary.json` | единые определения |
| `draft_lint.json` | блокирующий assertive-language lint |

Корневой `publication_drafts_manifest.json` фиксирует файлы, размеры, digests, audiences, число claims/candidate cards и lint status.

## 6. Архитектура цикла статей о методе

Этот цикл не зависит от того, какие результаты получены на основном архиве.

### Статья 1. Почему одна фотография не отвечает на вопрос

- различия света, камеры, компрессии, ракурса, мимики;
- почему «процент сходства» без calibration недостаточен;
- примеры reconstruction error.

### Статья 2. Происхождение и датировка

- filename authority;
- EXIF/source claim как corroboration;
- dHash/duplicates;
- source chain;
- почему ошибочная дата разрушает chronology inference.

### Статья 3. Что такое 3D-реконструкция

- параметрическая модель;
- один inference и immutable artifacts;
- raw/object-normalized/identity-only;
- почему это не КТ и не прямое измерение костей.

### Статья 4. Девять ракурсов

- pose bins;
- yaw/pitch/roll gaps;
- visibility intersection;
- profile limitations;
- same-bin policy.

### Статья 5. Калибровка и шум

- same-person dataset;
- person-balanced reference;
- LOPO;
- contamination;
- quality strata;
- matched calibration coverage.

### Статья 6. Мимика и качество

- smile/jaw flags;
- stable vs soft-tissue channels;
- image quality;
- resolution/source domain;
- abstention/limited status.

### Статья 7. Статистика

- pair count ≠ independent N;
- p95;
- FDR;
- uncertainty;
- negative controls;
- sensitivity analysis.

### Статья 8. Хронология

- adjacent/baseline pairs;
- rate;
- persistent change;
- cumulative drift;
- return A→B→A;
- same-day conflict;
- cross-bin/source corroboration.

### Статья 9. Blind review и falsification

- скрытые labels/dates;
- два reviewers;
- adjudication;
- условия ослабления/отзыва тезиса;
- публикация disagreement.

### Статья 10. Воспроизводимость

- schemas/configs;
- code/model/dataset identifiers;
- exclusions;
- artifact index;
- claims ledger;
- machine review packet.

## 7. Примеры на известных людях

Для понятного объяснения допустим отдельный same-person demonstration set из лицензированных публичных фотографий известного человека — например, Дональда Трампа или Илона Маска. Его назначение:

- показать, как алгоритм ведёт себя при разных углах;
- показать влияние качества и компрессии;
- показать smile/jaw confounders;
- показать, что тот же человек может давать ненулевую разницу;
- показать negative control и false-positive pressure.

Ограничения:

1. никаких выводов об идентичности, здоровье или внешних средствах этого человека;
2. отдельный dataset/manifest;
3. не использовать пример для настройки порогов основного исследования;
4. обеспечить права на изображения;
5. заранее зафиксировать ожидаемый результат;
6. публиковать failures так же, как successes.

Лучший первичный демонстрационный набор — данные участника с согласием; известные люди нужны только для узнаваемости примера.

## 8. Структура статьи о результатах

### Голос автора

Основной рассказ ведётся от первого лица журналиста, но роли не смешиваются:

- «мы собрали/проверили источник» — действие редакции;
- «система измерила/пометила» — автоматический результат;
- «технический специалист проверил применимость» — method review;
- «мы интерпретируем» — журналистская гипотеза с явной границей;
- «независимый рецензент согласился/не согласился» — external review.

Формула «мы доказали» запрещена, пока evidence state остаётся candidate/limited/inconclusive.

1. **Вопрос и граница исследования.** Что измерялось и чего метод не может установить.
2. **Архив.** Фото, даты, источники, coverage, exclusions.
3. **Метод в пяти абзацах.** Ссылка на независимый method series.
4. **Качество и calibration.** До результатов, а не в сноске после них.
5. **Общая хронология.** Не начинать с самой красной точки.
6. **Карточки кандидатов.** Фото A/B, дата, pose, measurement, calibration, alternatives, review.
7. **Повторяемость.** Другой ракурс/источник/дата.
8. **Сильнейшие альтернативные объяснения.** Открыто и рядом с находкой.
9. **Что сказали независимые reviewers.** Включая disagreement.
10. **Что результат не доказывает.** Ясно, без юридически двусмысленных формулировок.
11. **Данные для проверки.** Claims ledger, manifests, machine packet, exports.

## 9. Четырёхслойный паттерн каждой важной находки

### Для широкой аудитории

Одно предложение без жаргона: что изменилось и почему это выделено для проверки.

### Для технического специалиста

Coordinate space, pose gaps, common/calibrated points, raw metric, calibration reference, FDR, quality/provenance state.

### Для скептика

Самое сильное альтернативное объяснение и тест, который способен его проверить.

### Для AI/machine review

```json
{
  "claim_id": "RESULT-002",
  "allowed_strength": "candidate_only",
  "evidence_refs": ["change_points.json", "evidence_packets.json"],
  "limitations": [],
  "review_state": "unreviewed_draft"
}
```

## 10. Редакционная безопасность

Простой blacklist слов недостаточен: статья обязана нейтрально называть тему расследования и объяснять проверяемые гипотезы. Поэтому draft lint блокирует не сами слова, а неподдержанные assertive constructions:

- «доказано, что»;
- «анализ доказал»;
- «без сомнений»;
- «точно установлено»;
- «является двойником»;
- «обнаружена маска».

Нейтральный контекст, вопрос, цитата с provenance и явное отрицание допустимы. Финальная публикация всё равно проходит human legal/editorial review.

## 11. Требования к AI-review

Модель получает не только статью, но и `machine_review_packet.json`. Запрос на аудит должен требовать:

1. проверить каждый claim по evidence refs;
2. найти смену meaning между technical и plain text;
3. найти отсутствие знаменателя;
4. найти overclaim;
5. проверить alternative explanations;
6. проверить main-data threshold tuning;
7. проверить pose/quality/calibration coverage;
8. проверить correlation/effective N;
9. перечислить недостающие artifacts;
10. выдать machine-readable список objections.

AI не считается независимым forensic reviewer и не заменяет человека.

## 12. Publication gate

Черновик нельзя публиковать, пока:

- Stage 2/3 validation не complete;
- public-safety/draft lint не pass;
- provenance conflicts не разобраны или явно раскрыты;
- каждый сильный claim не имеет evidence refs;
- denominator/coverage отсутствуют;
- candidate cards не прошли human review;
- не завершён technical fact-check;
- не завершён legal/rights review изображений;
- private hypotheses не утекли в public bundle;
- редакционная правка не усилила allowed strength.

Целевая метрика качества — не «убедительность любой ценой», а доля вопросов, на которые читатель может получить проверяемый ответ без доверия к авторитету автора.
