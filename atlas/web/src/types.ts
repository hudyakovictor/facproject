export type PoseId =
  | "frontal"
  | "three_quarter_left"
  | "three_quarter_right"
  | "profile_left"
  | "profile_right"
  | "unclassified";
export type Photo = {
  id: string;
  name: string;
  group: string;
  date: string | null;
  status: "ready" | "pending";
  pose: PoseId;
  angles: { yaw: number; pitch: number; roll: number };
  angle_override?: Record<string, number> | null;
  thumbnail: string;
  url: string;
  demo: boolean;
  precropped: boolean;
  meta: null | {
    feature_key: string;
    seconds: number;
    sharpness: number;
    alignment: { mode: string; confidence: number };
    model: string;
  };
  error?: string;
};
export type Model = {
  id: string;
  title: string;
  available: boolean;
  enabled: boolean;
  reason?: string;
  device?: string;
  backbone?: string;
};
export type Job = {
  id: string;
  kind: string;
  status: "queued" | "running" | "completed" | "cancelled" | "failed";
  progress: number;
  message: string;
  created: number;
  result?: any;
  params: any;
};
export type PoseProfile = {
  id: string;
  title: string;
  yaw: [number, number];
  pitch: [number, number];
  roll: [number, number];
};
export type Profiles = {
  version: number;
  convention: string;
  profiles: PoseProfile[];
};
export type Metric = {
  id: string;
  title: string;
  model: string;
  unit: string;
  inputs: string[];
  source: string;
  poses: Record<
    string,
    {
      enabled: boolean;
      thresholds: { warn: number; alert: number };
      config_file?: string;
    }
  >;
};
export type MetricValue = {
  value: number | null;
  z: number | null;
  reason?: string;
  n: number;
};
export type MetricRow = {
  id: string;
  date: string | null;
  group: string;
  pose: PoseId;
  metrics: Record<string, MetricValue>;
  sharpness: number;
};
export type MetricTable = {
  catalog: Metric[];
  rows: MetricRow[];
  config_version: string;
};
export type MeshData = {
  vertices: Float32Array;
  identity: Float32Array;
  albedo: Float32Array;
};
export type Topology = {
  triangles: number[][];
  landmarks: Record<string, number[]>;
  mean: number[][];
  vertex_count: number;
  triangle_count: number;
  units: string;
  version: string;
  uv?: number[][];
};
export type Projection = {
  points: {
    id: string;
    group: string;
    coords: number[];
    norm: number;
    cluster: number;
  }[];
  matrix: number[][];
  groups: string[];
  centroid_distances: number[][];
  dispersion: Record<string, number>;
  silhouette: number | null;
  explained_variance: number | null;
  method: string;
  note: string | null;
  seed: number;
  cache_hit: boolean;
  cache_key: string;
};
export type HeatSettings = {
  photoTexture: boolean;
  noiseCorrection: boolean;
  enabled: boolean;
  metric: "distance" | "identity" | "normal";
  reference: string;
  vmin: number;
  vmax: number;
  auto: boolean;
  percentile: number;
  gamma: number;
  opacity: number;
  outsideOpacity: number;
  palette: string;
  inverse: boolean;
  onlyAbove: boolean;
  smoothing: number;
  low: string;
  mid: string;
  high: string;
  midPosition: number;
  texture: boolean;
  wireframe: boolean;
  ldm68: boolean;
  ldm106: boolean;
  ldm134: boolean;
  pointSize: number;
  view: "front" | "left" | "right" | "profile";
};
