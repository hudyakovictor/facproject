# DEEPUTIN Pipeline Observatory & Iteration Manager

> Системная архитектура интерфейса для наблюдения, тестирования, калибровки и поэтапного развития pipeline `app6`.

**Текущая готовность реализации: 44/100 (44%). Iteration 6 завершена.**

Прогресс: [`PROGRESS.md`](./PROGRESS.md) · Отчёты: [`Iteration 1`](./ITERATION_1_REPORT.md) · [`Iteration 2`](./ITERATION_2_REPORT.md) · [`Iteration 6`](./ITERATION_3_REPORT.md) · React Flow: [`DESIGN_DECISION_REACT_FLOW.md`](./DESIGN_DECISION_REACT_FLOW.md)

## Назначение

Это не обычный dashboard и не публичный журналистский отчёт. Это локальный инженерно-аналитический мост между журналистом и разработчиками:

```text
Журналист
   ↓
Понятная карта pipeline
   ↓
Запуск тестов
   ↓
Ошибки и незакрытые функции
   ↓
Автоматический план следующей итерации
   ↓
Fix Capsule для разработчика
   ↓
Patch от разработчика
   ↓
Изолированная проверка
   ↓
Принять или откатить
```

Журналист видит весь pipeline понятным языком, запускает проверки, изучает результаты и формирует следующую итерацию. Разработчик получает воспроизводимое ТЗ, логи, ожидаемое поведение и критерии приёмки. Полученное исправление проверяется изолированно, сравнивается с предыдущей версией и только затем принимается либо отклоняется.

Оценка соответствия проекту: **99/100**. Оставшийся 1% связан с тем, что статический AST-анализ не может без runtime полностью восстановить динамические Python-вызовы, а научную корректность калибровки нельзя определить только кодом.

---

## 1. Изоляция от `app6`

```text
project/
├── app6/                      # основной pipeline
└── ui/                        # полностью отдельный интерфейс
    ├── frontend/
    ├── backend/
    ├── config/
    ├── contracts/
    ├── templates/
    ├── scenarios/
    ├── generated/
    └── .data/
```

`ui` рассматривает `app6` как read-only наблюдаемый проект. Он сканирует Python-код через AST, читает `STATUS_AUDIT.py`, анализирует `test_module`, связывает тесты с функциями, наблюдает изменения и запускает разрешённые операции через subprocess.

В `app6` не создаются UI-кеши, layouts, runtime traces, task-файлы, backups, thumbnails, базы данных или patch bundles. Локальная `ui/.data/` хранит только компактный control plane: SQLite-индекс, настройки, layouts и небольшие журналы. Все тяжёлые извлечённые данные, Stage outputs, caches, run artifacts и previews по умолчанию находятся на съёмном диске в `/Volumes/SDCARD/uidata/`. Если диск не смонтирован или не прошёл проверку свободного места/записи/идентичности тома, тяжёлый запуск блокируется без скрытого fallback на системный диск.

UI запрещено:

- создавать `.ui` и cache внутри `app6`;
- писать историю тестов в `STATUS_AUDIT.py`;
- сохранять layouts и thumbnails рядом с pipeline;
- автоматически менять thresholds;
- автоматически редактировать исходный код;
- сохранять runtime events внутри `app6`.

Допустимы read-only анализ, контролируемый запуск entry points и чтение произведённых pipeline артефактов.

---

## 2. Интерфейс для журналиста

Основной заголовок каждого узла — понятное объяснение. Техническое имя показывается ниже мелким серым моноширинным текстом.

```text
┌────────────────────────────────────────────┐
│ Проверка совпадения ракурсов           ●   │
│ compare_landmarks() · stage2/core.py       │
├────────────────────────────────────────────┤
│ Сравнивает две реконструкции только при    │
│ совместимом положении головы.              │
│                                            │
│ Если проверка не пройдена, геометрическое  │
│ сравнение нельзя использовать.             │
├────────────────────────────────────────────┤
│ Синтетические тесты     5/5                 │
│ Реальные фотографии    не проверено        │
│ Последний запуск        успешно             │
��────────────────────────────────────────────┘
```

Приоритет информации:

1. понятное название;
2. что делает функция;
3. почему она важна;
4. что означает ошибка;
5. состояние готовности;
6. результат последнего теста;
7. техническое имя;
8. путь и строка исходного кода.

### Справочник описаний

Описания хранятся отдельно:

```text
ui/config/function_catalog.yaml
```

