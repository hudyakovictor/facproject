import { PhotoPoint, Era, FuzzyLabel, Hypothesis, PoseBucket, EventPinDef, ERA_DEFS } from "../types";

// Seeded pseudo-random for deterministic output
function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rng = mulberry32(42);

function randBetween(a: number, b: number) {
  return a + rng() * (b - a);
}
function clamp(v: number, a: number, b: number) {
  return Math.max(a, Math.min(b, v));
}

const POSES: PoseBucket[] = ["frontal_0", "frontal_yaw15", "frontal_yaw30", "profile_L", "profile_R"];

function pickPose(): PoseBucket {
  const r = rng();
  if (r < 0.45) return POSES[0];
  if (r < 0.7) return POSES[1];
  if (r < 0.85) return POSES[2];
  if (r < 0.93) return POSES[3];
  return POSES[4];
}

// Era-specific drifts applied to geometry & texture
function eraDrift(era: Era) {
  switch (era) {
    case "ERA_1":
      return { geo: 0, tex: 0 };
    case "ERA_2":
      return { geo: 0.02, tex: 0.01 };
    case "ERA_3":
      return { geo: 0.09, tex: 0.04 };
    case "ERA_4":
      return { geo: 0.13, tex: 0.06 };
    case "ERA_5":
      return { geo: 0.18, tex: 0.09 };
  }
}

function computeLabel(
  p0: number,
  p1: number,
  p2: number,
  geometryScore: number,
  flags: string[],
  quality: number
): FuzzyLabel {
  if (flags.includes("TEMPORAL_IMPOSSIBILITY")) return "TEMPORAL_IMPOSSIBILITY";
  if (p2 > 0.55) return "IDENTITY_ANOMALY";
  if (p1 > 0.5 && geometryScore < 0.65) return "GEOMETRIC_MISMATCH";
  if (flags.includes("TEXTURE_SPIKE")) return "SUSPICIOUS_TEXTURE";
  if (p0 > 0.75 && geometryScore > 0.78) return "STRONGLY_MATCHING";
  if (p0 > 0.55) return "CONSISTENT";
  if (quality < 0.35) return "INSUFFICIENT_DATA";
  return "WEAK_EVIDENCE";
}

function dominantHyp(p0: number, p1: number, p2: number): Hypothesis {
  if (p0 >= p1 && p0 >= p2) return "H0";
  if (p1 >= p0 && p1 >= p2) return "H1";
  return "H2";
}

