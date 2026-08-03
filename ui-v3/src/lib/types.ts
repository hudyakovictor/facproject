export type PoseBucket =
  | "left_profile" | "left_deep" | "left_mid" | "left_light"
  | "frontal"
  | "right_light" | "right_mid" | "right_deep" | "right_profile";

export const POSE_BUCKETS: PoseBucket[] = [
  "left_profile", "left_deep", "left_mid", "left_light", "frontal",
  "right_light", "right_mid", "right_deep", "right_profile",
];

export const POSE_LABELS: Record<PoseBucket, string> = {
  left_profile: "левый профиль", left_deep: "левый глубокий", left_mid: "левый средний",
  left_light: "левый лёгкий", frontal: "фронтальный", right_light: "правый лёгкий",
  right_mid: "правый средний", right_deep: "правый глубокий", right_profile: "правый профиль",
};

export type PhotoImageKind = "original" | "thumbnail" | "face_crop" | "uv_texture" | "zones_overlay";
export type Hypothesis = "H0" | "H1" | "H2";
export type DataMode = "research" | "loading" | "error" | "empty";

export interface EraMeta { label: string; short?: string; start?: string; end?: string; color?: string }

export interface Photo {
  id: string; date: string; t: number; era: string; bucket: PoseBucket;
  quality: number; boneScore: number; orbit: number; chin: number; jaw: number; cheek: number;
  symmetry: number; yaw: number; pitch?: number; roll?: number;
  siliconeProb: number; specular: number; lbpEntropy: number; frangi: number; wrinkle: number; subsurface: number;
  visualAge: number; calendarAge: number; confidence: number;
  zOrbitDepth: number; zChinProj: number; zJawWidth: number; zCheek: number;
  p0: number; p1: number; p2: number; dominant: Hypothesis; fuzzy: string; flags: string[];
  hidden?: boolean; exifAnomaly?: boolean; exifDate?: string | null; dateDeltaDays?: number | null;
  sourceClaimedDate?: string | null; sourceClaimedDeltaDays?: number | null;
  [key: string]: unknown;
}

export interface TimelineResult {
  photos: Photo[]; mode: DataMode; message: string;
  eraMeta: Record<string, EraMeta>;
  rejected: { id: string; reason: string }[];
  chronologyAnomalies: Record<string, Record<string, unknown>>;
}

export interface JobInfo {
  id: string; kind: string; status: string;
  created_at?: string; started_at?: string | null; finished_at?: string | null;
  progress?: { done: number; total: number }; logs?: string[];
  result?: Record<string, unknown> | null; error?: string | null;
}

export interface PhotoInfoKeys {
  leaf_count: number;
  categories: Record<string, Record<string, Record<string, unknown>>>;
  category_titles: Record<string, { ru: string; en: string }>;
}

export type RouteId =
  | "overview" | "timeline" | "gallery" | "inspector" | "pairs"
  | "calibration" | "run" | "report" | "control" | "settings";

export interface ToastItem { id: string; kind: "ok" | "warn" | "bad" | "info"; text: string }
