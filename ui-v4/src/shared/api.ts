import { POSES, type Era, type Photo, type TimelineData } from "./types";
import { log, scheduleFlush } from "./logger";

const POSE_SET = new Set<string>(POSES);
const REQUIRED = ["id", "date", "t", "era", "bucket"] as const;
const NUMERIC = ["quality", "confidence", "boneScore", "yaw", "pitch", "roll"] as const;

/** Same-origin by default; matches the proven UI v2/app6 contract. */
export function apiBase(): string {
  return ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "").replace(/\/$/, "");
}

function extractApiError(body: string): string {
  const text = body.trim();
  if (!text) return "";
  try {
    const parsed = JSON.parse(text) as unknown;
    if (typeof parsed === "string") return parsed;
    if (parsed && typeof parsed === "object") {
      const obj = parsed as Record<string, unknown>;
      for (const key of ["detail", "error", "message"]) {
        const value = obj[key];
        if (typeof value === "string") return value;
        if (Array.isArray(value)) {
          const messages = value.map(item => item && typeof item === "object" ? (item as Record<string, unknown>).msg : item).filter((x): x is string => typeof x === "string");
          if (messages.length) return messages.join("; ");
        }
      }
      return JSON.stringify(parsed).slice(0, 500);
    }
  } catch { /* plain-text response */ }
  return text.slice(0, 500);
}

async function apiJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 45_000);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init?.body !== undefined && init.body !== null) headers["Content-Type"] = "application/json";
  try {
    const response = await fetch(`${apiBase()}${path}`, {
      ...init,
      signal: init?.signal ?? controller.signal,
      headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      const detail = extractApiError(body);
      const message = `HTTP ${response.status} ${path}${detail ? `: ${detail}` : ""}`;
      log(response.status >= 500 ? "error" : "warn", "api", message, { detail, path });
      scheduleFlush();
      throw new Error(message);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("HTTP")) throw error;
    const message = error instanceof Error ? error.message : String(error);
    log("error", "api", `${init?.method ?? "GET"} ${path} failed`, { detail: message, path });
    scheduleFlush();
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

function finite(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : Number.NaN;
}

function validatePhoto(value: unknown, knownEras: ReadonlySet<string>): Photo {
  if (!value || typeof value !== "object") throw new Error("строка не является объектом");
  const row = value as Record<string, unknown>;
  const missing = REQUIRED.filter(key => !(key in row));
  if (missing.length) throw new Error(`нет обязательных полей: ${missing.join(", ")}`);
  if (typeof row.id !== "string") throw new Error("id не строка");
  if (typeof row.date !== "string") throw new Error("date не строка");
  if (typeof row.t !== "number" || !Number.isFinite(row.t)) throw new Error("t не конечное число");
  const bucket = String(row.bucket);
  if (!POSE_SET.has(bucket)) throw new Error(`неизвестный pose bin: ${bucket}`);
  const era = String(row.era);
  if (!era) throw new Error("пустой era");
  if (knownEras.size && !knownEras.has(era)) throw new Error(`сегмент ${era} отсутствует в era_meta`);
  const normalized = { ...row, id: row.id, date: row.date, t: row.t, era, bucket, flags: Array.isArray(row.flags) ? row.flags.map(String) : [] } as Record<string, unknown>;
  for (const field of NUMERIC) normalized[field] = finite(row[field]);
  return normalized as unknown as Photo;
}

function buildEraMeta(raw: Record<string, Partial<Era>> | undefined, photos: Photo[]): Record<string, Era> {
  const result: Record<string, Era> = {};
  const colors = ["#68c3cf", "#efb84d", "#e47c88", "#ff9856", "#ae7de1", "#65bd82"];
  const keys = [...new Set([...Object.keys(raw || {}), ...photos.map(photo => photo.era)])];
  keys.forEach((key, index) => {
    const meta = raw?.[key] || {};
    const timestamps = photos.filter(photo => photo.era === key).map(photo => photo.t);
    result[key] = {
      label: meta.label || key,
      short: meta.short || meta.label || key,
      start: meta.start || (timestamps.length ? new Date(Math.min(...timestamps)).toISOString().slice(0, 10) : ""),
      end: meta.end || (timestamps.length ? new Date(Math.max(...timestamps)).toISOString().slice(0, 10) : ""),
      color: meta.color || colors[index % colors.length],
    };
  });
  return result;
}

export async function timeline(signal?: AbortSignal): Promise<TimelineData> {
  try {
    const configured = import.meta.env.VITE_TIMELINE_API_URL as string | undefined;
    const endpoint = configured || `${apiBase()}/api/v1/timeline`;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 60_000);
    let response: Response;
    try {
      response = await fetch(endpoint, { signal: signal ?? controller.signal, headers: { Accept: "application/json" } });
    } finally {
      window.clearTimeout(timer);
    }
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      const message = `Timeline unavailable: HTTP ${response.status}${body ? ` · ${extractApiError(body)}` : ""}`;
      log("warn", "timeline", message, { path: endpoint });
      scheduleFlush();
      throw new Error(message);
    }
    const payload = await response.json() as { photos?: unknown[]; items?: unknown[]; source_mode?: string; analysis_stage?: string; note?: string; era_meta?: Record<string, Partial<Era>> } | unknown[];
    if (!Array.isArray(payload) && payload.source_mode !== "research") throw new Error(`Non-research timeline rejected (source_mode=${String(payload.source_mode ?? "missing")})`);
    const rows = Array.isArray(payload) ? payload : payload.photos ?? payload.items ?? [];
    const eraRaw = Array.isArray(payload) ? undefined : payload.era_meta;
    const knownEras = new Set(Object.keys(eraRaw || {}));
    const photos: Photo[] = [];
    const rejected: { id: string; reason: string }[] = [];
    for (const row of rows) {
      try { photos.push(validatePhoto(row, knownEras)); }
      catch (error) {
        const id = row && typeof row === "object" && "id" in row ? String((row as { id: unknown }).id) : "<без id>";
        rejected.push({ id, reason: error instanceof Error ? error.message : String(error) });
      }
    }
    photos.sort((a, b) => a.t - b.t || a.id.localeCompare(b.id));
    if (!photos.length) {
      const detail = rejected.length ? `; rejected ${rejected.length}: ${rejected[0].reason}` : "";
      throw new Error(`Research API returned no valid photo rows${detail}`);
    }
    return {
      photos,
      mode: "research",
      message: `${photos.length} records · verified research source${rejected.length ? ` · rejected: ${rejected.length}` : ""}${!Array.isArray(payload) && payload.note ? ` · ${payload.note}` : ""}`,
      eras: buildEraMeta(eraRaw, photos),
      rejected,
    };
  } catch (error) {
    if (signal?.aborted) throw error;
    return { photos: [], mode: "error", message: error instanceof Error ? error.message : String(error), eras: {}, rejected: [] };
  }
}

