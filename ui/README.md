# DEEPUTIN Forensic UI — React/Vite

Полноценный React 19 + TypeScript + Vite интерфейс на основе `final_ui_ideas/3`. Это исходный код приложения, а не статическая подмена.

## Запуск

```bash
cd ui
npm ci
npm run dev
```

Открыть `http://localhost:5173`.

## Production build

```bash
npm run typecheck
npm run build
npm run preview
```

## Реализовано

- 9 нормативных pose bins: профиль, глубокий, средний и лёгкий ракурс слева; фронтальный; четыре симметричных справа;
- 8 рабочих режимов: хронология, матрица, кластеры, сравнение, 3D/BFM Inspector, landmark drift, метрики, статистика;
- 14 дорожек geometry/skin в объединённой хронологии;
- фильтры, поиск, диапазоны A/B, сравнение, источники, эпохи, экспорт отчёта;
- полноэкранный 3D/landmark overlay и BFM-ready Inspector;
- API-first загрузка `/api/v1/timeline` с явно обозначенным deterministic demo fallback;
- Fix Capsule JSON `deeputin.fix-capsule.v2`;
- обязательный индикатор `API/DEMO · НЕ ВЕРДИКТ`.

## API

URL меняется через `VITE_TIMELINE_API_URL`. Ожидается JSON-массив `Photo[]` либо объект `{ "photos": Photo[] }` / `{ "items": Photo[] }`. Поля и runtime-проверка описаны в `src/api.ts`, тип `Photo` — в `src/data.ts`.

Demo-данные предназначены только для разработки интерфейса и никогда не маскируются под результаты исследования.
