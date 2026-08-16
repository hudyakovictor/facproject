# AGENTS.md — правила работы над DEEPUTIN

> Область действия: весь репозиторий. Более вложенный `AGENTS.md` может уточнять правила своей директории, но не отменяет научные, provenance- и safety-инварианты этого файла.

## 1. Назначение

DEEPUTIN — исследовательская workstation для продольного технического сравнения фотографий лица за 1999–2026 годы. Система извлекает 3D-геометрию, landmarks, visibility, pose, quality, provenance и диагностические признаки текстуры; затем сравнивает кадры внутри сопоставимых pose bins и отображает измерения в хронологии.

Система **не выносит автоматический вердикт о личности**. Статус, cluster, threshold exceedance или legacy-hypothesis match — это наблюдение/кандидат на проверку, а не доказательство того, что изображены один или разные люди.

Основные пользователи:

1. журналист-расследователь/аналитик;
2. независимый рецензент в blind workflow;
3. технический разработчик;
4. публичная аудитория — только через отдельный read-only publication layer.

## 2. Обязательный порядок чтения

Перед изменением кода прочитать:

1. `README.md`;
2. этот файл;
3. `SKILL.md`;
4. `docs/final/00_README.md`;
5. `docs/final/02_VALIDATED_METHOD.md`;
6. `docs/final/04_DATA_CONTRACTS.md`;
7. `docs/final/08_UI_AND_REPORTING.md`;
8. профильный документ задачи;
9. для UI v5 — `ui-v5/README.md`, `docs/UI_V5_COMPLETE_IMPLEMENTATION_SPEC.md` и `docs/UI_V5_RENDER_REVIEW_19_FACTORS_2026-08-05.md`;
10. для новых forensic/statistical methods — `docs/SPECIALIST_METHODS_ROADMAP.md`.

`CLAUDE.md` содержит дополнительный operational profile для Claude Code. Он не заменяет этот файл.

## 3. Source of truth

При конфликте источников приоритет следующий:

1. валидированные runtime artifacts и versioned schema;
2. regression/contract tests;
3. `docs/final/*` и зафиксированные decision records;
4. канонический код в корневом `app6/`;
5. OpenAPI schema корневого API;
6. UI documentation;
7. design renders;
8. старые комментарии, legacy output и private hypotheses.

Design render задаёт информационную архитектуру, но не является контрактом данных. Нельзя создавать поле только потому, что оно нарисовано на PNG.

### Канонические директории

- `app6/` — научный pipeline и основной backend;
- `3ddfa_v3/` — вендоренная 3DDFA_V3-интеграция; не форматировать массово;
- `uv_module/` — UV/визуализационные функции;
- `ui-v5/` — единственный целевой интерфейс;
- `docs/final/` — валидированные контракты и ограничения;
- `app6/private_hypothesis_seed/` — private quarantine, не публичный evidence source.

Вложенные копии backend внутри UI-директорий считаются удаляемым legacy. Не добавлять туда новую научную логику и не исправлять только их. Новая логика живёт в корневом `app6/`; нужные UI routes добавляются туда с contract tests.

## 4. Неизменяемые научные инварианты

Изменение любого пункта требует отдельного method study, decision record, schema/config version bump и regression tests.

1. **9 pose bins:** `left_profile`, `left_deep`, `left_mid`, `left_light`, `frontal`, `right_light`, `right_mid`, `right_deep`, `right_profile`.
2. Дата основного набора берётся из имени `YYYY_MM_DD[_N]`; EXIF/source claim только corroboration и никогда молча не заменяет дату.
3. Primary geometry — raw object-normalized coordinates.
4. Pair alignment — iteratively trimmed Kabsch без scale.
5. Primary pair comparison — только внутри одного pose bin и при прошедшем axis-specific pose gate.
6. Visibility — пересечение видимости A и B; скрытая зона не получает измерение.
7. LDM106/LDM134 и full mesh не смешиваются без явного coordinate-space field.
8. Missing/NaN/inapplicable/excluded не превращаются в `0`.
9. FDR canonical level — 0.05, если versioned analysis profile не говорит иначе после новой валидации.
10. A→B→A требует абсолютного эффекта и corroboration; отношение малых чисел недостаточно.
11. Calibration строится на same-person data, person-balanced, с LOPO/contamination checks.
12. Main dataset не используется для скрытой подгонки calibration thresholds.
13. Cluster ID не является identity label.
14. Texture/UV role должен соответствовать активной policy; визуализационный канал нельзя тихо повысить до identity evidence.
15. Legacy/private hypothesis не меняет blind Stage 2 measurement и публичный Stage 3.
16. Fuzzy membership degree не является probability. Байесовская логико-вероятностная модель нечёткого вывода не используется для production H0/H1/H2 posterior или итогового evidence score; понятные категории выводятся напрямую из versioned evidence states.

