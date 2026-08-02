/** Генератор встроенного демонстрационного набора (1809 кадров).
 *
 * 🚨 WARNING: это СИНТЕТИЧЕСКИЕ данные, детерминированно порождённые
 * seeded-PRNG (mulberry32). Они не являются результатом анализа и служат
 * единственной цели — показать работоспособность интерфейса, когда
 * backend недоступен.
 *
 * Модуль вынесен из `data.ts` и загружается ТОЛЬКО динамическим импортом
 * (аудит №27). Раньше 170 строк генератора и построенный им массив из
 * 1809 объектов попадали в основной бандл и исполнялись на старте — даже
 * при полностью рабочем backend, когда демо-набор не нужен ни разу.
 *
 * 📤 API: buildDemoPhotos()
 */
import type { Era, FuzzyLabel, Hypothesis, Photo } from "./data";
import { POSE_BUCKETS, POSE_YAW } from "./data";

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




export function buildDemoPhotos(): Photo[] {
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
