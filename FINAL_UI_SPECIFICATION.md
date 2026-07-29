# Финальное техническое задание: Forensic Timeline Suite UI

## 1. Назначение системы

Интерактивный аналитический интерфейс для криминалистического исследования 1800+ фотографий лица человека на временной шкале (1999–2025). Система предназначена для детекции подмены личности (силиконовая маска/дипфейк) через анализ 3D-геометрии черепа, текстуры кожи и хронологической когерентности.

---

## 2. Технологический стек (production)

### 2.1. Базовый стек

| Компонент | Технология | Обоснование |
|-----------|-----------|-------------|
| Runtime | React 19 + TypeScript 5.9 | Строгая типизация forensic-данных |
| Build | Vite 7 | Мгновенный HMR, ESM, desktop-ориентирован |
| Routing | TanStack Router v1 | type-safe URL state, deep links `/timeline?photo=P00432` |
| State (UI) | Zustand 5 | Синхронизация playhead, filters, panels между компонентами |
| State (async) | TanStack Query v5 | Загрузка JSON по photo_id, кэширование |
| Стилизация | Tailwind CSS v4 + CSS variables | Тёмная forensic-тема через token-driven систему |
| UI-компоненты | shadcn/ui (Radix Primitives) | Dialog, Popover, Tooltip, Command Palette, Sheet, Tabs |
| Иконки | Lucide React | Inline SVG, соответствует стилю |
| Шрифты | Fontsource (Space Grotesk, JetBrains Mono, Inter) | Локальная загрузка без CDN |

### 2.2. Визуализация

| Задача | Библиотека | Альтернатива |
|--------|-----------|-------------|
| Треки-графики (Canvas/SVG) | @visx/visx (Airbnb) | Низкоуровневые d3-обёртки для кастомных треков |
| Дашборд-панели | Tremor v3 | LineChart, AreaChart, ScatterChart, KPI cards |
| 3D mesh оверлей | react-three-fiber + drei | Загрузка 3DDFA-V3 mesh, 106/134 ландмарок, WebGL2 |
| Морфинг 3D | react-three-fiber + drei | Интерполяция вершин между двумя mesh, слайдер перехода |
| Локализация | i18next + react-i18next | Русский язык интерфейса, JSON-ресурсы переводов |
| Виртуализация filmstrip | @tanstack/react-virtual v3 | 1809+ фото без проседаний |
| Drag & Drop | dnd-kit | Drag-selection, reorder lanes |
| Анимация | Framer Motion | Плавные переходы, аномалии |
| PDF экспорт | jsPDF + html2canvas | Экспорт отчётов |

---

## 3. Архитектура интерфейса