export type PhotoImageKind = "original" | "thumbnail" | "face_crop" | "uv_texture" | "zones_overlay";
export function image(id: string, kind: PhotoImageKind = "thumbnail"): string {
  return `${apiBase()}/api/v1/photos/${encodeURIComponent(id)}/image?kind=${kind}`;
}

export const detail = (id: string) => apiJson<Record<string, unknown>>(`/api/v1/photos/${encodeURIComponent(id)}`);
export const info = (id: string) => apiJson<Record<string, unknown>>(`/api/v1/photos/${encodeURIComponent(id)}/info_keys`);
export const skin = (id: string) => apiJson<Record<string, unknown>>(`/api/v1/photos/${encodeURIComponent(id)}/skin_zones`);
export const pair = (a: string, b: string) => apiJson<Record<string, unknown>>(`/api/v1/pairs/${encodeURIComponent(a)}/${encodeURIComponent(b)}/metrics`);
export const health = () => apiJson<Record<string, unknown>>("/api/v1/health");
export const calibrationHealth = () => apiJson<Record<string, unknown>>("/api/v1/calibration/health");
export const systemHealth = () => apiJson<Record<string, unknown>>("/api/v1/system/health");
export const runSummary = () => apiJson<Record<string, unknown>>("/api/v1/run/summary");
export const runArtifact = (name: string) => apiJson<Record<string, unknown>>(`/api/v1/run/artifacts/${encodeURIComponent(name)}`);
export const reportSummary = () => apiJson<Record<string, unknown>>("/api/v1/report/summary");
export const reportSection = (name: string, limit = 200, offset = 0) => apiJson<Record<string, unknown>>(`/api/v1/report/sections/${encodeURIComponent(name)}?limit=${limit}&offset=${offset}`);

