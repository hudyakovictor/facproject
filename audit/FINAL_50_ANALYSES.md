# 50 Финальных Анализов DEEPUTIN + Карта Потока Данных

**Дата:** 2026-08-27
**Источники:** 14 независимых аудитов (`audit/1.md`–`audit/14.md`), `audit/final_report.md`, `audit/FIXES_APPLIED_ROUND1.md`, `audit/EXPERT_EVALUATION_15_FACTORS.md`, код `app6/stage1/`, `app6/stage2/`, `app6/stage2b/`, `app6/stage3/`, `docs/final/*`
**Консенсус 14 аудитов:** все сходятся — результаты нельзя предъявлять как доказательство, но архитектура — хорошая основа

---

## ЧАСТЬ 1: КАРТА ПОТОКА ДАННЫХ (Stage 1 → Stage 3)

### Как данные преобразуются от фото до отчёта

```
ФОТО (YYYY_MM_DD[_N].ext)
│
▼ STAGE 1: Извлечение (stage1/engine.py)
│
├── [1] Input Preflight
│   ├── Content Hash (SHA-256) → дедупликация побайтовых дубликатов
│   ├── Perceptual Hash (dHash) → near-duplicates (hamming ≤4)
│   ├── Filename Date Parsing → YYYY_MM_DD[_N] = authority
│   ├── EXIF Reading → corroboration only
│   └── Provenance Sidecar → source URL, archive URL
│   Output: input_provenance.csv
│
├── [2] 3DDFA_V3 Neural Inference (reconstruction.py)
│   ├── RetinaFace Detection → bbox, detection_confidence
│   ├── ResNet-50 Encoder → BFM parameters:
│   │   ├── alpha_id (199 coeffs) → identity shape
│   │   ├── alpha_exp (64 coeffs) → expression
│   │   ├── alpha_alb → albedo (texture color)
│   │   ├── alpha_sh → shading (lighting)
│   │   └── angles (pitch/yaw/roll) + translation
│   ├── Mesh Generation → 35,709 vertices in 4 spaces:
│   │   ├── object (BFM raw, identity+expression)
│   │   ├── object_normalized (RMS=1, PRIMARY)
│   │   ├── bin_canonical (yaw-only, deprecated)
│   │   └── chronology_aligned (full pose correction, diagnostic)
│   ├── Reprojection Check → p95 ≤ 5px, else reject
│   └── Renderer Visibility → front-facing × renderer masks
│   Output: reconstruction.npz, info.json
│
├── [3] Landmarks & Geometry (geometry.py)
│   ├── LDM106 → 106 facial landmarks (3D coords)
│   ├── LDM134 → 134 facial landmarks (3D coords)
│   ├── Pose Classification → 9 bins (yaw thresholds)
│   ├── Chronology Alignment → full pose correction
│   │   ├── target_pose (canonical)
│   │   ├── correction_matrix (applied rotation)
│   │   └── residual angles (pitch/yaw/roll after correction)
│   └── Normalization → center + RMS scale
│   Output: ldm106_chronology.csv, ldm134_chronology.csv
│
├── [4] UV Texture & Skin (assets.py, authenticity/)
│   ├── UV Texture Map → 1000×1000 px
│   ├── Face Mask → skin/nose segmentation
│   ├── Semantic Channels → 8 channels (skin, nose, eyes, etc.)
│   ├── Skin Quality → LBP, FFT, albedo analysis
│   ├── Skin Authenticity → z-score vs calibration
│   └── Texture Zones → per-zone quality assessment
│   Output: uv_texture.png, face_mask.png, texture.json
│
├── [5] Expression Detection (geometry-based)
│   ├── corner_lift_ioc > 0.005 → smile
│   ├── jaw_open_ratio > 0.28 → open mouth
│   ├── expression_magnitude → combined
│   └── smile_detected / jaw_open_detected → boolean flags
│   (stored in info.json → chronology section)
│
└── [6] Validation & Atomic Commit
    ├── validate_photo() → checks all artifacts
    ├── Atomic directory commit
    └── Hash-aware resume
    Output: photo_id/ directory with all artifacts

═══════════════════════════════════════════════════════════════

▼ STAGE 2: Попарный анализ (stage2/engine.py)
│
├── [7] Loading & Calibration
│   ├── load_main() → all Stage 1 records (1909 photos)
│   ├── load_calibration() → 7 persons, 943 frames
│   ├── CalibrationModel → person-balanced reference
│   │   ├── Per-bin per-zone per-metric null distributions
│   │   ├── LOPO sensitivity (leave-one-person-out)
│   │   ├── Cluster bootstrap CI
│   │   └── Contamination hardening (lower80 policy)
│   ├── PointNoiseModel → 134-point noise template
│   ├── DescriptorNoiseModel → 13 descriptor families
│   ├── MeshNoiseModel → dense mesh noise
│   └── Angle Noise Index → calibration pairs by delta
│
├── [8] Pair Planning (pair_planner.py)
│   ├── Within pose_bin only
│   ├── Adjacent pairs (consecutive by date)
│   ├── Baseline pairs (vs first frame in bin)
│   ├── Rolling anchor pairs (step=5, window=24)
│   └── Pose gap gate → per-bin thresholds from pose_gate_v2.csv
│       frontal ≤12° yaw, profile ≤2° yaw, etc.
│   Output: planned pairs list
│
├── [9] Per-Pair Analysis (core.py, motion.py, etc.)
│   │
│   ├── [9a] Gates (fail-closed):
│   │   ├── Pose gap → reject if > per-bin threshold
│   │   ├── Visibility intersection → ≥30/24 common points
│   │   ├── Expression gate → ⚠️ accepts all (P1-2 confirmed)
│   │   └── Quality gate → quality_limited flag
│   │
│   ├── [9b] Geometry (core.py):
│   │   ├── Robust Kabsch → iterative trimmed (15%, 5 iter, no scale)
│   │   ├── LDM134 RMSE / Median / P95
│   │   ├── LDM106 RMSE / Median / P95
│   │   ├── Identity-only RMSE (expression removed)
│   │   ├── Per-zone RMSE (9 coordinate zones)
│   │   └── calibrated_score() → robust z vs null
│   │
│   ├── [9c] Point Motion (motion.py):
│   │   ├── aligned_point_motion() → per-point z-scores
│   │   ├── p95_point_z → 95th percentile z
│   │   ├── significant_point_fraction → % above noise
│   │   ├── coherent_motion_fraction → % moving same direction
│   │   └── calibrated_point_count → points with valid null
│   │       (requires ≥54 for evidence-level status)
│   │
│   ├── [9d] Descriptors (descriptors.py):
│   │   ├── 13 families: Procrustes, local shape, stable subset91, etc.
│   │   ├── Per-family calibrated z-scores
│   │   └── descriptor_top_families → strongest signals
│   │
│   ├── [9e] Dense Mesh (mesh_dense.py):
│   │   ├── 35,709 vertices comparison
│   │   ├── mesh_rmse, mesh_p95
│   │   ├── point_to_plane metrics
│   │   └── ⚠️ same latent space as alpha_id (P1-1)
│   │
│   ├── [9f] Texture (texture_pair.py, texture_image.py):
│   │   ├── LBP, GLCM, Gabor, SSIM deltas
│   │   ├── ⚠️ No pose normalization (diagnostic only)
│   │   └── texture_pair_status → visualization only
│   │
│   ├── [9g] Angle Noise (angle_noise.py):
│   │   ├── Find matching calibration pair by angle delta
│   │   ├── Subtract noise from metrics
│   │   └── ⚠️ Result stored but NOT used in scoring (P1-5)
│   │
│   └── [9h] Evidence State (evidence.py):
│       ├── Primary status from geometry/motion
│       ├── Quality/calibration/pose downgrades
│       ├── Evidence state mapping (STATUS_TO_EVIDENCE_STATE)
│       ├── Alternative explanations list
│       └── EvidencePacket → structured record
│
├── [10] Temporal Analysis
│   ├── Chronology Rate Flags (chronology.py):
│   │   ├── rate = p95_z × coherent_fraction / sqrt(days)
│   │   ├── ⚠️ Self-calibrating baseline (P0-3)
│   │   └── Flags: same_day, rapid_change, biologically_improbable
│   ├── Baseline Return (baseline_return.py):
│   │   ├── Cosine between A→B and B→C vectors
│   │   ├── ⚠️ FP=0.9% on null (audit confirmed OK)
│   │   └── baseline_return flag
│   ├── Alpha Chronology (alpha_chronology.py):
│   │   └── alpha_id drift detection
│   └── Cumulative Drift (cumulative_drift.py):
│       └── CUSUM-style drift detection
│
├── [11] Multiple Testing (multiple_testing.py)
│   ├── Pair-level FDR (Benjamini-Hochberg)
│   ├── p95 order statistic p-value
│   ├── ⚠️ Single-z fallback for <20 points (P0-5)
│   ├── Zone-level FDR
│   └── Dependence inflation factor
│
├── [12] Cross-Bin Corroboration (corroboration.py)
│   ├── Check same signal in other pose bins
│   ├── Aggregate events across bins
│   └── ⚠️ independent_source_count not used as condition (P1-14)
│
├── [13] Persistence (_persistence)
│   ├── Adjacent candidates → persistent_geometric_change
│   └── ⚠️ Only 2 consecutive = "persistent" (P2-11)
│
└── [14] Output
    ├── pair_metrics.csv (all pairs with 68+ fields)
    ├── zone_metrics.csv (per-zone metrics)
    ├── change_points.json (reportable changes)
    ├── evidence_packets.json (structured evidence)
    ├── analysis_manifest.json (run metadata + hash quartet)
    ├── analysis_validation.json (contract validation)
    └── Post-process reports:
        ├── manual_review_queue.csv
        ├── public_safety_report.json (forbidden terms check)
        ├── degraded_modules.json
        └── gate_report.json

═══════════════════════════════════════════════════════════════

▼ STAGE 2B: Post-Processing (stage2b/engine.py)
│
├── [15] Private Prior Corroboration
│   ├── Load prior leads/archive
│   ├── Cross-reference with Stage 2 findings
│   ├── Lead overlap detection
│   └── ⚠️ Never modifies blind Stage 2 measurements
│
└── [16] Output
    ├── corroborated_pairs
    ├── lead_coverage
    └── Stage 2B reports (private, not public)

═══════════════════════════════════════════════════════════════

▼ STAGE 3: Final Report (stage3/engine.py)
│
├── [17] Input Validation
│   ├── Check analysis_validation.json → status=complete
│   ├── Check analysis_manifest.json → status=complete
│   └── Verify evidence-gate on all change points
│
├── [18] Data Assembly
│   ├── pair_metrics.csv → public_pair_projection()
│   │   └── status = evidence_state (not raw status)
│   ├── zone_metrics.csv
│   ├── change_points.json
│   ├── lead_registry.json
│   └── metric_catalog.json
│
├── [19] Timelines & Motion Maps
│   ├── Per-pose-bin timelines (SVG charts)
│   ├── Motion maps (134-point vectors on template)
│   └── Top 40 pairs by p95_point_z
│
├── [20] Narrative Generation
│   ├── 6 fixed paragraphs about methodology
│   ├── "Ни один статус не доказывает подмену..."
│   └── ⚠️ No per-pair, per-photo, per-epoch narrative (P0 report)
│
├── [21] Report Sections (JSON)
│   ├── summary.json
│   ├── narrative.json
│   ├── timelines.json
│   ├── motion_maps.json
│   ├── change_points.json
│   └── zones.json
│
└── [22] HTML Report
    ├── Interactive dashboard (SVG, filters, tables)
    ├── Forbidden terms check (public safety)
    └── ⚠️ _html()/TEMPLATE is dead code (P1-10)
        HTML generated via embedded JS in sections

═══════════════════════════════════════════════════════════════

КАЛИБРАЦИЯ (отдельный процесс):
│
├── 7 persons × 9 bins × 943 frames
├── Person-balanced reference (equal weight)
├── LOPO sensitivity (leave-one-dataset-out)
├── Cluster bootstrap CI
├── Contamination hardening (10% → TPR 0.51, 20% → 0.24)
└── Output: calibration_noise_model.json, point_noise_model.npz, etc.
```

