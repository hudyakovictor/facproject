# Улучшения для максимального балла (100/100)

## П.4 — Визуализация данных (Canvas/треки/графики) — текущий 90 → цель 100

### 4.1. Формат передачи данных в Canvas

**Проблема**: Не указано, как данные передаются из Zustand в Canvas-рендерер.

**Решение**:
```typescript
// core/canvas.ts
export interface CanvasDataPacket {
  /** Массив точек для одного трека */
  points: Array<{
    x: number;        // timestamp (unix ms) — позиция по оси X
    y: number;        // значение метрики — позиция по оси Y
    photoId: string;  // для клика/ховера
    flags?: string[]; // аномалии для маркеров
  }>;
  /** Мета-информация трека */
  meta: {
    id: string;
    label: string;
    type: TrackType;
    color: string;
    yMin: number;
    yMax: number;
    yUnit: string;
    thresholdLines?: Array<{ value: number; label: string; color: string }>;
  };
}

/** Единый буфер для Canvas (SharedArrayBuffer для Worker) */
export interface CanvasRenderBuffer {
  tracks: CanvasDataPacket[];
  viewport: { xStart: number; xEnd: number; yStart: number; yEnd: number };
  playheadX: number | null;
  dpr: number; // devicePixelRatio
}
```

### 4.2. Механизм Zoom (дискретный + плавный)

**Проблема**: Не описан механизм масштабирования.

**Решение**:
- **Scroll wheel**: плавный zoom с фиксацией на позиции курсора мыши (pinch-zoom логика)
- **Preset уровни**: 1Y (год), 5Y (пятилетка), 10Y (десятилетие), ALL (всё)
- **Кнопки**: `[+]` `[-]` `[Fit All]` в правом нижнем углу Canvas
- **Range slider** под Canvas для выбора видимого диапазона
- **Анимация**: при смене preset — плавный transition 300ms ease-in-out

```typescript
export type ZoomPreset = "1Y" | "5Y" | "10Y" | "ALL";

export interface ZoomState {
  level: number;          // 1.0 = ALL, 10.0 = 1Y
  anchorX: number;        // timestamp, на котором сфокусирован zoom
  preset: ZoomPreset;
  animation: {
    from: number;
    to: number;
    progress: number;     // 0..1
  } | null;
}
```

### 4.3. Threshold/gate линии на треках

**Проблема**: На треках нет пороговых линий, показывающих границы нормы.

**Решение**:
- Каждый трек может иметь **threshold lines**:
  - `warning` — жёлтая пунктирная линия
  - `critical` — красная пунктирная линия
  - `normal_range` — зелёная заливка между двумя значениями
- Пример для трека Bone Score:
  - `normal_range: [0.7, 1.0]` — зелёная зона
  - `warning: 0.5` — жёлтая линия
  - `critical: 0.3` — красная линия
- Пример для трека P(H0):
  - `normal_range: [0.8, 1.0]` — высокая вероятность одного человека
  - `warning: 0.5` — неуверенность

```typescript
export interface ThresholdLine {
  value: number;
  label: string;
  color: string;
  style: "solid" | "dashed" | "dotted";
  fillRange?: { from: number; to: number; color: string; opacity: number };
}
```

### 4.4. Легенда осей Y (разные шкалы у треков)

**Проблема**: 14 треков имеют разные единицы измерения и диапазоны.

**Решение**:
- Каждый трек имеет **собственную шкалу Y** (слева от трека)
- Шкала отображается как тонкая полоса с делениями и значениями
- Для треков с одинаковой единицей измерения — синхронизация шкал
- **Группировка шкал**:
  - Геометрия (треки 1–6): шкала 0–1 или -3σ..+3σ
  - Гипотезы (треки 7–9): шкала 0–1 (вероятность)
  - Качество (трек 10): шкала 0–1
  - Экспрессия (трек 11): шкала 0–12 (magnitude)
  - Pose (трек 12): шкала -90..+90 (градусы)
  - Флаги (трек 13): бинарная шкала
  - Эпохи (трек 14): цветовые полосы без шкалы

### 4.5. WebGL-ускорение для >5000 точек

**Проблема**: Canvas2D может тормозить при >5000 точек на 14 треках.

**Решение**:
- **PixiJS 8** как WebGL-рендерер для Canvas (fallback на Canvas2D если WebGL недоступен)
- Точки рендерятся как Geometry instances (один draw call на трек)
- Line rendering через Mesh + GLSL shader для сглаженных линий
- Auto-detection: если точек > 3000 → WebGL, иначе Canvas2D

```typescript
export type CanvasRenderer = "canvas2d" | "webgl";

export function selectRenderer(pointCount: number): CanvasRenderer {
  return pointCount > 3000 ? "webgl" : "canvas2d";
}
```

### 4.6. Интерактивные аннотации на треках

**Проблема**: Нет возможности добавлять заметки/аннотации на таймлайн.