export function generateDataset(): PhotoPoint[] {
  const photos: PhotoPoint[] = [];
  const startDate = new Date("1999-10-07T00:00:00Z").getTime();
  // Generate photos per era proportionally
  for (const era of ERA_DEFS) {
    const eraStart = new Date(`${era.startYear}-01-01`).getTime();
    const eraEnd = new Date(`${era.endYear + 1}-01-01`).getTime() - 1;
    for (let i = 0; i < era.count; i++) {
      // Cluster photos non-uniformly within era
      const t = eraStart + rng() * (eraEnd - eraStart);
      const d = new Date(t);
      const date = d.toISOString().slice(0, 10);
      const year = d.getFullYear();
      const ageAtDate = (t - startDate) / (1000 * 60 * 60 * 24 * 365.25);

      const drift = eraDrift(era.id);
      const noise = randBetween(-0.08, 0.08);

      // Geometry metrics (centered on 0.7 baseline for ERA_1, drift down)
      const orbits = clamp(0.7 + randBetween(-0.04, 0.04) - drift.geo * 0.6, 0.3, 0.95);
      const chin = clamp(0.72 + randBetween(-0.05, 0.05) - drift.geo * 0.8, 0.3, 0.95);
      const jaw = clamp(0.7 + randBetween(-0.05, 0.05) - drift.geo * 0.9, 0.3, 0.95);
      const cheekbones = clamp(0.7 + randBetween(-0.04, 0.04) - drift.geo * 0.7, 0.3, 0.95);
      const symmetry = clamp(0.82 + randBetween(-0.08, 0.06) - drift.geo * 0.4, 0.4, 0.98);
      const poseYaw = randBetween(-35, 35);
      const boneScore = clamp(
        (orbits + chin + jaw + cheekbones + symmetry) / 5 + noise,
        0.2,
        0.95
      );

      // Texture metrics
      const silicone = clamp(0.05 + drift.tex * 3 + randBetween(-0.05, 0.12), 0, 0.9);
      const gloss = clamp(0.55 - drift.tex * 1.2 + randBetween(-0.15, 0.2), 0.1, 0.95);
      const lbp = clamp(0.4 + drift.tex * 1.5 + randBetween(-0.1, 0.15), 0.1, 0.95);
      const frangi = clamp(0.7 - drift.tex * 1.8 + randBetween(-0.1, 0.1), 0.1, 0.95);
      const wrinkle = clamp(
        0.15 + (year - 1999) * 0.02 + randBetween(-0.08, 0.08),
        0.05,
        0.95
      );
      const subsurface = clamp(0.6 + drift.tex * 0.8 + randBetween(-0.1, 0.15), 0.2, 0.95);

      const visualAge =
        45 +
        wrinkle * 40 +
        (wrinkle * 0.5) * 35 +
        lbp * 15 +
        gloss * -10 +
        drift.tex * 20 +
        randBetween(-2, 2);
      const calendarAge = 47 + ageAtDate;

      const quality = clamp(
        0.7 - Math.abs(poseYaw) / 90 + randBetween(-0.2, 0.15),
        0.1,
        0.98
      );

      // Bayesian posteriors
      let p0 = clamp(boneScore * 0.9 + randBetween(-0.1, 0.1) - drift.geo * 1.5, 0.05, 0.95);
      let p1 = clamp(drift.geo * 2.5 + silicone * 0.8 + randBetween(-0.05, 0.15), 0.02, 0.85);
      let p2 = clamp(drift.geo * 2 + (silicone > 0.35 ? 0.3 : 0) + randBetween(-0.05, 0.15), 0.01, 0.75);
      // Normalize
      const sum = p0 + p1 + p2;
      p0 = p0 / sum;
      p1 = p1 / sum;
      p2 = p2 / sum;

      const confidence = Math.max(p0, p1, p2);

      // Flags
      const flags: string[] = [];
      const geoDeviation = Math.abs(boneScore - 0.7);
      if (geoDeviation > 0.15 && era.id !== "ERA_1") flags.push("IMPOSSIBLE_SHORT");
      if (silicone > 0.35 && subsurface > 0.7) flags.push("TEXTURE_SPIKE");
      if (era.id === "ERA_1" || (era.id === "ERA_3" && boneScore > 0.68 && rng() < 0.08))
        flags.push("RETURN_TO_BASELINE");
      if (era.id === "ERA_4") flags.push("TRANSITION");
      if (geoDeviation > 0.22 && era.id === "ERA_5" && rng() < 0.05)
        flags.push("TEMPORAL_IMPOSSIBILITY");

      const dominant = dominantHyp(p0, p1, p2);
      const fuzzyLabel = computeLabel(p0, p1, p2, boneScore, flags, quality);

      const id = `p_${year}_${String(i).padStart(4, "0")}`;

      photos.push({
        id,
        date,
        year,
        timestamp: t,
        era: era.id,
        pose: pickPose(),
        quality,
        fuzzyLabel,
        dominant,
        p0,
        p1,
        p2,
        confidence,
        flags,
        geometry: {
          boneScore,
          orbits,
          chin,
          jaw,
          cheekbones,
          symmetry,
          poseYaw,
        },
        texture: { silicone, gloss, lbp, frangi, wrinkle, subsurface },
        visualAge: clamp(visualAge, 40, 85),
        calendarAge,
        hidden: rng() < 0.008,
      });
    }
  }

  return photos.sort((a, b) => a.timestamp - b.timestamp);
}

export const EVENT_PINS: EventPinDef[] = [
  {
    date: "2015-03-15",
    label: "DISAPPEARANCE_2015",
    icon: "⚠",
    kind: "disappearance",
    color: "#e8af34",
    excerpt:
      "10-дневное исчезновение из публичного пространства; первые публикации о двойниках.",
    source: "BBC, 2015",
  },
  {
    date: "2022-03-15",
    label: "BUDAN_STATEMENT",
    icon: "◉",
    kind: "statement",
    color: "#5591c7",
    excerpt: "Заявление Буданова о возможной замене. Пресс-служба Кремля отвергла.",
    source: "Press statement, 2022",
  },
  {
    date: "2023-05-10",
    label: "JP_AI_STUDY",
    icon: "◈",
    kind: "study",
    color: "#4f98a3",
    excerpt: "Японское AI-исследование внешних изменений, опубликованное в открытом доступе.",
    source: "JP Research, 2023",
  },
  {
    date: "2024-04-22",
    label: "MINCHENKO_REPORT",
    icon: "▤",
    kind: "report",
    color: "#797876",
    excerpt: "Доклад: публичный образ, управление информационным полем.",
    source: "Minchenko Consulting, 2024",
  },
  {
    date: "2015-01-01",
    label: "ERA_3_START",
    icon: "▶",
    kind: "era",
    color: "#dd6974",
    excerpt: "Начало ERA_3_UDMURT. 480 фото. Пик H_UDMURT-гипотезы.",
    source: "Pipeline",
  },
  {
    date: "2021-09-09",
    label: "ERA_4_START",
    icon: "▶",
    kind: "era",
    color: "#fdab43",
    excerpt: "Начало Transition Zone. Изменение паттернов геометрии.",
    source: "Pipeline",
  },
  {
    date: "2023-10-01",
    label: "ERA_5_START",
    icon: "▶",
    kind: "era",
    color: "#a86fdf",
    excerpt: "Начало ERA_5_VASILICH. Текущий доминирующий кластер.",
    source: "Pipeline",
  },
];
