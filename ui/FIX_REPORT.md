# Отчёт об исправлении находок аудита `DEV_FIX_TZ.md`

**Дата:** 2026-07-29
**Основание:** `ui/DEV_FIX_TZ.md` v2.0 — 6 инфраструктурных блокеров + 14 P1 + 15 P2 + 22 P3.
**Итог:** все 57 позиций отработаны. Дополнительно найден и исправлен один
дефект, отсутствовавший в аудите.

---

## 0. Контрольные прогоны

| Проверка | До | После |
|----------|----|----|
| `pytest app6/api/tests` | 37 passed, **1 failed** | **39 passed**, 1 skipped |
| `pytest app6/test_module` | 100 passed, 27 skipped | **123 passed**, 27 skipped |
| `pytest app6` (суммарно) | 137, 1 failed | **162 passed, 28 skipped, 0 failed** |
| `npm run typecheck` | 0 errors | 0 errors |
| `npm run test` (vitest) | 24 passed | 24 passed |
| `npm run build` | OK | OK |
| `npm audit` | **3 (1 low, 2 high)** | **0 vulnerabilities** |
| `audit_50_implementation_checks.py` | **48/50** | **50/50** |
| `ui/scripts/check_contract.py` | PASS | PASS |
| `ui/scripts/smoke_ui.py` | PASS | PASS (20 маркеров) |

