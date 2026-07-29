// Synthetic but deterministic dataset for DeepUtin Forensic Timeline Suite
// All numbers derived from a seeded PRNG so render is stable.

export type Era = "ERA_1_BASELINE" | "ERA_2_EARLY" | "ERA_3_UDMURT" | "ERA_4_TRANSITION" | "ERA_5_VASILICH";
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
export type Hypothesis = "H0" | "H1" | "H2";

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
  exifAnomaly: boolean;
  // z-scores key zones
  zOrbitDepth: number;
  zChinProj: number;
  zJawWidth: number;
  zCheek: number;
}

// Simple seeded PRNG (mulberry32)
function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function fmtDate(d: Date): string {
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const ERA_RANGES: { era: Era; start: string; end: string; count: number }[] = [
  { era: "ERA_1_BASELINE", start: "1999-08-09", end: "2011-12-31", count: 520 },
  { era: "ERA_2_EARLY", start: "2012-01-01", end: "2014-12-31", count: 180 },
  { era: "ERA_3_UDMURT", start: "2015-01-01", end: "2021-09-08", count: 480 },
  { era: "ERA_4_TRANSITION", start: "2021-09-09", end: "2023-09-30", count: 210 },
  { era: "ERA_5_VASILICH", start: "2023-10-01", end: "2026-06-04", count: 419 },
];

const BIRTH = Date.UTC(1952, 9, 7); // 1952-10-07

export const POSE_BUCKETS: PoseBucket[] = ["left_profile", "left_deep", "left_mid", "left_light", "frontal", "right_light", "right_mid", "right_deep", "right_profile"];

export const POSE_YAW: Record<PoseBucket, number> = { left_profile: -90, left_deep: -67.5, left_mid: -45, left_light: -22.5, frontal: 0, right_light: 22.5, right_mid: 45, right_deep: 67.5, right_profile: 90 };

export const POSE_LABELS: Record<PoseBucket, string> = { left_profile: "левый профиль", left_deep: "левый глубокий", left_mid: "левый средний", left_light: "левый лёгкий", frontal: "фронтальный", right_light: "правый лёгкий", right_mid: "правый средний", right_deep: "правый глубокий", right_profile: "правый профиль" };

function buildPhotos(): Photo[] {
  const rng = mulberry32(20260604);
  const out: Photo[] = [];
  let idx = 0;
  for (const range of ERA_RANGES) {
    const s = Date.parse(range.start);
    const e = Date.parse(range.end);
    const span = e - s;
    // generate sorted random times
    const times: number[] = [];
    for (let i = 0; i < range.count; i++) {
      times.push(s + rng() * span);
    }
    times.sort((a, b) => a - b);

    for (const t of times) {
      const d = new Date(t);
      const date = fmtDate(d);
      const id = `P${String(idx + 1).padStart(5, "0")}`;
      const ageYrs = (t - BIRTH) / (365.25 * 24 * 3600 * 1000);

      // Era-conditioned drift parameters
      let geomDrift = 0;
      let textureDrift = 0;
      let p0 = 0.6, p1 = 0.3, p2 = 0.1;
      let fuzzy: FuzzyLabel = "CONSISTENT";

      switch (range.era) {
        case "ERA_1_BASELINE":
          geomDrift = (rng() - 0.5) * 0.04;
          textureDrift = (rng() - 0.5) * 0.05;
          p0 = 0.78 + rng() * 0.12;
          p1 = 0.12 + rng() * 0.08;
          p2 = 0.02 + rng() * 0.04;
          fuzzy = rng() > 0.85 ? "STRONGLY_MATCHING" : (rng() > 0.15 ? "CONSISTENT" : "INSUFFICIENT_DATA");
          break;
        case "ERA_2_EARLY":
          geomDrift = (rng() - 0.45) * 0.08;
          textureDrift = (rng() - 0.4) * 0.08;
          p0 = 0.6 + rng() * 0.15;
          p1 = 0.25 + rng() * 0.15;
          p2 = 0.05 + rng() * 0.08;
          fuzzy = rng() > 0.6 ? "CONSISTENT" : (rng() > 0.3 ? "WEAK_EVIDENCE" : "SUSPICIOUS_TEXTURE");
          break;
        case "ERA_3_UDMURT":
          geomDrift = 0.12 + (rng() - 0.4) * 0.14;
          textureDrift = 0.08 + (rng() - 0.4) * 0.12;
          p0 = 0.32 + rng() * 0.18;
          p1 = 0.45 + rng() * 0.18;
          p2 = 0.12 + rng() * 0.18;
          fuzzy = rng() > 0.5 ? "GEOMETRIC_MISMATCH" : (rng() > 0.3 ? "SUSPICIOUS_TEXTURE" : "WEAK_EVIDENCE");
          break;
        case "ERA_4_TRANSITION":
          geomDrift = 0.06 + (rng() - 0.5) * 0.18;
          textureDrift = 0.1 + (rng() - 0.5) * 0.16;
          p0 = 0.28 + rng() * 0.2;
          p1 = 0.4 + rng() * 0.2;
          p2 = 0.15 + rng() * 0.2;
          fuzzy = rng() > 0.55 ? "GEOMETRIC_MISMATCH" : (rng() > 0.3 ? "SUSPICIOUS_TEXTURE" : "WEAK_EVIDENCE");
          break;
        case "ERA_5_VASILICH":
          geomDrift = 0.18 + (rng() - 0.4) * 0.16;
          textureDrift = 0.14 + (rng() - 0.4) * 0.14;
          p0 = 0.18 + rng() * 0.18;
          p1 = 0.35 + rng() * 0.18;
          p2 = 0.32 + rng() * 0.22;
          fuzzy = rng() > 0.5 ? "IDENTITY_ANOMALY" : (rng() > 0.25 ? "GEOMETRIC_MISMATCH" : "SUSPICIOUS_TEXTURE");
          break;
      }

      // Normalize
      const sum = p0 + p1 + p2;
      p0 /= sum; p1 /= sum; p2 /= sum;

      const dom: Hypothesis = p0 >= p1 && p0 >= p2 ? "H0" : (p1 >= p2 ? "H1" : "H2");

      const boneScore = 0.85 - geomDrift + (rng() - 0.5) * 0.08;
      const orbit = 0.34 + geomDrift * 0.9 + (rng() - 0.5) * 0.05;
      const chin = 0.46 + geomDrift * 1.3 + (rng() - 0.5) * 0.06;
      const jaw = 0.52 + geomDrift * 0.8 + (rng() - 0.5) * 0.04;
      const cheek = 0.48 + geomDrift * 0.7 + (rng() - 0.5) * 0.05;
      const symmetry = 0.92 - geomDrift * 0.5 + (rng() - 0.5) * 0.04;
      const bucket = POSE_BUCKETS[Math.floor(rng() * POSE_BUCKETS.length)];
      const yaw = POSE_YAW[bucket] + (rng() - 0.5) * 8;

      const siliconeProb = Math.max(0, Math.min(1, 0.15 + textureDrift * 1.8 + (rng() - 0.5) * 0.08));
      const specular = Math.max(0.05, 0.55 - textureDrift * 0.6 + (rng() - 0.5) * 0.1);
      const lbpEntropy = 0.62 + textureDrift * 0.9 + (rng() - 0.5) * 0.08;
      const frangi = Math.max(0.05, 0.48 - textureDrift * 0.9 + (rng() - 0.5) * 0.08);
      // wrinkles should grow monotonically with age
      const wrinkle = Math.max(0.05, Math.min(0.95, 0.1 + (ageYrs - 47) * 0.018 - textureDrift * 0.6 + (rng() - 0.5) * 0.08));
      const subsurface = 0.42 + textureDrift * 0.7 + (rng() - 0.5) * 0.06;

      // Visual age formula
      const wrinkleMix = (wrinkle * 0.6 + lbpEntropy * 0.4);
      const visualAge =
        45 + wrinkle * 40 + wrinkle * 0.7 * 35 + (lbpEntropy - 0.4) * 25 + lbpEntropy * 15 - specular * 10 + wrinkleMix * 18 - (range.era === "ERA_5_VASILICH" ? 4 : 0);
      const calendarAge = ageYrs;

      // z scores
      const zOrbitDepth = ((orbit - 0.34) / 0.03);
      const zChinProj = ((chin - 0.46) / 0.035);
      const zJawWidth = ((jaw - 0.52) / 0.03);
      const zCheek = ((cheek - 0.48) / 0.035);

      const flags: string[] = [];
      if (range.era === "ERA_3_UDMURT" && rng() > 0.85) flags.push("IMPOSSIBLE_SHORT");
      if (range.era === "ERA_4_TRANSITION" && rng() > 0.7) flags.push("TRANSITION");
      if (range.era === "ERA_5_VASILICH" && rng() > 0.6) flags.push("TEXTURE_SPIKE");
      if (range.era === "ERA_5_VASILICH" && p2 > 0.45) flags.push("IDENTITY_ANOMALY");
      if (Math.abs(zChinProj) > 2.8 && range.era !== "ERA_1_BASELINE") flags.push("TEMPORAL_IMPOSSIBILITY");
      if (rng() > 0.94) flags.push("RETURN_TO_BASELINE");

      if (flags.includes("TEMPORAL_IMPOSSIBILITY")) fuzzy = "TEMPORAL_IMPOSSIBILITY";

      const quality = Math.max(0.15, Math.min(0.99, 0.7 + (rng() - 0.4) * 0.4));
      const hidden = rng() > 0.985;
      const exifAnomaly = rng() > 0.985;
      const confidence = Math.max(0.25, Math.min(0.98, 0.55 + Math.abs(p0 - p1) * 0.6 + (rng() - 0.5) * 0.1));

      out.push({
        id, date, t,
        era: range.era, bucket, quality, hidden,
        boneScore: Math.max(0.1, Math.min(1, boneScore)),
        orbit, chin, jaw, cheek, symmetry, yaw,
        siliconeProb, specular, lbpEntropy, frangi, wrinkle, subsurface,
        visualAge, calendarAge,
        p0, p1, p2, dominant: dom, fuzzy, confidence,
        flags, exifAnomaly,
        zOrbitDepth, zChinProj, zJawWidth, zCheek,
      });
      idx++;
    }
  }
  return out;
}

export const PHOTOS: Photo[] = buildPhotos();

export const TIME_MIN = Date.parse("1999-01-01");
export const TIME_MAX = Date.parse("2026-06-30");
export const TIME_SPAN = TIME_MAX - TIME_MIN;

export const ERA_META: Record<Era, { label: string; color: string; start: string; end: string; short: string }> = {
  ERA_1_BASELINE: { label: "ERA 1 · BASELINE", short: "BASELINE", color: "#4f98a3", start: "1999-08-09", end: "2011-12-31" },
  ERA_2_EARLY: { label: "ERA 2 · EARLY", short: "EARLY", color: "#e8af34", start: "2012-01-01", end: "2014-12-31" },
  ERA_3_UDMURT: { label: "ERA 3 · UDMURT", short: "UDMURT", color: "#dd6974", start: "2015-01-01", end: "2021-09-08" },
  ERA_4_TRANSITION: { label: "ERA 4 · TRANSITION", short: "TRANSITION", color: "#fdab43", start: "2021-09-09", end: "2023-09-30" },
  ERA_5_VASILICH: { label: "ERA 5 · VASILICH", short: "VASILICH", color: "#a86fdf", start: "2023-10-01", end: "2026-06-04" },
};

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

export const EVENT_PINS: EventPin[] = [
  { id: "ev1", date: "2015-03-06", t: Date.parse("2015-03-06"), type: "DISAPPEARANCE", iconName: "alert-triangle", color: "#e8af34",
    title: "Исчезновение 2015 года", tooltip: "10-дневное исчезновение из публичного пространства; первые публикации о двойниках (BBC, 2015).",
    source: "BBC News · 11 марта 2015", folkTag: "Удмурт (народная классификация)" },
  { id: "ev2", date: "2015-01-01", t: Date.parse("2015-01-01"), type: "ERA_START", iconName: "play", color: "#dd6974",
    title: "Начало ЭПОХИ 3 · УДМУРТ", tooltip: "Старт периода ERA_3_UDMURT. 480 фотографий. Пик гипотезы об альтерации.", source: "Пайплайн DeepUtin" },
  { id: "ev3", date: "2021-09-09", t: Date.parse("2021-09-09"), type: "ERA_START", iconName: "play", color: "#fdab43",
    title: "Начало ЭПОХИ 4 · ПЕРЕХОД", tooltip: "Старт переходной зоны. Изменение паттернов геометрии.", source: "Пайплайн DeepUtin" },
  { id: "ev4", date: "2022-05-23", t: Date.parse("2022-05-23"), type: "POLITICAL", iconName: "volume", color: "#5591c7",
    title: "Заявление Буданова", tooltip: "Глава ГУР Украины публично заявил о возможной замене. Пресс-служба Кремля отвергла версию.",
    source: "Ukrainska Pravda · май 2022", folkTag: "Говорун (народная классификация)" },
  { id: "ev5", date: "2023-04-12", t: Date.parse("2023-04-12"), type: "AI_RESEARCH", iconName: "flask", color: "#4f98a3",
    title: "Японское AI-исследование", tooltip: "Японские исследователи опубликовали анализ внешних изменений с применением нейросетей.",
    source: "Asahi Shimbun · апрель 2023" },
  { id: "ev6", date: "2023-10-01", t: Date.parse("2023-10-01"), type: "ERA_START", iconName: "play", color: "#a86fdf",
    title: "Начало ЭПОХИ 5 · ВАСИЛИЧ", tooltip: "Старт периода ERA_5_VASILICH. Текущий доминирующий кластер биометрических признаков.", source: "Пайплайн DeepUtin" },
  { id: "ev7", date: "2024-02-18", t: Date.parse("2024-02-18"), type: "REPORT", iconName: "file-text", color: "#797876",
    title: "Доклад Минченко", tooltip: "Доклад политологического агентства об управлении публичным образом и информационным полем.",
    source: "Холдинг «Минченко-консалтинг» · февраль 2024", folkTag: "Кучма (народная классификация)" },
  { id: "ev8", date: "2017-06-14", t: Date.parse("2017-06-14"), type: "RTR", iconName: "rotate", color: "#e2e2e8",
    title: "Возврат к норме (RTR)", tooltip: "Флаг RETURN_TO_BASELINE: метрики статистически откатились к эталону ЭПОХИ 1.",
    source: "Пайплайн DeepUtin · RTR_RATIO=0.81" },
  { id: "ev9", date: "2020-11-04", t: Date.parse("2020-11-04"), type: "RTR", iconName: "rotate", color: "#e2e2e8",
    title: "Возврат к норме (RTR)", tooltip: "Флаг RETURN_TO_BASELINE: метрики статистически откатились к эталону ЭПОХИ 1.",
    source: "Пайплайн DeepUtin · RTR_RATIO=0.77" },
];

// Aggregate medians per N buckets for fast track rendering
export interface TrackPoint {
  t: number;
  date: string;
  value: number;
  zScore?: number;
  flag?: "warn" | "critical" | "impossible";
}

export function buildTrack(metric: (p: Photo) => number, refMedian: number, refStd: number, bucketCount = 360): TrackPoint[] {
  const step = TIME_SPAN / bucketCount;
  const out: TrackPoint[] = [];
  for (let i = 0; i < bucketCount; i++) {
    const t0 = TIME_MIN + i * step;
    const t1 = t0 + step;
    const vals: number[] = [];
    for (const p of PHOTOS) {
      if (p.t >= t0 && p.t < t1) vals.push(metric(p));
    }
    if (!vals.length) continue;
    vals.sort((a, b) => a - b);
    const median = vals[Math.floor(vals.length / 2)];
    const z = (median - refMedian) / refStd;
    const flag: TrackPoint["flag"] = Math.abs(z) > 3 ? "critical" : Math.abs(z) > 2 ? "warn" : undefined;
    out.push({ t: (t0 + t1) / 2, date: fmtDate(new Date((t0 + t1) / 2)), value: median, zScore: z, flag });
  }
  return out;
}

// Reference medians from ERA_1
function refMedians() {
  const era1 = PHOTOS.filter(p => p.era === "ERA_1_BASELINE");
  function med(arr: number[]) { const s = [...arr].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; }
  function std(arr: number[], m: number) {
    return Math.sqrt(arr.reduce((s, v) => s + (v - m) ** 2, 0) / arr.length);
  }
  const keys: (keyof Photo)[] = ["boneScore", "orbit", "chin", "jaw", "cheek", "symmetry", "yaw",
    "siliconeProb", "specular", "lbpEntropy", "frangi", "wrinkle", "subsurface", "visualAge"];
  const out: Record<string, { median: number; std: number }> = {};
  for (const k of keys) {
    const arr = era1.map(p => p[k] as number);
    const m = med(arr);
    out[k as string] = { median: m, std: Math.max(0.001, std(arr, m)) };
  }
  return out;
}

export const REF = refMedians();
