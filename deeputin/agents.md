# DEEPUTIN — обязательные правила для AI-агента и разработчика

## 1. Миссия

Создавать forensic workbench, который визуализирует уже рассчитанные данные. Аналитика остаётся главным инструментом, а `Publications` — дополнительным редакционным слоем. Любой блок должен быть заменяемым: смена таблицы, карточки, графика, canvas или редактора не меняет смысл, источники, статусы и действия.

Целевой результат — удобная рабочая станция для параллельной разработки, а не максимальное количество UI-компонентов, файлов или routes.

## 2. Граница проекта

Можно:

- менять и создавать файлы только внутри `/home/user/facproject/deeputin`;
- читать `ui/spec` как исходное ТЗ;
- создавать typed adapters только после согласования source contract;
- добавлять контрактные тесты без mock/fixture-данных.

Нельзя:

- менять `/home/user/facproject/ui`;
- копировать `ui/mock`, реальные Stage-файлы или изображения;
- импортировать `ui/src` в production;
- создавать второй runtime или второй package manager;
- подключать браузер к `localhost` или `127.0.0.1`;
- добавлять mock, sample или fixture data — включая примерные строки, числа, фотографии и API responses;
- добавлять `Upload`/`Ingestion`: загрузка и расчёт данных находятся вне этого интерфейса.

Приложение получает источники, рассчитанные внешним процессом, и не пересчитывает аналитику в UI.

## 3. Целевая page architecture

Registry и top navigation содержат ровно семь top-level страниц:

```text
Timeline
Photo Detail
Compare
Research
Methodology
Report
Publications
```

Не создавать отдельную page/route для каждого аналитического подраздела. Связанные области принадлежат крупным страницам:

- `Timeline Map` — блок `Timeline`;
- `Pair Detail` и `Morphing` — блоки `Compare`;
- `Run Summary` — блок `Report`;
- `Zone Atlas`, `Casework`, `Corroboration`, `Key Points`, `Persistence` — блоки `Research`;
- `Calibration`, `Metrics`, `Integrity` — блоки `Methodology`.

Начальная граница ownership — один page-level файл на крупную страницу. Выносить блок в локальную папку только при собственных query/adapter, сложном view state, renderer, тестах или export. Не дробить код ради одной подписи, row, badge или искусственного route.

## 4. Текущий этап: semantic blueprint

Начальная реализация обязана содержать:

- `PageDefinition` для каждой из семи страниц;
- самостоятельные смысловые блоки в порядке чтения;
- comment рядом с каждым блоком со всеми допустимыми data keys;
- те же keys в `BlockDefinition`;
- `elements` — полный список внутренних controls, views, inspectors, captions и контекста блока;
- source refs, actions и required states;
- единый `PageBlueprint` и `EmptyBlock` renderer;
- ноль аналитических значений, ноль mock data и ноль verdict.

Фильтр, который меняет данные конкретной рабочей области, является частью этого же блока. Не создавать отдельный глобальный filter block только потому, что в будущем он может визуально оказаться рядом с данными.

Пустая заглушка показывает назначение и semantic contract. Она не изображает готовый результат и не навязывает будущую композицию.

## 5. Self-contained block contract

Каждый `BlockDefinition` обязан иметь:

```text
id
title
purpose
elements
inputs / data keys
view state
measurement/resource state
source refs
limitations
actions
loading state
empty state
limited/unavailable/fallback state
error state
accessibility
export behavior
```

`elements` — это не список отдельных routes. Это содержимое одного ownership boundary. Например, блок сравнения может включать выбор A/B, фильтры, таблицу метрик, gates, viewer, legend и actions, если они нужны для одной задачи.

До JSX сначала обновляются comment-contract, `elements` и `BlockDefinition`. Если ключ или источник неизвестен, писать `TBD`, а не угадывать.

## 6. Unified data contract

Общий measurement context:

```text
value + metric + unit
coordinateSpace
objectId / photoId / pairId / zoneId
sourceRef
measurementState
qualityState
visibilityState
calibrationState
limitations
notAVerdict: true
```

Общий `SourceRef` сохраняет `sourceMode: research`, `stage`, `relativePath`, `fileName`, `jsonKey/csvColumn`, `artifactType` и `availability`. Общий `EvidenceContext` сохраняет claim, plain-language meaning, support, weakening, source, limitations, status, explanation state и `not_a_verdict: true`.

