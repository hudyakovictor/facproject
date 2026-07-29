# DEEPUTIN Forensic UI — React/Vite

Полноценный React 19 + TypeScript + Vite интерфейс на основе `final_ui_ideas/3`. Это исходный код приложения, а не статическая подмена.

## Запуск

```bash
# Backend (в отдельном терминале, из корня репозитория)
python3 -m venv .venv && source .venv/bin/activate
pip install -r app6/api/requirements.txt
uvicorn app6.api.server:app --reload --port 8000

# Frontend
cd ui
npm ci
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Открыть `http://localhost:5173`.

## Тесты

```bash
npm run test        # vitest: heatColor, i18n, api fallback, SettingsModal, PairCompareView
npm run typecheck
```

## Production build

```bash
npm run typecheck
npm run build
npm run preview
```

## Проверки перед релизом

```bash
python scripts/check_contract.py   # исходники: контракт React/Vite, поз, режимов, API
npm run check                      # typecheck + test + build
python scripts/smoke_ui.py         # dist/: реальная раздача статики + маркеры после минификации
```

`app6/scripts/project_readiness.py` требует наличия обоих скриптов и
`ui/dist/index.html`, иначе помечает `ui_ready: false`.

## Реализовано

- 9 нормативных pose bins: профиль, глубокий, средний и лёгкий ракурс слева; фронтальный; четыре симметричных справа;
- 11 рабочих режимов: хронология, матрица, кластеры, сравнение диапазонов, **сравнение пары фото A/B**, 3D/BFM Inspector, landmark drift, метрики, статистика, **калибровка**, **управление данными**;
- 14 дорожек geometry/skin в объединённой хронологии;
- фильтры, поиск, диапазоны A/B, сравнение, источники, эпохи, экспорт отчёта;
- полноэкранный 3D overlay на **настоящей BFM-геометрии** (35 709 вершин / 70 789 треугольников из `3ddfa_v3/assets/face_model.tar.gz`), не приближение;
- **сравнение пары фото** (`/api/v1/compare`, `/api/v1/compare/full_mesh`) с настраиваемой тепловой картой различий и **реальным морфингом A→B** (per-vertex lerp на подлинной топологии);
- **раздел калибровки**: здоровье реальной базы (943 записи, 7×9), подбор ближайших калибровочных кадров по углам позы;
- **раздел управления данными**: загрузка фото, пакетные задания (extract/recompute), очистка извлечённых данных, системное здоровье (CPU/RAM/GPU/веса модели);
- **попап настроек** с раздельными порогами тепловой карты (0–25/25–50/50–75/75–100%) и порогами анализа, персистентно на backend;
- полноценный ru/en с живым переключением языка;
- адаптивность: честное уведомление на экранах <1024px, `:focus-visible`, `prefers-reduced-motion`;
- API-first загрузка `/api/v1/timeline` с явно обозначенным deterministic demo fallback;
- Fix Capsule JSON `deeputin.fix-capsule.v2`;
- обязательный индикатор `DEMO/RESEARCH · НЕ ВЕРДИКТ`.

## API

Базовый URL задаётся через `VITE_API_BASE_URL` (см. `.env.example`); пусто = same-origin. Полный список эндпоинтов — `app6/api/README.md`.

`GET /api/v1/timeline` ожидает JSON-массив `Photo[]` либо объект `{ "photos": Photo[] }` / `{ "items": Photo[] }`. Поля и runtime-проверка описаны в `src/api.ts`, тип `Photo` — в `src/data.ts`.

Demo-данные предназначены только для разработки интерфейса и никогда не маскируются под результаты исследования — источник геометрии (`demo`/`research`) всегда виден в интерфейсе.
