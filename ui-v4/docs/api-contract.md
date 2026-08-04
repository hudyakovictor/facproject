# Перенос API-контракта UI v2 → UI v4

API-клиент UI v4 сверен с `ui-v2/src/api.ts` и `app6`.

## Исправлено

- Каноническая переменная окружения: `VITE_API_BASE_URL`.
- Поддержан отдельный `VITE_TIMELINE_API_URL`.
- Timeline допускает массив либо `{photos}`/`{items}`, но объект обязан иметь `source_mode: research`.
- Строгая проверка `id`, `date`, `t`, `era`, `bucket` и девяти нормативных pose bins.
- Era проверяется против `era_meta`.
- Невалидные строки учитываются с причиной.
- `null` и нечисловые метрики превращаются в `NaN`, а интерфейс показывает `—`, не `0`.
- Ошибки FastAPI `detail/error/message` и validation arrays извлекаются без потери сообщения.
- `Content-Type` отправляется только при наличии request body.
- Все path-параметры кодируются через `encodeURIComponent`.
- Добавлены timeout и AbortSignal.
- Используется правильный маршрут `/api/v1/run/artifacts/{name}`.

## Маршруты, доступные клиенту v4

- `/api/v1/health`
- `/api/v1/timeline`
- `/api/v1/photos/{id}`
- `/api/v1/photos/{id}/image`
- `/api/v1/photos/{id}/info_keys`
- `/api/v1/photos/{id}/skin_zones`
- `/api/v1/pairs/{a}/{b}/metrics`
- `/api/v1/calibration/health`
- `/api/v1/system/health`
- `/api/v1/run/summary`
- `/api/v1/run/artifacts/{name}`
- `/api/v1/report/summary`
- `/api/v1/report/sections/{name}`

Никакие demo/mock fallbacks из старой документации UI v2 не переносились.
