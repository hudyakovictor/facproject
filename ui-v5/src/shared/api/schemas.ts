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
const nullableNumber = z.number().finite().nullable().catch(null);
const nullableString = z.string().nullable().catch(null);

/**
 * Поля, общие для обеих стадий. `.catch()` не маскирует ошибки: он переводит
 * непредвиденное значение в честное «нет данных», а несоответствие фиксируется
 * отдельно в `collectContractIssues`.
 */
const basePhoto = z.object({
  id: z.string(),
  date: nullableString,
  t: nullableNumber,
  bucket: z.string().catch("unknown"),
  era: z.string().catch("unknown"),
  quality: nullableNumber,
  yaw: nullableNumber,
  pitch: nullableNumber,
  roll: nullableNumber,
  fuzzy: z.string().catch(""),
  measurementStatus: z.string().catch("unknown"),
  flags: z.array(z.string()).catch([]),
  sourceMode: z.string().catch("research"),
  analysisStage: z.string().catch("stage1_inventory"),
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
    source_mode: z.string().catch("research"),
    not_a_verdict: z.boolean().catch(true),
    note: z.string().optional(),
    photos: z.array(PhotoSchema).catch([]),
    era_meta: EraMetaSchema.catch({}),
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
    source_mode: z.string().catch("research"),
    not_a_verdict: z.boolean().catch(true),
    categories: z.record(z.string(), z.unknown()).optional(),
    /**
     * Каталог метрик. Поле объявлено на будущее (задача B-09): текущий backend
     * его не присылает, поэтому подписи ведутся в `shared/metrics.ts`.
     * Ранний аудит утверждал обратное — это была ошибка.
     */
    metric_catalog: z.array(z.record(z.string(), z.unknown())).optional(),
    artifacts: z.record(z.string(), z.unknown()).optional(),
    category_titles: z.record(z.string(), z.string()).optional(),
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
    schema: z.string().catch(""),
    not_a_verdict: z.boolean().catch(true),
    total_records: z.number().catch(0),
    total_persons: z.number().catch(0),
    confidence_counts: z.record(z.string(), z.number()).catch({}),
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
    unreliable_buckets: z.array(z.string()).catch([]),
    recommendations: z.array(z.string()).catch([]),
    source: z.string().catch("н/д"),
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
    status: z.enum(["queued", "running", "complete", "blocked", "failed", "cancelled"]).catch("queued"),
    created_at: z.string().optional(),
    started_at: z.string().nullable().optional(),
    finished_at: z.string().nullable().optional(),
    progress: z
      .object({ done: z.number().catch(0), total: z.number().catch(0) })
      .catch({ done: 0, total: 0 }),
    logs: z.array(z.string()).catch([]),
    result: z.record(z.string(), z.unknown()).nullable().optional(),
    error: z.string().nullable().optional(),
  })
  .loose();

export const JobListSchema = z
  .object({ schema: z.string().optional(), jobs: z.array(JobSchema).catch([]) })
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
    source_mode: z.string().catch("research"),
    manifest: z.record(z.string(), z.unknown()).catch({}),
    count: z.number().catch(0),
    offset: z.number().catch(0),
    limit: z.number().catch(0),
    photos: z
      .array(
        z
          .object({
            id: z.string(),
            date: z.string().nullable().catch(null),
            bucket: z.string().catch("unknown"),
          })
          .loose(),
      )
      .catch([]),
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
    info: z.record(z.string(), z.unknown()).catch({}),
    validation: z.record(z.string(), z.unknown()).catch({}),
    texture: z.record(z.string(), z.unknown()).catch({}),
    artifacts: z.array(z.string()).catch([]),
  })
  .loose();

/**
 * Зоны кожи кадра (`/api/v1/photos/{id}/skin_zones`).
 *
 * `status` отличает измеренную зону от закрытой ракурсом или исключённой
 * сегментацией. Без этого различия пустая зона неотличима от нулевого
 * значения — а это ровно та подмена, которую запрещает `app6/AGENTS.md`.
 */
export const SkinZoneSchema = z
  .object({
    zone_id: z.string(),
    name: z.string().catch(""),
    label_ru: z.string().catch(""),
    group: z.string().catch(""),
    side: z.string().catch(""),
    status: z.string().catch("unknown"),
    pixel_count: z.number().nullable().catch(null),
    metrics: z.record(z.string(), z.number().nullable()).catch({}),
  })
  .loose();

export const SkinZonesSchema = z
  .object({
    schema: z.string().optional(),
    photo_id: z.string(),
    zone_count: z.number().catch(0),
    zones: z.array(SkinZoneSchema).catch([]),
  })
  .loose();

/** Атлас зон кожи (`/api/v1/zones/catalog`) — 40 зон с русскими названиями. */
export const ZoneCatalogSchema = z
  .object({
    schema: z.string().optional(),
    schema_version: z.string().optional(),
    zone_count: z.number().catch(0),
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
    count: z.number().catch(0),
    space: z.string().catch(""),
    columns: z.array(z.string()).catch([]),
    points: z.array(z.array(z.number())).catch([]),
  })
  .loose();

export type PhotoInfoKeys = z.infer<typeof PhotoInfoKeysSchema>;
export type SkinZone = z.infer<typeof SkinZoneSchema>;
export type SkinZones = z.infer<typeof SkinZonesSchema>;
export type ZoneCatalog = z.infer<typeof ZoneCatalogSchema>;
export type Landmarks = z.infer<typeof LandmarksSchema>;