---

## ЧАСТЬ 2: 50 ФИНАЛЬНЫХ АНАЛИЗОВ

### БЛОК A: ДОСТОВЕРНОСТЬ ДАННЫХ (Stage 1)

**A1.** 3DDFA_V3 реконструкция имеет систематический bias: поза объясняет 46.1% вариации, identity — только 5.5%. Это задокументировано и частично компенсировано same-bin сравнением.
**Консенсус 14/14 аудитов.** ✅ Подтверждено.

**A2.** Reprojection p95 ≤ 5px — внутренний invariant, не ground truth проверка. Два выхода одной модели сравниваются, а не 3D с реальностью.
**Консенсус 12/14.** ✅ Подтверждено.

**A3.** Pose estimation: ошибка углов на профилях не измерена. Гейт 2° для профиля сравнивает шум с шумом, если ошибка 3DDFA ~3–5°.
**Консенсус 11/14.** ✅ Подтверждено.

**A4.** `coordinate_noise_sigma` всегда 0.0 — stage1 не записывает это поле. Механизм `noise_adjusted_threshold` мёртв. **Исправлено в раунде 1** (fallback на reprojection_rmse).
**Консенсус 10/14.** ✅ Подтверждено + исправлено.

**A5.** Texture channel = diagnostic only. Извлекается в image-space без pose normalization. Корреляция с эпохой r=0.52. Код честно помечает как visualization-only.
**Консенсус 14/14.** ✅ Подтверждено.

