<callout icon="🎯" color="blue_bg">
	**Назначение:** довести текущий `app6` до воспроизводимой версии, сначала готовой к проверке skin-канала примерно на 200 фотографиях одного человека, а после прохождения критериев — к полному последовательному запуску всех этапов на основном хронологическом датасете.
</callout>
<table_of_contents/>
## 1. Что зафиксировано
- Существующий калибровочный датасет предназначен **только для геометрии**. Его результаты и нормы нельзя автоматически использовать для кожи.
- Для skin-разработки будет отдельный набор примерно из 200 фотографий **одного и того же человека**.
- Он нужен для проверки same-person repeatability: одинакового анатомического положения устойчивых морщин, согласованности их направлений, формы крупных ветвей, локальных особенностей и зональных texture-профилей.
- Слабое фото не обязано давать fine-detail результат. Оно может участвовать только в тех coarse-признаках, для которых хватает наблюдаемых пикселей; иначе результат — `INSUFFICIENT_EVIDENCE`, а не ложное различие.
- Этот набор не является полноценной калибровкой universal real-vs-silicone и не задаёт популяционную норму старения.
## 2. Роль набора из 200 фотографий
### Что он позволит настроить
- точность A20/S40/W14/Q-проекции;
- repeatability по ракурсам, качеству и сериям съёмки;
- common observed surface между парами;
- устойчивость wrinkle location;
- устойчивость направления в локальной касательной системе поверхности;
- graph matching крупных ветвей;
- персональные интервалы вариативности;
- quality gates для macro/meso/micro признаков;
- false-difference и abstention rates;
- degradation matching для blur/noise/JPEG;
- подготовку персональной временной baseline-модели.
### Чего он не доказывает
- универсальную точность на других людях;
- различение всех материалов масок;
- переносимость между всеми камерами и фотометрическими типами кожи;
- нормальную возрастную траекторию популяции;
- идентичность человека по одному skin score.
<callout icon="⚠️" color="yellow_bg">
	200 фотографий одного человека — сильный набор для **проверки повторяемости и ложных различий**, но слабый набор для обучения бинарного классификатора материала. Эти задачи будут разделены.
