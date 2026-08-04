import { POSES, type Era, type Photo, type TimelineData } from "./types";

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
      throw new Error(`HTTP ${response.status} ${path}${detail ? `: ${detail}` : ""}`);
    }
    return await response.json() as T;
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
      throw new Error(`Timeline unavailable: HTTP ${response.status}${body ? ` · ${extractApiError(body)}` : ""}`);
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
export const diffProfiles = (a: string, b: string) => apiJson<Record<string, unknown>>(`/api/v1/profiles/diff/${encodeURIComponent(a)}/${encodeURIComponent(b)}`);
export const exportProfile = (id: string) => apiJson<Record<string, unknown>>(`/api/v1/profiles/${encodeURIComponent(id)}/export`);
export const importProfile = (payload: Record<string, unknown>) => apiJson<ProfileDetail>("/api/v1/profiles/import", { method: "POST", body: JSON.stringify(payload) });