**A6.** Alpha coefficients: identity и expression коллинеарны. Нейросеть компенсирует нестандартную идентичность мимикой. Канал слабый (ci_lo 0.6768).
**Консенсус 10/14.** ✅ Подтверждено.

**A7.** Landmark стабильность не измерена (нет test-retest). Порядок ошибки ~0.3mm из калибровки, но включает фотографическую вариативность.
**Консенсус 9/14.** ✅ Подтверждено.

**A8.** Skin authenticity/quality извлекается корректно, но зависит от освещения и эпохи. Z-оценка против калибровки — правильная идея, но калибровка мала.
**Консенсус 8/14.** ✅ Подтверждено.

### БЛОК B: СТАТИСТИКА И КАЛИБРОВКА (Stage 2)

**B9.** FDR p-value: биномиальная формула предполагает независимость 134 точек. Реально они жестко связаны BFM (144 параметра). P-value занижен на 5–9 порядков.
**Консенсус 14/14.** ✅ Подтверждено. Критическая проблема.

**B10.** Single-z fallback для <20 точек: 81% пар (4503/5561) получают антиконсервативный p-value. Разница до 24× против порядковой статистики.
**Консенсус 13/14.** ✅ Подтверждено.

**B11.** Chronology rate self-calibration: baseline строится из исследуемых данных, не калибровки. Нарушает documented policy «пороги только на calibration split».
**Консенсус 12/14.** ✅ Подтверждено. P0.