## 5. Сущности данных

Каждая визуализация и API schema должна различать:

### PhotoPoint

Одна фотография, один `photo_id`, одна authoritative calendar date, один pose bin и одна X-координата на timeline.

### PairMeasurement

Связь A→B. Живёт между двумя фото и содержит applicability, coordinate space, pose gaps, common points, calibration, FDR и альтернативные объяснения.

### EventMarker

Событие на дате/границе: change point, return, conflict, review flag. Не является новой фотографией.

### Interval

Период: era, dense zone, cluster regime, limited calibration coverage, selected range.

### Run/Profile

Версионированный контекст анализа. Не рисуется как photo point.

### PrivateHypothesis

Карантинная retest-card с source, legacy space, migration, coverage и status. Не публикуется автоматически.

На timeline строго выполняется:

```text
photo-level  → одна X(date(photo))
pair-level   → x(A) → x(B)
event-level  → X(date/boundary)
interval     → x(start) → x(end)
```

## 6. Правила честности данных

Запрещено:

- mock/random/seeded measurements в production code;
- fallback, который выглядит как реальный research result;
- клиентский identity score, отсутствующий в backend artifact;
- вывод `0` вместо missing;
- придумывание cluster, confidence, probability или hypothesis percentage;
- чтение значения из design render как факта;
- использование legacy posteriors как calibration truth;
- скрытие failed/excluded rows;
- изменение исходных Stage 1 artifacts из UI;
- неявная запись scientific settings в `localStorage`.

Допустимы deterministic fixtures только в tests/Storybook/MSW. Они должны иметь явные labels `fixture`, `synthetic`, `not research data` и никогда не включаться как production fallback.

## 7. Forensic language

Предпочтительные статусы:

- `accepted`;
- `within_calibration_noise`;
- `candidate`;
- `warning`;
- `limited`;
- `inconclusive`;
- `excluded`;
- `not_applicable`;
- `pending_retest`;
- `requires_manual_review`.

Запрещено превращать их в утверждения «доказана подмена», «это другой человек», «обнаружена маска» или медицинский диагноз. Сильные формулировки допустимы только как цитата внешнего источника с provenance либо как явно обозначенная человеческая интерпретация после независимого review.

Каждый тревожный UI marker по возможности раскрывает:

- source artifact/metric;
- applicability;
- calibration status;
- effective sample/coverage;
- uncertainty;
- alternative explanations;
- run/profile/schema versions;
- reviewer state.

## 8. Целевая архитектура UI v5

UI v5 — одна SPA, не набор независимых приложений.

Основной стек зафиксирован в `README.md` и `ui-v5/README.md`:

- React 19 + strict TypeScript + Vite;
- TanStack Router/Query/Table/Virtual;
- Zustand + zundo;
- Radix UI + CSS Modules + design tokens;
- Canvas 2D + модульные `d3-*` для timeline;
- Three.js + React Three Fiber + GLSL для 3D/morphing;
- Web Workers + Comlink/OffscreenCanvas;
- React Hook Form + Zod;
- OpenAPI-generated typed client;
- Vitest + RTL + MSW + Playwright + axe.

### State boundaries

- TanStack Query: server/evidence state;
- Zustand: transient workspace state;
- URL: shareable/reproducible view state;
- backend profile/manifest: scientific settings;
- IndexedDB: только UI preferences/cache, не authoritative result.

### UI v5 layout rules

1. Timeline занимает основную площадь.
2. Один pose bin открыт по умолчанию.
3. Нет постоянных широких sidebar на timeline.
4. Controls раскрываются как contextual overlays сверху.
5. Графики находятся над photo row; markers — под photo row; years — внизу.
6. Длинные тексты уходят в tooltip/drawer.
7. Display threshold и scientific threshold визуально различаются.
8. Красный/зелёный всегда дублируются иконкой/формой/текстом.
9. Default view остаётся спокойным; anomaly-first — отдельный режим.
10. 1900 фото требуют viewport virtualization и zoom-dependent LOD.

Рекомендуемая композиция рендеров:

