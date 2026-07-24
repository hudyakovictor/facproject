# DEEPUTIN Pipeline Observatory — полный план реализации

> План построен от критического ядра к деталям. Каждая итерация имеет зависимости, deliverables, тесты и exit criteria. Следующая итерация не считается начатой, пока обязательные критерии предыдущей не закрыты.

## 0. Неподвижные архитектурные правила

- [ ] `app6` остаётся read-only для UI, кроме явно подтверждённого пользователем принятия patch.
- [ ] `ui/.data` хранит только компактный control plane; тяжёлые runtime/cache/artifact данные находятся в `/Volumes/SDCARD/uidata`.
- [ ] При отсутствии/подмене/переполнении SDCARD тяжёлый run блокируется без fallback на системный диск.
- [ ] Основной dataset по умолчанию регистрируется из `/Volumes/SDCARD/photo/main`.
- [ ] Корень calibration dataset задаётся явно; интерфейс не угадывает неуказанный абсолютный путь.
- [ ] Из calibration table доверяются pair bindings, identifiers и yaw/pitch/roll; координаты landmarks/mesh игнорируются как неверные.
- [ ] Production main analysis всегда включает fresh extraction основного и семи calibration datasets одной версией pipeline.
- [ ] UI не запускает произвольные shell-команды.
- [ ] Все операции выполняются через allowlist runners.
- [ ] Публичный evidence state не смешивается с measurement status.
- [ ] UV/texture остаются visualization-only.
- [ ] Threshold нельзя менять без calibration data и отдельной задачи.
- [ ] Реальные фото не включаются в Fix Capsule по умолчанию.
- [ ] Patch никогда не применяется напрямую к активной версии.
- [ ] Перед patch создаются Git/worktree и source snapshot.
- [ ] Accept/reject/revert сохраняют полную историю.
- [ ] Цвет состояния всегда дублируется текстом и иконкой.
- [ ] «Тест прошёл» не равно «функция release-ready».

---

# Итерация 1. Foundation, внешнее хранилище и границы проекта — ✅ завершена

## Цель

Создать минимальный запускаемый каркас `ui`, не затрагивая `app6`, и сразу исключить попадание тяжёлых данных на системный диск.

## Backend

- [x] Создать `ui/backend`, FastAPI entry point и `/api/health`.
- [x] Создать типизированные settings с `APP6_ROOT=../app6`; Pydantic dependency закрепить для API-моделей.
- [x] Проверять, что `APP6_ROOT` существует и не находится внутри `ui`.
- [x] Запретить backend bind за пределами `127.0.0.1` по умолчанию.
- [x] Создать SQLite WAL database.
- [x] Создать versioned SQLite WAL migration core; SQLAlchemy/Alembic закрепить как зависимости для последующих ORM migrations.
- [x] Создать таблицы project, source_snapshot, module, function, run, event.
- [x] Добавить structured logging.
- [x] Создать `/api/project`, `/api/system/health`.
- [x] Создать Storage Manager с двумя roots: compact local control data и external heavy data.
- [x] Проверять mount, volume identity, read/write, free space, symlink и source/output nesting.
- [x] Реализовать `storage_interrupted` и корректную остановку при отключении диска.
- [x] Создать Dataset Registry для main и calibration datasets без копирования фото.
- [x] Сохранять только paths, hashes, sizes, mtimes, dataset roles и availability.

## Frontend

- [x] Создать React + TypeScript + Vite.
- [x] Создать React/Vite dependency scaffold; TanStack Query/Zustand подключены, React Flow UI/shadcn используются с Canvas-итерации.
- [x] Создать foundation shell: header, sidebar и main workspace; inspector/bottom runtime panel развиваются в Canvas/Timeline итерациях.
- [x] Реализовать loading/error/empty/offline states.
- [x] Закрепить постоянную тёмную тему согласно пользовательскому решению.

## Storage

- [x] Создать `ui/.gitignore`.
- [x] Исключить `.data`, node modules, Python caches, builds, local env.
- [x] Проверить, что запуск UI не создаёт файлов в `app6`.
- [x] Не хранить Stage outputs, NPZ, images, meshes и previews в локальной `.data`.
- [x] Создать external layout `/Volumes/SDCARD/uidata/{runs,stage1,stage2,stage2b,stage3,test-cache,scenarios,calibration,artifacts,previews,backups,trash}`.
- [x] Добавить quota/retention/trash policy без автоматического удаления доказательных manifests.