```
┌──────────────────────────────────────────────────────────────────┐
│  Header Bar (фиксированный)                                      │
│  [Лого] [Photo ID: P00432] [Cmd+K поиск] [Глобальные фильтры]   │
│  [Экспорт PDF] [Настройки]                                       │
├──────────────────────────────────────────────────────────────────┤
│ ┌──────────────┐ ┌────────────────────────────────────────────┐ │
│ │  Left Panel  │ │         Unified Timeline (Canvas)           │ │
│ │  (5 вкладок) │ │  ┌────────────────────────────────────────┐ │ │
│ │              │ │  │ Track 1: Bone Score (line chart)       │ │ │
│ │  • GEOMETRY  │ │  │ Track 2: Orbits Depth (line + area)    │ │ │
│ │  • TEXTURE   │ │  │ Track 3: Chin Projection               │ │ │
│ │  • CHRONO    │ │  │ Track 4: Jaw Width                     │ │ │
│ │  • VERDICT   │ │  │ Track 5: Cheekbones                    │ │ │
│ │  • CLUSTER   │ │  │ Track 6: Symmetry Score                │ │ │
│ │              │ │  │ Track 7: P(H0) Hypothesis              │ │ │
│ │              │ │  │ Track 8: P(H1) Silicone Mask           │ │ │
│ │              │ │  │ Track 9: P(H2) Different Person        │ │ │
│ │              │ │  │ Track 10: Quality Score                │ │ │
│ │              │ │  │ Track 11: Expression Magnitude          │ │ │
│ │              │ │  │ Track 12: Pose Yaw                     │ │ │
│ │              │ │  │ Track 13: Flags/Anomalies (discrete)   │ │ │
│ │              │ │  │ Track 14: Era Strip (colored bands)    │ │ │
│ │              │ │  └────────────────────────────────────────┘ │ │
│ │              │ │  ┌────────────────────────────────────────┐ │ │
│ │              │ │  │ Filmstrip (горизонтальный скролл)      │ │ │
│ │              │ │  │ [img][img][img]...[▶ playhead]...[img] │ │ │
│ │              │ │  └────────────────────────────────────────┘ │ │
│ └──────────────┘ └────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│  Footer: Status bar, прогресс-бар, версия схемы                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Компоненты и их реализация

### 4.1. HeaderBar (`HeaderBar.tsx`)

**Назначение**: Верхняя навигационная панель.

**Элементы**:
- Логотип / название системы "DEEPUTIN Forensic Suite"
- Поле ввода `Photo ID` с автодополнением (поиск по всем photo_id)
- Command Palette (`Cmd+K`) — быстрый поиск по photo_id, датам, флагам
- Глобальные фильтры:
  - Фильтр по эпохе (Era 1–5)
  - Фильтр по гипотезе (H0/H1/H2)
  - Фильтр "Только аномалии" (скрывает нормальные кадры)
  - Фильтр по pose bucket
- Кнопка "Экспорт PDF" — экспорт текущего вида в PDF-отчёт
- Кнопка "Настройки" — Sheet с настройками отображения треков

**Состояния**: загрузка поиска, пустой результат, активные фильтры (отображаются как badges)

---

### 4.2. LeftPanel (`LeftPanel.tsx`)

**Назначение**: Левая боковая панель с 5 вкладками детальной информации по выбранному кадру.

**Вкладки**:

#### 4.2.1. GEOMETRY Tab
- Таблица 21 анатомической зоны черепа с значениями:
  - Orbit Depth (L/R)
  - Chin Projection
  - Gonial Angle
  - Jaw Width
  - Bigonial Width
  - Mandibular Body Length
  - Ramus Height
  - Zygomatic Arch (L/R)
  - Symmetry Score
- Цветовая индикация: зелёный (норма) / жёлтый (предупреждение) / красный (аномалия)
- Spidergon/Radar chart для визуального сравнения зон

#### 4.2.2. TEXTURE Tab
- Skin Quality Score (0–1)
- FFT Regularity Peak (детекция силикона)
- LBP Complexity (микроструктура кожи)
- Albedo HSV Spectrum
- Texture Score временной ряд
- Миниатюра face_mask.png с наложением тепловой карты

#### 4.2.3. CHRONO Tab
- Хронологическая ветка выбранного кадра
- Список флагов: `quality_limited`, `expression_qc_uncalibrated`, `angle_noise_uncompensated`, `irreversible_return_anomaly`, `SAME_DAY_IDENTITY_CONFLICT`
- CUSUM drift chart — cumulative sum отклонений
- Timeline позиция относительно эпох

#### 4.2.4. VERDICT Tab
- Итоговый вердикт по кадру:
  - `H0` (один человек) — зелёный
  - `H1` (силиконовая маска/дипфейк) — оранжевый
  - `H2` (разные люди) — красный
- Апостериорные вероятности P(H0), P(H1), P(H2)
- Уровень доверия (confidence score)
- Список доказательств: геометрия, текстура, хронология
- Кнопка "3D Inspector" — открывает 3D-сравнение

#### 4.2.5. CLUSTER Tab
- PCA/t-SNE проекция всех кадров
- Цветовая кодировка по гипотезам
- Возможность выделить кластер и увидеть список photo_id
- Scatter plot с осями Bone Score vs Texture Score

#### 4.2.6. LANDMARKS Tab

**Назначение**: Вкладка анализа ключевых точек (landmarks) выбранного кадра.

**Элементы**:
- **3D-просмотр ландмарок**: Визуализация 106/134 точек в 3D-пространстве (react-three-fiber)
  - Точки отображаются как сферические маркеры с нумерацией
  - Цветовая кодировка: передние (зелёные) vs самозакрытые/невидимые (серые) на основе `ldm*_visible_original`
  - Возможность вращения и зума (OrbitControls)
  - Отображение нормалей (`ldm*_object_normals`) как векторов
- **Таблица координат**: Список всех ландмарок с координатами (x, y, z) и статусом видимости
- **Канонические координаты**: Переключение между posed и canonical (`ldm*_canonical`) пространством
- **Сравнение с эталоном**: Наложение ландмарок текущего кадра на эталонный (средний по эпохе)
- **Экспорт**: Кнопка "Экспорт CSV" — выгрузка координат всех ландмарок

**Визуальные состояния**:
- Загрузка: скелетон с пустым 3D-вьюпортом
- Пусто: сообщение "Нет данных ландмарок для этого кадра"
- Ошибка: "Ошибка загрузки данных ландмарок" с кнопкой повтора

---

### 4.3. UnifiedTimeline (`TimelineTracks.tsx`)

**Назначение**: Основной компонент — 14 дорожек на Canvas с синхронизированным скроллом и зумом.

**Техническая реализация**:
- HTML5 Canvas API (raw) + Frustum Culling
- Отрисовываются только видимые点在 текущем viewport
- d3-scale для шкал времени, d3-array для интерполяции
- 60 FPS при скролле и перемещении playhead

**Дорожки (tracks)**:

| # | Название | Тип | Цвет |
|---|----------|-----|------|
| 1 | Bone Score | Line chart | #4f98a3 (бирюзовый) |
| 2 | Orbits Depth | Line + Area | #4f98a3 |
| 3 | Chin Projection | Line | #4f98a3 |
| 4 | Jaw Width | Line | #4f98a3 |
| 5 | Cheekbones | Line | #4f98a3 |
| 6 | Symmetry Score | Line | #4f98a3 |
| 7 | P(H0) — Same Person | Filled area | #22c55e (зелёный) |
| 8 | P(H1) — Silicone Mask | Filled area | #fdab43 (оранжевый) |
| 9 | P(H2) — Different Person | Filled area | #ff3b30 (красный) |
| 10 | Quality Score | Bar chart | #a78bfa (фиолетовый) |
| 11 | Expression Magnitude | Line | #f472b6 (розовый) |
| 12 | Pose Yaw | Scatter dots | #94a3b8 (серый) |
| 13 | Flags/Anomalies | Discrete markers | #ff3b30 |
| 14 | Era Strip | Colored bands | Era 1–5 |

**Взаимодействие**:
- Playhead (вертикальная линия) — синхронизирован со всеми панелями
- Zoom (колесо мыши) — масштабирование временной шкалы
- Pan (drag) — горизонтальная прокрутка
- Клик по точке — выбор кадра, обновление Left Panel
- Drag selection — выделение диапазона дат
- Контекстное меню на точке — "Open 3D Compare", "Show Details"

---

### 4.4. Filmstrip (`Filmstrip.tsx`)

**Назначение**: Горизонтальная лента миниатюр кадров.

**Техническая реализация**:
- `@tanstack/react-virtual` для виртуализации
- Ленивая загрузка превью (lazy loading)
- Хранение векторных миниатюр в кэше
- Полноразмерные текстуры подгружаются асинхронно при выборе

**Элементы**:
- Миниатюры 80×80 px с рамкой цвета гипотезы
- Playhead (подсветка выбранного кадра)
- Drag-to-scrub — перемещение playhead drag'ом
- Аномалии отмечены красной рамкой
- Фильтр "Только аномалии" стягивает ленту только к аномальным кадрам

---

### 4.5. ComparisonMode (`ComparisonMode.tsx`)

**Назначение**: Split-screen сравнение двух эпох с автоматическим подбором калибровочных пар.

**Реализация**:
- Левая панель: эталонный кадр (фиксирован)
- Правая панель: синхронно перемещается по таймлайну
- Отображение: 3D mesh, face_mask, UV-текстура
- Diff-метрики: Bone Score delta, Texture Score delta
- Тепловая карта расхождений на 3D-сетке (зелёный → красный)

#### 4.5.1. Калиброванный режим сравнения (Calibrated Comparison)

**Назначение**: Минимизация шума при сравнении двух фото за счёт подбора калибровочных пар с наиболее близкими углами наклона головы.

**Источник данных**:
- `calibration_dataset/all_calibration_index.csv` — индекс 943 фото 7 персон с углами yaw/pitch/roll
- `calibration_dataset/photos/` — директория с исходными фото
- `calibration_dataset/person_*/frame_*/record.npz` — 3D-реконструкции

**Алгоритм подбора калибровочной пары**:
1. При выборе двух фото для сравнения (Photo A и Photo B) система извлекает их углы поворота головы (yaw, pitch, roll) из `metadata.json`
2. В калибровочном наборе ищется фото с минимальным евклидовым расстоянием по углам:
   `d = sqrt((yaw_A - yaw_calib)² + (pitch_A - pitch_calib)² + (roll_A - roll_calib)²)`
3. Аналогично подбирается калибровочная пара для Photo B
4. Итоговое сравнение: `diff = (Photo A - Photo B) - (Calib_A - Calib_B)` — вычитание калибровочного шума

**Визуализация в интерфейсе**:
- Индикатор "Калибровка" с отображением подобранной калибровочной пары
- Отображение углов (yaw/pitch/roll) для обоих фото и калибровочной пары
- Кнопка "Показать калибровочную пару" — открывает фото из калибровочного набора
- Метрика "Шум калибровки" — остаточное угловое расхождение после подбора

**Элементы управления**:
- Переключатель "Калиброванный режим" (вкл/выкл)
- Селектор персоны для калибровки: "Авто" (по умолчанию) / конкретный person_ID
- Индикатор качества калибровки: зелёный (d < 5°) / жёлтый (5-15°) / красный (> 15°)

**Визуальные состояния**:
- Загрузка: "Подбор калибровочной пары..."
- Успех: "Калибровочная пара найдена: person_X/frame_XXXXXX (d = X.X°)"
- Предупреждение: "Калибровочная пара с большим расхождением (d > 15°)"
- Ошибка: "Калибровочная пара не найдена. Сравнение без калибровки"

---

### 4.6. HypothesisLegend (`HypothesisLegend.tsx`)

**Назначение**: Легенда гипотез и цветовая кодировка.

**Элементы**:
- H0 (Same Person) — зелёный `#22c55e`
- H1 (Silicone Mask / Deepfake) — оранжевый `#fdab43`
- H2 (Different Person) — красный `#ff3b30`
- Quality Limited — серый `#64748b`
- Fuzzy labels с описанием

