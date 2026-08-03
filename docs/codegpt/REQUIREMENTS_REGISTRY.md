# Requirements Registry — DEEPUTIN, итерация «Release Gates» (обновлено глубоким анализом 2026-08-03)

Статусы: ✅ выполнено · 🔄 в работе · ⏳ запланировано · ❌ нарушено · ⛔ блокировано (нет данных).

## Категория A. Провенанс и датировка (P1–P8)
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-A01 | Дата photo = имя файла `YYYY_MM_DD[_N]` (authority) | неверное имя → отказ, не тихий пропуск | ✅ |
| R-A02 | EXIF сохраняется, сравнивается, никогда не заменяет дату | conflict-флаг в выводе | ✅ |
| R-A03 | Входной ledger: файл, размер, SHA-256, duplicate link | каждый файл учтён | ✅ |
| R-A04 | Хэш dataset независим от пути и порядка FS | сортировка + относительные пути | ✅ |
| R-A05 | Preflight сверяет dataset/code/model/config hashes | 4 хэша в отчёте | ✅ |
| R-A06 | Upload через API фиксирует провенанс | датировочная запись для каждого upload | ⏳ (усиление) |

## Категория B. Геометрия и калибровка
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-B01 | Primary geometry = raw object-normalized | единый канал, Kabsch robust | ✅ |
| R-B02 | Pose gap axis-specific, 9 bins неизменны | per-bin yaw 2–12° + pitch/roll производные (pose_gate_v2.csv) | ✅ (код), ❌ (docs 6/2/5 устарели) |
| R-B03 | Utility NaN-safe, subset ровно 91 точка | exact-count тест | ✅ |
| R-B04 | Порог калибровки защищён от ≤20% contamination | contamination test + LOPO | ✅ (код), 🔄 (harness) |
| R-B05 | Калибровочный bundle пересобран на новых данных | golden bundle | ⛔ нет весов/фото |
| R-B06 | Калибровка загружается из опубликованного датасета (info.json) | адаптер → 943 Record, 7 персон, 9 бинов | ❌ (ER-138) |
| R-B07 | all_calibration_index.csv генерируется из sidecar | /api/v1/calibration/health 200 | ❌ (ER-139) |
| R-B08 | Калибровочные гейты (LOPO, contamination, negative control) выполнимы в CI | harness на 943 кадрах | ⏳ (стало возможным) |
| R-B09 | Единый источник atlas-политик | 3ddfa_v3/atlas не содержит дубликата | ❌ (ER-136) |

## Категория C. Статистика и сценарии
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-C01 | FDR=0.05, p95 order-statistic с фактическим числом точек | тест | ✅ |
| R-C02 | NULL не активирует irreversible return | AABBAA/NULL сценарии | ✅ |
| R-C03 | A→B→A детектор: абсолютный порог + тренд | сценарий | ✅ |
| R-C04 | CI с кластерным bootstrap/ESS; единица — person-pair/event | guard на n | ⏳ |
| R-C05 | Negative control AUC 0.45–0.55 | приёмка | ⏳ (стало выполнимо через B08) |

## Категория D. API
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-D01 | Runtime-тесты всех эндпоинтов server.py | app6/api/tests существует, зелёный | ⏳ (ключевой пробел) |
| R-D02 | Режим research строгий: нет данных → объясняющая ошибка, не синтетика | тесты 409/404/blocked | ✅ (код), 🔄 (тесты) |
| R-D03 | Версия схемы API явная | versioned schema | ✅ (deeputin-api-v1.0) |
| R-D04 | Upload валидирует формат/размер/тип по содержимому | тесты | ⏳ |
| R-D05 | Settings атомарны и персистентны | тест | ❌ (500 на не-macOS, ER-131) |
| R-D06 | API-дефолты портируемы (env-first, без /Volumes/SDCARD) | все endpoints работают на Linux без env-хаков | ❌ (ER-132, ER-133) |
| R-D07 | Контракт UI↔API: каждый UI-вызов имеет маршрут | контракт-скрипт зелёный | ❌ (ER-134) |

## Категория E. UI
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-E01 | v2: typecheck, vitest, build зелёные | 248/248 + tsc + build | ✅ |
| R-E02 | v3: воспроизводимая установка (package-lock.json) | npm ci на Linux | ⏳ (ключевой пробел) |
| R-E03 | v3: typecheck + build + базовые тесты | tsc 0, build, vitest | ⏳ |
| R-E04 | UI не превращает candidate в утверждение | i18n-тесты notAVerdict | ✅ |
| R-E05 | null/исключено отображается честно, не как 0 | typed validators + snapshot | ✅ (v2), 🔄 (v3) |
| R-E06 | Snapshot-тесты API response/timeline/anomalies/report | golden files | ⏳ |
| R-E07 | v3 RunPage работает (run/keys → run/artifacts) | 200 на артефакт | ❌ (ER-134) |
| R-E08 | Функциональная карта v3 vs v2 (mesh/compare/health) задокументирована | таблица покрытия | ⏳ |

## Категория F. Публичная безопасность
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-F01 | FORBIDDEN_PUBLIC_TERMS проверяется в evidence packets | lint pass | ✅ |
| R-F02 | FORBIDDEN_PUBLIC_TERMS проверяется в финальном HTML/print/export JSON | lint блокирует publication build | ⏳ (ключевой пробел) |
| R-F03 | not_a_verdict присутствует во всех публичных артефактах | сканер | ✅ (частично) |

