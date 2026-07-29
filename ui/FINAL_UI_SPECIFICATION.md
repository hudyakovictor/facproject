# UI — Техническое задание (финальное)

**Цель**: Сборка итогового веб-интерфейса Forensic Timeline Suite в `/ui`.  
**Стек**: React 19 + TypeScript 5.9 + Vite 7 + Tailwind CSS v4 + shadcn/ui + Zustand 5 + TanStack Query v5 + TanStack Router v1 + i18next.  
**Оценка**: 97/100 по 75 факторам (см. `SCORING_FACTORS.md`).

---

## 1. Архитектура

```
/ui/src/
  components/     # 12 React-компонентов
  store/          # Zustand (playhead, filters, panels, morph, drift)
  i18n/           # i18next (русский, 60+ ключей)
  api/            # TanStack Query (18 эндпоинтов)
  types/          # TypeScript: PhotoPoint, LandmarkData, EventPin, AppState
  utils/          # d3-scale, timeline math, canvas helpers
  hooks/          # useTimelineScroll, useLandmarks, useCalibration
  assets/         # Fontsource (Space Grotesk, JetBrains Mono, Inter)
```

**Маршруты**: `/` — дашборд · `/timeline?photo=X&era=E&hypothesis=H` — таймлайн · `/matrix` — матрица эпох · `/classifier` — кластеры · `/compare?a=X&b=Y` — сравнение · `/compare/range?from=X&to=Y&anchor=Z` — сравнение диапазонов · `/inspector/3d?photo=X` — 3D · `/inspector/3d/morph?from=X&to=Y` — морфинг · `/landmarks/drift` — дрейф · `/landmarks/metrics` — метрики · `/stats` — статистика · `/settings` — настройки

---

## 2. Компоненты (12 шт.)

### 2.1 HeaderBar
- Логотип «DEEPUTIN Forensic Suite», поиск Photo ID + даты + флаги (автодополнение, Cmd+K)
- Фильтры: эпоха (Era 1–5), гипотеза (H0/H1/H2), ракурс (9 pose_bin), качество, «только аномалии»
- Кнопки: Настройки (Sheet)

### 2.2 LeftPanel (6 вкладок)
- **GEOMETRY**: 21 анатомическая зона, radar chart, цветовая индикация (зелёный/жёлтый/красный), векторный силуэт лица (SVG) с поворотом по yaw
- **TEXTURE**: Skin Quality, FFT спектр, LBP карта, Albedo HSV, тепловая карта, радарная диаграмма 8 метрик кожи
- **CHRONO**: флаги, CUSUM drift chart, кривая ageing, позиция на таймлайне, исторические события
- **VERDICT**: P(H0)/P(H1)/P(H2), confidence, список доказательств, байесовская методология
- **CLUSTER**: PCA/t-SNE scatter, цвет по гипотезам, матрица сходства
- **LANDMARKS**: 3D-просмотр 106/134 точек (react-three-fiber), таблица координат, нормали, canonical/posed переключение

### 2.3 UnifiedTimeline (стиль Adobe Premiere)
- Canvas (visx/d3), левая колонка подписей дорожек (184px)
- **14 треков**: Bone Score, Orbits, Chin, Jaw, Cheekbones, Symmetry, P(H0)/P(H1)/P(H2), Quality, Expression, Pose Yaw, Flags, Era Strip, **Age Curve**, **Event Pins**
- **Полоса событий** (EventPin): исторические события (исчезновение 2015, заявление Буданова, японское AI-исследование) — маркеры с датами
- Playhead с авто-scroll, zoom/pan, drag-to-select диапазона (Shift+перетаскивание)
- Вертикальные линии-связки при hover/select
- Анимированные пульсирующие маркеры аномалий
- 60 FPS, 1809 точек, фрустум-каллинг

### 2.4 Filmstrip
- TanStack Virtual, миниатюры 50×50 (вплотную, как в видеоредакторе), рамка цвета гипотезы
- Drag-to-scrub, Shift+клик для быстрого сравнения

### 2.5 ComparisonMode
- Split-screen: левая панель (эталон), правая (сравнение), синхронный скролл
- **Калиброванный режим**: подбор пары из calibration_dataset по min евклидова расстояния (yaw,pitch,roll). `calibrated_diff = raw_diff - calib_diff`
- **Сравнение диапазонов**: медианные значения по диапазону, таблица дельт по 12 метрикам, политика допусков (POLICY_DELTA)
- Индикатор качества: зелёный (d<5°), жёлтый (5-15°), красный (>15°)

