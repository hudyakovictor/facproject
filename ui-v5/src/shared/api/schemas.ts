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
    /** Каталог метрик backend уже отдаёт; интерфейс его раньше отбрасывал. */
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
