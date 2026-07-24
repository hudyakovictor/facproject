# UI Iteration 3 — Status/Test Indexer и журналистский каталог

## Статус

**Завершено. Общая готовность UI: 20/100 (20%).**

## Реализовано

- Literal-only parser `STATUS_AUDIT.py` без импорта и выполнения кода.
- Нормализация status, blocker и notes; mapping на function IDs с confidence.
- Static test indexer для unittest/pytest-style функций, imports, calls и expected exceptions.
- Auto test bindings с `confirmed_static` и `heuristic_static`.
- Проверяемые manual overrides через `test_bindings.yaml`; неизвестные IDs отклоняются.
- `function_catalog.yaml` с ручными journalist-first описаниями критических точек и glossary.
- Каталог всех индексированных функций: title, description, why important, failure impact, stage, criticality, status, tests и source.
- Отсутствующие ручные/docstring описания получают generated fallback и задачу P2, а не скрываются.
- API `/api/status`, `/api/tests`, `/api/catalog`, безопасный read-only `/api/source`.
- Тёмный Function Catalog UI: поиск, stage/status/criticality/test/blocker filters, список, inspector и source preview.
- Техническое имя и путь отображаются мелкой серой подписью.

## Результат на app6

- Functions in catalog: **447**.
- STATUS_AUDIT entries: **131**.
- Однозначно сопоставленные status entries: **89**.
- Regression tests discovered: **65**.
- Static test bindings: **57**.
- Critical catalog entries: **71**, у всех заполнены четыре journalist-first поля.
- Generated-description P2 tasks: **331** — это честный backlog редакторской доработки, не ошибка индексации.

Неразрешённые status entries сохраняются видимыми: среди них class/config entries, исторические и переименованные symbols. Они не привязываются к функции автоматически без доказательства.

## Проверки

- UI backend: **29/29 PASS**.
- app6 regression: **65/65 PASS**.
- Frontend TypeScript syntax: **5/5 PASS**.
- Backend/app6 compileall: PASS.
- `git diff --check`: PASS.
- `app6` не изменён.

## Следующая итерация

Iteration 4: Pipeline Canvas MVP на React Flow с ELK layout и semantic zoom.
