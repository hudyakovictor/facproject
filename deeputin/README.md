# DEEPUTIN Forensic Workbench

`deeputin/` — отдельный frontend-корень рабочей станции, которая визуализирует уже рассчитанные данные. Он не импортирует production-код, runtime или mock-данные из `/home/user/facproject/ui`.

## Текущий этап

Blueprint и runtime-реализация находятся в одном frontend-корне:

- семь крупных рабочих страниц вместо набора микрорoutes;
- связанные аналитические области собраны в самостоятельные смысловые блоки;
- каждый блок владеет своими контролами, фильтрами, представлениями, состояниями, источниками, ограничениями и действиями;
- фильтры и настройки не вынесены в глобальные обязательные блоки: они находятся рядом с содержимым, которым управляют;
- общий renderer не навязывает колонку, размер или внешний способ композиции — это решение владельца страницы и реализации блока;
- calculated API/artifact endpoints запрашиваются только по явному действию пользователя;
- returned значения, источники, provenance, measurement/gate statuses, empty/error/unavailable и cross-page context остаются видимыми;
- клиент не рассчитывает метрики, точки, геометрию, heatmap или изображения и не подменяет ответ mock/sample/fixture данными или verdict.

**Загрузка исходных фотографий и ingestion находятся вне этого интерфейса.** Поэтому `Upload` и `Ingestion` намеренно отсутствуют. Publication Studio сохраняет редакционные изменения только локально: подтверждённого write API для публикаций в контракте нет.

## Запуск

Требуется Node.js `^20.19.0 || >=22.12.0`.

```bash
cd /home/user/facproject/deeputin
npm install
npm run dev
```

Dev server слушает `0.0.0.0` и принимает preview-host. Браузерный код использует только относительные `/api/v1/...` URL; Vite проксирует их на `DEEPUTIN_API_PROXY` (по умолчанию `http://127.0.0.1:8000`). Для удалённого calculated API задайте переменную окружения до запуска. В браузерном коде нельзя обращаться к `localhost` или `127.0.0.1` напрямую.

Lightweight UI-выходы читаются через те же относительные paths `/api/v1/ui_artifacts/...`. В dev/preview Vite read-only отдаёт только разрешённые файлы из `DEEPUTIN_UI_ARTIFACTS_ROOT` (по умолчанию `/Volumes/SDCARD/storage/ui_artifacts`); если съёмный каталог не смонтирован, запрос передаётся API proxy. UI не читает filesystem и не подменяет отсутствующий результат pipeline.

## Проверки

```bash
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run verify
```

Playwright-конфигурация подготовлена, но запуск браузерных тестов требует установленного browser binary:

```bash
npm run test:e2e
```

## Структура

```text
deeputin/
├── agents.md                 # обязательные правила агента/разработчика
├── sikll.md                  # workflow реализации; имя сохранено намеренно
├── STACK.md                  # стек, лицензии, upstream и правила добавления
├── README.md
├── package.json
├── package-lock.json
├── index.html
├── vite.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── biome.json
├── src/
│   ├── App.tsx               # shell, top navigation и registry семи страниц
│   ├── styles.css            # tokens и skin semantic blueprint
│   ├── main.tsx
│   ├── shared/
│   │   ├── contracts.ts      # общий словарь данных и semantic block contract
│   │   ├── PageBlueprint.tsx  # общий renderer порядка блоков
│   │   ├── PlaceholderBlock.tsx
│   │   └── README.md
│   ├── pages/
│   │   ├── Timeline.tsx       # Archive Explorer, Timeline Map, selection journal
│   │   ├── PhotoDetail.tsx    # overview/artifacts, pose/quality, landmarks/surface
│   │   ├── Compare.tsx        # Pair Detail, visual comparison and Morphing, evidence
│   │   ├── Research.tsx       # Zone Atlas, Casework, Corroboration, motion/persistence
│   │   ├── Methodology.tsx    # pipeline, calibration/metrics, integrity
│   │   ├── Report.tsx         # Run Summary/evidence, narrative/export
│   │   ├── Publications.tsx   # authoring, Evidence Map, reader/QA/export
│   │   ├── index.ts
│   │   └── README.md
│   └── test/
└── e2e/
```

## Целевые страницы и группировка

### Аналитика

- **Timeline** — Archive Explorer, `Timeline Map`, Selection Context and Session Journal.
- **Photo Detail** — Photo Overview and Artifact Viewer, Pose/Expression/Quality, Landmarks and Surface Diagnostics.
- **Compare** — `Pair Detail` and data-first analysis, visual-first comparison with `Morphing`, Zones/Evidence/Actions.

### Исследование и контроль

- **Research** — `Zone Atlas`, Casework Review, `Corroboration`, Key Points/Persistence/Review.
- **Methodology** — Pipeline/Archive Quality/Gates, Calibration/Metrics Reference, Integrity/Connectivity/Source Registry.

### Сборка результата

- **Report** — `Run Summary` and working evidence, Narrative/Sources/Export.
- **Publications** — Authoring Workspace, `Evidence Map`, Reader/QA/Export.

`Morphing`, `Timeline Map`, `Pair Detail` и `Run Summary` — не routes. Они принадлежат крупным рабочим страницам и остаются частью их semantic block ownership.

## Самостоятельный block contract

В `BlockDefinition` фиксируются только смысл и границы владения:

- `id` и `title`;
- `purpose`;
- `elements` — полный список будущих controls, views, inspectors, captions и context, которыми владеет блок;
- `keys`, `sourceRefs`, `actions`, `requiredStates`; в data contract сохраняются `source_mode: research`, `not_a_verdict: true`, provenance, limitations и measurement/gate states;
- coordinate-space keys остаются различимыми: `raw_object_normalized`, `chronology_aligned`, `original_image_px`, `mesh`, `uv`.

`PageBlueprint` намеренно не решает заранее, будет ли реализация блока одной панелью, несколькими колонками, вкладками, drawer, modal или отдельным рабочим canvas. Если фильтр меняет данные рядом с ним, фильтр и эти данные принадлежат одному самодостаточному блоку.

## Правило дальнейшей работы

1. Сначала реализуется самый необходимый блок существующей крупной страницы.
2. Перед JSX обновляются comment-contract, `elements` и `BlockDefinition`.
3. Реальные данные подключаются только через typed adapter и runtime validation.
4. Сохраняются keys, source refs, provenance, limitations, states и `not_a_verdict`.
5. Unavailable/limited/error/fallback остаются видимыми и не превращаются в ноль.
6. Визуальный слой можно заменить без изменения смысла блока или его source vocabulary.
7. Новый файл появляется только при собственных query/state/renderer/tests/export или реальной сложности; искусственно дробить блоки, страницы и routes нельзя.
8. Новый функционал добавляется только если он нужен ТЗ или необходим для корректного чтения уже рассчитанных данных.
