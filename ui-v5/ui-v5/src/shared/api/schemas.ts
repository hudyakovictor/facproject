import { z } from "zod";

/**
 * Схемы ответов API.
 *
 * До появления этого модуля `researchApi.ts` доверял ответу целиком: три вызова
 * `fetch` без валидации, без разбора ошибок и без единой проверки формы данных.
 * Расхождение контракта проявлялось не сообщением, а падением компонента или,
 * что хуже, показом неверного значения.
 *
 * Пакет `zod` был указан в зависимостях как «слой валидации», но не
 * импортировался ни разу.
 */

/** Число или явное отсутствие. `null` здесь семантически значим: это не ноль. */
const nullableNumber = z.number().finite().nullable();
const nullableString = z.string().nullable();

/**
 * Поля, общие для обеих стадий. Поля могут быть null/undefined если данных нет.
 * Ошибки валидации не маскируются — они возвращаются как 422 от сервера.
 */
const basePhoto = z.object({
  id: z.string(),
  date: nullableString.optional(),
  t: nullableNumber.optional(),
  bucket: z.string(),
  era: z.string().optional(),
  quality: nullableNumber,
  yaw: nullableNumber,
  pitch: nullableNumber,
  roll: nullableNumber,
  fuzzy: z.string().optional(),
  measurementStatus: z.string().optional(),
  flags: z.array(z.string()).optional(),
  sourceMode: z.string().optional().default("research"),
  analysisStage: z.string().optional().default("stage1_inventory"),
  dateProvenanceStatus: nullableString.optional(),

  qualityBasis: nullableString.optional(),
  boneScore: nullableNumber.optional(),
  orbit: nullableNumber.optional(),
  chin: nullableNumber.optional(),
  jaw: nullableNumber.optional(),
  cheek: nullableNumber.optional(),
  symmetry: nullableNumber.optional(),
  confidence: nullableNumber.optional(),
  siliconeProb: nullableNumber.optional(),
  fillerProb: nullableNumber.optional(),
  skinQuality: nullableNumber.optional(),
  wrinkleDensity: nullableNumber.optional(),
  subsurface: nullableNumber.optional(),
  visualAge: nullableNumber.optional(),
  calendarAge: nullableNumber.optional(),
  zOrbitDepth: nullableNumber.optional(),
  zChinProj: nullableNumber.optional(),
  zJawWidth: nullableNumber.optional(),
  zCheek: nullableNumber.optional(),
  p0: nullableNumber.optional(),
  p1: nullableNumber.optional(),
  p2: nullableNumber.optional(),
  dominant: nullableString.optional(),
  exifAnomaly: z.boolean().optional(),
  dateProvenanceLimited: z.boolean().optional(),
  bayesianProjectionAvailable: z.boolean().optional(),
  canonicalYaw: nullableNumber.optional(),
  poseConfidence: nullableNumber.optional(),
  detectionConfidence: nullableNumber.optional(),
  alignmentQuality: nullableNumber.optional(),
  expressionMagnitude: nullableNumber.optional(),
  jawOpenDegree: nullableNumber.optional(),
  jawOpenRatio: nullableNumber.optional(),
  jawOpenDetected: z.boolean().optional(),
  smileDetected: z.boolean().optional(),
  visibleLdm106: nullableNumber.optional(),
  visibleLdm134: nullableNumber.optional(),
  faceAreaRatio: nullableNumber.optional(),
  correctionMagnitude: nullableNumber.optional(),
  residualYaw: nullableNumber.optional(),
  residualPitch: nullableNumber.optional(),
  residualRoll: nullableNumber.optional(),
  skinAuthenticity: nullableNumber.optional(),
  uvCoverage: nullableNumber.optional(),
  laplacianVariance: nullableNumber.optional(),
  tenengradMean: nullableNumber.optional(),
  noiseResidual: nullableNumber.optional(),
  skinMaskCoverage: nullableNumber.optional(),

  uiContractViolations: z.array(z.string()).optional(),
  uiFieldsSchema: z.string().optional(),

  /**
   * Поля Stage 2 объявлены необязательными сознательно: `stage1_timeline.py`
   * их не присылает вовсе. Требовать их означало бы отвергать каждый корректный
   * ответ Stage 1.
   */
  evidenceState: z.string().optional(),
  stage2PairCount: z.number().optional(),
  stage2StatusCounts: z.record(z.string(), z.number()).optional(),
  stage2EvidenceCounts: z.record(z.string(), z.number()).optional(),
});