export interface ThresholdSettings {
  confidence_min: number;
  quality_min: number;
  geometry_zone_delta_limit: number;
  texture_zone_delta_limit: number;
  expression_smile: number;
  expression_jaw_open: number;
}
export interface AppSettings {
  schema: string;
  threshold_mode?: "diagnostic_only" | "calibrated";
  thresholds: ThresholdSettings;
  heatmap: { stop_blue_cyan: number; stop_cyan_green: number; stop_green_red: number; stop_saturated_red: number; max_residual_reference: number };
  landmark_shift?: { tolerance: number; suspect: number; calibrated: boolean };
  detail_level: string;
  language: string;
}
export type JobStatus = "queued" | "running" | "complete" | "blocked" | "failed" | "cancelled";
export interface JobRow {
  id: string; kind: string; status: JobStatus; created_at?: string;
  started_at?: string | null; finished_at?: string | null;
  progress?: { done: number; total: number }; logs?: string[];
  result?: Record<string, unknown> | null; error?: string | null;
  phases?: AnalysisRunPhase[]; run_id?: string | null; profile_id?: string | null;
}
export interface UploadResult { photo_id: string; date: string | null; stored: boolean; message: string }
export interface MeshPayload {
  source_mode?: string; id?: string; vertices: [number, number, number][];
  triangles: [number, number, number][]; vertex_count?: number; triangle_count?: number;
}
export const fetchSettings = () => apiJson<AppSettings>("/api/v1/settings");
export const saveSettings = (settings: AppSettings) => apiJson<AppSettings>("/api/v1/settings", { method: "PUT", body: JSON.stringify(settings) });
export const resetSettings = () => apiJson<AppSettings>("/api/v1/settings/reset", { method: "POST" });
export async function listJobs(): Promise<JobRow[]> { return (await apiJson<{ jobs: JobRow[] }>("/api/v1/jobs")).jobs || [] }
export async function submitExtractJob(extra: Record<string, unknown>): Promise<string> { return (await apiJson<{ job_id: string }>("/api/v1/jobs", { method: "POST", body: JSON.stringify({ kind: "extract", ...extra }) })).job_id }
export const cancelJob = (id: string) => apiJson<unknown>(`/api/v1/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" });
export const clearExtractedData = () => apiJson<{ removed?: string[]; note?: string }>("/api/v1/data/clear", { method: "POST" });
export async function uploadPhoto(file: File): Promise<UploadResult> {
  const form = new FormData(); form.append("file", file);
  const response = await fetch(`${apiBase()}/api/v1/photos/upload`, { method: "POST", body: form });
  const raw = await response.text().catch(() => "");
  if (!response.ok) throw new Error(`HTTP ${response.status} /api/v1/photos/upload${raw ? `: ${extractApiError(raw)}` : ""}`);
  return JSON.parse(raw) as UploadResult;
}
export const photoMesh = (id: string, lod = 1) => apiJson<MeshPayload>(`/api/v1/photos/${encodeURIComponent(id)}/mesh?lod=${lod}`);
/** Artifact endpoints are implemented directly by app6/api/server.py. */
export const photoArtifactJson = (id: string, name: "texture.json" | "info.json") => apiJson<Record<string, unknown>>(`/api/v1/photos/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(name)}`);
export const photoArtifactUrl = (id: string, name: "face_mask.png") => `${apiBase()}/api/v1/photos/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(name)}`;

export type LandmarkSpace = "raw" | "aligned" | "original";
export interface LandmarkPayload { photo_id: string; count: 106 | 134; space: LandmarkSpace; coordinate_space?: string; points: [number, number, number][]; source_file?: string }
export const photoLandmarks = (id: string, count: 106 | 134, space: LandmarkSpace) => apiJson<LandmarkPayload>(`/api/v1/photos/${encodeURIComponent(id)}/landmarks/${count}/${space}`);

export interface DatasetStageInventory {
  status: "ready" | "limited" | "unavailable" | string;
  root?: string;
  record_count?: number;
  valid_id_count?: number;
  ready_record_count?: number;
  incomplete_record_count?: number;
  date_range?: { start?: string | null; end?: string | null };
  pose_counts?: Record<string, number>;
  year_counts?: Record<string, number>;
  issue_counts?: Record<string, number>;
  index_sha256?: string | null;
  manifest_sha256?: string | null;
  person_count?: number;
  provenance?: {
    date_conflict_count?: number;
    near_duplicate_count?: number;
    exact_duplicate_count?: number;
  };
}
export interface DatasetInventory {
  schema?: string;
  status: "ready" | "limited" | "blocked" | string;
  stage1: DatasetStageInventory;
  calibration: DatasetStageInventory;
  paths?: Record<string, string>;
  active_registration?: Record<string, unknown> | null;
  not_a_verdict?: boolean;
}
export interface DatasetIssue {
  photo_id?: string;
  category: string;
  detail: string;
  row?: number;
}
export interface DatasetIssueReport {
  total: number;
  offset: number;
  limit: number;
  category?: string | null;
  category_counts: Record<string, number>;
  issues: DatasetIssue[];
}
export const fetchRuntimePaths = () => apiJson<Record<string, unknown>>("/api/v1/runtime/paths");
export const fetchDatasetInventory = () => apiJson<DatasetInventory>("/api/v1/datasets/inventory");
export const activateDataset = (payload?: { label?: string; notes?: string }) =>
  apiJson<{ activated: boolean; path: string; registration: Record<string, unknown> }>("/api/v1/datasets/activate", {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
export const fetchDatasetIssues = (params?: { offset?: number; limit?: number; category?: string }) => {
  const query = new URLSearchParams();
  query.set("offset", String(params?.offset ?? 0));
  query.set("limit", String(params?.limit ?? 100));
  if (params?.category) query.set("category", params.category);
  return apiJson<DatasetIssueReport>(`/api/v1/datasets/issues?${query.toString()}`);
};

export type QualityFilterKey =
  | "visibility"
  | "confidence"
  | "faceResolution"
  | "blur"
  | "exposure"
  | "occlusion"
  | "reconstructionResidual"
  | "alignmentQuality"
  | "landmarkVisibility"
  | "textureApplicability"
  | "expressionMagnitude"
  | "jawOpenRatio"
  | "smileScore";

export interface FilterRange { min: number | null; max: number | null }
export interface PoseOutlierConfig {
  enabled: boolean;
  method: "mad" | "percentile" | string;
  masterPercentile: number;
  yawLimit: number | null;
  pitchLimit: number | null;
  rollLimit: number | null;
  madMultiplier: number;
}
export interface FilterState {
  schema?: string;
  enabled: Record<string, boolean>;
  ranges: Record<string, FilterRange>;
  booleans: {
    excludeSmileDetected: boolean;
    excludeJawOpenDetected: boolean;
    excludeDateConflict: boolean;
    excludeNearDuplicate: boolean;
    excludeMissingSourceChain: boolean;
  };
  poseOutlier: PoseOutlierConfig;
  manualExclude: string[];
  manualInclude: string[];
}
export interface FilterDecision {
  photo_id: string;
  included: boolean;
  status: string;
  reasons: string[];
  pose_bin?: string;
  pose_distance?: number | null;
}
export interface FilterEvalResult {
  schema?: string;
  total: number;
  included_count: number;
  excluded_count: number;
  included_ids: string[];
  excluded_ids: string[];
  reason_counts: Record<string, number>;
  decisions: FilterDecision[];
  filter_state: FilterState;
  histograms: Record<string, { count: number; min: number | null; max: number | null; mean?: number | null; bins: number[]; counts: number[] }>;
  pose_outlier_stats?: { bins: Record<string, unknown> };
  mutates_stage1?: boolean;
  starts_stage2?: boolean;
}
export const fetchSelectionDefaults = () => apiJson<{ quality_keys: string[]; filter_state: FilterState }>("/api/v1/selection/defaults");
export const evaluateSelection = (filter_state: FilterState) =>
  apiJson<FilterEvalResult>("/api/v1/selection/evaluate", { method: "POST", body: JSON.stringify({ filter_state }) });
export const saveSelection = (filter_state: FilterState, label?: string) =>
  apiJson<{ saved: boolean; path: string; manifest: Record<string, unknown> }>("/api/v1/selection/save", {
    method: "POST",
    body: JSON.stringify({ filter_state, label }),
  });

export type PhotoCurationStatus =
  | "primary"
  | "diagnostic_only"
  | "automatic_exclusion"
  | "manual_exclusion"
  | "manual_include"
  | "manual_review"
  | "invalid";

export interface ProfileSummary {
  id: string;
  name: string;
  description?: string;
  locked?: boolean;
  created_at?: string;
  updated_at?: string;
  photo_status_counts?: Record<string, number>;
  has_manifest?: boolean;
}
export interface ProfileDetail {
  id: string;
  locked?: boolean;
  config: {
    name?: string;
    description?: string;
    filter_state?: FilterState;
    created_at?: string;
    updated_at?: string;
    last_manifest_at?: string;
  };
  curation?: { photos?: Record<string, { status?: string; reason_code?: string; comment?: string }> };
  selection_manifest?: Record<string, unknown> | null;
  journal_tail?: Array<Record<string, unknown>>;
  photo_status_counts?: Record<string, number>;
}
export interface ProfileStatusMap {
  photos: Record<string, { photo_id: string; status: PhotoCurationStatus | string; source: string; reasons: string[]; comment?: string; included: boolean }>;
  included_ids: string[];
  excluded_ids: string[];
  included_count: number;
  excluded_count: number;
  status_counts: Record<string, number>;
  allowed_statuses?: string[];
  reason_codes?: string[];
}
export const listProfiles = async () => (await apiJson<{ profiles: ProfileSummary[] }>("/api/v1/profiles")).profiles || [];
export const createProfile = (payload: { name: string; description?: string; filter_state?: FilterState }) =>
  apiJson<ProfileDetail>("/api/v1/profiles", { method: "POST", body: JSON.stringify(payload) });
export const getProfile = (id: string) => apiJson<ProfileDetail>(`/api/v1/profiles/${encodeURIComponent(id)}`);
export const renameProfile = (id: string, payload: { name: string; description?: string }) =>
  apiJson<ProfileDetail>(`/api/v1/profiles/${encodeURIComponent(id)}/rename`, { method: "POST", body: JSON.stringify(payload) });
export const cloneProfile = (id: string, name?: string) =>
  apiJson<ProfileDetail>(`/api/v1/profiles/${encodeURIComponent(id)}/clone`, { method: "POST", body: JSON.stringify(name ? { name } : {}) });
export const lockProfile = (id: string, locked = true) =>
  apiJson<ProfileDetail>(`/api/v1/profiles/${encodeURIComponent(id)}/lock`, { method: "POST", body: JSON.stringify({ locked }) });
export const updateProfileFilters = (id: string, filter_state: FilterState) =>
  apiJson<ProfileDetail>(`/api/v1/profiles/${encodeURIComponent(id)}/filters`, { method: "PUT", body: JSON.stringify({ filter_state }) });
export const applyCuration = (id: string, payload: { photo_ids: string[]; status: string; reason_code?: string; comment?: string }) =>
  apiJson<Record<string, unknown>>(`/api/v1/profiles/${encodeURIComponent(id)}/curation`, { method: "POST", body: JSON.stringify(payload) });
export const restoreAutomatic = (id: string, photo_ids: string[]) =>
  apiJson<Record<string, unknown>>(`/api/v1/profiles/${encodeURIComponent(id)}/curation/restore`, { method: "POST", body: JSON.stringify({ photo_ids }) });
export const fetchProfileStatuses = (id: string) => apiJson<ProfileStatusMap>(`/api/v1/profiles/${encodeURIComponent(id)}/statuses`);
export const freezeProfile = (id: string) => apiJson<{ path: string; manifest: Record<string, unknown> }>(`/api/v1/profiles/${encodeURIComponent(id)}/freeze`, { method: "POST" });
export const submitProfileAnalysis = (id: string) => apiJson<{ job_id: string; run_id: string; profile_id: string; included_count: number }>(`/api/v1/profiles/${encodeURIComponent(id)}/analysis-runs`, {
  method: "POST",
  body: JSON.stringify({ confirm_frozen_selection: true }),
});
export const diffProfiles = (a: string, b: string) => apiJson<Record<string, unknown>>(`/api/v1/profiles/diff/${encodeURIComponent(a)}/${encodeURIComponent(b)}`);
export const exportProfile = (id: string) => apiJson<Record<string, unknown>>(`/api/v1/profiles/${encodeURIComponent(id)}/export`);
export const importProfile = (payload: Record<string, unknown>) => apiJson<ProfileDetail>("/api/v1/profiles/import", { method: "POST", body: JSON.stringify(payload) });

// ---------------------------------------------------------------------------
// Iteration 05 — Stage 2 Run Manager
// ---------------------------------------------------------------------------
export interface RunProgress { done: number; total: number; phase: string }
export interface RunRow {
  schema?: string;
  run_id: string;
  legacy?: boolean;
  archived?: boolean;
  label?: string;
  profile_id?: string | null;
  profile_name?: string | null;
  created_at?: string;
  status: "queued" | "running" | "complete" | "failed" | "cancelled" | "cancelling" | string;
  progress?: RunProgress;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  has_manifest?: boolean;
  valid?: boolean;
  validation_status?: string | null;
  record_count?: number | null;
  pair_count?: number | null;
  included_count?: number | null;
  directory?: string;
  logs?: string[];
  artifacts?: string[];
  config?: Record<string, unknown>;
  selection?: Record<string, unknown> | null;
  stage2b?: Record<string, unknown> | null;
  stage2b_output?: string | null;
}
export interface Stage2Preflight {
  schema?: string;
  ready: boolean;
  stage1: { root: string; record_count: number; selected_count: number; per_bin: Record<string, { records: number; adjacent_pairs: number; baseline_pairs: number }> };
  calibration: { root: string; record_count: number; person_count: number; persons: string[]; pose_bins: string[] };
  pairs: { adjacent: number; baseline: number; total_estimate: number };
  selection?: { profile_id?: string | null; profile_name?: string | null; included_count: number; excluded_count: number } | null;
  min_points106: number;
  min_points134: number;
  not_a_verdict?: boolean;
}
export const listRuns = async (): Promise<RunRow[]> => (await apiJson<{ runs: RunRow[] }>("/api/v1/runs")).runs || [];
export const getRun = (runId: string) => apiJson<RunRow>(`/api/v1/runs/${encodeURIComponent(runId)}`);
export const preflightStage2 = (payload: { profile_id?: string | null; calibration_root?: string | null; min_points106?: number; min_points134?: number }) =>
  apiJson<Stage2Preflight>("/api/v1/runs/preflight", { method: "POST", body: JSON.stringify(payload) });
export const startStage2Run = (payload: { profile_id?: string | null; label?: string; calibration_root?: string | null; min_points106?: number; min_points134?: number; lead_archive?: string | null }) =>
  apiJson<RunRow>("/api/v1/runs/stage2", { method: "POST", body: JSON.stringify(payload) });
export const cancelRun = (runId: string) => apiJson<RunRow>(`/api/v1/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
export const runStage2b = (runId: string, priorRoot?: string | null) =>
  apiJson<RunRow>(`/api/v1/runs/${encodeURIComponent(runId)}/stage2b`, { method: "POST", body: JSON.stringify({ prior_root: priorRoot ?? null }) });
