# DEEPUTIN UI v5 — полное ТЗ реализации от нуля до 100% готовности

**Статус:** целевая спецификация будущего интерфейса.  
**Принцип:** тезисно, но с полным описанием страниц, элементов, состояний, данных и acceptance gates.  
**Граница:** UI отображает измерения и рабочие гипотезы, но не выносит автоматический вердикт о личности.

---

# 1. Цель интерфейса

UI v5 должен объединить в одной forensic workstation весь цикл:

```text
источники → ingest/provenance → Stage 1 → контроль качества → выборка →
Stage 2 → хронология → pair analysis → morphing → clustering →
private hypothesis validation → human review → Stage 3 → публикационные черновики →
экспорт/архив/проверка воспроизводимости
```

Интерфейс предназначен одновременно для:

1. журналиста-расследователя;
2. технического специалиста по computer vision/статистике;
3. независимого скептического reviewer;
4. редактора/fact-checker;
5. AI/machine reviewer через структурированные artifacts;
6. администратора локальной workstation.

---

# 2. Неизменяемые продуктовые правила

1. Одна фотография — один `photo_id`, одна дата и одна точка времени.
2. Pair/event/interval/run не изображаются как дополнительные фотографии.
3. На главном timeline по умолчанию открыт один pose bin.
4. Timeline занимает основную площадь экрана.
5. Постоянных широких sidebar на timeline нет.
6. Контекстные controls раскрываются сверху поверх рабочей области.
7. Настройка располагается на странице, результат которой она изменяет.
8. Display settings и scientific settings визуально и технически разделены.
9. Значение без source artifact не отображается как измерение.
10. `null`, `excluded`, `limited`, `not_applicable` не превращаются в ноль.
11. Красный цвет означает приоритет проверки/threshold state, а не «другой человек».
12. Cluster ID не является identity label.
13. Private hypotheses не влияют на blind Stage 2 и не попадают в public report.
14. Любая тревожная карточка раскрывает applicability, calibration, provenance и альтернативы.
15. Stage 1 считается immutable evidence layer.
16. Все действия пользователя журналируются в audit log.
17. Любой экспорт содержит run/profile/schema/config identifiers.
18. Интерфейс работает с ~1900 фотографиями без отрисовки всех тяжёлых элементов одновременно.
19. Морфинг является визуализацией и не создаёт новые измерения.
20. Постоянно видна маркировка «отображение данных — не вердикт».

---

# 3. Типы сущностей интерфейса

## 3.1. PhotoPoint

Поля:

- `photo_id`;
- authoritative date;
- sequence внутри даты;
- pose bin;
- yaw/pitch/roll;
- Stage 1 status;
- quality/provenance/expression states;
- thumbnail/image URLs;
- artifact availability;
- run-independent Stage 1 fields.

Timeline semantics:

```text
x = xForDate(photo.date)
```

Все photo-level dots, thumbnail, markers, hover-guide и A/B pin используют один `x`.

## 3.2. PairMeasurement

Поля:

- `pair_id`;
- photo A/B;
- pair type;
- dates и interval;
- pose bin и axis gaps;
- common/calibrated points;
- coordinate space;
- geometry/mesh/descriptor metrics;
- calibration reference;
- measurement/evidence status;
- FDR p/q;
- quality/expression/provenance limitations;
- alternative explanations;
- reviewer state.

Timeline semantics:

```text
bridge x(A) → x(B)
```

## 3.3. EventMarker

Типы:

- change point;
- persistent change;
- return;
- rapid-rate candidate;
- same-day conflict;
- provenance conflict;
- duplicate;
- review flag;
- external publication/event marker.

## 3.4. IntervalBand

Типы:

- era;
- selected range;
- cluster regime;
- dense zone;
- low calibration coverage;
- source gap;
- review period;
- public event period.

## 3.5. Run/Profile

- analysis profile;
- frozen selection;
- Stage 2 run;
- Stage 3 report;
- calibration release;
- clustering run;
- hypothesis sensitivity profile.

## 3.6. Claim

Используется в публикационном модуле:

- claim ID;
- plain/technical wording;
- allowed strength;
- evidence refs;
- limitations;
- review/adjudication;
- public/private state.

---

# 4. Глобальная оболочка приложения

## 4.1. Верхняя панель

Высота ориентировочно 48–56 px. Содержит:

### Логотип и название

- `DEEPUTIN V5`;
- текущий раздел;
- клик открывает список основных разделов;
- не занимает отдельный sidebar.

### Dataset/Run selector

Показывает:

- активный dataset;
- Stage 1 snapshot;
- активный selection profile;
- Stage 2 run;
- calibration release;
- report version.

Функции:

- быстро переключить run;
- сравнить два run;
- скопировать permalink;
- показать fingerprint;
- предупредить, если profile изменён после run.

### Pipeline status

Компактные chips:

- Stage 1;
- selection profile;
- calibration;
- Stage 2;
- FDR;
- Stage 3;
- publication lint;
- private isolation.

Клик раскрывает подробный status popover.

### Blind mode

- `Blind: off/on`;
- скрывает даты, ID, имена сущностей и исторический контекст;
- не скрывает quality/applicability;
- раскрытие labels возможно только после фиксации review;
- состояние blind session журналируется.

### Command palette

Горячая клавиша `⌘K/Ctrl+K`.

Команды:

- перейти к фото/date/pair/run;
- открыть раздел;
- выбрать pose;
- включить metric layer;
- открыть A/B;
- запустить preflight/run;
- открыть review queue;
- экспортировать текущий view;
- показать shortcuts.

### Пользователь/роль

- reviewer/analyst/editor/admin;
- active workspace;
- audit identity;
- logout/session status при сетевом deployment.

## 4.2. Контекстная строка раздела

Под глобальной панелью. Содержание зависит от страницы.

Пример timeline:

```text
РАКУРС | МЕТРИКИ | ФИЛЬТРЫ | НАХОДКИ | СРАВНЕНИЕ | ВИД | ПОИСК
```

Все пункты открываются dropdown/popover поверх canvas.

## 4.3. Нижняя status bar

Показывает:

- текущий период;
- zoom;
- pose;
- видимых/всего фото;
- исключённых фото;
- active profile/run;
- loading/job state;
- keyboard hints;
- schema/build version;
- `ДАННЫЕ, НЕ ВЕРДИКТ`.

## 4.4. Глобальные overlays

- Command Palette;
- Recommendations;
- Job Progress;
- Notifications;
- Error details;
- Shortcut help;
- Audit event details;
- Global search results;
- Confirm/preview destructive action.

---

# 5. Карта маршрутов