export const PhotoSchema = basePhoto.loose();

export const EraMetaSchema = z.record(
  z.string(),
  z.object({ label: z.string(), start: z.string(), end: z.string() }),
);

export const TimelineSchema = z
  .object({
    schema: z.string().optional(),
    source_mode: z.string().optional().default("research"),
    not_a_verdict: z.boolean().optional().default(true),
    note: z.string().optional(),
    photos: z.array(PhotoSchema).optional(),
    era_meta: EraMetaSchema.optional(),
    chronology_anomalies: z.record(z.string(), z.unknown()).optional(),
    analysis_manifest: z.record(z.string(), z.unknown()).optional(),
    analysis_stage: z.string().optional(),
    stage1_manifest: z.record(z.string(), z.unknown()).nullable().optional(),
    ui_fields_schema: z.string().optional(),
    ui_fields_complete_photo_count: z.number().optional(),
    ui_fields_violations_by_field: z.record(z.string(), z.number()).optional(),
  })
  .loose();

export const RunSummarySchema = z
  .object({
    source_mode: z.string().optional().default("research"),
    not_a_verdict: z.boolean().optional().default(true),
    categories: z.record(z.string(), z.unknown()).optional(),
    metric_catalog: z
      .union([z.record(z.string(), z.unknown()), z.array(z.record(z.string(), z.unknown()))])
      .optional(),
    artifacts: z
      .union([z.array(z.record(z.string(), z.unknown())), z.record(z.string(), z.unknown())])
      .optional(),
    category_titles: z
      .record(
        z.string(),
        z.union([z.string(), z.object({ ru: z.string().optional(), en: z.string().optional() }).loose()]),
      )
      .optional(),
    technical_summary: z
      .object({
        change_point_count: z.number().optional(),
        status_counts: z.record(z.string(), z.number()).optional(),
        evidence_state_counts: z.record(z.string(), z.number()).optional(),
      })
      .loose()
      .nullable()
      .optional(),
  })
  .loose();

export const CalibrationHealthSchema = z
  .object({
    schema: z.string().optional(),
    not_a_verdict: z.boolean().optional().default(true),
    total_records: z.number().optional(),
    total_persons: z.number().optional(),
    confidence_counts: z.record(z.string(), z.number()).optional(),
    buckets: z
      .record(
        z.string(),
        z.object({
          pose_bin: z.string(),
          frame_count: z.number(),
          person_count: z.number(),
          confidence: z.string(),
          runtime_usable: z.boolean(),
        }),
      )
      .catch({}),
    unreliable_buckets: z.array(z.string()).optional(),
    recommendations: z.array(z.string()).optional(),
    source: z.string().optional(),
  })
  .loose();

export type TimelineResponse = z.infer<typeof TimelineSchema>;
export type RunSummaryResponse = z.infer<typeof RunSummarySchema>;
export type CalibrationHealthResponse = z.infer<typeof CalibrationHealthSchema>;

/**
 * Проверка обязательных полей интерфейса, зеркало `REQUIRED_UI_FIELDS` из
 * `app6/api/ui_fields.py`. Расхождение версий схемы — повод предупредить
 * пользователя, а не молча показать неполные данные.
 */
export const UI_FIELDS_SCHEMA = "deeputin-ui-fields-v1.0";

/**
 * Задание пакетной обработки (`/api/v1/jobs`).
 *
 * Зеркало `app6/api/jobs.py`. Статус `blocked` существует потому, что backend
 * честно сообщает о невозможности выполнить извлечение без весов модели, а не
 * притворяется завершённым. Интерфейс обязан показывать это состояние как
 * отдельное, иначе «заблокировано» будет прочитано как «готово».
 */
