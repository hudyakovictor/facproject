# UI implementation progress

## Итоговая готовность: 80/100 — 80%

Процент рассчитывается по фиксированному весу 17 итераций. Архитектурная документация сама по себе не добавляет процент: учитывается только реализованный и проверенный функционал. Таблица приведена в соответствие фактически реализованным и протестированным итерациям 1–9 и 11; итерация 10 (Iteration Manager) засчитана частично (per-run spec без сквозного backlog); итерация 12 — 6/8% (изолированный worktree apply + авто-тесты + условный commit + git-revert rollback, без live HTTP/UI проверки); строка 13 (Calibration/Metrics/Pose/Artifacts) засчитана частично — 3/6% — за Run Group hash-consistency guard (запрет смешивания dataset/code/model/config hashes), workflow draft→candidate→approved/rejected с persisted provenance и bundle-hash reproducibility check, и за добавленный UI-экран Calibration Panel (создание группы, регистрация участников по ролям, привязка доверенной таблицы, approve/reject, проверка целостности bundle); Metric/Pose Lab визуализация, LOO sensitivity, dataset train/holdout split и Artifact previews остаются нереализованными. Итерация 7 (Timeline) также получила UI-экран Timeline Panel (реплей по трекам run/tests/photos/log со скраббером и честной пометкой оценённого начала отрезка), закрывая ранее отмеченный разрыв «backend готов, экрана нет».

| Итерация | Содержание | Вес | Статус | Получено |
|---:|---|---:|---|---:|
| 1 | Foundation, SDCARD Storage Manager, Dataset Registry | 7% | ✅ Завершена | 7% |
| 2 | Read-only AST Indexer | 7% | ✅ Завершена | 7% |
| 3 | Status/Test Indexer и журналистский каталог | 6% | ✅ Завершена | 6% |
| 4 | Pipeline Canvas | 9% | ✅ Завершена | 9% |
| 5 | Readiness Engine | 6% | ✅ Завершена | 6% |
| 6 | Process Manager и Live Runtime | 8% | ✅ Завершена | 8% |
| 7 | Timeline и Replay | 5% | ✅ Завершена (+ UI: Timeline Panel) | 5% |
| 8 | Scenario Lab и Test Matrix | 8% | ✅ Завершена | 8% |
| 9 | Result Analyzer и Root Cause | 6% | ✅ Завершена | 6% |
| 10 | Iteration Manager и генератор ТЗ | 8% | 🟡 Частично (per-run spec, без сквозного backlog) | 3% |
| 11 | Fix Capsule | 6% | ✅ Завершена | 6% |
| 12 | Patch Center, backup и rollback | 8% | 🟡 Частично (изолированный worktree apply + авто-тесты + условный commit + git-revert rollback; без live-проверки через реальный HTTP-роут/UI) | 6% |
| 13 | Calibration, Metrics, Pose и Artifacts | 6% | 🟡 Частично (Run Group hash-consistency guard + draft→candidate→approved/rejected workflow + persisted provenance/bundle-hash reproducibility + UI: Calibration Panel; без Metric/Pose Lab, LOO sensitivity, holdout split и artifact previews) | 3% |
| 14 | 3D Inspector | 3% | Не начата | 0% |
| 15 | Interface Contract и генерация типов | 3% | Не начата | 0% |
| 16 | Performance, Security, Accessibility | 2% | Не начата | 0% |
| 17 | End-to-end gates и release | 2% | Не начата | 0% |
|  | **Итого** | **100%** |  | **80%** |

## Правило обновления

После каждой итерации обновляются:

1. статус строки;
2. полученный процент;
3. итоговая готовность;
4. отдельный `ITERATION_N_REPORT.md`;
5. commit и Git bundle.

Частично выполненная итерация получает только подтверждённую долю своего веса. Итерация считается завершённой после тестов и exit criteria.

## Iteration 7 — 54/100
Scientific Validation Core: 21 existing scenarios, 1/3/7 × nine-pose plans, Fresh-5 trusted-data planner, synthetic boundary and Test Matrix adapter.

## Iteration 8 — 69/100
Investigation Feedback Loop: root-cause classification (P0–P3) from run status/logs/scenario checks, suspected-function matching against the function matrix, prioritized Fix Spec with acceptance criteria, allowlisted Fix Capsule export, path-contained backup manager, and dry-run-checked git patch apply/rollback. This turn's table update also corrects iterations 4–6 and 8, which were functionally complete in earlier turns but had not been marked in this file.