## Тесты

- [x] Backend health test.
- [x] Settings/path tests.
- [x] SQLite migration test.
- [x] Frontend TypeScript source smoke; полный Vite browser build выполняется после установки declared dependencies.
- [x] Read-only pollution test для `app6`.
- [x] No-local-heavy-fallback test.
- [x] Missing/unmounted/low-space/wrong-volume tests.
- [x] Disk disconnect recovery test.

## Exit criteria

- UI и backend запускаются одной documented-командой.
- Health показывает путь и доступность `app6`, SDCARD, main/calibration datasets и свободное место.
- После smoke run дерево `app6` не изменилось.
- Ни один heavy artifact не записан на системный диск.

---

# Итерация 2. Read-only AST Indexer

## Цель

Построить достоверный каталог модулей, классов и функций без импорта pipeline.

## Реализация

- [x] `ast_indexer.py`: modules, classes, functions, async functions, methods.
- [x] Извлекать qualified name, signature, annotations, docstring, line range.
- [x] Извлекать imports, constants, decorators, raises, `log_status`, `status_warning`.
- [x] Находить `pass`, `NotImplementedError`, TODO markers и broad exceptions.
- [x] Считать content hash каждого source file.
- [x] Реализовать incremental reindex только changed files.
- [x] Создать function fingerprint для rename/move detection.
- [x] Ввести edge confidence: confirmed, heuristic, runtime, manual.
- [x] Не считать динамический вызов confirmed без доказательства.
- [x] Создать `/api/modules`, `/api/functions`, `/api/project/graph`.

## Watcher

- [x] Подключить optional `watchfiles` backend с dependency-light polling fallback.
- [x] Debounce 300–500 ms.
- [x] Игнорировать caches, archives, `.data`, generated.
- [x] WebSocket project update events.

## Тесты

- [x] Fixtures с обычными, class, nested, async functions.
- [x] Dynamic call fixture.
- [x] Rename/move fixture.
- [x] Incremental reindex test.
- [x] No-import/side-effect test.

## Exit criteria

- 100% Python-файлов `app6` индексируются или имеют объяснённую parse error.
- Ни один модуль `app6` не импортируется индексатором.
- Повторный scan без изменений детерминирован.

---

# Итерация 3. Status, Test Indexer и понятный каталог

## Цель

Связать исходный код, `STATUS_AUDIT.py`, тесты и журналистские описания.

## Реализация

- [x] Read-only parser `STATUS_AUDIT.py` без выполнения произвольного кода.
- [x] Сопоставить status entries с function IDs.
- [x] `test_indexer.py`: test classes/functions/imports/calls/expected exceptions.
- [x] Создать auto test bindings с confidence.
- [x] Реализовать `test_bindings.yaml` для ручных overrides.
- [x] Создать `function_catalog.yaml`.
- [x] Для функции хранить title, description, why important, failure impact.
- [x] Техническое имя и source всегда показывать мелкой серой подписью.
- [x] Создать glossary терминов.
- [x] Отмечать отсутствующее описание как отдельную задачу P2.

## API/UI

- [x] Function Catalog table.
- [x] Фильтры stage/status/test/blocker/criticality.
- [x] Function Inspector «Простыми словами» и «Техническая».
- [x] Source preview read-only.

## Тесты

- [x] Status mapping tests.
- [x] Test binding tests.
- [x] Unknown/renamed function handling.
- [x] Journalist description validation.

## Exit criteria

- Каждая критическая функция имеет понятное название, назначение и failure impact.
- Для каждого auto binding отображается confidence и источник.

---

# Итерация 4. Pipeline Canvas MVP

## Цель

Создать ComfyUI-подобную карту pipeline.

## Реализация

- [ ] Подключить XYFlow/React Flow.
- [ ] Создать Stage, Module, Class, Function, Artifact nodes.
- [ ] Создать confirmed/heuristic/runtime/manual edges.
- [x] Подключить ELK.js auto-layout.
- [ ] Реализовать collapse/expand stage и module groups.
- [ ] Minimap, zoom, pan, fit, selection, multi-select.
- [ ] Сохранять layouts только в `ui/.data/layouts`.
- [x] Реализовать semantic zoom: stages → modules → functions → ports.
- [ ] Создать presets Full, Stage1, Geometry, Calibration, Evidence, Testing, Blockers.
- [ ] Command Palette.

