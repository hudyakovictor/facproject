import { POSE_BUCKETS, buildEraMeta, ERA_META, loadDemoPhotos, type EraMeta, type Photo } from "./data";

export type DataMode = "research" | "demo" | "loading" | "error";
export interface TimelinePayload {
  schema?: string; source_mode?: string; photos?: unknown[]; items?: unknown[]; note?: string;
  era_meta?: Record<string, { label?: string; start?: string; end?: string }>;
  /** Сводки хронологических детекторов Stage 2 (возвраты к базовой линии,
   * необратимые возвраты, биологически невозможные скорости). */
  chronology_anomalies?: Record<string, Record<string, unknown>>;
}
export interface TimelineResult {
  photos: Photo[]; mode: DataMode; message: string;
  /** Сегменты хронологии, построенные из `era_meta` ответа. */
  eraMeta: Record<string, EraMeta>;
  /** Строки, отвергнутые валидатором, с причиной — показываются пользователю,
   * а не теряются молча. */
  rejected: { id: string; reason: string }[];
  /** Сводки хронологических аномалий Stage 2; пусто в demo-режиме. */
  chronologyAnomalies: Record<string, Record<string, unknown>>;
}

const required = ["id", "date", "t", "era", "bucket", "quality", "boneScore", "p0", "p1", "p2"] as const;

const POSE_SET: ReadonlySet<string> = new Set(POSE_BUCKETS);

/** Числовые поля `Photo`, которые research-режим Stage 2 отдаёт как `null`.
 *
 * `app6/api/research_timeline.py` заполняет 18 полей значением `None`, когда
 * соответствующий канал не вычислен. Тип `Photo` объявляет их `number`,
 * поэтому без нормализации `p.quality.toFixed(2)` роняет рендер с
 * `TypeError: Cannot read properties of null`. */
const NULLABLE_NUMERIC_FIELDS = [
  "quality", "boneScore", "orbit", "chin", "jaw", "cheek", "symmetry", "yaw",
  "siliconeProb", "specular", "lbpEntropy", "frangi", "wrinkle", "subsurface",
  "visualAge", "calendarAge", "confidence",
  "zOrbitDepth", "zChinProj", "zJawWidth", "zCheek",
  "p0", "p1", "p2",
] as const;

/** Поля, обязательные для осмысленной строки: без них кадр непригоден. */
const CRITICAL_NUMERIC_FIELDS = ["quality", "boneScore", "p0", "p1", "p2"] as const;

/** 🚧 Привести числовое поле к `NaN`, если backend прислал `null`/мусор.
 *
 * `NaN` выбран намеренно вместо `0`: ноль — это измеренное значение, а
 * отсутствие измерения им подменять нельзя (`app6/AGENTS.md`). Графики
 * фильтруют нечисловые значения через `Number.isFinite`, а форматирование
 * (`formatMetric`) показывает «—». */
function normalizeNumeric(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return Number.NaN;
}

/** Проверка строки таймлайна с ПРИЧИНОЙ отказа.
 *
 * Раньше валидатор проверял только наличие ключей, поэтому строка с
 * неизвестным `era` проходила проверку, а затем беззвучно отбрасывалась
 * фильтром эпох — пользователь видел пустой экран без единой ошибки.
 * Теперь несоответствие контракту это явный, видимый отказ. */
