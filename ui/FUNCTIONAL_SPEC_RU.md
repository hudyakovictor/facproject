# React UI — уточнённая функциональная спецификация

## 1. Точный scope

Интерфейс **не предназначен для просмотра основного расследовательского датасета, хронологических отчётов или подготовки публикации**.

У UI только две задачи:

1. **Calibration Studio** — загрузить ваши same-day фотографии, проверить работу зон/ракурсов, подобрать и заморозить конфиги, которые затем используются headless-командой основного анализа.
2. **Face Comparison Lab** — загружать фотографии любых людей для тестового A/B-сравнения геометрии и кожи, включая обязательный интерактивный 3D/UV-морфинг.

Основной датасет 1999–2026 после калибровки обрабатывается существующим `run_main_analysis.py` без UI.

---

## 2. Навигация

- **System Doctor** — готовность Mac, Python, библиотек, renderer и весов.
- **Calibration Studio** — ваши фотографии, зоны, ракурсы, конфиги и calibration profile.
- **Comparison Lab** — тесты фотографий разных людей.
- **Morph Studio** — детальный 3D/UV-морфинг выбранной пары.
- **Runs & Logs** — локальные jobs, ошибки, resume и cache.
- **Settings** — пути, CPU, preview и внешний вид.

Разделы основного датасета, расследовательская timeline, review queue и report builder исключены.

---

## 3. System Doctor

Проверки:

- Apple Silicon/macOS;
- `.venv` и Python;
- PyTorch, OpenCV, scikit-image, Skan, SciPy;
- Cython CPU renderer;
- веса 3DDFA_V3;
- доступное место;
- read/write permissions;
- тестовый decode изображений;
- тестовая реконструкция на одном встроенном/выбранном кадре.

Статусы: ready, warning, blocked. Для ошибки показывается точная команда исправления.

---

## 4. Calibration Studio

### 4.1 Импорт

- выбор папки или drag-and-drop;
- произвольные имена файлов;
- оригиналы read-only;
- exact SHA-256 duplicates;
- perceptual near-duplicates;
- multiple/no-face errors;
- resolution, face span, blur, grain, JPEG и lighting diagnostics.

### 4.2 Pose Board

Матрица 9 ракурсов с количеством usable/limited/rejected фото и покрытием 13 зон. Доступна ручная коррекция pose bin; detected и reviewed pose сохраняются раздельно.

### 4.3 Zone Calibration Workbench

Для каждой связки `pose × anatomical zone`:

- filmstrip исходных фото;
- face crop;
- observed analytical UV;
- confidence/provenance;
- zone mask;
- raw Retinex branch;
- NLM descriptor branch;
- raw/NLM disagreement;
- Hessian scales;
- ridge probability;
- thresholded ridges;
- Skan skeleton и branches;
- source-pixel span;
- noise estimate;
- quality class;
- повторяемость метрик между same-day кадрами.

### 4.4 Параметры конфигурации

UI изменяет только draft profile:

- minimum source span;
- observed coverage;
- maximum noise;
- multiscale sigma set;
- NLM strength limits;
- ridge quantile/MAD multiplier;
- scale persistence;
- raw/NLM consensus;
- minimum branch length;
- orientation tolerance;
- branch matching distance/cost;
- target false-anomaly rate;
- minimum photos/pairs for reliable zone.

Любое изменение вызывает пересчёт preview и показывает diff относительно Recommended. Low-level параметры можно pin/unpin.

### 4.5 Presets

- Recommended;
- Strict;
- Balanced;
- Sensitive.

Macro controls:

- Data cleanliness;
- Low-resolution tolerance;
- Grain tolerance;
- Ridge sensitivity;
- Pose tolerance;
- Temporal stability.

Macro slider раскрывает точный config diff — скрытых изменений нет.

### 4.6 Leak-safe calibration

- pHash clusters;
- calibration/validation/test split;
- near-duplicate cluster нельзя разделить между splits;
- coverage каждого split;
- held-out false-anomaly rate;
- список false-positive pairs;
- unreliable pose-zones;
- рекомендации по недостающим фото.