export const JobSchema = z
  .object({
    schema: z.string().optional(),
    id: z.string(),
    kind: z.string(),
    status: z.enum(["queued", "running", "complete", "blocked", "failed", "cancelled"]).optional(),
    created_at: z.string().optional(),
    started_at: z.string().nullable().optional(),
    finished_at: z.string().nullable().optional(),
    progress: z
      .object({ done: z.number().optional(), total: z.number().optional() }),
    logs: z.array(z.string()).catch([]),
    result: z.record(z.string(), z.unknown()).nullable().optional(),
    error: z.string().nullable().optional(),
  })
  .loose();

export const JobListSchema = z
  .object({ schema: z.string().optional(), jobs: z.array(JobSchema) })
  .loose();

export const JobSubmitSchema = z
  .object({ schema: z.string().optional(), job_id: z.string() })
  .loose();

export const JobCancelSchema = z
  .object({ schema: z.string().optional(), cancelled: z.string() })
  .loose();

/** Инвентарь Stage 1 (`/api/v1/photos`) — постраничный список без изображений. */
export const PhotoInventorySchema = z
  .object({
    schema: z.string().optional(),
    source_mode: z.string().optional().default("research"),
    manifest: z.record(z.string(), z.unknown()).optional(),
    count: z.number().optional(),
    offset: z.number().optional(),
    limit: z.number().optional(),
    photos: z
      .array(
        z
          .object({
            id: z.string(),
            date: z.string().nullable().optional(),
            bucket: z.string().optional(),
          })
          .loose(),
      )
      .optional(),
  })
  .loose();

export const UploadResultSchema = z
  .object({
    schema: z.string().optional(),
    stored: z.string().optional(),
    filename: z.string().optional(),
    path: z.string().optional(),
  })
  .loose();
export const DeleteResultSchema = z
  .object({ schema: z.string().optional(), deleted: z.string() })
  .loose();

export type Job = z.infer<typeof JobSchema>;
export type PhotoInventory = z.infer<typeof PhotoInventorySchema>;

// ---------------------------------------------------------------------------
// Инспектор кадра (§10)
// ---------------------------------------------------------------------------

/**
 * Полный `info.json` кадра (`/api/v1/photos/{id}/info_keys`).
 *
 * Stage 1 сохраняет около 156 листовых ключей на кадр: параметры декодирования,
 * провенанс даты, позу, репроекцию, качество кожи, перечень файлов. Интерфейс
 * до сих пор использовал восемь из них. Схема намеренно не перечисляет ключи
 * поимённо: список зависит от версии пайплайна, и жёсткий перечень превратил бы
 * появление нового ключа в ошибку контракта. Разбор по категориям — в
 * `infoKeys.ts`, там же живут русские заголовки.
 */
export const PhotoInfoKeysSchema = z
  .object({
    schema: z.string().optional(),
    photo_id: z.string(),
    info: z.record(z.string(), z.unknown()).optional(),
    validation: z.record(z.string(), z.unknown()).optional(),
    texture: z.record(z.string(), z.unknown()).optional(),
    artifacts: z.array(z.string()).optional(),
  })
  .loose();

/**
 * Зоны кожи кадра (`/api/v1/photos/{id}/skin_zones`).
 *
 * `status` отличает измеренную зону от закрытой ракурс��м или исключённой
 * сегментацией. Без этого различия пустая зона неотличима от нулевого
 * значения — а это ровно та подмена, которую запрещает `app6/AGENTS.md`.
 */
export const SkinZoneSchema = z
  .object({
    // Зона, которой нет в атласе, приходит без zone_id — это нормальный
    // случай, а не повреждённый ответ, поэтому поле nullable.
    zone_id: z.string().nullable().optional(),
    name: z.string().optional(),
    label_ru: z.string().optional(),
    group: z.string().nullable().optional(),
    side: z.string().nullable().optional(),
    /** `active` | `excluded` | `no_data` — словарь задан backend (ZONE_STATUSES). */
    status: z.string().optional(),
    exclusion_reasons: z.array(z.string()).optional(),
    // --- skin_zone_quality.json ---
    visible_fraction: z.number().nullable().optional(),
    skin_pixels: z.number().nullable().optional(),
    quality: z.number().nullable().optional(),
    // --- quality.json → per_zone_quality ---
    texture_score: z.number().nullable().optional(),
    texture_usable: z.boolean().nullable().optional(),
    quality_class: z.string().nullable().optional(),
    laplacian_var: z.number().nullable().optional(),
    tenengrad_mean: z.number().nullable().optional(),
    highlight_fraction: z.number().nullable().optional(),
    shadow_fraction: z.number().nullable().optional(),
    skin_fraction: z.number().nullable().optional(),
    texture_pixels: z.number().nullable().optional(),
    roi_source: z.string().nullable().optional(),
  })
  .loose();

