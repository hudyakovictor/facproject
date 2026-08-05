# DEEPUTIN UI v5

Целевой интерфейс forensic workstation для продольного анализа фотоархива 1999–2026.

## Статус

На 2026-08-05 создан runnable foundation UI v5 и первый внутренний раздел `/design-system`. Он фиксирует design tokens, primitives, forensic states, timeline grammar, data components, overlays, publication/review patterns и accessibility rules. Основной timeline и research pages будут добавляться поверх этих компонентов. В `ui-v5/screens/` сохранены 23 исходных дизайн-рендера; данные будущих рабочих страниц поступают из канонического root API `app6/`.

Оценка всех рендеров: [`../docs/UI_V5_RENDER_REVIEW_19_FACTORS_2026-08-05.md`](../docs/UI_V5_RENDER_REVIEW_19_FACTORS_2026-08-05.md).

Полное функциональное ТЗ от foundation до production release: [`../docs/UI_V5_COMPLETE_IMPLEMENTATION_SPEC.md`](../docs/UI_V5_COMPLETE_IMPLEMENTATION_SPEC.md).

Правила и governance живого каталога компонентов: [`../docs/UI_V5_DESIGN_SYSTEM.md`](../docs/UI_V5_DESIGN_SYSTEM.md).

Объективная 25-факторная оценка DS 0.1: [`80/100`](../docs/UI_V5_DESIGN_SYSTEM_REVIEW.md).

Репозиторные правила: [`../AGENTS.md`](../AGENTS.md), [`../SKILL.md`](../SKILL.md), [`../CLAUDE.md`](../CLAUDE.md).

## Продуктовые принципы

1. Timeline — основной источник навигации и контекста.
2. Один pose bin открыт по умолчанию.
3. Одна фотография = один `photo_id`, одна дата, одна X-координата.
4. Pair/event/interval не изображаются как дополнительные фото.
5. Постоянных широких sidebar на timeline нет.
6. Настройки раскрываются контекстно поверх текущего результата.
7. Display settings отделены от versioned scientific settings.
8. Все значения поступают из реальных API/artifacts; production mock fallback запрещён.
9. Missing/excluded/inapplicable не равны нулю.
10. Candidate/cluster/hypothesis match не является identity verdict.

## Итоговый стек

| Слой | Выбор |
|---|---|
| UI | React 19 |
| Язык | TypeScript strict |
| Сборка | Vite 7, актуальная patched stable версия |
| Routing | TanStack Router |
| Server state | TanStack Query |
| Workspace state | Zustand + zundo |
| Forms/validation | React Hook Form + Zod |
| UI primitives | Radix UI |
| Styling | CSS Modules + CSS Custom Properties/design tokens |
| Tables/lists | TanStack Table + TanStack Virtual |
| Timeline | DOM + Canvas 2D + `d3-scale/array/shape` |
| 3D/morphing | Three.js + React Three Fiber + custom GLSL |
| Background work | Web Workers + Comlink + OffscreenCanvas where available |
| API types | OpenAPI snapshot + openapi-typescript/openapi-fetch |
| Dates | `Temporal.PlainDate` polyfill или backend `epoch_day` |
| i18n | react-i18next |
| Unit/component tests | Vitest + React Testing Library |
| API test fixtures | MSW, tests/Storybook only |
| E2E/visual | Playwright |
| Accessibility | axe-core + Playwright |
| Component catalog | Storybook |

Не использовать как базовые решения: Next.js, Redux, GraphQL, Electron, full-SVG timeline, client-side production clustering, Recharts/ECharts для главной временной оси, Tailwind как основной design system.

## Внутренний раздел Design System

Маршрут: `/design-system`.

Содержит живые интерактивные эталоны:

- surface/semantic color tokens;
- typography, spacing, radius;
- buttons, icon actions и keyboard hints;
- fields, selects, checkbox, switch и live slider;
- evidence/pipeline statuses и quality rings;
- top contextual toolbar, dropdown, popover и tabs;
- metrics, sparklines, histogram и evidence table;
- типизированную timeline grammar: PhotoPoint, PairBridge, EventMarker, IntervalBand;
- applicability, claim и A/B cards;
- dialog, tooltip, toast и job progress;
- loading/empty/error/blocked states;
- publication readiness и reviewer patterns;
- icon language и accessibility checklist;
- dark/light и compact/comfortable modes.

Любой новый визуальный pattern сначала добавляется сюда с состояниями, keyboard behavior и тестом, затем применяется на продуктовой странице. Числа/миниатюры внутри раздела явно маркированы как `UI fixture` и не являются research data.

## Почему SPA

Это аналитическая локальная workstation, а не SEO-сайт. SSR не нужен; Canvas/WebGL всё равно исполняются в браузере. Vite SPA проще связывается с существующим FastAPI, Workers и 3D renderer.

## Архитектура состояния

```text
FastAPI / versioned artifacts
          ↓
OpenAPI-generated client
          ↓
TanStack Query cache
          ↓
view model / Web Worker
          ↓
DOM + Canvas + Three.js
```

- TanStack Query — только server/evidence data;
- Zustand — viewport, active pose, A/B, layers, drawers, camera;
- URL — run/profile/pose/range/selected pair;
- backend manifest/profile — scientific filters/thresholds;
- IndexedDB — UI preferences и bounded cache.