```yaml
functions:
  app6.stage2.core.compare_landmarks:
    journalist_title:
      ru: Проверка геометрического различия лица
    short_description:
      ru: Сравнивает ключевые точки реконструкций после нормализации ракурса.
    why_important:
      ru: Это один из основных каналов измерения геометрических изменений.
    failure_impact:
      ru: Ошибка может создать ложный сигнал или скрыть превышение reconstruction noise.
    technical_name: compare_landmarks
    source: app6/stage2/core.py
    stage: stage2
    category: geometry
    criticality: critical
    required_tests:
      - same_pose_pair
      - cross_pose_rejection
      - residual_pose_rejection
      - insufficient_visibility
    closure_policy: critical_geometry
```

Первичный текст можно извлекать из имени, docstring, комментариев, `STATUS_AUDIT.py` и тестов. Журналистское описание редактируется в UI и не изменяет `app6`.

---

## 3. Главный экран: Infinite Pipeline Canvas

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Project · Branch · Code hash · Model · Dataset · Run · Health       │
├──────────────┬───────────────────────────────────────┬──────────────┤
│ Навигатор    │         INFINITE PIPELINE CANVAS      │ Inspector    │
│ Stages       │ Input → Detection → 3DDFA → Stage 2   │ Function     │
│ Runs         │                 ↓                     │ Tests        │
│ Scenarios    │             Evidence → Stage 3        │ Metrics      │
│ Gates        │                                       │ Artifacts    │
├──────────────┴───────────────────────────────────────┴──────────────┤
│                    ZOOMABLE EXECUTION TIMELINE                       │
├─────────────────────────────────────────────────────────────────────┤
│ Logs · Events · Warnings · Errors · Resource usage                   │
└─────────────────────────────────────────────────────────────────────┘
```

Canvas — основной интерфейс. Остальные возможности открываются как панели, drawers и режимы полотна.

### Семантический zoom

- При сильном отдалении: Dataset, Stage 1, Calibration, Stage 2, Stage 2B, Stage 3, Validation, Testing, Visualization.
- Средний масштаб: модули `loaders`, `core`, `motion`, `descriptors`, `calibration`, `chronology`, `evidence`.
- Близкий масштаб: классы и функции.
- Максимальный масштаб: сигнатура, входы, выходы, типы, метрики, тесты, артефакты и exceptions.

Пример детального узла:

```text
┌────────────────────────────────────┐
│ aligned_point_motion()         ●   │
│ stage2/motion.py:48                │
├────────────────────────────────────┤
│ INPUT                              │
│ Record a · Record b                │
│ landmark_count: 106 | 134          │
│ identity_only: bool                │
├────────────────────────────────────┤
│ OUTPUT                             │
│ vectors: float32[N,3]              │
│ magnitude: float32[N]              │
│ visible: bool[N] · status: enum    │
├────────────────────────────────────┤
│ Implementation  ██████████ 100%    │
│ Unit tests      ██████████ 100%    │
│ Synthetic       █████████░  90%    │
│ Real photos     ██░░░░░░░░  44%    │
│ Calibration     ██████░░░░  60%    │
└────────────────────────────────────┘
```

---

## 4. Состояния функций

| Цвет/вид | Состояние | Значение |
|---|---|---|
| Тёмно-серый | `discovered` | функция найдена, состояние неизвестно |
| Светло-серый | `implemented_unverified` | код есть, подтверждения нет |
| Жёлтый | `synthetic_verified` | синтетические сценарии прошли |
| Голубой | `integration_verified` | интеграционные тесты прошли |
| Фиолетовый | `real_photo_verified` | проверено на реальных фото |
| Оранжевый | `calibration_required` | код работает, блокирует калибровка |
| Зелёный | `release_ready` | закрыты все обязательные gates |
| Красный | `failing` | обязательный тест упал |
| Красное кольцо | `runtime_error` | ошибка текущего запуска |
| Фиолетовый пунктир | `experimental` | экспериментальная функция |
| Серый зачёркнутый | `deprecated` | больше не используется |
| Бирюзовый | `visualization_only` | только визуализация |

Цвет всегда дублируется иконкой, подписью и формой рамки.

У функции два независимых статуса:

- **readiness** — сохраняемая зрелость;
- **runtime** — `idle`, `queued`, `running`, `passed`, `warning`, `failed`, `cancelled`, `skipped`.

Фон узла показывает readiness, внешнее кольцо — runtime. Успешный единичный вызов не делает calibration-required функцию зелёной.

### Closure policy

Обычная utility-функция требует отсутствия stub, прохождения unit и contract tests и отсутствия regression. Critical Stage 1 функция дополнительно требует synthetic, integration, real-photo и output validation. Calibration-функция требует dataset, holdout, sensitivity и утверждённый bundle. Evidence-функция требует исчерпывающего mapping, limited-state tests, public gate и отсутствия visual leakage.

---

## 5. Наблюдение без изменения pipeline

### Static AST Indexer

`ui/backend/indexer/` использует `ast.parse()` и не импортирует pipeline. Извлекаются модули, классы, функции, методы, сигнатуры, type hints, docstrings, imports, вызовы, константы, `log_status`, `status_warning` и source locations.

Связи помечаются как:

```text
confirmed edge
heuristic edge
runtime-observed edge
manual override
```

### Status Adapter

Read-only читает `app6/STATUS_AUDIT.py`: complete, need_testing, in_progress, experimental, deprecated, blocker, note.

### Test Indexer

Сканирует `app6/test_module/`, извлекает тесты и приблизительные связи. Неоднозначные связи задаются в:

```text
ui/config/test_bindings.yaml
```

### Runtime Tracer

`ui/backend/runtime/instrumented_runner.py` запускает pipeline в отдельном subprocess, использует `sys.setprofile`/`threading.setprofile`, фильтрует события по пути `app6` и отправляет JSONL/WebSocket события call, return, warning, exception, artifact.

### File Watcher

Read-only наблюдает `app6/**/*.py`, `STATUS_AUDIT.py`, `test_module/**/*.py`, contracts. После debounce переиндексируется только изменённый файл, пересчитываются затронутые узлы и canvas обновляется через WebSocket.

---

## 6. Live execution

При запуске теста активный узел подсвечивается, по ребру идёт импульс, выводится duration, создаваемые артефакты появляются рядом, следующий узел активируется, timeline получает span. Ошибка помечает первичный узел, а downstream получает `blocked_by_upstream`, а не ложный статус «сломано».

Переключаемые слои canvas:

- Architecture;
- Runtime;
- Readiness;
- Tests;
- Calibration;
- Metrics;
- Artifacts;
- Evidence;
- Regression;
- Performance.

### Exploded Pipeline

```text
Photo
→ RetinaFace crop
→ Reconstruction NPZ
→ Pose bin
→ Pair
→ Motion vectors
→ Calibration reference
→ Robust Z
→ Evidence state
→ Change point
→ Report card
```

### Data Lineage

Выбор `p95_point_z` оставляет цепочку producer → transformations → artifact → consumers → frontend component. Это связывает код с будущим `INTERFACE_CONTRACT.yaml`.

---

## 7. Timeline и replay

Timeline — вторая о��новная часть интерфейса. Tracks группируются по stage/module/function. Колесо мыши масштабирует относительно курсора, `Shift+wheel` выполняет горизонтальный pan, `Alt+wheel` — вертикальный, drag перемещает, двойной клик приближает, `F` показывает весь run.

Time scrubber возвращает canvas в выбранный момент: завершённые, активные, ещё не вызванные функции, существовавшие артефакты и метрики. Выбор узла фильтрует timeline; выбор span центрирует canvas и открывает inputs/outputs этого вызова.

---

## 8. Function Inspector

Вкладки:

- **Простыми словами** — назначение, важность, ошибка, зависимости, незакрытое;
- **Техническая** — ID, module, source, signature, types, exceptions;
- **Tests** — unit, synthetic, integration, real photo, calibration, история;
- **Runtime** — calls, mean/P95 duration, exceptions;
- **Inputs/Outputs** — shapes, nullable, примеры, contract fields;
- **Metrics** — связанные метрики, distributions, calibration;
- **Artifacts** — входные и выходные файлы;
- **Source** — read-only код;
- **Tasks** — ошибки, блокеры, patches, критерии закрытия.

Действия: Quick unit, bound tests, synthetic, integration, real-photo, calibration, dependency chain, downstream regression, compare runs.

---

## 9. Scenario Composer

Сценарии размещаются на canvas в стиле ComfyUI, но только из allowlisted nodes:

```text
Synthetic Mesh
→ Pose Transform
→ Expression Transform
→ Quality Degradation
→ Stage 1 Adapter
→ Stage 2 Pair
→ Expected Assertions
```

### Input nodes

Synthetic mesh, landmarks, real photo, Stage 1 record, pair, calibration dataset.

### Transform nodes

Pose, expression, camera, blur, noise, compression, occlusion, landmark/mesh displacement, visibility reduction.

### Pipeline nodes

Reconstruction, pose classification, chronology alignment, masks, pair comparison, motion, descriptors, chronology, evidence, Stage 3 projection.

### Assertion nodes

Status equals, evidence state equals, raises exception, metric in range, shape equals, no NaN, artifact exists, absent from change points.

Каждый scenario хранит seed, generator version, ground truth type, expected applicability, measurement status, evidence state и expected failure.

---

## 10. Результаты тестов простым языком

Первый уровень не показывает traceback:

```text
Тест завершён с проблемами
Проверено функций: 47
Успешно: 39
С ошибками: 3
Заблокировано: 4
Критических проблем: 1
```

Каждая проблема объясняется журналисту: что случилось, почему важно, что нельзя интерпретировать. Ниже мелко показываются техническая функция, файл, status, traceback, inputs, actual/expected, артефакты, версия кода, model и seed.

### Root-cause grouping

Один первичный сбой не превращается в десятки задач. UI группирует primary cause и downstream consequences. Типы проблем:

```text
code_defect · test_failure · regression · missing_implementation
missing_test · missing_real_photo_test · calibration_gap · dataset_gap
environment_error · schema_mismatch · performance_problem
documentation_gap · ui_observability_gap · expected_limitation · experimental_module
```

Calibration gap никогда не предлагает «придумать threshold»; задача требует данных, holdout и проверки.

---

## 11. Iteration Manager и правило 20/80

Приоритеты:

- **P0** — повреждение данных, ложный public result, смешение pose, bypass validation, потеря output, evidence boundary;
- **P1** — reconstruction, pose, alignment, visibility, pair QC, calibration, motion, evidence;
- **P2** — coverage, diagnostics, scenarios, calibration extension, observability;
- **P3** — оптимизация, UX, редкие edge cases, дополнительные графики;
- **Research** — thresholds, новые метрики и гипотезы без ground truth.

```text
Priority score =
Criticality × Downstream impact × Reproducibility × Confidence ÷ Estimated effort
```

P0 назначается также жёсткими правилами, а не только score.

Режим **«Показать задачи 80/20»** оставляет blockers, critical pipeline, calibration gaps, evidence risks, задачи с большим downstream impact и повторяющиеся regressions.

Kanban:

```text
Найдено → Проверяется → Готово к передаче → Передано разработчику
→ Patch получен → Тестируется → Принято / Отклонено / Отложено
```

---

## 12. Генератор технического задания

Автоматическое ТЗ содержит две части.

### Для журналиста

- проблема;
- почему важна;
- последствия;
- ожидаемое поведение;
- что нельзя интерпретировать.

### Для разработчика

- functions и files;
- reproduction command;
- actual/expected;
- stack trace и logs;
- affected downstream;
- code/model/contract version;
- acceptance criteria;
- required regression tests;
- out of scope;
- forbidden changes;
- rollback conditions.

Вероятная причина маркируется как `Confirmed`, `High-confidence hypothesis`, `Possible cause` или `Unknown`.

Постоянные ограничения автоматически добавляются во все ТЗ:

```text
Не изменять uv_module.
Texture/UV — только визуализация.
Не создавать identity verdict.
Не менять scientific thresholds без calibration data.
Не ослаблять validation ради прохождения теста.
```

---

## 13. Fix Capsule

Экспортируемый пакет:

```text
fix-capsule-P0-stage2-cross-pose.zip
├── TASK.md
├── task.json
├── PROJECT_RULES.md
├── REPRODUCTION.md
├── ACCEPTANCE_CRITERIA.md
├── baseline.json
├���─ affected_functions.json
├── affected_files.txt
├── logs/failure.log
├── scenarios/cross_pose_scenario.json
├── fixtures/synthetic_pair_summary.json
└── expected/expected_result.json
```

Fix Capsule строится по положительному allowlist. По умолчанию разрешены только компактные `.log`, `.txt`, `.json`, `.jsonl`, `.csv`, `.md`, `.yaml`/`.yml` и служебный manifest. Реальные фото, изображения, видео, веса, полный dataset, OBJ/MTL, NPZ/NPY, meshes, UV/texture, previews, SQLite, caches и тяжёлые run artifacts исключаются. Для бинарного результата exporter создаёт компактную JSON/CSV-сводку вместо копирования исходного файла. В manifest фиксируются исключённые категории, размеры, hashes и причины исключения.

Ответ разработчика:

```text
fix-response.zip
├── response.json
├── fix.patch
├── CHANGELOG.md
├── TEST_REPORT.md
├── added_tests.patch
└���─ notes/limitations.md
```

---

## 14. Patch Center

Patch не применяется к рабочей версии напрямую:

```text
Import patch
→ Verify task and base hash
→ Create backup
→ Create isolated Git worktree
→ git apply --check
→ Apply patch in worktree
→ Compile
→ Affected tests
→ Dependency tests
→ Full regression
→ Compare baseline/candidate
→ Accept or reject
```

Экран показывает base match, changed files, forbidden files, compile, tests, new warnings, removed/new failures.

Для diff используется Monaco Diff Editor. Отдельно подсвечиваются threshold changes, evidence mappings, UV/texture, удалённые тесты, weakened validation и exception suppression.

Patch требует ручного подтверждения, если затронут `uv_module`, texture включена в evidence, удалён тест, добавлен `except Exception: pass`, threshold изменён без calibration, отключена validation, схема изменена без migration, добавлен `NaN → 0`, изменён public gate или не совпадает base version.

---

## 15. Версии, backup и rollback

Каждое принятое исправление — отдельный commit. До и после создаются tags:

```text
dpo-before-TASK-P0-0024
dpo-after-TASK-P0-0024
```

Откат выполняется `git revert`, а не разрушительным `git reset --hard`.

Дополнительные source snapshots:

```text
/Volumes/SDCARD/uidata/backups/source/
├── 2026-07-24_130000_before_TASK-P0-0024.tar.zst
├── 2026-07-24_132500_after_TASK-P0-0024.tar.zst
└── backup_index.json
```

В backup входят source, Markdown, JSON/YAML contracts и tests. Не входят datasets, results, weights, caches, images и run NPZ. Периодически создаётся переносимый `git bundle`.

Version Center хранит code hash, задачи, changed files, tests, calibration version, contract, restore и compare.

---

## 16. Calibration, Metrics, Pose и 3D

### Calibration overlay

Показывает datasets → pose/metric references → consumers. Для reference: samples, median, MAD, P95, LOO spread и stability. Calibration имеет статусы `draft`, `running`, `failed`, `candidate`, `needs_review`, `approved`, `rejected`, `deprecated`. Автоматического изменения production threshold нет.

Реализовано (backend, без UI): `CalibrationRegistry` ведёт калибровочный Run Group через состояния `draft → candidate → approved/rejected`. Каждый из четырёх участников (`main_extraction`, `calibration_extraction`, `calibration_build`, `main_analysis`) регистрируется со своими `dataset_hash`/`code_hash`/`model_hash`/`config_hash`; любое рассогласование отклоняется сразу (fail-closed) с точным указанием, какой hash и какие роли конфликтуют. Approve фиксирует `bundle_hash` по всем ролям для последующей проверки воспроизводимости; approved/rejected Run Group иммутабелен. Доверенная калибровочная таблица прикрепляется к Run Group только после второй, независимой проверки (`assert_trusted_only`), которая повторно исключает landmark/keypoint/mesh/coordinate поля, даже если основной trust-классификатор в `datasets.py` регрессирует. Metric Explorer, Pose Lab, LOO sensitivity, train/holdout split и Artifact previews ниже остаются описанием плана (ещё не реализованы).

### Metric Explorer

Тип, единицы, producer, applicability, missing fraction, distributions, pose/dataset/quality breakdown, correlations with pose/expression, outliers и evidence role.

### Pose Lab

Девять колонок LP–RP: yaw/pitch/roll, boundaries, canonical target, residual distance, pair eligibility, coverage, calibration и ошибки.

### 3D Inspector

React Three Fiber: raw/normalized/canonical, identity-only и identity+expression meshes, overlay, motion vectors, visibility, landmarks, anchors и residual heatmap. UV/texture находится только во вкладке `Visualization only` с постоянным предупреждением.

### Artifact Explorer

JSON tree, CSV table, NPZ arrays, dtype, shape, min/max, NaN count, schema, producer, consumers и preview. Артефакты являются first-class nodes canvas.

---

## 17. Preset layouts и режимы

Layouts:

- Full Pipeline;
- Stage 1 Extraction;
- Geometry;
- Quality;
- Calibration;
- Chronology;
- Evidence;
- Testing;
- Debug Current Run;
- Blockers.

Режимы для журналиста:

- «Как работает система»;
- «Что сейчас сломано»;
- «Что делать дальше»;
- «Что передать разработчику»;
- «Что изменил patch»;
- «Что ещё не проверено».

Command Palette `Ctrl/Cmd+K`: найти функцию, metric, artifact, error, scenario; показать untested/calibration-required; compare runs; fit canvas.

---

## 18. Технологический стек

### Frontend

- React + TypeScript + Vite;
- React Flow / XYFlow — canvas, nodes, edges, groups, minimap;
- ELK.js — layered auto-layout большого графа;
- shadcn/ui + Radix UI — доступные controls;
- Tailwind CSS — visual tokens;
- TanStack Query — server state;
- TanStack Table — каталоги и версии;
- Zustand — canvas, filters, timeline;
- Monaco Editor — source и patch diff;
- Apache ECharts/Plotly — calibration и distributions;
- React Three Fiber + Drei — 3D;
- vis-timeline для MVP, PixiJS для больших traces;
- dnd-kit — Kanban.

Готовые основы: XYFlow Workflow Editor, Expand/Collapse, Auto Layout, shadcn dashboard/sidebar/data-table, Monaco Diff Editor.

### Backend

- FastAPI;
- Pydantic;
- SQLAlchemy/SQLModel;
- Alembic;
- SQLite WAL;
- watchfiles;
- Jinja2;
- structlog;
- psutil;
- системный Git CLI (`worktree`, `apply --check`, `diff`, `commit`, `revert`, `tag`, `bundle`).

Первый релиз — локальное web-приложение на `127.0.0.1`; desktop packaging возможен позже и не должен блокировать ядро.

---

## 19. Backend API

```text
GET  /api/project
GET  /api/project/graph
GET  /api/functions
GET  /api/functions/{id}
GET  /api/functions/{id}/tests
GET  /api/scenarios
POST /api/runs
POST /api/runs/{id}/cancel
GET  /api/runs/{id}/timeline
GET  /api/runs/{id}/artifacts
GET  /api/calibration
POST /api/calibration/experiments
GET  /api/calibration/run-groups
POST /api/calibration/run-groups
GET  /api/calibration/run-groups/{id}
POST /api/calibration/run-groups/{id}/members
POST /api/calibration/run-groups/{id}/table
POST /api/calibration/run-groups/{id}/approve
POST /api/calibration/run-groups/{id}/reject
GET  /api/calibration/run-groups/{id}/verify
GET  /api/gates
GET  /api/contracts
GET  /api/tasks
POST /api/tasks/generate
POST /api/fix-capsules
POST /api/patches/import
POST /api/patches/{id}/verify
POST /api/patches/{id}/accept
POST /api/patches/{id}/reject
GET  /api/versions
POST /api/versions/{id}/revert
WS   /ws/runs/{id}
WS   /ws/project
```

Никакого произвольного shell input. Разрешены только зарегистрированные операции: `run_test`, `run_scenario`, `run_gate`, `run_calibration`, `cancel_run`, `validate_artifact`, `compare_runs`, `verify_patch`.

---

## 20. Структура `ui`

```text
ui/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── .gitignore
├── package.json
├── pyproject.toml
├── frontend/src/
│   ├── app/
│   ├── canvas/{nodes,edges,layouts}/
│   ├── timeline/
│   ├── inspector/
│   ├── scenarios/
│   ├── calibration/
│   ├── artifacts/
│   ├── three/
│   ├── runs/
│   ├── tasks/
│   ├── patches/
│   ├── versions/
│   ├── gates/
│   ├── contracts/
│   �������── api/
├── backend/
│   ├── main.py
│   ├── api/
│   ├── models/
│   ├── indexer/{ast_indexer,call_graph,test_indexer,status_adapter}.py
│   ├── runtime/{instrumented_runner,event_protocol,process_manager}.py
│   ├── readiness/{evaluator,policies}.py
│   ├── tasks/
│   ├── patches/
│   ├── backups/
│   ├── calibration/
│   ├── artifacts/
│   └── storage/
├── config/
│   ├── project.yaml
│   ├── function_catalog.yaml
│   ├── readiness_policies.yaml
│   ├── test_bindings.yaml
│   ├── graph_overrides.yaml
│   └── visual_tokens.yaml
├── templates/
│   ├── task/
│   ├── fix_capsule/
│   └── reports/
├── scenarios/{synthetic,failure,chronology,real_photo}/
├── contracts/INTERFACE_CONTRACT.yaml
├── generated/{python,typescript,json_schema}/
└── .data/{studio.sqlite,layouts,compact-logs,manifests}/

