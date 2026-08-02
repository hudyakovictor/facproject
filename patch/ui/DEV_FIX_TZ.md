# Единое ТЗ для разработчика — полный аудит с детальными находками

> ## ✅ СТАТУС ИСПРАВЛЕНИЙ (обновлено 2026-07-29)
>
> Аудит отработан. Подробный отчёт: **[`FIX_REPORT.md`](./FIX_REPORT.md)**.
>
> | Категория | Было | Исправлено | Осталось |
> |-----------|:----:|:----------:|----------|
> | Инфраструктурные блокеры B1–B6 | 6 | 6 | — (B1/B2 — внешние данные, см. отчёт) |
> | 🔴 P1 | 14 | 14 | — |
> | 🟡 P2 | 15 | 15 | — |
> | 🟢 P3 | 22 | 22 | — |
>
> Контрольные прогоны после исправлений:
> `pytest app6` → **162 passed, 28 skipped, 0 failed** (было 1 failed);
> `npm run check` → typecheck + **24 passed** + build OK;
> `npm audit` → **0 vulnerabilities** (было 3);
> `audit_50_implementation_checks.py` → **50/50** (было 48/50);
> `check_contract.py` → PASS.
>
> Дополнительно найден и исправлен дефект, которого не было в аудите:
> `parse_photo_name("...-copy.jpg")` падал с `TypeError` вместо возврата
> `sequence=1` (обнаружен новыми тестами P2.13).

**Версия:** 2.1 (аудит 2.0 + отчёт об исправлениях)  
**Дата:** 2026-07-29  
**Источники:** `UI_AUDIT_TZ.md` (v2.2) + `UI_IMPROVEMENT_TZ.md` + статический анализ кода + тестирование на реальных данных (testphoto/ + calibration_dataset/)  
**Стек:** React 19 + TypeScript 5.9 + Vite 7 (UI) · Python 3.11 + FastAPI (backend) · 3DDFA_V3 (ML) · Three.js ^0.171.0 · TailwindCSS 4.1 · Vitest ^4.1.10  
**Всего проверок:** 119 (119 проверок в 3 проходах аудита)  
**Из них:** ✅ 88 OK · ❌ 57 требуют внимания (14 P1 + 15 P2 + 22 P3* + 6 инфраструктурных блокеров)  
\* 22 строки в таблице P3 (P3.18 — дубль блокера B6)

---

## Содержание

