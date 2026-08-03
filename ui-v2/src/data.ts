// Production research data contracts. No generated evidence is permitted.

/** Идентификатор сегмента хронологии.
 *
 * ⚠️ НЕ жёсткий union: backend возвращает собственные идентификаторы
 * (`DEMO_SEGMENT_1..5` в неисследовательском режиме, `STAGE2_RESEARCH` в research), и они
 * НЕ совпадают со встроенным демо-набором. Прежний закрытый union приводил к
 * тому, что фильтр эпох отбрасывал 100% строк из API, и таймлайн молча
 * оставался пустым. Единственный источник истины о сегментах — поле
 * `era_meta` ответа `/api/v1/timeline`; локальные `ERA_*` ниже — только
 * fallback для встроенного демо-набора. */
export type Era = string;

/** Метаданные одного сегмента хронологии. */
export interface EraMeta { label: string; color: string; start: string; end: string; short: string }
export type PoseBucket = "left_profile" | "left_deep" | "left_mid" | "left_light" | "frontal" | "right_light" | "right_mid" | "right_deep" | "right_profile";
export type FuzzyLabel =
  | "STRONGLY_MATCHING"
  | "CONSISTENT"
  | "INSUFFICIENT_DATA"
  | "WEAK_EVIDENCE"
  | "SUSPICIOUS_TEXTURE"
  | "GEOMETRIC_MISMATCH"
  | "IDENTITY_ANOMALY"
  | "TEMPORAL_IMPOSSIBILITY";
export type Hypothesis = "H0" | "H1" | "H2" | "UNAVAILABLE";

export interface Photo {
  id: string;
  date: string; // YYYY-MM-DD
  t: number; // unix ms
  era: Era;
  bucket: PoseBucket;
  quality: number;
  hidden: boolean;
  // metrics
  boneScore: number;
  orbit: number;
  chin: number;
  jaw: number;
  cheek: number;
  symmetry: number;
  yaw: number;
  // texture
  siliconeProb: number;
  specular: number;
  lbpEntropy: number;
  frangi: number;
  wrinkle: number;
  subsurface: number;
  visualAge: number;
  calendarAge: number;
  // verdict
  p0: number;
  p1: number;
  p2: number;
  dominant: Hypothesis;
  fuzzy: FuzzyLabel;
  confidence: number;
  flags: string[];
  exifAnomaly:boolean;dateProvenanceStatus?:"filename_only"|"corroborated"|"conflict"|"unknown";exifDate?:string|null;dateDeltaDays?:number|null;sourceClaimedDate?:string|null;sourceClaimedDeltaDays?:number|null;dateConflictSources?:string[];dateProvenanceLimited?:boolean;
  // z-scores key zones
  zOrbitDepth: number;
  zChinProj: number;
  zJawWidth: number;
  zCheek: number;
}

/** Нормативная схема девяти ракурсов. Не демо-данные: этой раскладкой
 * оперирует весь пайплайн, поэтому она живёт в общем модуле. */
export const POSE_BUCKETS: PoseBucket[] = ["left_profile", "left_deep", "left_mid", "left_light", "frontal", "right_light", "right_mid", "right_deep", "right_profile"];
export const POSE_YAW: Record<PoseBucket, number> = { left_profile: -90, left_deep: -67.5, left_mid: -45, left_light: -22.5, frontal: 0, right_light: 22.5, right_mid: 45, right_deep: 67.5, right_profile: 90 };
export const POSE_LABELS: Record<PoseBucket, string> = { left_profile: "левый профиль", left_deep: "левый глубокий", left_mid: "левый средний", left_light: "левый лёгкий", frontal: "фронтальный", right_light: "правый лёгкий", right_mid: "правый средний", right_deep: "правый глубокий", right_profile: "правый профиль" };


export const TIME_MIN = Date.parse("1999-01-01");
export const TIME_MAX = Date.parse("2026-06-30");
export const TIME_SPAN = TIME_MAX - TIME_MIN;

export const ERA_META: Record<string, EraMeta> = {};

/** Детерминированная палитра сегментов: один и тот же идентификатор всегда
 * получает один и тот же цвет, независимо от порядка загрузки. */
const SEGMENT_PALETTE = ["#4f98a3", "#e8af34", "#dd6974", "#fdab43", "#a86fdf", "#6daa45", "#5591c7", "#a13544"];

/** 🏭 Построить таблицу сегментов из `era_meta` ответа `/api/v1/timeline`.
 *
 * Backend уже отдаёт `era_meta` (label/start/end) — менять контракт не нужно,
 * достаточно его использовать. Цвет и короткая подпись выводятся здесь, так
 * как backend их не передаёт. */
export function buildEraMeta(
  raw: Record<string, { label?: string; start?: string; end?: string }> | undefined,
  photos: Photo[],
): Record<string, EraMeta> {
  const ids = raw && Object.keys(raw).length
    ? Object.keys(raw)
    : Array.from(new Set(photos.map(p => p.era))).sort();
  if (!ids.length) return {};

  const out: Record<string, EraMeta> = {};
  ids.forEach((id, index) => {
    const entry = raw?.[id] ?? {};
    // Границы сегмента: из ответа API, иначе — из фактических дат его кадров,
    // чтобы `currentEra` и полоса эпохи работали и без era_meta.
    const own = photos.filter(p => p.era === id).map(p => p.t).sort((a, b) => a - b);
    const start = entry.start ?? (own.length ? new Date(own[0]).toISOString().slice(0, 10) : "1999-01-01");
    const end = entry.end ?? (own.length ? new Date(own[own.length - 1]).toISOString().slice(0, 10) : "2026-06-30");
    const label = entry.label ?? id;
    out[id] = {
      label,
      // Короткая подпись для тесных мест (центроиды кластеров, колонки).
      short: label.length > 14 ? `${label.slice(0, 13)}…` : label,
      color: SEGMENT_PALETTE[index % SEGMENT_PALETTE.length],
      start, end,
    };
  });
  return out;
}

export const FUZZY_COLORS: Record<FuzzyLabel, string> = {
  STRONGLY_MATCHING: "#6daa45",
  CONSISTENT: "#4f98a3",
  INSUFFICIENT_DATA: "#797876",
  WEAK_EVIDENCE: "#e8af34",
  SUSPICIOUS_TEXTURE: "#fdab43",
  GEOMETRIC_MISMATCH: "#dd6974",
  IDENTITY_ANOMALY: "#a13544",
  TEMPORAL_IMPOSSIBILITY: "#ff3b30",
};

export const HYPOTHESIS_COLORS: Record<Hypothesis, string> = {
  H0: "#6daa45",
  H1: "#fdab43",
  H2: "#a13544",
  UNAVAILABLE: "#797876",
};

export interface EventPin {
  id: string;
  date: string;
  t: number;
  type: "DISAPPEARANCE" | "POLITICAL" | "AI_RESEARCH" | "REPORT" | "ERA_START" | "RTR";
  iconName: "alert-triangle" | "volume" | "flask" | "file-text" | "play" | "rotate";
  color: string;
  title: string;
  tooltip: string;
  source: string;
  folkTag?: string;
}

export const EVENT_PINS: EventPin[] = [];

// Aggregate medians per N buckets for fast track rendering
export interface TrackPoint {
  t: number;
  date: string;
  value: number;
  zScore?: number;
  flag?: "warn" | "critical" | "impossible";
}

/** Pipeline reference values are not embedded in the UI. */
export const REF: Record<string, { median: number; std: number }> = {};