function validatePhoto(value: unknown, knownEras: ReadonlySet<string>): { ok: true; photo: Photo } | { ok: false; id: string; reason: string } {
  if (!value || typeof value !== "object") return { ok: false, id: "<не объект>", reason: "строка не является объектом" };
  const row = value as Record<string, unknown>;
  const id = typeof row.id === "string" ? row.id : "<без id>";

  const missing = required.filter(key => !(key in row));
  if (missing.length) return { ok: false, id, reason: `нет обязательных полей: ${missing.join(", ")}` };
  if (typeof row.id !== "string") return { ok: false, id, reason: "id не строка" };
  if (typeof row.date !== "string") return { ok: false, id, reason: "date не строка" };
  if (typeof row.t !== "number" || !Number.isFinite(row.t)) return { ok: false, id, reason: "t не конечное число" };

  const bucket = String(row.bucket);
  if (!POSE_SET.has(bucket)) {
    return { ok: false, id, reason: `неизвестный pose bin "${bucket}" (ожидались 9 нормативных ракурсов)` };
  }
  // `era` сверяется с сегментами, объявленными самим backend в `era_meta`;
  // пустое множество означает, что backend их не прислал — тогда принимаем
  // любой непустой идентификатор и строим сегменты из дат.
  const era = String(row.era);
  if (knownEras.size > 0 && !knownEras.has(era)) {
    return { ok: false, id, reason: `сегмент "${era}" отсутствует в era_meta ответа` };
  }
  if (!era) return { ok: false, id, reason: "пустой era" };

  // Нормализация числовых полей: research-режим отдаёт часть каналов как
  // `null`, и без приведения к NaN любое `.toFixed()` роняет компонент.
  const normalized: Record<string, unknown> = { ...row };
  for (const field of NULLABLE_NUMERIC_FIELDS) {
    if (field in normalized) normalized[field] = normalizeNumeric(normalized[field]);
  }
  // Строка без единого критичного измерения бесполезна для анализа —
  // отвергаем явно, чтобы она не «висела» пустой на таймлайне.
  const allCriticalMissing = CRITICAL_NUMERIC_FIELDS.every(
    field => !Number.isFinite(normalized[field] as number));
  if (allCriticalMissing) {
    return { ok: false, id, reason: "все ключевые метрики отсутствуют (null)" };
  }

  return { ok: true, photo: normalized as unknown as Photo };
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
    const eraMetaRaw = Array.isArray(payload) ? undefined : payload.era_meta;
    const knownEras = new Set(Object.keys(eraMetaRaw ?? {}));

    const photos: Photo[] = [];
    const rejected: { id: string; reason: string }[] = [];
    for (const row of rows) {
      const verdict = validatePhoto(row, knownEras);
      if (verdict.ok) photos.push(verdict.photo);
      else rejected.push({ id: verdict.id, reason: verdict.reason });
    }
    if (!photos.length) {
      const detail = rejected.length ? ` (отвергнуто ${rejected.length}: ${rejected[0].reason})` : "";
      throw new Error(`API returned no valid photo rows${detail}`);
    }

    const sourceMode = Array.isArray(payload) ? "research" : (payload.source_mode === "research" ? "research" : "demo");
    const note = Array.isArray(payload) ? undefined : payload.note;
    const label = sourceMode === "research" ? "реальный вывод Stage 2" : "демо-датасет (иллюстрация метода)";
    const sorted = photos.sort((a, b) => a.t - b.t);
    const rejectedNote = rejected.length ? ` · отвергнуто строк: ${rejected.length}` : "";
    return {
      photos: sorted,
      mode: sourceMode,
      message: `${sorted.length} записей · ${label}${note ? " · " + note : ""}${rejectedNote}`,
      eraMeta: buildEraMeta(eraMetaRaw, sorted),
      rejected,
      chronologyAnomalies: (Array.isArray(payload) ? undefined : payload.chronology_anomalies) ?? {},
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    const message = error instanceof Error ? error.message : "unknown API error";
    // Демо-набор подгружается отдельным чанком только здесь — в ветке,
    // куда попадаем лишь при недоступном backend (аудит №27).
    return {
      photos: await loadDemoPhotos(), mode: "demo",
      message: `API недоступен, встроенный фронтенд-демо-набор: ${message}`,
      eraMeta: ERA_META, rejected: [], chronologyAnomalies: {},
    };
  }
}