### 4.7 Freeze & Export

Passed profile можно заморозить. Frozen profile нельзя редактировать; изменения создают новую версию.

Экспорт:

- `calibration_profile.json`;
- `calibration_report.json`;
- `calibration_split.csv`;
- config diff;
- hashes моделей/кода/входа;
- готовая команда `run_main_analysis.py`.

---

## 5. Face Comparison Lab

### 5.1 Тестовая сессия

Пользователь загружает:

- Photo A и Photo B;
- либо несколько фото Person A и Person B;
- произвольные лица и даты;
- опционально существующий calibration profile как baseline измерительного шума.

Это лабораторный pairwise-режим, а не обучение профиля и не identity verdict.

### 5.2 Автоматическая обработка

Для каждого фото:

- face detection;
- 3DDFA reconstruction;
- pose classification;
- identity-only и expression mesh;
- analytical/synthetic UV;
- 13 zone masks;
- skin quality;
- Skan graphs.

При нескольких фото система автоматически предлагает наиболее сопоставимые пары по pose, visibility и quality.

### 5.3 Pair selector

Матрица совместимости A×B:

- pose difference;
- pitch/yaw/roll;
- visible overlap;
- source resolution;
- common usable skin zones;
- geometry comparability;
- skin comparability;
- recommended pair badge.

Несопоставимая пара не блокируется для визуального просмотра, но аналитические показатели маркируются limited.

### 5.4 Геометрическое сравнение

- identity-only geometry как основной режим;
- identity+expression как дополнительный;
- rigid Kabsch alignment без scale;
- опциональный normalized-scale view, отдельно маркированный;
- vertex displacement heatmap;
- global RMSE, median, p95;
- landmark 106/134 deltas;
- региональные различия: лоб, глаза, нос, скулы, челюсть, подбородок;
- asymmetry comparison;
- expression influence;
- synchronized camera and pose presets;
- wireframe overlay;
- difference exaggeration только как visual diagnostic.

### 5.5 Сравнение кожи

Только пересечение observed analytical pixels:

- common zone coverage;
- LBP/GLCM/frequency differences;
- ridge density;
- branch count/length/orientation;
- Skan branch correspondences;
- matched/unmatched graph overlay;
- raw/NLM detector agreement;
- quality mismatch;
- calibration-normalized difference, если profile выбран;
- raw uncalibrated difference всегда доступна отдельно.

Синтетическая UV запрещена для метрик.

### 5.6 Результат теста

Показываются отдельные блоки:

- Geometry similarity/difference;
- Skin texture similarity/difference;
- Skin-line graph similarity/difference;
- Pose/quality limitations;
- Expression influence;
- Measurement uncertainty.

Никакой единый процент «это один человек» не выводится. Допустим только технический composite similarity для навигации, с раскрытием компонентов и предупреждением, что он не является вероятностью личности.

### 5.7 История тестов

- локальные сохранённые sessions;
- A/B thumbnails;
- config/profile version;
- повторный запуск после изменения draft config;
- clone session;
- удаление только производных результатов;
- оригиналы остаются нетронутыми.

---

## 6. Обязательный Morph Studio

### 6.1 Предусловия

Обе реконструкции используют одну BFM topology и одинаковые UV coordinates. Перед морфингом:

1. выбирается identity-only или expression-inclusive mesh;
2. mesh B жёстко выравнивается на A через Kabsch;
3. проверяются vertex/triangle/UV counts;
4. фиксируется единая canonical camera.

При несовместимых topology morph блокируется с явной ошибкой.

### 6.2 Geometry morph

Для `t ∈ [0,1]`:

```text
V(t) = (1 − t) · V_A + t · V_B
```

Поскольку topology одинакова, vertex-to-vertex correspondence детерминирован. Нормали пересчитываются на каждом preview frame. Доступны:

- continuous slider;
- play/pause;
- speed;
- ping-pong;
- key positions 0/25/50/75/100%;
- identity-only morph;
- identity+expression morph;
- shape-only material;
- wireframe;
- displacement heatmap;
- split-screen synchronized view.

### 6.3 Texture morph

Два режима:

1. **Synthetic UV crossfade** — для цельной визуализации поверхности:
   `T(t) = (1 − t)·T_A + t·T_B`.
2. **Analytical overlap preview** — только общие observed pixels; дыры не дорисовываются и режим не используется как цельная 3D-текстура.

Synthetic morph всегда имеет badge **Visual only**. Можно отдельно управлять geometry mix и texture mix, чтобы видеть:

- геометрию A с текстурой B;
- геометрию B с текстурой A;
- 50/50 geometry при фиксированной текстуре;
- texture-only transition.

### 6.4 Region morph

- full face;
- forehead;
- eye region;
- nose;
- cheekbones;
- jaw;
- chin.

В региональном режиме blend weight плавно feathered по mesh geodesic boundary, чтобы не создавать разрывов. Он диагностический и не участвует в метриках.

### 6.5 Morph visual diagnostics

- vertex trajectories;
- maximum displacement regions;
- per-region displacement;
- silhouette A/B;
- landmarks;
- normals;
- UV seam view;
- synthetic provenance overlay;
- expression contribution.

### 6.6 Экспорт morph

- PNG текущего кадра;
- короткий MP4/WebM turntable или morph animation;
- OBJ выбранного `t`;
- GLB с текущей текстурой;
- JSON manifest с A/B IDs, alignment, t, mesh mode, texture mode и hashes.

Экспорт — техническая визуализация, не отчёт основного анализа.

---

## 7. Основной анализ вне UI

После freeze интерфейс показывает только готовую команду:

```bash
python run_main_analysis.py \
  --input /path/to/main_dataset \
  --calibration /path/to/calibration_run \
  --output /path/to/main_results
```

UI не загружает основной датасет, не строит расследовательскую timeline и не формирует его отчёт.

---

## 8. Runs & Logs

Только jobs калибровки и тестовых сравнений:

- queued/running/paused/completed/failed/cancelled/interrupted;
- реальный progress;
- current photo/step;
- ETA;
- stdout/stderr;
- retry failed photo;
- resume по hashes;
- cache reuse;
- config diff;
- disk usage;
- безопасная очистка derived files.

---

## 9. UI layout

### Calibration Studio

- left: pose/zone navigator;
- center: photo/UV/Skan viewer;
- right: config inspector;
- bottom: filmstrip, distributions и split status.

### Comparison Lab

- left: Person A set;
- right: Person B set;
- center: A/B viewer;
- bottom: pair matrix и metrics.

### Morph Studio

- крупный центральный 3D viewport;
- слева A/B assets;
- справа geometry/texture/region controls;
- снизу morph timeline и playback.

---

## 10. Жёсткие guards

- synthetic UV никогда не участвует в skin metrics;
- frozen calibration profile неизменяем;
- near-duplicate cluster не делится между splits;
- основной command не создаётся как approved, пока profile не passed+frozen;
- cross-pose skin comparison маркируется limited;
- identity-only и expression-inclusive результаты не смешиваются;
- visual exaggeration не меняет численные метрики;
- UI не выводит identity probability;
- оригинальные фото не удаляются и не модифицируются.

---

## 11. Acceptance criteria

- калибровка полностью выполняется без терминала;
- пользователь может визуально проверить каждую pose-zone модель;
- draft config изменяется с немедленным preview и точным diff;
- freeze создаёт профиль, готовый для headless основного анализа;
- любые две фотографии можно обработать и сравнить;
- при нескольких фото автоматически выбираются сопоставимые пары;
- geometry, skin texture и Skan graph показываются раздельно;
- morph работает для identity-only и expression meshes;
- geometry и texture mix управляются независимо;
- synthetic/analytical режимы невозможно перепутать;
- jobs поддерживают cancel/retry/resume;
- UI работает локально на MacBook M1 и не отправляет фото в сеть.