export const SkinZonesSchema = z
  .object({
    schema: z.string().optional(),
    photo_id: z.string(),
    pose_bin: z.string().nullable().optional(),
    skin_mask_coverage: z.number().nullable().optional(),
    zone_count: z.number().optional(),
    active_zone_count: z.number().optional(),
    excluded_zone_count: z.number().optional(),
    no_data_zone_count: z.number().optional(),
    zones: z.array(SkinZoneSchema).catch([]),
    /** Честный перечень того, какие артефакты Stage 1 реально нашлись. */
    available_sources: z
      .object({
        skin_zone_quality: z.boolean().optional(),
        per_zone_quality: z.boolean().optional(),
        wrinkle_zones: z.boolean().optional(),
        wrinkle_note: z.string().optional(),
      })
      .loose()
      .nullable()
      .catch(null),
  })
  .loose();

/** Атлас зон кожи (`/api/v1/zones/catalog`) — 40 зон с русскими названиями. */
export const ZoneCatalogSchema = z
  .object({
    schema: z.string().optional(),
    schema_version: z.string().optional(),
    zone_count: z.number().optional(),
    primary_policy: z.string().nullable().optional(),
    photo_mask_formula: z.string().nullable().optional(),
    zones: z
      .array(
        z
          .object({
            zone_id: z.string(),
            name: z.string().catch(""),
            label_ru: z.string().catch(""),
            group: z.string().catch(""),
            side: z.string().catch(""),
            seed_uv: z.array(z.number()).catch([]),
            scale_uv: z.array(z.number()).catch([]),
          })
          .loose(),
      )
      .catch([]),
  })
  .loose();

/**
 * Ландмарки кадра (`/api/v1/photos/{id}/landmarks/{count}/{space}`).
 *
 * `space` существенен: `original` — пиксели исходного кадра, `raw` — объект с
 * выражением, `aligned` — нормировка по RMS с каноническим yaw, `chronology` —
 * полная коррекция позы. Наложить `chronology` на исходное изображение нельзя,
 * поэтому пространство показывается пользователю, а не выбирается молча.
 */
export const LandmarksSchema = z
  .object({
    schema: z.string().optional(),
    photo_id: z.string(),
    count: z.number().optional(),
    space: z.string().optional(),
    columns: z.array(z.string()).optional(),
    points: z.array(z.array(z.number())).optional(),
  })
  .loose();

export type PhotoInfoKeys = z.infer<typeof PhotoInfoKeysSchema>;
export type SkinZone = z.infer<typeof SkinZoneSchema>;
export type SkinZones = z.infer<typeof SkinZonesSchema>;
export type ZoneCatalog = z.infer<typeof ZoneCatalogSchema>;
export type Landmarks = z.infer<typeof LandmarksSchema>;

// ---------------------------------------------------------------------------
// Отчёт Stage 3
// ---------------------------------------------------------------------------

/**
 * Секции отчёта описываются самим backend: `present` и `size` — это
 * факт наличия данных, а не обещание фронтенда. Перечисля��ь имена
 * секций константой в UI нельзя: список задаёт Stage 3.
 */
export const ReportSectionListItemSchema = z
  .object({
    name: z.string(),
    title: z.string().optional(),
    present: z.boolean().optional(),
    size: z.number().nullable().optional(),
    paged: z.boolean().optional(),
  })
  .loose();

export const ReportSummarySchema = z
  .object({
    schema: z.string().optional(),
    not_a_verdict: z.boolean().optional(),
    source_mode: z.string().optional().default("research"),
    report_schema_version: z.string().nullable().optional(),
    stage2_schema_version: z.string().nullable().optional(),
    created_at_utc: z.string().nullable().optional(),
    summary: z.record(z.string(), z.unknown()).optional(),
    narrative: z.array(z.unknown()).optional(),
    methodology: z.record(z.string(), z.unknown()).optional(),
    validation: z.unknown().nullable().optional(),
    sections: z.array(ReportSectionListItemSchema).optional(),
    status_semantics: z.record(z.string(), z.string()).optional(),
    withheld_column_prefixes: z.array(z.string()).optional(),
    withheld_note: z.string().nullable().optional(),
  })
  .loose();