```text
/overview
/timeline
/photos
/photos/:photoId
/pairs
/pairs/:photoA/:photoB
/morphing
/clustering
/hypotheses
/calibration
/profiles
/runs
/review
/reports
/publications
/demonstrations
/audit
/system
/settings
```

Modal/drawer state может кодироваться query parameters, чтобы ссылка воспроизводила рабочее состояние.

---

# 6. Страница «Обзор»

## Назначение

За 10–20 секунд ответить:

- какие данные подключены;
- что готово;
- что заблокировано;
- где пробелы;
- какие действия приоритетны.

## 6.1. Readiness header

Карточки:

- photos total/valid/failed;
- date range;
- 9 pose coverage;
- calibration persons/bins;
- latest Stage 2 run;
- candidate/limited/review counts;
- publication draft state.

Каждая карточка кликабельна и ведёт в соответствующий раздел.

## 6.2. Pipeline diagram

Этапы:

```text
Ingest → Stage 1 → Profile → Calibration → Stage 2 → Review → Stage 3 → Publication
```

Для каждого:

- ready/running/blocked/degraded;
- timestamp;
- version;
- count;
- действие.

## 6.3. Pose coverage

Матрица:

```text
era × 9 pose bins
```

Ячейка показывает:

- photo count;
- median quality;
- calibration support;
- empty/limited state.

Клик открывает timeline с pose/period filter.

## 6.4. Quality distribution

Гистограммы:

- resolution;
- blur/sharpness;
- exposure;
- visibility;
- reconstruction residual;
- texture applicability;
- provenance completeness.

## 6.5. Findings summary

Не только красные события, но и:

- within-noise;
- limited;
- excluded;
- pending review;
- reviewed;
- corroborated across bins;
- unresolved conflicts.

## 6.6. Recommendations preview

Три-пять наиболее важных действий с кнопкой `Открыть все`.

## 6.7. Latest activity

- завершённый job;
- новый run;
- reviewer action;
- profile change;
- generated report/export;
- integrity warning.

---

# 7. Страница «Данные и provenance»

## Назначение

Подготовить архив до Stage 1 и гарантировать, что каждый файл учтён.

## 7.1. Ingest area

Поддерживает:

- drag-and-drop;
- file picker;
- folder selection;
- batch upload;
- image + provenance sidecar;
- ZIP manifest только после безопасной проверки.

Для каждого файла до сохранения:

- extension/magic bytes;
- decode test;
- filename date;
- duplicate digest;
- perceptual near-duplicate;
- image dimensions;
- EXIF presence;
- sidecar schema;
- source/rights status.

## 7.2. Filename/date preview

Показывает:

- parsed authoritative date;
- sequence;
- proposed photo ID;
- EXIF date;
- source-claimed date;
- delta/conflict;
- исправление имени до ingest.

Нельзя молча исправлять дату.

## 7.3. Sidecar editor

Поля:

- source URL;
- archive URL;
- publisher;
- acquired time;
- collector;
- claimed date;
- rights/license;
- notes.

Функции:

- schema validation;
- URL check;
- archive link check;
- шаблоны источников;
- массовое применение publisher/collector;
- отдельный audit event.

## 7.4. Data table

Колонки:

- filename;
- authoritative date;
- source status;
- SHA/dHash;
- exact/near duplicate;
- Stage 1 state;
- pose;
- quality;
- artifact completeness;
- flags;
- actions.

Функции:

- TanStack Table + virtual rows;
- column chooser;
- saved views;
- multi-sort;
- advanced filters;
- CSV/JSON export;
- keyboard navigation.

## 7.5. Detail drawer

Временный drawer, не постоянный sidebar.

Содержит:

- source image;
- face crop;
- provenance chain;
- hashes;
- duplicate links;
- Stage 1 artifacts;
- validation errors;
- dependent pairs/runs/reports;
- rights status;
- actions.

## 7.6. Batch operations

- add/update sidecar;
- mark for review;
- exclude from profile;
- rerun validation;
- queue extraction;
- export evidence bundle;
- deletion preview.

Удаление:

- показывает dependencies;
- не удаляет immutable Stage 1 без admin workflow;
- требует typed confirmation;
- создаёт audit event.

## 7.7. Extraction queue

Параметры:

- input selection;
- CPU/device policy;
- limit/test gate;
- full or sample run;
- output snapshot;
- fail-fast/continue;
- expected runtime.

Прогресс:

- phase;
- N/total;
- current file;
- ETA;
- failures;
- logs;
- cancel;
- retry failed only.

---

# 8. Главная страница «Таймлайн»

## Назначение

Главный инструмент анализа всей хронологии.

## 8.1. Верхнее меню timeline

### «Ракурс»

- 9 pose bins;
- count;
- median quality;
- calibration support;
- limited badge;
- один active bin;
- multi-pose comparison включается отдельным режимом, не default.

### «Метрики»

Группы:

- pose;
- quality;
- landmarks;
- descriptors;
- mesh;
- chronology;
- texture diagnostics;
- provenance;
- calibration.

Для каждой metric:

- checkbox;
- цвет/shape;
- unit;
- coordinate space;
- availability count;
- calibrated/diagnostic badge;
- drag order;
- solo/hide.

### «Фильтры»

Описаны в разделе 9.

### «Находки»

- all;
- persistent geometry;
- change points;
- returns;
- rapid-rate;
- same-day conflict;
- provenance;
- quality/calibration limited;
- unreviewed/reviewed;
- cross-bin support.

Показывает count и позволяет перейти по находкам.

### «Сравнение»

- включить A/B mode;
- очистить A/B;
- открыть Pair Analysis;
- открыть Morphing;
- выбрать reference period;
- batch compare selected range.

### «Вид»

Presets:

- Clean timeline;
- Findings;
- Quality/provenance;
- Geometry;
- Texture diagnostics;
- Calibration support;
- Presentation;
- Custom saved view.

### «Поиск»

Поиск по:

- photo ID;
- filename;
- date;
- source;
- flag;
- pair ID;
- reviewer tag.

## 8.2. Вертикальные слои timeline

Сверху вниз:

1. **Pose track:** yaw/pitch/roll.
2. **Quality track:** quality, visibility, resolution, reconstruction state.
3. **Geometry tracks:** LDM106/134, mesh, descriptors.
4. **Chronology tracks:** rate, drift, return support.
5. **Texture diagnostic tracks:** только applicable values.
6. **Photo row:** немного ниже центра.
7. **Photo markers:** quality ring, provenance, expression, visibility, exclusion.
8. **Pair/event row:** change, return, rapid, A/B bridges.
9. **Coverage/era row.**
10. **Density navigator.**
11. **Year/month ruler внизу.**