---

### 4.7. EraVerdictStrip (`EraVerdictStrip.tsx`)

**Назначение**: Полоса эпох с итоговым вердиктом по каждой.

**Элементы**:
- Era 1 (1999–2004) — цвет эпохи
- Era 2 (2005–2009)
- Era 3 (2010–2014)
- Era 4 (2015–2019)
- Era 5 (2020–2025)
- Для каждой эпохи: доминирующая гипотеза, confidence, количество кадров
- Клик по эпохе — зум на неё в таймлайне

---

### 4.8. 3D Inspector (`Inspector3D.tsx`)

**Назначение**: 3D-просмотрщик mesh лица с тепловой картой и режимом морфинга между двумя кадрами.

**Техническая реализация**:
- `react-three-fiber` + `@react-three/drei`
- Загрузка BFM-сетки (35709 вершин) из `record.npz`
- 106/134 ландмарок как сферические маркеры
- Тепловая карта Point-to-Plane расстояний (зелёный → красный)
- OrbitControls — вращение, зум, панорамирование

#### 4.8.1. Режим морфинга (Morphing Mode)

**Назначение**: Интерактивный плавный переход между 3D-сетками двух анализируемых фото с использованием OBJ-модели и UV-текстуры.

**Источник данных**:
- 3DDFA-V3 реконструкция: `alpha_id` (80), `alpha_exp` (64) из `record.npz`
- BFM-сетка: 35709 вершин, OBJ-формат (`atlas/bfm_model.obj`)
- UV-текстура: атлас текстур лица (`atlas/uv_face_mask.png`)
- Канонические ландмарки: `ldm*_canonical` из `record.npz`

**Реализация**:
1. **Загрузка двух mesh**: Photo A (эталон) и Photo B (сравниваемый)
2. **Интерполяция вершин**: Линейная интерполяция между соответствующими вершинами двух mesh
   - `V(t) = (1-t) * V_A + t * V_B`, где `t ∈ [0, 1]`
3. **Интерактивный слайдер**: Ползунок Morph Transition (0% = Photo A, 100% = Photo B)
   - Автоматическое воспроизведение (кнопка ▶) — плавный переход за 3 секунды
   - Ручной режим — перетаскивание слайдера
4. **UV-текстура**: Интерполяция текстур между двумя кадрами (cross-fade)
5. **Наложение ландмарок**: Отображение 106 ключевых точек на морфируемой сетке

**Элементы управления**:
- Слайдер морфинга (0–100%) с отображением текущего процента
- Кнопка "▶ Воспроизвести" / "⏸ Пауза"
- Кнопка "⟲ Сброс" (возврат к Photo A)
- Переключатель "Показать ландмарки" (вкл/выкл)
- Переключатель "Показать UV-текстуру" (вкл/выкл)
- Селектор ракурса: "Фронтальный", "Профиль L", "Профиль R", "Свободный"

**Экспорт**:
- Кнопка "Экспорт GIF" — генерация animated GIF морфинга (3 секунды, 15 FPS)
- Кнопка "Экспорт OBJ" — выгрузка текущего состояния mesh в OBJ-формат
- Параметры экспорта: разрешение, качество, количество кадров

**Визуальные состояния**:
- Загрузка: прогресс-бар "Загрузка mesh Photo A..." / "Загрузка mesh Photo B..."
- Ошибка: "Не удалось загрузить mesh для одного из кадров"
- Пусто: "Выберите два кадра для сравнения"

---

### 4.9. LandmarkDriftChart (`LandmarkDriftChart.tsx`)

**Назначение**: Визуализация дрейфа положения ключевых точек во времени с группировкой по ракурсам (pose_bin).

**Источник данных**:
- `ldm106_aligned.csv` / `ldm134_aligned.csv` — 3D-координаты ландмарок, выровненные в каноническое пространство
- `metadata.json` — `pose_bin`, одно из девяти нормативных значений: `left_profile`, `left_deep`, `left_mid`, `left_light`, `frontal`, `right_light`, `right_mid`, `right_deep`, `right_profile`
- `all_calibration_index.csv` — хронология всех кадров

**Реализация**:
1. **Группировка по pose_bin**: Все кадры разбиваются на 9 групп по ракурсу
2. **Для каждой группы**:
   - Вычисление среднего положения каждой ландмарки (эталонная форма для данного ракурса)
   - RMS-отклонение каждой ландмарки от среднего
   - Визуализация дрейфа: scatter plot, где ось X — год, ось Y — отклонение (мм)
3. **Цветовая кодировка**: Годы отображаются градиентом (1999 → 2025)
4. **Выбор ландмарки**: Возможность выбрать конкретную ландмарку (по ID) для детального просмотра

**Типы визуализации**:
- **Drift Scatter**: Точки всех кадров, цвет = год, форма = pose_bin
- **Drift Timeline**: Временной ряд отклонений для выбранной ландмарки с линией тренда (LOESS)
- **Pose Grid**: Матрица 3×3 (по ракурсам), в каждой ячейке — проекция ландмарок со смещением от эталона
- **Heatmap Grid**: Тепловая карта RMS-отклонений: строки = ландмарки, столбцы = годы

**Элементы управления**:
- Селектор набора ландмарок: "106 ключевых" / "134 полных"
- Селектор ракурса: "Все" / конкретный pose_bin
- Ползунок диапазона лет (1999–2025)
- Переключатель "Показать тренд" (линия LOESS)
- Кнопка "Сбросить выделение"

**Визуальные состояния**:
- Загрузка: скелетон графика
- Пусто: "Нет данных для выбранного ракурса"
- Ошибка: "Ошибка загрузки данных ландмарок"

---

### 4.10. LandmarkMetrics (`LandmarkMetrics.tsx`)

**Назначение**: Расчёт и визуализация аналитических метрик на основе ключевых точек для детекции аномалий геометрии лица.

**Источник данных**:
- `ldm106_aligned.csv` / `ldm134_aligned.csv` — 3D-координаты
- `ldm*_canonical` из `record.npz` — канонические координаты
- `ldm*_visible_original` — маски видимости

**Реализация метрик**:

#### 4.10.1. Межландмаркные расстояния (Inter-landmark Distances)
- **Ширина глазниц** (Orbit Width): расстояние между внешним и внутренним углом глаза (L/R)
- **Высота глазниц** (Orbit Height): вертикальный размер глазницы (L/R)
- **Ширина носа** (Nose Width): расстояние между крыльями носа
- **Высота носа** (Nose Height): от переносицы до кончика носа
- **Ширина рта** (Mouth Width): расстояние между углами рта
- **Высота подбородка** (Chin Height): от нижней губы до кончика подбородка
- **Скуловая ширина** (Zygomatic Width): расстояние между скуловыми дугами
- **Нижнечелюстная ширина** (Jaw Width): расстояние между углами нижней челюсти

#### 4.10.2. Коэффициенты симметрии (Symmetry Ratios)
- Для каждой парной структуры (глаза, скулы, челюсть):
  - `Symmetry Ratio = min(L, R) / max(L, R)` — значение от 0 (асимметрия) до 1 (идеал)