export const archiveRun = (runId: string) => apiJson<{ archived: boolean; destination: string }>(`/api/v1/runs/${encodeURIComponent(runId)}/archive`, { method: "POST" });

// ---------------------------------------------------------------------------
// Iteration 06 — Stage 3 Report Manager
// ---------------------------------------------------------------------------
export interface ReportRow {
  schema?: string;
  report_id: string;
  legacy?: boolean;
  label?: string;
  mode?: "technical" | "internal" | "public" | string;
  run_id?: string | null;
  created_at?: string;
  valid?: boolean;
  validation_status?: string | null;
  pair_count?: number | null;
  change_count?: number | null;
  status_counts?: Record<string, number> | null;
  files?: string[];
  exports?: string[];
  public_lint?: { status?: string; violation_count?: number; violations?: { path: string; term: string }[] } | null;
  directory?: string;
}
export const listReports = async (): Promise<ReportRow[]> => (await apiJson<{ reports: ReportRow[] }>("/api/v1/reports")).reports || [];
export const getReport = (reportId: string) => apiJson<ReportRow>(`/api/v1/reports/${encodeURIComponent(reportId)}`);
export const generateReport = (payload: { run_id: string; mode: string; label?: string | null }) =>
  apiJson<ReportRow>("/api/v1/reports", { method: "POST", body: JSON.stringify(payload) });
