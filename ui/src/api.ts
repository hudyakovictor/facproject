import { PHOTOS, type Photo } from "./data";

export type DataMode = "api" | "demo" | "loading" | "error";
export interface TimelinePayload { schema?: string; photos?: unknown[]; items?: unknown[]; }
export interface TimelineResult { photos: Photo[]; mode: DataMode; message: string; }

const required = ["id", "date", "t", "era", "bucket", "quality", "boneScore", "p0", "p1", "p2"] as const;

function isPhoto(value: unknown): value is Photo {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return required.every((key) => key in row) && typeof row.id === "string" && typeof row.date === "string";
}

export async function loadTimeline(signal?: AbortSignal): Promise<TimelineResult> {
  const endpoint = import.meta.env.VITE_TIMELINE_API_URL || "/api/v1/timeline";
  try {
    const response = await fetch(endpoint, { signal, headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json() as TimelinePayload | unknown[];
    const rows = Array.isArray(payload) ? payload : (payload.photos ?? payload.items ?? []);
    const photos = rows.filter(isPhoto);
    if (!photos.length) throw new Error("API returned no valid photo rows");
    return { photos: photos.sort((a, b) => a.t - b.t), mode: "api", message: `${photos.length} записей загружено` };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    const message = error instanceof Error ? error.message : "unknown API error";
    return { photos: PHOTOS, mode: "demo", message: `API недоступен: ${message}` };
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
