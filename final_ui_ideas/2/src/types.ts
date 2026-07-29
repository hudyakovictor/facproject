export type Era = "ERA_1" | "ERA_2" | "ERA_3" | "ERA_4" | "ERA_5";

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

export type PoseBucket = "frontal_0" | "frontal_yaw15" | "frontal_yaw30" | "profile_L" | "profile_R";

export interface PhotoPoint {
  id: string; // photo_id
  date: string; // YYYY-MM-DD
  year: number;
  timestamp: number;
  era: Era;
  pose: PoseBucket;
  quality: number; // 0-1
  fuzzyLabel: FuzzyLabel;
  dominant: Hypothesis;
  p0: number; // P(H0)
  p1: number; // P(H1)
  p2: number; // P(H2)
  confidence: number;
  flags: string[];
  geometry: {
    boneScore: number;
    orbits: number;
    chin: number;
    jaw: number;
    cheekbones: number;
    symmetry: number;
    poseYaw: number;
  };
  texture: {
    silicone: number;
    gloss: number;
    lbp: number;
    frangi: number;
    wrinkle: number;
    subsurface: number;
  };
  visualAge: number;
  calendarAge: number;
  hidden?: boolean;
}

export interface EventPinDef {
  date: string;
  label: string;
  icon: string;
  kind: "disappearance" | "statement" | "study" | "report" | "era" | "return";
  color: string;
  excerpt: string;
  source: string;
}

export const ERA_DEFS: {
  id: Era;
  label: string;
  startYear: number;
  endYear: number;
  color: string;
  count: number;
}[] = [
  { id: "ERA_1", label: "BASELINE", startYear: 1999, endYear: 2011, color: "#4f98a3", count: 520 },
  { id: "ERA_2", label: "EARLY", startYear: 2012, endYear: 2014, color: "#e8af34", count: 180 },
  { id: "ERA_3", label: "UDMURT", startYear: 2015, endYear: 2021, color: "#dd6974", count: 480 },
  { id: "ERA_4", label: "TRANSITION", startYear: 2021, endYear: 2023, color: "#fdab43", count: 210 },
  { id: "ERA_5", label: "VASILICH", startYear: 2023, endYear: 2026, color: "#a86fdf", count: 419 },
];

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

export const HYP_COLORS: Record<Hypothesis, string> = {
  H0: "#6daa45",
  H1: "#fdab43",
  H2: "#a13544",
};
