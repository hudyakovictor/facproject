---
name: deeputin-forensic-workstation
description: Проектирование, реализация и проверка DEEPUTIN Stage 1/2/3, FastAPI и React UI v5 с сохранением provenance, calibration, nine-pose policy, not-a-verdict и private/public isolation.
---

# SKILL.md — operational playbook DEEPUTIN

## 1. Когда применять этот skill

Использовать для любой задачи, затрагивающей:

- Stage 1 extraction;
- Stage 2 pair/chronology analysis;
- Stage 2B/private hypothesis retest;
- Stage 3/report/export;
- FastAPI/OpenAPI;
- UI v5 timeline, pair analysis, morphing, clustering, calibration или hypotheses;
- data/provenance/jobs/profiles;
- Stage 2→3 journalist handoff и многоаудиторные publication drafts;
- testing, CI, documentation и release readiness.

Не использовать этот skill как разрешение делать вывод о личности. Он описывает инженерный процесс и границы интерпретации.

## 2. Цель skill

Преобразовать пользовательское ТЗ в:

1. проверяемый data contract;
2. минимальный архитектурно правильный diff;
3. честную визуализацию реальных artifacts;
4. tests и acceptance evidence;
5. документацию, позволяющую следующему разработчику воспроизвести решение.

## 3. Входной контекст

Перед работой собрать:

- точную пользовательскую задачу;
- затрагиваемую сущность;
- source artifact/schema;
- текущую реализацию и tests;
- relevant design render;
- runtime constraints;
- public/private scope;
- необходимость реальных weights/dataset;
- допустимые изменения scientific policy.

Если файл не передан из-за размера, не объявлять его несуществующим в локальной системе. Различать:

```text
not present in current checkout
not present in owner environment
not generated yet
not applicable
```

## 4. Стандартный workflow

## Phase 1 — Discover

1. Прочитать `AGENTS.md` и scoped instructions.
2. Найти routes, schemas, types и artifacts.
3. Проверить git status.
4. Определить, нет ли двух реализаций одного contract.
5. Не полагаться на README без сверки с кодом/tests.
6. Зафиксировать external prerequisites.

**Выход:** краткая карта source → transform → API → view.

## Phase 2 — Frame

Записать:

- user story;
- entity type;
- inputs;
- outputs;
- invariants;
- empty/error/limited states;
- performance target;
- tests;
- out-of-scope.

**Выход:** acceptance checklist до написания кода.

## Phase 3 — Design

Выбрать самый простой путь, не нарушающий boundaries:

- scientific calculation → Python backend;
- server state → TanStack Query;
- workspace state → Zustand;
- shareable view → URL;
- dense timeline → Canvas + virtualized DOM;
- 3D → Three.js/WebGL2;
- settings → contextual UI + versioned profile;
- heavy transformation → Worker;
- publication → отдельный read-only contract.

**Выход:** план файлов и contract changes.

## Phase 4 — Implement

Порядок:

1. schema/type;
2. backend/data adapter;
3. contract test;
4. frontend query/view model;
5. renderer/component;
6. interactions;
7. error/empty/limited states;
8. accessibility;
9. documentation.

Избегать big-bang rewrite. Переиспользовать только проверенные data contracts и алгоритмические adapters; целевой visual shell и feature architecture создаются в `ui-v5/`.

## Phase 5 — Verify

- unit;
- contract;
- scenario;
- typecheck;
- build;
- E2E;
- visual regression;
- accessibility;
- performance;
- no-mock scan;
- forensic wording;
- 25-factor score.

## Phase 6 — Report

Финальный ответ содержит:

- что сделано;
- изменённые файлы;
- source contracts;
- tests и фактический результат;
- что не проверено;
- external prerequisites;
- следующий безопасный шаг.

## 5. Рубрика 98/100 по 25 факторам

Каждый фактор получает:

- **4** — полностью выполнен и подтверждён evidence;
- **3** — выполнен, но есть малое документированное ограничение;
- **2** — частично;
- **1** — номинально;
- **0** — отсутствует/нарушен.

Максимум: 25 × 4 = **100**.  
Production-ready threshold: **≥98** и ни одного P0-нарушения.  
`N/A` разрешён только с объяснением; итог нормируется, но нельзя объявить N/A фактор, который прямо затронут задачей.

