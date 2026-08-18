# DEEPUTIN — 50 дополнительных анализов кода (аудит ранее непроверенных участков)

**Дата:** 2026-08-18 · **Ветка:** `arena/01a01526-facproject`
**Цель:** выявление ранее не замеченных ошибок в участках, которые не входили в первый ревью-проход (25 факторов ТЗ). Проанализированы: полный текст `MatrixView.tsx`, `PersistenceAnalysis.tsx`, `Casework.tsx`, `Report.tsx`, `DataIntegrity.tsx`, `SessionJournal.tsx`, `ABCompare.tsx`, скрипты (`selftest.mjs`, `RUN_PROJECT.sh`, `route_coverage_audit.sh`), тесты (`contract.test.ts`), весь бэкенд `app6/` (API: server/jobs/compare/calibration/noise_calibration/research_timeline/stage1_timeline/photo_fields/ui_fields/settings/system_health/bfm_topology; Stage 1: engine/naming; Stage 2: evidence), утилиты (`tools/`, `uv_module/`), CI.

**Метод:** статический анализ кода построчно, проверка инвариантов данных, `python3 -m compileall app6 tools uv_module` (OK), `npm run verify` (7/7 тестов, lint, selftest — зелёный), `vite build` (OK).

**Сводка:** 50 анализов → **9 ошибок исправлено** (1 высокая, 4 средних, 4 низких), **4 логических/документационных расхождения**, остальное — подтверждённые корректные участки либо задокументированные риски.

---

## A. Исправленные ошибки (9)

| # | Участок | Ошибка | Серьёзность | Статус |
|---|---|---|---|---|
| 1 | `RUN_PROJECT.sh` (режим `ui`) | Команда `./RUN_PROJECT.sh ui` вела в несуществующий каталог `$ROOT/ui-v5/ui-v5` — **запуск интерфейса через штатный скрипт был невозможен** | **HIGH** | ✅ исправлено → `$ROOT/ui` |
| 2 | `ui/src/App.tsx` (глобальный keydown) | Enter на сфокусированной кнопке-миниатюре вызывал и нативный click (выбор нового кадра), и глобальный обработчик (открытие деталей **старого** выбранного кадра) — детали открывались не того фото | MEDIUM | ✅ guard `tagName === 'BUTTON'` |
| 3 | `ui/src/Timeline.tsx` (initialSlot/initialScroll) | Значения из URL-хэша не клампились: `#slot=9999` из закладки ломал layout до первого wheel-события | MEDIUM | ✅ кламп `[MIN_SLOT..MAX_SLOT]`, scroll ≥ 0 |
| 4 | `ui/src/PersistenceAnalysis.tsx` (backward-цепочки) | При поиске предшественников брался произвольный первый из отфильтрованного списка — цепочка могла прыгнуть к ранней паре и нарушить хронологическую непрерывность | MEDIUM | ✅ сортировка по `dateB` desc, ближайший предшественник |
| 5 | `app6/api/research_timeline.py` | `int(float(delta))` без защиты от NaN: при значении `nan` в CSV (допустимом для остальных полей, фильтруемых `_optional_num`) — `ValueError` и падение всего эндпоинта timeline | MEDIUM | ✅ через `_optional_num` с NaN-фильтром |
| 6 | `ui/src/PersistenceAnalysis.tsx` | `start` цепочки брался как `chain[0].dateB` — показывал конец, а не начало периода | LOW | ✅ `chain[0].dateA` |
| 7 | `ui/src/Report.tsx` | «Не рассмотрено» = `fdr − |decisions|` могло стать отрицательным (решения по парам вне текущего FDR-набора) | LOW | ✅ `Math.max(0, …)` |
| 8 | `ui/src/FrameDetail.tsx` | При 404 обоих изображений (face_crop и thumb) оставалась битая иконка — вторая ошибка не обрабатывалась | LOW | ✅ каскад: crop → thumb → hide |
| 9 | `ui/src/DataIntegrity.tsx` | Мёртвый код `const nullAlign = frames.length && 0` (всегда 0, нигде не рендерился) | LOW | ✅ удалён |

## B. Логические и документационные расхождения (4)

| # | Участок | Найденное | Статус |
|---|---|---|---|
| 10 | `ui/scripts/selftest.mjs` (п.4) | Проверка `check('zone robustZ guarded', badCalib > 0)` имеет **инвертированную семантику**: она «упадёт», когда калибровку зон починят (badCalib станет 0). Сейчас это документированное предупреждение, но как CI-гейт — ловушка на будущее | ⚠️ рекомендация: сделать INFO-выводом |
| 11 | `docs/PROJECT_STATUS_FOR_JOURNALIST.md` | Утверждает, что `ui/scripts/smoke_ui.py` «реализован с нуля» — **файл не существует** (в `ui/scripts/` только `selftest.mjs`); строка про 162 автотеста тоже устарела | ⚠️ документ требует актуализации |
| 12 | `route_coverage_audit.sh` | Жёсткий `cd /Users/victorkhudyakov/work` — скрипт не работает ни на одной другой машине (репозиторий же кроссплатформенный) | ⚠️ заменить на `cd "$(dirname "$0")/.."` |
| 13 | `app6/README.md` (строки 91–92) | Ссылки на несуществующие `ui-v5/AGENTS.md`, `ui-v5/SKILL.md` | ⚠️ актуализировать на `ui/` |

