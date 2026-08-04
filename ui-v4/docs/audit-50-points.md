# Финальный аудит ui-v4 · 50 пунктов (2026-08-04)

50 проверок всех модулей интерфейса. Результат: **2 найденных бага исправлены,
7 новых функций/кнопок добавлены, Stage 1 подтверждён неизменным, откат Stage 2/3
полностью поддержан, система рекомендаций добавлена.** Тесты: 30 passed.

---

## Backend · API (25 пунктов)

| # | Проверка | Статус |
|---|----------|--------|
| 1 | `/api/v1/health` | ✅ ok |
| 2 | `/api/v1/runtime/paths` | ✅ ok |
| 3 | `/api/v1/timeline` (126 фото, 9 бинов) | ✅ ok |
| 4 | `/api/v1/photos` (список) | ✅ ok |
| 5 | `/api/v1/photos/{id}` (детали) | ✅ ok |
| 6 | `/api/v1/photos/{id}/mesh` | ✅ 503 без весов — корректное поведение |
| 7 | `/api/v1/photos/{id}/image?kind=…` | ✅ ok |
| 8 | `/api/v1/photos/{id}/artifacts/{name}` | ✅ ok |
| 9 | `/api/v1/photos/{id}/landmarks/{n}/{space}` | ✅ ok |
| 10 | `/api/v1/photos/{id}/skin_zones` | 🐛 **было 500** → исправлено: 409 с объяснением |
| 11 | `/api/v1/zones/catalog` | 🐛 **было 500** → исправлено: 409 с объяснением |
| 12 | `/api/v1/settings` | ✅ ok |
| 13 | `/api/v1/datasets/inventory` + issues | ✅ ok |
| 14 | `/api/v1/selection/*` (defaults/evaluate/save) | ✅ ok |
| 15 | `/api/v1/profiles/*` (CRUD, freeze, diff, export) | ✅ ok |
| 16 | `/api/v1/runs/*` (list/preflight/start/cancel/stage2b/archive) | ✅ ok |
| 17 | `/api/v1/reports/*` (list/create/regenerate/file) | ✅ ok |
| 18 | `/api/v1/morphing/*` (bins/photo/diff) | ✅ ok |
| 19 | `/api/v1/landmarks/compare` + `/pairs/batch` | ✅ ok |
| 20 | `/api/v1/calibration/*` (health/workspace/thresholds) | ✅ ok |
| 21 | `/api/v1/timeline/findings` | ✅ ok |
| 22 | `/api/v1/logs*` (journal/summary/client/export) | ✅ ok |
| 23 | `/api/v1/integrity/stage1` | 🆕 **добавлено** — хэш-снимок Stage 1 |
| 24 | `/api/v1/recommendations*` | 🆕 **добавлено** — советник + настройки |
| 25 | rollback: `/runs/{id}/restore`, `/retry`, `/delete` | 🆕 **добавлено** |

## Frontend · модули (15 пунктов)

| # | Модуль | Статус |
|---|--------|--------|
| 26 | App shell, навигация, хоткеи (Ctrl+Shift+L/R) | ✅ ok |
| 27 | TimelineView + слой находок (⚑/⌁/◈/▦) | ✅ ok |
| 28 | FilterPanel (качество, поза, булевы гейты) | ✅ ok |
| 29 | A/B-режим, сравнение, jump-to-date, клавиатура | ✅ ok |
| 30 | DataManager | 🆕 кнопки «Прогоны Stage 2 →», «Калибровка →» |
| 31 | ProfilesPage | 🆕 кнопка «▶ Stage 2 с этим профилем» |
| 32 | SettingsPage | ✅ ok |
| 33 | PhotoPage (Photo Lab) | 🆕 кнопки «⌖ Точки», «◈ Morphing» |
| 34 | RunManagerPage | 🆕 Retry / Restore / Удалить + чип целостности Stage 1 |
| 35 | CalibrationPage | ✅ ok |
| 36 | MorphingWorkspace (+ тепловая карта) | ✅ ok |
| 37 | LandmarkCompareWorkspace (+ градиент) | ✅ ok |
| 38 | LogPanel | ✅ ok |
| 39 | RecommendationsPanel | 🆕 **добавлен** (карточки + настройки типов) |
| 40 | shared: api.ts / logger.ts / рендереры | ✅ ok |

## Кросс-проверки (10 пунктов)

