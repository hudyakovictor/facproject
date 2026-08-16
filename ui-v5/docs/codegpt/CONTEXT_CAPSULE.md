# Context Capsule — DEEPUTIN (facproject)

**Дата:** 2026-08-03 · **Ветка:** arena/019fc6fe-facproject · **Режим CodeGPT:** 1 (Autonomous)

## Суть проекта
Судебно-медицинская рабочая станция сравнения лиц **DEEPUTIN** (диапазон 1999–2026).
Измеряет воспроизводимость и хронологическую устойчивость 3D-геометрии лица по фото.
**Не** выносит автоматический вердикт о личности: любой флаг — повод для ручной проверки
(`not_a_verdict` обязателен в публичных артефактах).

## Пользователи
- Эксперт-аналитик / журналист-расследователь (основной пользователь UI).
- Внешний рецензент (слепая выборка, adjudication).
- Публичная аудитория (только observation-based формулировки).

## Архитектура (текущая)
- `3ddfa_v3/` — 3DDFA_V3 реконструкция лица (форк апстрима, вендоренный код).
- `app6/` — Stage 1 (извлечение), Stage 2 (парный анализ), Stage 2b (пост-обработка),
  Stage 3 (отчёт), API FastAPI (`/api/v1/*`, 36 маршрутов), калибровка.
- `ui-v2/` — React+Vite UI (9 поз, 8 режимов; vitest 248/248 зелёных, tsc+build OK).
- `ui-v3/` — новая тёмная forensic-станция (React+Vite; **нет package-lock.json**, тестов нет).
- `uv_module/` — UV-анализ; `calibration_dataset/` — 7 персон × 9 ракурсов (943 кадра, метаданные).
- `docs/final/` — 14 документов передачи (провенанс, метод, контракты, калибровка, статистика, тесты, UI, риски, runbook, decision log).

## Ключевые ограничения ТЗ (зафиксированы)
- D-001: 9 pose bins неизменны. D-002: дата из имени файла authoritative, EXIF — corroboration.
- D-003: primary coordinates = raw object-normalized. D-004: axis-specific pose gap (yaw≤6°, pitch≤2°, roll≤5°).
- D-005: NaN-safe utility, subset ровно 91. D-006: FDR=0.05. D-007: A→B→A требует абсолютный порог.
- D-008: порог калибровки защищён от ≤20% contamination, LOPO. D-010: публичный результат всегда `not_a_verdict`.
- Новый анализ кожи не добавлять (ограничение заказчика). Запрещённые публичные термины (FORBIDDEN_PUBLIC_TERMS).
- Вендоренный код (3ddfa_v3, FFHQ) не приводить к нашему стилю.

## Фактическое состояние (верифицировано 2026-08-03)
| Проверка | Результат |
|---|---|
| pytest app6/test_module | **87/87 passed** (venv `.venv`, Python 3.11) |
| ruff check app6 | **69 ошибок** (F401 ×16, UP035 ×12, F811 ×10, B007 ×8, UP017 ×7, B905 ×6, F841 ×5, S603/S310/F541) |
| Импорт app6.api.server | OK, 36 маршрутов |
| app6/api/tests | **отсутствует** (pyproject testpaths ссылается на него!) |
| ui-v2 npm ci + vitest | **248/248 passed**; tsc 0 ошибок; build OK |
| ui-v3 npm ci | **FAIL** — нет package-lock.json |
| app6/AGENTS.md, SKILL.md, scripts/audit_50_implementation_checks.py | **отсутствуют** (упомянуты в README) |
| .github (CI) | отсутствует |
| docs/final/00_README.md | утверждение «UI-тесты нельзя запустить на Linux» — **опровергнуто** (запускаются) |
| README.md | пути `/Users/victorkhudyakov/...` — не работают в этой среде |

## Пробел для следующей итерации
Достижение документированных release gates (docs/final/01, 07, 08): API runtime tests,
ruff = 0, воспроизводимый UI (v3 lockfile + тесты), CI, golden synthetic E2E fixture,
public-term lint на финальных артефактах, актуализация документации.