# Тяжёлое runtime-хранилище находится вне ui:
/Volumes/SDCARD/uidata/{runs,stage1,stage2,stage2b,stage3,test-cache,scenarios,calibration,artifacts,previews,backups,trash}/
```

---

## 21. Внешнее хранилище, датасеты и режимы повторного извлечения

### Два уровня хранения

```text
Локально, внутри ui/.data/                 На съёмном диске
──────────────────────────                 ─────────────────────────────
studio.sqlite                              /Volumes/SDCARD/uidata/
настройки и layouts                        ├── runs/
компактные индексы                         ├── stage1/
небольшие логи                             ├── stage2/
задачи и manifests                         ├── stage2b/
                                           ├── stage3/
                                           ├── test-cache/
                                           ├── scenarios/
                                           ├── calibration/
                                           ├── artifacts/
                                           ├── previews/
                                           ├── backups/
                                           └── trash/
```

`ui/.data` не должен становиться дублирующим хранилищем результатов. SQLite хранит только metadata, относительные ссылки, hashes, размеры, состояния и provenance. Большие файлы открываются lazy из внешнего data root.

Перед запуском Storage Manager проверяет:

- существует ли `/Volumes/SDCARD` и совпадает ли сохранённый volume identity;
- доступен ли `/Volumes/SDCARD/uidata` для чтения и записи;
- достаточно ли свободного места для выбранного профиля;
- не является ли output вложенным в source dataset;
- нет ли ошибочного fallback/symlink на системный диск;
- не был ли диск отключён во время выполнения.

При отключении диска run переводится в `storage_interrupted`, новые тяжёлые записи прекращаются, process корректно останавливается, а уже записанные manifests сохраняются. Удаление выполняется через управляемую корзину и retention policy, а не немедленно.

### Источники фотографий

Основной dataset регистрируется как:

```text
/Volumes/SDCARD/photo/main
```

Корень калибровочного dataset задаётся отдельно в настройках, потому что его точный абсолютный путь нельзя угадывать. Внутри него интерфейс ожидает каталог `photos/` с фотографиями семи лиц и индексную таблицу с парами/углами.

Dataset Registry хранит не копии фотографий, а paths, content hashes, размер, время изменения, принадлежность dataset и доступность. Фото не копируются в `uidata`, если пользователь явно не создал управляемый snapshot.

### Политика доверия к калибровочной таблице

Из таблицы разрешено брать только:

- привязку калибровочного фото/лица к фото основного dataset;
- идентификаторы человека, кадра и файла;
- `yaw`, `pitch`, `roll` калибровочных кадров;
- порядок/роль пары и служебную provenance-информацию.

**Координаты ключевых точек из таблицы считаются неверными и запрещены как вход геометрического анализа.** Также нельзя использовать табличные mesh/landmark coordinates как fallback. Landmarks, mesh, visibility, pose diagnostics, descriptors и остальные производные должны каждый раз извлекаться из исходных фото актуальной версией `app6`/3DDFA-V3. `pose_bin` лучше пересчитывать из доверенных углов по текущей политике и отдельно показывать расхождение с табличной меткой.

Каждое поле таблицы получает trust class:

```text
trusted_pair_binding
trusted_pose_angle
identifier_only
recompute_from_photo
ignored_invalid_coordinate
unknown_requires_review
```

### Связанный полный анализ

Один production analysis создаётся как единая Run Group:

```text
Main dataset fresh extraction
+ Seven-person calibration fresh extraction
+ Calibration build/validation
+ Main Stage 2/2B/3 analysis
+ Combined provenance and gates
```

Калибровочные datasets запускаются вместе с основным анализом. После изменения code hash, model hash, extraction config или pipeline version предыдущая геометрия не считается актуальной: Stage 1 для основного и калибровочных наборов извлекается из фотографий заново. Нельзя незаметно подмешивать старую calibration geometry в новый основной run.

Run Group фиксирует source photo hashes, code/model/config hashes, extraction timestamp, доверенные табличные поля, версию parser и причины пропуска. UI показывает раздельный progress основного и семи calibration lanes, но release gate оценивает их совместно.

Сейчас реализован бэкенд-слой этой связки — `CalibrationRegistry` и `/api/calibration/run-groups...` (см. «16. Calibration, Metrics, Pose и 3D») — как hash-consistency guard и candidate/approval workflow без автоматизации самих fresh extraction загрузок и без UI отображения seven calibration lanes.

### Главный режим разработки — Scenario Lab

UI в первую очередь оборачивает уже существующий `app6/test_module`, а не создаёт параллельный тестовый механизм. Он импортирует 21 сценарий, `FUNCTION_MAP`, `STAGE_GATES`, assertions, генератор комбинаций и существующий checker.

Профили запуска:

1. **Synthetic 3D — секунды.** Использует `3DDFA-V3 face_model.npy` для asset/topology, девяти pose bins, точной геометрии, visibility masks, rigid alignment, same/different synthetic identity и chronology contracts. Это regression test, а не оценка точности и не источник forensic thresholds.
2. **Fresh-5 — основной цикл разработки.** Для выбранного сценария извлекает заново минимальный набор примерно из пяти реальных фотографий, чтобы быстро увидеть, работает ли изменённая версия целиком, включая Stage 1.
3. **Combination-1 — быстрая проверка одной пары/ротации лиц.**
4. **Combination-3 — обычная проверка на нескольких степенях внешнего сходства.**
5. **Combination-7 — уверенная матрица.** Детерминированно ротирует все семь лиц по ролям сценария, чтобы результат не зависел от одной чрезмерно похожей или непохожей пары.
6. **All poses — расширяет выбранные комбинации на девять pose bins.**
7. **Release matrix — все обязательные scenarios × комбинации × требуемые poses.**

Для каждого scenario-combination UI показывает, какие лица и фото выбраны, pair bindings, доверенные углы, pose bin, причину выбора, expected assertions и фактический результат. Сводка должна отдельно считать pass rate по scenario, человеку, паре людей, pose и степени сходства, не усредняя семь комбинаций в один непрозрачный показатель.

Существующий fast cache допускается только как явно маркированный режим для изменений Stage 2/2B/3. После изменения Stage 1, 3DDFA-V3, model weights или extraction config UI автоматически требует Fresh-5/Fresh-combination и не позволяет cached run закрыть Stage 1 readiness.

### Конфигурация путей и экспорта

Канонические примеры находятся в `ui/config/project.example.yaml` и `ui/config/export_policy.example.yaml`. Реальный calibration root задаётся пользователем или переменной окружения и не выдумывается интерфейсом.

### Компактный архив разработчику

Exporter никогда не архивирует run directory целиком. Он сначала строит `compact_result.json`/`compact_metrics.csv`, нормализует traceback, редактирует абсолютные пользовательские paths и применяет allowlist. До создания ZIP показываются размер и полный список файлов. Если установленный лимит превышен, export прекращается, пока пользователь не удалит тяжёлые вложения.

## 22. Итоговый пользовательский сценарий

1. Журналист получает новую папку `app6`.
2. UI проверяет SDCARD, `/Volumes/SDCARD/uidata`, main dataset и явно заданный calibration root.
3. UI обнаруживает changed files/functions/tests и обновляет карту.
4. Серые узлы — новые, зелёные — подтверждённые, красные — regressions, оранжевые — calibration gaps.
5. Для быстрой проверки запускается Synthetic 3D или Fresh-5; затем при необходимости 3–7 комбинаций лиц.
6. Полный анализ запускает fresh extraction main и всех семи calibration datasets как единую Run Group.
7. UI группирует root causes, downstream failures, missing tests и calibration gaps.
8. Формируется P0–P3/Research план по правилу 20/80.
9. Журналист редактирует ТЗ и фиксирует запреты.
10. Создаётся компактный allowlisted Fix Capsule без фото и тяжёлых результатов.
11. Разработчик возвращает patch package.
12. UI создаёт backup/worktree, применяет patch, компилирует и запускает affected/full tests.
13. Журналист видит понятный diff и принимает либо отклоняет patch.
14. Принятое изменение сохраняется отдельным commit, tags и snapshot; доступен безопасный revert.

## Финальная формула

Это три продукта в одной локальной системе:

1. **Pipeline Observatory** — живой цифровой двойник `app6`;
2. **Iteration Manager** — планирование следующей итерации по тестам и 20/80;
3. **Patch & Version Center** — безопасная передача задач, проверка исправлений, backup и rollback.

Журналист всегда видит понятное назначение функции, техническое имя, состояние, доказательства работоспособности, открытые проблемы и точную формулировку следующей задачи. Разработчик получает не абстрактную жалобу, а воспроизводимый Fix Capsule с файлами, функциями, тестами, логами, expected result и критериями приёмки.

Подробный последовательный план находится в [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).

## Scientific Validation Core
`/api/scenarios` импортирует 21 существующий сценарий app6 без выполнения кода. `/api/scenarios/plan` строит bounded-планы 1/3/7 комбинаций для frontal или девяти ракурсов. Fresh-5 использует только идентификаторы, пары и yaw/pitch/roll; координаты из таблицы запрещены.

## Investigation Feedback Loop
`GET /api/runs/{id}/investigation` классифицирует причину неуспешного прогона (P0 — нет измеримого результата или падение до результата, P1 — нарушение научного контракта сценария или timeout, P2 — вторичная проверка, P3 — отмена пользователем) и подбирает подозреваемые функции по `FUNCTION_MAP`. `POST /api/capsules` сохраняет allowlisted Fix Capsule (спецификация + обрезанный лог) для передачи разработчику. `POST /api/patches/apply` — прежний прямой путь: принимает unified diff, проверяет, что все затронутые пути лежат внутри `app6`, выполняет `git apply --check`, создаёт файловый backup и только затем применяет патч к рабочей копии напрямую. `POST /api/patches/apply-safe` — безопасный путь: применяет тот же diff в одноразовом изолированном `git worktree`, запускает там регрессионный тест-раннер (`app6-regression` из `runners.yaml`) и только при зелёном прогоне создаёт файловый backup, применяет патч к реальному дереву и делает настоящий git commit; при падении теста или ошибке apply реальное дерево гарантированно не тронуто, а временный worktree всегда удаляется. `POST /api/patches/{sha}/revert` откатывает такой commit через `git revert` (сохраняет историю). `POST /api/backups/{id}/rollback` восстанавливает исходные файлы из файлового backup. Изолированный путь проверен только на синтетических git-фикстурах (модульные тесты), не через живой HTTP-роут/UI; полноценный commit/tag lifecycle для серии патчей остаётся в открытом backlog.
