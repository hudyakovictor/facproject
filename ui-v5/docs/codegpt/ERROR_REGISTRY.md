# Error Registry — DEEPUTIN (полный реестр, 90 ошибок)
Формат: ID | Описание | P (вероятность L/M/H) | I (ущерб L/M/H/C) | Этап | Предотвращение | Обнаружение | Файлы

## Часть 1. Базовые ошибки реализации (30)
| ID | Описание | P | I | Этап | Предотвращение | Обнаружение | Файлы |
|---|---|---|---|---|---|---|---|
| ER-001 | Неверный парсинг имени фото (не YYYY_MM_DD) | M | C | Stage1 | строгий regex + отказ | unit naming | stage1/naming*.py |
| ER-002 | EXIF молча заменяет дату файла | L | C | Stage1 | EXIF только corroboration | provenance tests | input_provenance.py |
| ER-003 | Коллизия hash-based photo ID | L | C | Stage1 | SHA-256 + длина | validator | engine.py |
| ER-004 | NaN в utility ломает subset/weights | M | C | Stage2 | sanitation + exact count | тест 91 | landmark_policy.py |
| ER-005 | Kabsch на NaN-координатах | M | C | Stage2 | NaN-guard до выравнивания | edge tests | core.py |
| ER-006 | Pose gap считается скалярно, не по осям | M | C | Stage2 | axis-specific gate | synthetic | analysis_policy.py |
| ER-007 | NULL активирует irreversible return | M | C | Stage2 | absolute floor | AABBAA/NULL | irreversible_return.py |
| ER-008 | FDR применяется к неверному числу точек | M | C | Stage3 | p95 order-statistic с фактическим n | multiple_testing | multiple_testing.py |
| ER-009 | Смешение raw/chronology координат | L | C | Stage2/3 | единый primary channel | schema tests | loaders/report |
| ER-010 | Порядок bins нарушен | L | C | Stage2 | константа 9 bins | bin tests | analysis_policy.py |
| ER-011 | Dataset hash зависит от порядка FS | M | C | Stage1 | сортировка + относительные пути | hash tests | input_provenance.py |
| ER-012 | Ledger пропускает файл | M | C | Stage1 | построчный учёт | count assert | input_provenance.py |
| ER-013 | Атомарный коммит частично записан | M | C | Stage1 | tmp+rename | resume validator | engine.py |
| ER-014 | Resume пропускает повреждённые записи | M | C | Stage1 | валидатор + hash-aware | resume tests | engine.py |
| ER-015 | LDM106/LDM134 индексы неверны | M | C | Stage1 | официальные индексы | landmark tests | stage1/landmarks |
| ER-016 | alpha_alb/alpha_sh перепутаны | M | C | Stage1 | проверка каналов | unit | reconstruction.py |
| ER-017 | Visibility без учёта ракурса | M | C | Stage1/2 | front/renderer/combined | visibility tests | visibility.py |
| ER-018 | Fallback skin-mask с ложным resize | M | C | Stage1 | явная policy | skin tests | skin_zones.py |
| ER-019 | Ошибка чтения BFM-кэша без понятного сообщения | M | M | API | health-check + 503 | api tests | bfm_topology.py |
| ER-020 | Upload принимает произвольный MIME | M | C | API | валидация по содержимому | api tests | server.py |
| ER-021 | Upload path traversal | L | C | API | безопасные имена | api tests | server.py |
| ER-022 | Job остаётся running после исключения | M | M | API | try/finally статусы | api tests | jobs.py |
| ER-023 | Settings не атомарны при записи | L | M | API | tmp+rename | api tests | settings.py |
| ER-024 | Отчёт показывает null как 0 | M | C | Stage3/UI | typed validators | snapshot | report.py |
| ER-025 | JSON и HTML отчёта расходятся | M | C | Stage3 | единый data model | golden files | report.py |
| ER-026 | Export не подписан версией схемы | M | M | Stage3 | versioned schema | schema tests | export.py |
| ER-027 | Тесты зависят от абсолютных путей | M | M | тесты | tmp_path/фикстуры | pytest | test_*.py |
| ER-028 | Порог калибровки применяется к некалиброванным точкам | M | C | Stage2 | calibrated count | LOPO | calibration.py |
| ER-029 | Повторный прогон даёт разные артефакты | M | C | E2E | детерминизм, seed | determinism harness | stage1/2/3 |
| ER-030 | Молчаливый откат к демо-данным при отсутствии вывода | L | C | API/UI | research mode строгий | smoke tests | server/ui |

