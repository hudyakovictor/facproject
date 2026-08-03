import type {
  DataMode, EraMeta, JobInfo, Photo, PhotoImageKind, PhotoInfoKeys,
  PoseBucket, TimelineResult,
} from "./types";
import { POSE_BUCKETS } from "./types";

const POSE_SET = new Set<string>(POSE_BUCKETS);

function apiBase(): string {
  const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
  return (env?.VITE_API_BASE ?? "").replace(/\/$/, "");
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function apiJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const timeoutMs = init?.timeoutMs ?? 30000;
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${apiBase()}${path}`, {
      ...init,
      signal: init?.signal ?? ctrl.signal,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers || {}),
      },
    });
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        const d = body?.detail || body?.error || body?.message || detail;
        detail = typeof d === "string" ? d : JSON.stringify(d);
      } catch { /* ignore */ }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    return await res.json() as T;
  } finally {
    window.clearTimeout(timer);
  }
}

function normNum(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? v : Number.NaN;
}

const NULLABLE = [
  "quality", "boneScore", "orbit", "chin", "jaw", "cheek", "symmetry", "yaw", "pitch", "roll",
  "siliconeProb", "specular", "lbpEntropy", "frangi", "wrinkle", "subsurface",
  "visualAge", "calendarAge", "confidence",
  "zOrbitDepth", "zChinProj", "zJawWidth", "zCheek", "p0", "p1", "p2",
] as const;

function buildEraMeta(raw: Record<string, { label?: string; start?: string; end?: string }> | undefined, photos: Photo[]): Record<string, EraMeta> {
  const out: Record<string, EraMeta> = {};
  const palette = ["#4f98a3", "#e8af34", "#dd6974", "#fdab43", "#a86fdf", "#6daa45", "#5591c7"];
  const keys = new Set<string>([...Object.keys(raw || {}), ...photos.map(p => p.era).filter(Boolean)]);
  let i = 0;
  for (const k of keys) {
    const meta = raw?.[k];
    const pts = photos.filter(p => p.era === k);
    const ts = pts.map(p => p.t).filter(Number.isFinite);
    out[k] = {
      label: meta?.label || k,
      short: (meta?.label || k).slice(0, 18),
      start: meta?.start || (ts.length ? new Date(Math.min(...ts)).toISOString().slice(0, 10) : ""),
      end: meta?.end || (ts.length ? new Date(Math.max(...ts)).toISOString().slice(0, 10) : ""),
      color: palette[i % palette.length],
    };
    i += 1;
  }
  return out;
}

function validatePhoto(value: unknown, knownEras: ReadonlySet<string>): { ok: true; photo: Photo } | { ok: false; id: string; reason: string } {
  if (!value || typeof value !== "object") return { ok: false, id: "<не объект>", reason: "строка не является объектом" };
  const row = value as Record<string, unknown>;
  const id = typeof row.id === "string" ? row.id : "<без id>";
  for (const key of ["id", "date", "t", "era", "bucket"] as const) {
    if (!(key in row)) return { ok: false, id, reason: `нет поля: ${key}` };
  }
  if (typeof row.t !== "number" || !Number.isFinite(row.t)) return { ok: false, id, reason: "t не число" };
  const bucket = String(row.bucket);
  if (!POSE_SET.has(bucket)) return { ok: false, id, reason: `unknown pose bin ${bucket}` };
  const era = String(row.era);
  if (knownEras.size > 0 && !knownEras.has(era)) return { ok: false, id, reason: `era ${era} missing in era_meta` };
  const photo = { ...row } as Photo;
  photo.id = String(row.id); photo.date = String(row.date); photo.t = Number(row.t);
  photo.era = era; photo.bucket = bucket as PoseBucket;
  photo.flags = Array.isArray(row.flags) ? row.flags.map(String) : [];
  photo.dominant = (row.dominant === "H1" || row.dominant === "H2" ? row.dominant : "H0") as Photo["dominant"];
  photo.fuzzy = typeof row.fuzzy === "string" ? row.fuzzy : "UNKNOWN";
  for (const k of NULLABLE) (photo as Record<string, unknown>)[k] = normNum(row[k]);
  const hyp = row.hypothesis as Record<string, unknown> | undefined;
  if (hyp) {
    photo.p0 = normNum(hyp.H0 ?? hyp.h0 ?? photo.p0);
    photo.p1 = normNum(hyp.H1 ?? hyp.h1 ?? photo.p1);
    photo.p2 = normNum(hyp.H2 ?? hyp.h2 ?? photo.p2);
  }
  return { ok: true, photo };
}

export async function pingBackend(signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch(`${apiBase()}/api/v1/health`, { signal, headers: { Accept: "application/json" } });
    return res.ok;
  } catch { return false; }
}

export async function loadTimeline(signal?: AbortSignal): Promise<TimelineResult> {
  try {
    const payload = await apiJson<{
      photos?: unknown[]; items?: unknown[]; note?: string; source_mode?: string;
      era_meta?: Record<string, { label?: string; start?: string; end?: string }>;
      chronology_anomalies?: Record<string, Record<string, unknown>>;
    }>("/api/v1/timeline", { signal, timeoutMs: 60000 });
    const rows = (payload.photos || payload.items || []) as unknown[];
    const knownEras = new Set(Object.keys(payload.era_meta || {}));
    const photos: Photo[] = [];
    const rejected: { id: string; reason: string }[] = [];
    for (const row of rows) {
      const v = validatePhoto(row, knownEras);
      if (v.ok) photos.push(v.photo); else rejected.push({ id: v.id, reason: v.reason });
    }
    photos.sort((a, b) => a.t - b.t || a.id.localeCompare(b.id));
    return {
      photos,
      mode: photos.length ? "research" : "empty",
      message: payload.note || payload.source_mode || (photos.length ? "timeline loaded" : "нет фото"),
      eraMeta: buildEraMeta(payload.era_meta, photos),
      rejected,
      chronologyAnomalies: payload.chronology_anomalies || {},
    };
  } catch (err) {
    return {
      photos: [], mode: "error",
      message: err instanceof Error ? err.message : String(err),
      eraMeta: {}, rejected: [], chronologyAnomalies: {},
    };
  }
}

export function photoImageUrl(photoId: string, kind: PhotoImageKind = "original"): string {
  return `${apiBase()}/api/v1/photos/${encodeURIComponent(photoId)}/image?kind=${kind}`;
}
export async function fetchPhotoInfoKeys(photoId: string): Promise<PhotoInfoKeys> {
  return apiJson(`/api/v1/photos/${encodeURIComponent(photoId)}/info_keys`);
}
export async function fetchPhotoDetail(photoId: string): Promise<Record<string, unknown>> {
  return apiJson(`/api/v1/photos/${encodeURIComponent(photoId)}`);
}
export async function fetchSkinZones(photoId: string): Promise<Record<string, unknown>> {
  return apiJson(`/api/v1/photos/${encodeURIComponent(photoId)}/skin_zones`);
}
export async function fetchPairMetrics(a: string, b: string): Promise<Record<string, unknown>> {
  return apiJson(`/api/v1/pairs/${encodeURIComponent(a)}/${encodeURIComponent(b)}/metrics`);
}
export async function fetchRunSummary(): Promise<Record<string, unknown>> { return apiJson("/api/v1/run/summary"); }
export async function fetchRunKeys(name: string): Promise<Record<string, unknown>> {
  return apiJson(`/api/v1/run/keys/${encodeURIComponent(name)}`);
}
export async function fetchReportSummary(): Promise<Record<string, unknown>> { return apiJson("/api/v1/report/summary"); }
export async function fetchReportSection(name: string): Promise<Record<string, unknown>> {
  return apiJson(`/api/v1/report/sections/${encodeURIComponent(name)}`);
}
export async function fetchSettings(): Promise<Record<string, unknown>> { return apiJson("/api/v1/settings"); }
export async function saveSettings(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return apiJson("/api/v1/settings", { method: "PUT", body: JSON.stringify(payload) });
}
export async function resetSettings(): Promise<Record<string, unknown>> {
  return apiJson("/api/v1/settings/reset", { method: "POST", body: "{}" });
}
export async function listJobs(): Promise<JobInfo[]> {
  const res = await apiJson<{ jobs?: JobInfo[] }>("/api/v1/jobs");
  return res.jobs || [];
}
export async function getJob(id: string): Promise<JobInfo> {
  return apiJson(`/api/v1/jobs/${encodeURIComponent(id)}`);
}
export async function submitJob(body: {
  kind: "extract" | "recompute_metrics"; limit?: number; device?: string;
  input_dir?: string; output_dir?: string; stage1_root?: string; calibration_root?: string;
}): Promise<{ job_id: string }> {
  return apiJson("/api/v1/jobs", { method: "POST", body: JSON.stringify(body) });
}
export async function cancelJob(id: string): Promise<void> {
  await apiJson(`/api/v1/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST", body: "{}" });
}
export async function clearExtractedData(): Promise<{ removed?: string[]; note?: string }> {
  return apiJson("/api/v1/data/clear", { method: "POST", body: "{}" });
}
export async function fetchCalibrationHealth(): Promise<Record<string, unknown>> {
  return apiJson("/api/v1/calibration/health");
}
export async function fetchZoneCatalog(): Promise<Record<string, unknown>> {
  return apiJson("/api/v1/zones/catalog");
}