- timeline: R23 + R04 + R21 + R05;
- pair analysis: R19 + R18 + R11;
- morphing: R20 + R10;
- clustering: R15 + R12, R13 secondary;
- hypothesis validation: R16 + R17.

## 9. MacBook M1: CPU, GPU и морфинг

Не смешивать два разных compute path.

### 3DDFA extraction

Текущая bundled Python/3DDFA renderer path не считается валидированной для PyTorch MPS. На macOS `--device auto` выбирает CPU. Не включать MPS без отдельного numerical parity/reproducibility study.

### Frontend morphing

Морфинг выполняется в браузере через WebGL2/Three.js и использует Apple Silicon GPU. WebGL2 транслируется браузером в нативный графический backend macOS; CUDA и PyTorch MPS для этого не нужны.

- topology загружается один раз;
- A/B positions хранятся в `Float32Array`/`BufferAttribute`;
- `morphFactor` обновляется uniform;
- интерполяция выполняется vertex shader;
- React state не пересчитывает 35 709 вершин на каждый frame;
- baseline — WebGL2; WebGPU возможен позже только как progressive enhancement;
- обязан существовать capability check и честное сообщение при software fallback/context loss.

Shader principle:

```glsl
vec3 morphed = mix(positionA, positionB, uMorphFactor);
```

GPU morph — визуализация. Он не создаёт новых measurement rows и не участвует в Stage 2.

## 10. API и контракты

1. FastAPI/Pydantic остаются backend source.
2. TypeScript types генерируются из versioned OpenAPI snapshot.
3. Критические payloads проходят runtime validation.
4. API error/empty/limited states отображаются явно.
5. Full mesh желательно отдавать binary/GLB, не многомегабайтным JSON на каждый scrub.
6. Job progress — SSE; polling допустим как fallback.
7. Query cache keys включают run/profile/schema/pose/viewport.
8. UI не вычисляет scientific cluster/hypothesis/calibration result самостоятельно.
9. Новые endpoint и schema получают contract tests и version field.
10. Старый API route нельзя тихо переопределять несовместимым payload.

## 11. Clustering

- вычисление только backend-side;
- versioned feature space и normalization;
- HDBSCAN/другой algorithm с params;
- membership, outlier score, stability, sensitivity runs;
- chronology mode — основной;
- embedding — secondary diagnostic;
- cloud — optional presentation mode;
- обязательная надпись `cluster ≠ identity`;
- переход к pair analysis должен сохранять исходные photo IDs/run ID.

## 12. Private hypothesis validation

1. Страница называется «Валидация гипотез»/«Тестирование гипотез», не именем private-модуля.
2. Данные private-only и не попадают в Stage 3/public exports.
3. Legacy value хранится неизменным.
4. Coordinate-space migration версионируется.
5. Systematic shift — sensitivity scenario, не инструмент максимизации agreement.
6. Показываются coverage, denominator, uncertainty и applicability.
7. Статусы: supported/contradicted/inconclusive/not_applicable/pending.
8. Любая ручная калибровка получает audit entry.
9. Blind Stage 2 measurement не меняется после просмотра legacy hypothesis.
10. Entity names могут быть скрыты в blind review.

## 13. Публикационный pipeline

Stage 2/3 обязаны готовить не один «красивый отчёт», а синхронизированный многоаудиторный пакет:

- `journalist_handoff.json` — технический специалист → журналист;
- plain-language method explainer — широкая аудитория;
- technical appendix — специалисты;
- skeptic Q&A — альтернативы и falsification;
- result-story draft — тезисы, не готовая публикация;
- claims ledger — claim → evidence → limitation → review;
- machine-review packet — AI/static audit;
- independent demonstration protocol — примеры, не зависящие от результата расследования.

Правила:

1. Общий и технический текст строятся из одного claims ledger.
2. Каждое число сохраняет denominator и evidence refs.
3. Observation, interpretation и external reporting не смешиваются.
4. Candidate не усиливается редакционной правкой.
5. Method series не зависит от полученных результатов.
6. Пример на известном человеке используется только как licensed same-person demonstration и не содержит выводов о нём.
7. Скептический раздел публикует сильнейшие альтернативы и условия отзыва тезиса.
8. AI-review получает structured artifacts, но не заменяет independent human reviewer.
9. Draft/public lint блокирует unsupported assertive constructions, а не само нейтральное название темы.
10. Ни один draft не публикуется без technical, provenance, legal и editorial review.

Полный контракт: `docs/PUBLICATION_PIPELINE.md`.

## 14. Security и privacy