## Планируемая структура

```text
ui-v5/
  src/
    app/
      router/
      providers/
      shell/
    features/
      timeline/
      pair-analysis/
      morphing/
      photo-inspector/
      clustering/
      hypothesis-validation/
      data-manager/
      calibration/
      profiles/
      runs-reports/
      recommendations/
    entities/
      photo/
      pair/
      event/
      interval/
      cluster/
      hypothesis/
    shared/
      api/
      ui/
      dates/
      rendering/
      workers/
      design-tokens/
      forensic-status/
  tests/
  e2e/
  stories/
```

## Timeline renderer

UI v5 использует гибридный renderer:

### DOM

- toolbar/dropdowns;
- visible virtualized thumbnails;
- focus targets;
- tooltip/drawer;
- accessibility alternatives.

### Canvas 2D

- metric lines/points;
- pair bridges;
- change/return markers;
- intervals/eras;
- density navigator;
- matrices и clustering chronology.

### Worker

- viewport filtering;
- LOD/aggregation;
- histogram/geometry preparation;
- similarity tint;
- binary decoding.

Все слои используют единый `TemporalViewport`. На дальнем zoom показывается density/representative frames; при приближении раскрываются реальные photos без изменения даты.

## 3D и морфинг на MacBook M1

Есть два разных GPU/CPU контура.

### Python Stage 1

3DDFA extraction по текущей validated policy запускается на CPU. PyTorch MPS не включается автоматически без отдельной проверки численной эквивалентности и bundled renderer path.

### UI morphing

Frontend morphing работает на Apple GPU через WebGL2/Three.js. CUDA и PyTorch MPS не нужны. Браузер реализует WebGL2 поверх графического стека macOS.

Реализация:

- topology/indices загружаются один раз;
- A/B vertex positions находятся в `BufferAttribute`;
- slider обновляет `uMorphFactor`;
- vertex shader вычисляет `mix(positionA, positionB, factor)`;
- heatmap использует per-vertex residual/color attribute;
- React не пересчитывает 35 709 вершин на каждый кадр;
- WebGPU возможен позже как optional acceleration, но WebGL2 остаётся baseline;
- при software fallback/WebGL context loss показывается явный degraded state.

Morphing — visualization-only. Интерполированное положение не создаёт measurement record и не поступает в Stage 2.

## Комбинации 3D-слоёв

Независимые controls:

- mesh;
- texture;
- wireframe;
- heatmap;
- LDM106;
- LDM134;
- displacement vectors;
- visibility;
- excluded expression zones;
- neutral/original expression.

Настройки heatmap и света открываются overlay непосредственно над моделью. Range selector должен поддерживать переход `1999–2026 → 2009–2012` без смены страницы.

## Экранные основы

- Main timeline: R23 + R04 + R21 + R05;
- Pair Analysis: R19 + R18 + R11;
- Morphing: R20 + R10;
- Clustering: R15 + R12; embedding R13 secondary;
- Hypothesis Validation: R16 + R17;
- Recommendations: R22;
- Data/provenance: R03;
- Pose coverage: R02.

R07 не используется как visual base из-за микротипографики. R14 cloud — только optional presentation mode. R09 — неосновной дубликат.

## API policy

UI v5 не должен поддерживать собственную копию Python backend. Канонический API находится в root `app6/`.

Новые contracts должны обеспечивать:

- version/schema;
- run/profile IDs;
- source mode;
- explicit `not_a_verdict`;
- missing/limited states;
- applicability/calibration;
- pagination/viewport where needed;
- binary full-mesh transport;
- SSE job progress.

TypeScript API client генерируется из OpenAPI; ручные adapters используются только для view-model normalization.

## Clustering

Clustering вычисляется backend-side. UI получает records, membership, outlier score, transitions, stability и sensitivity runs. Default mode — chronology. Всегда показывается `cluster ≠ identity`.

## Hypothesis Validation

Private-only workspace. Legacy/current/migration показываются отдельно. Systematic shift является sensitivity profile с audit trail, а не способом максимизировать agreement. Private result не попадает в Stage 3/public export.

## Accessibility

- keyboard-first controls;
- focus management Radix;
- цвет + shape + text;
- Canvas/WebGL имеют screen-reader summary и table alternative;
- `prefers-reduced-motion`;
- browser zoom 200%;
- критичные controls не меньше 13–14 px;
- body/metrics обычно не меньше 12 px;
- contrast и axe gate.

## Scripts

Текущий `package.json` содержит:

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 4175",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest",
    "test:e2e": "playwright test",
    "build": "tsc --noEmit && vite build",
    "storybook": "storybook dev -p 6006"
  }
}
```

Для локального E2E один раз выполнить `npx playwright install chromium`. Если CDN browser binary недоступен, unit/typecheck/lint/build остаются проверяемыми, а E2E фиксируется как environment blocker, не как успешный gate.

## Definition of Done

- no production mocks/random measurements;
- OpenAPI/typecheck green;
- unit/contract/E2E/visual/a11y tests green;
- null and excluded states verified;
- 1900-photo timeline performance measured;
- M1 WebGL2 morph performance measured;
- keyboard/focus path verified;
- private/public boundaries verified;
- 25-factor `SKILL.md` score ≥98/100;
- build reproducible from lockfile.