**B12.** Calibration: 7 человек — минимально допустимо. LOPO, person-balanced, contamination hardening — правильная архитектура, но репрезентативность недостаточна.
**Консенсус 14/14.** ✅ Подтверждено.

**B13.** Expression gate: `_pair_qc_decision()` исключает только отсутствие QC, `expression_gate()` всегда возвращает `accepted=True`. Мимика фактически не гейтится.
**Консенсус 11/14.** ✅ Подтверждено.

**B14.** Angle noise subtraction: результат записывается, но НЕ используется в скоринге/статусе. Ключ `angle_noise_compensated` не существовал. **Исправлено в раунде 1.**
**Консенсус 12/14.** ✅ Подтверждено + исправлено.

**B15.** Quality stratification: множители (1.0/1.45/2.05) вычисляются, но не применяются. `has_stratified_references` всегда False.
**Консенсус 10/14.** ✅ Подтверждено.

**B16.** Mesh канал = производный от alpha_id: `vertices_identity_only = compute_shape(alpha_id, 0)`. Не независимый канал, хотя помечен `forensic_measurement`.
**Консенсус 9/14.** ✅ Подтверждено.

**B17.** Pose leakage: ρ=0.463 между pose_distance и ldm134_rmse. Диагностируется, но не вычитается из метрик.
**Консенсус 14/14.** ✅ Подтверждено.

**B18.** Domain shift: meshRmse калибровка 0.0053 vs данные 0.0332 = 6.3×. Не объясняется позой/качеством/эпохой. Это доменный сдвиг, принятый за сигнал.
**Найдено аудитом #9.** ✅ Подтверждено. Критическая проблема.