## 8.3. Photo row

Thumbnail содержит только изображение и короткие A/B/review badges.

Состояния:

- normal;
- hover;
- selected;
- A;
- B;
- excluded;
- limited;
- failed image;
- unreviewed candidate;
- reviewed.

Photo не смещается по X для устранения collision. Решения:

- vertical micro-lanes;
- aggregation;
- density;
- zoom-dependent representative thumbnails.

## 8.4. Hover crosshair

При hover:

- единая вертикальная линия через все tracks;
- metric values в компактном tooltip;
- date/pose/quality/provenance;
- nearest pair events;
- quick actions.

## 8.5. Rich tooltip

Содержит:

- thumbnail;
- date/photo ID;
- yaw/pitch/roll;
- quality/visibility;
- provenance status;
- expression flags;
- 2–3 приоритетные находки;
- открыть Inspector;
- назначить A/B;
- exclude/include в profile;
- copy permalink.

## 8.6. Zoom/pan

- wheel — cursor-anchored zoom;
- Shift+wheel/trackpad — pan;
- middle drag/Space drag — hand tool;
- brush — увеличить selected period;
- Fit — весь период;
- кнопки decade/era/event;
- keyboard `+/-`, arrows;
- URL сохраняет range.

## 8.7. A/B на timeline

- первый клик в A/B mode → A;
- второй → B;
- цветные pins;
- bridge A→B;
- compact pair preview;
- недопустимая пара сразу показывает причину;
- кнопки Pair Analysis/Morphing;
- history последних пар;
- swap A/B.

## 8.8. Findings mode

- обычные фото остаются видимыми, но менее контрастными;
- candidates — shape + icon + color;
- interval candidates — bands;
- return — arrow/arc к baseline;
- dense zone — hatched band;
- click открывает evidence card;
- никакой надписи «доказано».

## 8.9. Multi-pose mode

Включается явно:

- 2–9 компактных pose lanes;
- общий temporal viewport;
- одна photo row на pose;
- independent metrics;
- cross-bin event alignment;
- нельзя рисовать одну линию score через разные bins;
- cross-bin support отображается event marker, а не объединённой raw metric.

## 8.10. Timeline export

- screenshot текущего viewport;
- SVG/PNG chart layer;
- CSV visible data;
- JSON view state;
- permalink;
- publication figure request с claim ID;
- watermark run/schema/not-a-verdict.

---

# 9. Live filters и Analysis Profiles

## 9.1. Два режима фильтра

### View filter

- мгновенно меняет только отображение;
- не создаёт новый scientific result;
- помечен `view-only`;
- сохраняется как UI preset.

### Analysis profile filter

- изменяет selection для будущего run;
- versioned;
- preview before apply;
- journal diff;
- freeze/lock;
- создаёт selection manifest.

## 9.2. Photo-level filters

- date/era;
- pose bins;
- quality score/status;
- face resolution;
- blur/sharpness;
- exposure;
- occlusion;
- visible landmarks;
- reconstruction residual;
- alignment/reliability;
- texture applicability;
- expression magnitude;
- smile;
- jaw open;
- provenance conflict;
- missing source chain;
- exact/near duplicate;
- Stage 1 status;
- manual tags/status.

## 9.3. Pose outlier controls

- percentile/MAD method;
- yaw/pitch/roll limits;
- per-bin distribution;
- number included/excluded;
- «почему исключено» для каждого фото;
- calibration/reference policy.

## 9.4. Live histogram

Для каждого threshold:

- distribution;
- current cut;
- before/after count;
- affected dates;
- affected pose bins;
- candidate loss/gain;
- warning о слишком малом N.

## 9.5. Filter chain inspector

Для исключённого фото:

```text
quality 0.31 < 0.50
pose MAD 4.2 > 3.5
smile_detected=true
near_duplicate_of=...
```

Каждая причина ведёт к управляющему control.

## 9.6. Profile management

- create;
- clone;
- rename;
- compare;
- lock;
- freeze;
- import/export;
- restore automatic;
- manual include/exclude;
- notes/reason code;
- estimate pair count/runtime;
- start Stage 2;
- profile/run compatibility warning.

---

# 10. Страница «Инспектор фотографии»

## Назначение

Проверить один Stage 1 result без огромных JSON-таблиц.

## 10.1. Header

- photo ID/date;
- pose bin + angles;
- Stage 1/validation status;
- quality/provenance badges;
- previous/next photo в active pose/range;
- assign A/B;
- open source;
- copy permalink.

## 10.2. Main split view

### Левая область

Переключатели:

- original;
- face crop;
- face mask;
- zones overlay;
- LDM overlay;
- visibility overlay.

Controls:

- zoom/pan;
- opacity;
- before/after;
- pixel coordinates;
- screenshot.

### Правая область: 3D panel

Tabs/layers:

- mesh only;
- texture only;
- mesh + texture;
- wireframe;
- LDM106;
- LDM134;
- visibility;
- zones;
- neutral/original expression.

Controls:

- orbit;
- zoom;
- reset canonical camera;
- light intensity/direction;
- background;
- screenshot/GLB export при разрешении.

## 10.3. Compact facts

Без больших таблиц:

- pose;
- image dimensions;
- face area;
- reprojection;
- visible counts;
- quality status;
- expression flags;
- artifact completeness;
- source/date state.

## 10.4. Tabs

### Summary

Главные факты и limitations.

### Geometry

- coordinate spaces;
- LDM counts;
- alpha diagnostics;
- mesh availability;
- no identity verdict.

### Texture

- texture.json summary;
- quality/applicability;
- FFT/LBP/albedo/specular diagnostics, если реально извлечены;
- original-pixel source;
- unavailable states.

### Provenance

Полная source chain, hashes, duplicates, rights.

### Artifacts

Allowlisted files, schema, size, digest, download.

### Raw/Advanced

JSON tree только как advanced view.

## 10.5. Manual QA

- approve;
- reject reconstruction;
- needs recrop;
- wrong face;
- invalid source/date;
- comment;
- reviewer identity;
- create issue;
- no silent mutation Stage 1.

---

# 11. Страница «Pair Analysis»

## Назначение

Выбрать A/B внутри pose bin, быстро просмотреть большой ряд и подробно проверить сходство/различие.

## 11.1. Pair header

- A/B IDs/dates;
- pose bin;
- run/profile;
- applicability status;
- swap;
- reset;
- permalink;
- add note/tag;
- submit review.

## 11.2. Range selector

- full 1999–2026;
- draggable handles;
- brush zoom;
- era presets;
- only current pose;
- count in range;
- candidate markers;
- reference-period selector.