**Решение**:
- **Правый клик** на треке → "Add annotation"
- Аннотация: текст + цвет + привязка к photo_id
- Отображается как иконка заметки на треке
- Ховер на иконку → всплывающий текст
- Аннотации сохраняются в localStorage (или синхронизируются с бэкендом)

### 4.7. Мини-карта (MiniMap)

**Проблема**: При zoom'е на детальный участок теряется контекст всего таймлайна.

**Решение**:
- **MiniMap** в нижней части Canvas (уменьшенная копия всех треков)
- Прямоугольник viewport на MiniMap показывает текущую видимую область
- Drag прямоугольника — перемещение viewport
- Клик на MiniMap — прыжок в выбранную позицию
- Высота MiniMap: 80px

### 4.8. Экспорт трека как PNG

**Проблема**: Нет возможности сохранить отдельный трек как изображение.

**Решение**:
- Правый клик на треке → "Export as PNG"
- Canvas трека рендерится в отдельный offscreen canvas
- Сохраняется как PNG с прозрачным фоном
- Разрешение: 2x (Retina)

### 4.9. Сравнение треков (Overlay Mode)

**Проблема**: Нельзя наложить два трека друг на друга для визуального сравнения.

**Решение**:
- **Overlay Mode**: кнопка "Compare Tracks" в контекстном меню
- Выбор двух треков → они рендерятся на одном Canvas с разными цветами
- Отображение разницы (diff) как затенённая область между линиями
- Коэффициент корреляции Пирсона между треками

### 4.10. Анимация playhead (Auto-play)

**Проблема**: Нет автоматического проигрывания таймлайна.

**Решение**:
- Кнопка "▶ Play" в панели управления
- Playhead автоматически движется слева направо
- Скорость: 1x, 2x, 5x, 10x
- При достижении конца — стоп
- Left Panel обновляется синхронно с движением playhead
- Hotkey: `Space` — play/pause

---

## П.6 — 3D-визуализация и mesh — текущий 78 → цель 100

### 6.1. Формат загрузки reconstruction.npz в браузер

**Проблема**: .npz — бинарный формат NumPy, не читается браузером напрямую.

**Решение**:
- **Вариант A (рекомендуемый)**: Бэкенд конвертирует .npz в .glb (GLTF Binary) при запросе
  - Эндпоинт: `GET /api/v1/photos/:id/mesh.glb`
  - Формат: стандартный 3D-формат, читается Three.js напрямую
  - Размер: ~2-5 MB (сжатие Draco)
- **Вариант B**: Браузерный декодер .npz через fflate + сырой парсинг
  - Библиотека: `fflate` (6KB) для распаковки .npz
  - Парсинг заголовка .npz (PK_NPY header)
  - Конвертация Float32Array в BufferGeometry Three.js
- **Кэширование**: IndexedDB (idb) для хранения загруженных mesh

```typescript
// 3d/loader.ts
export async function loadMesh(photoId: string): Promise<BufferGeometry> {
  // 1. Проверить IndexedDB кэш
  const cached = await meshCache.get(photoId);
  if (cached) return cached;

  // 2. Загрузить .glb с бэкенда
  const response = await fetch(`/api/v1/photos/${photoId}/mesh.glb`);
  const glb = await response.arrayBuffer();
  
  // 3. Декодировать Draco (если сжато)
  const decoder = new DRACOLoader();
  const geometry = await decoder.decode(glb);
  
  // 4. Сохранить в кэш
  await meshCache.set(photoId, geometry);
  
  return geometry;
}
```

### 6.2. Fallback при недоступности WebGL2

**Проблема**: WebGL2 может быть недоступен (старые браузеры, встроенные GPU).

**Решение**:
- **Уровень 1**: WebGL2 + Three.js (полный функционал)
- **Уровень 2**: WebGL1 + Three.js (без post-processing, без теней)
- **Уровень 3**: Canvas2D рендеринг (только проекция 3D→2D)
  - Ортографическая проекция: фронт, профиль L, профиль R
  - Рендеринг линий вместо mesh
  - Без текстур, без освещения
- **Уровень 4**: Статическое изображение (заглушка)
  - Показать предварительно зарендеренный PNG с бэкенда
  - Сообщение: "3D Inspector requires WebGL"

```typescript
export type WebGLSupport = "webgl2" | "webgl1" | "canvas2d" | "none";

export function detectWebGLSupport(): WebGLSupport {
  try {
    const canvas = document.createElement("canvas");
    const gl2 = canvas.getContext("webgl2");
    if (gl2) return "webgl2";
    const gl1 = canvas.getContext("webgl");
    if (gl1) return "webgl1";
    return "canvas2d";
  } catch {
    return "none";
  }
}
```

### 6.3. Метрики производительности для 35K вершин

**Проблема**: BFM-сетка содержит 35709 вершин — нужны гарантии FPS.

