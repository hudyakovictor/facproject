# DEEPUTIN UI v4 — профессиональный forensic timeline

UI v4 полностью переписан как монтажный таймлайн уровня Adobe Premiere и работает только с реальными ответами `app6`. В исходниках отсутствуют mock-датасеты, seeded/random generation, фиктивные события, identity hypotheses и клиентские «выводы».

## Интеграция с app6

Vite dev proxy направляет `/api` на `http://127.0.0.1:8000`. Альтернативный dev backend задаётся `APP6_API_URL`; канонический production base URL, перенесённый из UI v2, — `VITE_API_BASE_URL`. Для отдельного timeline допускается `VITE_TIMELINE_API_URL`.

Используемые контракты:

- `GET /api/v1/timeline`
- `GET /api/v1/photos/{id}`
- `GET /api/v1/photos/{id}/image?kind=thumbnail|face_crop|original`
- `GET /api/v1/photos/{id}/info_keys`
- `GET /api/v1/photos/{id}/skin_zones`
- `GET /api/v1/pairs/{a}/{b}/metrics`
- `GET /api/v1/health`
- `GET /api/v1/calibration/health`
- `GET /api/v1/system/health`
- `GET /api/v1/run/summary`
- `GET /api/v1/run/artifacts/{name}`
- `GET /api/v1/report/summary`
- `GET /api/v1/report/sections/{name}`

Null/NaN отображаются как `—`, а не преобразуются в ноль.

## Управление

- **Wheel** — zoom 1×–96× с сохранением даты под курсором.
- **Shift+Wheel / горизонтальный touchpad** — быстрое перемещение по времени.
- **Space+drag / средняя кнопка мыши** — hand tool.
- **Клик по ruler** — playhead.
- **Клик по кадру** — выбор A.
- **Shift+Click** — выбор B для реального pair endpoint.
- **Double Click** — оригинал из app6.
- **Fit** — показать весь временной диапазон.
- Navigator внизу показывает плотность реальных кадров и viewport.

## Архитектурные гарантии

- 9 синхронных pose tracks с фиксированным track rail.
- Виртуализация карточек по горизонтальному viewport.
- Lazy loading реальных thumbnail.
- Независимое скрытие треков без изменения датасета.
- Поиск по ID, дате, era, pose и flags.
- Фильтры не меняют и не удаляют backend-данные.
- A/B inspector запрашивает метрики только после реального выбора двух кадров.
- Error/empty/loading состояния не подменяются фиктивным контентом.
- Интерфейс явно маркирован `Observation only · not a verdict`.

## Проверка без установки зависимостей

По требованию зависимости не устанавливались. Выполнена статическая проверка отсутствия mock/random/legacy hypothesis-кода и проверка структуры архива. После размещения в окружении проекта используйте уже установленные зависимости:

```bash
npm run typecheck
npm run build
```