## Node design

- [ ] Журналистский title — главный.
- [ ] Function/path — мелкая серая подпись.
- [ ] Readiness background, runtime ring.
- [ ] Status icon/text/pattern для accessibility.
- [ ] Test/calibration/real-photo segmented bars.
- [ ] Badges critical/experimental/visual-only/deprecated.

## Тесты

- [ ] Layout determinism.
- [ ] 500+ node performance fixture.
- [ ] Keyboard navigation.
- [ ] Color-independent status test.

## Exit criteria

- Журналист может найти любую функцию и понять её место без чтения кода.
- Canvas остаётся интерактивным на полном графе.

---

# Итерация 5. Readiness Engine

## Цель

Автоматически и честно рассчитывать зрелость функций.

## Реализация

- [x] Создать readiness dimensions: implementation, unit, synthetic, integration, real_photo, calibration, docs, observability.
- [x] Создать policy types utility, critical_stage1, calibration, evidence, visual_only.
- [x] Статусы discovered, implemented_unverified, synthetic_verified, integration_verified, real_photo_verified, calibration_required, release_ready, failing, experimental, deprecated.
- [x] Не использовать среднее, если обязательный dimension не закрыт.
- [x] Реализовать blocker propagation без маркировки downstream как broken.
- [x] Хранить readiness snapshots по code hash.
- [x] Объяснять каждое решение readiness engine.
- [ ] Добавить manual approval только там, где он обязателен.

## Тесты

- [x] Policy truth tables.
- [x] Blocker propagation.
- [x] Visual-only closure.
- [x] Calibration-required cannot become green after unit pass.
- [x] Deterministic recomputation.

## Exit criteria

- Любой цвет узла имеет проверяемое объяснение и список незакрытых условий.

---

# Итерация 6. Process Manager и Live Runtime

## Цель

Безопасно запускать tests/pipeline и видеть выполнение в реальном времени.

## Реализация

- [x] Allowlisted runner registry.
- [x] Async queue с `max_parallel_runs=1` по умолчанию.
- [x] Subprocess isolation, PID tracking, timeout, cancel, process tree cleanup.
- [ ] `instrumented_runner.py` с `sys.setprofile` и фильтром `app6`.
- [x] JSONL event protocol с schema version.
- [ ] Events call/return/exception/warning/artifact/progress/resource.
- [x] Event batching и WebSocket `/ws/runs/{id}`.
- [ ] Сохранять run config, code/model/contract hash, environment, seed.
- [x] Защита от произвольных arguments/path traversal.
- [x] Recovery после restart UI.

## Canvas integration

- [ ] Running pulse по edge.
- [ ] Active node spinner.
- [ ] Runtime ring.
- [ ] Downstream blocked state.
- [ ] Live logs и current photo/step.

## Тесты

- [x] Success/failure/cancel/timeout.
- [ ] Child process cleanup.
- [x] Malformed event isolation.
- [x] Reconnect/replay.
- [x] No source writes.

## Exit criteria

- Run можно запустить, наблюдать, отменить и восстановить историю без orphan processes.

---

# Итерация 7. Timeline и Replay

## Цель

Дать временное представление каждого run.

## Реализация

- [ ] MVP на vis-timeline; performance threshold для перехода на PixiJS.
- [ ] Tracks stage/module/function.
- [ ] Nested spans, warning/error/artifact markers.
- [ ] Cursor-anchored wheel zoom.
- [ ] Shift+wheel pan, Alt+wheel vertical, drag, fit.
- [ ] Time scrubber.
- [ ] Canvas state replay на выбранный timestamp.
- [ ] Синхронизация node ↔ spans.
- [ ] Baseline/candidate overlay.
- [ ] Duration, CPU, RAM tracks.

## Тесты

- [ ] Zoom anchor accuracy.
- [ ] Replay determinism.
- [ ] Thousands-event performance.
- [ ] Interrupted run rendering.

## Exit criteria

- Пользователь может восстановить путь ошибки во времени и перейти от span к функции/артефакту.

