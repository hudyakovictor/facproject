import type { HeatSettings, MeshData, Topology } from "./types";
export const palettes: Record<string, string[]> = {
  turbo: ["#30123b", "#3a74e8", "#29c7a5", "#b0ed3d", "#f8aa27", "#cc321b"],
  viridis: ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
  coolwarm: ["#3b4cc0", "#8db0fe", "#dddddd", "#f49a7b", "#b40426"],
};
function rgb(hex: string) {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
}
export function paletteColor(t: number, h: HeatSettings) {
  t = Math.max(0, Math.min(1, t));
  if (h.inverse) t = 1 - t;
  t = Math.pow(t, h.gamma);
  if (h.palette === "custom") {
    const p = [rgb(h.low), rgb(h.mid), rgb(h.high)];
    const mid = h.midPosition,
      a = t < mid ? 0 : 1,
      x = t < mid ? t / mid : (t - mid) / (1 - mid);
    return p[a].map((v, i) => v * (1 - x) + p[a + 1][i] * x);
  }
  const pal = palettes[h.palette] || palettes.turbo,
    x = t * (pal.length - 1),
    i = Math.min(Math.floor(x), pal.length - 2),
    q = x - i,
    a = rgb(pal[i]),
    b = rgb(pal[i + 1]);
  return a.map((v, k) => v * (1 - q) + b[k] * q);
}
const graphCache = new WeakMap<
  Topology,
  { indices: Uint32Array; neighbors: number[][] }
>();
export function graph(topo: Topology) {
  let g = graphCache.get(topo);
  if (!g) {
    const sets = Array.from(
      { length: topo.vertex_count },
      () => new Set<number>(),
    );
    for (const [a, b, c] of topo.triangles) {
      sets[a].add(b).add(c);
      sets[b].add(a).add(c);
      sets[c].add(a).add(b);
    }
    g = {
      indices: new Uint32Array(topo.triangles.flat()),
      neighbors: sets.map((s) => Array.from(s)),
    };
    graphCache.set(topo, g);
  }
  return g;
}
export function vertexNormals(v: Float32Array, tri: number[][]) {
  const out = new Float32Array(v.length);
  for (const [a, b, c] of tri) {
    const ax = v[b * 3] - v[a * 3],
      ay = v[b * 3 + 1] - v[a * 3 + 1],
      az = v[b * 3 + 2] - v[a * 3 + 2],
      bx = v[c * 3] - v[a * 3],
      by = v[c * 3 + 1] - v[a * 3 + 1],
      bz = v[c * 3 + 2] - v[a * 3 + 2];
    const n = [ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx];
    for (const j of [a, b, c])
      for (let k = 0; k < 3; k++) out[j * 3 + k] += n[k];
  }
  for (let i = 0; i < out.length; i += 3) {
    const len = Math.hypot(out[i], out[i + 1], out[i + 2]) || 1;
    for (let k = 0; k < 3; k++) out[i + k] /= len;
  }
  return out;
}
export type HeatStats = {
  hist: number[];
  mean: number;
  p95: number;
  max: number;
  hi: number;
  lo: number;
  vertices: number;
};
export function calculate(
  a: MeshData,
  b: MeshData,
  ref: MeshData,
  t: number,
  h: HeatSettings,
  topo: Topology,
  noiseThreshold?: number[] | null,
) {
  const n = a.vertices.length / 3,
    positions = new Float32Array(n * 3),
    colors = new Float32Array(n * 3);
  let values = new Float32Array(n),
    endpoint = new Float32Array(n);
  const normal =
    h.metric === "normal" ? vertexNormals(ref.vertices, topo.triangles) : null;
  for (let i = 0; i < n; i++) {
    let sum = 0,
      esum = 0,
      dot = 0,
      edot = 0;
    for (let k = 0; k < 3; k++) {
      const j = i * 3 + k;
      positions[j] = a.vertices[j] * (1 - t) + b.vertices[j] * t;
      const key = h.metric === "identity" ? "identity" : "vertices";
      const d = a[key][j] * (1 - t) + b[key][j] * t - ref[key][j],
        e = b[key][j] - ref[key][j];
      sum += d * d;
      esum += e * e;
      if (normal) {
        dot += d * normal[j];
        edot += e * normal[j];
      }
    }
    values[i] = normal ? Math.abs(dot) : Math.sqrt(sum);
    endpoint[i] = normal ? Math.abs(edot) : Math.sqrt(esum);
  }
  if (h.smoothing) {
    const { neighbors } = graph(topo);
    for (let pass = 0; pass < h.smoothing; pass++) {
      const next = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        let sum = values[i];
        for (const k of neighbors[i]) sum += values[k];
        next[i] = sum / (neighbors[i].length + 1);
      }
      values = next;
    }
  }
  if (h.noiseCorrection && h.metric === "distance" && noiseThreshold?.length === n) {
    for (let i = 0; i < n; i++) {
      values[i] = Math.max(0, values[i] - noiseThreshold[i]);
      endpoint[i] = Math.max(0, endpoint[i] - noiseThreshold[i]);
    }
  }
  const sorted = Array.from(values).sort((a, b) => a - b),
    ends = Array.from(endpoint).sort((a, b) => a - b);
  const hi = h.auto
      ? Math.max(
          ends[Math.min(n - 1, Math.floor((n * h.percentile) / 100))],
          0.0002,
        )
      : Math.max(h.vmax, h.vmin + 0.00001),
    lo = h.vmin;
  const max = sorted[n - 1] || 0,
    p95 = sorted[Math.floor(n * 0.95)] || 0,
    mean = values.reduce((s, v) => s + v, 0) / n;
  const hist = Array(36).fill(0);
  for (const v of values)
    hist[Math.min(35, Math.floor((v / Math.max(max, 1e-8)) * 35))]++;
  for (let i = 0; i < n; i++) {
    const v = values[i],
      color = paletteColor((v - lo) / (hi - lo), h);
    const outside = v < lo || v > hi;
    const rawAlpha = h.enabled
      ? h.onlyAbove && v < lo
        ? 0
        : outside
          ? h.outsideOpacity
          : h.opacity
      : 0;
    // Keep the original photo visibly recognizable under the heat overlay.
    const alpha = h.photoTexture ? rawAlpha * 0.32 : rawAlpha;
    for (let k = 0; k < 3; k++) {
      const j = i * 3 + k,
        base = h.photoTexture
          ? 1.0
          : h.texture
            ? a.albedo[j] * (1 - t) + b.albedo[j] * t
            : [0.53, 0.59, 0.65][k];
      const srgb = base * (1 - alpha) + color[k] * alpha;
      colors[j] =
        srgb <= 0.04045 ? srgb / 12.92 : Math.pow((srgb + 0.055) / 1.055, 2.4);
    }
  }
  return {
    positions,
    colors,
    values,
    stats: { hist, mean, p95, max, hi, lo, vertices: n } as HeatStats,
  };
}