## 11.3. Four-row thumbnail browser

- virtualized;
- default ~40×40;
- size slider;
- 1–6 rows;
- chronological order;
- A/B pins;
- quality/exclusion overlay;
- filter by status/source/era;
- keyboard movement;
- quick preview.

После выбора A:

- все thumbnails получают A-relative tint;
- green/amber/red дублируется числом/shape;
- metric selector указывает источник similarity;
- unknown/inapplicable остаётся серым/штрихованным;
- нельзя называть tint identity probability.

## 11.4. Main A/B canvas

Режимы:

- side-by-side;
- overlay;
- blink;
- split slider;
- landmarks;
- vectors;
- zone heatmap;
- difference image diagnostic.

## 11.5. Applicability card

До метрик:

- same bin;
- yaw/pitch/roll gaps и limits;
- common LDM106/134;
- calibration coverage;
- quality;
- expression;
- provenance;
- duplicates;
- coordinate space;
- accepted/limited/excluded reason.

## 11.6. Metrics panel

Группы:

- primary landmarks;
- identity-only;
- mesh;
- local descriptors;
- chronology;
- texture diagnostics;
- quality/provenance.

Каждая metric:

- A/B/raw difference;
- calibrated reference;
- z/p/q при наличии;
- unit;
- support count;
- status;
- tooltip method;
- evidence link.

## 11.7. Landmark settings

На этой же странице:

- LDM106/134;
- raw/other display space;
- vectors;
- point numbers;
- region selection;
- diagnostic/calibrated thresholds;
- gradient;
- point size/opacity;
- excluded points;
- calibration p95.

## 11.8. Zone panel

- anatomical/coordinate zone name и contract;
- visible/excluded;
- weight;
- point count;
- residual summary;
- expression sensitivity;
- calibration support;
- click highlights zone on both faces/3D.

## 11.9. Early-reference comparison

Для A/B подбираются reference photos раннего периода:

- same pose;
- closest angles;
- adequate quality;
- provenance;
- configurable reference period;
- compare `A→reference` и `B→reference`;
- не делать identity conclusion автоматически;
- показывать selection rationale.

## 11.10. Reviewer workspace

- observation;
- confidence;
- alternatives checked;
- approve candidate/limited/inconclusive;
- request recrop/source check;
- second reviewer;
- adjudication;
- export pair card.

---

# 12. Страница «Morphing / 3D chronology»

## Назначение

Ручное исследование изменения сохранённых 3D-моделей и текстур во времени.

## 12.1. Header

- pose bin;
- active range;
- anchor count;
- current interpolated date/segment;
- visualization-only;
- layers;
- camera preset;
- export.

## 12.2. Main 3D canvas

- занимает максимальную площадь;
- GPU WebGL2/Three.js;
- A/B positions в buffers;
- shader interpolation;
- texture blending;
- per-vertex heatmap;
- landmarks/zones;
- context-loss recovery.

## 12.3. Layer popover

Независимые checkboxes:

- mesh;
- texture;
- wireframe;
- heatmap;
- LDM106;
- LDM134;
- vectors;
- visible only;
- excluded expression zones;
- neutral/original expression;
- A/B split.

## 12.4. Heatmap settings overlay

Прямо над моделью:

- max reference;
- color stops;
- positions;
- sharpness;
- calibrated/diagnostic source;
- linear/log scale;
- clamp;
- reset;
- save display preset;
- no mutation scientific result.

## 12.5. Light/texture settings

- A/B lighting transition;
- brightness/contrast только display;
- texture opacity;
- albedo/raw texture selection;
- provenance of texture;
- warning, если сравниваются разные photometric conditions.

## 12.6. Temporal scrubber

Главный control:

- ручной horizontal slider;
- real photo anchors;
- current segment A→B;
- snap to real photo;
- slow movement with pointer precision;
- keyboard frame/anchor step;
- play — маленькая secondary button;
- speed/loop optional.

## 12.7. Range zoom

- full range;
- brush period;
- click anomaly → zoom вокруг него;
- history/back;
- 1999–2026 → 2009–2012 без смены страницы;
- anchor density adjusts automatically.

## 12.8. Anchor sequence

- chronological miniatures;
- quality/provenance state;
- excluded anchors visible but not interpolated;
- manual include/display-only;
- reason for anchor selection;
- max anchors/LOD.

## 12.9. Export

- PNG current frame;
- side-by-side A/B;
- 10-second loop/video;
- GLB visualization;
- heatmap legend;
- metadata/claim ID/run;
- no interpolated frame exported as measurement.

---

# 13. Страница «Кластеризация»

## Назначение

Исследовать повторяющиеся технические состояния и временные границы, не называя clusters личностями.

## 13.1. Run controls

- source run/profile;
- pose: one/all;
- feature family;
- coordinate space;
- normalization;
- algorithm;
- params;
- random seed;
- exclusions;
- recompute;
- save clustering run.

## 13.2. Основной режим «Хронология»

- cluster lanes C1…Cn;
- photo points по реальной дате;
- membership opacity/shape;
- outliers;
- transition lines;
- regime bands;
- boundary confidence;
- review markers;
- pose lanes independent;
- zoom/pan/range.

## 13.3. Boundary detector

Controls:

- persistence window;
- minimum support;
- membership threshold;
- transition confidence;
- cross-pose agreement;
- merge gap;
- sensitivity preview.

Registry:

- boundary ID;
- date/period;
- from/to clusters;
- support photos/poses/sources;
- stability;
- alternatives;
- review state;
- open pair analysis.

## 13.4. Embedding mode

- UMAP/other projection;
- axes marked as projection, not physical metric;
- seed/params;
- hull optional;
- density;
- outliers;
- lasso selection;
- cluster inspector;
- reference-period comparison.

## 13.5. Cloud mode

Только presentation/exploration:

- optional bubble layout;
- size semantics explicitly stated;
- no use for boundary calculation;
- minimap;
- click to inspect;
- `не временная шкала` badge.

## 13.6. Sensitivity/stability

- compare parameter runs;
- ARI/stability;
- membership changes;
- boundary shifts;
- consensus clusters;
- unstable records;
- export sensitivity table.

## 13.7. Cluster inspector

- members;
- chronology;
- pose/source/quality distribution;
- medoid/reference;
- outliers;
- early-period similarity;
- compare two members;
- notes;
- no identity name field.

## 13.8. Обязательная маркировка

```text
КЛАСТЕР — ТЕХНИЧЕСКАЯ ГРУППА СХОЖИХ ИЗМЕРЕНИЙ, НЕ ИДЕНТИФИКАЦИЯ ЛИЧНОСТИ
```

