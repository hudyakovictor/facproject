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

import { consoleLogger } from "./logger";

/**
 * Ошибка обращения к API с сохранённым контекстом.
 *
 * Раньше запрос падал обычным `Error` со склеенной строкой, и экраны показывали
 * либо «не удалось загрузить», либо — что хуже — текст про нехватку данных.
 * Теперь код ответа, endpoint и `detail` от FastAPI доступны интерфейсу и
 * попадают в журнал.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly endpoint: string;
  readonly detail: string;

  constructor(status: number, endpoint: string, detail: string) {
    super(`API ${status} ${endpoint}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.endpoint = endpoint;
    this.detail = detail;
  }
}

/** Таймаут одного запроса. Без него зависший backend оставляет вечный спиннер. */
const REQUEST_TIMEOUT_MS = 30_000;

function extractDetail(body: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (parsed.detail != null) return JSON.stringify(parsed.detail);
  } catch {
    /* тело не JSON — вернём как есть */
  }
  return body.slice(0, 400) || "Ответ без описания причины.";
}

async function get<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(path, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) {
      const detail = extractDetail(await response.text());
      consoleLogger.addLog("ERROR", "API", `${response.status} ${path}`, detail);
      throw new ApiError(response.status, path, detail);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const aborted = error instanceof DOMException && error.name === "AbortError";
    const message = aborted
      ? `Превышено время ожидания ${REQUEST_TIMEOUT_MS / 1000} с`
      : error instanceof Error
        ? error.message
        : String(error);
    consoleLogger.addLog("ERROR", "API", `Сбой запроса ${path}`, message);
    throw new ApiError(0, path, message);
  } finally {
    clearTimeout(timer);
  }
}

export function researchTimeline(): Promise<ResearchTimeline> {
  return get<ResearchTimeline>("/api/v1/timeline");
}

export function runSummary(): Promise<RunSummary> {
  return get<RunSummary>("/api/v1/run/summary");
}

export function calibrationHealth(): Promise<CalibrationHealth> {
  return get<CalibrationHealth>("/api/v1/calibration/health");
}
