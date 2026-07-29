# ТЗ доработок UI

**Стек**: React 19 + TS 5.9 + Vite 7. Сборка: 0 ошибок, 39 модулей, 317 KB.
**Данные**: 1809 синтетических фото (PRNG). Реальное API не подключено — fallback на демо.

---

## 1. Критические (без них UI бесполезен)

**1.1 API эндпоинты (11 шт.)**
`GET /api/v1/timeline`, `/photos/:id`, `/photos/:id/mesh`, `/photos/:id/landmarks/{106,134}`, `/calibration/pair`, `/compare/:a/:b`, `/compare/range`, `/landmarks/drift`, `/clusters`, `/events`, `/stats`

**1.2 Замена синтетики** — удалить `data.ts` (PRNG), все данные только с API.

**1.3 Inspector3D** — react-three-fiber + drei. BFM mesh (35709 вершин), тепловая карта, морфинг (слайдер 0–100%), OrbitControls.

---

## 2. Функциональные

**2.1 Калиброванное сравнение** — подбор пары из calibration_dataset по yaw/pitch/roll. `calibrated_diff = raw_diff - calib_diff`. Индикатор: зелёный (<5°), жёлтый (5-15°), красный (>15°).

**2.2 Drift ландмарок** — 4 режима: Drift Scatter, LOESS тренд, Pose Grid 3×3, Heatmap Grid. Фильтр по набору (106/134), ракурсу, годам.

**2.3 Матрица сходства** — эпохи vs метрики, тепловая карта.

**2.4 PublicationsPanel** — загрузка публикаций, связь с фото/эпохами.

**2.5 StatsDashboard** — распределение качества, confidence, аномалий. Гистограммы, круговые диаграммы.

---

## 3. Техдолг

**3.1 Рефакторинг App.tsx** — 740 строк, 20+ useState. Выделить Zustand (playhead, filters, panels, compare). HeaderBar — строгие пропсы (сейчас `any`).

**3.2 Error Boundaries** — обернуть каждый крупный компонент.

**3.3 Тесты** — vitest для utils, компонентов, api.

**3.4 Производительность** — useMemo для SVG-путей, виртуализация дорожек.

---

## 4. UI/UX

**4.1 Силуэт лица** — SVG с поворотом по yaw, 21 зона, цветовая индикация.

**4.2 Радар кожи** — 8 метрик (silicone, specular, lbp, frangi, wrinkle, subsurface, visualAge, calendarAge).

**4.3 Анимации** — Framer Motion, пульсирующие маркеры аномалий.

**4.4 Горячие клавиши** — Ctrl+Z/Ctrl+Shift+Z undo/redo, Ctrl+F поиск, 1-6 вкладки.

---

## 5. Инфраструктура

**5.1 CI/CD** — GitHub Actions (сборка, линтинг, тесты).

**5.2 Docker** — Dockerfile + nginx.

---

## Этапы

| # | Что делаем | Дней |
|---|-----------|------|
| 1 | API + синтетика → реальные данные + Error Boundaries | 1-2 |
| 2 | Inspector3D (three-fiber) + калиброванное сравнение | 2-3 |
| 3 | Drift, матрица, StatsDashboard | 1-2 |
| 4 | Zustand, типизация, тесты | 2-3 |
| 5 | Анимации, клавиши, силуэт | 1-2 |
| 6 | CI/CD, Docker | 1 |