export function exportFixCapsule(photo: Photo | null, sourceMode: DataMode): void {
  const capsule = {
    schema: "deeputin.fix-capsule.v2",
    created_at: new Date().toISOString(),
    source_mode: sourceMode,
    photo_id: photo?.id ?? null,
    source:photo?{date:photo.date,pose_bin:photo.bucket,quality:photo.quality,date_authority:"filename",date_provenance_status:photo.dateProvenanceStatus??"unknown",exif_date:photo.exifDate??null,date_delta_days:photo.dateDeltaDays??null,source_claimed_date:photo.sourceClaimedDate??null,source_claimed_delta_days:photo.sourceClaimedDeltaDays??null,date_conflict_sources:photo.dateConflictSources??[],date_provenance_limited:photo.dateProvenanceLimited??false}:null,
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

/** Извлечь максимально информативное сообщение из тела ошибки API.
 *
 * P2.7 (DEV_FIX_TZ 3.7): раньше тело читалось только как текст и резалось на
 * 300 символов, из-за чего структурированная ошибка FastAPI
 * (`{"detail": "..."}`) превращалась в мусорный JSON-огрызок. Теперь сначала
 * пробуем разобрать JSON и достать `detail`/`error`/`message`, и лишь затем
 * откатываемся к сырому тексту. */
function extractApiError(body: string): string {
  const trimmed = body.trim();
  if (!trimmed) return "";
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (typeof parsed === "string") return parsed;
    if (parsed && typeof parsed === "object") {
      const obj = parsed as Record<string, unknown>;
      for (const key of ["detail", "error", "message"] as const) {
        const value = obj[key];
        if (typeof value === "string" && value) return value;
        // FastAPI validation errors: detail — массив объектов с msg/loc.
        if (Array.isArray(value)) {
          const messages = value
            .map(item => (item && typeof item === "object" ? (item as Record<string, unknown>).msg : item))
            .filter((m): m is string => typeof m === "string");
          if (messages.length) return messages.join("; ");
        }
      }
      return JSON.stringify(parsed).slice(0, 500);
    }
  } catch {
    // не JSON — используем текст как есть
  }
  return trimmed.slice(0, 500);
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  // P2.6 (DEV_FIX_TZ 3.6): Content-Type ставится ТОЛЬКО при наличии тела.
  // На GET-запросах он бессмысленен (тела нет) и может ломать кэширование на
  // прокси/CDN, а также провоцировать лишние preflight-запросы.
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init?.body !== undefined && init.body !== null) headers["Content-Type"] = "application/json";
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    const detail = extractApiError(body);
    throw new Error(`HTTP ${response.status} ${path}${detail ? `: ${detail}` : ""}`);
  }
  return response.json() as Promise<T>;
}

/** Точка сравнения. `visible=false` → координаты и residual равны null:
 * точка не видна на одном из кадров, измерения нет. */
