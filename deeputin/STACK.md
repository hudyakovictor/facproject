# DEEPUTIN — technology and component policy

**Дата фиксации:** 2026-08-24  
**Scope:** только `/home/user/facproject/deeputin`; существующий `/home/user/facproject/ui` не является runtime dependency.

## 1. Принцип выбора

Сначала строится контракт пустых страниц и блоков. Зависимость добавляется только тогда, когда конкретный блок действительно требует её поведения. Это уменьшает initial bundle, не связывает весь проект с одним UI-kit и позволяет нескольким разработчикам работать по одним правилам.

Критерии проверки перед добавлением:

1. официальный GitHub upstream и понятная активность;
2. лицензия и наличие license metadata;
3. React/TypeScript/Vite compatibility;
4. размер, lazy-loading и стоимость для initial bundle;
5. возможность заменить визуальный слой;
6. отсутствие зависимости от чужой темы или закрытого SaaS;
7. наличие доступного fallback для пустых, ограниченных и недоступных данных.

## 2. Foundation, который используется сейчас

| Решение | Назначение и почему подходит | Ограничения | Лицензия / upstream | Правило применения | Альтернатива |
|---|---|---|---|---|---|
| React 19 | Компонентная композиция страниц и блоков | Не является data/cache layer | MIT, https://github.com/facebook/react | Держать page shell, shared renderer и page ownership раздельно | Preact, если появится отдельное performance-обоснование |
| Vite 8 | Быстрый dev/build для отдельного runtime | Не решает routing/data contracts | MIT, https://github.com/vitejs/vite | Bind `0.0.0.0`; preview host разрешён в config | Rsbuild, только после отдельной проверки |
| TypeScript 7 | Типы page/block/source/evidence contracts | Не заменяет runtime validation | Apache-2.0, https://github.com/microsoft/TypeScript | Не использовать `any` в data/domain; типы сохраняются при замене визуала | Flow, не предпочтителен |
| Tailwind CSS 4 + CSS tokens | Композиция и единые styles без vendor theme lock-in | Utility classes сами не описывают forensic semantics | MIT, https://github.com/tailwindlabs/tailwindcss | Семантические состояния хранить в tokens; данные не зависят от классов | Plain CSS, CSS Modules |
| Vitest + Testing Library | Быстрые component/contract tests | Не заменяют browser/a11y tests | MIT, https://github.com/vitest-dev/vitest; MIT, https://github.com/testing-library | Тестировать пустые и boundary states до реальных данных | Jest |
| Playwright | E2E, keyboard и cross-browser путь | Browser binaries нужны отдельно | Apache-2.0, https://github.com/microsoft/playwright | Добавлять критический путь после появления интерактива | Cypress |
| Biome + Oxlint | Единый формат и быстрый correctness lint | Не являются domain QA | MIT, https://github.com/biomejs/biome; MIT, https://github.com/oxc-project/oxc | Все страницы проходят общий verify | ESLint + Prettier, не добавлять вторую пару без причины |

## 3. Planned additions — только по потребности блока

