# Iteration 8 — Investigation Feedback Loop

Готово: `feedback.py` — классификация причины отказа (P0–P3) по статусу прогона, логам (traceback detection) и результатам scenario checks (`no_pairs`/`pipeline_complete` → P0, нарушение научного контракта пары/corroboration → P1, timeout → P1, вторичные проверки → P2, отмена пользователем → P3). Подбор подозреваемых функций по `FUNCTION_MAP` и блоку сценария. `build_spec` формирует приоритизированное ТЗ (заголовок, human/technical summary, воспроизведение, критерии приёмки). `build_capsule` сохраняет allowlisted Fix Capsule (JSON, схема `dpo-fix-capsule-v1`, лог обрезан до 40 строк). `BackupManager` делает файловый backup/rollback только внутри allowlisted корня (`app6`), отказывает на `.git` и на путях, выходящих за пределы корня. `apply_patch` проверяет пути диффа, делает `git apply --check` перед мутацией, создаёт backup и только затем применяет патч; ошибка dry-run не оставляет следов.

API: `GET /api/runs/{run_id}/investigation`, `POST /api/capsules`, `GET /api/backups`, `POST /api/patches/apply`, `POST /api/backups/{backup_id}/rollback`. Frontend: `InvestigationPanel.tsx` — показывает приоритет, human/technical summary, подозреваемые функции, критерии приёмки, кнопку «Сформировать Fix Capsule», поле для applying diff, список бэкапов с откатом.

Проверки: backend 58/58 (включая 12 новых тестов feedback: классификация, spec с подозреваемыми функциями, capsule, backup/rollback round-trip, отказ на `.git`/выходе за корень, apply/rollback через реальный git-репозиторий), app6 65/65, frontend syntax 9/9 (`--jsx react-jsx`, единственные ожидаемые предупреждения — отсутствующие типы `@xyflow/react`/`elkjs`, не относящиеся к новым файлам), `compileall` PASS, `git diff --check` PASS, `git diff --name-only -- app6` пуст.

Ограничения (честно, без переоценки):
- Patch/backup механизм проверен только на временных git-фикстурах в тестах; против реального дерева app6 в этом прогоне не применялся.
- Iteration Manager реализован только как per-run генератор одного Fix Spec, а не как сквозной backlog по нескольким прогонам/сценариям.
- Patch Center не создаёт изолированный worktree, не запускает автоматически тесты после патча и не создаёт commit/tag при принятии — это MVP безопасного apply/backup/rollback, а не полный жизненный цикл версии.
- `_investigate` в API сейчас классифицирует только по статусу и логам прогона; для сценарных `check_result` (pair_status и т.п.) классификация протестирована в `feedback.py`, но эндпоинт пока не подключает файл `check_result.json` конкретного сценария автоматически.

Итоговая готовность: 69/100 (таблица `PROGRESS.md` также приведена в соответствие с фактически завершёнными итерациями 4–6 и 8, ранее не отмеченными).