export const regenerateReport = (reportId: string) => apiJson<ReportRow>(`/api/v1/reports/${encodeURIComponent(reportId)}/regenerate`, { method: "POST" });
export const reportFileUrl = (reportId: string, name: string) =>
  `${apiBase()}/api/v1/reports/${encodeURIComponent(reportId)}/file/${name.split("/").map(encodeURIComponent).join("/")}`;

// ---------------------------------------------------------------------------
// Iteration 07 — batch pair displacement (timeline LDM tracks)
// ---------------------------------------------------------------------------
export interface PairDisplacement {
  photo_a: string;
  photo_b: string;
  count: number;
  rms: number | null;
  p95: number | null;
  max: number | null;
  common_visible: number;
  calibrated: boolean;
  exceeds_calibration_p95?: number | null;
  source?: string;
}
export const batchPairs = (pairs: [string, string][], count = 106) =>
  apiJson<{ results: PairDisplacement[]; errors: { photo_a: string; photo_b: string; error: string }[] }>(
    "/api/v1/pairs/batch", { method: "POST", body: JSON.stringify({ pairs, count }) });

// ---------------------------------------------------------------------------
// Iteration 08 — Landmark comparison
// ---------------------------------------------------------------------------
export interface LandmarkComparePoint {
  i: number;
  region: string;
  x_a: number; y_a: number; z_a: number;
  x_b: number; y_b: number; z_b: number;
  dx: number; dy: number; dz: number;
  magnitude: number | null;
  visible_a: boolean; visible_b: boolean;
  common_visible: boolean;
  calibration_median?: number | null;
  calibration_p95?: number | null;
  exceeds_calibration_p95?: boolean;
}
export interface LandmarkComparePayload {
  schema?: string;
  not_a_verdict?: boolean;
  photo_a: string;
  photo_b: string;
  count: number;
  space: string;
  pose_bin: string;
  summary: { rms: number | null; p95: number | null; max: number | null; common_visible: number; exceeds_calibration_p95: number; calibrated: boolean };
  calibration?: { pose_bin: string; count: number; median?: number[] | null; mad?: number[] | null; p95?: number[] | null; calibrated: boolean } | null;
  points: LandmarkComparePoint[];
}
export const landmarkCompare = (a: string, b: string, count: 106 | 134 = 134, space = "chronology") =>
  apiJson<LandmarkComparePayload>(`/api/v1/landmarks/compare/${encodeURIComponent(a)}/${encodeURIComponent(b)}?count=${count}&space=${space}`);