| ID | Фактор | 4/4 означает |
|---|---|---|
| Q01 | Fidelity to request | Реализовано точное пользовательское поведение, не удобная подмена задачи |
| Q02 | Real-data grounding | Каждая визуальная сущность связана с реальным artifact/field |
| Q03 | Provenance | Source/date/hash/run/schema/reviewer trace не теряется |
| Q04 | Entity semantics | Photo/pair/event/interval/run/hypothesis не смешаны |
| Q05 | Scientific invariants | 9 bins, raw space, pose/visibility/FDR policy сохранены |
| Q06 | Calibration rigor | Calibration/applicability/coverage/uncertainty показаны и не подгоняются на main data |
| Q07 | Confounders | Quality, pose, visibility, expression, duplicates, source domain обработаны |
| Q08 | Missing-data honesty | null/NaN/excluded/inapplicable не превращены в 0/normal |
| Q09 | Forensic wording | Candidate не превращён в identity/medical verdict |
| Q10 | Privacy/security | Private/public, auth/path/upload/destructive risks учтены |
| Q11 | Architecture fit | Logic находится в правильном слое, нет нового split-brain |
| Q12 | Types/contracts | Versioned schema, strict types, validation и compatibility |
| Q13 | Visual hierarchy | Главный объект/сигнал/действие читаются сразу |
| Q14 | Contextual controls | Настройка находится рядом с результатом; scope изменения понятен |
| Q15 | Timeline invariant | Одно фото = одна X; pair/event/interval корректны |
| Q16 | Nine-pose workflow | Один bin default, 9-bin applicability и cross-bin boundary честны |
| Q17 | Scale/performance | 1900 фото, 35k vertices, virtualization/worker/GPU измерены |
| Q18 | Apple M1 compatibility | CPU extraction и WebGL2 GPU rendering не смешаны; fallback проверен |
| Q19 | Accessibility | Keyboard/focus/contrast/non-color/alternatives/reduced motion |
| Q20 | Tests | Unit/contract/E2E/visual/a11y соответствуют риску |
| Q21 | Determinism | Stable ordering, version/fingerprint, no random production result |
| Q22 | Observability | Loading/progress/error/log/retry/cancel/degraded state видимы |
| Q23 | Reversibility | Preview, undo view actions, immutable Stage 1, safe migrations |
| Q24 | Documentation | README/AGENTS/schema/decision/limitations обновлены |
| Q25 | Delivery evidence | Tests/results/files/limitations сообщены; repo чист от secrets/bulk data |

### Self-review template

```text
Q01 4 — acceptance X verified by test Y
Q02 4 — fields come from endpoint/schema Z
...
Q18 3 — WebGL2 checked on Chrome M1, Safari pending
...
TOTAL 99/100
P0 violations: none
Open limitations: Safari visual snapshot pending
```

Не ставить 4 без evidence. «Код выглядит правильно» — максимум 2.

## 6. Playbook: UI v5 timeline

### Required model

```ts
type TimelineEntity =
  | PhotoPoint
  | PairBridge
  | EventMarker
  | IntervalBand;
```

### Required properties

- один active pose;
- one temporal transform;
- photo row ниже центра;
- metrics сверху;
- markers снизу;
- years внизу;
- top contextual panels;
- no permanent sidebar;
- cursor-anchored zoom;
- horizontal pan;
- brush range;
- LOD/virtualization;
- tooltip + accessible table alternative.

### Rendering split

- DOM: controls, visible thumbnails, focus targets;
- Canvas: metric/event/pair/interval layers;
- Worker: aggregation/geometry;
- TanStack Query: data;
- Zustand: viewport/layers/A-B;
- URL: pose/range/run/profile.

### Timeline tests

1. Все photo-level layers используют одинаковый `x(photo.epochDay)`.
2. Pair bridge endpoints совпадают с A/B points.
3. Interval не создаёт fake photo.
4. Zoom сохраняет date under cursor.
5. Hidden/excluded photo остаётся учтённым.
6. 1900 records не создают 1900 heavy DOM cards вне viewport.
7. null разрывает line, а не падает в zero baseline.
8. display filter не мутирует Stage 1.

## 7. Playbook: Pair Analysis

Объединить:

- большие A/B views;
- LDM106/134 vectors;
- calibrated/diagnostic thresholds;
- 4-row virtualized thumbnails;
- A-relative similarity tint;
- time-range selector;
- early reference period;
- provenance/applicability drawer;
- links to Morphing/Photo Inspector.

### Pair guard

До score показывать:

- same pose bin;
- yaw/pitch/roll gaps;
- common visibility;
- quality/expression;
- date/source conflict;
- calibration coverage;
- coordinate space.

Similarity tint всегда указывает metric, run и calibration state. Красный не означает «другой человек».

## 8. Playbook: Morphing/3D

### M1 path

- WebGL2 baseline;
- Three.js `BufferGeometry`;
- GPU vertex shader interpolation;
- `requestAnimationFrame`/R3F frame loop;
- uniform update per scrub;
- no React array interpolation per frame;
- `powerPreference: high-performance` как preference, не гарантия;
- capability/context-loss handling;
- WebGPU только optional enhancement.

### Data path

```text
topology once
positions A/B binary
texture A/B
residual/vertex colors
landmarks/zones
```

### Required labels

- real photo anchors;
- interpolated frame;
- visualization only;
- active date range;
- active layers;
- heat scale and calibrated/diagnostic source.

### Performance acceptance

- scrub measured on target M1;
- no long main-thread task >50 ms during interaction;
- no mesh refetch on every frame;
- texture/topology cache bounded;
- context loss does not corrupt analysis state.

## 9. Playbook: Clustering

