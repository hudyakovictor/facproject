<callout icon="📊" color="blue_bg">
	Каталог фиксирует все анализы и метрики, включённые в архитектуру, оценённую выше 95/100 по совокупности научной корректности, устойчивости, воспроизводимости, объяснимости и инженерной реализуемости. Баллы отдельных анализов означают практическую ценность для хронологического исследования, а не вероятность подмены личности.
</callout>
<table_of_contents/>
## 1. Общие правила для всех метрик
- Анализировать только оригинальные наблюдаемые пиксели.
- UV/surface coordinates используются для соответствия и визуализации.
- Любое значение сопровождается `state`, quality, support, uncertainty и provenance.
- `NOT_OBSERVED`, `NOT_MEASURABLE`, `NOT_COMPARABLE` не заменяются нулём.
- Масштаб фильтра определяется effective surface resolution.
- Сравнение выполняется только на `common_observed_surface`.
- Для каждой метрики сохраняются raw и допустимая normalized/sensitivity branches.
- Один признак не является доказательством личности, материала или вмешательства.
## 2. Обязательный контроль качества и применимости
### 2.1 Геометрическая применимость
**Метрики:**
- detector confidence/stability;
- landmark reprojection residual;
- crop round-trip error;
- TTA variance identity/expression/pose;
- silhouette agreement;
- visible surface fraction;
- mean/p10 incidence;
- projection confidence;
- distance to silhouette/occlusion boundary;
- common surface coverage.
**Выход:** `geometry_usable`, `surface_projection_usable`, reasons.
### 2.2 Effective resolution
**Показатели:**
- native face width/height;
- projected pixels per surface unit;
- local foreshortening;
- local stretch;
- focus transfer;
- processing survival;
- effective macro/meso/micro resolution.
```plain text
effective_resolution ≈ projected_density
                     × focus_factor
                     × incidence_factor
                     × processing_survival
```
### 2.3 Резкость и blur
- Tenengrad/Sobel energy;
- Laplacian variance/energy;
- directional gradient energy;
- edge width/spread;
- local sharpness percentiles;
- anisotropic motion-blur estimate;
- skin-vs-nonskin sharpness difference.
### 2.4 Noise/grain
- wavelet MAD sigma;
- high-pass residual MAD;
- flat-patch noise;
- chroma/luma noise ratio;
- spatial heteroscedasticity;
- correlated grain spectrum;
- local noise inconsistency.
### 2.5 JPEG/resampling/processing
- 8×8 block-boundary energy;
- ringing/halo score;
- chroma subsampling indicators;
- periodic resampling peaks;
- high-frequency roll-off;
- repeated compression inconsistency;
- denoise/smoothing probability;
- sharpening probability;
- local skin blur;
- effective/native resolution ratio.
### 2.6 Photometric quality
- clipping fraction;
- shadow fraction;
- specular fraction;
- local dynamic range;
- illumination gradient;
- white-balance/color reliability;
- saturation/chroma reliability.
### 2.7 Помехи
- hair/beard/stubble coverage;
- glasses/hand/object coverage;
- specular/deep-shadow contamination;
- makeup-likely weak flag;
- unknown occlusion fraction.
---
## 3. Анализ №1 — топология постоянных морщин и складок, 91/100
### Области
Лоб, glabella, переносица, crow’s feet, under-eye, nasolabial, perioral, подбородок и устойчивые складки.
### Pipeline
```plain text
native luminance
→ low-frequency illumination removal
→ Frangi/Meijering/Hessian multiscale response
→ ridge polarity
→ orientation field
→ non-maximum suppression
→ quality-aware hysteresis
→ morphology/component filtering
→ skeletonize
→ Skan graph
→ triangle+barycentric projection
```
### Pixel/ridge metrics
- mean/max/p90 ridge response;
- ridge probability area fraction;
- response scale distribution;
- apparent width distribution;
- ridge continuity;
- response agreement FFHQ/classical;
- threshold stability.
### Graph metrics
- total branch length per valid surface area;
- branch count;
- endpoint count;
- junction count;
- connected component count;
- median/mean/p90/max branch length;
- endpoint geodesic distance;
- `tortuosity = path_length / endpoint_distance`;
- branch-type distribution;
- branch density;
- fragmentation;
- main-branch length where justified;
- graph degree distribution;
- mean/max ridge strength per branch;
- persistence across events.
### Pair metrics
- symmetric geodesic Chamfer distance;
- robust p95 Hausdorff distance;
- endpoint proximity;
- branch length ratio;
- curve resampling distance;
- topology neighborhood mismatch;
- junction consistency;
- matched/unmatched observable branch rates;
- common coverage;
- graph-match confidence.
### Ограничения
Expression, side light, blur, retouching, hair/brows, eyelid/lip boundaries. Skan измеряет skeleton, но не определяет, является ли линия морщиной.
## 4. Анализ №2 — региональный текстурный профиль, 88/100
### LBP
- multi-radius `(8,1)`, `(16,2)`, `(24,3)` после scale calibration;
- uniform/nri-uniform/variance LBP;
- normalized histogram;
- LBP entropy;
- uniform/nonuniform fractions;
- dominant-bin concentration;
- histogram χ²/intersection distance;
- cross-scale consistency;
- between-patch variation.
### Masked GLCM
Только валидные pixel pairs.
- contrast;
- dissimilarity;
- homogeneity;
- ASM;
- energy;
- correlation;
- entropy;
- mean/variance/std;
- distance slope;
- orientation anisotropy;
- cross-angle dispersion.
### Gabor
- energy by scale/orientation;
- dominant orientation;
- orientation entropy;
- anisotropy index;
- scale-energy slope;
- cross-scale consistency;
- response sparsity;
- rotation-pooled summary.
### Spectrum
После detrending и Hann window:
- low/mid/high-frequency energy ratios;
- spectral slope;
- spectral entropy;
- high-frequency roll-off;
- angular anisotropy;
- periodic peak score;
- radial-band variance;
- patch-to-patch spectral consistency.
### Distribution metrics
- weighted median/MAD/IQR;
- p10/p90;
- trimmed mean where validated;
- effective support;
- between-patch variance;
- spatial clustering;
- raw vs quality-matched distance.
## 5. Анализ №3 — хронологическая динамика кожи, 87/100
### Базовые временные показатели
- raw value by event/date;
- calibrated value;
- elapsed days/years;
- robust slope;
- Theil–Sen slope;
- slope confidence interval;
- rolling median;
- residual from expected trajectory;
- adjacent delta;
- long-range delta;
- rate normalized by elapsed time.
### Change metrics
- level-jump effect size;
- pre/post mean/median difference;
- pre/post slope difference;
- change-point bootstrap support;
- detection persistence;
- post-change duration;
- source/quality alternative-model fit;
- multi-zone support;
- multi-family support;
- cross-pose/cross-source replication.
### Специальные события
- `level_jump`;
- `slope_change`;
- `plateau_after_prior_trend`;
- `reversal_or_reset`;
- `persistent_post_change_state`;
- `A_B_A_recurrence`;
- `multiple_incompatible_trajectories`.
### Правило plateau
Нужны устойчивый pre-slope, несколько post-events, достаточный временной интервал, comparable quality, отсутствие source explanation и подтверждение несколькими зонами/семействами.
## 6. Анализ №4 — постоянные локальные особенности, 85/100
### Объекты
Родинки, пигментные пятна, шрамы, депигментации, устойчивые точки, углубления/выпуклости и scar-like линии.
### Метрики объекта
- triangle ID + barycentric centre;
- geodesic area/extent;
- equivalent apparent diameter;
- eccentricity/circularity;
- orientation;
- local relative Lab contrast;
- surrounding-background contrast;
- descriptor similarity;
- spatial uncertainty;
- independent event support;
- independent source support;
- persistence fraction;
- false-candidate/confounder flags.
### Pair metrics
- geodesic centre distance;
- shape similarity;
- relative contrast similarity;
- size ratio;
- descriptor distance;
- support diversity;
- match ambiguity.
## 7. Анализ №5 — направленность и анизотропия линий, 82/100
### Источники
Structure tensor, Hessian eigenvectors, gradient orientation, Gabor orientations и Skan branches.
### Метрики
- dominant tangent orientation;
- circular mean orientation;
- orientation resultant length;
- circular dispersion;
- orientation entropy;
- anisotropy index;
- horizontal/vertical/diagonal ratios относительно anatomical frame;
- crossing-angle distribution;
- local orientation coherence;
- cross-scale orientation consistency;
- pair circular difference modulo 180°.
```plain text
Δθ = min(|θ1-θ2| mod π, π-(|θ1-θ2| mod π))
```
## 8. Анализ №6 — неоднородность и наблюдаемый микрорельеф, 79/100
### Метрики
- local variance/std/MAD/IQR;
- RMS/Weber contrast;
- local entropy;
- gradient magnitude;
- Laplacian energy;
- DoG response bands;
- Hessian eigenvalue ratios;
- structure tensor coherence;
- LBP variance;
- GLCM contrast/homogeneity;
- spectral slope;
- autocorrelation decay length;
- patch roughness heterogeneity;
- transition density smooth↔rough;
- bilateral asymmetry.
**Термин:** `observed_texture_roughness`, не физическая высота или глубина кожи.
## 9. Анализ №7 — пигментация и цветовая неоднородность, 74/100
### Пространства
Linear/raw RGB where possible, Lab, normalized chromaticity и luminance/chroma separation.
### Метрики
- robust L*/a*/b\* median and spread;
- local chroma entropy;
- relative dark/light area fraction;
- hyper/hypopigmentation candidate count;
- connected-component area/shape;
- local relative contrast;
- regional mottling index;
- bilateral asymmetry;
- persistence across sources;
- color reliability/confidence.
Абсолютный RGB между годами имеет низкий вес. Предпочтительны относительные показатели внутри изображения.
## 10. Анализ №8 — поры и точечная микротекстура, 68/100
### Strict applicability
Только high native/effective resolution, low blur/JPEG, acceptable incidence, без beauty filter/сильного denoise.
### Метрики
- LoG/DoG blob candidate density per valid area;
- scale-response distribution;
- apparent diameter median/p90;
- area fraction;
- circularity/eccentricity;
- nearest-neighbor distance;
- clustering/dispersion index;
- regional pore-like density ratios;
- stability under small parameter changes;
- noise/JPEG confounding score.
Называть `pore_like_blob`, а не подтверждённая пора.
## 11. Анализ №9 — ретушь, сглаживание и локальное редактирование, 66/100
### Метрики
- skin-vs-adjacent high-frequency deficit;
- local blur discontinuity;
- noise residual discontinuity;
- JPEG inconsistency;
- sharpening halo score;
- repeated patch similarity;
- clone/heal candidate matches;
- abnormal local homogeneity;
- skin/hair sharpness mismatch;
- boundary between smoothed/non-smoothed regions;
- resampling periodicity;
- denoise probability;
- local edit cluster size.
Результат означает statistical processing anomaly, а не доказанный конкретный инструмент ретуши.
## 12. Анализ №10 — сосудистые, эритематозные и подглазничные паттерны, 58/100
### Метрики
- relative Lab a\* redness;
- normalized red/green chromaticity;
- under-eye relative luminance/chroma;
- local color contrast;
- vascular-like ridge response on chroma residual;
- redness/blue-area fraction;
- bilateral asymmetry;
- temporal variability;
- color reliability.
Только вспомогательный канал: обычные RGB-фото не являются медицинской или multispectral съёмкой.
---
## 13. Дополнительный анализ — блеск и specular response, 55/100
- specular area fraction;
- connected component count/size;
- location by zone;
- intensity/saturation profile;
- highlight boundary sharpness;
- texture survival inside/around highlight;
- diffuse/specular contrast;
- cross-zone distribution;
- masking coverage.
Главная функция — исключение загрязнённых пикселей; material inference вторична.
## 14. Лево-/правосторонняя асимметрия, 72/100
- mirrored surface patch distance;
- texture-family distance;
- wrinkle length/density asymmetry;
- orientation asymmetry;
- pigmentation asymmetry;
- local feature asymmetry;
- quality/light asymmetry control.
Требует анатомической handedness и контроля направления света.
## 15. Makeup/foundation-likely, 52/100
- local texture suppression;
- chroma shift;
- unusual regional uniformity;
- boundary discontinuity;
- pore-like density reduction;
- specular change;
- cross-zone inconsistency.
Статус только `makeup_or_processing_confounder_candidate`.
## 16. Щетина/борода как помеха, ценность контроля 80/100
- hair-like ridge density;
- orientation coherence;
- high-frequency excess;
- dark-line connected components;
- lower-face contamination fraction;
- overlap with W14/S40;
- exclusion/support loss.
Не использовать как skin identity feature.
## 17. Acne-like/воспалительные элементы, 50/100
- blob count/density;
- local redness;
- component area/shape;
- regional distribution;
- short-term persistence;
- quality/color confidence.
Нестабильный временный признак, не постоянная идентификационная характеристика.
## 18. Шрамы и устойчивые линейные дефекты, 83/100
- surface location;
- geodesic length;
- tangent orientation;
- width/contrast;
- branch topology;
- persistence;
- distinction score wrinkle-vs-scar;
- independent event/source support.
## 19. Текстурная симметрия относительно 3D-срединной плоскости, 76/100
- mirror patch mapping validity;
- LBP/GLCM/Gabor/spectrum distance;
- line orientation difference;
- local-feature mismatch;
- symmetric common coverage;
- illumination asymmetry penalty.
## 20. Стабильность границ кожа–губы–нос–глаза, 70/100
- contour reprojection residual;
- local edge position;
- transition width;
- nose-wing/nasolabial boundary stability;
- under-eye boundary stability;
- local refinement displacement;
- segmentation uncertainty.
Промежуточный канал между skin и geometry.
## 21. Следы изменения масштаба и интерполяции, 78/100
- periodic spectral peaks;
- aliasing/ringing;
- interpolation-kernel candidates;
- edge staircasing;
- effective/native resolution ratio;
- anisotropic resampling;
- double-resize indicators;
- microtexture permission flag.
## 22. Согласованность текстуры между ракурсами одной серии, 84/100
- same-event surface overlap;
- local photometric consistency;
- patch feature repeatability;
- subpixel alignment residual;
- source contribution count;
- robust fused patch variance;
- reconstruction inconsistency;
- view-angle dependence;
- effective resolution gain;
- outlier observation rate.
Multi-view fusion допускается только evidence-preserving, без генерации.
---
## 23. Material-consistency analyses
### 23.1 Organic microtexture
- multi-scale irregularity;
- nonperiodic local variation;
- patch distribution diversity;
- cross-scale decorrelation;
- degradation stability.
### 23.2 Excessive homogeneity
- low local variance after quality control;
- reduced entropy;
- low between-patch variation;
- abnormal cross-zone uniformity;
- absence of expected meso variation только при sufficient sensitivity.
### 23.3 Repetition/pattern regularity
- autocorrelation peaks;
- patch-nearest-neighbor duplication;
- spectral periodicity;
- repeated orientation pattern;
- spatial regularity index.
### 23.4 Specular/material optics
- highlight distribution;
- texture persistence through highlights;
- diffuse/specular boundary behaviour;
- zone consistency;
- single-image intrinsic reflectance experimental metrics.
### 23.5 Anatomical variation
- expected zone-to-zone texture differences;
- nose/cheek/forehead ratio profiles;
- bilateral relationships;
- local anomaly clustering.
### 23.6 Processing-confounder separation
- material evidence before/after degradation matching;
- noise/blur/JPEG explained fraction;
- source-domain distance;
- quality-only baseline;
- processing-only baseline.
### Material outputs
```plain text
compatible_with_observed_skin
localized_material_anomaly_candidate
multi_zone_material_anomaly_candidate
quality_explained
processing_confounding
out_of_validated_domain
mixed_uncertain
insufficient_evidence
```
## 24. Cross-photo similarity metrics
### Location
- geodesic centre/curve distance;
- normalized by patch radius;
- spatial uncertainty overlap.
### Orientation
- circular distance modulo π;
- orientation-field correlation;
- dominant-direction agreement;
- resultant-length confidence.
### Shape/topology
- curve resampling distance;
- robust Hausdorff;
- branch/junction neighborhood;
- graph edit-like descriptor distance;
- length/tortuosity ratios.
### Distribution
- χ²/intersection for histograms;
- robust standardized effect size;
- Wasserstein/energy distance candidates;
- correlation/cosine only where justified;
- bootstrap confidence intervals.
### Support
- common coverage;
- effective pixels/surface area;
- independent event count;
- source diversity;
- quality strata;
- ambiguity.
## 25. Quality/degradation matching metrics
```plain text
raw_delta
matched_delta_distribution
explained_fraction = 1 - matched_delta/raw_delta
degradation_robust_fraction
quality_parameter_uncertainty
feature_breakpoint
coverage_after_matching
```
При малом `raw_delta` explained fraction не интерпретируется.
## 26. Same-person calibration metrics
- within-event variance;
- between-event variance;
- source variance;
- ICC/test-retest reliability;
- coefficient of variation where valid;
- rank stability;
- false-difference rate;
- abstention/coverage;
- leave-one-event-out consensus error;
- branch localization error;
- circular orientation error;
- matched stable-structure rate;
- non-comparable rate by quality/pose.
## 27. Material/PAD validation metrics
- APCER;
- BPCER;
- ACER;
- EER;
- ROC-AUC;
- PR-AUC;
- Brier score;
- Expected Calibration Error;
- coverage-risk curve;
- OOD AUROC;
- FPR95;
- per-device/source/quality/photometric strata;
- confidence intervals;
- source-only, identity-only и quality-only baselines.
## 28. Chronology validation metrics
- false change-point rate on stable controls;
- event-level precision/recall;
- change-point localization interval;
- detection delay;
- bootstrap support;
- slope CI coverage;
- recurrence cluster stability;
- persistence duration;
- cross-source replication rate;
- confounder-explained rate;
- geometry–skin temporal agreement.
## 29. 15 факторов оценки итоговой архитектуры
1. Научная корректность постановки.
2. Анатомическая точность A20/S40/W14/Q.
3. Учёт ракурса и видимости.
4. Защита от noise/blur/JPEG.
5. Полнота texture metrics.
6. Wrinkle topology.
7. Осторожная material interpretation.
8. Готовность к chronology.
9. Uncertainty/applicability/abstention.
10. Leakage-free validation.
11. Reproducibility/provenance.
12. Эффективность на M1.
13. Storage/schema scalability.
14. Explainability/auditability.
15. Testability/maintainability.
Проектная оценка выше 95/100 относится к полноте архитектуры. Реальная диагностическая точность определяется только после grouped и external validation.
## 30. Приоритет реализации
```plain text
1. Quality/applicability
2. Surface projection и common coverage
3. Major wrinkle topology/orientation
4. Regional texture profile
5. Persistent local features
6. Same-event/cross-view repeatability
7. Degradation matching
8. Chronology
9. Material-consistency
10. Supporting color/pore/vascular channels
```
## 31. Минимальный feature output
Каждая метрика обязана иметь:
```plain text
feature_name/version
family
zone/patch
raw value
units
state/reasons
quality decomposition
support/common coverage
uncertainty
input branch
config/model hashes
source-pixel provenance
```
## 32. Запрещённые интерпретации
- Балл анализа ≠ вероятность другого человека.
- Similarity ≠ доказательство идентичности.
- Difference ≠ доказательство подмены.
- Material-like signal ≠ доказательство силикона.
- Pore-like blob ≠ подтверждённая пора.
- Observed roughness ≠ физическая глубина.
- Canonical surface unit ≠ миллиметр.
- Необнаруженная линия ≠ отсутствующая линия без sufficient sensitivity и coverage.