- **Общий индекс симметрии**: среднее всех Symmetry Ratio
- Визуализация: radar chart с 8 осями (каждая метрика)

#### 4.10.3. Procrustes-анализ
- **Procrustes Distance**: Расстояние между формой текущего кадра и эталонной формой (средней по эпохе)
- **Full Procrustes Fit**: Выравнивание (трансляция, вращение, масштаб) перед вычислением расстояния
- **Визуализация**: Наложение двух форм (текущая + эталон) после Procrustes-выравнивания

#### 4.10.4. PCA на ландмарках
- **PCA-проекция**: Все кадры проецируются на первые 2-3 главные компоненты
- **Цветовая кодировка**: по гипотезам (H0/H1/H2) или по эпохам
- **Biplot**: Отображение вклада каждой ландмарки в PC1/PC2
- **Scree plot**: График собственных значений для определения числа значимых компонент

#### 4.10.5. Временные ряды метрик
- Для каждой метрики строится временной ряд (год → значение метрики)
- **Детекция тренда**: Линейная регрессия, CUSUM, Z-оценка
- **Аномалии**: Подсветка точек, отклоняющихся более чем на 2σ от тренда
- **Сводная таблица**: Все метрики в одной таблице с цветовой индикацией (зелёный/жёлтый/красный)

**Элементы управления**:
- Вкладки: "Расстояния" / "Симметрия" / "Procrustes" / "PCA" / "Временные ряды"
- Селектор набора ландмарок: 106 / 134
- Ползунок диапазона лет
- Кнопка "Экспорт CSV" — выгрузка всех метрик
- Кнопка "Экспорт PDF" — отчёт по метрикам

**Визуальные состояния**:
- Загрузка: скелетон для каждого графика
- Пусто: "Нет данных для расчёта метрик"
- Ошибка: "Ошибка расчёта метрик" с детализацией

---

## 5. Типы данных (TypeScript)

```typescript
// core/types.ts

export type Era = "ERA_1" | "ERA_2" | "ERA_3" | "ERA_4" | "ERA_5";

// ИСПРАВЛЕНО 2026-07-29. Единственный нормативный словарь ракурсов — девять
// бинов из app6/atlas/pose_policy_v3_9bins.csv, они же в calibration_dataset
// (943 записи) и в pose_policy бэкенда. Прежний PoseBucket из пяти значений
// ("frontal_0", "frontal_yaw15", "profile_L", ...) в данных НЕ существует:
// такие имена не вернёт ни один эндпоинт. Использовать только PoseBucket ниже.
export type PoseBucket =
  | "left_profile" | "left_deep" | "left_mid" | "left_light"
  | "frontal"
  | "right_light" | "right_mid" | "right_deep" | "right_profile";

/** @deprecated Историческое имя; оставлено как алиас на время миграции. */
export type PoseBucketFull = PoseBucket;

/** Центры бинов по yaw. Отрицательный yaw — левый профиль (конвенция v3). */
export const POSE_BUCKET_YAW: Record<PoseBucket, number> = {
  left_profile: -60, left_deep: -40, left_mid: -25, left_light: -10,
  frontal: 0,
  right_light: 10, right_mid: 25, right_deep: 40, right_profile: 60,
};
export type Hypothesis = "H0" | "H1" | "H2";

export type FuzzyLabel =
  | "STRONGLY_MATCHING"
  | "CONSISTENT"
  | "INSUFFICIENT_DATA"
  | "WEAK_EVIDENCE"
  | "SUSPICIOUS_TEXTURE"
  | "GEOMETRIC_MISMATCH"
  | "IDENTITY_ANOMALY"
  | "TEMPORAL_IMPOSSIBILITY";

export interface PhotoPoint {
  id: string;           // photo_id
  date: string;         // YYYY-MM-DD
  year: number;
  timestamp: number;    // unix ms
  era: Era;
  pose: PoseBucket;
  quality: number;      // 0–1
  fuzzyLabel: FuzzyLabel;
  dominant: Hypothesis;
  p0: number;           // P(H0)
  p1: number;           // P(H1)
  p2: number;           // P(H2)
  confidence: number;
  flags: string[];

  geometry: {
    boneScore: number;
    orbits: number;
    chin: number;
    jaw: number;
    cheekbones: number;
    symmetry: number;
    poseYaw: number;
  };

  texture: {
    qualityScore: number;
    fftRegularity: number;
    lbpComplexity: number;
    albedoHsvStd: number;
  };

  chronology: {
    cusumDrift: number;
    irreversibleReturn: boolean;
    sameDayConflict: boolean;
  };

  // Данные ландмарок (загружаются асинхронно)
  landmarks?: LandmarkData;
}

// Координаты ландмарки
export interface LandmarkPoint {
  id: number;
  x: number;
  y: number;
  z: number;
  visible: boolean;
  frontFacing: boolean;
}

// Данные ландмарок для кадра
export interface LandmarkData {
  // 106 ключевых точек
  ldm106: {
    object: LandmarkPoint[];       // объектное пространство
    posed: LandmarkPoint[];        // с учётом позы
    canonical: LandmarkPoint[];    // канонические
    image224: { id: number; x: number; y: number }[];  // в пикселях
    vertexIndices: number[];       // индексы вершин BFM
    normals: { x: number; y: number; z: number }[];
  };
  // 134 ключевых точки (расширенный набор)
  ldm134: {
    object: LandmarkPoint[];
    posed: LandmarkPoint[];
    canonical: LandmarkPoint[];
    image224: { id: number; x: number; y: number }[];
    vertexIndices: number[];
    normals: { x: number; y: number; z: number }[];
  };
  // Параметры 3DMM
  alpha: {
    full: number[];   // 257
    id: number[];     // 80
    exp: number[];    // 64
    alb: number[];    // 80
    sh: number[];     // 27
  };
  // Поза
  pose: {
    yaw: number;
    pitch: number;
    roll: number;
    rotationMatrix: number[][];  // 3×3
    translation: number[];       // 3
    canonicalYaw: number;
  };
}

// Метрики, вычисленные на основе ландмарок
export interface LandmarkMetrics {
  // Межландмаркные расстояния
  distances: {
    orbitWidthL: number;
    orbitWidthR: number;
    orbitHeightL: number;
    orbitHeightR: number;
    noseWidth: number;
    noseHeight: number;
    mouthWidth: number;
    chinHeight: number;
    zygomaticWidth: number;
    jawWidth: number;
  };
  // Коэффициенты симметрии
  symmetry: {
    orbits: number;       // min(L,R)/max(L,R)
    zygomatic: number;
    jaw: number;
    overall: number;      // среднее всех
  };
  // Procrustes
  procrustes: {
    distance: number;     // Procrustes Distance до эталона
    scale: number;
    rotation: number[][];
  };
  // PCA
  pca: {
    pc1: number;
    pc2: number;
    pc3?: number;
    explainedVariance: number[];
  };
}

export interface TrackConfig {
  id: string;
  label: string;
  type: "line" | "area" | "bar" | "scatter" | "discrete" | "band";
  color: string;
  visible: boolean;
  yAxis: { min: number; max: number };
}

export interface AppState {
  // Selection
  selectedPhotoId: string | null;
  playheadIndex: number;
  
  // View
  zoomLevel: number;
  scrollOffset: number;
  visibleRange: [number, number];
  
  // Filters
  activeFilters: {
    eras: Era[];
    hypotheses: Hypothesis[];
    anomaliesOnly: boolean;
    poseBuckets: PoseBucket[];
  };
  
  // Panels
  leftPanelTab: "geometry" | "texture" | "chrono" | "verdict" | "cluster" | "landmarks";
  comparisonMode: boolean;
  comparisonAnchorId: string | null;
  
  // Data
  photos: PhotoPoint[];
  tracks: TrackConfig[];
}
```