**B19.** Coverage: 1064/5561 = 19.1% принято. Профили 0/1873. 75.2% — frontal. «9 ракурсных рядов» = 1 ряд frontal + 2 малых.
**Найдено аудитом #9.** ✅ Подтверждено.

**B20.** CalibrationModel._build_references: crash при <2 кластерах (`UnboundLocalError: ci`) или утечка CI из предыдущей метрики.
**Найдено аудитом #3.** ✅ Подтверждено.

### БЛОК C: КОД И АРХИТЕКТУРА

**C21.** IndentationError на main: engine.py не компилировался (4 места). **Исправлено в раунде 1.**
**Консенсус 6/6 проверивших.** ✅ Подтверждено + исправлено.

**C22.** Evidence state перезапись: date_provenance_limited/near_duplicate_limited терялись на втором проходе. **Исправлено в раунде 1.**
**Консенсус 14/14.** ✅ Подтверждено + исправлено.

**C23.** Двойной вызов write_postprocess_reports. **Исправлено в раунде 1.**
**Консенсус 8/14.** ✅ Подтверждено + исправлено.

**C24.** Мертвые модули: same_day_gate_v2 и irreversible_return написаны, протестированы, но не подключены в прогон. Документация маркирует как «сделано».
**Консенсус 12/14.** ✅ Подтверждено.

**C25.** Поле `pixels` не заполнялось → resolution_disparity gate мёртв. **Исправлено в раунде 1.**
**Консенсус 10/14.** ✅ Подтверждено + исправлено.

**C26.** quality_zones.npz не пишется в stage1. Stage2 корректно обрабатывает отсутствие (fail-closed).
**Консенсус 8/14.** ✅ Подтверждено. Не блокирует.

**C27.** Hash quartet (data/code/model/config) — воспроизводимость на высоком уровне. Atomic commits, schema versioning, checkpoint/resume.
**Консенсус 14/14.** ✅ Подтверждено. Сильнейшая сторона.

**C28.** Stage 2B падает на старте: требует `evidence_packets.json`, который Stage 2 больше не пишет.
**Найдено аудитом #7.** ⚠️ Требует проверки.

**C29.** `_persistence`: persistent = 2 смежных кандидата. Семантически «локальный кластер», не «устойчивое изменение».
**Консенсус 9/14.** ✅ Подтверждено.

**C30.** Cross-bin corroboration: `independent_source_count` вычисляется, но не используется как условие. Все 1909 кадров `source_provenance_status = not_provided`.
**Консенсус 8/14.** ✅ Подтверждено.

### БЛОК D: ЧТО ПОЛУЧИТ ЖУРНАЛИСТ

**D31.** Геометрические аномалии (persistent_geometric_change): 18 пар. Реальный сигнал, но persistence = 2 пары, не годы.
**Балл: 72/100.**

**D32.** Хронологические скачки: rapid_change, same_day, biologically_improbable — флаги работают, но self-calibrating baseline (круговая логика).
**Балл: 75/100.**

**D33.** Мини-флаги: 0 из 10 типов реализовано. Локальное исчезновение кожи, texture echo, cross-zone decoupling — ничего нет в коде.
**Балл: 0/100.**

**D34.** Комплексные аномалии: 0 из 10 комбо. Хроно-текстурный разрыв, мимическая маска, фантомная пластика — ничего нет.
**Балл: 0/100.**

**D35.** Многоканальное усиление: нет composite score. 3+ канала одновременно → верхний приоритет (ТЗ), но в коде каждый канал отдельно.
**Балл: 20/100.**

**D36.** Кросс-ракурсная корроборация: support count есть, но агрегация «N ракурсов × M эпох = strong evidence» отсутствует.
**Балл: 45/100.**

**D37.** Сквозные наблюдения: нет сущности Observation с ID, биографией, статусом. Журналист не получит «НАБЛ-014: впервые 2004, подтверждено 2007».
**Балл: 0/100.**

**D38.** Хронологический каркас: нет эпох, базовой линии, narrative от раннего к позднему. Stage 3 = приборная панель, не расследование.
**Балл: 10/100.**