## Глубокий анализ (2026-08-03, 2-й проход) — верифицированные находки
| ID | Находка | Тяжесть |
|---|---|---|
| ER-131 | settings.py игнорирует project_root; путь `/Volumes/SDCARD/project_data` захардкожен → GET/PUT settings падают 500 на любой машине без этого пути | C |
| ER-132 | server.py: дефолты `/Volumes/SDCARD/storage` в uploads/jobs/data/clear; `_require_removable_output` жёстко требует этот корень → jobs недоступны на Linux | C |
| ER-133 | run_calibration.py DEFAULT_OUTPUT = /Volumes/SDCARD/... | M |
| ER-134 | ui-v3 `fetchRunKeys` → `/api/v1/run/keys/{name}` — маршрута НЕТ (сервер: `run/artifacts/{name}`, как в v2 и KEYS_IMPLEMENTATION.md) → RunPage v3 404 | C |
| ER-135 | ui-v3 не покрывает mesh/compare/full_mesh/system_health/subtract_noise/noise_model/match/upload — регресс ключевых forensических функций против v2 | M |
| ER-136 | Два разных `pose_policy_v3_9bins.csv`: app6/atlas (канонический, v3-схема, загружается пайплайном) vs 3ddfa_v3/atlas (устаревшая схема, statuses 'primary'); README называет «основным» устаревший | C |
| ER-137 | docs/final/02,05 фиксируют yaw≤6°/pitch≤2°/roll≤5°, код: per-bin yaw 2–12° (pose_gate_v2.csv) + производные pitch/roll — дрейф документации | M |
| ER-138 | `load_calibration_from_sidecar` ждёт `metadata.json` с `arrays.*`; датасет публикует `info.json` с `normalization.*` → 0 кадров загружается; `load_calibration` требует `photos/` (нет в репо) | C |
| ER-139 | `calibration_dataset/all_calibration_index.csv` отсутствует → `/api/v1/calibration/health` 404 | M |
| ER-140 | `3ddfa_v3/3DDFA-V3` — gitlink (mode 120000) + симлинк на `/Users/victorkhudyakov/...` (битый в этой среде); вендоренный код живёт в 3ddfa_v3/{model,util,face_box} | M |
| ER-141 | `RUN_PROJECT.sh check` → `app6/scripts/project_readiness.py` не существует (упомянут также в ui-v2/README и smoke_ui.py) | M |
| ER-142 | CONVENTIONS.py: ссылки на run_skin_stage1.py и app6/stage1/skin (нет); «core.py использует chronology-aligned» противоречит D-003 (raw primary) | M |
| ER-143 | app6/README.md упоминает AGENTS.md, SKILL.md, audit_50_implementation_checks.py — отсутствуют | M |
| ER-144 | stage3 narrative захардкожен: «семь наборов», «13 семейств» — факт: 6 семейств (100 метрик) в metric_registry; narrative не выводится из данных | M |

**Позитивный пересмотр:** калибровочный датасет в репо полон (943 info.json-кадра, 7 персон, 9 бинов —
совпадает с docs/final/09). Через адаптер info.json→Record калибровочный протокол (null-модели, LOPO,
contamination) становится ВЫПОЛНИМЫМ в CI без весов и фото. Блокирован только реальный Stage1-реэкстракт.

## Фаза обсуждения (18 экспертов, 10 циклов) — завершена
Коллегия расширена до 18 (PR, CR, TE + FE, ST, PV, CV, ML, MT, UX, AP, SC, QA, DO, JR, LG, MD, DL).
10 циклов перекрёстной критики (покрытие 306/306 пар к циклу 9), голосование 18 экспертов каждый цикл.
Итог: закрыто 115/118 ошибок в плане (97.5% ≥95%); готовность 12/12 DoD-гейтов (100%);
3 открытых — не блокеры (ER-227/229/230); 2 внешних условия — веса/фото и внешняя рецензия.
Полный лог: docs/codegpt/DISCUSSION_LOG.md. Следующий шаг: Code Prompt → план файлов → код.

## Приватный слой гипотез (private_hypothesis_seed) — охват подтверждён
- Данные: 6223 ledger + 6223 retest (валидный JSON, 16 источников, все retest = pending_missing_current_data) — изолированы от Stage 3/API/UI (подтверждено grep-аудитом).
- Пробелы, закрытые в плане (IT-18): ER-190 (нет тестов приватного слоя), ER-191 (seed закоммичен без manifest/coverage/gitignore), ER-192 («confirmed_independently» противоречит AA01), ER-193 (retest-ветка не покрыта), ER-194 (AA02: fail-closed prior-root), ER-195 (legacy_bridge мёртвый код — не интегрирован).
- Решения: CD-127; категория R-I в Requirements; циклы 137–138 в Discussion Log.

## Ограничения среды
- Весов моделей (assets/*.pth, face_model.npy) и фотодатасета в репо нет → полный E2E на реальных данных невозможен; используется синтетика.
- Оригинальный текст ТЗ (`docs/техническое задание проекта/aboutplatform*.txt`) в репо отсутствует → полнота соответствия ТЗ проверяется по docs/final и контрактам кода.
- Интерпретатор: `.venv/bin/python` (системный python — PEP 668, изолирован).