## Часть 2. Контекстные ошибки предметной области (30)
| ID | Описание | P | I | Этап | Предотвращение | Обнаружение | Файлы |
|---|---|---|---|---|---|---|---|
| ER-101 | Pose leakage доминирует identity | M | C | Stage2 | raw + axis gap + same-bin | AUC | analysis_policy.py |
| ER-102 | Контаминация калибровки персонами | M | C | Calib | person-balanced LOPO | LOPO | calibration.py |
| ER-103 | Коррелированные кадры завышают CI | M | C | Stage3 | cluster ESS/bootstrap | stats | multiple_testing.py |
| ER-104 | Quality gate пропускает низкое качество | M | C | Stage2 | quality gate + abstention | scenario | quality.py |
| ER-105 | Профиль self-occlusion не учтён | M | C | Stage1/2 | visibility intersection | mesh tests | visibility.py |
| ER-106 | Выражение лица искажает геометрию | M | M | Stage2 | landmark QC, mismatch review | scenario | core.py |
| ER-107 | Пороги подогнаны на основном датасете | L | C | Calib | запрет, holdout | policy | stats |
| ER-108 | 9 bins меняются без нового study | L | C | вся | D-001 неизменность | diff review | analysis_policy.py |
| ER-109 | Дата из EXIF становится authoritative | L | C | Stage1 | D-002 | provenance | input_provenance.py |
| ER-110 | A→B→A ложно-положителен на NULL | M | C | Stage2 | absolute divergence floor | AABBAA | irreversible_return.py |
| ER-111 | Исключённые пары скрыты из отчёта | M | C | Stage3 | full disclosure | report audit | report.py |
| ER-112 | Числа симуляции поданы как доказательство | L | C | Stage3/UI | маркировка simulation | lint | export/ui |
| ER-113 | Candidate превращается в утверждение | M | C | UI | not_a_verdict i18n | UI tests | ui |
| ER-114 | Отчёт не показывает pose gate/coverage/space | M | C | Stage3 | обязательные поля | snapshot | report.py |
| ER-115 | Excluded records показаны как 0 | M | C | UI/Stage3 | «нет данных/исключено» | snapshot | report/ui |
| ER-116 | Hash quartet не выводится в отчёт | M | M | Stage3 | обязательный блок | snapshot | report.py |
| ER-117 | Calibration match без учёта качества | M | M | API | ранжирование по метаданным | api tests | calibration.py |
| ER-118 | Noise subtraction применим вне калибровки | M | C | API | guard | api tests | noise_calibration.py |
| ER-119 | Малые выборки без предупреждения | M | M | UI | small-sample warning | UI tests | ui |
| ER-120 | Бины без калибровочного покрытия | M | M | Calib | coverage check | health | calibration.py |
| ER-121 | Upload фото без провенанса | M | C | API | датировочная запись | api tests | server.py |
| ER-122 | Сравнение разных coordinate spaces | L | C | API | явный source_mode | api tests | compare.py |
| ER-123 | Публичный термин в финальном HTML | M | C | Export | FORBIDDEN scan | lint | export.py |
| ER-124 | Публичный термин в print/export JSON | M | C | Export | сканер всех артефактов | lint | export.py |
| ER-125 | Кластерные CI на кадр-парах | M | C | Stage3 | person-pair единица | stats | multiple_testing.py |
| ER-126 | Эксперт интерпретирует как вердикт | M | C | Рецензия | forensic protocol | review | docs/final/14 |
| ER-127 | Календарная датировка без подтверждения | M | C | Stage1 | filename authority | provenance | naming |
| ER-128 | AABBAA return без тренда | M | M | Stage2 | trend corroboration | scenario | irreversible_return.py |
| ER-129 | Повреждённый NPZ в Stage2 молча пропускается | M | C | Stage2 | валидатор артефактов | resume tests | loaders.py |
| ER-130 | Недостаточность данных для ESS | M | C | Stage3 | min-n guard | stats | multiple_testing.py |

