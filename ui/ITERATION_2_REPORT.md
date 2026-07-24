# UI Iteration 2 — Read-only AST Indexer

## Статус

**Завершено. Общая готовность UI: 14/100 (14%).**

## Реализовано

- Read-only AST indexer, который не импортирует и не исполняет `app6`.
- Каталог modules, classes, functions, nested functions, async functions и methods.
- Qualified names, signatures, annotations, docstrings и source line ranges.
- Imports, constants, decorators, raises и status calls.
- Сигналы незавершённости: `pass`, `NotImplementedError`, TODO/FIXME/HACK/XXX и broad exceptions.
- SHA-256 content hash source files.
- Function fingerprint, устойчивый к перемещению файла.
- Incremental reindex: added/changed/removed/unchanged.
- Статический call graph с `confirmed_static` и `heuristic_static`; зарезервированы runtime/manual confidence.
- Динамические вызовы не получают статус confirmed.
- Watcher с debounce, optional `watchfiles` и polling fallback.
- Игнорирование caches, `.data`, generated/artifacts/build/dist и служебных каталогов.
- Thread-safe project event hub и WebSocket `/ws/project`.
- API `/api/modules`, `/api/functions`, `/api/project/graph`.
- Устранены незакрытые SQLite connections в control database и тесте.

## Проверка реального app6

- Python modules: **91**.
- Functions/methods/nested functions: **447**.
- Classes: **38**.
- Static graph edges: **802**.
- Parse errors: **0**.
- Повторный scan без изменений детерминирован.
- Файлы `app6` не изменены.

## Тесты

- UI backend: **25/25 PASS**.
- app6 regression: **65/65 PASS**.
- Frontend TypeScript syntax: **4/4 PASS**.
- Backend/app6 compileall: PASS.
- `git diff --check`: PASS.

## Ограничения

AST не может достоверно восстановить каждый динамический Python-вызов. Поэтому неоднозначные связи остаются heuristic или отсутствуют до runtime observation/manual override. Это намеренная защита от ложной уверенности.

## Exit criteria

- [x] Все 91 Python-модуля индексируются.
- [x] Parse errors отсутствуют.
- [x] Индексатор не импортирует наблюдаемый source.
- [x] Повторный scan детерминирован.
- [x] Incremental refresh и watcher проверены.
- [x] Dynamic calls не маркируются confirmed.
- [x] API и project-update WebSocket реализованы.

## Следующая итерация

Iteration 3: Status/Test Indexer и понятный журналистский каталог функций.