---

# Итерация 8. Scenario Lab, calibration combinations и Test Matrix

## Цель

Сделать существующий `app6/test_module` главным development workflow: быстрый synthetic 3D, Fresh-5 и 1–7 сбалансированных комбинаций семи calibration-лиц.

## Реализация

- [ ] Scenario schema: ID, type, seed, generator, inputs, expected results.
- [ ] Импортировать существующие 21 scenarios, runner, checker, `FUNCTION_MAP` и `STAGE_GATES`, не создавать конкурирующую библиотеку.
- [ ] Импорт существующих synthetic runner/tests на 3DDFA-V3 `face_model.npy`.
- [ ] Явно подписать: synthetic проверяет contracts/regressions, но не accuracy и не thresholds.
- [ ] Реализовать профиль Fresh-5 с повторным Stage 1 extraction примерно пяти выбранных фото.
- [ ] Реализовать Combination-1/3/7 через существующую детерминированную ротацию `person_01..person_07`.
- [ ] Показывать состав ролей A/A2/B/C/D, выбранные фото, pair bindings и pose для каждой комбинации.
- [ ] Не сводить семь комбинаций в один непрозрачный result: показывать breakdown по лицам, парам, poses и scenarios.
- [ ] Scenario nodes: input, transforms, pipeline, assertions.
- [ ] Pose/expression/camera/quality/occlusion/failure/chronology presets.
- [ ] Безопасный visual Scenario Composer.
- [ ] Test Matrix function × scenario.
- [ ] Expected/actual/diff/log/artifact per cell.
- [ ] Real-photo registry хранит pointers/hashes, не копии по умолчанию.
- [ ] Основной dataset зарегистрировать из `/Volumes/SDCARD/photo/main`.
- [ ] Calibration dataset root задавать явно и валидировать `photos/` и index table.
- [ ] Создать schema/trust policy parser таблицы: pair binding и yaw/pitch/roll trusted; keypoint/mesh coordinates ignored.
- [ ] Пересчитывать pose bin текущей политикой из trusted angles и показывать расхождения с table label.
- [ ] Для production Run Group всегда заново извлекать main + семь calibration datasets текущим code/model/config hash.
- [ ] Cached fast mode разрешить только для Stage 2/2B/3 и запретить ему закрывать Stage 1 readiness.
- [ ] Ground truth type и confidence обязательны.
- [ ] Отделить not-run, skipped, inapplicable, expected-failure и failed.

## Тесты

- [ ] Seed reproducibility.
- [ ] Scenario serialization.
- [ ] Assertion node tests.
- [ ] Real-photo privacy test.
- [ ] Invalid table coordinate rejection test.
- [ ] Pair/angle-only trust test.
- [ ] Balanced seven-person rotation test.
- [ ] Fresh-5 really re-extracts test.
- [ ] Cached run cannot verify Stage 1 test.
- [ ] No arbitrary code node.

## Exit criteria

- Критические функции имеют объявленные synthetic scenarios; UI запускает их и показывает точный diff.
- Любой выбранный scenario запускается на 1–7 комбинациях; Fresh-5 обеспечивает короткий полный цикл.
- Production analysis не использует устаревшую calibration geometry.

---

# Итерация 9. Result Analyzer и Root Cause

## Цель

Перевести технические результаты в понятные причины и не создавать дубликаты задач.

## Реализация

- [ ] Error fingerprinting: exception type + normalized stack + function.
- [ ] Root cause vs downstream consequence graph.
- [ ] Problem types code/test/regression/calibration/dataset/environment/schema/performance/docs/UI/expected limitation.
- [ ] Понятное journalist summary.
- [ ] Technical evidence drawer.
- [ ] Confidence labels Confirmed/High-confidence/Possible/Unknown.
- [ ] Не выдавать hypothesis за confirmed cause.
- [ ] Calibration gap создаёт data/calibration task, не threshold patch.
- [ ] Сравнение baseline/candidate outcomes.
- [ ] Deduplication across repeated runs.

## Тесты

- [ ] One root → many downstream.
- [ ] Repeated traceback grouping.
- [ ] Calibration gap classification.
- [ ] Unknown cause safe wording.

## Exit criteria