### Backend responsibilities

- feature extraction/selection;
- normalization;
- algorithm;
- membership/outlier;
- stability/bootstrap;
- sensitivity runs;
- transitions/change boundaries;
- versioned artifact.

### Frontend responsibilities

- render chronology/embedding;
- filter pose/period/feature run;
- expose params and scope;
- compare sensitivity;
- open pair/member;
- never relabel cluster as identity.

### Required metadata

```text
run_id
feature_space
normalization
pose_policy
algorithm + params
random_seed if applicable
record coverage
excluded reasons
stability
schema_version
```

## 10. Playbook: Private hypothesis validation

1. Load private schema, not public report.
2. Separate three entities/pair relations only if source data maps them explicitly.
3. Preserve immutable legacy value and source.
4. Display current measurement separately.
5. Apply migration/correction as a named sensitivity profile.
6. Show denominator, missing count, pose coverage and CI.
7. Log every manual adjustment.
8. Do not optimize for maximum agreement.
9. Keep private output out of Stage 3/public exports.
10. Support blind labels.

## 11. Playbook: Backend/API

- add Pydantic models instead of untyped dict where practical;
- version response schemas;
- use explicit `not_a_verdict` on public analytical payloads;
- return 409/422 with actionable detail for unavailable artifacts;
- contain filesystem paths;
- no write on GET except explicitly documented first-run registry behavior;
- no hidden fallback data;
- OpenAPI snapshot diff reviewed;
- contract tests cover success + missing + invalid + limited;
- heavy binary data streamed/compressed/cached.

## 12. Playbook: Stage 1/2 scientific changes

Before any change:

1. state hypothesis;
2. identify calibration data;
3. define null/negative control;
4. define operating point;
5. define contamination/LOPO effect;
6. version schema/config;
7. add regression and scenario tests;
8. prevent mixing old/new artifacts;
9. document interpretation boundary.

A UI request alone is not justification to alter scientific thresholds.

## 13. Playbook: Documentation-only task

Documentation is code-adjacent and must be verified:

- commands exist;
- paths are current;
- links resolve;
- filenames respect macOS case-insensitive filesystems;
- no claim of passed test without current output;
- external/local assets described accurately;
- current vs planned clearly separated;
- decisions link to source docs;
- examples do not look like research results.

## 14. Playbook: Publication drafts

### Four synchronized audiences

1. General reader — plain language and examples.
2. Technical reviewer — exact contracts, statistics and reproducibility.
3. Skeptical reviewer — alternatives, negative controls and falsification.
4. Machine reviewer — structured claims/evidence/assumptions.

### Required outputs

- Stage 2 `journalist_handoff.json`;
- Stage 3 plain-language method draft;
- technical appendix;
- results-story draft;
- skeptic Q&A;
- independent demonstration protocol;
- claims ledger;
- machine-review packet;
- glossary and draft lint;
- file/digest manifest.

### Claim contract

Every material claim carries:

```text
claim_id
kind
plain_language
technical_language
allowed_strength
evidence_refs
limitations
review_state
reviewer/adjudication
```

### Editorial rules

- Method series remains independent of the investigation result.
- Every number keeps a denominator.
- Observation, interpretation and external reporting are separate.
- Candidate language cannot be strengthened during copy-editing.
- The strongest alternative explanation is placed beside the finding.
- A public-figure example is same-person method demonstration only, with rights/provenance and no claim about that person.
- AI audits claim-to-evidence consistency but is not an independent forensic reviewer.
- Publication requires technical, provenance, legal and editorial review.

### Publication tests

1. Drafts are deterministic for the same artifacts.
2. Every claim has evidence refs.
3. Zero candidates is not worded as proof of absence.
4. Limited counts retain denominators.
5. Unsupported assertive patterns fail lint.
6. Private hypotheses do not enter public bundle.
7. Machine packet and human drafts contain the same claim IDs.
8. Publication manifest contains digests for every draft file.

Full contract: `docs/PUBLICATION_PIPELINE.md`.

## 15. Anti-patterns

Reject a solution if it:

- duplicates `app6` under a new UI directory;
- uses a giant untyped global store;
- puts all server data in Zustand;
- renders dense timeline as tens of thousands of SVG/DOM nodes;
- performs BFM interpolation in React state;
- runs clustering in the browser for production results;
- stores scientific thresholds only client-side;
- labels heuristic as probability/confidence without calibration;
- uses color alone;
- hides excluded rows;
- silently accepts unknown schema;
- publishes private hypotheses;
- treats design screenshot numbers as fixtures;
- changes Stage 1 during UI filtering;
- announces 98/100 without a completed rubric.

## 16. Completion report template

```markdown
## Сделано
- ...

## Контракты
- source: ...
- schema/API: ...
- migration: ...

## Проверки
- command — PASS/FAIL, exact count

## 25-factor gate
- total: 99/100
- deductions: Q18 −1, Safari check pending
- P0 violations: none

## Ограничения
- ...

## Следующий шаг
- ...
```
