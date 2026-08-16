export interface ResearchPhoto {
  id: string;
  date: string | null;
  t: number | null;
  bucket: string;
  era: string;
  quality: number | null;
  yaw: number | null;
  pitch: number | null;
  roll: number | null;
  fuzzy: string;
  measurementStatus: string;
  flags: string[];
  sourceMode: string;
  analysisStage: string;
  dateProvenanceStatus?: string | null;

  /**
   * Поля Stage 2. В режиме `stage1_inventory` backend их не присылает вовсе —
   * объявлять их обязательными означало бы гарантированный TypeError на первом
   * же `Object.entries(photo.stage2StatusCounts)`.
   */
  evidenceState?: string;
  stage2PairCount?: number;
  stage2StatusCounts?: Record<string, number>;
  stage2EvidenceCounts?: Record<string, number>;

  /** Поля, которые backend отдаёт, а интерфейс до сих пор отбрасывал. */
  qualityBasis?: string | null;
  boneScore?: number | null;
  orbit?: number | null;
  chin?: number | null;
  jaw?: number | null;
  cheek?: number | null;
  symmetry?: number | null;
  confidence?: number | null;
  siliconeProb?: number | null;
  fillerProb?: number | null;
  skinQuality?: number | null;
  wrinkleDensity?: number | null;
  subsurface?: number | null;
  visualAge?: number | null;
  calendarAge?: number | null;
  zOrbitDepth?: number | null;
  zChinProj?: number | null;
  zJawWidth?: number | null;
  zCheek?: number | null;
  p0?: number | null;
  p1?: number | null;
  p2?: number | null;
  dominant?: string | null;
  exifAnomaly?: boolean;
  dateProvenanceLimited?: boolean;
  bayesianProjectionAvailable?: boolean;

  /**
   * Сигналы честности контракта: какие обязательные поля отсутствуют именно у
   * этой записи. Источник — `validate_ui_row` в `app6/api/ui_fields.py`.
   */
  uiContractViolations?: string[];
  uiFieldsSchema?: string;
}

export interface ResearchTimeline {
  source_mode: string;
  not_a_verdict: boolean;
  note?: string;
  photos: ResearchPhoto[];
  era_meta: Record<string, { label: string; start: string; end: string }>;
  chronology_anomalies?: Record<string, unknown>;
  analysis_manifest?: Record<string, unknown>;

  /**
   * Режим, в котором получены данные. `stage1_inventory` означает, что Stage 2
   * ещё не выполнен и сравнительных метрик в ответе нет.
   */
  analysis_stage?: string;
  stage1_manifest?: Record<string, unknown> | null;

  /** Сводка соблюдения контракта полей по всему прогону. */
  ui_fields_schema?: string;
  ui_fields_complete_photo_count?: number;
  ui_fields_violations_by_field?: Record<string, number>;
}

export interface RunSummary {
  source_mode: string;
  not_a_verdict: boolean;
  categories?: Record<string, unknown>;
  technical_summary?: {
    change_point_count?: number;
    status_counts?: Record<string, number>;
    evidence_state_counts?: Record<string, number>;
    [key: string]: unknown;
  } | null;
}

export interface CalibrationHealth {
  schema: string;
  not_a_verdict: boolean;
  total_records: number;
  total_persons: number;
  confidence_counts: Record<string, number>;
  buckets: Record<string, { pose_bin: string; frame_count: number; person_count: number; confidence: string; runtime_usable: boolean }>;
  unreliable_buckets: string[];
  recommendations: string[];
  source: string;
}

import { getValidated, ApiError, ContractError } from "./api/client";
import { CalibrationHealthSchema, RunSummarySchema, TimelineSchema } from "./api/schemas";

export { ApiError, ContractError };

export function researchTimeline(): Promise<ResearchTimeline> {
  return getValidated("/api/v1/timeline", TimelineSchema) as Promise<ResearchTimeline>;
}

export function runSummary(): Promise<RunSummary> {
  return getValidated("/api/v1/run/summary", RunSummarySchema) as Promise<RunSummary>;
}

export function calibrationHealth(): Promise<CalibrationHealth> {
  return getValidated("/api/v1/calibration/health", CalibrationHealthSchema) as Promise<CalibrationHealth>;
}
