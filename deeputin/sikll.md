# DEEPUTIN implementation skill

Имя файла сохранено ровно как `sikll.md` по требованию проекта. Это практический workflow для AI-агента и разработчика.

## 1. Главная формула

```text
Read → Inventory → Group → Blueprint → Contract → Compose → States → Link → Verify
```

Не начинать с рендера. Сначала определить, какой крупной странице принадлежит область и какой self-contained block отвечает за цель пользователя.

## 2. Read

Перед изменением прочитать:

1. `agents.md`;
2. `STACK.md`;
3. `README.md`;
4. соответствующие `ui/spec/INTERFACE_ARCHITECTURE.md`, `SPEC.md`, `API_CONTRACT.md`, `DATA_SOURCES.md` и editorial/source документы;
5. соответствующий page file в `src/pages/`;
6. только затем текущий компонент из `ui` для понимания поведения — не для копирования runtime или данных.

`ui/spec` является источником полноты: из него нужно сверять не только названия страниц, но и элементы, источники, статусы, ограничения, переходы и сценарии редактора.

## 3. Inventory and grouping

Составить короткую таблицу:

```text
Top-level page:
Route key:
Primary question:
Self-contained block:
Owned elements:
Source files and keys:
Object scope:
Actions:
Required states:
Non-goals:
Owner:
```

Использовать только семь top-level страниц:

```text
Timeline
Photo Detail
Compare
Research
Methodology
Report
Publications
```

Связанные области не превращать в новые routes:

```text
Timeline Map         → Timeline block
Pair Detail          → Compare block
Morphing             → Compare block
Zone Atlas           → Research block
Casework             → Research block
Corroboration        → Research block
Key Points           → Research block
Persistence          → Research block
Calibration          → Methodology block
Metrics              → Methodology block
Integrity            → Methodology block
Run Summary          → Report block
```

`Upload`/`Ingestion` не входят в приложение: данные уже загружены и рассчитаны внешним процессом.

## 4. Semantic blueprint

Page file должен содержать:

- `PageDefinition` с `id`, `title`, `group`, `purpose`, `primaryQuestion`;
- self-contained blocks в порядке чтения;
- comment над каждым блоком;
- полный список DATA KEYS в comment;
- те же keys в `BlockDefinition`;
- `elements` — все будущие controls, views, inspectors, captions, legends, source context и actions, которыми владеет блок;
- source refs с ожидаемыми именами файлов/API;
- actions и required states.

Пример комментария:

```tsx
/**
 * BLOCK: Pose, expression and quality.
 * OWNED ELEMENTS: pose controls, expression readout, quality summary, visibility context, limitation explanation.
 * DATA KEYS: yaw, pitch, roll, expression_magnitude, visible_landmarks_106,
 * visible_landmarks_134, quality_state, visibility_state, source_ref, limitation_refs.
 */
```

Пример определения:

```tsx
{
  id: 'photo-detail.pose-quality',
  title: 'Pose, expression and quality',
  purpose: '...',
  elements: ['pose controls', 'quality summary', 'limitation explanation'],
  keys: ['yaw', 'pitch', 'roll', ...],
  sourceRefs: ['stage1/<photo_id>/info.json'],
  actions: ['open_methodology', 'open_limitation'],
  requiredStates: ['empty', 'limited', 'unavailable', 'error'],
}
```

Если ключ нужен нескольким страницам, он остаётся одинаковым. Не переименовывать источник в удобное UI-название. Если ключ или путь неизвестен, писать `TBD`.

## 5. Self-contained boundary

Граница блока определяется не визуальной панелью, а общей задачей и состоянием.

Если controls или filter меняют данные конкретного рабочего представления, они входят в тот же блок:

```text
цель пользователя
→ controls / filters
→ data view
→ selection / inspector
→ source / limitations
→ actions / export
```

Не создавать отдельный глобальный block только для фильтра, header, inspector, legend, source note или actions, если они нужны для понимания той же цели. Весь код feature должен иметь одного page/block owner.