export const ReportSectionSchema = z
  .object({
    schema: z.string().optional(),
    not_a_verdict: z.boolean().optional(),
    name: z.string(),
    title: z.string(),
    present: z.boolean().optional(),
    total: z.number().nullable().optional(),
    offset: z.number().nullable().optional(),
    returned: z.number().nullable().optional(),
    paged: z.boolean().optional(),
    payload: z.unknown(),
  })
  .loose();

export const RunArtifactSchema = z
  .object({
    schema: z.string().optional(),
    not_a_verdict: z.boolean().optional(),
    name: z.string(),
    format: z.string().optional(),
    category: z.string().optional(),
    purpose: z.string().optional(),
    size_bytes: z.number().nullable().optional(),
    truncated: z.boolean().optional(),
    row_count: z.number().nullable().optional(),
    payload: z.unknown().nullable(),
  })
  .loose();

export type ReportSectionListItem = z.infer<typeof ReportSectionListItemSchema>;
export type ReportSummary = z.infer<typeof ReportSummarySchema>;
export type ReportSection = z.infer<typeof ReportSectionSchema>;
export type RunArtifact = z.infer<typeof RunArtifactSchema>;

// ---------------------------------------------------------------------------
// Парное сравнение (§11)
// ---------------------------------------------------------------------------

/**
 * Значение одной колонки `pair_metrics.csv`. Backend уже привёл типы
 * (`key_catalog.coerce`): пустая строка и `nan` стали `null`.
 *
 * 🚨 WARNING: `null` здесь означает «Stage 2 не смог измерить», а не ноль.
 * Из 208 колонок на реальной паре заполнены 182 — оставшиеся 26 обязаны
 * выглядеть как пропуск, иначе «мера равна нулю» будет прочитано как
 * «различий нет».
 */
const MetricValueSchema = z.union([z.number(), z.string(), z.boolean(), z.null()]);

/**
 * Метрики пары (`/api/v1/pairs/{a}/{b}/metrics`).
 *
 * Структура — три уровня: категория A–I → подгруппа → колонка. Она приходит
 * от `key_catalog.categorize_pair_columns`, и интерфейс её не переизобретает:
 * своя группировка разошлась бы с backend при первой же новой колонке.
 */
export const PairMetricsSchema = z
  .object({
    schema: z.string().optional(),
    not_a_verdict: z.boolean().optional(),
    source_mode: z.string().optional().default("research"),
    photo_a: z.string(),
    photo_b: z.string(),
    /** Stage 2 хранит хронологический порядок; пользователь мог выбрать обратный. */
reversed_order: z.boolean().optional(),
    column_count: z.number().optional(),
    available_count: z.number().optional(),
    category_titles: z
      .record(z.string(), z.object({ ru: z.string(), en: z.string() }).loose())
      .optional(),
    categories: z
      .record(z.string(), z.record(z.string(), z.record(z.string(), MetricValueSchema)))
      .optional(),
  })
  .loose();

/** Список пар прогона (`/api/v1/pairs`). */
export const PairListSchema = z
  .object({
    schema: z.string().optional(),
    count: z.number().optional(),
    pairs: z
      .array(
        z
          .object({
            pair_id: z.string(),
            photo_a: z.string(),
            photo_b: z.string(),
            pose_bin: z.string().nullable().optional(),
            date_a: z.string().nullable().optional(),
            date_b: z.string().nullable().optional(),
            status: z.string().nullable().optional(),
            evidence_state: z.string().nullable().optional(),
            pair_type: z.string().nullable().optional(),
          })
          .loose(),
      )
      .optional(),
  })
  .loose();

export type PairMetrics = z.infer<typeof PairMetricsSchema>;
export type PairList = z.infer<typeof PairListSchema>;
export type MetricValue = z.infer<typeof MetricValueSchema>;