---

## 6. Состояния UI (Zustand store)

```typescript
// store/useAppStore.ts
import { create } from "zustand";

interface AppStore {
  // Данные
  photos: PhotoPoint[];
  tracks: TrackConfig[];
  
  // Выбор
  selectedPhotoId: string | null;
  playheadIndex: number;
  
  // View
  zoomLevel: number;
  scrollOffset: number;
  
  // Фильтры
  anomaliesOnly: boolean;
  activeEras: Era[];
  activeHypotheses: Hypothesis[];
  
  // Панели
  leftPanelTab: string;
  comparisonMode: boolean;
  comparisonAnchorId: string | null;
  
  // Ландмарки
  landmarkData: Record<string, LandmarkData>;  // photo_id → данные
  landmarkMetrics: Record<string, LandmarkMetrics>;
  selectedLandmarkId: number | null;
  landmarkSet: "ldm106" | "ldm134";
  landmarkViewMode: "posed" | "canonical" | "image";
  
  // Морфинг
  morphTargetId: string | null;
  morphProgress: number;  // 0–1
  morphPlaying: boolean;
  morphShowLandmarks: boolean;
  morphShowTexture: boolean;
  
  // Дрейф ландмарок
  driftPoseFilter: PoseBucketFull | "all";
  driftYearRange: [number, number];
  driftShowTrend: boolean;
  
  // Actions
  setPhotos: (photos: PhotoPoint[]) => void;
  selectPhoto: (id: string) => void;
  setPlayhead: (index: number) => void;
  setZoom: (level: number) => void;
  toggleAnomaliesOnly: () => void;
  setFilter: (filter: Partial<AppStore>) => void;
  toggleComparison: (anchorId?: string) => void;
  
  // Landmark actions
  setLandmarkData: (photoId: string, data: LandmarkData) => void;
  setLandmarkMetrics: (photoId: string, metrics: LandmarkMetrics) => void;
  selectLandmark: (id: number | null) => void;
  setLandmarkSet: (set: "ldm106" | "ldm134") => void;
  setLandmarkViewMode: (mode: "posed" | "canonical" | "image") => void;
  
  // Morph actions
  setMorphTarget: (photoId: string | null) => void;
  setMorphProgress: (progress: number) => void;
  setMorphPlaying: (playing: boolean) => void;
  toggleMorphLandmarks: () => void;
  toggleMorphTexture: () => void;
  
  // Drift actions
  setDriftPoseFilter: (pose: PoseBucketFull | "all") => void;
  setDriftYearRange: (range: [number, number]) => void;
  toggleDriftTrend: () => void;
}
```

---

## 12. Пример данных (reference dataset)

### 12.1. Эталонное фото

Для разработки и тестирования интерфейса используется эталонное фото из калибровочного набора:

**Путь**: `calibration_dataset/person_01/frame_000205/`

**Файлы**:

| Файл | Формат | Размерность | Описание |
|------|--------|-------------|----------|
| `ldm106_aligned.csv` | CSV (107 строк) | 106 × 3 (x, y, z) | 106 ключевых точек, выровненных в каноническое пространство BFM |
| `ldm134_aligned.csv` | CSV (135 строк) | 134 × 3 (x, y, z) | 134 ключевых точки (расширенный набор), выровненных |
| `ldm106_raw.csv` | CSV (107 строк) | 106 × 3 (x, y, z) | 106 ключевых точек в исходном пространстве изображения (224×224) |
| `ldm134_raw.csv` | CSV (135 строк) | 134 × 3 (x, y, z) | 134 ключевых точки в исходном пространстве изображения |
| `metadata.json` | JSON | — | Метаданные: pose_bin, yaw/pitch/roll, source_filename, frame_index |
| `record.npz` | NPZ (34 массива) | — | Полная 3DDFA-V3 реконструкция (см. 12.2) |

### 12.2. Содержимое record.npz

| Массив | Размерность | Описание |
|--------|-------------|----------|
| `ldm106_object` | (106, 3) | 106 ландмарок в объектном пространстве (float32) |
| `ldm134_object` | (134, 3) | 134 ландмарок в объектном пространстве |
| `ldm106_object_norm` | (106, 3) | 106 ландмарок нормализованных |
| `ldm134_object_norm` | (134, 3) | 134 ландмарок нормализованных |
| `ldm106_posed` | (106, 3) | 106 ландмарок с учётом позы (rotation + translation) |
| `ldm134_posed` | (134, 3) | 134 ландмарок с учётом позы |
| `ldm106_camera` | (106, 3) | 106 ландмарок в камера-пространстве |
| `ldm134_camera` | (134, 3) | 134 ландмарок в камера-пространстве |
| `ldm106_image224` | (106, 2) | 106 ландмарок в пикселях изображения 224×224 |
| `ldm134_image224` | (134, 2) | 134 ландмарок в пикселях изображения |
| `alpha_full` | (257,) | Полный вектор альфа-параметров 3DMM |
| `alpha_id` | (80,) | Альфа-параметры идентичности (80 компонент) |
| `alpha_alb` | (80,) | Альфа-параметры альбедо (80 компонент) |
| `alpha_sh` | (27,) | Коэффициенты сферических гармоник (27 компонент) |
| `alpha_exp` | (64,) | Альфа-параметры экспрессии (64 компоненты) |
| `angle_rad` | (3,) | Угол поворота в радианах (pitch, yaw, roll) |
| `angle_deg_pitch_yaw_roll` | (3,) | Угол поворота в градусах |
| `rotation_row_matrix` | (3, 3) | Матрица поворота (row-major) |
| `translation` | (3,) | Вектор трансляции |
| `object_normalization_center` | (3,) | Центр нормализации объекта |
| `object_normalization_scale` | (1,) | Масштаб нормализации объекта |
| `ldm106_vertex_indices` | (106,) | Индексы вершин BFM-сетки для 106 ландмарок |
| `ldm134_vertex_indices` | (134,) | Индексы вершин BFM-сетки для 134 ландмарок |
| `ldm*_object_normals` | (106/134, 3) | Нормали ландмарок в объектном пространстве |
| `ldm*_posed_normals` | (106/134, 3) | Нормали ландмарок с учётом позы |
| `ldm*_front_facing_original` | (106/134,) | Маска: обращена ли ландмарка к камере (0/1) |
| `ldm*_renderer_visible_original` | (106/134,) | Маска: видна ли ландмарка рендереру (0/1) |
| `ldm*_visible_original` | (106/134,) | Итоговая маска видимости (0/1) |
| `ldm*_canonical` | (106/134, 3) | Канонические координаты ландмарок (без позы) |
| `ldm*_canonical_normals` | (106/134, 3) | Нормали в каноническом пространстве |
| `canonical_rotation_row_matrix` | (3, 3) | Матрица поворота для канонического выравнивания |
| `canonical_yaw` | (1,) | Yaw в каноническом пространстве |
| `full_mesh_visible_packbits` | (4464,) | Упакованная маска видимости для всех 35709 вершин mesh |

