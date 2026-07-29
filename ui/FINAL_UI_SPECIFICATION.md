# UI — Техническое задание (финальное)

**Цель**: Сборка итогового веб-интерфейса Forensic Timeline Suite в `/ui`.  
**Оценка**: 97/100 по 80 факторам (см. Приложение А).  
**Стек**: React 19 + TypeScript 5.9 + Vite 7 + Tailwind CSS v4 + shadcn/ui.

---

## 1. Архитектура

```
/ui/
  src/
    components/     # 8 React-компонентов
    store/          # Zustand 5 store
    i18n/           # i18next (русский)
    api/            # TanStack Query v5
    types/          # TypeScript типы
    utils/          # d3-scale, helpers
    assets/         # шрифты, иконки
  public/           # статика
  package.json
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
```

**Маршруты** (TanStack Router):
`/` — дашборд · `/timeline?photo=X` — таймлайн · `/compare?a=X&b=Y` — сравнение · `/inspector/3d?photo=X` — 3D · `/inspector/3d/morph?from=X&to=Y` — морфинг · `/landmarks/drift` — дрейф · `/landmarks/metrics` — метрики · `/report` — PDF-отчёт

---

## 2. Компоненты (8 шт.)

### 2.1 HeaderBar
- Логотип «DEEPUTIN Forensic Suite», поиск Photo ID (автодополнение), Cmd+K
- Фильтры: эпоха (Era 1–5), гипотеза (H0/H1/H2), ракурс (9 pose_bin), «только аномалии»
- Кнопки: Экспорт PDF, Настройки (Sheet)

### 2.2 LeftPanel (6 вкладок)
- **GEOMETRY**: 21 анатомическая зона, radar chart, цветовая индикация
- **TEXTURE**: Skin Quality, FFT Regularity, LBP Complexity, Albedo HSV, тепловая карта
- **CHRONO**: флаги, CUSUM drift chart, позиция на таймлайне
- **VERDICT**: P(H0)/P(H1)/P(H2), confidence, список доказательств
- **CLUSTER**: PCA/t-SNE scatter, цвет по гипотезам
- **LANDMARKS**: 3D-просмотр 106/134 точек (react-three-fiber), таблица координат, нормали, canonical/posed переключение

### 2.3 UnifiedTimeline
- Canvas (visx/d3), 14 треков: Bone Score, Orbits, Chin, Jaw, Cheekbones, Symmetry, P(H0)/P(H1)/P(H2), Quality, Expression, Pose Yaw, Flags, Era Strip
- Playhead, zoom/pan, drag-selection, 60 FPS, 1809 точек

### 2.4 Filmstrip
- TanStack Virtual, миниатюры 80×80, рамка цвета гипотезы, drag-to-scrub

### 2.5 ComparisonMode
- Split-screen, калиброванный режим: подбор пары из calibration_dataset по min евклидова расстояния (yaw,pitch,roll). `calibrated_diff = raw_diff - calib_diff`. Индикатор качества: зелёный (d<5°), жёлтый (5-15°), красный (>15°)

### 2.6 Inspector3D
- react-three-fiber + drei, BFM mesh (35709 вершин), тепловая карта
- **Морфинг**: слайдер 0–100%, `V(t) = (1-t)·V_A + t·V_B`, cross-fade UV, экспорт GIF/OBJ
- Переключатели: показать ландмарки, UV-текстуру

### 2.7 LandmarkDriftChart
- Группировка по 9 pose_bin, scatter plot (год vs отклонение), цвет-градиент 1999→2025
- 4 режима: Drift Scatter, Drift Timeline (LOESS тренд), Pose Grid 3×3, Heatmap Grid
- Фильтр: набор ландмарок (106/134), ракурс, диапазон лет

### 2.8 LandmarkMetrics
- 10 межландмаркных расстояний (orbit width/height, nose, mouth, chin, zygomatic, jaw)
- Симметрия L/R, Procrustes Distance, PCA (biplot + scree plot)
- Временные ряды с детекцией тренда (CUSUM, Z-score), подсветка >2σ
- Экспорт CSV/PDF

---

## 3. Данные

**API** (TanStack Query):
```
GET  /api/v1/photos                    — PhotoPoint[]
GET  /api/v1/photos/:id/mesh           — record.npz
GET  /api/v1/photos/:id/landmarks/{106,134,record,metrics}
GET  /api/v1/calibration/pair?photo_a=X&photo_b=Y
GET  /api/v1/landmarks/drift?pose=frontal
GET  /api/v1/landmarks/pca
GET  /api/v1/compare/:a/:b/calibrated
```

**Типы** (TypeScript): `PhotoPoint`, `LandmarkData`, `LandmarkMetrics`, `PoseBucketFull` (9 значений), `TrackConfig`, `AppState` (Zustand)

---

## 4. Локализация

- i18next, язык по умолчанию — русский
- 60+ ключей: интерфейс, фильтры, метрики, гипотезы, 3D, ошибки
- Форматы: «1 января 2000», «0,92», «1 809»

---

## 5. Критерии 97/100

| Категория | Факторов | Требование |
|---|---|---|
| Функциональность | 20 | Все 8 компонентов, 6 вкладок, 14 треков, морфинг, дрейф, метрики |
| Производительность | 10 | Canvas 60 FPS, виртуализация 1809 фото, ленивая загрузка |
| UI/UX | 15 | Тёмная тема, русский язык, адаптивность, анимации (Framer Motion) |
| 3D | 10 | Mesh 35709 вершин, морфинг, тепловая карта, экспорт GIF/OBJ |
| Данные | 10 | Калиброванный режим, API интеграция, кэширование TanStack Query |
| Код | 10 | TypeScript strict, Zustand, TanStack Router, тесты компонентов |
| Безопасность | 5 | XSS-защита, CSP, валидация входных данных |

---

## 6. Этапы сборки

1. **Фундамент**: Vite + React + TypeScript + Tailwind + shadcn/ui + Zustand + i18next + роутинг
2. **Таймлайн**: Canvas 14 треков + Filmstrip (TanStack Virtual)
3. **Панели**: LeftPanel 6 вкладок + HeaderBar + фильтры
4. **3D + Ландмарки**: Inspector3D (морфинг) + LandmarkDriftChart + LandmarkMetrics
5. **Сравнение + Калибровка**: ComparisonMode + калиброванный режим
6. **Финал**: API интеграция, PDF экспорт, тестирование, сборка

---

## Приложение А — 80 факторов оценки

Доступны в `ui/SCORING_FACTORS.md` (80 строк, каждый с весом и критерием приёмки).