---

# 14. Страница «Валидация гипотез»

## Назначение

Private-only проверка ранее собранных гипотез на новых данных, не влияющая на blind Stage 2/public Stage 3.

## 14.1. Isolation header

- PRIVATE;
- read-only legacy source;
- current run;
- hypothesis schema;
- isolation state;
- no public export;
- audit identity;
- blind labels option.

## 14.2. Entity blocks

Если private contract определяет три сущности:

- entity 1;
- entity 2;
- entity 3;
- periods;
- hypothesis count;
- current coverage;
- private aliases;
- no automatic identity assignment.

## 14.3. Pairwise groups

- 1↔2;
- 1↔3;
- 2↔3;
- entity-specific hypotheses;
- all/geometry/texture/chronology/provenance filters;
- pose filter;
- period filter;
- status filter.

## 14.4. 90+ hypothesis tiles

Tile показывает:

- hypothesis ID;
- short label;
- feature/zone;
- legacy expected range;
- current range;
- migration profile;
- pose applicability;
- coverage N/M;
- supported/contradicted/inconclusive/not-applicable/pending;
- uncertainty;
- source reference;
- reviewer status.

Color — secondary; status всегда текстом/shape.

## 14.5. Tile details

- full original wording;
- source document;
- legacy coordinate space;
- old landmark indices;
- current mapping;
- calibration correction;
- matched photos/pairs;
- distribution plot;
- sensitivity;
- alternatives;
- notes/audit.

## 14.6. Systematic shift laboratory

- global offset — sensitivity only;
- per-pose offset;
- per-feature offset;
- range width;
- uncertainty;
- before/after agreement;
- holdout result;
- changed tile count;
- preview only;
- save immutable calibration profile;
- apply scope;
- reset;
- audit event.

Нельзя оптимизировать profile только ради максимального agreement.

## 14.7. Agreement curve

- x: shift/scale;
- y: supported/contradicted/inconclusive;
- separate train/holdout;
- per-pose curves;
- selected profile;
- confidence band;
- legacy/current reference.

## 14.8. Private review/export

- internal JSON/CSV/PDF;
- no public report action;
- redacted screenshot;
- reviewer notes;
- second reviewer;
- audit log;
- explicit private watermark.

---

# 15. Страница «Калибровка»

## Назначение

Показать, насколько надёжно система оценивает собственный шум и где calibration insufficient.

## 15.1. Health summary

- persons;
- photos;
- 9 bins;
- complete/low/medium/high/invalid references;
- active release;
- LOPO status;
- contamination status;
- negative control;
- release signature/version.

## 15.2. Coverage matrix

```text
person × pose bin
```

Показывает:

- frame count;
- usable pairs;
- quality strata;
- angle coverage;
- missing cell;
- click to inspect.

## 15.3. Pose distributions

- yaw/pitch/roll histograms;
- current gate;
- supported angle span;
- overlap with main dataset;
- missing priority.

## 15.4. Noise distributions

Для metric/pose:

- median;
- MAD;
- p95/p99;
- effective N;
- per-person summaries;
- matched references;
- outliers;
- release threshold.

## 15.5. LOPO/sensitivity

- fold table;
- threshold variation;
- unstable bins/metrics;
- person dependence;
- holdout performance;
- warning/block release.

## 15.6. Contamination

- simulated contamination fraction;
- threshold shift;
- false positive/negative sensitivity;
- lower-tail policy;
- release gate.

## 15.7. Pair matching explorer

Для main pair:

- selected calibration pairs;
- angle distances;
- quality/expression match;
- replace candidate;
- rationale;
- raw vs adjusted diagnostics;
- no silent subtraction.

## 15.8. Add calibration data

- upload;
- subject/person ID;
- consent/rights;
- pose target;
- quality preview;
- duplicate angle warning;
- Stage 1 queue;
- proposed bin;
- release inclusion only after validation.

## 15.9. Calibration release

- draft;
- validate;
- compare previous;
- freeze;
- sign/version;
- activate;
- rollback;
- impact preview on runs/profiles;
- automatic recompute optional but confirmable.

---

# 16. Страница «Analysis Profiles»

## Назначение

Версионировать выбор фото и правила применимости до запуска Stage 2.

## 16.1. Profile list

- name/version;
- draft/frozen/locked;
- included/excluded counts;
- filters fingerprint;
- author/date;
- dependent runs;
- clone/diff/export.

## 16.2. Profile editor

- contextual filters;
- manual curation;
- reason codes;
- comments;
- status map;
- undo view changes;
- journal;
- no Stage 1 mutation.

## 16.3. Preview

- photo count;
- per-pose count;
- adjacent/baseline/rolling pair estimate;
- calibration pair estimate;
- expected runtime;
- blockers;
- warnings;
- active filters;
- candidate retention impact;
- confirmation.

## 16.4. Freeze/start

- freeze manifest;
- digest;
- lock;
- Stage 2 preflight;
- start run;
- open progress;
- new run never overwrites old run.

---

# 17. Страница «Прогоны»

## Назначение

Управлять Stage 2/2B/3 jobs, не смешивая результаты разных конфигураций.

## 17.1. Run list

Колонки:

- run ID;
- profile;
- calibration release;
- status;
- phases;
- records/pairs;
- start/duration;
- valid;
- reports;
- archived;
- actions.

## 17.2. Preflight form

- profile;
- calibration;
- min points;
- output root;
- expected hashes/versions;
- pair estimate;
- disk/memory estimate;
- blockers;
- confirmation.

## 17.3. Progress

Phases:

- load/validate;
- calibration models;
- pair planning;
- geometry;
- mesh;
- texture diagnostics;
- chronology;
- FDR;
- evidence;
- postprocess;
- validation;
- drafts/reports.

Для каждой:

- status;
- N/total;
- ETA;
- logs;
- degraded state;
- cancel.

## 17.4. Run detail

- config/profile snapshot;
- manifest;
- hashes;
- counts;
- skipped reasons;
- degraded modules;
- artifacts;
- validation;
- findings summary;
- open timeline;
- generate Stage 3;
- start private Stage 2B.

## 17.5. Run diff

Сравнивает:

- config;
- selection;
- calibration;
- pair count;
- status transitions;
- candidate added/removed;
- metric shift;
- boundary shift;
- publication claim changes.

## 17.6. Lifecycle actions

- cancel;
- retry as new run;
- archive;
- restore;
- delete failed/cancelled only;
- regenerate report without Stage 2;
- no overwrite complete run.

---

# 18. Страница «Review Queue»

## Назначение