### 12.3. Структура metadata.json

> **Исправлено 2026-07-29 по фактическим данным.** Прежняя версия раздела
> описывала `frame_000205` как фронтальный кадр (`pose_bin: "frontal_0"`,
> `yaw: -2.3`) и приводила углы плоскими полями. В репозитории это **левый
> профиль** с `yaw ≈ -79.6°`, а углы лежат во вложенном объекте `pose`.
> Ниже — реальное содержимое `calibration_dataset/person_01/frame_000205/metadata.json`.

```json
{
  "schema_version": "deeputin-calibration-seven-datasets-v7",
  "dataset_id": "person_01",
  "record_id": "frame_000205",
  "source_filename": "frame_000205.jpg",
  "frame_index": 205,
  "sequence_id": "person_01",
  "pose": {
    "yaw": -79.5689468383789,
    "pitch": 4.7526535987854,
    "roll": -9.202227592468262
  },
  "pose_bin": "left_profile",
  "canonical_yaw": -70.0,
  "alignment": {
    "raw": "3DDFA object-space landmarks before pose/translation/camera",
    "aligned": "full-mesh normalized object-space landmarks rotated to pose-bin canonical yaw"
  }
}
```

**Важно для реализации:**

- углы читаются как `metadata.pose.yaw`, а не `metadata.yaw`;
- `record.npz` **отсутствует** в git (`.gitignore: *.npz`) — API обязан
  корректно отдавать 404 и деградировать без 3D, когда файла нет;
- для фронтального эталона используйте кадр с `pose_bin: "frontal"`,
  например из `calibration_dataset/person_01/` с `canonical_yaw: 0.0`.

### 12.4. Распределение ракурсов в наборе

| pose_bin | Количество кадров | Описание |
|----------|-------------------|----------|
| `frontal` | 186 | Фронтальный (0°) |
| `left_profile` | 187 | Профиль левый (≈90°) |
| `right_profile` | 187 | Профиль правый (≈90°) |
| `left_light` | 70 | Левый полупрофиль (≈30°) |
| `right_light` | 77 | Правый полупрофиль (≈30°) |
| `left_mid` | 62 | Левый средний (≈45°) |
| `right_mid` | 68 | Правый средний (≈45°) |
| `left_deep` | 49 | Левый глубокий (≈60°) |
| `right_deep` | 57 | Правый глубокий (≈60°) |

---

## 13. Локализация (i18n)

### 13.1. Язык интерфейса

- **Язык по умолчанию**: Русский
- **Система**: i18next с React-биндингом (`react-i18next`)
- **Файлы переводов**: JSON-ресурсы в `src/locales/ru/`
- **Переключение языка**: Опционально (English fallback), но по умолчанию всегда русский

### 13.2. Словарь интерфейса

#### Основные элементы

| Английский (ключ) | Русский (значение) |
|-------------------|--------------------|
| `app.title` | "DEEPUTIN Forensic Suite" |
| `app.subtitle` | "Криминалистический анализ фотографий" |
| `app.search` | "Поиск по Photo ID..." |
| `app.cmdk.placeholder` | "Введите команду или Photo ID..." |
| `app.export.pdf` | "Экспорт PDF" |
| `app.settings` | "Настройки" |

#### Фильтры

| Ключ | Значение |
|------|----------|
| `filter.anomalies_only` | "Только аномалии" |
| `filter.era` | "Эпоха" |
| `filter.hypothesis` | "Гипотеза" |
| `filter.pose` | "Ракурс" |
| `filter.clear` | "Сбросить фильтры" |

#### Вкладки Left Panel

| Ключ | Значение |
|------|----------|
| `tab.geometry` | "Геометрия" |
| `tab.texture` | "Текстура" |
| `tab.chrono` | "Хронология" |
| `tab.verdict` | "Вердикт" |
| `tab.cluster` | "Кластеры" |
| `tab.landmarks` | "Ландмарки" |

#### Метрики геометрии

| Ключ | Значение |
|------|----------|
| `metric.bone_score` | "Оценка костной структуры" |
| `metric.orbits` | "Глубина глазниц" |
| `metric.chin` | "Проекция подбородка" |
| `metric.jaw` | "Ширина челюсти" |
| `metric.cheekbones` | "Скулы" |
| `metric.symmetry` | "Симметрия" |
| `metric.orbit_width_l` | "Ширина глазницы (лев.)" |
| `metric.orbit_width_r` | "Ширина глазницы (прав.)" |
| `metric.orbit_height_l` | "Высота глазницы (лев.)" |
| `metric.orbit_height_r` | "Высота глазницы (прав.)" |
| `metric.nose_width` | "Ширина носа" |
| `metric.nose_height` | "Высота носа" |
| `metric.mouth_width` | "Ширина рта" |
| `metric.chin_height` | "Высота подбородка" |
| `metric.zygomatic_width` | "Скуловая ширина" |
| `metric.jaw_width` | "Нижнечелюстная ширина" |

#### Гипотезы

| Ключ | Значение |
|------|----------|
| `hypothesis.h0` | "Один человек" |
| `hypothesis.h1` | "Силиконовая маска / Дипфейк" |
| `hypothesis.h2` | "Разные люди" |
| `hypothesis.confidence` | "Уровень доверия" |

#### 3D и ландмарки

| Ключ | Значение |
|------|----------|
| `landmark.title` | "Ключевые точки" |
| `landmark.drift` | "Дрейф ландмарок" |
| `landmark.metrics` | "Метрики ландмарок" |
| `landmark.show` | "Показать ландмарки" |
| `landmark.hide` | "Скрыть ландмарки" |
| `morph.title` | "Морфинг" |
| `morph.slider` | "Переход" |
| `morph.play` | "Воспроизвести" |
| `morph.pause` | "Пауза" |
| `morph.reset` | "Сброс" |
| `morph.export_gif` | "Экспорт GIF" |
| `morph.export_obj` | "Экспорт OBJ" |
| `morph.photo_a` | "Фото A (эталон)" |
| `morph.photo_b` | "Фото B (сравнение)" |

#### Эпохи

| Ключ | Значение |
|------|----------|
| `era.1` | "Эпоха 1 (1999–2004)" |
| `era.2` | "Эпоха 2 (2005–2009)" |
| `era.3` | "Эпоха 3 (2010–2014)" |
| `era.4` | "Эпоха 4 (2015–2019)" |
| `era.5` | "Эпоха 5 (2020–2025)" |

#### Сообщения об ошибках и состояниях

| Ключ | Значение |
|------|----------|
| `error.loading` | "Ошибка загрузки данных" |
| `error.network` | "Ошибка сети. Проверьте подключение" |
| `error.no_data` | "Нет данных для отображения" |
| `error.no_photo` | "Фото не найдено" |
| `loading.photos` | "Загрузка фотографий..." |
| `loading.mesh` | "Загрузка 3D-модели..." |
| `loading.landmarks` | "Загрузка ключевых точек..." |
| `empty.no_results` | "Ничего не найдено" |
| `empty.select_photo` | "Выберите фото для просмотра" |
| `empty.select_two` | "Выберите два фото для сравнения" |