Private workstation по умолчанию слушает localhost. До remote hosting обязательны:

- authentication и RBAC;
- strict CORS/origin policy;
- CSRF protection для cookie sessions;
- path containment для всех write/delete endpoints;
- upload size + magic-byte + decode validation;
- audit log;
- rate limits;
- immutable evidence backup;
- разделение private API и public read-only API.

Не публиковать on-chain оригинальные фото, facial vectors, landmarks или 3D geometry без отдельной правовой оценки. Для proof-of-existence использовать hash, manifest и signature; тяжёлые данные хранить off-chain с versioning/access control.

## 15. Производительность

Целевые ограничения UI v5:

- controls реагируют <100 ms;
- pan/zoom стремится к 60 fps, минимум 30 fps на M1;
- morph scrub — 60 fps при одной BFM-модели;
- не более viewport + overscan thumbnails в DOM;
- metric layers рисуются Canvas, не десятками тысяч SVG nodes;
- heavy transforms — worker;
- отмена obsolete requests через AbortController;
- topology/texture caching;
- no React state update per vertex/per frame;
- memory/context loss отображается и восстанавливается безопасно.

Performance claim подтверждается measurement, а не словами.

## 16. Accessibility

Минимум:

- keyboard path для всех основных действий;
- semantic buttons/inputs;
- `aria-label` для icon-only controls;
- focus trap в dialogs и возврат focus;
- `prefers-reduced-motion`;
- цвет не единственный носитель статуса;
- достаточный contrast;
- body text обычно не меньше 12 px, критичные controls 13–14 px;
- screen-reader summary для Canvas/WebGL;
- tabular alternative для графиков;
- zoom браузера 200% не ломает controls.

## 17. Рабочий процесс агента

### До изменения

1. Определить сущность: photo/pair/event/interval/run/hypothesis.
2. Найти source artifact и schema.
3. Найти существующий API route/type/test.
4. Проверить локальный `AGENTS.md`.
5. Сформулировать acceptance criteria.
6. Оценить влияние на scientific policy, provenance и public wording.

### Во время изменения

1. Делать минимальный связный diff.
2. Не дублировать scientific logic во frontend.
3. Добавлять typed boundary.
4. Обрабатывать loading/error/empty/limited/null.
5. Добавлять tests одновременно с logic.
6. Сохранять backward compatibility либо писать migration.
7. Не редактировать generated/runtime/weights/datasets.

### После изменения

1. Запустить релевантные tests.
2. Запустить typecheck/build для UI.
3. Проверить no-mock/no-random production path.
4. Проверить null ≠ 0.
5. Проверить `not_a_verdict` и private/public boundary.
6. Обновить README/schema/decision record при изменении контракта.
7. Выполнить self-review по 25 факторам из `SKILL.md`.
8. Сообщить пользователю изменённые файлы, tests и оставшиеся ограничения.

## 18. Команды проверки

Использовать активный project venv, не хардкодить чужой абсолютный путь.

```bash
python -m compileall -q app6
python -m pytest -q app6/test_module app6/api/tests
ruff check app6 uv_module
```

После создания runnable UI v5 обязательный frontend gate:

```bash
cd ui-v5
npm ci
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm run test:e2e
```

Если внешний dataset/weights отсутствуют в рабочей среде, это фиксируется как external prerequisite; нельзя заменять реальный E2E фиктивным успехом.

## 19. Definition of Done

Задача завершена только когда:

- выполнено заявленное пользовательское поведение;
- данные имеют реальный source contract;
- scientific invariants не нарушены;
- все states обработаны;
- tests/typecheck/build пройдены либо дано точное объяснение блокера;
- UI доступен с клавиатуры;
- performance path соответствует масштабу;
- private/public boundaries соблюдены;
- документация актуальна;
- diff не содержит runtime data, weights, secrets или generated bulk artifacts;
- 25-факторный self-score из `SKILL.md` ≥98/100 либо задача явно не объявляется готовой.

## 20. Что нельзя делать без отдельного согласования

- менять pose bins;
- менять primary coordinate space;
- менять FDR/calibration operating point;
- вводить identity labels для clusters;
- публиковать private hypotheses;
- включать MPS extraction path;
- переписывать pipeline на другой framework;
- добавлять GraphQL/Next.js/Electron/Redux без доказанной необходимости;
- делать destructive migration Stage 1;
- отправлять локальные weights/photos во внешний сервис;
- коммитить credentials, private URLs или персональные данные.