## Часть 3. Ошибки экспериментальных решений (30)
| ID | Описание | P | I | Этап | Предотвращение | Обнаружение | Файлы |
|---|---|---|---|---|---|---|---|
| ER-201 | Fuzzing parsers генерирует шум, а не кейсы | M | M | Эксп | направленные стратегии | coverage | tests/fuzz |
| ER-202 | Mutation testing убивает тривиальные мутанты | H | M | Эксп | review мутантов | report | tests/mutation |
| ER-203 | Golden fixture не детерминирован | M | C | Эксп | фикс. seed | double-run | fixtures |
| ER-204 | Snapshot тесты хрупки к косметике | H | M | Эксп | канонизация вывода | review | snapshots |
| ER-205 | Synthetic mesh без реальной BFM-топологии | M | C | Эксп | использовать 3ddfa_v3 util | mesh tests | fixtures |
| ER-206 | Параллельные тесты дерутся за runs/ | M | M | Эксп | tmp-каталоги | CI | tests |
| ER-207 | Fuzz-кейс ломает CI на легитимном вводе | M | M | Эксп | триаж, минимальный кейс | CI log | tests/fuzz |
| ER-208 | Mutation gate блокирует поставку шумом | M | M | Эксп | порог + исключения | CI | mutation |
| ER-209 | Экспериментальный модуль без отката | M | C | Эксп | feature flag | revert plan | — |
| ER-210 | Метрика эксперимента не определена заранее | M | C | Эксп | A/B метрика до запуска | review | docs |
| ER-211 | Leverage-идея повышает сложность без эффекта | M | M | Эксп | порог LI | ретро | docs |
| ER-212 | Небезопасный откат после эксперимента | L | C | Эксп | snapshot до/после | git revert | — |
| ER-213 | Эксперимент на «грязных» данных | M | C | Эксп | фиксация seed/версий | hash | docs |
| ER-214 | UI-параллельная итерация ломает контракт | M | C | Эксп | contract tests | CI | api/ui |
| ER-215 | Генерация тестовых данных тяжелее теста | M | M | Эксп | минимум фикстур | review | fixtures |
| ER-216 | Порог успеха эксперимента завышен | M | M | Эксп | baseline до старта | метрика | docs |
| ER-217 | Ранний откат из-за одной флуктуации | M | M | Эксп | повторные прогоны | статистика | docs |
| ER-218 | Эксперимент меняет публичные формулировки | M | C | Эксп | not_a_verdict неизменен | lint | export |
| ER-219 | Эксперимент трогает 9 bins / пороги | L | C | Эксп | запрет | diff review | policy |
| ER-220 | Результат эксперимента не зафиксирован в журнале | M | M | Эксп | decision log | review | docs |
| ER-221 | Два эксперимента конфликтуют по файлам | M | M | Эксп | изоляция веток | merge | — |
| ER-222 | Эксперимент требует весов, которых нет | M | C | Эксп | preflight | CI | — |
| ER-223 | Метрика успеха не измерима в среде | M | M | Эксп | проверка измеримости | review | docs |
| ER-224 | Эксперимент увеличивает время CI недопустимо | M | M | Эксп | таймауты, параллель | CI | workflow |
| ER-225 | Fuzz finds crash → паника в проде | L | C | Эксп | sandbox до прода | fuzz CI | — |
| ER-226 | Эксперимент меняет формат артефактов | M | C | Эксп | schema version | golden | export |
| ER-227 | Эксперимент несовместим с Python 3.11 | M | M | Эксп | CI matrix | CI | pyproject |
| ER-228 | Новая зависимость тянет конфликты | M | M | Эксп | пины версий | pip check | requirements |
| ER-229 | Эксперимент затрагивает вендоренный код | M | M | Эксп | исключение из линта | diff | 3ddfa_v3 |
| ER-230 | Отсутствует план «если не сработает» | M | C | Эксп | откат + альтернатива | review | docs |