Провести human review до сильной интерпретации/публикации.

## 18.1. Queue filters

- priority;
- evidence state;
- pose;
- period;
- quality/calibration limitation;
- provenance;
- unreviewed/reviewer disagreement;
- publication claim dependency.

## 18.2. Review card

- A/B images;
- pair applicability;
- main measurements;
- calibration;
- provenance;
- alternatives checklist;
- independent bins/sources;
- related events;
- raw overlay/3D link;
- claim IDs.

## 18.3. Blind review

- random masked IDs;
- no dates/context;
- fixed observation form;
- cannot reveal until save;
- reveal key after session;
- separate label map;
- audit.

## 18.4. Decision

- within expected variation;
- candidate supported for further review;
- limited/inconclusive;
- reject reconstruction/source;
- request more data;
- confidence;
- comment;
- alternatives checked;
- reviewer signature/date.

## 18.5. Adjudication

- reviewer A/B decisions;
- disagreement;
- shared evidence;
- adjudicator decision;
- rationale;
- immutable history;
- claim publication gate update.

---

# 19. Страница «Отчёты»

## Назначение

Просматривать Stage 3 artifacts и генерировать technical/internal/public representations.

## 19.1. Report list

- report ID;
- run;
- mode;
- language;
- created;
- validation;
- pair/change counts;
- lint;
- publication readiness;
- exports.

## 19.2. Report viewer

Sections:

- summary;
- methodology;
- provenance;
- calibration;
- chronology;
- change candidates;
- motion maps;
- pairs;
- exclusions;
- limitations;
- review state;
- claims;
- drafts.

## 19.3. Report modes

### Technical

Полные measurement details.

### Internal

Evidence/review/notes, private team only.

### Public

Observation-based projection, no private hypotheses, claim/public lint.

## 19.4. Export

- JSON;
- CSV;
- HTML;
- PDF/print;
- image package;
- evidence bundle;
- machine packet;
- signed manifest;
- public watermark/version.

---

# 20. Страница «Публикации»

## Назначение

Совместная работа журналиста, технического редактора, fact-checker и AI reviewer.

## 20.1. Publication readiness header

- Stage 3 validation;
- claims count;
- unreviewed claims;
- provenance blockers;
- rights blockers;
- technical review;
- skeptic review;
- public lint;
- translation status;
- figure status;
- ready/not ready.

## 20.2. Draft tabs

- Public Method Explainer;
- Technical Appendix;
- Results Story;
- Skeptic Q&A;
- Demonstration Protocol;
- Claims Ledger;
- Machine Review;
- Glossary;
- Rights/Figures.

## 20.3. Split editor

Левая часть:

- Markdown/editorial text.

Правая часть:

- selected claim;
- technical wording;
- evidence refs;
- denominator;
- limitations;
- review state;
- source artifact preview.

Редактирование public wording не меняет technical claim.

## 20.4. Journalist voice controls

Шаблон ролей:

- `мы собрали/проверили` — редакция;
- `система измерила` — автоматическое;
- `специалист проверил` — technical;
- `мы интерпретируем` — журналистская версия;
- `reviewer согласился/оспорил` — independent review.

Lint блокирует смешение ролей и overclaim.

## 20.5. Claims ledger

Таблица:

- claim ID;
- section;
- plain wording;
- technical wording;
- allowed strength;
- evidence refs;
- denominator;
- limitations;
- reviewer;
- adjudication;
- translation;
- figures;
- public status.

## 20.6. Skeptic panel

Для каждого claim:

- strongest objection;
- alternative explanation;
- required falsification test;
- evidence available/missing;
- response;
- unresolved flag.

## 20.7. AI-review

- export machine packet;
- paste/import AI objections;
- objections mapped to claim IDs;
- accepted/rejected/needs evidence;
- no auto-approval;
- model/version/prompt logged;
- AI is not independent forensic reviewer.

## 20.8. Translation

- Russian source claim;
- English synchronized wording;
- same claim ID;
- terminology glossary;
- meaning-diff checker;
- translation reviewer;
- no independent editing that strengthens claim.

## 20.9. Figures/storyboards

Figure manifest:

- figure ID;
- claim IDs;
- source photos/artifacts;
- caption RU/EN;
- alt text;
- crop/overlay settings;
- run/schema;
- rights status;
- draft/final;
- regenerate.

Виды:

- pipeline diagram;
- nine-pose diagram;
- calibration/noise example;
- timeline overview;
- pair card;
- limitation/exclusion example;
- provenance chain;
- sensitivity chart.

## 20.10. Rights gate

Для каждого image/figure:

- source URL;
- publisher;
- rights/license;
- transformation;
- publication territory;
- credit;
- approved/restricted/unknown;
- legal reviewer;
- block public export if unresolved.

## 20.11. Publication lint

Проверяет:

- unsupported assertive language;
- candidate→fact drift;
- missing denominator;
- missing evidence;
- unresolved review;
- private field leak;
- translation meaning drift;
- missing rights;
- broken links;
- missing alt text;
- version mismatch.

## 20.12. Final publish package

- article Markdown/HTML;
- technical appendix;
- skeptic Q&A;
- figures;
- claims ledger;
- machine packet;
- source manifest;
- public data exports;
- lint/review reports;
- digest/signature.

---

# 21. Страница «Демонстрации метода»

## Назначение

Публикационный цикл примеров, независимый от результатов расследования.

## 21.1. Demonstration datasets

- consenting participant;
- licensed public-figure same-person set;
- synthetic scenarios;
- negative controls;
- separate manifests;
- no threshold tuning on investigation result.

## 21.2. Scenario builder

Сценарии:

- same person, close pose;
- pose mismatch;
- smile/jaw;
- quality/compression;
- duplicate frames;
- A-B-A return;
- gradual drift;
- blind review;
- known different-person negative/positive control при lawful dataset.

## 21.3. Expected result

До запуска фиксируются:

- hypothesis;
- expected status;
- metrics;
- acceptance;
- failure interpretation.

## 21.4. Result card

- images;
- conditions;
- metrics;
- calibration;
- expected/actual;
- explanation;
- artifact links;
- publication figure.

## 21.5. Public figure restriction

Известный человек используется только для объяснения работы метода. Запрещены выводы о его здоровье, идентичности или внешних средствах. Требуются rights/provenance.

---

# 22. Recommendations overlay

## Назначение

Показывать следующие действия, не выполняя их автоматически.

Карточка:

- priority;
- type;
- short title;
- reason;
- source artifacts;
- expected impact;
- action;
- dismiss/snooze;
- reviewed;
- settings.

Типы:

- weak calibration;
- missing pose coverage;
- low-quality dense zone;
- no Stage 2/report;
- invalid run;
- profile changed;
- provenance conflict;
- unreviewed candidates;
- publication blockers;
- system health;
- integrity warning.

Клик ведёт в конкретный раздел/фильтр/range.

---

# 23. Audit и журнал

## 23.1. Event log

События:

- ingest;
- profile change;
- threshold/profile save;
- run start/cancel/complete;
- review/adjudication;
- private hypothesis calibration;
- report/draft generation;
- export;
- delete/archive;
- auth/security;
- AI review import.

## 23.2. Filters

- actor;
- date;
- entity;
- action;
- run/profile;
- severity;
- public/private;
- success/failure.

## 23.3. Diff

Показывает before/after для:

- settings;
- profile;
- calibration release;
- hypothesis sensitivity;
- claim wording;
- review decision.

## 23.4. Stage 1 integrity

- baseline snapshot;
- current digest;
- unchanged/changed;
- affected runs;
- block release on mismatch.

---

# 24. System Health

## 24.1. Backend

- API;
- Python version;
- dependencies;
- model files;
- Stage roots;
- calibration;
- disk;
- queue;
- errors.

## 24.2. Compute

На MacBook M1 отдельно:

- Stage 1 CPU policy;
- unified memory;
- load;
- free disk;
- temperature unavailable/available честно;
- no fake CUDA VRAM.

## 24.3. Browser GPU

- WebGL2 available;
- renderer/vendor when permitted;
- max texture size;
- context state;
- software fallback warning;
- morph benchmark;
- WebGPU optional state.

## 24.4. Storage

- Stage 1 immutable root;
- Stage 2/3 space;
- cache size;
- thumbnails;
- cleanup preview;
- never delete source photos by generic clear action.

---

# 25. Global Settings

Глобальная Settings page содержит только общие параметры.

## 25.1. Appearance

- dark/light/system;
- density;
- font size;
- thumbnail default;
- color-safe palette;
- reduced motion;
- high contrast.

## 25.2. Language

- RU/EN;
- terminology glossary;
- date/number formatting;
- fallback/missing translation report.

## 25.3. Workspace

- saved layouts;
- default route;
- default pose;
- open overlays;
- keyboard map;
- reset UI preferences.

## 25.4. API/storage

- API base;
- timeout;
- cache policy;
- SSE fallback;
- local paths — admin only;
- connectivity test.

## 25.5. Security

- session;
- role;
- local-only/network mode;
- audit identity;
- auto-lock;
- clipboard/export restrictions.

## 25.6. Не размещать здесь

Не размещать глобально controls, влияющие только на:

- timeline filters;
- landmark threshold;
- morph heatmap;
- cluster parameters;
- hypothesis shift;
- calibration release.

Они остаются на соответствующих страницах.

---

# 26. Shared components

## 26.1. StatusBadge

Типизированные состояния, icon + text + color.

## 26.2. MetricValue

- value/unit;
- null state;
- precision;
- calibration badge;
- source tooltip.

## 26.3. EvidenceLink

Открывает artifact/row/claim с сохранением context.

## 26.4. ApplicabilityBanner

Accepted/limited/excluded с причинами.

## 26.5. RangeBrush

Единый component для timeline/pair/morph/clustering.

## 26.6. PhotoThumbnail

Virtualized, lazy, A/B/review/quality states.

## 26.7. PairCard

A/B + applicability + key metrics + actions.

## 26.8. ContextPanel

Radix popover/dropdown, pin/unpin, keyboard/focus, overlay.

## 26.9. Empty/Error/Blocked State

Каждое состояние содержит:

- что произошло;
- чего не хватает;
- безопасное действие;
- details/log;
- retry.

## 26.10. ExportDialog

- format;
- scope;
- public/internal;
- watermark;
- claims/run;
- rights/lint;
- preview;
- confirm.

---

# 27. API contracts, необходимые UI

## Foundation

- health;
- runtime paths;
- OpenAPI version;
- capabilities;
- user/role;
- audit events.

## Data

- dataset inventory;
- photos pagination;
- photo detail/artifacts/images/landmarks/mesh;
- upload/sidecar validation;
- issues/duplicates/provenance;
- safe mutations.

## Timeline

- viewport/range query;
- findings;
- density/aggregation;
- metrics catalog;
- eras;
- filter evaluation;
- permalink state.

## Pair/Morph

- pair metrics;
- full comparison;
- batch A-relative metrics;
- landmarks;
- binary mesh A/B/diff;
- calibration matches.

## Profiles/Runs

- profile CRUD/freeze/diff/status;
- run preflight/start/progress/cancel/retry/archive;
- artifacts;
- run diff.

## Clustering

- create/list/get run;
- records/transitions/boundaries;
- sensitivity;
- members;
- export.

## Hypotheses

- private auth boundary;
- entities/families/tiles;
- migration profiles;
- sensitivity preview/save;
- review/export private.

## Reports/Publications

- reports;
- sections;
- drafts manifest/files;
- claim update/review;
- lint;
- translation;
- figure/rights manifests;
- publish package.

Все responses:

- versioned schema;
- explicit source mode;
- null semantics;
- not-a-verdict где применимо;
- pagination/offset или viewport;
- error/limited state;
- no synthetic fallback.

---

# 28. Performance requirements

## Timeline

- 1900 photos;
- only viewport + overscan thumbnails в DOM;
- Canvas metrics/events;
- Worker LOD;
- cursor zoom без long task;
- target 60 fps, minimum 30 fps на M1.

## 3D

- BFM topology cached once;
- binary arrays;
- GPU interpolation;
- no React per-vertex state;
- target 60 fps scrub;
- context-loss recovery;
- memory budget measurement.

## Tables

- virtualized rows;
- server pagination where needed;
- no 6000-row normal DOM map.

## Network

- cancellation;
- gzip/binary;
- query deduplication;
- cache by run/schema;
- lazy heavy artifacts;
- SSE jobs.

---

# 29. Accessibility

Обязательно:

- full keyboard workflow;
- visible focus;
- semantic controls;
- dialogs focus trap/return;
- icon aria-label;
- color + shape + text;
- contrast;
- 200% browser zoom;
- reduced motion;
- Canvas/WebGL accessible summary;
- table alternative;
- captions/alt text figures;
- screen reader announcements jobs/errors.

---

# 30. Security и privacy

## Local default

- bind localhost;
- no public write API;
- private hypotheses isolated;
- source paths hidden from public output.

## Network deployment

- authentication;
- RBAC;
- strict CORS;
- CSRF;
- rate limits;
- upload validation;
- path containment;
- session/audit;
- encrypted transport;
- public read-only API separately.

