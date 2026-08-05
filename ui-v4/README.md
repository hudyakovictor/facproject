# DEEPUTIN UI v4 — complete module

Один нормальный модуль без overlay/patch-папок и без версионного мусора в именах.

## Структура

- `src/app` — оболочка приложения;
- `src/features/timeline` — multi-pose forensic timeline;
- `src/features/data-manager` — очистка и запуск извлечения;
- `src/features/photo-lab` — фото, mesh, LDM106/134 и chronology;
- `src/features/settings` — пороги качества и landmark shift;
- `src/shared` — API-клиент и общие типы;
- `backend/app6` — полностью интегрированный backend;
- `backend/3ddfa_v3` — 3DDFA_V3;
- `docs` — документация с нормальными стабильными именами.

Все API-маршруты, sampling и настройки встроены непосредственно в `backend/app6`.

## Запуск

Frontend: `npm run dev` из корня `ui-v4`.

Backend: `uvicorn app6.api.server:app --host 127.0.0.1 --port 8000` из `ui-v4/backend`.