// ---------------------------------------------------------------------------
// Iteration 09 — Morphing workspace
// ---------------------------------------------------------------------------
export interface MorphPhoto { id: string; date: string; t?: number | null; quality?: number | null; yaw?: number | null; pitch?: number | null; roll?: number | null }
export interface MorphBin {
  pose: string;
  label: string;
  camera: { yaw_deg: number; elevation_deg: number };
  photos: MorphPhoto[];
}
export interface MorphingBins { schema?: string; pose_bins: MorphBin[] }
export interface MorphPhotoPayload {
  schema?: string;
  photo_id: string;
  pose_bin: string;
  date?: string | null;
  vertices: number[];
  triangles: number[];
  uv_coords: number[];
  vertex_count: number;
  triangle_count: number;
  has_uv: boolean;
  texture_url?: string | null;
  actual_pose_deg?: number[] | null;
  canonical_pose_deg?: { yaw: number; pitch: number; roll: number } | null;
}
export const morphingBins = () => apiJson<MorphingBins>("/api/v1/morphing/bins");
export const morphingPhoto = (id: string) => apiJson<MorphPhotoPayload>(`/api/v1/morphing/photo/${encodeURIComponent(id)}`);

// ---------------------------------------------------------------------------
// Iteration 09b — 3D heatmap (per-vertex mesh displacement)
// ---------------------------------------------------------------------------
export interface MorphingDiff {
  schema?: string;
  not_a_verdict?: boolean;
  photo_a: string;
  photo_b: string;
  pose_bin: string;
  vertex_count: number;
  triangle_count: number;
  vertices_a: number[];
  vertices_b: number[]; // B aligned to A (Kabsch on 106 landmarks)
  magnitudes: number[]; // per-vertex |vB_aligned − vA|
  stats: { min: number; median: number; p95: number; max: number };
  calibration: {
    available: boolean;
    mean_p95: number | null;
    per_vertex_p95: number[] | null;
    pose_bin?: string;
  };
}
export const morphingDiff = (a: string, b: string) =>
  apiJson<MorphingDiff>(`/api/v1/morphing/diff/${encodeURIComponent(a)}/${encodeURIComponent(b)}`);