- Один первичный дефект формирует одну корневую проблему с перечисленными последствиями.

---

# Итерация 10. Iteration Manager и ТЗ

## Цель

Автоматически формировать приоритетный план и developer-ready задачи.

## Реализация

- [ ] Priority rules P0/P1/P2/P3/Research.
- [ ] Impact/reach/reproducibility/confidence/effort score.
- [ ] Жёсткие P0 overrides.
- [ ] Режим 80/20.
- [ ] Kanban workflow.
- [ ] Merge/split/reprioritize/edit/archive tasks.
- [ ] Связи task ↔ problem ↔ function ↔ test ↔ run.
- [ ] Jinja2 templates TASK, reproduction, acceptance criteria.
- [ ] Автоматические project constraints.
- [ ] Iteration report Markdown/JSON.

## Acceptance template

- [ ] Actual/expected.
- [ ] Reproduction command.
- [ ] Affected files/functions/downstream.
- [ ] Required tests.
- [ ] Forbidden changes.
- [ ] Out of scope.
- [ ] Rollback conditions.

## Тесты

- [ ] P0 safety cases.
- [ ] 80/20 ranking stability.
- [ ] No threshold suggestion without calibration.
- [ ] No visual-only evidence task.
- [ ] Template completeness.

## Exit criteria

- После failed run автоматически создаётся редактируемый, полный и воспроизводимый iteration draft.

---

# Итерация 11. Fix Capsule Export/Import

## Цель

Передавать разработчику минимальный самодостаточный пакет.

## Реализация

- [ ] Fix Capsule schema и version.
- [ ] TASK.md, task.json, rules, reproduction, acceptance, baseline, functions, files, logs, scenario, synthetic fixture, expected.
- [ ] Использовать положительный allowlist: `.log`, `.txt`, `.json`, `.jsonl`, `.csv`, `.md`, `.yaml`, `.yml` и manifest.
- [ ] Исключать real photos, images, video, weights, OBJ/MTL, NPZ/NPY, SQLite, caches, private data и large artifacts.
- [ ] Преобразовывать тяжёлые бинарные результаты в компактные JSON/CSV summaries вместо копирования originals.
- [ ] Редактировать абсолютные paths и персональные данные по policy.
- [ ] До ZIP показывать полный file list и total size; превышение configurable budget блокирует export.
- [ ] Size and content preview до экспорта.
- [ ] Checksum manifest.
- [ ] Developer response schema.
- [ ] Импорт response, patch, changelog, test report, limitations.
- [ ] Проверка task ID и base hash.
- [ ] Quarantine неизвестных файлов.
- [ ] Audit trail export/import.

## Тесты

- [ ] Capsule round-trip.
- [ ] Privacy exclusion.
- [ ] Heavy-extension and oversize rejection.
- [ ] Binary-to-compact-summary test.
- [ ] Absolute-path redaction test.
- [ ] Zip-slip protection.
- [ ] Schema mismatch.
- [ ] Base mismatch.

## Exit criteria

- Пакет воспроизводит ошибку без полного проекта/датасета там, где это возможно, и не содержит запрещённых данных.

---

# Итерация 12. Patch Center, Git Worktree и Rollback

## Цель

Безопасно проверять и принимать исправления.

## Реализация

- [ ] Проверить наличие/состояние Git repository.
- [ ] Перед patch создавать source snapshot и before tag.
- [ ] Создавать isolated worktree/branch.
- [ ] `git apply --check`, затем controlled apply.
- [ ] Monaco Diff Editor.
- [ ] Policy scanner: forbidden files, thresholds, tests, validation, exception suppression, NaN fallbacks, schema/public gate.
- [ ] Compile, affected tests, dependency tests, full regression.
- [ ] Baseline/candidate diff.
- [ ] Accept создаёт commit и after tag.
- [ ] Reject сохраняет отчёт, удаляет worktree, не меняет main.
- [ ] Revert создаёт новый revert commit.
- [ ] Никогда не выполнять автоматический `reset --hard` main.

## Backup

- [ ] Source-only `.tar.zst` before/after.
- [ ] Backup index с SHA-256.
- [ ] Restore verification.
- [ ] Periodic `git bundle --all`.
- [ ] Retention policy.

## Тесты