</callout>
## 3. Итоги проверки приложенного документа
Документ в целом методологически совпадает с целевой архитектурой. Особенно правильны следующие положения:
- анализ на исходных пикселях;
- `seg_visible` и common observed area;
- UV как карта соответствия, а не источник дорисованной микротекстуры;
- triangle ID + barycentric coordinates;
- сравнение wrinkle graph на поверхности;
- tangent-space orientation вместо угла в фотографии;
- раздельные quality levels для geometry/macro/meso/micro;
- `NOT_OBSERVED` вместо нулевого значения;
- evidence atlas отдельно от visualization atlas;
- multi-image fusion только при поддержке реальными наблюдениями;
- camera/processing fingerprint как confounder-контроль;
- provenance до исходного пикселя.
### Уточнения к документу
1. **Surface length нельзя автоматически называть миллиметрами.** BFM/3DDFA scale не гарантирует метрическую калибровку. До отдельной scale calibration сохраняются `canonical_surface_units` и нормализованные длины.
2. **Uncertainty head для переобучения 3DDFA не входит в первую production-версию.** Сначала применяется эмпирическая uncertainty через crop/detector/test-time perturbations и стабильность результата.
3. **Joint multi-image 3D fitting откладывается.** Сильное shared-identity ограничение способно само скрыть искомую аномалию. Сначала каждое фото реконструируется независимо; joint fitting позднее используется только как альтернативная модель H0/H1.
4. **Frontal photo не гарантирует microtexture.** Решение принимается по effective resolution, native detail, blur, JPEG и incidence.
5. **FFHQ и Frangi не подтверждают друг друга автоматически.** Их согласие повышает evidence, расхождение сохраняется и показывается отдельно.
### Дополнительная библиотека: `potpourri3d`
Интеграция **принята как условно обязательная для surface-геометрии**, после теста установки и численной стабильности на MacBook M1. Библиотека предоставляет heat-method geodesic distances и vector heat/parallel transport для triangle meshes.[\[1\]](https://github.com/nmwsharp/potpourri3d)
Использование:
- geodesic distance между wrinkle curves;
- построение canonical geodesic patches;
- tangent-vector transport;
- сравнение ориентаций на разных участках поверхности;
- surface log-map/local coordinates;
- geodesic distance transform от линий и landmarks.
Не используется для:
- определения морщин;
- rasterization;
- исправления 3DDFA;
- генерации отсутствующей текстуры.
Fallback при проблемах сборки: precomputed mesh graph + SciPy sparse shortest paths. Solver/factorization кэшируется один раз для фиксированной BFM topology.
<pdf src="file://%7B%22source%22%3A%22attachment%3A0cab4e6e-807c-4d21-97ba-eb1c7c90c590%3A483ed1d1-4598-4348-bc9b-615769967323.pdf%22%2C%22permissionRecord%22%3A%7B%22table%22%3A%22block%22%2C%22id%22%3A%226259e003-7b03-4d87-b1a0-ead856b7a926%22%2C%22spaceId%22%3A%22ddb38bb5-c057-81fd-aeab-0003139596bd%22%7D%7D">Исходный документ: топ анализов кожи и FSEA</pdf>
---
## 4. Целевая архитектура
```plain text
Original images
  ↓
Preflight / provenance / source quality
  ↓
Stage 1A — independent 3DDFA reconstruction
  ↓
Stage 1B — full-resolution surface observation projection
  ↓
Stage 1C — A20/S40/W14/Q + applicability maps
  ↓
Stage 1D — texture / microrelief / local features
  ↓
Stage 1E — FFHQ + classical ridges + Skan
  ↓
Stage 1F — material-consistency evidence
  ↓
Immutable per-photo skin package
  ↓
Stage 2A — calibration and quality matching
  ↓
Stage 2B — pair and group comparison
  ↓
Stage 2C — chronology / change points / recurring states
  ↓
Stage 2D — geometry–skin corroboration
  ↓
Stage 3 — maps, tables and investigator report
```
**Правило:** 3DDFA выполняется один раз в Stage 1. Stage 2/3 читают сохранённые продукты и не повторяют reconstruction.
## 5. Целевая структура кода
```plain text
app6/
├── stage1/
│   └── skin/
│       ├── contracts.py
│       ├── manifest.py
│       ├── atlas_registry.py
│       ├── projection.py
│       ├── visibility.py
│       ├── surface_geometry.py
│       ├── quality.py
│       ├── patch_sampler.py
│       ├── feature_registry.py
│       ├── texture/
│       ├── wrinkles/
│       ├── local_features/
│       ├── material/
│       ├── sensitivity/
│       └── serialization.py
├── stage2/
│   └── skin/
│       ├── loader.py
│       ├── calibration.py
│       ├── applicability.py
│       ├── quality_matching.py
│       ├── pair_comparison.py
│       ├── wrinkle_matching.py
│       ├── material_model.py
│       ├── uncertainty.py
│       ├── chronology.py
│       ├── change_points.py
│       └── corroboration.py
└── stage3/
    └── skin/
        ├── overlays.py
        ├── zone_tables.py
        ├── chronology_plots.py
        └── report.py
```
---
## 6. Последовательный план реализации
### Фаза 0 — snapshot и migration map
- заморозить текущую версию;
- записать hashes и текущие тесты;
- классифицировать legacy skin-модули;
- вывести из production `forehead-fallback-v1`;
- заменить placeholders `wrinkle_zones` и `forensics-disabled`;
- устранить зависимости от удалённых `SkinAnalyzer`, `uv_module.zones`, `uv_module.calibration`;
- исправить `photo_id`, resolution guard и provenance tests.
**Gate:** legacy-код не запускается неявно; проект стартует в чистом окружении.
### Фаза 1 — schemas и provenance
Новые версии:
```plain text
skin-manifest-v1
skin-surface-observations-v1
skin-atlas-projection-v1
skin-quality-v1
skin-features-v1
skin-wrinkles-v1
skin-material-evidence-v1
skin-pair-v1
skin-temporal-v1
```
Manifest хранит source SHA-256, versions, weights hashes, topology/atlas/config hashes, backend, seed, warnings и runtime.
**Gate:** несовместимые версии не смешиваются; одинаковый вход воспроизводим.
### Фаза 2 — полноразмерная observation projection
- triangle-level rasterization;
- z-buffer;
- barycentric map;
- original → crop → model → original transforms;
- triangle visibility и incidence;
- observed/synthetic separation;
- отдельный background ID;
- anatomical left/right convention;
- compact label maps вместо object arrays.
Выходы:
```plain text
triangle_id_map
barycentric_map
source_xy
normal_map
incidence_map
depth_map
visibility_map
projection_confidence
boundary_distance
zone_id_a20
zone_id_s40
wrinkle_bits_w14
```
**Gate:** `allow_pickle=False`; фон не смешивается с zone 0; synthetic pixels не участвуют в измерении; все 9 pose bins протестированы.
### Фаза 3 — mesh-native surface geometry
- интегрировать `potpourri3d`;
- построить canonical patch registry;
- вычислить geodesic neighborhoods;
- создать локальные tangent frames;
- определить mirror-patch relations;
- кэшировать surface solvers для topology 35709/70789;
- добавить тесты geodesic symmetry, transport round-trip и left/right consistency.
**Gate:** ориентация линии не зависит от roll изображения; surface distance стабилен и детерминирован.
### Фаза 4 — quality/applicability engine
Отдельные уровни:
```plain text
geometry
macro_texture
meso_texture
micro_texture
wrinkles
pigmentation
material_optics
```
Карты и показатели:
- effective projected resolution;
- focus/blur;
- wavelet/high-pass noise;
- JPEG blocking/ringing;
- sharpening/denoise indicators;
- clipping/exposure;
- local contrast;
- specular/deep shadow;
- hair/beard/stubble;
- occlusion;
- source/upscale/scan indicators.
**Gate:** плохое качество создаёт abstention или coarse-only режим, но не ложное отличие.
### Фаза 5 — texture и microrelief
A20:
- multi-radius LBP;
- custom masked GLCM;
- multi-scale Gabor;
- patch entropy/MAD/IQR;
- autocorrelation;
- spectral bands, slope и anisotropy.
S40:
- DoG/LoG;
- Hessian eigenvalues;
- structure tensor;
- pore-like blob density;
- local relief variation;
- repetition и patch heterogeneity.
Правила:
- FFT только на валидных detrended patches с Hann window;
- GLCM учитывает только пары валидных пикселей;
- масштабы зависят от effective surface resolution;
- `NOT_MEASURABLE` не заменяется нулём.
**Gate:** каждая метрика имеет applicability rule, unit test, sensitivity class и repeatability report.
### Фаза 6 — local persistent features
- родинки, шрамы, устойчивые пятна и линейные дефекты;
- LoG/DoG candidate generation;
- relative Lab contrast вместо абсолютного RGB;
- shape/eccentricity/local descriptor;
- projection centre как triangle+barycentric;
- persistence только после нескольких независимых событий.
**Gate:** одиночная точка не становится identity evidence; scan/JPEG/dust candidates маркируются как confounded.
### Фаза 7 — wrinkle engine
Классическая ветка:
```plain text
native ROI
→ illumination residual
→ Frangi/Meijering/Hessian
→ direction field
→ non-maximum suppression
→ quality-aware hysteresis
→ skeletonize
→ Skan
→ project graph nodes to mesh
```
FFHQ-ветка:
- убрать Gradio/runtime coupling;
- batch API;
- lazy model loading;
- model hash;
- probability map;
- inverse mapping в original/surface coordinates;
- порог калибруется по zone/quality/scale.
Skan сохраняет branches, endpoints, junctions, length, tortuosity, strength, fragmentation и orientation.
**Gate:** FFHQ/classical сохраняются отдельно; граф трассируется до исходных пикселей; слабое фото не получает false absence.
### Фаза 8 — same-person wrinkle matching
Для пары формируется:
```plain text
common_observed_surface =
patch ∩ observed_A ∩ observed_B ∩ confidence_A ∩ confidence_B
```
Сравнения:
- geodesic Chamfer distance;
- robust Hausdorff distance;
- endpoint proximity;
- branch length ratio;
- tangent orientation difference с периодом 180°;
- topology descriptors;
- junction/branch consistency;
- curve-shape similarity;
- agreement после degradation matching.
Статусы:
```plain text
MATCHED_STABLE_STRUCTURE
PARTIAL_MATCH
COARSE_DIRECTION_MATCH
QUALITY_EXPLAINED_DIFFERENCE
NOT_COMPARABLE
NOT_OBSERVED
INSUFFICIENT_EVIDENCE
```
**Gate:** алгоритм способен показать, что крупная линия находится в той же surface region и имеет согласованное направление, даже если её контраст/тонкая форма различаются.
### Фаза 9 — material-consistency
Независимые families:
- organic microtexture;
- wrinkle/ridge topology;
- spatial homogeneity;
- repeated patterns;
- pore-like distribution;
- specular/diffuse behaviour;
- cross-zone anatomical variation;
- processing/degradation consistency;
- optional deep PAD channel.
Статусы:
```plain text
compatible_live_skin
material_like_signal
quality_explained
processing_artifact_suspected
mixed_uncertain
insufficient_evidence
out_of_validated_domain
```
**Gate:** один показатель не создаёт вердикт; вероятность не публикуется до внешней material calibration.
### Фаза 10 — immutable per-photo package
```plain text
skin/
├── manifest.json
├── surface_observations.npz
├── atlas_projection.npz
├── quality_maps.npz
├── quality.json
├── patch_index.npz
├── feature_values.npz
├── feature_summary.json
├── feature_table.csv
├── local_features/
├── wrinkles/
├── material/
├── sensitivity/
└── previews/
```
**Gate:** Stage 2 получает всё без повторного 3DDFA; optional failure не ломает весь результат.
### Фаза 11 — Stage 2 comparison/calibration
- schema validation;
- common zones;
- pose/expression policy;
- quality matching;
- raw и matched differences;
- uncertainty decomposition;
- zone-level explanations;
- geometry и skin — раздельные outputs;
- late corroboration.
**Gate:** missing не становится zero; результат раскладывается по зонам и причинам.
### Фаза 12 — chronology
Для `pose × zone × metric family`:
- elapsed days/years;
- robust slope;
- bootstrap interval;
- piecewise trends;
- change points;
- plateau after prior trend;
- reversal/reset;
- persistent post-change state;
- A→B→A recurrence;
- source/quality controls;
- cross-zone и cross-pose support.
**Gate:** «остановка старения» требует прежнего устойчивого slope, достаточного интервала, нескольких последующих фото и отсутствия quality/source explanation.
### Фаза 13 — Stage 3
- original-space overlays;
- surface/UV evidence maps;
- matched wrinkle branches;
- per-zone tables;
- quality/applicability explanations;
- chronology plots;
- geometry–skin agreement/disagreement;
- investigator summary без автоматического утверждения личности или материала.
---
## 7. Протокол калибровки на 200 фотографиях
### Metadata
Желательно подготовить:
- дату или диапазон даты;
- capture event/series;
- camera/source;
- original/recompressed/scanned;
- обработку, если известна;
- pose и expression;
- makeup/facial hair, если известны.
### Разделение
```plain text
60% development
20% calibration
20% untouched final test
```
Разделение выполняется по событию/серии/камере, а не случайно по отдельным кадрам.
### Этапы
1. Extraction-only Stage 1 для всех фото.
2. Quality/source/pose stratification.
3. Построение pair matrix только внутри допустимых сравнений.
4. Repeatability: ICC, CV, bootstrap intervals.
5. Consensus wrinkle maps только из независимых пригодных событий.
6. Проверка location/orientation/graph persistence.
7. Искусственные degradation controls от лучших исходников.
8. Отбор feature families по repeatability и false-difference.
9. Calibration thresholds без доступа к final test.
10. Финальный blind-like test.
### Критерии готовности
- стабильная проекция всех поддержанных ракурсов;
- low false-difference на quality-matched same-person pairs;
- крупные устойчивые wrinkle branches совпадают по surface location и direction;
- low-quality повышает abstention, а не anomaly;
- noise/blur/JPEG различия объясняются degradation matching;
- нестабильные метрики исключены или понижены;
- final test не участвовал в настройке;
- Stage 1/2/3 завершаются без ручного редактирования результатов.
---
## 8. Переход к основному датасету
Перед полным запуском:
- freeze code/config/models/atlas;
- создать release manifest;
- выполнить dry run на небольшой стратифицированной выборке;
- проверить storage и runtime;
- подтвердить resume/restart;
- создать failure registry;
- запретить silent fallback на legacy.
Полный запуск:
```plain text
1. Ingest + duplicate/source grouping
2. Stage 1 geometry
3. Stage 1 skin evidence
4. Per-photo validation
5. Stage 2 calibration application
6. Pair/group comparison
7. Chronology
8. Geometry–skin corroboration
9. Stage 3 reports
10. Dataset-level audit
```
Для main run ничего не дообучается на анализируемых фотографиях. Любое изменение модели или thresholds создаёт новую версию результатов.
## 9. Test matrix
- unit tests для каждой metric family;
- projection/golden triangle tests;
- handedness и symmetry tests;
- M1 CPU/MPS parity;
- `allow_pickle=False` storage tests;
- crop/scale/rotation perturbation;
- blur/noise/JPEG/resize/scan/sharpen/denoise controls;
- subject/event/source grouped validation;
- provenance round-trip до source pixel;
- no-rerun-3DDFA test;
- regression tests на фиксированных фотографиях;
- memory/runtime benchmark.
## 10. Definition of Done
Проект считается готовым к основному запуску, когда:
- все обязательные Stage 1 продукты реальны, а не placeholders;
- A20/S40/W14/Q — единственный production atlas contract;
- `potpourri3d` surface module прошёл M1 tests или включён проверенный fallback;
- FFHQ работает как batch adapter;
- Skan действительно интегрирован;
- quality/applicability действует по metric families;
- Stage 2 не запускает 3DDFA;
- same-person skin calibration прошла untouched test;
- material status умеет abstain;
- chronology различает jump, plateau, reversal и recurrence;
- все результаты воспроизводимы и трассируются до исходных пикселей;
- полный pipeline выполняется последовательно и поддерживает безопасный resume.
<callout icon="✅" color="green_bg">
	**Итог:** набор из 200 фотографий будет использоваться как строгий same-person repeatability benchmark. Его главная проверка — не «узнал ли классификатор человека», а сохранились ли при разных условиях анатомическое положение, surface-направление и топология действительно наблюдаемых устойчивых признаков без ложных различий от качества.
</callout>
<page url="https://app.notion.com/p/5a6446973d7345b2ac37a9be9f895520">00 — Паспорт проекта, память решений и ограничения</page>
<page url="https://app.notion.com/p/d8365e63f0014b83b30b5d98061337d6">03 — Датасеты, калибровка, валидация и критерии достоверности</page>
<page url="https://app.notion.com/p/f97a49886bc34f798fd0bff6134987b2">01 — Детальная спецификация Stage 1 и per-photo evidence</page>
<page url="https://app.notion.com/p/c107999d083e43f287efcf462d3f6aa2">02 — Stage 2, хронология, fusion и Stage 3</page>
<page url="https://app.notion.com/p/8faef6676b74461ba5ca9140d47f9ca3">04 — Миграция app6, тесты, библиотеки и эксплуатационный runbook</page>
<page url="https://app.notion.com/p/b3d74839cc884e358cf3312eff08ab8d">05 — Контракты данных, формулы, статусы и псевдокод</page>
<page url="https://app.notion.com/p/fa598a95afd44b5bab5c6ccb6875b7db">06 — Журнал решений, открытые вопросы и точка продолжения</page>
<page url="https://app.notion.com/p/1a171ec8bf0e4ddda8d9674bcd3d359b">Часть 3 — Полный каталог анализов, признаков и метрик skin pipeline</page>
