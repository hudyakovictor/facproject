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
  evidenceState: string;
  measurementStatus: string;
  flags: string[];
  stage2PairCount: number;
  stage2StatusCounts: Record<string, number>;
  stage2EvidenceCounts: Record<string, number>;
  sourceMode: string;
  analysisStage: string;
  dateProvenanceStatus?: string | null;
}

export interface ResearchTimeline {
  source_mode: string;
  not_a_verdict: boolean;
  note?: string;
  photos: ResearchPhoto[];
  era_meta: Record<string, { label: string; start: string; end: string }>;
  chronology_anomalies?: Record<string, unknown>;
  analysis_manifest?: Record<string, unknown>;
  ui_fields_complete_photo_count?: number;
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

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
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