## Часть 4. Находки глубокого анализа (2026-08-03) — портируемость, контракты, дрейф схем
| ID | Описание | P | I | Этап | Предотвращение | Обнаружение | Файлы |
|---|---|---|---|---|---|---|---|
| ER-131 | settings игнорирует project_root; захардкожен /Volumes/SDCARD → 500 | H | C | API | env-first пути | API-тесты | api/settings.py |
| ER-132 | Дефолты /Volumes/SDCARD/storage в uploads/jobs/clear; жёсткий _require_removable_output | H | C | API | DEEPUTIN_STORAGE_ROOT, fail-closed | API-тесты | api/server.py |
| ER-133 | run_calibration DEFAULT_OUTPUT /Volumes/SDCARD | M | M | CLI | env-first | smoke | run_calibration.py |
| ER-134 | ui-v3 run/keys — несуществующий маршрут | H | C | UI | контракт-тесты | контракт-скрипт | ui-v3 api.ts, RunPage |
| ER-135 | v3 без mesh/compare/health — регресс функций | M | M | UI | функциональная карта | review | ui-v3 pages |
| ER-136 | Дублирующийся pose_policy_v3_9bins.csv (3ddfa_v3/atlas — устаревший) | M | C | Stage2 | единый источник atlas | diff-тест | atlas |
| ER-137 | docs 6/2/5 vs код per-bin 2–12° | M | M | Docs | актуализация | diff | docs/final |
| ER-138 | sidecar loader ждёт metadata.json/arrays; датасет info.json/normalization | H | C | Calib | адаптер info.json→Record | загрузка 943 | loaders.py |
| ER-139 | all_calibration_index.csv отсутствует | H | M | API | генератор индекса | health-тест | calibration.py |
| ER-140 | gitlink+симлинк 3DDFA-V3 битый | M | M | Repo | удалить gitlink | git audit | 3ddfa_v3 |
| ER-141 | RUN_PROJECT.sh check → нет project_readiness.py | M | M | Ops | создать скрипт | smoke | scripts/ |
| ER-142 | CONVENTIONS.py устарел (run_skin_stage1, chronology-aligned) | M | M | Docs | ревизия | review | CONVENTIONS.py |
| ER-143 | README ссылается на AGENTS.md/SKILL.md/audit_50 — нет | M | M | Docs | актуализация | link check | app6/README.md |
| ER-144 | narrative захардкожен (7 наборов/13 семейств vs 6 семейств/100 метрик) | M | M | Stage3 | вывод из данных | golden | stage3/engine.py |

**Критические (показываются в чате):** ER-001, ER-002, ER-004, ER-006, ER-007, ER-008, ER-009, ER-011, ER-015, ER-020, ER-021, ER-024, ER-029, ER-101, ER-102, ER-103, ER-111, ER-113, ER-114, ER-123, ER-124, ER-125, ER-131, ER-132, ER-134, ER-136, ER-138, ER-205. Всего в реестре: 104.