- [ ] Clean patch.
- [ ] Conflicting patch.
- [ ] Wrong base.
- [ ] Forbidden file.
- [ ] Failed tests preserve main.
- [ ] Accept/reject/revert.
- [ ] Restore snapshot and bundle.

## Exit criteria

- Ни один неуспешный patch не изменяет активный `app6`; любое принятое изменение обратимо.

---

# Итерация 13. Calibration, Metric, Pose и Artifact Labs

## Цель

Закрыть научно-инженерную диагностику.

## Calibration

- [ ] Dataset registry, train/holdout.
- [ ] Run Group orchestrator: fresh main extraction + fresh seven-person calibration extraction + calibration build + main analysis.
- [ ] Запрещать смешивание outputs с разными code/model/config hashes.
- [ ] Хранить trusted table fields отдельно от recomputed geometry.
- [ ] Показывать семь calibration lanes и общий release gate.
- [ ] LOO sensitivity.
- [ ] Median/MAD/P95 distributions.
- [ ] Sparse cells и pose coverage.
- [ ] Candidate/approval workflow.
- [ ] Bundle version/hash/provenance.
- [ ] Shadow calibration без изменения app6.

## Metrics/Pose

- [ ] Metric registry, units, applicability, missing fraction.
- [ ] Distributions и correlation with pose/expression/quality.
- [ ] Pose leakage views.
- [ ] Nine-bin Pose Lab.
- [ ] Boundary/residual diagnostics.

## Artifacts

- [ ] JSON/CSV/NPZ/image previews.
- [ ] dtype/shape/min/max/NaN/schema.
- [ ] Producer/consumer/data lineage.
- [ ] Large artifact lazy load.

## Тесты/Exit

- [ ] No threshold auto-apply.
- [ ] Main/calibration fresh extraction coupling.
- [ ] Stale calibration geometry rejection.
- [ ] Invalid landmark coordinates from table never enter pipeline.
- [ ] Holdout leakage prevention.
- [ ] Large NPZ memory limits.
- [ ] Каждая approved calibration воспроизводима по dataset/code/config hashes.

---

# Итерация 14. 3D Inspector

## Цель

Визуально диагностировать геометрию без смешения с evidence.

- [ ] React Three Fiber/Drei scene.
- [ ] Raw, normalized, canonical, identity-only, identity+expression.
- [ ] Pair overlay, opacity, synchronized cameras.
- [ ] LDM106/LDM134, visibility, anchors, motion vectors.
- [ ] Residual heatmap.
- [ ] Lazy load и LOD.
- [ ] Screenshot/export.
- [ ] UV/texture только во вкладке Visualization only.
- [ ] Постоянный evidence disclaimer.
- [ ] WebGL fallback/unsupported state.

## Exit criteria

- 3D не влияет на evidence state; большие meshes не блокируют основной UI.

---

# Итерация 15. Contract Inspector и генерация типов

## Цель

Свести backend и frontend через единый `INTERFACE_CONTRACT.yaml`.

- [ ] Meta-schema контракта.
- [ ] Inventory JSON/CSV/NPZ keys.
- [ ] Entities, fields, enums, artifacts, errors, migrations, UI metadata.
- [ ] Python/Pydantic generation.
- [ ] TypeScript/Zod generation.
- [ ] JSON Schema generation.
- [ ] CSV header contracts.
- [ ] Backend key without contract.
- [ ] Contract key never produced.
- [ ] Frontend key without contract.
- [ ] Enum/type/nullability mismatch.
- [ ] Visualization leakage.
- [ ] Generated files reproducibility.

## Exit criteria

- CI запрещает drift backend/frontend; generated files не редактируются вручную.

---

# Итерация 16. Performance, Security, Accessibility

## Performance

- [ ] 500+ graph nodes benchmark.
- [ ] 100k events timeline benchmark.
- [ ] Virtual tables/logs.
- [ ] Event batching/backpressure.
- [ ] Cache invalidation.
- [ ] Memory/resource limits.

## Security/privacy

- [ ] Bind localhost.
- [ ] Allowlist runners/arguments.
- [ ] Path traversal и zip-slip protection.
- [ ] Upload type/size validation.
- [ ] Process sandbox and timeout.
- [ ] No secrets/env dump.
- [ ] Real-photo privacy controls.
- [ ] Audit logs.