## Iteration 9 — 72/100
Patch Safety Lifecycle: patches are now applied inside a disposable, isolated `git worktree` (never the real tree first), the caller-supplied regression command runs there, and the real `app6` tree and a real commit are only touched if that run passes — on failure or apply error the real tree is guaranteed untouched and the worktree is always cleaned up. Rollback of an applied patch is now a real `git revert` (history-preserving) rather than only a file-copy restore. This iteration also found and fixed a real, previously-latent bug: `git apply` can silently "skip" a patch (exit code 0, no file changed, no error) when invoked with its working directory set to a subdirectory of the repository rather than the repository root — this affected both the new isolated-apply path and the original Iteration 8 `apply_patch`, and both now always run from the true repo root with `--directory=<subpath>`. Validated only against synthetic temp-git fixtures (61/61 backend tests, including new isolated-worktree pass/fail/revert cases) and the unchanged app6 regression suite (65/65); not yet exercised end-to-end through the live HTTP API or the UI.

## Iteration 10 — 74/100
Calibration Integrity Core: a new `CalibrationRegistry` enforces that a calibration Run Group (`main_extraction` + `calibration_extraction` + `calibration_build` + `main_analysis`) can never be assembled from outputs with mismatched `dataset_hash`/`code_hash`/`model_hash`/`config_hash` — any mismatch is rejected outright at registration time (fail-closed, never silently merged), with the error naming the exact hash dimension and the two conflicting roles. A Run Group only becomes `candidate` once all four roles are present and mutually consistent, and only then can it be `approved` (recording `approved_by`, `approved_at`, and a `bundle_hash` computed over every role's provenance) or `rejected`; approved/rejected Run Groups are immutable. `verify_bundle_integrity` recomputes that bundle hash from the stored members so tampering with an approved record after the fact is detectable. A trusted calibration table (already filtered by the existing `datasets.py` trust classifier) can be attached to a Run Group only after a second, independent defense-in-depth check (`assert_trusted_only`) that re-scans every row for landmark/keypoint/mesh/vertex/coordinate field names and refuses to attach if any survive — this guarantees invalid table coordinates can never reach an approved calibration bundle even if the upstream classifier regresses. Seven new REST endpoints (`/api/calibration/run-groups...`) expose create/list/get/register-member/attach-table/approve/reject/verify. Explicitly out of scope for this slice (left as open backlog per 20/80): Metric Explorer and Pose Lab visualization, LOO sensitivity, dataset train/holdout split, sparse-cell/pose-coverage reporting, and Artifact previews — none of that was implemented. Validated only against synthetic fixtures (11 new backend tests, 72/72 backend total, 65/65 app6 regression unchanged); not exercised through a live HTTP call or the UI, and no real calibration dataset was available in this sandbox to test against.
## Iteration 7 report
Timeline/Replay: run/test/photo/log tracks reconstructed from runner stdout (unittest lines + stage1 photo-progress lines), seq-based state slicing (`/timeline/state`), honest `start_is_estimated` marking when a real start timestamp is unavailable, unrecognized lines kept (not dropped). New REST endpoints: `/api/runs/{id}/timeline`, `/api/runs/{id}/timeline/state`. 5 new backend tests, 77/77 backend total. Function-level track (status_logger.py-based) deferred as a valuable but postponed enhancement.

## Interface polish pass (post-Iteration-10, ops-workbench only)
Per explicit instruction, the TZ-described forensic workstation interface stays deferred until the ops-workbench reaches 100%; this pass only audited and fixed already-built ops-workbench frontend sections (no new large surfaces added). Fixes: sidebar navigation is now functional (scrolls to each real section) instead of decorative/disabled with stale hints, and now includes the previously-missing Function Catalog entry; stale hardcoded 69% progress and stale Iteration-8 header replaced with the current 79% total; wired the already-built-but-unused safe patch-apply and git-revert backend endpoints into the Patch Center panel (isolated test gate + commit, plus revert-by-SHA), kept the legacy unsafe apply behind a confirmation; removed dead no-op code and merged error/success message states in the Patch Center; added missing error handling/try-catch around scenario loading and plan building, pipeline canvas data loading, and run cancellation; added busy/loading guards to prevent duplicate run launches and duplicate patch submissions; fixed a mislabeled catalog field (a Description label was showing task priority instead); added a visible truncation notice when the function list is capped. Verified with the full backend/unittest suite (77/77 passing); a full frontend TypeScript build could not be run in this sandbox because npm has no network access to install node_modules, so the fixes were verified by manual review and brace/paren-balance checks instead.