## C. Подтверждённые корректные участки и задокументированные риски (37)

### UI — компоненты
| # | Участок | Проверка | Вердикт |
|---|---|---|---|
| 14 | `MatrixView.tsx` grid | Годы = все года кадров (29 колонок), сетка `minmax(28px,1fr)` + overflow auto — на 1366px горизонтальный скролл, данные не теряются | OK |
| 15 | `MatrixView.tsx` corroborated | Корроборация = годы с кандидатами в ≥2 ракурсах; по данным: 1999–2026, подсветка работает | OK |
| 16 | `MatrixView.tsx` навигация | Клик по ячейке → `firstFrameOf(bin, year)` — если кадра нет (года пар ≠ года кадров), `fid` undefined, таймлайн откроется с первого кадра ракурса — приемлемо | OK |
| 17 | `Casework.tsx` очередь | `queue` = только FDR-пары всех ракурсов; `findIndex(initialPairId)` → −1 безопасен (max 0); клавиатура размонтируется вместе с секцией | OK |
| 18 | `Casework.tsx` счётчик «решено» | `decided` считает все решения из localStorage, включая пары вне текущей очереди — при неизменных данных совпадает; при обновлении данных возможен счётчик > очереди | ⚠️ риск, не ошибка |
| 19 | `SessionJournal.tsx` | `addEntry` не в deps эффектов, но использует функциональный setState — утечек/устаревания нет; лишняя запись `view_pair` при монтировании — шум, не ошибка | OK |
| 20 | `SessionJournal.tsx` storage | localStorage try/catch, лимит 500 записей, экспорт/очистка — корректно | OK |
| 21 | `ABCompare.tsx` wheel | React 17+ вешает `wheel` на root пассивно — `preventDefault()` не срабатывает (предупреждение в консоли). Функционально зум работает (скроллить нечего — overflow hidden), но при появлении скроллируемого родителя зум сломается | ⚠️ перевести на нативный listener |
| 22 | `ABCompare.tsx` pan/zoom | Общий pan/zoom для A и B — синхронное сравнение by design; drag через setPointerCapture корректен | OK |
| 23 | `ABCompare.tsx` зоны-оверлей | Сетка 33.3% позиционируется по ZONE_ORDER (high сверху) — согласовано с ZoneAtlas | OK |
| 24 | `ZoneAtlas.tsx` поиск+селект | Если `selectedPairId` отфильтрован запросом, select показывает первый из списка (value не в options) — визуально приемлемо, без падений | OK |
| 25 | `ZoneAtlas.tsx` агрегаты | Усредняются только `measured && rmse != null`; `n/total` показывает покрытие честно — инвариант «null ≠ 0» соблюдён | OK |
| 26 | `Calibration.tsx` | `quantile` по отсортированным z; семейства вычисляются из данных, не захардкожены; гистограммы SVG — корректно | OK |
| 27 | `PairOverlay.tsx` гейты | Все 11 гейтов открыты по умолчанию; `pair.status.includes('pose')` корректно ловит `residual_pose_mismatch`; «что опровергнет» — на месте | OK |
| 28 | `PairOverlay.tsx` зоны | Сортировка по raw rmse (не по z) — соответствует некалиброванному robustZ; подсказки собираются строкой | OK |
| 29 | `Timeline.tsx` bands | Логика «полоса скрыта только если скрыты ВСЕ её треки» — корректна для всех 4 зон | OK |
| 30 | `Timeline.tsx` graphH | `Math.max(240, …)` — при высоте окна < ~506px ряды переполняют контейнер; на целевых 1080p/768p проблем нет | ⚠️ edge-case |
| 31 | `Timeline.tsx` minimap | `jumpTo` по клику/драгу; кластеры-закладки исправлены в прошлой итерации (позиционирование в % SVG) | OK |
| 32 | `Timeline.tsx` виртуализация | `visible` фильтрует по viewport ±2 слота; SVG остаётся полным (305 пар) — на слабых машинах возможны просадки при zoom-out | ⚠️ известно |
| 33 | `Timeline.tsx` зум | Клампы MIN_SLOT=60/MAX_SLOT=128, привязка к курсору, `next === s` no-op на границах — корректно | OK |
| 34 | `Timeline.tsx` ховер-конфликт | Инспектор фото подавляется readout'ом графика, пока курсор в зоне графиков — мелкий UX-нюанс | ⚠️ косметика |
| 35 | `types.ts` / `track-registry.ts` | Мёртвые типы и функции (`TimelineStats`, `AnomalyMarker`, `ALL_METRICS`, `DEFAULT_VISIBLE_METRICS`, `getPairSeverity`, `getPairColor*`) — не ошибки, но балласт | ⚠️ чистка |
| 36 | `track-registry.ts` `pair_anchor` | displayMin/Max `log(14000)…log(23000)` при данных-дробях 0–1 — известное расхождение, задокументировано в `deficiency_analysis.md` (#11) | ⚠️ известно |
| 37 | `App.tsx` csvLine | Парсер кавычек корректен; в текущем CSV кавычек нет — совместимость с будущими экспортами (запятые в source_filename) не гарантирована | ⚠️ риск |
| 38 | `App.tsx` даты | `Date.parse` + сортировка; кадр с пустой датой дал бы NaN-year (validateFrames это не ловит) — при текущих данных невозможно | ⚠️ риск |
| 39 | `App.tsx` deep-links | URL-хэш (pose/id/pair/hide/view/slot/scroll) через `replaceState` — история не засоряется; initialView клампится (фикс #3) | OK |
| 40 | `App.tsx` клавиатура | Стрелки двигают кадры, `[`/`]` — пары, Esc — каскад закрытий; конфликтов с инпутами нет (guard) | OK |

### Скрипты, тесты, CI
| # | Участок | Проверка | Вердикт |
|---|---|---|---|
| 41 | `selftest.mjs` CSV-парсинг | Наивный `split(',')` без учёта кавычек — сейчас данных с запятыми нет (проверено: 0 кавычек в файле); при появлении — ложные FAIL | ⚠️ риск |
| 42 | `selftest.mjs` enum статусов | KNOWN содержит 6 статусов; в данных 4 — проверка не ложно-сработает | OK |
| 43 | `contract.test.ts` | 7 тестов контракта, node:test с type-stripping — проходят; покрывают classify/zone/validate | OK |
| 44 | `.github/workflows/ci.yml` | Бэкенд: compileall + pytest + ruff (жёсткий gate). **Frontend НЕ в CI** — регрессии UI (`npm run verify`) не ловятся на push | ⚠️ пробел |
| 45 | `vite.config.ts` storagePlugin | Path traversal через `/storage/../` не экранируется — dev-only риск, прод-сборка отдаёт только public/ | ⚠️ известно |

### Бэкенд app6
| # | Участок | Проверка | Вердикт |
|---|---|---|---|
| 46 | `api/server.py` upload | Потоковая запись, лимит 32MiB по фактическим байтам, проверка signature + декод, fsync, атомарный rename, dedupe по digest — добротная защита | OK |
| 47 | `api/server.py` storage-корни | `_storage_root` защищён от корня (`root == root.anchor` → RuntimeError); env-переопределения валидны; `stage2_resumable_20260816` — датированный хардкод с fallback-глобом | OK/⚠️ |
| 48 | `api/jobs.py` | JobManager потокобезопасен (lock), статусы честные (`blocked` без весов), история в памяти — задокументировано | OK |
| 49 | `api/compare.py` | Per-vertex heatmap после Kabsch; невидимые точки → `visible:false` (не выдаются за «совпали») — соответствует AGENTS.md | OK |
| 50 | `api/research_timeline.py` / `stage1_timeline.py` / `ui_fields.py` | NaN-фильтры (`_num`/`_optional_num`/`_float`), `boneScore` явно derived_display_only, флаги evidence не смешиваются с вердиктом; era-сегменты по годам — корректно (фикс #5 применён) | OK |

---

## Детали исправлений (что именно изменено)

```text
RUN_PROJECT.sh                          ui) cd "$ROOT/ui"            (было ui-v5/ui-v5)
ui/src/App.tsx                          guard Enter на BUTTON + abPair/persistence рендер
ui/src/Timeline.tsx                     кламп initialSlot/initialScroll; stack-fan без двойного scroll
ui/src/FrameDetail.tsx                  каскад onError face_crop → thumb → hide
ui/src/Report.tsx                       Math.max(0, …) для «не рассмотрено»
ui/src/DataIntegrity.tsx                удалён мёртвый nullAlign
ui/src/PersistenceAnalysis.tsx          backward-цепочки: ближайший предшественник; start=dateA
app6/api/research_timeline.py           NaN-safe конверсия dateDeltaDays/sourceClaimedDeltaDays
```

**Проверка после правок:** `python3 -m compileall app6` — OK; `npm run verify` (tsc + oxlint + selftest + 7 тестов) — зелёный; `vite build` — успешен; dev-сервер отдаёт данные (HTTP 200).

## Приоритеты на следующую итерацию (по результатам аудита)

1. **P0:** добавить frontend-гейт в CI (`npm run verify` в `.github/workflows/ci.yml`) — сейчас UI-регрессии не ловятся.
2. **P1:** `selftest.mjs` — парсер CSV с кавычками; убрать инвертированную проверку zone robustZ; `route_coverage_audit.sh` — относительный путь.
3. **P1:** актуализировать `docs/PROJECT_STATUS_FOR_JOURNALIST.md` и `app6/README.md` (smoke_ui.py не существует, ui-v5 ссылки).
4. **P2:** ABCompare — нативный wheel-listener; чистка мёртвых типов в `types.ts`.

*Документ — результат аудита кода, не вердикт по данным расследования.*