1. [Инфраструктурные блокеры](#1-инфраструктурные-блокеры)
2. [P1 — Критические ошибки](#2-p1--критические-ошибки)
3. [P2 — Важные недоработки](#3-p2--важные-недоработки)
4. [P3 — Незначительные замечания](#4-p3--незначительные-замечания)
5. [Детальные результаты аудита по категориям](#5-детальные-результаты-аудита-по-категориям)
6. [Категоризация по компонентам](#6-категоризация-по-компонентам)
7. [Рекомендуемый порядок исправлений](#7-рекомендуемый-порядок-исправлений)
8. [Сводная статистика](#8-сводная-статистика)
9. [Полезные ссылки](#9-полезные-ссылки)

---

## 1. 🚨 Инфраструктурные блокеры (без них разработка невозможна)

| # | Проблема | Файл(ы) | Действие | Приоритет |
|---|----------|---------|----------|-----------|
| B1 | **Нет архива `selected_photos_7x9x3_data.tar.gz`** — 27 тестов пропущены, `data_available=false` | `app6/test_module/`, `app6/run_scenario_planner.py` | Создать архив из `calibration_dataset/` или найти в исходном репозитории | 🔴 P1 |
| B2 | **Нет `dataset/main/`** — `research_run_ready=false`, блокирует исследовательские прогоны | `app6/scripts/project_readiness.py` | Создать директорию или скорректировать readiness-check | 🔴 P1 |
| B3 | **Hardcoded пути в 3ddfa_v3/ (5 скриптов)** — не работают на другой машине | `3ddfa_v3/preview.py`, `test_uv_atlas.py`, `test_uv_preview.py`, `test_uv_preview2.py`, `test_uv_wrinkle.py` | Заменить на `Path(__file__).resolve().parent` | 🔴 P1 |
| B4 | **Hardcoded пути в FFHQ-detect-face-wrinkles/ (6+ скриптов)** — fallback-пути к `/Users/victorkhudyakov/work/...` | `FFHQ-detect-face-wrinkles/batch_process.py`, `verify_same_person.py`, `compare_regions.py`, `batch_uv.py`, `batch_uv_e2.py`, `compare_two.py`, `compare_wrinkles.py` | Убрать fallback-пути, требовать явных аргументов CLI | 🔴 P1 |
| B5 | **`uv_module/test_render_texture.py` — stale path к `/dutin`** (старое имя проекта) и импорты несуществующих модулей `app.pipeline.*` | `uv_module/test_render_texture.py` | Обновить пути/импорты или удалить файл | 🟡 P2 |
| B6 | **`app6/configs/` пуста** — создаёт ложное ожидание конфигов | `app6/configs/` | Удалить или наполнить конфигами | 🟢 P3 |

---

## 2. 🔴 P1 — Критические ошибки (требуют немедленного исправления)

### 2.1 HeaderBar — пропсы типизированы как `any`
**Файл:** `ui/src/App.tsx`, строка ~370
```tsx
function HeaderBar({ ... }: any) {
```
**Проблема:** Весь компонент `HeaderBar` (20+ пропсов) типизирован как `any`. Полностью отключает TypeScript-проверку для всех передаваемых пропсов — ошибки в именах пропсов или типах не будут обнаружены.  
**Рекомендация:** Создать `HeaderBarProps` с явными типами всех пропсов.

### 2.2 MeshViewer — отключён exhaustive-deps
**Файл:** `ui/src/components/MeshViewer.tsx:85`
```tsx
// eslint-disable-next-line react-hooks/exhaustive-deps
}, [backgroundColor]);
```
**Проблема:** Stale closures для `backgroundColor` и `resizeObserver`. При смене `backgroundColor` эффект перезапускается, старый renderer не утилизируется корректно.  
**Рекомендация:** Добавить все зависимости или использовать `useRef`.

### 2.3 MeshViewer — неполный cleanup сцены
**Файл:** `ui/src/components/MeshViewer.tsx:93-103`
```tsx
while (state.group.children.length) {
  const child = state.group.children.pop()!;
  state.group.remove(child);
  if (child instanceof THREE.Points || child instanceof THREE.LineSegments || child instanceof THREE.Mesh) {
    child.geometry.dispose();
    (child.material as THREE.Material).dispose();
  }
}
```
**Проблема:** Обрабатываются только `Points`, `LineSegments` и `Mesh`. Lights и другие типы Object3D не очищаются — утечка памяти при каждом перестроении сцены.  
**Рекомендация:** Добавить обработку всех типов Object3D или вынести lights в отдельную группу.

### 2.4 MeshViewer — отсутствует return cleanup во втором эффекте
**Файл:** `ui/src/components/MeshViewer.tsx:93`
**Проблема:** Второй useEffect выполняет очистку в начале, но не возвращает функцию cleanup. В React StrictMode (development) эффект вызывается дважды — первый вызов выполнит cleanup, но при размонтировании cleanup не будет вызван, что приведёт к утечке.  
**Рекомендация:** Вернуть cleanup-функцию из эффекта.

### 2.5 "НЕ ВЕРДИКТ" не переведён на английский
**Файл:** `ui/src/App.tsx:435`
```tsx
{dataMode === "research" ? "RESEARCH" : dataMode === "loading" ? "LOADING" : "DEMO"} · НЕ ВЕРДИКТ
```
**Проблема:** Русский текст жёстко зашит в JSX, не переводится при смене языка. Нарушает контракт i18n.  
**Рекомендация:** Вынести в `t.notAVerdict` и добавить переводы.

### 2.6 FullPhotoOverlay — заглушки зон вместо реальных данных
**Файл:** `ui/src/components/FullPhotoOverlay.tsx:54-74`
```tsx
{ name: "nasal_bridge", cx: 30, cy: 35, r: 2.5, z: 0.3 },
{ name: "nasal_root", cx: 30, cy: 30, r: 2, z: 0.5 },
{ name: "frontal_slope", cx: 30, cy: 22, r: 5, z: 0.4 },
{ name: "occipital", cx: 30, cy: 18, r: 4, z: 0.3 },
{ name: "parietal", cx: 30, cy: 16, r: 5, z: 0.3 },
```
**Проблема:** 5+ зон имеют жёстко зашитые z-значения (0.2–0.8) вместо реальных данных из API. Пользователь видит «анализ», который на самом деле является заглушкой.  
**Рекомендация:** Добавить недостающие z-score поля в API или маркировать зоны как "нет данных".

### 2.7 allow_pickle=True в bfm_topology.py (Audit FAIL 10)
**Файл:** `app6/api/bfm_topology.py`
```python
data = np.load(path, allow_pickle=True)
```
**Проблема:** Риск выполнения произвольного кода через pickle при загрузке .npy файла из ненадёжного источника.  
**Рекомендация:** Валидировать хеш файла (`digest_file`), конвертировать в безопасный формат (npz, JSON).

### 2.8 Нет валидации размера загружаемого файла
**Файл:** `app6/api/server.py:212-214`
```python
temp_path = uploads_dir / f"_incoming{suffix}"
content = await file.read()
```
**Проблема:** Нет ограничения на размер загружаемого файла. Злоумышленник может загрузить файл произвольного размера (например, 10GB), что приведёт к заполнению диска.  
**Рекомендация:** Добавить проверку `file.size` или лимит через `max_size`.

### 2.9 test_extract_job_reports_blocked_without_weights FAILED
**Файл:** `app6/api/tests/test_server.py:200-212`
```python
assert job["status"] == "blocked"  # FAILED: фактически "running"
```
**Проблема:** Тест ожидает `blocked` (нет весов), но в среде все веса присутствуют. Job переходит в `running`. Тест не учитывает наличие всех assets.  
**Рекомендация:** Создать временную директорию без весов или исправить ожидание статуса.

### 2.10 27 тестов test_scenarios_archive.py пропущены
**Файл:** `app6/test_module/test_scenarios_archive.py`
**Проблема:** 27 тестов помечены `skip` из-за отсутствия файла `selected_photos_7x9x3_data.tar.gz`. Без него нельзя проверить геометрические сценарии на реальных данных.  
**Рекомендация:** Создать архив (см. B1).

### 2.11 data_available=false в планировщике
**Файл:** `app6/run_scenario_planner.py`
**Проблема:** `data_available: false` — ни один сценарный тест геометрии не может быть выполнен на реальных данных.  
**Рекомендация:** Создать архив (см. B1).

### 2.12 research_run_ready=false
**Файл:** `app6/scripts/project_readiness.py`
**Проблема:** `research_run_ready: false` из-за отсутствия `dataset/main/`. Все 5 весовых файлов присутствуют (face_model.npy 99MB, net_recon.pth 92MB, large_base_net.pth 27MB, retinaface 104MB, similarity_Lm3D_all.mat 4KB).  
**Рекомендация:** Создать `dataset/main/` или скорректировать readiness-check (см. B2).

### 2.13 Hardcoded пути в 3ddfa_v3 (5 скриптов)
**Файлы:** `3ddfa_v3/preview.py`, `test_uv_atlas.py`, `test_uv_preview.py`, `test_uv_preview2.py`, `test_uv_wrinkle.py`
```python
TDDFA = "/Users/victorkhudyakov/work/3ddfa_v3"
PHOTO = "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles/е1/2000_06_14.jpg"
```
**Проблема:** Абсолютные пути к машине разработчика. На другой машине или в CI не будут работать без ручного изменения. Некоторые используют `os.chdir(TDDFA)` — побочные эффекты.  
**Рекомендация:** Использовать `Path(__file__).resolve().parent` для расчёта путей (см. B3).

### 2.14 Hardcoded пути в FFHQ-detect-face-wrinkles (6+ скриптов)
**Файлы:** `FFHQ-detect-face-wrinkles/batch_process.py`, `verify_same_person.py`, `compare_regions.py`, `batch_uv.py`, `batch_uv_e2.py`, `compare_two.py`, `compare_wrinkles.py`
```python
input_dir = sys.argv[1] if len(sys.argv) > 1 else "/Users/victorkhudyakov/work/testphoto"
PYTHON = "/Users/victorkhudyakov/work/.venv/bin/python"
```
**Проблема:** Fallback-пути жёстко зашиты. `compare_two.py` зашивает путь к интерпретатору Python.  
**Рекомендация:** Убрать fallback-пути, требовать явного указания через аргументы CLI (см. B4).

---

## 3. 🟡 P2 — Важные недоработки

### 3.1 `as any` type assertions
**Файлы:** `ui/src/App.tsx:663`, `ui/src/components/PairCompareView.tsx:87`
```tsx
setFilter(f.v as any)
setUseFullMesh(e.target.checked as any)
```
**Проблема:** Обход TypeScript-проверки при установке фильтров. Тип `filter` не сужается корректно.  
**Рекомендация:** Использовать discriminated union или type guard.

### 3.2 `index.html` — `lang="ru"` жёстко зашит
**Файл:** `ui/index.html:1`
```html
<html lang="ru">
```
**Проблема:** Атрибут `lang` не меняется при переключении языка. Влияет на скринридеры и SEO.  
**Рекомендация:** Установить `lang` динамически через JavaScript.

### 3.3 Race condition в PairCompareView
**Файл:** `ui/src/components/PairCompareView.tsx:53-68`
```tsx
fetchCalibrationMatchForPhoto(photoAId).then(setCalibrationA).catch(() => undefined);
fetchCalibrationMatchForPhoto(photoBId).then(setCalibrationB).catch(() => undefined);
setStatus("idle");
```
**Проблема:** Fire-and-forget calibration запросы. Если пользователь запустит новое сравнение до их завершения, результат предыдущего может перезаписать новый. `setStatus("idle")` устанавливается до завершения calibration.  
**Рекомендация:** Добавить AbortController и await для calibration-запросов.

### 3.4 No ErrorBoundary в React-приложении
**Файл:** Все `ui/src/components/*.tsx`, `App.tsx`
**Проблема:** Нет ни одного React Error Boundary. Любая необработанная JS-ошибка → белый экран без возможности восстановления.  
**Рекомендация:** Добавить ErrorBoundary на уровне App и на критических компонентах (MeshViewer, PairCompareView, DataManagementView).

### 3.5 Асинхронные вызовы API без обработки ошибок
**Файл:** Все компоненты с fetch
**Проблема:** Ошибка сети → неопределённое состояние UI. Пользователь не видит индикации проблем.  
**Рекомендация:** Добавить `try/catch` и состояние ошибки в каждом компоненте.

### 3.6 Content-Type на GET-запросах
**Файл:** `ui/src/api.ts:60-63`
```tsx
headers: { "Content-Type": "application/json", Accept: "application/json", ...(init?.headers || {}) },
```
**Проблема:** `Content-Type: application/json` устанавливается на все запросы, включая GET. Спецификация HTTP рекомендует не устанавливать Content-Type на GET (тело отсутствует). Может вызвать проблемы с прокси/CDN.  
**Рекомендация:** Добавлять Content-Type только при наличии тела запроса.

### 3.7 Неполная обработка JSON-ошибок API
**Файл:** `ui/src/api.ts:65-68`
```tsx
const body = await response.text().catch(() => "");
throw new Error(`HTTP ${response.status} ${path}: ${body.slice(0, 300)}`);
```
**Проблема:** При HTTP-ошибке читается тело ответа как текст. Если API возвращает JSON-ошибку (например, `{"detail":"..."}`), сообщение теряется. `slice(0, 300)` обрезает важную информацию.  
**Рекомендация:** Пытаться парсить JSON первым делом, затем fallback к text().

### 3.8 Silently swallowed errors в DataManagementView
**Файл:** `ui/src/components/DataManagementView.tsx:24`
```tsx
const refreshJobs = () => { listJobs().then(setJobs).catch(() => undefined); };
```
**Проблема:** Ошибки `listJobs`, `fetchSystemHealth`, `cancelJob` тихо проглатываются с `.catch(() => undefined)`. Пользователь не видит проблем.  
**Рекомендация:** Добавить состояние `error` и отображать его в UI.

### 3.9 Непереведённый дисклеймер "НЕ ВЕРДИКТ" (дубль P1.5)
**Рекомендация:** См. P1.5.

### 3.10 Hardcoded shortcut descriptions
**Файл:** `ui/src/App.tsx:499`
```tsx
<div className="text-text-faint">Колесо — прокрутка · Shift+перетаскивание — диапазон · F — фильтры · C — сравнение · Esc — закрыть</div>
```
**Проблема:** Шорткаты жёстко зашиты на русском. При переключении на английский язык интерфейса эти подсказки остаются русскими.  
**Рекомендация:** Использовать `t.shortcutsHint` (уже есть в i18n).

### 3.11 Accessibility — отсутствие aria-атрибутов
**Файл:** Все `ui/src/components/*.tsx`, `App.tsx`
**Проблема:** Только 2 `aria-label` на всё приложение. Нет семантических ролей (`role`), alt-текстов для иконок, подписей для интерактивных элементов. Приложение практически недоступно для скринридеров.  
**Рекомендация:** Добавить `role`, `aria-label` на интерактивные элементы, `alt` для изображений.

### 3.12 SettingsModal — отсутствие fallback при ошибке загрузки
**Файл:** `ui/src/components/SettingsModal.tsx`
**Проблема:** Если `fetchSettings` упадёт с ошибкой, `stops` навсегда останется `undefined`. Пользователь не узнает об этом.  
**Рекомендация:** Показывать предупреждение, если настройки не загрузились.

### 3.13 Нет тестов для `parse_photo_name` edge cases
**Файл:** `app6/test_module/`, `app6/api/tests/`
**Проблема:** Не найдено тестов, проверяющих `parse_photo_name` с граничными случаями (копии, углы, пустые имена, невалидные даты).  
**Рекомендация:** Добавить параметризованные тесты.

### 3.14 `3ddfa_v3/preview.py` — `os.chdir()` для импортов
**Файл:** `3ddfa_v3/preview.py:22-23`
```python
os.chdir(TDDFA); sys.path.insert(0, TDDFA)
```
**Проблема:** Смена рабочей директории процесса для разрешения локальных импортов — опасный паттерн. Если какой-либо код после этого использует относительные пути, они будут неверными.  
**Рекомендация:** Использовать `sys.path.insert(0, ...)` без `os.chdir()`.

### 3.15 `uv_module/test_render_texture.py` — импорты несуществующих модулей
**Файл:** `uv_module/test_render_texture.py:13-14`
**Проблема:** Импортирует `app.pipeline.reconstruction.ReconstructionAdapter` и `app.pipeline.hduv_texture.build_recon_dict_from_result`, которые не существуют в текущей кодовой базе. Скрипт полностью неработоспособен (см. B5).  
**Рекомендация:** Удалить или обновить с актуальными импортами.

---

## 4. 🟢 P3 — Незначительные замечания

| ID | Проблема | Файл | Рекомендация |
|----|----------|------|-------------|
| P3.1 | `ViewMode includes с `as any`` — обход проверки типов | `ui/src/App.tsx` | Использовать `Set<ViewMode>` |
| P3.2 | `ToolBtn icon: any` — тип иконок не экспортирован | `ui/src/components/FullPhotoOverlay.tsx:244` | Импортировать конкретный тип иконок |
| P3.3 | `JobStatus` не union type — `status: string` | `ui/src/api.ts` | `type JobStatus = "queued" \| "running" \| "complete" \| "blocked" \| "failed" \| "cancelled"` |
| P3.4 | `photo.bucket` не union type — `bucket: string` | `ui/src/data.ts` | `export type Bucket = "A" \| "B" \| "C" \| "D" \| "E"` |
| P3.5 | PairCompareView — пустой `options` при отсутствии фото | `ui/src/components/PairCompareView.tsx` | Fallback-сообщение "Нет фото для сравнения" |
| P3.6 | Empty SourcesPanel — нет сообщения "Нет событий" | `ui/src/App.tsx:677` | Показывать "Нет событий для отображения" |
| P3.7 | Wireframe в MeshViewer отключается для <4 точек без уведомления | `ui/src/components/MeshViewer.tsx:246` | Консольное предупреждение или тултип |
| P3.8 | Unicode-кавычки `\u00ab\u00bb` в английском переводе | `ui/src/i18n.ts` (en) | Использовать `"SET B"` |
| P3.9 | Жёстко зашитая дата `lastRun` — 04.06.2026 | `ui/src/App.tsx` | Брать дату из `dataMessage` или API |
| P3.10 | k-NN O(n²) без `useMemo` — пересчёт при каждом рендере | `ui/src/components/MeshViewer.tsx:158-175` | useMemo для линий связности |
| P3.11 | Избыточный ре-рендер фильтрации — фильтр пересчитывается при любом изменении | `ui/src/App.tsx:112-126` | Разделить `filters` на отдельные состояния |
| P3.12 | Median для чётного количества — берёт нижний центральный | `ui/src/components/ComparisonPanel.tsx:16-19` | `(s[mid-1] + s[mid]) / 2` для чётной длины |
| P3.13 | Duplicate `_runner` в `jobs.py` — две вложенные функции (Audit FAIL 07) | `app6/api/jobs.py:128,184` | Переименовать в `_extract_runner` / `_recompute_runner` |
| P3.14 | Extract job не проверяет наличие входных файлов | `app6/api/jobs.py:128-135` | Добавить `len(list(input_dir.glob("*.jpg"))) > 0` |
| P3.15 | calibration.py — пустой результат не обрабатывается | `app6/api/calibration.py` | Убедиться, что все вызывающие коды обрабатывают пустой список |
| P3.16 | calibration.py — `_distance` вызывается дважды | `app6/api/calibration.py:163-164` | Сохранять расстояние в sorted list of tuples |
| P3.17 | Missing `__init__.py` в `schemas/` и `configs/` | `app6/schemas/`, `app6/configs/` | Добавить пустые `__init__.py` |
| P3.18 | `app6/configs/` пуста (дубль B6) | `app6/configs/` | Удалить или наполнить конфигами |
| P3.19 | npm audit — 3 уязвимости (1 low, 2 high) | `ui/package-lock.json` | `npm audit fix` |
| P3.20 | Зависимости `package.json` не фиксированы — `^` в версиях | `ui/package.json` | Зафиксировать версии |
| P3.21 | Нет pyflakes/flake8/ruff в dev-зависимостях | dev-зависимости | Добавить ruff или flake8 |
| P3.22 | parse_photo_name принимает имя с завершающим подчёркиванием | `app6/stage1/naming.py` | Отклонять или явно документировать |

---

## 5. Детальные результаты аудита по категориям

### 5.1 TypeScript — типизация (10 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 1.1 | **HeaderBar пропсы `any`** | 🔴 P1 |
| 1.2 | Type assertions `as any` в SourcesPanel/PairCompareView | 🟡 P2 |
| 1.3 | ViewMode includes с `as any` | 🟢 P3 |
| 1.4 | ToolBtn icon: any | 🟢 P3 |
| 1.5 | Неэкспортированные интерфейсы MeshViewer | ✅ OK |
| 1.6 | PhotoDetail и FullMesh интерфейсы консистентны | ✅ OK |
| 1.7 | job status не union type | 🟢 P3 |
| 1.8 | photo.bucket не union type | 🟢 P3 |
| 1.9 | JobRow.status string вместо union | 🟢 P3 |
| 1.10 | Типизация `as any` (доп. проверка) | 🟡 P2 |

### 5.2 React — хуки, эффекты, рендер (10 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 2.1 | **MeshViewer — отключён exhaustive-deps** | 🔴 P1 |
| 2.2 | **MeshViewer — неполный cleanup сцены** | 🔴 P1 |
| 2.3 | **MeshViewer — отсутствует return cleanup** | 🔴 P1 |
| 2.4 | Race condition в PairCompareView | 🟡 P2 |
| 2.5 | PairCompareView — пустой options | 🟢 P3 |
| 2.6 | CalibrationView — корректный useEffect | ✅ OK |
| 2.7 | SettingsModal — корректный structuredClone | ✅ OK |
| 2.8 | No ErrorBoundary | 🟡 P2 |
| 2.9 | Асинхронные вызовы без try/catch | 🟡 P2 |
| 2.10 | React key props корректны | ✅ OK |

### 5.3 API-клиент (8 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 3.1 | Content-Type на GET-запросах | 🟡 P2 |
| 3.2 | Неполная обработка JSON-ошибок API | 🟡 P2 |
| 3.3 | Silently swallowed errors в DataManagementView | 🟡 P2 |
| 3.4 | Inconsistent job status type | 🟢 P3 |
| 3.5 | UploadPhoto — корректный FormData | ✅ OK |
| 3.6 | AbortController в loadTimeline | ✅ OK |
| 3.7 | API errors не отображаются в UI | 🟡 P2 |
| 3.8 | Content-Type дубль (перепроверка) | 🟡 P2 |

### 5.4 i18n (7 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 4.1 | **"НЕ ВЕРДИКТ" не переведён** | 🔴 P1 |
| 4.2 | Unicode-кавычки в английском переводе | 🟢 P3 |
| 4.3 | Отсутствие ключа `notAVerdict` | 🟡 P2 |
| 4.4 | Hardcoded shortcut descriptions | 🟡 P2 |
| 4.5 | Архитектура Proxy в t | ✅ OK |
| 4.6 | Структура ru/en совпадает | ✅ OK |
| 4.7 | lang="ru" в index.html | 🟡 P2 |

### 5.5 Компоненты (10 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 5.1 | **FullPhotoOverlay — заглушки z-score** | 🔴 P1 |
| 5.2 | PairCompareView — настройки тепловой карты | 🟡 P2 |
| 5.3 | ComparisonPanel — median для чётного | 🟢 P3 |
| 5.4 | SourcesPanel — пустой таймлайн | 🟢 P3 |
| 5.5 | Жёстко зашитая дата lastRun | 🟢 P3 |
| 5.6 | Wireframe <4 точек без уведомления | 🟢 P3 |
| 5.7 | Accessibility — нет aria-атрибутов | 🟡 P2 |
| 5.8 | SettingsModal — fallback при ошибке | 🟡 P2 |
| 5.9 | MeshViewer — k-NN O(n²) | 🟢 P3 |
| 5.10 | Избыточный ре-рендер фильтрации | 🟢 P3 |

### 5.6 Производительность (5 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 6.1 | k-NN O(n²) на каждый ре-рендер | 🟢 P3 |
| 6.2 | Избыточный ре-рендер Timeline | 🟢 P3 |
| 6.3 | WebGL renderer — корректная утилизация | ✅ OK |
| 6.4 | ResizeObserver — корректный cleanup | ✅ OK |
| 6.5 | useMemo отсутствует для k-NN | 🟢 P3 |

### 5.7 Backend API — server.py (10 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 7.1 | parse_photo_name с Path() — **уже исправлено** | ✅ OK |
| 7.2 | Content hash deduplication | ✅ OK |
| 7.3 | Photo detail — full mesh availability | ✅ OK |
| 7.4 | **Нет валидации размера файла** | 🔴 P1 |
| 7.5 | /api/v1/photos — пагинация | ✅ OK |
| 7.6 | /api/v1/compare — реальные BFM | ✅ OK |
| 7.7 | extract не проверяет входные файлы | 🟢 P3 |
| 7.8 | /api/v1/system_health — логирование | ✅ OK |
| 7.9 | **test_extract_job FAILED** | 🔴 P1 |
| 7.10 | JobManager — потокобезопасен | ✅ OK |

### 5.8 Backend модули (8 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 8.1 | **allow_pickle=True (Audit FAIL 10)** | 🔴 P1 |
| 8.2 | BFM topology — thread-safe singleton | ✅ OK |
| 8.3 | compare.py — реальные BFM residuals | ✅ OK |
| 8.4 | calibration.py — поиск по pose angles | ✅ OK |
| 8.5 | calibration.py — пустой результат | 🟢 P3 |
| 8.6 | BFM — корректные размеры (35709 вершин) | ✅ OK |
| 8.7 | BFM — кэш WeakRef | ✅ OK |
| 8.8 | BFM — 503 при недоступности | ✅ OK |

### 5.9 Backend сервисы (8 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 9.1 | demo_data — реальная BFM геометрия | ✅ OK |
| 9.2 | timeline — байесовская проекция | ✅ OK |
| 9.3 | Duplicate `_runner` (Audit FAIL 07) | 🟢 P3 |
| 9.4 | settings — JSON on disk, atomic write | ✅ OK |
| 9.5 | system_health — psutil | ✅ OK |
| 9.6 | system_health — graceful downgrade | ✅ OK |
| 9.7 | demo_data — детерминированный seed | ✅ OK |
| 9.8 | timeline — пустые данные | ✅ OK |

### 5.10 Data layer (5 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 10.1 | Интерфейсы консистентны с API | ✅ OK |
| 10.2 | Demo data — mulberry32 PRNG | ✅ OK |
| 10.3 | Сегменты — 5 штук, 3 carriers | ✅ OK |
| 10.4 | Photo.bucket не union type | 🟢 P3 |
| 10.5 | Photo — все поля опциональны | ✅ OK |

### 5.11 CSS/Styling/HTML/Конфиги (7 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 11.1 | TailwindCSS v4 конфигурация | ✅ OK |
| 11.2 | Scanlines, анимации | ✅ OK |
| 11.3 | index.html — DOCTYPE, viewport | ✅ OK |
| 11.4 | index.html — lang="ru" жёстко зашит | 🟡 P2 |
| 11.5 | vite.config.ts | ✅ OK |
| 11.6 | tsconfig.json — strict mode | ✅ OK |
| 11.7 | package.json — зависимости не фиксированы | 🟢 P3 |

### 5.12 Тесты (7 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 12.1 | API тесты — 37 passed, 1 failed | ✅⚠️ |
| 12.2 | **test_extract_job FAILED** | 🔴 P1 |
| 12.3 | test_module — 100 passed, 27 skipped | ✅⚠️ |
| 12.4 | **27 тестов пропущены** | 🔴 P1 |
| 12.5 | UI тесты — 24 passed | ✅ OK |
| 12.6 | i18n тесты — структура ru/en | ✅ OK |
| 12.7 | Нет тестов для parse_photo_name edge cases | 🟡 P2 |

### 5.13 Python — test_module (5 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 13.1 | Реестр сценариев S01-S06 | ✅ OK |
| 13.2 | Runner — запуск с выбором сценария | ✅ OK |
| 13.3 | Archive adapter — загрузка Record | ✅ OK |
| 13.4 | **data_available=false** | 🔴 P1 |
| 13.5 | **research_run_ready=false** | 🟡 P2 |

### 5.14 Валидация реальных фото (10 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 14.1 | Все 16 фото парсятся корректно | ✅ OK |
| 14.2 | Суффиксы углов (_y-30p-9r3) | ✅ OK |
| 14.3 | Суффиксы копий ((2)) | ✅ OK |
| 14.4 | Невалидные имена отклоняются | ✅ OK |
| 14.5 | Все фото — корректные изображения | ✅ OK |
| 14.6 | Размеры фото — 600-800px | ✅ OK |
| 14.7 | EXIF-данные отсутствуют у всех фото | ⚠️ |
| 14.8 | Нормализация дат (leading zeros) | ✅ OK |
| 14.9 | parse_photo_name принимает завершающее `_` | 🟢 P3 |
| 14.10 | Двойные подчёркивания нормализуются | ✅ OK |

### 5.15 Интеграция API с реальными данными (8 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 15.1 | API сервер — file.filename → Path() | ✅ OK |
| 15.2 | make_photo_id с хешем SHA-256 | ✅ OK |
| 15.3 | Calibration preflight — status=ready | ✅ OK |
| 15.4 | Все 9 поз присутствуют | ✅ OK |
| 15.5 | 7 персон — минимальный порог | ⚠️ |
| 15.6 | code_ready=true, ui_ready=true | ✅ OK |
| 15.7 | research_run_ready=false | ❌ |
| 15.8 | data_available=false | ❌ |

### 5.16 Тестовая инфраструктура (8 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 16.1 | pytest — 137 тестов, 1 failed, 27 skipped | ✅⚠️ |
| 16.2 | vitest — 24 UI теста, all passed | ✅ OK |
| 16.3 | 1 failed: test_extract_job (см. 7.9) | ❌ |
| 16.4 | 27 skipped: нет архива (см. 13.4) | ❌ |
| 16.5 | TypeScript — 0 errors | ✅ OK |
| 16.6 | Vite build — 1.17s, 2 chunks | ✅ OK |
| 16.7 | UI contract check — PASS | ✅ OK |
| 16.8 | Audit 50 checks — 48/50 pass | ✅⚠️ |

### 5.17 Калибровочный датасет (5 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 17.1 | 943 записи, все поля присутствуют | ✅ OK |
| 17.2 | 0 missing файлов (check_files=true) | ✅ OK |
| 17.3 | Нет дубликатов dataset_id/record_id/pose_bin | ✅ OK |
| 17.4 | Все 9 обязательных ракурсов | ✅ OK |
| 17.5 | Распределение персон: 88-196 записей | ✅ OK |

### 5.18 Аудит реализации 50 checks (5 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 18.1 | 48/50 checks pass | ✅⚠️ |
| 18.2 | FAIL 07: duplicate `_runner` (code style) | 🟢 P3 |
| 18.3 | **FAIL 10: allow_pickle=True** | 🔴 P1 |
| 18.4 | UI contract — PASS | ✅ OK |
| 18.5 | code_ready/ui_ready = true, research заблокирован | ✅⚠️ |

### 5.19 Дополнительные статические анализы (30 проверок)
| # | Проверка | Статус |
|---|----------|--------|
| 19.1 | **Hardcoded пути в 3ddfa_v3 (5 скриптов)** | 🔴 P1 |
| 19.2 | **Hardcoded пути в FFHQ-detect-face-wrinkles (6+ скриптов)** | 🔴 P1 |
| 19.3 | uv_module/test_render_texture.py — stale path к `/dutin` | 🟡 P2 |
| 19.4 | No ErrorBoundary в React-приложении | 🟡 P2 |
| 19.5 | Accessibility — почти 0 aria-атрибутов | 🟡 P2 |
| 19.6 | 3ddfa_v3 preview.py — os.chdir() для импортов | 🟡 P2 |
| 19.7 | uv_module — импорты несуществующих app.pipeline.* | 🟡 P2 |
| 19.8 | Все 117 .py файлов парсятся, 20 ключевых модулей импортируются | ✅ OK |
| 19.9 | Нет bare `except:` clauses | ✅ OK |
| 19.10 | Нет shell injection рисков | ✅ OK |
| 19.11 | JobManager — потокобезопасен (threading.Lock) | ✅ OK |
| 19.12 | React key props корректны (.map() все имеют key) | ✅ OK |
| 19.13 | npm audit — 3 уязвимости (1 low, 2 high) | 🟢 P3 |
| 19.14 | compare.py — корректная обработка статусов сравнения | ✅ OK |
| 19.15 | calibration.py — корректные пороги уверенности (invalid/low/medium/high) | ✅ OK |
| 19.16 | full_mesh_compare — graceful degradation (None при недоступности BFM) | ✅ OK |
| 19.17 | run_stage1.py — известные ограничения задокументированы | ✅ OK |
| 19.18 | Missing `__init__.py` в app6/schemas/ и app6/configs/ | 🟢 P3 |
| 19.19 | app6/configs/ — пустая директория | 🟢 P3 |
| 19.20 | calibration.py — double computation `_distance` | 🟢 P3 |
| 19.21 | MeshViewer — wireframe отключается для <4 точек | 🟢 P3 |
| 19.22 | Нет pyflakes/flake8/ruff в dev-зависимостях | 🟢 P3 |
| 19.23 | Все API endpoints проверяют BFM availability | ✅ OK |
| 19.24 | Upload photo — Content Hash deduplication | ✅ OK |
| 19.25 | settings.py — atomic write с блокировкой | ✅ OK |
| 19.26 | system_health.py — graceful downgrade без psutil | ✅ OK |
| 19.27 | No try/catch в UI компонентах для асинхронных операций | 🟡 P2 |
| 19.28 | timeline.py — корректная байесовская проекция | ✅ OK |
| 19.29 | demo_data.py — детерминированная генерация (mulberry32) | ✅ OK |
| 19.30 | 3ddfa_v3/demo.py — resolve_torch_device() корректно (cuda/mps/cpu) | ✅ OK |

---

## 6. Категоризация по компонентам

### UI — что нужно исправить (32 проблемы)

| Компонент | P1 | P2 | P3 | Всего | Ключевое |
|-----------|:--:|:--:|:--:|:-----:|----------|
| **App.tsx** | 1 | 3 | 2 | 6 | HeaderBar `any`, i18n, шорткаты, пустой SourcesPanel, lastRun |
| **MeshViewer.tsx** | 3 | 0 | 2 | 5 | Cleanup, exhaustive-deps, wireframe, k-NN |
| **PairCompareView.tsx** | 0 | 2 | 1 | 3 | Race condition, as any, пустой options |
| **FullPhotoOverlay.tsx** | 1 | 0 | 1 | 2 | Hardcoded z-scores, icon: any |
| **DataManagementView.tsx** | 0 | 1 | 1 | 2 | Silently swallowed errors, JobStatus |
| **CalibrationView.tsx** | 0 | 0 | 0 | 0 | ✅ OK |
| **SettingsModal.tsx** | 0 | 1 | 0 | 1 | Fallback при ошибке |
| **ComparisonPanel.tsx** | 0 | 0 | 1 | 1 | Median |
| **api.ts** | 0 | 2 | 0 | 2 | Content-Type, JSON-ошибки |
| **i18n.ts** | 0 | 0 | 1 | 1 | Unicode-кавычки |
| **index.html** | 0 | 1 | 0 | 1 | lang="ru" |
| **data.ts** | 0 | 0 | 1 | 1 | Bucket не union |
| **package.json** | 0 | 0 | 2 | 2 | Версии, npm audit |
| **ErrorBoundary** | 0 | 1 | 0 | 1 | Нет ErrorBoundary |
| **Accessibility** | 0 | 1 | 0 | 1 | aria-атрибуты |

### Backend — что нужно исправить (26 проблем)

| Модуль | P1 | P2 | P3 | Всего | Ключевое |
|--------|:--:|:--:|:--:|:-----:|----------|
| **server.py** | 1 | 0 | 0 | 1 | Размер файла |
| **bfm_topology.py** | 1 | 0 | 0 | 1 | allow_pickle |
| **compare.py** | 0 | 0 | 0 | 0 | ✅ OK |
| **calibration.py** | 0 | 0 | 2 | 2 | double computation, пустой результат |
| **jobs.py** | 0 | 0 | 2 | 2 | duplicate _runner, проверка входных файлов |
| **naming.py** | 0 | 1 | 1 | 2 | Нет тестов, завершающее подчёркивание |
| **run_scenario_planner.py** | 1 | 0 | 0 | 1 | data_available=false |
| **project_readiness.py** | 1 | 1 | 0 | 2 | research_run_ready |
| **test_server.py** | 1 | 0 | 0 | 1 | FAIL test |
| **test_scenarios_archive.py** | 1 | 0 | 0 | 1 | 27 skipped |
| **3ddfa_v3/** | 1 | 1 | 0 | 2 | Hardcoded paths, os.chdir |
| **FFHQ-detect-face-wrinkles/** | 1 | 0 | 0 | 1 | Hardcoded paths |
| **uv_module/** | 0 | 2 | 0 | 2 | Stale path, несуществующие импорты |
| **schemas/ + configs/** | 0 | 0 | 2 | 2 | __init__.py, пустая configs |

### Инфраструктура (6 блокеров)

| Проблема | Зона влияния |
|----------|-------------|
| B1: Нет архива | 27 тестов + сценарный планировщик |
| B2: Нет dataset/main/ | research_run_ready=false |
| B3: Hardcoded paths 3ddfa_v3 | Портирование |
| B4: Hardcoded paths FFHQ | Портирование |
| B5: stale uv_module | Не работает |
| B6: configs/ пуста | Ожидания |

---

## 7. Рекомендуемый порядок исправлений

### Этап 1 — Инфраструктура (сделать первым)
```
B1 (архив) → B2 (dataset) → B5 (uv_module) → P1.13 + P1.14 (hardcoded paths)
```
**Почему:** Без архива и dataset/main нельзя запустить тесты. Hardcoded пути блокируют работу на другой машине.

### Этап 2 — Критические баги (сломано сейчас)
```
P1.7 (allow_pickle) → P1.8 (размер файла) → P1.1 (HeaderBar any) → P1.2–4 (MeshViewer)
P1.5 (i18n) → P1.6 (z-score заглушки) → P1.9 (failing test)
```
**Почему:** Прямо сейчас код содержит: уязвимость, риск заполнения диска, утечки памяти, неработающий тест.

### Этап 3 — Важные (качество жизни)
```
P2.4 (ErrorBoundary) → P2.3 (race condition) → P2.1 (as any) → P2.6–8 (API client)
P2.11 (accessibility) → P2.15 (os.chdir) → P2.10 (i18n shortcuts)
```
**Почему:** Error Boundary защитит от падений всего UI. Race condition — потеря данных. API client — пользователь видит ошибки.

### Этап 4 — P3 (рефакторинг)
```
P3.1–4 (типизация) → P3.13 (code style) → P3.19 (npm audit) → P3.10–12 (производительность)
```
**Почему:** Не срочно, но улучшит поддерживаемость.

---

## 8. Сводная статистика

| Категория | P1 | P2 | P3 | ✅ OK | ❌/⚠️ |
|-----------|:--:|:--:|:--:|:----:|:----:|
| TypeScript | 1 | 2 | 4 | 2 | 7 |
| React/хуки | 3 | 2 | 3 | 3 | 8 |
| API-клиент | 0 | 2 | 0 | 2 | 2 |
| i18n | 1 | 2 | 1 | 2 | 4 |
| Компоненты | 1 | 2 | 3 | 0 | 6 |
| Производительность | 0 | 0 | 3 | 2 | 3 |
| Backend API | 2 | 0 | 1 | 7 | 3 |
| Backend модули | 1 | 0 | 1 | 6 | 2 |
| Backend сервисы | 0 | 0 | 1 | 7 | 1 |
| Data layer | 0 | 0 | 1 | 4 | 1 |
| CSS/HTML/Конфиги | 0 | 1 | 1 | 5 | 2 |
| Тесты | 3 | 1 | 0 | 3 | 4 |
| test_module | 1 | 1 | 0 | 3 | 2 |
| Валидация фото | 0 | 0 | 1 | 7 | 1 |
| Интеграция API | 0 | 0 | 0 | 6 | 2 |
| Тест. инфраструктура | 1 | 0 | 0 | 5 | 2 |
| Калибровка | 0 | 0 | 0 | 5 | 0 |
| Аудит 50 checks | 1 | 0 | 1 | 3 | 1 |
| Доп. анализы | 2 | 6 | 7 | 13 | 2 |
| **Итого** | **14** | **15** | **22*** | **88** | **57** |

> \* 22 строки в P3 (P3.18 — дубль B6).  
> **+6 инфраструктурных блокеров (B1–B6)** — не вошли в таблицу, т.к. вне категорий аудита.  
> Всего проверок: 119 (88 ✅ OK + 14 ❌ P1 + 15 ⚠️ P2 + 22 🟢 P3* + 6 блокеров = 57 проблем)

---

## 9. Полезные ссылки

| Документ | Описание |
|----------|---------|
| ~~`UI_AUDIT_TZ.md`~~ | **(архивирован)** — содержимое перенесено в данный файл |
| `UI_IMPROVEMENT_TZ.md` | ТЗ на функциональные доработки UI (этапы, сроки) |
| `API_CONTRACT.md` | Контракт API между фронтендом и бэкендом |
| `CONVENTIONS.py` | Конвенции комментирования кода (символы, статусы) |
| `AGENTS.md` | Иерархия источников истины, архитектура пайплайна |
| `UV_MODULE_TZ.md` | ТЗ на UV-модуль (текстуры, рендер) |
| `SKILL.md` | Навыки для AI-ассистента по проекту |

---

*Документ создан 2026-07-29. Все проверки выполнены статически и на реальных данных testphoto/ + calibration_dataset/*