# DEEPUTIN UI v5 — Design System DS 0.1

**Runnable catalog:** `/design-system`  
**Code:** `ui-v5/src/features/design-system/`  
**Tokens:** `ui-v5/src/styles/tokens.css`  
**Primitives:** `ui-v5/src/shared/ui/primitives.tsx`

## 1. Назначение

Design System — обязательный внутренний раздел и source of truth для всех будущих страниц. Он фиксирует не только внешний вид, но и forensic semantics:

- photo ≠ pair ≠ event ≠ interval;
- missing ≠ zero;
- limited ≠ candidate;
- candidate ≠ verdict;
- private ≠ public;
- view-only threshold ≠ scientific profile;
- interpolated morph frame ≠ measurement.

Новый визуальный pattern сначала добавляется в `/design-system`, проходит keyboard/a11y/states review и только после этого используется в продуктовой странице.

## 2. Foundations

### Цвета

Surface:

- canvas;
- base;
- raised;
- overlay;
- subtle;
- hover;
- active.

Semantic:

- cyan — navigation/information/A;
- green — accepted/within expected range;
- amber — limitation/review needed/B;
- red — candidate/critical review, не identity verdict;
- violet — private/hypothesis;
- gray/dashed — missing/not applicable.

Цвет всегда дублируется icon/shape/text.

### Typography

- sans — интерфейс и объяснения;
- mono — IDs, dates, metrics, hashes, units;
- tabular numbers — все динамические числа;
- critical controls ≥13 px;
- body/metrics обычно ≥12 px;
- micro labels допускаются 10–11 px только как secondary metadata.

### Grid

- базовый шаг 4 px;
- controls 28/34/40 px;
- radius 2/4/7/10/full;
- hairline border 1 px;
- z-index tokens для sticky/popover/dialog/toast.

## 3. Actions

Компоненты:

- `Button`: primary/secondary/ghost/danger;
- `IconButton` с обязательным label/title;
- sizes sm/md/lg;
- loading/disabled/pressed/focus states;
- destructive action всегда через preview/confirm;
- primary action — не более одного на локальный context.

## 4. Form controls

- text/search/date/URL;
- select/combobox;
- checkbox;
- radio;
- switch;
- single/dual range slider;
- validation/hint/error;
- view-only/scientific scope badge;
- before/after count для filters;
- reset/save version actions.

## 5. Status vocabulary

Canonical states:

- accepted;
- within noise;
- info;
- warning;
- limited;
- candidate;
- private;
- missing;
- excluded;
- blocked;
- running;
- complete;
- failed.

Status component всегда имеет label и icon. Tooltip раскрывает source/reason.

## 6. Navigation

- глобальная top bar;
- context toolbar;
- dropdown/popover;
- tabs;
- breadcrumb;
- pagination;
- command palette;
- bottom status bar.

На timeline постоянный широкий sidebar запрещён.

## 7. Data display

- `MetricValue`: label/value/unit/trend/source state;
- sparkline;
- histogram;
- distribution threshold;
- evidence table;
- quality ring;
- progress;
- calibrated/diagnostic badge;
- explicit `—`/no data.

## 8. Temporal grammar

### PhotoPoint

Одна дата и одна X-координата для thumbnail, graph dots и markers.

### PairBridge

Связь `x(A) → x(B)`, отдельная от photo points.

### EventMarker

Change/return/conflict/review на одной дате или boundary.

### IntervalBand

Era/range/regime/coverage от `from` до `to`.

UI fixture в каталоге не является research data.

## 9. Forensic components

### ApplicabilityCard

Показывает до метрик:

- pose/bin;
- axis gaps;
- quality;
- visibility/common points;
- calibration;
- provenance;
- accepted/limited/excluded.

### ClaimCard

- claim ID;
- allowed strength;
- public text;
- evidence count;
- denominator/coverage;
- review state.

### PairCard/A-B

- cyan A;
- amber B;
- dates/quality;
- swap/open/clear;
- цвет не означает outcome.

### ReviewCard

- reviewer identity;
- blind session;
- decision;
- rationale;
- timestamp;
- disagreement/adjudication.

## 10. Overlays

- tooltip — короткое объяснение;
- popover — live/context controls;
- dialog — подтверждение/preview;
- drawer — подробности сущности;
- toast — завершённое фоновое действие;
- notification — критическая ошибка;
- context menu — быстрые действия.

Требования:

- focus trap;
- Escape;
- focus return;
- no loss of page context;
- no nested modal chains.

## 11. System states

Каждая страница/виджет имеет:

- skeleton/loading;
- empty;
- filtered-empty;
- error;
- blocked prerequisite;
- degraded/limited;
- offline/API unavailable;
- permission denied;
- retry/corrective action.

Production UI никогда не заменяет error/empty фиктивным результатом.

## 12. Publication components

- publication readiness;
- claim row/card;
- source/evidence link;
- public/technical split editor;
- skeptic objection;
- rights blocker;
- translation state;
- figure state;
- lint result;
- machine-review import.

## 13. Layer controls

Для 3D/morph:

- mesh;
- texture;
- wireframe;
- heatmap;
- LDM106/134;
- vectors;
- visible only;
- expression exclusions.

Checkboxes допускают комбинации. Radio используется только для взаимоисключающих modes.

## 14. Themes and density

Themes:

- dark — рабочая default;
- light — отчёты/печать/яркое окружение;
- future high-contrast.

Density:

- comfortable;
- compact.

Scientific meaning и status colors не меняются при theme/density switch.

## 15. Accessibility gate

- keyboard path;
- visible focus;
- semantic labels;
- icon aria-label;
- no color-only status;
- contrast target WCAG AA;
- 200% browser zoom;
- reduced motion;
- Canvas/WebGL summary + table alternative;
- screen-reader announcements для jobs/errors;
- RU/EN meaning parity.

## 16. Governance

Для нового компонента обязательно:

1. описать entity и use case;
2. использовать tokens, не hardcoded random colors;
3. добавить normal/hover/focus/disabled/loading/error states;
4. добавить keyboard behavior;
5. добавить dark/light;
6. добавить compact/comfortable, если применимо;
7. добавить test;
8. добавить пример в `/design-system`;
9. пройти screenshot/a11y review;
10. только затем использовать на рабочей странице.

## 17. Anti-patterns

- копирование CSS между features;
- новый цвет без token;
- red = different person;
- tooltip как единственный источник критичной информации;
- icon-only без label;
- modal поверх modal;
- scientific slider без scope/version;
- null как zero;
- thumbnail horizontal jitter относительно даты;
- cluster label как identity;
- fixture без явной маркировки;
- microscopic text ради плотности;
- permanent timeline sidebar.

## 18. Acceptance DS 0.1

- route `/design-system` работает;
- tokens centralized;
- primitives typed;
- dark/light;
- density switch;
- interactive Radix controls;
- timeline grammar documented;
- forensic statuses documented;
- system states documented;
- tests/typecheck/lint/build green;
- E2E test присутствует; browser binary gate выполняется в CI/окружении с Playwright browsers.