## Roles

- viewer;
- reviewer;
- analyst;
- editor;
- admin.

## Publication

- rights gate;
- private-field lint;
- no on-chain raw biometrics/photos by default;
- proof-of-existence через hashes/manifests/signatures;
- off-chain controlled storage.

---

# 31. Testing

## Unit

- temporal transform;
- filters;
- state reducers;
- format/null;
- shader data prep;
- claim rendering.

## Contract

- OpenAPI/types;
- success/missing/invalid/limited;
- version compatibility;
- private/public isolation.

## Component

- panels/forms/tables;
- keyboard/focus;
- empty/error/loading;
- threshold live updates.

## E2E

- ingest → Stage 1 job;
- profile → Stage 2;
- timeline zoom/filter/A-B;
- pair analysis;
- morph range/scrub;
- clustering boundary;
- hypothesis private review;
- Stage 3 drafts;
- claims/lint/export;
- audit.

## Visual regression

- all primary routes;
- overlays;
- 1024/1440/4K;
- dark/light;
- RU/EN;
- high contrast;
- no-data/error.

## Accessibility

- axe;
- keyboard script;
- screen reader smoke;
- color blindness snapshots.

## Performance

- 1900-photo fixture;
- large pair grid;
- 35k vertex morph;
- clustering 1900 points;
- 6000 hypothesis records;
- memory leak/context loss;
- M1 Chrome/Safari benchmark.

---

# 32. План реализации от 0 до 100%

## Фаза 0 — Контракты и подготовка, 0–8%

- зафиксировать OpenAPI snapshot;
- убрать backend duplication;
- определить entity schemas;
- создать UI package/lock/scripts;
- design tokens;
- routing/state/query providers;
- error boundary;
- test harness;
- Storybook/Playwright.

**Gate:** clean install, lint/typecheck/test/build.

## Фаза 1 — Shell и API foundation, 8–16%

- top shell;
- bottom status bar;
- route map;
- command palette;
- pipeline chips;
- global error/loading;
- API client;
- i18n/theme/accessibility base;
- capabilities/health.

**Gate:** navigation, URL state, no mock production fallback.

## Фаза 2 — Data/provenance/ingest, 16–27%

- inventory;
- upload;
- filename/date validation;
- sidecar editor;
- duplicate handling;
- data table/detail drawer;
- extraction jobs;
- integrity state.

**Gate:** каждый input учтён; destructive preview; audit.

## Фаза 3 — Timeline core, 27–43%

- temporal viewport;
- Canvas renderer;
- virtual thumbnails;
- photo/metric/event/interval layers;
- zoom/pan/brush;
- pose/metrics panels;
- tooltip/crosshair;
- findings mode;
- multi-pose mode;
- exports.

**Gate:** one photo = one X; 1900-photo performance.

## Фаза 4 — Filters/profiles/photo inspector, 43–54%

- live filters;
- filter chain;
- profile CRUD/freeze/diff;
- inspector image/3D/tabs;
- manual QA;
- provenance/artifacts.

**Gate:** view filter не меняет evidence; profile versioned.

## Фаза 5 — Pair Analysis, 54–64%

- range brush;
- 4-row virtual browser;
- A-relative tint;
- A/B canvas;
- applicability;
- metrics/zones/landmarks;
- reference-period comparison;
- reviewer notes.

**Gate:** all pair values source-backed; invalid pair explained.

## Фаза 6 — Morphing, 64–71%

- Three.js/R3F;
- binary mesh;
- GPU shader interpolation;
- layer combinations;
- heat/light overlay;
- temporal scrub/range zoom;
- export.

**Gate:** M1 60/30 fps targets; visualization-only invariant.

## Фаза 7 — Calibration/runs/review, 71–81%

- health/coverage;
- noise/LOPO/contamination;
- pair matching;
- release workflow;
- run preflight/progress/diff/lifecycle;
- blind review/adjudication.

**Gate:** frozen calibration/profile/run trace; reviewers auditable.

## Фаза 8 — Clustering/hypotheses, 81–89%

- backend clustering contracts;
- chronology/embedding/sensitivity;
- boundaries/inspector;
- private hypothesis entities/tiles;
- systematic shift lab;
- isolation/audit.

**Gate:** cluster ≠ identity; private data cannot enter public output.

## Фаза 9 — Reports/publications/demonstrations, 89–95%

- report viewer;
- drafts editor;
- claims ledger;
- skeptic/AI review;
- RU/EN sync;
- figures/storyboards;
- rights gate;
- demo scenarios;
- final export package.

**Gate:** publication lint + technical/provenance/legal/editorial review.

## Фаза 10 — Production hardening, 95–100%

- full E2E on owner environment;
- M1 Chrome/Safari benchmark;
- 1900-photo load;
- accessibility audit;
- security review;
- deterministic rerun;
- visual snapshots;
- recovery/backup;
- documentation;
- 25-factor review per module;
- independent reviewer acceptance.

**Gate:** все критерии 100% ниже.

---

# 33. Критерии 100% готовности

## Data

- весь архив учтён;
- provenance conflicts видимы;
- failed/excluded не потеряны;
- 9 bins представлены/limited честно;
- Stage 1 immutable.

## Scientific display

- coordinate spaces точны;
- applicability before score;
- calibration/coverage/uncertainty;
- null ≠ 0;
- candidate ≠ verdict;
- clusters/private hypotheses не повышены до identity facts.

## UX

- все страницы/controls реализованы;
- no permanent timeline sidebars;
- contextual settings;
- keyboard/permalink/undo view;
- errors lead to action;
- RU/EN.

## Performance

- 1900-photo timeline benchmark;
- virtual tables/grids;
- M1 morph benchmark;
- no memory leak;
- context loss recovery.

## Quality

- lint/typecheck/unit/contract/E2E/visual/a11y green;
- OpenAPI snapshot sync;
- no production mocks/random data;
- no broken links;
- clean build from lockfile.

## Security

- local/network modes;
- RBAC;
- write/delete containment;
- upload safety;
- audit;
- private/public separation;
- rights gate.

## Publication

- journalist handoff;
- public/technical/skeptic/machine layers;
- claim evidence refs;
- denominators;
- human reviews;
- translations;
- figures/rights;
- lint pass;
- signed export manifest.

## Release declaration

100% означает:

- код завершён;
- tests завершены;
- real-data validation завершена;
- M1 validation завершена;
- independent review завершён;
- publication/security gates завершены.

Нельзя объявлять интерфейс готовым на основании только красивого рендера, успешного build или synthetic fixture.