## Категория G. Качество и инженерия
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-G01 | ruff = 0 ошибок (F, B, S, UP) в app6 | `ruff check app6` | ⏳ (69 ошибок) |
| R-G02 | compileall -q app6 без ошибок | gate | ✅ |
| R-G03 | CI (GitHub Actions) с обязательными gates | workflow | ⏳ (ключевой пробел) |
| R-G04 | Determinism: два прогона → одинаковые canonical artifacts | double-run harness | ⏳ |
| R-G05 | Golden synthetic E2E fixture (9 bins, конфликты, NULL, step, return) | snapshot сравнение | ⏳ (ключевой пробел) |
| R-G06 | Документация актуальна (README, docs/final) | нет устаревших утверждений | ❌ (ER-137, ER-142) |
| R-G07 | Упомянутые в README файлы существуют (AGENTS.md, audit_50) | наличие | ❌ (ER-143) |
| R-G08 | Нет «мёртвых ссылок» (project_readiness, run_skin_stage1, gitlink 3DDFA-V3) | link-check pass | ❌ (ER-140, ER-141) |
| R-G09 | Narrative Stage 3 выводится из данных | нет захардкоженных чисел | ❌ (ER-144) |
| R-G10 | docs/final согласованы с кодом (pose gate per-bin) | diff-review | ❌ (ER-137) |

## Критерии готовности итерации (DoD)
1. `pytest app6/test_module app6/api/tests` — зелёный.
2. `ruff check app6` — 0 ошибок.
3. `npm ci && npm run check` в ui-v2 и ui-v3 — зелёный.
4. Public-term lint pass на JSON/CSV/HTML/print артефактах.
5. Golden synthetic fixture + snapshot-сравнение — pass.
6. CI workflow отрабатывает все gates на push.
7. README/docs/final актуализированы; отсутствующие ссылки устранены.
8. Два последовательных прогона deterministic harness дают одинаковые хэши.
9. API-портируемость: все 36 маршрутов отвечают на Linux без env-хаков (ER-131…133 закрыты).
10. Калибровочный адаптер: 943 Records из репозитория, calibration health 200 (ER-138/139 закрыты).
11. Контракт UI↔API: ui-v3 не вызывает несуществующих маршрутов (ER-134 закрыт).

## Решение пользователя 2026-08-03 (обновление scope)
- Отменены работы по новым хэшам/SHA-256 (CD-122): C02, C04, C05, Q01, Q02, Q10, X04, канонизация. Существующие R-A04 (dataset hash) не меняются.
- Отменены D02/E04 (CD-123), X01/X02 (CD-125).
- Отменена UV-аналитика (CD-124): R01-R03, R07-R09, S01-S02, S06, S09; UV — только визуализация; анализ кожи по face_mask.png.
- UI: v3 — единственный интерфейс; план UI-1…UI-16 (UI_REVIEW.md), итерации IT-15…IT-17.

### Категория H. UI (добавлена)
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-H01 | 3D-инспектор в v3 (меш/heatmap/morph) | UI-1 | ⏳ IT-15 |
| R-H02 | Workspace пары без JSON-дампов | UI-2/UI-3 | ⏳ IT-15 |
| R-H03 | Настройки — форма с валидацией | UI-4 | ⏳ IT-15 |
| R-H04 | RunPage рабочий (run/artifacts) | UI-5 | ❌ ER-134 |
| R-H05 | Таймлайн с эрами/маркерами/baseline | UI-6 | ⏳ IT-16 |
| R-H06 | Analytics: matrix/drift/metrics/stats | UI-7 | ⏳ IT-16 |
| R-H07 | Noise calibration + provenance popup | UI-8/UI-9 | ⏳ IT-16 |
| R-H08 | Upload/drag&drop + data management | UI-10/UI-11 | ⏳ IT-16 |
| R-H09 | ErrorBoundary, хоткеи, i18n, theme, a11y | UI-12/UI-13 | ⏳ IT-17 |
| R-H10 | Candidate-легенда и глобальный поиск | UI-15/UI-16 | ⏳ IT-17 |

### Категория I. Приватный слой гипотез (добавлена)
| ID | Требование | Критерий приёмки | Статус |
|---|---|---|---|
| R-I01 | seed-данные (ledger/retest) валидны и изолированы от публичного Stage 3/API/UI | guard-тест; grep-аудит | ✅ (изоляция подтверждена), 🔄 (guard-тест) |
| R-I02 | legacy_bridge интегрирован в ретест (bin/photo_id нормализация) | 0-ретестов → матчинг работает | ❌ ER-195 |
| R-I03 | retest-логика покрыта тестами (pending/retested/candidate_keys) | unit-тесты зелёные | ❌ ER-190/193 |
| R-I04 | Формулировки AA01: совпадение с prior ≠ независимое подтверждение | нет «confirmed_independently» | ❌ ER-192 |
| R-I05 | stage2b fail-closed без prior-реестра | CLI-тест | ❌ ER-194 |
| R-I06 | seed — замороженный снимок с процедурой регенерации | README + .gitignore | ❌ ER-191 |