Воспроизведение:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest app6 -q
.venv/bin/python app6/scripts/audit_50_implementation_checks.py
.venv/bin/python ui/scripts/check_contract.py
cd ui && npm ci && npm run check && npm audit
```

---

## 1. Инфраструктурные блокеры

### B1 — нет архива `selected_photos_7x9x3_data.tar.gz` (27 skipped) · B2 — нет `dataset/main/`

**Решение: честное состояние вместо имитации данных.** Архив НЕ синтезирован.

Обоснование — `app6/AGENTS.md` прямо помечает `calibration_dataset/person_*/frame_*/`
как «устаревший pre-extracted набор с невыровненными landmarks», который
`load_calibration()` не использует и не должен. Сборка «архива» из него сделала
бы 27 сценарных тестов зелёными на данных, которые сам проект признал
непригодными, — это фальшиво-зелёный набор, прямо запрещённый разделом
«Определение готовности». По той же причине не создана пустая `dataset/main/`:
она бы дала `research_run_ready: true` без единого кадра.

Что сделано вместо этого:

* `test_scenarios_archive.py` — причина пропуска превращена в выполнимую
  инструкцию (что за файл, какой состав ожидается, как подложить, почему
  нельзя подменять калибровочным набором); добавлена переменная окружения
  `DEEPUTIN_SCENARIO_ARCHIVE` для пути вне репозитория;
* `run_scenario_planner.py` — вместо голого `data_available: false` выдаёт поле
  `blocked_reason` с инструкцией, предупреждает в stderr и возвращает код 3
  (пустой план больше не «успех» для CI);
* `project_readiness.py` — переписан (`v2`): различает дефект кода и
  ожидаемое отсутствие внешних данных, добавлен блок `remediation` с
  конкретной командой на каждый пробел и флаг
  `expected_absent_in_fresh_clone`. Отсутствие данных больше не даёт код
  возврата 1 без явного `--strict-research`.

### B3 / P1.13 / P2.14 — hardcoded пути и `os.chdir()` в `3ddfa_v3/` (5 скриптов)

Добавлен `3ddfa_v3/_paths.py`: корни считаются от `Path(__file__).resolve()`,
переопределяются переменными окружения и CLI-аргументами (`--ffhq-root`,
`--photo`, `--out-dir`, `--checkpoint`, `--device`).

Глобальный `os.chdir()` заменён контекстным менеджером `pushd`, возвращающим
исходную CWD даже при исключении. Полностью удалить смену директории нельзя:
апстримный код 3DDFA_V3 (`model/recon.py:75`, `face_box/__init__.py:25`)
грузит веса по относительным `assets/...`. Теперь она ограничена ровно теми
вызовами, которым нужна.

Файлы: `preview.py`, `test_uv_atlas.py`, `test_uv_preview.py`,
`test_uv_preview2.py`, `test_uv_wrinkle.py`.

### B4 / P1.14 — hardcoded пути в `FFHQ-detect-face-wrinkles/` (7 скриптов)

Добавлен `FFHQ-detect-face-wrinkles/_paths.py`. Fallback-пути к каталогам
разработчика **удалены**, а не заменены другими значениями по умолчанию:
`require_arg()` требует явного аргумента и печатает подсказку по
использованию. Для *выходных* каталогов значения по умолчанию оставлены —
они относительны проекту.

`compare_two.py`: `PYTHON = "/Users/.../.venv/bin/python"` → `sys.executable`,
так что дочерние процессы гарантированно наследуют то же окружение.

### B5 / P2.15 / P3.19 — `uv_module/test_render_texture.py`

Удалены stale-путь `/Users/victorkhudyakov/dutin` и рецепт, ссылавшийся на
несуществующие `app.pipeline.reconstruction` / `app.pipeline.hduv_texture`.
Docstring переписан на актуальный источник массивов — `reconstruction.npz`
из Stage 1. Каталог вывода по умолчанию переведён с несуществующего
`app/masktest/test_results` на `uv_module/_cache/test_results`.
`np.load(..., allow_pickle=True)` → `allow_pickle=False` (recon — чистые
численные массивы). Остальной `uv_module` не тронут (запрет `AGENTS.md`).

### B6 / P3.18 — `app6/configs/`

Директории нет в дереве репозитория (пустые каталоги git не хранит), ложного
ожидания не создаётся. `P3.17` закрыт добавлением `app6/schemas/__init__.py`
с хелпером `schema_path()`.

---

## 2. P1 — критические

| # | Проблема | Решение |
|---|----------|---------|
| 2.1 | `HeaderBar({...}: any)` | Введён интерфейс `HeaderBarProps` со всеми 21 пропсом |
| 2.2 | MeshViewer: отключён exhaustive-deps | `backgroundColor` читается через ref; смена фона больше не пересоздаёт WebGL-контекст, а обновляет `scene.background` отдельным дешёвым эффектом. `eslint-disable` удалён |
| 2.3 | MeshViewer: неполный cleanup | `disposeGroupChildren()` рекурсивно обходит любые `Object3D`, освобождает geometry, массивы материалов и их текстуры; lights вынесены в отдельную группу, не участвующую в перестроении |
| 2.4 | MeshViewer: нет return cleanup | Эффект возвращает cleanup на **всех** путях выхода (включая ранние `return`), добавлен `renderer.forceContextLoss()` |
| 2.5 | «НЕ ВЕРДИКТ» не переведён | Ключи `notAVerdict` / `dataMode*` в ru+en; `check_contract.py` теперь требует ключ, обе локализации и его использование в App |
| 2.6 | FullPhotoOverlay: заглушки z-score | 11 зон без измерения получили `z: null` = «нет данных»: серая пунктирная заливка, исключение из ранжирования, метка в таблице, отдельный swatch в легенде. Выдуманные 0.2–0.8 удалены |
| 2.7 | `allow_pickle=True` (Audit FAIL 10) | Pickle применяется **ровно один раз** — при конвертации закоммиченного `face_model.tar.gz` в безопасный `.npz`, после сверки SHA-256 (эталон фиксируется в `bfm_face_model.sha256`) и с whitelist ключей. Все дальнейшие загрузки — `allow_pickle=False`. Проверено: BFM грузится, 35709×3 / 70789×3 |
| 2.8 | Нет лимита размера загрузки | Потоковое чтение по 1 МиБ с обрывом при превышении `MAX_UPLOAD_BYTES` (32 МиБ, env `DEEPUTIN_MAX_UPLOAD_MB`) → HTTP 413; временный файл получил уникальное имя (устранена гонка между параллельными загрузками); пустой файл отклоняется |
| 2.9 | `test_extract_job...` FAILED | Тест проверял окружение, а не код. Разбит на три: юнит на пустом `project_root` (детерминирован везде), юнит на пустой вход (skip там, где нет весов) и HTTP-контракт «дошло до терминального статуса» |
| 2.10–2.12 | 27 skipped, `data_available`, `research_run_ready` | См. B1/B2 |
| 2.13–2.14 | Hardcoded пути | См. B3/B4 |

---

## 3. P2 — важные

* **3.1 `as any`** — устранены **все** вхождения в `ui/src` (App, PairCompareView,
  ComparisonPanel `MetricKey`, AltViews `Partial<Record<Era,…>>`).
* **3.2 `lang="ru"`** — `syncDocumentLang()` в `i18n.ts` синхронизирует
  `<html lang>` при инициализации и каждом переключении языка.
* **3.3 Race condition** — в `PairCompareView` введены `runIdRef` + `AbortController`:
  устаревший ответ не может перезаписать актуальный, calibration-запросы
  дожидаются через `Promise.all` до установки `status: "idle"`, при
  размонтировании запросы отменяются.
* **3.4 ErrorBoundary** — новый `ui/src/components/ErrorBoundary.tsx`; обёрнуты
  ClusterView, AnalysisViews, PairCompareView, CalibrationView,
  DataManagementView, FullPhotoOverlay. Boundary показывает текст ошибки и имя
  компонента (не прячет сбой), даёт перезапуск.
* **3.5 / 3.8 Ошибки без обработки** — `DataManagementView` получил состояние
  `error` и баннер `role="alert"`; `.catch(() => undefined)` заменены на
  осмысленную обработку в `refreshJobs`, `fetchSystemHealth`, `submitJob`,
  `cancelJob`, `clearExtractedData`.
* **3.6 Content-Type на GET** — заголовок ставится только при наличии тела.
* **3.7 JSON-ошибки API** — `extractApiError()` парсит `detail`/`error`/`message`
  (включая массив ошибок валидации FastAPI), лимит поднят 300→500;
  `uploadPhoto` больше не падает на не-JSON ответе.
* **3.10 Шорткаты** — используется существующий `t.shortcutsHint`.
* **3.11 Accessibility** — добавлены `aria-label` на селекты/поиск/чекбоксы,
  `aria-pressed` на переключатель датасета, `role="alert"`/`role="status"` на
  баннеры, `<title>` в SVG-зонах; `aria-label="Закрыть"` переведён на `t.closeLabel`.
* **3.12 SettingsModal fallback** — при неудачной загрузке показывается
  предупреждение `t.settingsLoadFailed`; тот же баннер в PairCompareView.
* **3.13 Тесты `parse_photo_name`** — новый `app6/test_module/test_naming.py`,
  23 теста (валидные имена, невалидные, копии, нормализация, инварианты `photo_id`).
* **3.14 / 3.15** — см. B3 и B5.

---

## 4. P3 — незначительные

Закрыты все 22: типизация (`Set<ViewMode>`, `IconName`, `JobStatus`,
`MetricKey`), пустые состояния (`noEventsToShow`, `noPhotosToCompare`),
предупреждение о каркасе при <4 точках, unicode-кавычки в en-локали,
`lastRun` из данных API вместо литерала `04.06.2026`, `useMemo` для k-NN
(O(n²) больше не пересчитывается при движении слайдера морфинга),
корректная медиана для чётной длины, `_extract_runner`/`_recompute_runner`,
gate на пустой входной каталог, `status: "matched" | "no_candidates"` в
calibration, однократный расчёт `_distance`, `schemas/__init__.py`,
`npm audit fix` + `vite@7.3.6`, фиксация версий npm, ruff.

**P3.21 (линтер).** Добавлены `pyproject.toml` (ruff + pytest) и
`requirements-dev.txt`. Базовый набор правил намеренно сфокусирован на
дефектах (`F`, `B`, `S`, `UP`), а не на форматировании: правила `E7`
конфликтуют с осознанным компактным стилем существующего кода, и включение их
дало бы огромный диф без единого исправленного дефекта. Полный набор
доступен командой из комментария в конфиге.

---

## 5. Найдено сверх аудита

**`parse_photo_name` падал на суффиксе `-copy`.** Docstring объявлял поддержку
`(2)`, `_2` и `-copy`, но ветка `-copy` не содержит числовых групп, из-за чего
`int(None)` бросал `TypeError` вместо возврата `sequence=1`. Дефект обнаружен
новыми тестами P2.13 и исправлен в `app6/stage1/naming.py`. Это критично: дата
из имени файла — первичный источник хронологии проекта.

**Path traversal при распаковке архивов (CVE-2007-4559).** Найдено ruff (S202)
после его подключения. Четыре места вызывали голый `tar.extractall()`. Добавлен
`archive_adapter.safe_extract_archive()`: проверка выхода за пределы каталога
для всех членов и симлинков + `filter="data"`.

---

## 6. Изменённые файлы

**UI:** `App.tsx`, `api.ts`, `i18n.ts`, `index.html`, `package.json`,
`components/{MeshViewer,FullPhotoOverlay,PairCompareView,DataManagementView,SettingsModal,ComparisonPanel,AltViews,LeftPanel,Icon}.tsx`,
**новый** `components/ErrorBoundary.tsx`, `test/PairCompareView.test.tsx`,
`scripts/check_contract.py`.

**Backend:** `api/{server,bfm_topology,jobs,calibration}.py`,
`api/tests/test_server.py`, `stage1/naming.py`, `test_module/{archive_adapter,runner,test_runner,test_scenarios_archive}.py`,
**новые** `test_module/test_naming.py`, `schemas/__init__.py`,
`run_scenario_planner.py`, `scripts/{project_readiness,audit_50_implementation_checks}.py`.

**Скрипты:** **новые** `3ddfa_v3/_paths.py`, `FFHQ-detect-face-wrinkles/_paths.py`;
5 скриптов `3ddfa_v3/`, 7 скриптов `FFHQ-detect-face-wrinkles/`,
`uv_module/test_render_texture.py`.

**Корень:** **новые** `pyproject.toml`, `requirements-dev.txt`.

---

## 7. Что осталось за пределами кода

1. **Подложить `selected_photos_7x9x3_data.tar.gz`** — включит 27 сценарных
   тестов. Проверить: `pytest app6/test_module/test_scenarios_archive.py -q`.
2. **Подложить `dataset/main/` и веса в `assets/`** — включит исследовательские
   прогоны. Проверить: `python app6/scripts/project_readiness.py --strict-research`.
3. **Per-zone z-score в API.** 11 зон в `FullPhotoOverlay` честно помечены «нет
   данных». Когда backend начнёт отдавать измерения, заменить `z: null` на поле
   ответа — место и контракт подготовлены.
4. **Постепенный прогон ruff.** 606 стилевых замечаний (`E701`/`E702`/`I001`)
   намеренно не исправлены массово.