**Решение**:
- **Target**: 30 FPS minimum, 60 FPS target
- **Оптимизации**:
  - InstancedMesh для ландмарок (106 сфер — один draw call)
  - LOD (Level of Detail):
    - Полная сетка (35K вершин) — при zoom < 2x
    - Упрощённая сетка (8K вершин) — при zoom 2-5x
    - Bounding box — при zoom > 5x
  - Draco compression для .glb (сжатие 10:1)
  - Geometry merging для тепловой карты
- **Мониторинг**: FPS counter в debug-режиме (Ctrl+D)

```typescript
export interface LODConfig {
  full: { maxDistance: number; vertices: number };   // 35K
  medium: { maxDistance: number; vertices: number };  // 8K
  low: { maxDistance: number; vertices: number };     // 2K
  boundingBox: { maxDistance: number };               // box
}
```

### 6.4. Цветовая шкала тепловой карты

**Проблема**: Не описана цветовая схема Point-to-Plane расстояний.

**Решение**:
- **Цветовая шкала** (от минимального к максимальному отклонению):
  - `#22c55e` (зелёный) — 0 мм (идеальное совпадение)
  - `#84cc16` (лайм) — 0.5 мм
  - `#eab308` (жёлтый) — 1.0 мм (порог нормы)
  - `#fdab43` (оранжевый) — 2.0 мм (предупреждение)
  - `#ff3b30` (красный) — 3.0+ мм (аномалия)
- **Дискретизация**: 5 цветовых зон с линейной интерполяцией
- **Легенда**: вертикальный gradient bar справа от 3D-вьюпорта
- **Auto-range**: шкала автоматически подстраивается под min/max отклонение в текущей паре

### 6.5. Генерация GIF морфинга

**Проблема**: Не описан механизм генерации animated GIF.

**Решение**:
- **Бэкенд** (рекомендуемый вариант):
  - Эндпоинт: `POST /api/v1/render/morph`
  - Тело: `{ "from": "photo_id_A", "to": "photo_id_B", "frames": 30, "fps": 10 }`
  - Бэкенд интерполирует вершины между двумя mesh
  - Рендерит 30 кадров с разных углов (фронт, профиль L/R, 3/4)
  - Собирает GIF через `imageio` (Python)
  - Возвращает: `{ "gif_url": "/renders/morph_A_B.gif", "frames": 30, "duration_ms": 3000 }`
- **Фронтенд** (альтернатива для малого числа кадров):
  - `gif.js` библиотека (3KB) для сборки GIF в браузере
  - Только для 5-10 кадров (иначе браузер зависнет)
  - Canvas.captureStream() + MediaRecorder для WebM видео

### 6.6. Сравнение двух mesh (Split-screen 3D)

**Проблема**: Нет возможности визуально сравнить две 3D-сетки рядом.

**Решение**:
- **Split-screen 3D**: левая mesh (эталон), правая mesh (сравниваемая)
- Синхронизированный OrbitControls — вращение одновременно обеих mesh
- **Diff overlay**: полупрозрачное наложение одной mesh на другую
- **Cross-fade**: слайдер, плавно переключающий видимость между mesh A и B
- **Point-to-Plane гистограмма**: распределение расстояний между mesh

### 6.7. Анатомические зоны с подсветкой

**Проблема**: 21 анатомическая зона не визуализирована на mesh.

**Решение**:
- **Vertex coloring**: каждая зона окрашена в свой цвет
- **Легенда зон**: список 21 зоны с цветовыми маркерами
- **Клик по зоне**: подсветка + отображение названия и значения метрики
- **Режимы отображения**:
  - "Anatomy" — цвет по анатомическим зонам
  - "Heatmap" — цвет по Point-to-Plane отклонению
  - "Hybrid" — анатомические границы + тепловая карта внутри

### 6.8. Измерение расстояний на mesh

**Проблема**: Нет инструмента для ручного измерения расстояний.

**Решение**:
- **Инструмент "Ruler"**: клик по двум точкам на mesh → расстояние в мм
- **Инструмент "Angle"**: клик по трём точкам → угол в градусах
- **Инструмент "Cross-section"**: плоскость сечения mesh → 2D-профиль
- Результаты отображаются в панели справа
- Экспорт измерений как JSON

### 6.9. Анимация возрастных изменений

**Проблема**: Нет визуализации плавного изменения mesh во времени.

**Решение**:
- **Timeline slider** под 3D-вьюпортом
- При перемещении slider — mesh морфит между кадрами хронологически
- Интерполяция вершин между соседними reconstruction.npz
- Отображение года на слайдере
- Кнопка "▶ Auto-play" — автоматическая анимация по годам

### 6.10. Экспорт 3D-сцены

**Проблема**: Нет возможности выгрузить 3D-сцену для внешних инструментов.

**Решение**:
- **Экспорт как .glb**: полная сцена с текстурами и тепловой картой
- **Экспорт как .ply**: только геометрия (для MeshLab/CloudCompare)
- **Экспорт как .csv**: таблица Point-to-Plane расстояний для каждой вершины
- **Экспорт как .png**: скриншот текущего вида (4K разрешение)
- Все экспорты через бэкенд (фронтенд отправляет запрос, бэкенд генерирует файл)