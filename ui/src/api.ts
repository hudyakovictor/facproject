import { PHOTOS, type Photo } from "./data";

export type DataMode = "research" | "demo" | "loading" | "error";
export interface TimelinePayload { schema?: string; source_mode?: string; photos?: unknown[]; items?: unknown[]; note?: string; }
export interface TimelineResult { photos: Photo[]; mode: DataMode; message: string; }

const required = ["id", "date", "t", "era", "bucket", "quality", "boneScore", "p0", "p1", "p2"] as const;

function isPhoto(value: unknown): value is Photo {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return required.every((key) => key in row) && typeof row.id === "string" && typeof row.date === "string";
}

/** Единственный источник истины для базового URL API: relative same-origin по умолчанию. */
export function apiBase(): string {
  return (import.meta.env.VITE_API_BASE_URL as string | undefined) || "";
}

export async function loadTimeline(signal?: AbortSignal): Promise<TimelineResult> {
  const endpoint = (import.meta.env.VITE_TIMELINE_API_URL as string | undefined) || `${apiBase()}/api/v1/timeline`;
  try {
    const response = await fetch(endpoint, { signal, headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json() as TimelinePayload | unknown[];
    const rows = Array.isArray(payload) ? payload : (payload.photos ?? payload.items ?? []);
    const photos = rows.filter(isPhoto);
    if (!photos.length) throw new Error("API returned no valid photo rows");
    const sourceMode = Array.isArray(payload) ? "research" : (payload.source_mode === "research" ? "research" : "demo");
    const note = Array.isArray(payload) ? undefined : payload.note;
    const label = sourceMode === "research" ? "реальный вывод Stage 2" : "демо-датасет (иллюстрация метода)";
    return {
      photos: photos.sort((a, b) => a.t - b.t),
      mode: sourceMode,
      message: `${photos.length} записей · ${label}${note ? " · " + note : ""}`,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    const message = error instanceof Error ? error.message : "unknown API error";
    return { photos: PHOTOS, mode: "demo", message: `API недоступен, встроенный фронтенд-демо-набор: ${message}` };
  }
}

export function exportFixCapsule(photo: Photo | null, sourceMode: DataMode): void {
  const capsule = {
    schema: "deeputin.fix-capsule.v2",
    created_at: new Date().toISOString(),
    source_mode: sourceMode,
    photo_id: photo?.id ?? null,
    source: photo ? { date: photo.date, pose_bin: photo.bucket, quality: photo.quality } : null,
    evidence: photo ? {
      hypothesis: { H0: photo.p0, H1: photo.p1, H2: photo.p2 },
      fuzzy_label: photo.fuzzy,
      confidence: photo.confidence,
      flags: photo.flags,
    } : null,
    limitations: [
      "Исследовательский сигнал, а не установление личности.",
      "Требуется проверка происхождения изображения и независимая экспертиза.",
    ],
  };
  const blob = new Blob([JSON.stringify(capsule, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `fix-capsule-${photo?.id ?? "selection"}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Расширенный API-клиент: сравнение, калибровка, задания, настройки, система.
// Каждая функция бросает исключение при сетевой ошибке — вызывающий код
// решает, показывать ли fallback; это не скрывается внутри api.ts.
// ---------------------------------------------------------------------------

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Accept: "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`HTTP ${response.status} ${path}: ${body.slice(0, 300)}`);
  }
  return response.json() as Promise<T>;
}

export interface HeatmapPoint { index: number; x: number; y: number; z: number; residual: number; }
export interface CompareResult {
  schema: string;
  status: string;
  metrics: Record<string, number>;
  zones: { zone: string; status: string; rmse?: number; point_count?: number }[];
  diagnostics: Record<string, unknown>;
  not_a_verdict: boolean;
  heatmap_points: HeatmapPoint[];
  heatmap_stats?: { min: number; max: number; median: number; p95: number };
  source_mode: string;
  photo_a: { id: string; date: string; bucket: string };
  photo_b: { id: string; date: string; bucket: string };
}

export async function comparePhotos(photoA: string, photoB: string): Promise<CompareResult> {
  return apiJson<CompareResult>("/api/v1/compare", {
    method: "POST",
    body: JSON.stringify({ photo_a: photoA, photo_b: photoB }),
  });
}

export interface FullMeshCompareResult {
  schema: string;
  vertex_count: number;
  triangle_count: number;
  vertices_a: [number, number, number][];
  vertices_b_aligned: [number, number, number][];
  residuals: number[];
  triangles: [number, number, number][];
  primary_zone_ids: string[];
  primary_zone_names: string[];
  primary_triangle_zone: number[];
  residual_stats: { min: number; max: number; median: number; p95: number };
  not_a_verdict: boolean;
  note: string;
  source_mode: string;
  photo_a: { id: string; date: string; bucket: string };
  photo_b: { id: string; date: string; bucket: string };
}

/** Полное BFM-сравнение (35 709 вершин, реальная топология BFM) — для
 * морфинга/3D Inspector. Бросает исключение с понятным сообщением, если
 * BFM-геометрия недоступна на backend (HTTP 503) — вызывающий код обязан
 * явно обработать это состояние, а не тихо падать в пустой экран. */
export async function comparePhotosFullMesh(photoA: string, photoB: string): Promise<FullMeshCompareResult> {
  return apiJson<FullMeshCompareResult>("/api/v1/compare/full_mesh", {
    method: "POST",
    body: JSON.stringify({ photo_a: photoA, photo_b: photoB }),
  });
}

export interface PhotoDetail {
  id: string; date: string; bucket: string; era: string;
  angles: { pitch: number; yaw: number; roll: number };
  landmarks_106: [number, number, number][];
  landmarks_134: [number, number, number][];
  visible_134: boolean[];
  full_mesh_available: boolean;
}

export async function fetchPhotoDetail(photoId: string): Promise<PhotoDetail> {
  return apiJson<PhotoDetail>(`/api/v1/photos/${encodeURIComponent(photoId)}`);
}

export interface FullMesh {
  id: string;
  vertices: [number, number, number][];
  triangles: [number, number, number][];
  ldm106_indices: number[];
  ldm134_indices: number[];
  primary_triangle_zone: number[];
  primary_zone_ids: string[];
  primary_zone_names: string[];
}

/** Полный BFM-меш одного фото (35 709 вершин, реальная топология) для
 * настоящего 3D-просмотра вместо landmark-приближения. */
export async function fetchPhotoFullMesh(photoId: string): Promise<FullMesh> {
  return apiJson<FullMesh>(`/api/v1/photos/${encodeURIComponent(photoId)}/mesh`);
}

export interface CalibrationBucket {
  pose_bin: string; frame_count: number; person_count: number; persons: string[];
  confidence: "invalid" | "low" | "medium" | "high"; runtime_usable: boolean;
}
export interface CalibrationHealth {
  schema: string; not_a_verdict: boolean; total_records: number; total_persons: number;
  confidence_counts: Record<string, number>;
  buckets: Record<string, CalibrationBucket>;
  unreliable_buckets: string[];
  recommendations: { pose_bin: string; reason: string; action: string }[];
  source: string;
}

export async function fetchCalibrationHealth(): Promise<CalibrationHealth> {
  return apiJson<CalibrationHealth>("/api/v1/calibration/health");
}

export interface CalibrationCandidate {
  dataset_id: string; record_id: string; pose_bin: string;
  yaw: number; pitch: number; roll: number; angle_distance: number; source_filename: string;
}
export interface CalibrationMatch {
  schema: string; not_a_verdict: boolean;
  query: { yaw: number; pitch: number; roll: number; pose_bin: string | null };
  candidate_count: number;
  candidates: CalibrationCandidate[];
  note: string;
}

/** Подобрать калибровочные кадры для фото по ID (использует уже известные
 * углы записи) — раздел ТЗ "к парам основного анализа подбирается пара из
 * калибровочного датасета" для вычитания углового шума. */
export async function fetchCalibrationMatchForPhoto(photoId: string): Promise<CalibrationMatch> {
  return apiJson<CalibrationMatch>(`/api/v1/calibration/match?photo_id=${encodeURIComponent(photoId)}`);
}

export interface SystemHealth {
  schema: string; python_version: string; platform: string;
  dependencies: Record<string, { available: boolean; version: string | null }>;
  resources: { available: boolean; cpu_percent?: number; process_rss_mb?: number; system_memory_percent?: number; system_memory_total_gb?: number };
  gpu: { available: boolean; cuda_available?: boolean; device_count?: number; device_name?: string | null };
  model_assets: { required: string[]; missing: string[]; ready: boolean };
  bfm_geometry_available: boolean;
  calibration_dataset_present: boolean;
}

export async function fetchSystemHealth(): Promise<SystemHealth> {
  return apiJson<SystemHealth>("/api/v1/system/health");
}

export interface HeatmapSettings {
  stop_blue_cyan: number; stop_cyan_green: number; stop_green_red: number;
  stop_saturated_red: number; max_residual_reference: number;
}
export interface ThresholdSettings {
  confidence_min: number; quality_min: number; geometry_zone_delta_limit: number;
  texture_zone_delta_limit: number; expression_smile: number; expression_jaw_open: number;
}
export interface AppSettings {
  schema: string; heatmap: HeatmapSettings; thresholds: ThresholdSettings;
  detail_level: string; language: string;
}

export async function fetchSettings(): Promise<AppSettings> {
  return apiJson<AppSettings>("/api/v1/settings");
}
export async function saveSettings(settings: AppSettings): Promise<AppSettings> {
  return apiJson<AppSettings>("/api/v1/settings", { method: "PUT", body: JSON.stringify(settings) });
}
export async function resetSettings(): Promise<AppSettings> {
  return apiJson<AppSettings>("/api/v1/settings/reset", { method: "POST" });
}

export interface JobRow {
  schema: string; id: string; kind: string; status: string;
  created_at: string; started_at: string | null; finished_at: string | null;
  progress: { done: number; total: number };
  logs: string[]; result: Record<string, unknown> | null; error: string | null;
}

export async function listJobs(): Promise<JobRow[]> {
  const body = await apiJson<{ jobs: JobRow[] }>("/api/v1/jobs");
  return body.jobs;
}
export async function submitJob(kind: "extract" | "recompute_metrics", extra?: Record<string, unknown>): Promise<string> {
  const body = await apiJson<{ job_id: string }>("/api/v1/jobs", { method: "POST", body: JSON.stringify({ kind, ...extra }) });
  return body.job_id;
}
export async function cancelJob(jobId: string): Promise<void> {
  await apiJson(`/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
}

export async function clearExtractedData(): Promise<{ removed: string[]; note: string }> {
  return apiJson("/api/v1/data/clear", { method: "POST" });
}

export interface UploadResult { photo_id: string; date: string | null; stored: boolean; message: string; }
export async function uploadPhoto(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${apiBase()}/api/v1/photos/upload`, { method: "POST", body: form });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || body.error || `HTTP ${response.status}`);
  return body as UploadResult;
}
