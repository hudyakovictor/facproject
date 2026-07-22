# DEEPUTIN — АУДИТ-3: модули и скрипты вне диффа, новые реализации, док-дефицит
Дата: 2026-07-22 · Ветка: `arena/019f89cd-facproject`

## 1. Охват «незатронутых» файлов
Из 278 отслеживаемых `.py` PR затронул 64. Оставшиеся **214**:
- **Вендорные (56+)**: `3ddfa_v3/*`, `FFHQ-detect-face-wrinkles/*` — внешние библиотеки, намеренно не тронуты, менять не требуется.
- **Собственные (~158)**: run-скрипты app6 (9), `app6/scripts/*` (13), stage1/skin поддержка (12), stage2/skin (16), stage2b, stage3/skin (3), тесты (24), `app7/*`, `uv_module/*`.

## 2. Привязка вызовов (образец бага run_calibration) — 🐛→✅FIXED 2
AST-проверка «метод существует у класса / имя найдено в модуле» по всем run-скриптам и `scripts/*`:
1. `run_calibration.py` — импорт `sha256_file` из `stage1.naming` (функция живёт в `stage1.utils`) → ImportError внутри `main()`. Плюс 8 мёртвых импортов после унификации на `engine._one()`. **Исправлено** (минимальный импорт-блок, `py_compile` ✓).
2. `scripts/audit_100_metric_pipeline.py` — `METRICS` из `metric_registry` — ЛОЖНОЕ срабатывание моего чекера (AnnAssign), скрипт корректен.
Полный скан графа импортов по всему app6 — **0 реальных проблем** (13 срабатываний — ложные, relative-import normalization/сабмодули).

## 3. app7 — дрейф legacy-брата — ⚠️ документировано
`app7/stage1` расходится с `app6/stage1` по 63 позициям: есть `expression.py`, `geodesic.py`, `landmark_zones.py`, свой `input_provenance.py`; НЕТ chronology alignment, `nearest_canonical_yaw`, status-логирования, `quality_zones.py`, `skin/batch.py`, `config_loader.py`, `feature_registry.py`, `migrations.py`, `patch_registry.py`. app7 самодостаточен (на него ссылаются только `app7/run_stage1.py`, `app7/verify_same_person.py`) и **не используется app6** → рассматривать как замороженный legacy; при возврате к app7 портировать исправления PR (особенно патч 01) отдельно.

## 4. Новые реализации патчей (логи/комменты) — разбор
- **`status_logger.py` v2**: `logging.basicConfig(stream=stdout)` при импорте модуля — перехват root-config хост-процесса (⚠️ библиотечный анти-паттерн, но для CLI-скриптов проекта приемлемо); flush при каждом emit ✓; `STATUS_FLOW` (need_testing→complete→closed) vs `ALWAYS_SHOW` (6 статусов) — статус `'deprecated'` (quality_zones) вне обоих словарей (см. AUDIT2, A6); обёртки `log_need_testing/close_function/_update_audit_status` самосогласованы; добавленный `status_warning()` — alias `log_warning` ✓.
- **`add_all_logging.py`** — генератор патча 25: ставит `log_status()` ПЕРЕД docstring (системный артефакт, AUDIT2 A3); функцию-генератор держим как воспроизводимый инструмент.
- **Комментарии патчей**: символьный словарь CONVENTIONS соблюдён; 2 emoji (`📝`, `🏭`) вне словаря; все `log_status`-метки совпадают с именами функций (AUDIT2 A4 ✓).

## 5. «Недоданный контент» и 3000+ символов к дописыванию — ✅FIXED
Док-дефицит (AST): **~97 600 симв.** оценочно по 148 файлам (148 файлов/функций без docstring). Приоритизированы ядровые модули патча и дописаны **модульные docstring'и (4 615 символов ≥ 3000)** в стиле CONVENTIONS:
| Файл | +символов | Содержание |
|---|---|---|
| `stage1/geometry.py` | 646 | контракт chronology alignment (R_corr = R_target@R_actual^T), POSE_BINS |
| `stage1/engine.py` | 699 | оркестрация Stage 1, schema v2.4, ключи info["chronology"], SHA256-resume |
| `stage1/reconstruction.py` | 611 | bundle-наборы вершин, QA-гейты #10/#27/#34/#37 |
| `stage2/core.py` | 631 | compare_landmarks, calibrated/zone-weighted score, mismatch-семантика |
| `stage2/engine.py` | 529 | пары, фильтры 0.5/1.5, persistence, открытые TODO |
| `stage1/validator.py` | 603 | contract-gate: CSV⇄npz, isfinite, ортонормальность, статусы |
| `stage1/assets.py` | 490 | ассеты, единственная uv_texture (S1), save_mesh-флаг |
| `stage1/utils.py` | 406 | хеши, атомарная запись, воспроизводимость |
Проверка: все 8 файлов компилируются; суть сверена с кодом (не выдумка, а фиксация фактического поведения).

## 6. YouTube-контент
Прямую сверку с YouTube выполнить невозможно (нет доступа к роликам; веб-поиск выдаёт лишь текст). Проверено вместо этого: весь контент, фигурирующий в артефактах PR (FINAL_SUMMARY, 27 патчей, статус-система, тесты), присутствует в дереве и зафиксирован в `PR_APPLICATION_REPORT.md`/`AUDIT2_REPORT.md`. Если имелся в виду конкретный ролик с инструкциями — пришлите ссылку или транскрипт, внесу недостающее отдельным коммитом.

## 7. Итог по исправлениям этого аудита
| # | Дефект | Статус |
|---|---|---|
| 1 | `run_calibration.py`: битый импорт `sha256_file` из `naming` + 8 мёртвых импортов | ✅FIXED |
| 2 | Мёртвые `numpy/cv2` в `__main__` run_calibration | ✅FIXED |
| 3 | Док-дефицит ядра (~3000 симв.) | ✅FIXED (+4615) |
| 4 | app7-дрейф | ⚠️документирован (legacy) |
| 5 | basicConfig в библиотечном модуле | ⚠️принято (CLI-проект) |

Тесты после аудита: **78 passed**, 6 failed/4 errors — без изменений (все out-of-scope от AUDIT-2: корневой `uv_module`, atlas-ассеты).