## Часть 5. Находки блоков циклов 11–30 (верифицировано 2026-08-03)
| ID | Описание | P | I | Этап | Предотвращение | Обнаружение | Файлы |
|---|---|---|---|---|---|---|---|
| ER-158 | ~40 модулей app6 без прямых тестов (geometry, naming, storage, authenticity/*, legacy_bridge, texture_*, mesh_dense, mesh_calibration, anchor_policy, leads, corroboration, date_provenance, motion, descriptors, alpha_chronology, expression_pair_gate, quality_*, run_manifest, technical_summary, temporal_axis, validation, space_selection) | H | C | Тесты | приоритизация по риску: 15 модулей-ядра в 1-й волне | coverage-отчёт | test_module/* |
| ER-159 | stage2/engine.py docstring «Использует chronology-aligned landmarks» — противоречит D-003 (raw primary) | M | C | Stage2 | актуализация docstring+CONVENTIONS | diff-review | engine.py |
| ER-160 | Нет бенчмарка Stage 2 (FDR/пары) — «при большом количестве пар медленно» | M | M | Stage2 | benchmark harness на синтетике 1k/10k пар | perf-тест | engine.py, multiple_testing.py |
| ER-161 | texture_image.py:356 TODO pose-normalized texture comparison; канал visualization_only | M | M | Stage2 | явное решение scope (не evidence) | ревью | texture_image.py |
| ER-162 | run_stage2.py без --project-root (stage1/2b имеют) — CLI-контракт неоднороден | M | M | CLI | добавить --project-root (default APP_DIR.parent) | CLI-тесты | run_stage2.py |
| ER-163 | corroboration: окна 2×window и отрицательные дельты — нет edge-тестов | M | M | Stage2 | тесты окна 0/1/45/90 дней, конфликт порядка | unit | corroboration.py |
| ER-164 | Дублирование BH: fdr_control.py и multiple_testing.py — риск расхождения | M | C | Stage2 | единый модуль BH, второй — тонкий wrapper | diff-тест q-значений | fdr_control.py, multiple_testing.py |
| ER-165 | bone_score (1/(1+z/3)) отдаётся в UI без маркера derived/display-only | M | M | API/UI | маркер derived, не evidence-метрика | контракт-тест | ui_fields.py |
| ER-166 | Семантика API-ошибок не консистентна (409/404/503 по эндпоинтам) | M | M | API | таблица статусов в контракте; тесты | api/tests | server.py |
| ER-167 | run_stage2b принимает --project-root, но не использует | M | M | CLI | убрать или использовать (config_hash) | CLI-тест | run_stage2b.py |
| ER-168 | Golden E2E fixture не содержит date-conflict пары (требование docs/final/08) | M | M | E2E | добавить конфликтную пару в фикстуру | snapshot | tests/e2e_fixture |
| ER-169 | Upload не делает fsync/не проверяет свободное место | M | M | API | fsync + preflight размера | api-тест | server.py |
| ER-170 | Upload принимает файлы по расширению, не по содержимому (magic bytes) | M | C | API | сигнатуры JPEG/PNG | api-тест | server.py |
| ER-171 | v3 рендерит keys/строки без экранирования (XSS-риск из данных) | M | C | UI | esc() как в Stage3/React-safe | UI-тест | ui-v3 pages |
| ER-172 | Harness 943 кадров без runtime-бюджета — риск таймаутов CI | M | M | CI | бюджет <15 мин; разбиение на jobs | CI-замер | workflow |
| ER-173 | Канонизация snapshot не покрывает float-точность и порядок dict | M | M | QA | sort_keys + фикс. precision + normalize-float | snapshot-тест | tests/e2e_fixture |
| ER-174 | Адаптер калибровки: пустой бин → конфуз (нет 9/9 покрытия) | M | M | Calib | явный отчёт «bin missing» | harness | loaders.py |
| ER-177 | Golden snapshot-дрейф: допуск не задан (все или ничего) | M | M | QA | допуск по категориям полей | snapshot-тест | snapshot_check.py |
| ER-178 | v3 a11y: контраст/aria не проверены | M | M | UI | axe-прогон в CI | UI-тест | ui-v3 |
| ER-179 | Детерминизм: seed не фиксирован в фикстурах (bootstrap) | M | M | QA | seed=0 везде | determinism | fixtures |
| ER-180 | v3: aria/контраст (см. 178) — расширение | M | M | UI | — | — | ui-v3 |
| ER-181 | CI: matrix Python 3.11 не зафиксирован; таймауты jobs не заданы | M | M | CI | matrix + timeout-minutes | CI | workflow |
| ER-182 | Риск утечки secrets (веса/фото) в логах CI | M | C | CI | маскирование, отдельный runner, не логировать пути | CI-аудит | workflow |

## Часть 6. Верификация 100 пунктов ТЗ-листа (2026-08-03)
| ID | Описание | Верификация | Файлы |
|---|---|---|---|
| ER-183 | V03: full_mesh_compare не применяет pose/applicability gate (Kabsch без bins/gaps) | подтверждено | api/compare.py |
| ER-184 | M05: H0/H1/H2 захардкожены в private_hypothesis (retest targets, но не priors) | подтверждено | stage2/private_hypothesis.py |
| ER-185 | Q01: preflight пересчитывает только dataset/code hash; model/config — только сравнение с expected | подтверждено частично | run_preflight.py |
| ER-186 | F03: quality_gate.accepted пишется в row; потребление threshold_multiplier в scoring требует проверки | частично | stage2/engine.py, core.calibrated_score |
| ER-187 | S01: min_coverage_ratio=0.03 есть в uv analysis, но uv_status=valid в bake/render-путях не проверен | частично | uv_module/analysis.py |
| ER-188 | R02/R03: back-facing triangles — вес в [0,1]; обнуление backface требует проверки остатка visibility.py | частично | uv_module/visibility.py |
| ER-189 | X01: per-photo info lookup не перегружает Stage1; но inventory (stage1_timeline) перечитывает CSV при каждом вызове | частично | api/pair_metrics.py, api/stage1_timeline.py |

## Отменено решением пользователя (2026-08-03) — работы не выполняются
Отменённые пункты ТЗ-листа: C02, C04, C05, D02, E04, G10 (hash-часть), Q01, Q02, Q10, R01, R02, R03, R07, R08, R09, S01, S02, S06, S09, X01, X02, X04 — см. CD-122…CD-125.
Основание: SHA-256/hash-инфраструктура избыточна (CD-122); детектор/2D fit не требуются (CD-123); UV — только визуализация, анализ кожи по face_mask.png (CD-124); X01/X02 не нужны (CD-125).
Существующее хэширование (photo_id SHA-256, dataset_hash в ledger) НЕ изменяется.

## Часть 7. Приватный слой гипотез (private_hypothesis_seed) — аудит 2026-08-03
| ID | Описание | P | I | Этап | Предотвращение | Обнаружение | Файлы |
|---|---|---|---|---|---|---|---|
| ER-190 | Нулевое тестовое покрытие приватного слоя: private_hypothesis.py, legacy_bridge.py, leads.py, stage2b/engine.py — ни одного теста в test_module | H | C | Stage2B | тесты retest-веток, leads, statuses | coverage-отчёт | test_module/* |
| ER-191 | seed-данные (37.6 MB ledger + 2.6 MB retest) закоммичены в git; manifest/coverage engine-вывода в seed отсутствует (частичный снимок); regenerated outputs не в .gitignore | M | M | Ops | зафиксировать seed как замороженный снимок; регенерация в runs/; gitignore для новых выводов | git audit | private_hypothesis_seed/ |
| ER-192 | stage2b статус «confirmed_independently» противоречит AA01: совпадение с prior leads не является независимым подтверждением | M | C | Stage2B | переименовать в prior_overlap_strong/partial | тест формулировок | stage2b/engine.py |
| ER-193 | Ветка _retest_record «retested_with_current_alignment» не покрыта тестами (все 6223 seed-записи = pending); _candidate_keys walk не проверен | M | C | Stage2B | тесты с текущими парами (matched/strong/limited) | unit | private_hypothesis.py |
| ER-194 | AA02 подтверждён кодом: run_stage2b без --prior-root и без lead_registry.json → подстановка {"status":"not_provided"} вместо fail-closed | M | C | Stage2B | fail-closed «prior registry missing» | CLI-тест | stage2b/engine.py |
| ER-195 | legacy_bridge.py — мёртвый код: не вызывается ни одним модулем (grep пуст); docstring заявляет решение D12 (bin-name mapping), но мост не интегрирован → причина 0 ретестов | H | C | Stage2B | подключить в _retest_record (normalize_photo_id/normalize_pose_bin) | интеграционный тест | legacy_bridge.py, private_hypothesis.py |