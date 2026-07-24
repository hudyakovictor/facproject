# Design Decision: React Flow composition for DEEPUTIN

## Решение

Не брать один showcase-проект целиком. Использовать **бесплатный Workflow Editor как композиционную основу**, но сохранить текущий React + Vite frontend вместо перехода на Next.js. Из официальных бесплатных React Flow примеров вручную перенести только необходимые паттерны.

## Базовая комбинация

1. **Workflow Editor** — структура canvas, sidebar, custom nodes, Zustand, runner и ELK layout.
2. **Dark Mode** — интерфейс только тёмный; пользовательского light theme не требуется.
3. **Sub Flow** — Stage → module → function и вложенные scenario groups.
4. **ELKjs Multiple Handles** — фиксированные порты и уменьшение пересечений связей.
5. **Contextual Zoom** — semantic zoom: stage → module → function → ports/metrics.
6. **Node Status Indicator** — readiness как тело узла, runtime как внешнее кольцо.
7. **Node Search, MiniMap, Controls, Zoom Slider** — навигация по большому pipeline.
8. **DevTools** — только development/debug режим интерфейса.

Pro-примеры не становятся зависимостью проекта. Expand/Collapse реализуется собственной фильтрацией visible graph и ELK relayout, чтобы проект оставался бесплатным и переносимым.

## Почему одного node canvas недостаточно

Для проекта нужны три синхронизированные поверхности:

```text
A. Pipeline Canvas
   Основные функции и зависимости app6

B. Scenario Rail / Photo Timeline
   5–7 миниатюр текущего теста, статусы обработки и связи пар

C. Pair Analysis Workbench
   Графики, landmarks, 3D meshes, heatmap и параметры визуализации
```

React Flow отвечает за A и за короткоживущие scenario groups в B. Графики и 3D не помещаются внутрь обычных function nodes: они открываются в нижней/правой аналитической панели, синхронизированной с выбранной фотографией или pair edge.

## Scenario Rail

При выборе или запуске сценария под pipeline появляется отдельная горизонтальная линия:

```text
[Фото 1] ─ pair 1 ─ [Фото 2] ─ pair 2 ─ [Фото 3] ... [Фото 7]
   ↓                   ↓                   ↓
Stage 1 status      Stage 1 status      Stage 1 status
pose/quality        pose/quality        pose/quality
```

Миниатюра показывает:

- изображение или privacy-safe placeholder;
- person role A/A2/B/C/D;
- pose bin и yaw/pitch/roll;
- runtime ring;
- Stage 1 QC;
- cached/fresh badge;
- ошибки и предупреждения.

Pair edge показывает:

- applicable/skipped;
- raw geometric delta;
- pose-corrected delta;
- residual noise;
- evidence state;
- кнопку открытия Pair Workbench.

Scenario Rail временный: он появляется для выбранного/активного сценария и может быть закреплён. Первый обязательный сценарий закреплён всегда, пока его gate не закрыт. Остальные не занимают canvas постоянно.

## График 5–7 фотографий

Под Photo Rail располагается linked multi-series chart:

- yaw/pitch/roll;
- residual pose после correction;
- landmark/mesh delta;
- raw signal;
- corrected signal;
- estimated pose noise;
- signal after noise suppression;
- quality/visibility;
- calibration reference band.

Общий X — фотографии/пары в хронологическом порядке. Наведение на точку выделяет thumbnail, pair edge, function span и соответствующую 3D модель. Можно включать режимы `raw`, `corrected`, `difference`, `noise only`, `before/after`.

## Variable Combination Matrix

Количество комбинаций нельзя фиксировать глобально. Оно задаётся по сценарию и pose bin:

```yaml
scenario: S01_stability_frontal_A
pose_combinations:
  frontal: 7
  left_light: 3
  right_light: 3
  left_profile: 1
  right_profile: 1
```

UI поддерживает:

- одну комбинацию на выбранном pose;
- другую комбинацию на другом pose;
- 1/3/7 комбинаций;
- все комбинации для одного pose;
- одну комбинацию для всех девяти poses;
- полную variable matrix;
- автоматическое предложение дополнительных комбинаций для плохо покрытых или нестабильных poses.

Coverage Matrix показывает строки person combinations и столбцы девяти pose bins. Ячейки имеют состояния not planned, queued, passed, warning, failed, calibration-required.

## Pair Analysis Workbench

### 2D

- исходные фотографии A/B;
- synchronized zoom/pan;
- LDM106/LDM134 overlays;
- visibility и confidence;
- raw/canonical/chronology-aligned переключатель;
- difference vectors;
- включение отдельных landmark zones.

### 3D

- mesh A и mesh B в синхронных viewports;
- overlay mode;
- identity-only и identity+expression;
- raw/normalized/canonical;
- landmarks и motion vectors;
- residual shape heatmap;
- clipping/opacity/wireframe;
- UV texture только в режиме `Visualization only`.

### Heatmap

Настройки отображения не являются научными thresholds. Они хранятся отдельно в `visualization_heatmap.yaml`:

- palette;
- symmetric/asymmetric scale;
- min/max или percentile clip;
- zero color;
- NaN color;
- opacity;
- units;
- zone filtering.

Изменение палитры или диапазона отображения никогда не меняет metric, evidence state или calibration bundle. Научные параметры находятся в отдельном versioned analysis config и применяются только после validation gate.

## Config workflow

```text
Изменение параметров в UI
→ draft config
→ run scenario matrix
→ compare baseline/candidate
→ validation gates
→ approve
→ export versioned YAML/JSON config
→ developer reviews patch
→ config enters app6 only through Patch Center
```

Каждый config содержит schema, version, author/time, source run IDs, dataset hashes, code/model hashes, affected functions и rollback reference.

## Main Analysis Timeline

Позже тот же Photo Rail используется для основного dataset, но с virtualization и lazy thumbnails. На canvas одновременно рендерится только видимый временной диапазон. Полный dataset не превращается в тысячи постоянных React Flow nodes.

## Граница evidence

- UV/texture — только визуализация.
- Heatmap palette — только визуализация.
- Скрытие неудобных точек на графике не меняет расчёт.
- UI config не попадает в app6 без test matrix и review.
- Больше комбинаций повышает test coverage, но не превращает synthetic/curated tests в доказательство личности.