## Accessibility

- [ ] Keyboard operation.
- [ ] Focus order.
- [ ] Screen-reader labels.
- [ ] Contrast.
- [ ] Reduced motion.
- [ ] Status independent of color.
- [ ] Responsive degraded view.

## Exit criteria

- Установленные performance/security/a11y budgets проходят автоматически.

---

# Итерация 17. End-to-end Gates и Release

## Gates

- [ ] Contract gate.
- [ ] Backend unit/integration.
- [ ] Frontend unit/component.
- [ ] E2E Playwright.
- [ ] Synthetic 3DDFA-V3 contract gate.
- [ ] Fresh-5 quick full-pipeline gate.
- [ ] Balanced Combination-7 scenario gate.
- [ ] Synthetic full pipeline.
- [ ] Runtime replay.
- [ ] Fix Capsule round-trip.
- [ ] Patch accept/reject/revert.
- [ ] Backup restore.
- [ ] Calibration reproducibility.
- [ ] One-photo, resume, 10-photo, 100-photo integration when assets exist.

## Documentation

- [ ] Installation macOS/Linux.
- [ ] Local startup/shutdown.
- [ ] Journalist guide.
- [ ] Developer Fix Capsule guide.
- [ ] System architect guide.
- [ ] Backup/recovery runbook.
- [ ] Troubleshooting.
- [ ] Data privacy.
- [ ] Release notes and migration guide.

## Release criteria

- [ ] Все P0/P1 закрыты или явно accepted risk.
- [ ] Нет writes в `app6` вне approved patch flow.
- [ ] Нет arbitrary shell.
- [ ] Нет real-photo leakage.
- [ ] Fix Capsule содержит только allowlisted compact files.
- [ ] Heavy data находится на SDCARD, local fallback отсутствует.
- [ ] Main и calibration photo extraction выполнены одной актуальной версией.
- [ ] Full regression green.
- [ ] E2E user journey пройден журналистом без чтения кода.
- [ ] Независимый разработчик воспроизвёл Fix Capsule и вернул patch.
- [ ] Patch безопасно принят и затем тестово откатан.
- [ ] Backup восстановлен на чистой копии.
- [ ] Версия tagged и source bundle создан.

---

# Общая Definition of Done — 100%

Система считается завершённой только если выполнено всё:

## Наблюдаемость

- [ ] Все индексируемые функции и модули представлены на canvas.
- [ ] Для каждой critical-функции есть понятное описание.
- [ ] Readiness и runtime состояния разделены.
- [ ] Любой status имеет объяснение.
- [ ] Dynamic runtime edges дополняют AST graph.

## Тестирование

- [ ] Unit, synthetic, integration, real-photo и calibration результаты различаются.
- [ ] Scenario seeds воспроизводимы.
- [ ] Test Matrix покрывает critical pipeline.
- [ ] Root causes не дублируются downstream failures.

## Итерации и ТЗ

- [ ] P0–P3/Research формируются автоматически.
- [ ] Режим 80/20 работает.
- [ ] ТЗ содержит reproduction и acceptance criteria.
- [ ] Каждая задача связана с функциями, тестами и runs.
- [ ] Не генерируются ложные научные рекомендации.

## Patch и backup

- [ ] Patch тестируется только в worktree.
- [ ] Base hash проверяется.
- [ ] Forbidden changes обнаруживаются.
- [ ] Accept/reject/revert безопасны.
- [ ] Source snapshot и Git history восстановимы.

## ��������онтракты

- [ ] Backend и frontend типы генерируются из одного источника.
- [ ] Unknown/missing/null policies явные.
- [ ] Measurement и evidence не смешиваются.
- [ ] Texture/UV не попадают в evidence.

## UX

- [ ] Журналист понимает назначение функции без знания Python.
- [ ] Техническое имя всегда доступно.
- [ ] Ошибка объяснена простым и техническим языком.
- [ ] Canvas, timeline, tasks и patch связаны между собой.
- [ ] Все критические действия требуют подтверждения.

## Эксплуатация

- [ ] UI запускается локально документированной командой.
- [ ] Не оставляет orphan processes.
- [ ] Не засоряет `app6`.
- [ ] Работает после restart с сохранением истории.
- [ ] Имеет проверенный recovery runbook.