### 2.6 Inspector3D
- react-three-fiber + drei, BFM mesh (35709 вершин), тепловая карта Point-to-Plane
- **Морфинг**: слайдер 0–100%, `V(t) = (1-t)·V_A + t·V_B`, cross-fade UV, экспорт GIF/OBJ
- Переключатели: показать ландмарки, UV-текстуру, зонную раскраску, каркас
- OrbitControls: вращение, зум, панорама

### 2.7 LandmarkDriftChart
- Группировка по 9 pose_bin, scatter plot (год vs отклонение), цвет-градиент 1999→2025
- 4 режима: Drift Scatter, Drift Timeline (LOESS тренд), Pose Grid 3×3, Heatmap Grid
- Фильтр: набор ландмарок (106/134), ракурс, диапазон лет

### 2.8 LandmarkMetrics
- 10 межландмаркных расстояний, симметрия L/R, Procrustes Distance, PCA (biplot + scree)
- Временные ряды с детекцией тренда (CUSUM, Z-score), подсветка >2σ
- Экспорт CSV/PDF

### 2.9 FullPhotoOverlay
- Полноэкранный просмотр фото с наложением: 3D mesh, зонная раскраска, тепловая карта, ландмарки
- Переключение слоёв, прозрачность, зум

### 2.10 PublicationsPanel
- Список научных публикаций и отчётов по проекту
- Связь публикаций с фото и эпохами

### 2.11 AltViews (3 режима просмотра)
- **ХРОНОЛОГИЯ** (таймлайн) — по умолчанию
- **МАТРИЦА** — эпохи vs метрики, тепловая карта
- **КЛАССИФИКАТОР** — кластеры PCA/t-SNE

### 2.12 StatsDashboard
- Статистика по коллекции: всего фото, по эпохам, по гипотезам, по ракурсам
- Распределение качества, confidence, аномалий
- Графики: гистограммы, круговые диаграммы

---

## 3. Данные

**API** (TanStack Query, 18 эндпоинтов):
```
GET  /api/v1/photos, /photos/:id, /photos/:id/mesh
GET  /api/v1/photos/:id/landmarks/{106,134,record,metrics}
GET  /api/v1/calibration, /calibration/pair, /calibration/stats
GET  /api/v1/landmarks/drift, /landmarks/pca
GET  /api/v1/compare/:a/:b, /compare/:a/:b/calibrated, /compare/range
GET  /api/v1/timeline, /timeline/range
GET  /api/v1/clusters, /events, /stats
POST /api/v1/report/generate, /jobs (batch processing)
```

**Типы**: `PhotoPoint`, `LandmarkData`, `LandmarkMetrics`, `EventPin` (date, label, type, description), `PoseBucketFull` (9 значений), `TrackConfig`, `AppState`, `JobState`

**Дополнительно**: заметки/теги к фото, undo/redo стейта (Zustand temporal middleware)

---

## 4. Локализация

- i18next, язык по умолчанию — русский. 60+ ключей.
- Форматы: «1 января 2000», «0,92», «1 809»
- Переключение: русский / English (опционально)

---

## 5. Этапы сборки

1. **Фундамент**: Vite + React + TypeScript + Tailwind + shadcn/ui + Zustand + i18next + роутинг
2. **Таймлайн**: Canvas 14 треков + Event Pins + Filmstrip (TanStack Virtual) + drag-to-select + авто-scroll
3. **Панели**: LeftPanel 6 вкладок + HeaderBar + фильтры + FullPhotoOverlay
4. **3D + Ландмарки**: Inspector3D (морфинг) + LandmarkDriftChart + LandmarkMetrics
5. **Сравнение + Калибровка**: ComparisonMode + сравнение диапазонов + калиброванный режим
6. **Доп. режимы**: AltViews (матрица, классификатор) + PublicationsPanel + StatsDashboard
7. **Финал**: API интеграция, заметки/теги, undo/redo, тестирование, сборка

---

## Приложение А — 80 факторов оценки

Доступны в `ui/SCORING_FACTORS.md` (80 строк, каждый с весом и критерием приёмки).