**D39.** Готовые тезисы: 0 шаблонов для журналиста. 68 технических полей на пару, ни одной готовой фразы для статьи.
**Балл: 5/100.**

**D40.** Claim safety: FORBIDDEN_PUBLIC_TERMS блокирует «двойник/подмена/маска». Narrative честно отделяет наблюдение от интерпретации.
**Балл: 78/100.** Сильная сторона.

### БЛОК E: МЕТОДОЛОГИЧЕСКИЕ ВЫВОДЫ

**E41.** Система = скринер, не доказательство. Все 14 аудитов единогласны: результаты можно использовать для приоритизации ручной проверки, но не как самостоятельное доказательство.

**E42.** Kabsch alignment — отличное решение. Trimmed 15%, без scale, 5 итераций. Локальная аномалия не «перетягивает» глобальное выравнивание.
**Консенсус 14/14.**

**E43.** Raw object_normalized как primary — правильное решение. Chronology-aligned усиливает остаток при больших угловых разрывах (AUC падает 0.987→0.837).
**Консенсус 14/14.**

**E44.** Evidence layer — правильная архитектура. Measurement → applicability → evidence → interpretation. Каждый слой может downgradеить, но не повышать.
**Консенсус 13/14.**

**E45.** Fail-closed принципы: NaN ≠ 0, отсутствие данных ≠ измерение, разные ракурсы не смешиваются. Это сильная сторона проекта.
**Консенсус 14/14.**

**E46.** Era bias не компенсируется: VHS 1999 vs студия 2025 — стратифицированные пороги написаны, но не задействованы.
**Консенсус 10/14.**

**E47.** 3DDFA = «модельная галлюцинация» в судебном смысле. Монокулярная 3D-реконструкция — ill-posed inverse problem. Глубина восстанавливается из статистических априорных данных.
**Консенсус 12/14.**

**E48.** FDR inflation factor 5.83 — это m/(photo_count/2), не измеренная зависимость. Не имеет строгой математической базы.
**Консенсус 11/14.**

**E49.** Baseline return: первоначальный аудит заявил «100% triggers on noise» (косинус шума = -0.50). Финальный отчёт опроверг: реальная функция считает косинус по 134 точкам (axis=1), FP = 0.9%. **Базовый механизм работает корректно.**
**Опровергнуто в финальном отчёте.**

**E50.** Путь к доверию: (1) расширенная калибровка ≥30 персон, (2) эмпирический null из перестановок, (3) ground truth holdout, (4) устранение domain shift, (5) мини-флаги + composite score + наблюдения + тезисы.
**Консенсус 14/14.**

---

## СВОДНАЯ ТАБЛИЦА КОНСЕНСУСА 14 АУДИТОВ

| Категория | Кол-во выводов | Средний консенсус | Ключевые находки |
|---|---|---|---|
| A: Stage 1 (достоверность данных) | 8 | 11/14 | Pose bias 46%, texture = diagnostic, alpha weak |
| B: Stage 2 (статистика) | 12 | 12/14 | FDR занижен, 81% insufficient, domain shift 6.3× |
| C: Код и архитектура | 10 | 10/14 | 8 исправлено в раунде 1, hash quartet = сильнейшая сторона |
| D: Продукт для журналиста | 10 | — | Средний балл 29.7/100, мини-флаги = 0 |
| E: Методологические выводы | 10 | 13/14 | Скринер, не доказательство; Kabsch, raw, fail-closed = ✅ |

### Что подтверждено 14/14 аудитов:
1. Результаты нельзя предъявлять как доказательство
2. Архитектура — хорошая основа
3. Kabsch alignment — отличное решение
4. Raw object_normalized — правильный primary канал
5. Fail-closed принципы — сильная сторона
6. Pose bias реален (46% вариации)
7. Hash quartet — воспроизводимость на уровне
8. Texture = diagnostic only
9. Калибровка 7 человек — минимально допустимо
10. FDR на зависимых данных — критическая проблема

### Что исправлено в раунде 1 (8 ошибок):
1. IndentationError (компиляция)
2. Evidence state перезапись
3. Двойной вызов write_postprocess_reports
4. Ключ angle_noise_compensated
5. coordinate_noise_sigma fallback
6. Поле pixels
7. Мертвый imported:True
8. Отступы в engine.py