Объединять нужно связанные части, но не смешивать несвязанные workflows. Например, `Pair Detail` может владеть выбором A/B, metric table и gates; `Morphing` может владеть viewer, playback, layers и artifact fallback.

## 6. Layout freedom

Не фиксировать в shared contract:

- колонки;
- ширину;
- высоту;
- постоянные панели;
- обязательное соседство блоков;
- modal/drawer/fullscreen форму;
- конкретную библиотеку визуализации.

`PageBlueprint` служит только проверяемым semantic scaffold. Page owner сам решает, будет ли один блок одной панелью, canvas, несколькими внутренними зонами, tabs, modal, drawer или составным рабочим экраном. Это решение можно менять без изменения `BlockDefinition` и source vocabulary.

## 7. Contract

В любом будущем data adapter сохранять:

```text
SourceRef = sourceMode + stage + relativePath + fileName + jsonKey/csvColumn + artifactType + availability
MeasurementContext = sourceMode + notAVerdict + value + metric + unit + coordinateSpace + objectId + sourceRef + states + limitations
EvidenceContext = claim + plain-language meaning + support + weakening + source + limitations + explanation state
```

Нельзя принимать raw JSON/CSV прямо в visual component. Adapter нормализует данные, runtime schema проверяет shape, visual block получает normalized domain object.

## 8. States

Каждый data-dependent block предусматривает:

- loading;
- empty — источник пуст или ещё не рассчитан;
- limited — часть условий не выполнена;
- unavailable — источник/артефакт недоступен;
- fallback — явно указано, что это замена;
- error;
- long content;
- narrow viewport;
- keyboard focus.

Missing data не отображается как ноль. Empty source не выглядит как отсутствие изменений. Битый image URL заменяется текстовым unavailable state с expected path.

## 9. Compare rule

`Compare` всегда сохраняет два равноправных сценария:

- **data-first:** метрики, raw/calibrated/robust-z, q-value, quality, visibility, calibration, pose/expression gates, zones, source refs, limitations;
- **visual-first:** A/B, side-by-side, overlay, divider, zoom/pan, landmarks, heatmap, morphing и 3D при доступности.

Визуальный слой не формирует statistical confirmation или identity verdict. `Pair Detail` и `Morphing` остаются block-level features внутри `Compare`.

## 10. Publication rule

`Publications` начинается с claim и plain-language meaning, затем добавляет media, source refs, limitations и unresolved questions. Текст — главный слой, media — evidence attachment. Длинный материал не получает искусственного лимита глав/блоков/страниц. Export самодостаточен и не скрывает warnings.

## 11. Link

Переходы передают domain identifiers, а не DOM state:

```text
photoId, pairId, zoneId, date, poseBin, claimId, blockId, publicationId
```

Позже route state должен восстанавливаться по deep link. Не передавать на другую страницу визуальные детали конкретной раскладки.

## 12. Verify

Минимум:

```bash
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run verify
```

Ручной минимум:

- открыть каждую страницу напрямую по hash route;
- обновить страницу;
- пройти top navigation и keyboard focus;
- открыть keys/source refs/elements;
- увидеть empty/unavailable/limited;
- проверить, что control, data view, source и action не разнесены искусственно по routes;
- проверить, что нет mock data и verdict;
- подтвердить, что вложенные области не стали отдельными routes.

## 13. 20/80 acceptance rubric

| Критерий | Вес |
|---|---:|
| Сохранены семь целевых страниц и вложенные блоки | 20 |
| Keys/source refs/статусы не потеряны | 20 |
| Self-contained boundaries и ownership понятны | 15 |
| Нет mock data и автоматического verdict | 15 |
| Accessibility и keyboard path | 10 |
| Performance/deferred dependencies | 10 |
| Tests/documentation | 10 |
| **Итого** | **100** |

Целевой результат — 90+. Сначала закрывается структура и критический смысл, потом детали. Нельзя компенсировать потерю source/limitation красивой вёрсткой.