### 13.3. Форматы дат и чисел

- **Даты**: `"1 января 2000"` (day month year, родительный падеж для месяца)
- **Числа**: десятичный разделитель — запятая (`0,92`), разделитель тысяч — пробел (`1 809`)
- **Проценты**: `92%`
- **Годы**: `1999–2025` (тире, не дефис)

### 13.4. Реализация

```typescript
// src/i18n/config.ts
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ru from "./locales/ru/translation.json";

i18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: "ru",
  fallbackLng: "ru",
  interpolation: { escapeValue: false },
});

export default i18n;
```

```typescript
// Использование в компонентах
import { useTranslation } from "react-i18next";

function HeaderBar() {
  const { t } = useTranslation();
  return <h1>{t("app.title")}</h1>;
}
```

## 14. Калибровочный набор данных (Calibration Dataset)

### 14.1. Состав набора

| Параметр | Значение |
|----------|----------|
| Всего фото | 943 |
| Всего персон | 7 |
| Ракурсов | 9 (frontal, left_*, right_*) |
| Источник | `calibration_dataset/` |
| Индекс | `calibration_dataset/all_calibration_index.csv` |

**Персоны**:

| Персона | Количество фото |
|---------|-----------------|
| person_01 | 133 |
| person_02 | 196 |
| person_03 | 91 |
| person_04 | 168 |
| person_05 | 91 |
| person_06 | 176 |
| person_07 | 88 |

### 14.2. Назначение в системе

Калибровочный набор используется для:

1. **Калибровка сравнения двух фото**: Подбор пары с наиболее близкими углами (yaw/pitch/roll) для минимизации шума, вызванного разницей в ракурсе
2. **Построение эталонной формы**: Для каждого ракурса вычисляется средняя форма лица по всем персонам
3. **Оценка шума системы**: Вариативность метрик внутри одной персоны при одинаковом ракурсе
4. **Валидация аномалий**: Сравнение отклонений в анализируемых фото с распределением отклонений в калибровочном наборе

### 14.3. Алгоритм калиброванного сравнения

```
Вход: Photo A (анализируемое), Photo B (сравниваемое)
Выход: Скорректированные diff-метрики

1. Извлечь углы (yaw_A, pitch_A, roll_A) из metadata.json Photo A
2. Извлечь углы (yaw_B, pitch_B, roll_B) из metadata.json Photo B
3. Для Photo A:
   a. Найти в all_calibration_index.csv запись с минимальным
      d = sqrt((yaw_A - yaw_c)^2 + (pitch_A - pitch_c)^2 + (roll_A - roll_c)^2)
   b. Кандидаты: все 943 записи (или ограниченные той же pose_bin)
   c. Результат: Calib_A с углами (yaw_cA, pitch_cA, roll_cA) и остаточным d_A
4. Для Photo B — аналогично, получить Calib_B с остаточным d_B
5. Вычислить сырые метрики:
   raw_diff = metrics(Photo A) - metrics(Photo B)
   calib_diff = metrics(Calib_A) - metrics(Calib_B)
6. Итоговый результат:
   calibrated_diff = raw_diff - calib_diff
   noise_estimate = |calib_diff|
7. Если d_A > 15° или d_B > 15° — выдать предупреждение о низком качестве калибровки
```

### 14.4. API эндпоинты

```
GET  /api/v1/calibration                   — информация о калибровочном наборе
GET  /api/v1/calibration/pairs?yaw=X&pitch=Y&roll=Z  — поиск ближайшей калибровочной пары по углам
GET  /api/v1/calibration/pair?photo_a=ID_A&photo_b=ID_B  — калиброванное сравнение двух фото
GET  /api/v1/calibration/stats             — статистика калибровочного набора
```

### 14.5. Визуализация в интерфейсе

- **Индикатор калибровки** в ComparisonMode: зелёный/жёлтый/красный в зависимости от d_A, d_B
- **Таблица калибровочных пар**: отображение подобранных пар с углами и остаточным расхождением
- **График распределения углов**: scatter plot всех 943 калибровочных фото в пространстве (yaw, pitch) с подсветкой выбранной пары
- **Метрика качества калибровки**: "Шум: X.X мм (d = X.X°)"

---

## 15. Цветовая палитра (forensic dark theme)

```css
:root {
  /* Background */
  --bg-primary: #09090b;
  --bg-secondary: #0d0d12;
  --bg-tertiary: #14141a;
  --bg-elevated: #1a1a24;
  
  /* Text */
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  
  /* Accent — Geometry */
  --accent-geometry: #4f98a3;
  --accent-geometry-dim: #2d6b75;
  
  /* Accent — Bio-Age */
  --accent-bio: #fdab43;
  --accent-bio-dim: #b87a2e;
  
  /* Accent — Anomaly */
  --accent-anomaly: #ff3b30;
  --accent-anomaly-dim: #b82a22;
  
  /* Hypothesis colors */
  --h0-color: #22c55e;
  --h1-color: #fdab43;
  --h2-color: #ff3b30;
  
  /* Borders */
  --border-color: #1e293b;
  --border-hover: #334155;
  
  /* Era colors */
  --era-1: #3b82f6;
  --era-2: #8b5cf6;
  --era-3: #ec4899;
  --era-4: #f59e0b;
  --era-5: #10b981;
}
```

---

## 16. Маршрутизация (TanStack Router)

```
/                                   — Dashboard overview
/timeline                           — Full timeline view
/timeline?photo=P00432              — Timeline с выбранным кадром
/timeline?era=ERA_1&hypothesis=H0   — Timeline с фильтрами
/compare?anchor=P00001              — Split-screen сравнение
/compare?anchor=P00001&target=P00432 — Сравнение двух конкретных кадров
/inspector/3d?photo=P00432          — 3D Inspector для кадра
/inspector/3d/morph?from=P00001&to=P00432 — 3D морфинг между двумя кадрами
/landmarks/drift                      — Дрейф ландмарок
/landmarks/metrics                    — Метрики ландмарок
/landmarks/pca                        — PCA-проекция
/report                             — Сгенерированный PDF-отчёт
/settings                           — Настройки отображения
```

---

## 17. API интеграция (бэкенд)

### 17.1. Эндпоинты