// ---------------------------------------------------------------------------
// Iteration 10 — Calibration workspace
// ---------------------------------------------------------------------------
export interface CalibrationWorkspace {
  schema?: string;
  status: string;
  person_count?: number;
  persons?: { person: string; total: number; per_bin: Record<string, number>; covered_bins: number }[];
  pose_bins?: { pose: string; total: number; persons_with_frames: number; adjacent_pair_estimate: number }[];
  complete_bins?: string[];
  covered_bin_count?: number;
  total_frames?: number;
  total_pair_estimate?: number;
  detail?: string;
  not_a_verdict?: boolean;
}
export interface CalibrationThresholdRow {
  pose_bin: string;
  count: number;
  supported_points: number | null;
  scalar: { median: number | null; mad: number | null; p95: number | null };
  per_point: { median: number[]; mad?: number[] | null; p95?: number[] | null };
}
export interface CalibrationThresholds {
  schema?: string;
  status: string;
  calibrated: boolean;
  run_id?: string | null;
  run_directory?: string;
  references: CalibrationThresholdRow[];
  sensitivity?: Record<string, unknown> | null;
  mesh_noise_model?: Record<string, unknown> | null;
  manifest?: { record_count?: number | null; pair_count?: number | null } | null;
  distinction?: Record<string, string>;
  detail?: string;
  not_a_verdict?: boolean;
}
export const calibrationWorkspace = () => apiJson<CalibrationWorkspace>("/api/v1/calibration/workspace");
export const calibrationThresholds = () => apiJson<CalibrationThresholds>("/api/v1/calibration/thresholds");

// ---------------------------------------------------------------------------
// Iteration 07b — timeline findings layer
// ---------------------------------------------------------------------------
export interface ShapeFinding {
  rmse: number | null;
  ldm134_rmse: number | null;
  p95_z: number | null;
  status: string;
  significant_fraction: number | null;
  coherent_fraction: number | null;
  rate_status: string | null;
  alert: boolean;
}
export interface TextureFinding {
  status: string | null;
  quality_a: number | null;
  quality_b: number | null;
  delta: number | null;
}
export interface PairFinding {
  a: string;
  b: string;
  date_a: string | null;
  date_b: string | null;
  days_delta: number | null;
  shape: ShapeFinding;
  texture: TextureFinding;
}
export interface ChangePointFinding {
  date: string | null;
  status: string | null;
  pair: string | null;
  days_delta: number | null;
  p95_z: number | null;
  rate_status: string | null;
}
export interface ReturnFinding {
  date: string | null;
  photo_id: string | null;
  baseline_photo_id: string | null;
  kind: string | null;
  strength: number | null;
}
export interface ZonePhotoSuggestion { id: string; noise_score: number; reasons: string[] }
export interface DenseZone {
  start: string | null;
  end: string | null;
  count: number;
  days: number;
  remove: ZonePhotoSuggestion[];
  keep: string[];
}
export interface BinFindings {
  pairs: PairFinding[];
  change_points: ChangePointFinding[];
  returns: ReturnFinding[];
  zones: DenseZone[];
}
export interface TimelineFindings {
  schema?: string;
  not_a_verdict?: boolean;
  run_id: string | null;
  has_stage2: boolean;
  bins: Record<string, BinFindings>;
}
export const timelineFindings = () => apiJson<TimelineFindings>("/api/v1/timeline/findings");

// ---------------------------------------------------------------------------
// Iteration 13 — integrity, rollback, recommendations
// ---------------------------------------------------------------------------
export interface Stage1Integrity {
  schema?: string;
  unchanged: boolean;
  baseline?: { dataset_hash?: string; timeline_sha256?: string; photo_count?: number } | null;
  current?: { dataset_hash?: string; timeline_sha256?: string; photo_count?: number } | null;
  note?: string;
}
export const stage1Integrity = () => apiJson<Stage1Integrity>("/api/v1/integrity/stage1");

export interface RecommendationAction {
  kind: string;
  run_id?: string | null;
  pose?: string | null;
  profile_id?: string | null;
}
export interface Recommendation {
  type: string;
  priority: number;
  title: string;
  body: string;
  action: RecommendationAction | null;
}
export interface Recommendations {
  schema?: string;
  generated_at?: string | null;
  count: number;
  max_total?: number;
  recommendations: Recommendation[];
  error?: string | null;
  not_a_verdict?: boolean;
}
export interface RecTypeSettings { enabled: boolean; limit: number }
export interface RecSettings {
  schema?: string;
  max_total: number;
  types: Record<string, RecTypeSettings>;
}
export const recommendations = () => apiJson<Recommendations>("/api/v1/recommendations");
export const recommendationSettings = () => apiJson<RecSettings>("/api/v1/recommendations/settings");
export const saveRecommendationSettings = (payload: Partial<RecSettings>) =>
  apiJson<RecSettings>("/api/v1/recommendations/settings", { method: "PUT", body: JSON.stringify(payload) });

export const restoreRun = (runId: string) => apiJson<RunRow>(`/api/v1/runs/${encodeURIComponent(runId)}/restore`, { method: "POST" });
export const retryRun = (runId: string, label?: string | null) =>
  apiJson<RunRow>(`/api/v1/runs/${encodeURIComponent(runId)}/retry`, { method: "POST", body: JSON.stringify({ label: label ?? null }) });