export interface HeatmapPoint {
  index: number;
  visible?: boolean;
  x: number | null; y: number | null; z: number | null;
  /** Позиция B после Kabsch-выравнивания в систему координат A (для морфинга). */
  bx?: number | null; by?: number | null; bz?: number | null;
  /** Знаковое смещение по осям — направление ухода точки. */
  dx?: number | null; dy?: number | null; dz?: number | null;
  residual: number | null;
  /** Координатная зона (НЕ анатомическая метка). */
  zone?: string | null;
}
export interface CompareResult {
  schema: string;
  status: string;
  metrics: Record<string, number>;
  /** Per-zone разбивка из Stage 2. `signed_*` — медианное знаковое смещение
   * зоны по осям: показывает, КУДА сместилась геометрия, а не только
   * насколько. Поля отсутствуют у зон со статусом `insufficient_visibility`. */
  zones: {
    zone: string; status: string; point_count?: number;
    rmse?: number; median?: number; p95?: number;
    signed_x?: number; signed_y?: number; signed_z?: number;
  }[];
  diagnostics: Record<string, unknown>;
  not_a_verdict: boolean;
  heatmap_points: HeatmapPoint[];
  landmark_count?: number;
  visible_point_count?: number;
  zone_policy?: string;
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
  /** "no_candidates" — в разрешённом pose_bin нет калибровочных кадров,
   * угловой шум для этой пары вычесть нечем (P3.15). */
  status: "matched" | "no_candidates";
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
export interface LandmarkShiftSettings {
  tolerance: number; suspect: number; calibrated: boolean;
}
export interface ThresholdSettings {
  confidence_min: number; quality_min: number; geometry_zone_delta_limit: number;
  texture_zone_delta_limit: number; expression_smile: number; expression_jaw_open: number;
}
export interface AppSettings {
  schema: string; heatmap: HeatmapSettings; thresholds: ThresholdSettings;
  landmark_shift?: LandmarkShiftSettings;
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

/** P3.3 (DEV_FIX_TZ): статус задания — union, а не свободная строка. Так
 * опечатка в сравнении статуса ловится компилятором, а не в рантайме. */
export type JobStatus = "queued" | "running" | "complete" | "blocked" | "failed" | "cancelled";
export type JobKind = "extract" | "recompute_metrics";

export interface JobRow {
  schema: string; id: string; kind: string; status: JobStatus;
  created_at: string; started_at: string | null; finished_at: string | null;
  progress: { done: number; total: number };
  logs: string[]; result: Record<string, unknown> | null; error: string | null;
}

export async function listJobs(): Promise<JobRow[]> {
  const body = await apiJson<{ jobs: JobRow[] }>("/api/v1/jobs");
  return body.jobs;
}
export async function submitJob(kind: JobKind, extra?: Record<string, unknown>): Promise<string> {
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
  const raw = await response.text().catch(() => "");
  if (!response.ok) {
    const detail = extractApiError(raw);
    throw new Error(`HTTP ${response.status} /api/v1/photos/upload${detail ? `: ${detail}` : ""}`);
  }
  try {
    return JSON.parse(raw) as UploadResult;
  } catch {
    throw new Error(`upload succeeded but response was not JSON: ${raw.slice(0, 200)}`);
  }
}

// ---------------------------------------------------------------------------
// Зоны кожи: НЕ новый анализ, а чтение уже сохранённых артефактов Stage 1
// (`skin_zone_quality.json`, `quality.json`, `wrinkle_zones.json`).
// Поля, которых Stage 1 не сохранил, приходят как `null` — интерфейс обязан
// показать их как «нет данных», а не как ноль.
// ---------------------------------------------------------------------------

export type SkinZoneStatus = "active" | "excluded" | "no_data";

export interface SkinZone {
  zone_id: string | null;
  name: string;
  label_ru: string;
  group: string | null;
  side: string | null;
  status: SkinZoneStatus;
  exclusion_reasons: string[];
  visible_fraction: number | null;
  skin_pixels: number | null;
  quality: number | null;
  bbox_original: [number, number, number, number] | null;
  texture_score: number | null;
  texture_usable: boolean | null;
  quality_class: string | null;
  laplacian_var: number | null;
  tenengrad_mean: number | null;
  highlight_fraction: number | null;
  shadow_fraction: number | null;
  skin_fraction: number | null;
  texture_pixels: number | null;
  roi_source: string | null;
  wrinkle: unknown;
}

export interface SkinZoneReport {
  schema: string;
  not_a_verdict: boolean;
  source_mode: string;
  photo_id: string;
  pose_bin: string | null;
  skin_mask_coverage: number | null;
  global_texture_quality: { status?: string; texture_score_0_1?: number } | null;
  mask_quality: { status?: string; skin_coverage_original?: number; skin_pixels_original?: number } | null;
  zone_count: number;
  active_zone_count: number;
  excluded_zone_count: number;
  no_data_zone_count: number;
  zones: SkinZone[];
  available_sources: {
    skin_zone_quality: boolean;
    per_zone_quality: boolean;
    wrinkle_zones: boolean;
    wrinkle_note: string | null;
  };
}

/** Per-zone отчёт кожи по сохранённым артефактам Stage 1.
 * Бросает исключение с понятной причиной при HTTP 409 (демо-режим: реальных
 * текстурных артефактов не существует) — вызывающий код обязан это показать,
 * а не подставить синтетику. */
export async function fetchSkinZones(photoId: string): Promise<SkinZoneReport> {
  return apiJson<SkinZoneReport>(`/api/v1/photos/${encodeURIComponent(photoId)}/skin_zones`);
}

export interface ZoneCatalogEntry {
  zone_id: string;
  name: string;
  label_ru: string;
  group: string | null;
  side: string | null;
  seed_uv: [number, number] | null;
  scale_uv: [number, number] | null;
  excluded_by_segmentation: boolean;
}

export async function fetchZoneCatalog(): Promise<{ zone_count: number; zones: ZoneCatalogEntry[] }> {
  return apiJson<{ zone_count: number; zones: ZoneCatalogEntry[] }>("/api/v1/zones/catalog");
}

/** Удалить извлечённые Stage-1-данные фото (исходный файл не трогается).
 * Эндпоинт существовал в backend, но интерфейс его не вызывал. */
export async function deletePhotoExtraction(photoId: string): Promise<{ deleted: string }> {
  return apiJson<{ deleted: string }>(`/api/v1/photos/${encodeURIComponent(photoId)}`, { method: "DELETE" });
}

/** URL сохранённого Stage 1 изображения фотографии.
 *
 * Возвращает строку для `<img src>`, а не Blob: браузер сам кэширует и
 * показывает прогресс загрузки. В demo-режиме backend ответит 409 — компонент
 * обязан показать заглушку с причиной, а не пустой прямоугольник.
 */
export type PhotoImageKind = "original" | "thumbnail" | "face_crop" | "uv_texture" | "zones_overlay";

export function photoImageUrl(photoId: string, kind: PhotoImageKind = "original"): string {
  return `${apiBase()}/api/v1/photos/${encodeURIComponent(photoId)}/image?kind=${kind}`;
}

// ---------------------------------------------------------------------------
// Вычитание углового шума по калибровочному набору.
// Компенсация УМЕНЬШАЕТ расхождение, поэтому API всегда отдаёт сырое и
// компенсированное значение вместе с признаками надёжности подбора.
// ---------------------------------------------------------------------------

export interface AngleTolerance { yaw: number; pitch: number; roll: number }

export interface CompensatedMetric {
  raw: number;
  noise: number | null;
  compensated: number | null;
}

export interface NoiseSubtractionResult {
  schema: string;
  status: string;
  source_mode: string;
  tolerance: AngleTolerance;
  angle_delta: { yaw: number; pitch: number; roll: number } | null;
  /** Подходящей калибровочной пары не нашлось — компенсация НЕ применена. */
  uncompensated: boolean;
  /** Расхождение схлопнулось в ноль: подбор вырожденный, доверять нельзя. */
  degenerate_match?: boolean;
  reason: string;
  match: {
    dataset_id: string; record_a: string; record_b: string;
    delta: Record<string, number>; match_distance: number;
  } | null;
  metrics: Record<string, CompensatedMetric>;
  index_size?: number;
  note?: string;
}

export async function subtractAngleNoise(
  photoA: string, photoB: string, tolerance?: Partial<AngleTolerance>,
): Promise<NoiseSubtractionResult> {
  return apiJson<NoiseSubtractionResult>("/api/v1/calibration/subtract_noise", {
    method: "POST",
    body: JSON.stringify({ photo_a: photoA, photo_b: photoB, tolerance: tolerance ?? null }),
  });
}

export interface NoiseModelInfo {
  schema: string;
  tolerance: AngleTolerance;
  index_size: number;
  pairs_per_pose_bin: Record<string, number>;
  coverage: {
    pair_count: number;
    compensated_count: number;
    coverage: number | null;
    uncompensated_reasons: Record<string, number>;
    median_noise_removed: number | null;
  };
  note: string;
}

export async function fetchNoiseModel(tolerance?: Partial<AngleTolerance>): Promise<NoiseModelInfo> {
  const q = new URLSearchParams();
  if (tolerance?.yaw !== undefined) q.set("yaw", String(tolerance.yaw));
  if (tolerance?.pitch !== undefined) q.set("pitch", String(tolerance.pitch));
  if (tolerance?.roll !== undefined) q.set("roll", String(tolerance.roll));
  const suffix = q.toString() ? `?${q}` : "";
  return apiJson<NoiseModelInfo>(`/api/v1/calibration/noise_model${suffix}`);
}

// =============================================================================
// Полные метрики пайплайна по категориям A–I (ui/KEYS_PLACEMENT_MAP.md)
// =============================================================================
// 🚨 До этих клиентов интерфейс видел 13 колонок `pair_metrics.csv` из 186.
// Статистика множественных сравнений, mesh-канал, текстура, дескрипторы и
// корроборация оставались на диске.

/** Значение ключа пайплайна. `null` — «нет данных», НЕ ноль. */
export type KeyValue = string | number | boolean | null;

/** Категория → подгруппа → ключ → значение. */
export type KeyCategories = Record<string, Record<string, Record<string, KeyValue>>>;

/** Вложенная структура Stage 1 `info.json` (произвольная глубина). */
export type NestedKeys = Record<string, Record<string, unknown>>;

export interface CategoryTitle { ru: string; en: string }

export interface PairMetrics {
  schema: string;
  not_a_verdict: boolean;
  source_mode: string;
  photo_a: string;
  photo_b: string;
  /** Пара найдена в обратном порядке: Stage 2 хранит хронологический. */
  reversed_order: boolean;
  column_count: number;
  /** Сколько колонок реально имеют значение (остальные — «нет данных»). */
  available_count: number;
  category_titles: Record<string, CategoryTitle>;
  categories: KeyCategories;
}

/** Все колонки `pair_metrics.csv` для пары, разложенные по категориям A–I.
 * HTTP 409 — нет вывода Stage 2; HTTP 404 — пара не построена (кадры в
 * разных pose bin). Оба состояния вызывающий код обязан показать явно. */
export async function fetchPairMetrics(photoA: string, photoB: string): Promise<PairMetrics> {
  return apiJson<PairMetrics>(
    `/api/v1/pairs/${encodeURIComponent(photoA)}/${encodeURIComponent(photoB)}/metrics`);
}

export interface ArtifactEntry {
  name: string;
  category: string;
  purpose: string;
  /** Артефакт создан этим прогоном. Отсутствующие тоже перечисляются —
   * иначе «не создан» неотличимо от «раздел не реализован». */
  present: boolean;
  size_bytes: number | null;
}

export interface RunSummary {
  schema: string;
  not_a_verdict: boolean;
  source_mode: string;
  category_titles: Record<string, CategoryTitle>;
  categories: Record<string, Record<string, Record<string, unknown>>>;
  technical_summary: Record<string, unknown> | null;
  metric_catalog: Record<string, unknown> | null;
  artifacts: ArtifactEntry[];
}

/** Сводка прогона: манифест, техотчёт, каталог метрик, перечень артефактов. */
export async function fetchRunSummary(): Promise<RunSummary> {
  return apiJson<RunSummary>("/api/v1/run/summary");
}

export interface ArtifactPayload {
  schema: string;
  name: string;
  category: string;
  purpose: string;
  size_bytes: number;
  /** Артефакт больше лимита и не передан целиком. */
  truncated: boolean;
  payload: unknown;
}

export async function fetchRunArtifact(name: string): Promise<ArtifactPayload> {
  return apiJson<ArtifactPayload>(`/api/v1/run/artifacts/${encodeURIComponent(name)}`);
}

export interface PhotoInfoKeys {
  schema: string;
  not_a_verdict: boolean;
  source_mode: string;
  photo_id: string;
  /** Число листовых значений `info.json` — честный счётчик охвата. */
  leaf_count: number;
  category_titles: Record<string, CategoryTitle>;
  categories: NestedKeys;
}

/** Все ключи Stage 1 `info.json` одного фото по категориям C/D/G/H. */
export async function fetchPhotoInfoKeys(photoId: string): Promise<PhotoInfoKeys> {
  return apiJson<PhotoInfoKeys>(`/api/v1/photos/${encodeURIComponent(photoId)}/info_keys`);
}

// =============================================================================
// Публичный отчёт Stage 3
// =============================================================================
// 🚨 Stage 3 был единственным этапом пайплайна без эндпоинта: итоговый отчёт
// существовал только как файл на диске, мимо рабочей станции.

export interface ReportSectionEntry {
  name: string;
  title: string;
  /** Секция есть в этом прогоне. Отсутствующие тоже перечисляются. */
  present: boolean;
  size: number | null;
  paged: boolean;
}

export interface ReportSummary {
  schema: string;
  not_a_verdict: boolean;
  source_mode: string;
  report_schema_version: string | null;
  stage2_schema_version: string | null;
  created_at_utc: string | null;
  summary: Record<string, unknown>;
  narrative: string[];
  methodology: Record<string, unknown>;
  validation: Record<string, unknown> | null;
  sections: ReportSectionEntry[];
  /** 🚨 В Stage 3 `status` — это `evidence_state` Stage 2, а измерительный
   * статус лежит в `measurement_status`. Без этой пометки сравнение отчёта
   * с таблицей пары выглядит как расхождение данных. */
  status_semantics: Record<string, string>;
  /** Колонки, не публикуемые Stage 3 по политике (не пропуск данных). */
  withheld_column_prefixes: string[];
  withheld_note: string;
}

export async function fetchReportSummary(): Promise<ReportSummary> {
  return apiJson<ReportSummary>("/api/v1/report/summary");
}

export interface ReportSection {
  schema: string;
  name: string;
  title: string;
  present: boolean;
  total: number | null;
  offset: number | null;
  returned: number | null;
  paged: boolean;
  payload: unknown;
}

export async function fetchReportSection(
  name: string, offset = 0, limit = 100,
): Promise<ReportSection> {
  const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return apiJson<ReportSection>(
    `/api/v1/report/sections/${encodeURIComponent(name)}?${query}`);
}

/** Лёгкая проверка связи с backend (`GET /api/v1/health`).
 *
 * Эндпоинт существовал с самого начала, но не имел ни одного потребителя
 * (аудит №11). Он отличается от `/api/v1/system/health` тем, что не
 * собирает сведения о зависимостях, GPU и моделях: это дешёвый пинг,
 * пригодный для периодического опроса.
 *
 * Возвращает `false` вместо исключения — вызывающему коду нужен факт
 * доступности, а не разбор причины.
 */
export async function pingBackend(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${apiBase()}/api/v1/health`, { signal });
    if (!response.ok) return false;
    const payload = await response.json() as { status?: string };
    return payload.status === "ok";
  } catch {
    return false;
  }
}