| Решение | Для какого блока | Почему | Ограничения | Лицензия / upstream | Правила и альтернатива |
|---|---|---|---|---|---|
| shadcn/ui source code + Base UI | dialog, drawer, tabs, select, menu, slider | Headless/source-owned, внешний skin остаётся у проекта | Нужно владеть и поддерживать сгенерированный код | MIT, https://github.com/shadcn-ui/ui; MIT, https://github.com/mui/base-ui | Один primitive layer, не смешивать Radix и React Aria; fallback обязателен. Альтернатива: React Aria Components |
| TanStack Router | deep links и route params | Типизированный route state для photo/pair/zone/publication | Добавлять, когда появятся реальные routes и URL state | MIT, https://github.com/TanStack/router | Не дублировать route state в произвольном store. Альтернатива: React Router |
| TanStack Query | API/manifest server state | cache, stale, retry и pagination | Не хранить server response параллельно в Zustand | MIT, https://github.com/TanStack/query | Page не делает ad-hoc fetch. Альтернатива: SWR |
| TanStack Table + Virtual | timeline, pair queue, metrics и большие приложения | Headless table + виртуализация без сетки vendor | Нужен собственный accessible markup | MIT, https://github.com/TanStack/table; https://github.com/TanStack/virtual | Не загружать большой CSV целиком. Альтернатива: AG Grid при доказанной enterprise-потребности |
| Zustand | выбранные photo/pair/zone, view и publication state | Небольшой cross-page UI state | Не cache и не источник аналитического truth | MIT, https://github.com/pmndrs/zustand | Сохранять только selection/annotations, не API response. Альтернатива: URL + React state |
| React Hook Form + Zod | filters, Casework, provenance, publication settings | typed forms + runtime schemas | Схема не должна менять source schema | MIT, https://github.com/react-hook-form/react-hook-form; MIT, https://github.com/colinhacks/zod | Одна схема для parse и type. Альтернатива: Valibot |
| Apache ECharts через local adapter | distributions, time series, heatmap | Canvas/SVG и большие серии | Нельзя бросать raw options в page; bundle heavy | Apache-2.0, https://github.com/apache/echarts | `ChartFrame` с summary/source/legend. Альтернатива: custom SVG или Observable Plot |
| XYFlow | только Evidence Map | Graph interactions и viewport | Не использовать как общий layout | MIT, https://github.com/xyflow/xyflow | Domain evidence links отдельно от node payload. Альтернатива: accessible relation table |
| Three.js + R3F + Drei + mesh-bvh | только Morphing/3D layers | Lazy scene и готовые controls | Heavy, artifacts may be unavailable | MIT, https://github.com/mrdoob/three.js; MIT, https://github.com/pmndrs/react-three-fiber; MIT, https://github.com/pmndrs/drei; MIT, https://github.com/gkjohnson/three-mesh-bvh | Lazy boundary; mesh/UV ≠ original/photo/verdict. Альтернатива: 2D fallback |
| Tiptap / ProseMirror | только Publications | JSON document, extensions, custom evidence nodes | Editor не должен пересчитывать аналитику | MIT, https://github.com/ueberdosis/tiptap | Хранить evidence/source/limitation attrs и serializers. Альтернатива: Lexical |
| dnd-kit core + sortable | Outline и reorder | Keyboard/touch sorting | Не file uploader; peer versions must match | MIT, https://github.com/clauderic/dnd-kit | Добавлять только вместе с keyboard sensor. Альтернатива: native drag/drop |
| Lucide | action/navigation icons | ISC, neutral icon language | Icon cannot carry status alone | ISC, https://github.com/lucide-icons/lucide | Visible label or accessible name. Альтернатива: inline SVG |

## 4. Unified data vocabulary

Любое будущее значение проходит через общий контекст:

```ts
value: number | null
metric: string
unit: string | null
coordinateSpace: raw_object_normalized | chronology_aligned | original_image_px | mesh | uv | null
objectId: string
sourceRef: SourceRef
measurementState: measured | limited | unavailable | not_computed | skipped | error | not_applicable | fallback
qualityState: string | null
visibilityState: string | null
calibrationState: string | null
limitations: Limitation[]
notAVerdict: true
```

Каждый source ref сохраняет `sourceMode: research`, `stage`, `relativePath`, `fileName`, `jsonKey/csvColumn`, `artifactType` и `availability`.

## 5. Page architecture and directory policy

Registry содержит только семь top-level страниц:

```text
Timeline → Timeline Map block
Photo Detail
Compare → Pair Detail + Morphing blocks
Research → Zone Atlas + Casework + Corroboration + Key Points + Persistence blocks
Methodology → Calibration + Metrics + Integrity blocks
Report → Run Summary block
Publications
```

`Upload`/`Ingestion` не являются частью runtime: загрузка и расчёт находятся вне интерфейса.

```text
deeputin/src/
├── App.tsx                 # shell and seven-page registry, not data calculations
├── shared/                 # only truly cross-page contracts/renderers
├── pages/                  # one file per top-level page blueprint initially
├── styles.css              # shared tokens and semantic blueprint skin
└── test/
```

До роста feature не создавать папку из одного файла и не делать route на каждый аналитический подраздел. Page file может быть до примерно 1000 строк, если это улучшает читаемость и ownership. Когда у блока появляются отдельные query/state/renderer/tests/export или файл перестаёт быть обозримым, он выносится в локальную подпапку конкретной страницы.

Каждый block contract фиксирует смысловую границу, owned elements, источники, состояния и действия. Layout, ширина, размер и конкретная визуализация остаются решением page owner и разработчика блока.

## 6. Prohibited

- mock data, fake fixtures и hardcoded analytics;
- API CDN для критических компонентов;
- второй UI primitive layer;
- hidden `unavailable`, `limited`, `warning` или `fallback`;
- direct imports из `ui/src`;
- browser requests к `localhost` / `127.0.0.1`;
- automatic identity/medical/forensic verdict;
- выдавать proxy или reconstruction за original;
- использовать `private_hypothesis_seed` как truth;
- менять source schema ради удобства страницы.