export const deleteRun = (runId: string) => apiJson<{ run_id: string; deleted: boolean }>(`/api/v1/runs/${encodeURIComponent(runId)}/delete`, { method: "POST" });

// ---------------------------------------------------------------------------
// Iteration 06 — Profile preview + analysis runs (from stashed)
// ---------------------------------------------------------------------------

// Iteration 06 — предварительная оценка профиля + каталог прогонов анализа
// ---------------------------------------------------------------------------

export interface ProfilePreviewPairBreakdown {
  pose_bin: string;
  included_count: number;
  adjacent_pairs: number;
  baseline_pairs: number;
  total_pairs: number;
  calibration_pairs?: number;
}
export interface ProfilePreviewEstimatedRuntime {
  stage2_seconds: number;
  stage3_seconds: number;
  total_seconds: number;
  stage2_human: string;
  stage3_human: string;
  total_human: string;
  notes: string[];
}
export interface ProfilePreviewFilterSummary {
  active_metrics: string[];
  active_ranges: { metric: string; min: number | null; max: number | null }[];
  active_booleans: string[];
  pose_outlier: { enabled: boolean; method?: string; master_percentile?: number; mad_multiplier?: number };
  manual_include_count: number;
  manual_exclude_count: number;
}
export interface ProfilePreview {
  schema: string;
  not_a_verdict: boolean;
  profile_id: string;
  selection_manifest_path: string | null;
  selected_at: string | null;
  included_count: number;
  excluded_count: number;
  status_counts: Record<string, number>;
  total_pairs: number;
  pair_breakdown: ProfilePreviewPairBreakdown[];
  estimated_runtime: ProfilePreviewEstimatedRuntime;
  filter_summary: ProfilePreviewFilterSummary;
  blockers: string[];
  warnings: string[];
  is_runnable: boolean;
  calibration_root: string | null;
  stage1_root: string | null;
}
export const fetchProfilePreview = (profileId: string) =>
  apiJson<ProfilePreview>(`/api/v1/profiles/${encodeURIComponent(profileId)}/preview`);

export interface AnalysisRunPhase {
  name: string;
  title?: string;
  status: "pending" | "running" | "complete" | "failed" | "blocked" | "skipped" | string;
  started_at?: string | null;
  finished_at?: string | null;
  progress: { done: number; total: number };
  note?: string | null;
}
export interface AnalysisRunSummary {
  schema: string;
  not_a_verdict: boolean;
  run_id: string;
  run_dir?: string;
  status: string | null;
  status_updated_at?: string | null;
  selected_at?: string | null;
  included_count?: number | null;
  profile_id?: string | null;
  stage2_output?: string | null;
  stage3_output?: string | null;
  has_summary: boolean;
  has_stage2: boolean;
  has_stage3: boolean;
  phases?: AnalysisRunPhase[];
  selection_manifest_digest?: string | null;
  summary?: Record<string, unknown>;
  stage2_manifest?: Record<string, unknown>;
}
export interface AnalysisRunListResponse {
  schema: string;
  not_a_verdict: boolean;
  count: number;
  offset: number;
  limit: number;
  has_more: boolean;
  runs: AnalysisRunSummary[];
}
export interface AnalysisRunPairEntry {
  pose_bin?: string;
  pair?: string;
  photo_a?: string;
  photo_b?: string;
  status?: string;
  score?: number;
  landmark_distance?: number;
  landmark_distance_106?: number;
  landmark_distance_134?: number;
  mesh_distance?: number;
  texture_distance?: number;
  pair_id?: string;
  [key: string]: unknown;
}
export interface AnalysisRunPairsResponse {
  schema: string;
  not_a_verdict: boolean;
  run_id: string;
  count: number;
  offset: number;
  limit: number;
  has_more: boolean;
  pairs: AnalysisRunPairEntry[];
  fields?: string[];
  missing?: string;
}
export const fetchAnalysisRuns = (opts?: { profileId?: string; offset?: number; limit?: number }) => {
  const params = new URLSearchParams();
  if (opts?.profileId) params.set("profile_id", opts.profileId);
  params.set("offset", String(opts?.offset ?? 0));
  params.set("limit", String(opts?.limit ?? 50));
  return apiJson<AnalysisRunListResponse>(`/api/v1/analysis-runs?${params.toString()}`);
};
export const fetchAnalysisRun = (runId: string) =>
  apiJson<AnalysisRunSummary>(`/api/v1/analysis-runs/${encodeURIComponent(runId)}`);
export const fetchAnalysisRunPairs = (
  runId: string,
  opts?: { offset?: number; limit?: number; poseBin?: string },
) => {
  const params = new URLSearchParams();
  params.set("offset", String(opts?.offset ?? 0));
  params.set("limit", String(opts?.limit ?? 50));
  if (opts?.poseBin) params.set("pose_bin", opts.poseBin);
  return apiJson<AnalysisRunPairsResponse>(
    `/api/v1/analysis-runs/${encodeURIComponent(runId)}/pairs?${params.toString()}`,
  );
};