| # | Проверка | Результат |
|---|----------|-----------|
| 41 | Stage 1 не пишется ни одним модулем (grep по writes) | ✅ подтверждено |
| 42 | `ensure_runtime_write_dirs` создаёт только registry/uploads | ✅ |
| 43 | `data/clear` трогает только api_stage1/api_stage2 | ✅ |
| 44 | Integrity-хэш Stage 1 стабилен между вызовами | ✅ (тест) |
| 45 | Прогоны уникальны, перезапись запрещена | ✅ |
| 46 | Архив → restore возвращает run без потерь | ✅ (тест) |
| 47 | Retry создаёт НОВЫЙ run (оригинал не трогается) | ✅ |
| 48 | Отчёты регенерируются без пересчёта Stage 2 | ✅ |
| 49 | Пустые состояния с действием (все страницы) | ✅ |
| 50 | tsc + vite build + pytest (30 passed) | ✅ |

---

## Что исправлено (баги)

1. **`/api/v1/photos/{id}/skin_zones` и `/api/v1/zones/catalog` → 500** при
   отсутствии `skin_zone_atlas.json` (нормативный файл не входит в частичную
   поставку). Теперь — честный HTTP 409 с объяснением, что атлас нужно
   скопировать из полной поставки 3DDFA_V3. `AtlasUnavailableError` ловится
   в обоих роутах.

## Что добавлено

### Гарантия неизменности Stage 1 + откат (ключевое требование)
- **`/api/v1/integrity/stage1`** — хэш-снимок evidence-датасета
  (timeline + manifest + упорядоченные photo_id). Первый вызов фиксирует
  baseline в `<storage>/registry/stage1_integrity_baseline.json`, дальше —
  сравнение «изменился/нет». Рекомендация «Stage 1 не изменён ✓» или
  «⚠ Stage 1 ИЗМЕНЁН» видна в Advisor и в чипе RunManager.
- **Архив ↔ restore**: `POST /runs/{id}/restore` возвращает архивированный
  run в `stage2/runs`; архивированные прогоны видны в списке с бейджем «архив»
  и **отчёты из них снова доступны** (get_run ищет и в архиве).
- **Retry**: `POST /runs/{id}/retry` создаёт новый run с конфигом старого —
  оригинал не модифицируется никогда. Это и есть цикл «настроил → запустил →
  откатился → поменял → запустил заново».
- **Delete** (только failed/cancelled): уборка мусора без риска для evidence.
- Итог: любой Stage 2/3 можно пересчитывать сколько угодно раз; Stage 1
  остаётся эталоном, и система сама контролирует его неизменность.

### Система рекомендаций (советы системы, всё подкручивается)
- `GET /api/v1/recommendations` — 14 типов советов, собираемых из реального
  состояния: целостность Stage 1, «запустите Stage 2», невалидный прогон,
  «профиль изменён после прогона», «нет отчёта», «нет public-отчёта»,
  зоны перекопирования, пропуски покрытия, слабая калибровка бина, кластеры
  тревожных пар, события возврата, дубликаты, находки Stage 2, ошибки журнала.
- Каждый совет — карточка с кнопкой действия, ведущей в нужный модуль
  (Run Manager / Timeline / Calibration / Logs / Landmark Compare / профиль).
- `GET/PUT /api/v1/recommendations/settings` — каждый тип можно выключить,
  задать лимит и общий максимум. Панель «💡 Advisor» в навигации (Ctrl+Shift+R)
  с бейджем количества, внутри — ⚙ настройки.
- Советы ничего не меняют сами — только предлагают действие.

### Отсутствующие кнопки (связки между модулями)
- DataManager → «Прогоны Stage 2 →», «Калибровка →» (после подключения Stage 1).
- ProfilesPage → «▶ Stage 2 с этим профилем» (открывает Run Manager с выбранным
  профилем и скроллом к форме).
- PhotoPage → «⌖ Точки», «◈ Morphing» (переход из Photo Lab в экспертные виджеты).
- RunManager → Retry / Restore / Delete + чип целостности Stage 1 в шапке.
- Навигация событий реализована через `deeputin:*` Custom Events.

---

## Оставшееся (не блокеры)
- `skin_zone_atlas.json` — нормативный файл 3DDFA_V3, отсутствует в частичной
  поставке; скопировать из полной поставки (тогда 2 pre-existing теста
  `test_skin_zones.py` станут зелёными).
- Полный E2E на реальном датасете /Volumes/SDCARD (веса + фото — внешнее условие).