Нельзя принимать raw JSON/CSV прямо в visual component. Adapter нормализует данные, runtime schema проверяет shape, visual block получает normalized domain object.

## 7. Данные и статусы

- отсутствие поля никогда не превращается в `0`, пустую уверенность или «изменений нет»;
- `measured`, `limited`, `unavailable`, `not_computed`, `skipped`, `error`, `not_applicable`, `fallback` различаются;
- `fallback` описывает замену артефакта, а не наличие original;
- original, crop, thumbnail, mask, UV, mesh и proxy имеют отдельную availability;
- canonical spaces `raw_object_normalized`, `chronology_aligned`, `original_image_px`, `mesh` и `uv` не смешиваются; короткие UI-подписи маппятся на них явно;
- каждое число имеет metric, unit, coordinate space, object id, source ref и limitation;
- `FDR`, `q-value`, robust-z и visual similarity не являются identity score;
- `not_a_verdict: true` сохраняется в аналитическом и редакционном контексте;
- `private_hypothesis_seed` и legacy posterior остаются quarantine material;
- warning либо исправляется, либо попадает в видимое ограничение.

## 8. Приоритеты 20/80

1. Обязательная структура семи страниц и ключевые блоки ТЗ.
2. Data contract, source mapping и complete self-contained block boundaries.
3. Один критический пользовательский путь.
4. Accessibility, deep link и performance для этого пути.
5. Вторичные controls, украшения, редкие режимы и дополнительные экспорты.

Не начинать с 3D, сложного редактора, графовых эффектов или полной автоматизации, если не собран необходимый аналитический блок.

## 9. Compare rule

`Compare` сохраняет два равноправных сценария:

- **data-first:** метрики, raw/calibrated/robust-z, q-value, quality, visibility, calibration, pose/expression gates, zones, source refs и limitations;
- **visual-first:** A/B, side-by-side, overlay, divider, zoom/pan, landmarks, heatmap, morphing и 3D при доступности.

Фильтры режима, управление viewer, данные и их контекст принадлежат соответствующему self-contained block. Визуальный слой не формирует statistical confirmation или identity verdict.

## 10. Publication rule

`Publications` начинается с claim и plain-language meaning, затем добавляет media, source refs, limitations и unresolved questions. Текст — главный слой, media — evidence attachment. Длинный материал не получает искусственного лимита глав/блоков/страниц. Export самодостаточен и не скрывает warnings.

## 11. Link

Переходы передают domain identifiers, а не DOM state:

```text
photoId, pairId, zoneId, date, poseBin, claimId, blockId, publicationId
```

Позже route state должен восстанавливаться по deep link. Не передавать на другую страницу визуальные детали конкретной раскладки.

## 12. Ready-made libraries

Использовать только решения из `STACK.md` и только по назначению. Сначала проверить существующий shared primitive, затем source-owned shadcn/Base UI, затем TanStack или профильный renderer. Не строить один и тот же dialog/menu/tabs на нескольких UI libraries. Не использовать UI-kit как источник бизнес-логики, данных, analytics verdict или limitation policy.

## 13. QA и Definition of Done

Перед завершением page/block:

```bash
cd /home/user/facproject/deeputin
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run verify
```

Для интерактивного блока добавить keyboard test и, когда browser binary доступен, Playwright/axe test. Проверить normal, loading, empty, limited, unavailable, fallback, error, long content и narrow viewport.

Готово означает:

- код находится в `deeputin`;
- нет mock/sample/fixture data и выдуманных значений;
- registry и top navigation содержат только семь целевых страниц;
- каждая страница разделена на понятные self-contained blocks;
- фильтры и controls находятся внутри блока, на который они влияют;
- page/block keys и comments совпадают;
- source refs и limitations не потеряны;
- визуал можно заменить без изменения contract;
- data-first и visual-first Compare сохранены;
- Publications не меняет analytics semantics;
- source/alt/caption/units доступны без hover;
- `npm run verify` проходит;
- нет автоматического identity verdict.

Критический дефект: hidden unavailable, fallback as original, unavailable as zero, lost source/limitation, browser localhost call, identity verdict или изменение одного блока ломает соседнюю страницу.