---

# Порядок приоритетов реализации

```text
1. Изоляция, SDCARD Storage Manager и Dataset Registry
2. Read-only индексатор
3. Понятный каталог функций
4. Canvas
5. Честный readiness
6. Безопасный runtime runner
7. Timeline/replay
8. Scenario/Test Matrix
9. Root-cause analysis
10. Iteration Manager и ТЗ
11. Fix Capsule
12. Patch/backup/rollback
13. Calibration/metrics/artifacts
14. 3D
15. Interface contract generation
16. Performance/security/accessibility
17. End-to-end release gates
```

Этот порядок намеренно ставит наблюдаемость, безопасность и передачу задач выше декоративных графиков и 3D. Нельзя переходить к тяжёлой визуализации, пока не готовы read-only index, runner, readiness, task generation и безопасный patch flow.

### Завершено: Iteration 7 Scientific Validation Core
Импорт сценариев, balanced 1/3/7 matrix, nine-pose planner, synthetic contract boundary, Fresh-5 trusted-data planner.

### Завершено: Iteration 8 Investigation Feedback Loop
Классификация причины отказа (P0–P3), подбор подозреваемых функций, приоритизированный Fix Spec, Fix Capsule, безопасный backup/apply/rollback патчей внутри allowlisted корня.

### завершено (частично): Iteration 9 Patch Safety Lifecycle
Изолированный `git worktree` apply, обязательный авто-запуск регрессионного теста перед любым касанием реального дерева, условный real-commit только при зелёных тестах, безопасный rollback через `git revert`. Попутно найден и исправлен реальный скрытый баг: `git apply`, вызванный с `cwd` в подкаталоге репозитория (а не в его корне), мог тихо «Skipped patch» без ошибки и без изменения файла — исправлено в обоих путях через заведомую запуск из корня репозитория с `--directory`. Проверено только на синтетических git-фикстурах (61/61 backend, 65/65 app6); без живой проверки через HTTP-роут/UI и без commit/tag lifecycle для серии патчей. Главные критичные архитектурные блоки завершены; оставшиеся итерации (Timeline/Replay, Calibration/Metrics/Artifacts, 3D Inspector, Interface Contract, Performance/Security, End-to-end gates) — открытый backlog, приоритеты по нему следует согласовывать с заказчиком.

### завершено (частично): Iteration 10 Calibration Integrity Core
Из всей Iteration 13 (Calibration/Metrics/Pose/Artifacts) выбран и реализован самый архитектурно сложный и научно рискозначимый срез — Run Group hash-consistency guard и candidate/approval workflow. Новый `CalibrationRegistry`: (1) не даёт собрать калибровочный Run Group (`main_extraction` + `calibration_extraction` + `calibration_build` + `main_analysis`) из выходов с разными `dataset_hash`/`code_hash`/`model_hash`/`config_hash` — рассогласование отклоняется сразу же при регистрации участника (fail-closed, без тихого слияния), с точным указанием конфликтующего измерения и ролей; (2) состояние `draft → candidate → approved/rejected`, approve возможен только когда присутствуют и согласованы все четыре роли, approved/rejected неизменяемы; (3) approve фиксирует `bundle_hash` по всем ролям, а `verify_bundle_integrity` пересчитывает его и обнаруживает подмену данных после утверждения; (4) доверенная калибровочная таблица (уже отфильтрованная существующим trust-классификатором `datasets.py`) прикрепляется к Run Group только после второй, независимой defense-in-depth проверки (`assert_trusted_only`), которая повторно ищет landmark/keypoint/mesh/vertex/coordinate поля и отклоняет прикрепление при их обнаружении — так табличные координаты не попадут в approved calibration bundle даже при регрессии основного классификатора. Добавлены 7 REST-маршрутов `/api/calibration/run-groups...`. Осознанно не сделано в этой итерации (открытый backlog по правилу 20/80): Metric Explorer и Pose Lab визуализация, LOO sensitivity, dataset train/holdout split, sparse-cell/pose-coverage отчётность, Artifact previews, автоматизация самих fresh extraction запусков и UI. Проверено только синтетическими фикстурами (11 новых backend-тестов, 72/72 backend, 65/65 app6 без изменений); реального калибровочного датасета в этой песочнице не было.