```
GET  /api/v1/photos                    — список всех фото (PhotoPoint[])
GET  /api/v1/photos/:id                — детали фото
GET  /api/v1/photos/:id/mesh           — record.npz (3D mesh + реконструкция)
GET  /api/v1/photos/:id/landmarks/106    — ldm106_aligned.csv
GET  /api/v1/photos/:id/landmarks/134    — ldm134_aligned.csv
GET  /api/v1/photos/:id/landmarks/record — record.npz (полная реконструкция)
GET  /api/v1/photos/:id/landmarks/metrics — рассчитанные метрики ландмарок
GET  /api/v1/landmarks/drift?pose=frontal — данные дрейфа ландмарок по ракурсу
GET  /api/v1/landmarks/pca              — PCA-проекция всех кадров
GET  /api/v1/photos/:id/face_mask      — face_mask.png
GET  /api/v1/photos/:id/texture        — texture.json
GET  /api/v1/timeline                  — данные для таймлайна
GET  /api/v1/timeline/range?from=X&to=Y — данные за диапазон
GET  /api/v1/compare/:a/:b             — сравнение двух кадров
GET  /api/v1/compare/:a/:b/calibrated  — калиброванное сравнение (с подбором пар из calibration_dataset)
GET  /api/v1/clusters                  — PCA/t-SNE кластеризация
POST /api/v1/report/generate           — генерация PDF-отчёта
GET  /api/v1/calibration               — информация о калибровочном наборе
GET  /api/v1/calibration/pair?yaw=X&pitch=Y&roll=Z  — поиск ближайшей калибровочной пары
GET  /api/v1/calibration/pair?photo_a=ID_A&photo_b=ID_B  — калиброванное сравнение двух фото
GET  /api/v1/calibration/stats         — статистика калибровочного набора
```

### 17.2. Формат данных

```json
// GET /api/v1/photos — ответ
{
  "photos": [
    {
      "id": "2000_01_01_p01f000227__551a232ede50",
      "date": "2000-01-01",
      "year": 2000,
      "era": "ERA_1",
      "pose": "frontal",
      "quality": 0.85,
      "fuzzyLabel": "STRONGLY_MATCHING",
      "dominant": "H0",
      "p0": 0.92,
      "p1": 0.05,
      "p2": 0.03,
      "confidence": 0.88,
      "flags": [],
      "geometry": {
        "boneScore": 0.87,
        "orbits": 0.91,
        "chin": 0.84,
        "jaw": 0.79,
        "cheekbones": 0.88,
        "symmetry": 0.93,
        "poseYaw": -2.3
      }
    }
  ],
  "meta": {
    "total": 1809,
    "eras": ["ERA_1", "ERA_2", "ERA_3", "ERA_4", "ERA_5"],
    "schema": "deeputin-ui-v1"
  }
}
```

---

## 17.3. Границы формулировок (обязательно к соблюдению)

> Добавлено 2026-07-29. Раздел разрешает конфликт между UI-моделью `H0/H1/H2`
> и `app6/AGENTS.md`, который запрещает категоричный вывод о личности.

Бэкенд **не выдаёт** и UI **не отображает** утверждений вида «другой человек»,
«двойник», «маска». Вероятности `p0/p1/p2` — диагностическая величина, а не
вердикт. Правила отображения:

1. Рядом с любой гипотезой обязательно показывается `evidence_state`
   (`within_noise`, `elevated_uncertain`, `insufficient_calibration`,
   `not_measurable`, `quality_limited`, `pose_leakage_limited`) и список
   применённых гейтов.
2. Если `texture_conclusions_allowed === false` (сработал гейт качества,
   см. ТЗ п.8), текстурные метрики отображаются серым с пометкой
   «недостаточное качество источника» и не участвуют в агрегате.
3. Метрика `not_measurable` не приравнивается к нулю и не рисуется как точка на
   треке: пропуск данных отображается разрывом линии.
4. Любая аномалия сопровождается полем `alternative_explanations` из ответа API.
5. Формулировка результата: «обнаружено статистически необычное расхождение при
   данных условиях», а не «доказан другой человек».

Метрика текстуры называется `texture_anomaly_score` — она измеряет отклонение
от нормы реальной кожи (модель one-class на 402 образцах), а **не** вероятность
силикона. Подпись «вероятность силикона» в интерфейсе недопустима.

---

## 18. Критерии приёмки (Definition of Done)

- [ ] Все компоненты реализованы на React 19 + TypeScript 5.9
- [ ] Canvas-таймлайн работает на 60 FPS при 1809 точках на 14 треках
- [ ] Виртуализация filmstrip: 1809 миниатюр без проседания производительности
- [ ] Zustand store синхронизирует playhead, zoom, filters между всеми панелями
- [ ] Split-screen сравнение: левая панель фиксирована, правая синхронно скроллится
- [ ] Фильтр "Только аномалии" динамически скрывает нормальные кадры
- [ ] 3D Inspector загружает record.npz и отображает mesh с тепловой картой
- [ ] Command Palette (Cmd+K) ищет по photo_id, датам, флагам
- [ ] Экспорт PDF: текущий вид таймлайна + выбранные панели
- [ ] Тёмная тема (Cosmic Slate) применена ко всем компонентам
- [ ] Все 6 вкладок Left Panel реализованы и заполнены данными (включая LANDMARKS)
- [ ] Маршрутизация TanStack Router работает для всех путей
- [ ] API-интеграция с бэкендом через TanStack Query
- [ ] Локализация: весь интерфейс на русском языке через i18next
- [ ] Сборка: `npm run build` без ошибок, production-бандл < 2MB (без 3D)
- [ ] **LandmarkDriftChart**: визуализация дрейфа ландмарок с группировкой по pose_bin
- [ ] **LandmarkMetrics**: расчёт межландмаркных расстояний, симметрии, Procrustes, PCA
- [ ] **3D Morphing**: интерактивный слайдер перехода между двумя mesh, экспорт GIF/OBJ
- [ ] **i18n**: все тексты интерфейса на русском, корректные форматы дат и чисел
- [ ] **Пример данных**: эталонное фото person_01/frame_000205 используется для тестирования
- [ ] **Калиброванный режим**: ComparisonMode использует calibration_dataset для подбора пар с минимальным угловым расхождением
- [ ] **Калибровочный алгоритм**: реализован поиск ближайшей пары по евклидову расстоянию (yaw, pitch, roll)
- [ ] **Индикатор качества калибровки**: цветовая индикация (зелёный/жёлтый/красный) в зависимости от остаточного угла d

---

## 19. Этапы реализации

### Этап 1 (Фундамент)
- Настройка Vite + React 19 + TypeScript + Tailwind + shadcn/ui
- Реализация Zustand store с полным состоянием
- HeaderBar с Command Palette и глобальными фильтрами
- Тёмная тема (CSS variables)

### Этап 2 (Таймлайн)
- Canvas-таймлайн с 14 треками (visx/d3)
- Playhead, zoom, pan, клик по точке
- Filmstrip с TanStack Virtual
- Drag-to-scrub

### Этап 3 (Панели)
- LeftPanel с 6 вкладками
- GEOMETRY: таблица 21 зоны + radar chart
- TEXTURE: метрики кожи + миниатюра
- CHRONO: флаги + CUSUM chart
- VERDICT: вердикт + вероятности
- CLUSTER: PCA/t-SNE scatter plot
- LANDMARKS: 3D-просмотр ландмарок, таблица координат, нормали

### Этап 4 (Сравнение, 3D и ландмарки)
- ComparisonMode (split-screen)
- 3D Inspector (react-three-fiber) с режимом морфинга
- Тепловая карта расхождений
- LandmarkDriftChart — дрейф ландмарок по ракурсам
- LandmarkMetrics — межландмаркные расстояния, симметрия, Procrustes, PCA
- Экспорт GIF и OBJ

### Этап 5 (Локализация и интеграция)
- i18next: русский язык интерфейса
- API-эндпоинты бэкенда
- TanStack Query интеграция
- Экспорт PDF
- Маршрутизация TanStack Router
- Финальное тестирование на эталонном фото person_01/frame_000205