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
export type NormalizedMesh = {
  topology: Topology;
  vertices: Float32Array;
  identity: Float32Array;
  iod: number;
};
const normalizedCache = new WeakMap<MeshData, NormalizedMesh>();
/** Remove per-frame global translation/scale before shape comparison/rendering.
 * The displayed IOD change is retained separately in HeatStats. */
export function normalizeMesh(mesh: MeshData, topo: Topology): NormalizedMesh {
  const cached = normalizedCache.get(mesh);
  if (cached?.topology === topo) return cached;
  const lm = topo.landmarks.ldm68;
  if (!lm || lm.length < 48) {
    const fallback = { topology: topo, vertices: mesh.vertices, identity: mesh.identity, iod: 1 };
    normalizedCache.set(mesh, fallback);
    return fallback;
  }
  const center = [0, 0, 0];
  const left = [0, 0, 0];
  const right = [0, 0, 0];
  for (let i = 36; i < 42; i++)
    for (let k = 0; k < 3; k++) left[k] += mesh.vertices[lm[i] * 3 + k] / 6;
  for (let i = 42; i < 48; i++)
    for (let k = 0; k < 3; k++) right[k] += mesh.vertices[lm[i] * 3 + k] / 6;
  let iod = 0;
  for (let k = 0; k < 3; k++) {
    center[k] = (left[k] + right[k]) / 2;
    iod += (left[k] - right[k]) ** 2;
  }
  iod = Math.sqrt(iod);
  if (!Number.isFinite(iod) || iod < 1e-8) iod = 1;
  const vertices = new Float32Array(mesh.vertices.length);
  const identity = new Float32Array(mesh.identity.length);
  for (let i = 0; i < vertices.length; i += 3)
    for (let k = 0; k < 3; k++) {
      vertices[i + k] = (mesh.vertices[i + k] - center[k]) / iod;
      identity[i + k] = (mesh.identity[i + k] - center[k]) / iod;
    }
  const out = { topology: topo, vertices, identity, iod };
  normalizedCache.set(mesh, out);
  return out;
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
  iodCurrent: number;
  iodReference: number;
  scaleChangePct: number;
};
export type ServerHeat = {
  start: Float32Array;
  end: Float32Array;
  vmax?: number;
};
const decodeFloats = (b64: string) => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Float32Array(bytes.buffer);
};
/** Values already computed by server/heat.py (normal metric, calibrated weights). */
export function decodeHeat(payload: {
  start: string;
  end: string;
  vmax?: number;
}): ServerHeat {
  return {
    start: decodeFloats(payload.start),
    end: decodeFloats(payload.end),
    vmax: payload.vmax,
  };
}
export function calculate(
  a: MeshData,
  b: MeshData,
  ref: MeshData,
  t: number,
  h: HeatSettings,
  topo: Topology,
  noiseThreshold?: number[] | null,
  morphing = false,
  server?: ServerHeat | null,
) {
  const na = normalizeMesh(a, topo),
    nb = normalizeMesh(b, topo),
    nr = normalizeMesh(ref, topo),
    n = a.vertices.length / 3,
    positions = new Float32Array(n * 3),
    colors = new Float32Array(n * 3),
    key = h.metric === "identity" ? "identity" : "vertices",
    av = h.normalizeScale ? na[key] : a[key],
    bv = h.normalizeScale ? nb[key] : b[key],
    rv = h.normalizeScale ? nr[key] : ref[key],
    posA = h.normalizeScale ? na.vertices : a.vertices,
    posB = h.normalizeScale ? nb.vertices : b.vertices,
    refPositions = h.normalizeScale ? nr.vertices : ref.vertices;
  // Server values replace the metric + weighting + smoothing chain entirely:
  // the backend owns those formulas so preview and export cannot diverge.
  const srv =
    server && server.start.length === n && server.end.length === n
      ? server
      : null;
  let values = new Float32Array(n),
    endpoint = new Float32Array(n),
    startValues = new Float32Array(n),
    endValues = new Float32Array(n);
  const normal =
    !srv && h.metric === "normal"
      ? vertexNormals(morphing ? posA : refPositions, topo.triangles)
      : null;
  const iodCurrent = na.iod * (1 - t) + nb.iod * t,
    iodReference = nr.iod,
    scaleChangePct = 100 * (iodCurrent / Math.max(iodReference, 1e-8) - 1),
    noiseScale = h.normalizeScale
      ? 1 / Math.max(((morphing ? na.iod + nb.iod : iodCurrent + nr.iod) / 2), 1e-8)
      : 1;
  for (let i = 0; i < n; i++) {
    let startSum = 0,
      endSum = 0,
      startDot = 0,
      endDot = 0;
    for (let k = 0; k < 3; k++) {
      const j = i * 3 + k;
      positions[j] = posA[j] * (1 - t) + posB[j] * t;
      // Morph heat is an interpolation between the adjacent pair maps. The
      // segment starts at its predecessor's map and ends at this pair's map,
      // so the field remains continuous at A→B→C keyframes (and starts at 0).
      const startDelta = morphing
          ? av[j] - rv[j]
          : av[j] * (1 - t) + bv[j] * t - rv[j],
        endDelta = morphing ? bv[j] - av[j] : bv[j] - rv[j];
      startSum += startDelta * startDelta;
      endSum += endDelta * endDelta;
      if (normal) {
        startDot += startDelta * normal[j];
        endDot += endDelta * normal[j];
      }
    }
    const startValue = srv
        ? srv.start[i]
        : normal
          ? Math.abs(startDot)
          : Math.sqrt(startSum),
      endValue = srv
        ? srv.end[i]
        : normal
          ? Math.abs(endDot)
          : Math.sqrt(endSum);
    startValues[i] = startValue;
    endValues[i] = morphing ? endValue : startValue;
    values[i] = morphing
      ? startValue * (1 - t) + endValue * t
      : startValue;
    endpoint[i] = morphing ? Math.max(startValue, endValue) : endValue;
  }
  if (h.smoothing && !srv) {
    const { neighbors } = graph(topo);
    const smooth = (input: Float32Array) => {
      let field = input;
      for (let pass = 0; pass < h.smoothing; pass++) {
        const next = new Float32Array(n);
        for (let i = 0; i < n; i++) {
          let sum = field[i];
          for (const k of neighbors[i]) sum += field[k];
          next[i] = sum / (neighbors[i].length + 1);
        }
        field = next;
      }
      return field;
    };
    if (morphing) {
      startValues.set(smooth(startValues));
      endValues.set(smooth(endValues));
      for (let i = 0; i < n; i++) {
        values[i] = startValues[i] * (1 - t) + endValues[i] * t;
        endpoint[i] = Math.max(startValues[i], endValues[i]);
      }
    } else {
      values.set(smooth(values));
    }
  }
  if (!srv && h.noiseCorrection && h.metric === "distance" && noiseThreshold?.length === n) {
    for (let i = 0; i < n; i++) {
      const threshold = noiseThreshold[i] * noiseScale;
      startValues[i] = Math.max(0, startValues[i] - threshold);
      endValues[i] = Math.max(0, endValues[i] - threshold);
      values[i] = morphing
        ? startValues[i] * (1 - t) + endValues[i] * t
        : Math.max(0, values[i] - threshold);
      endpoint[i] = morphing
        ? Math.max(startValues[i], endValues[i])
        : Math.max(0, endpoint[i] - threshold);
    }
  }
  const sorted = Array.from(values).sort((a, b) => a - b),
    ends = Array.from(endpoint).sort((a, b) => a - b);
  const autoHi = Math.max(
    ends[Math.min(n - 1, Math.floor((n * h.percentile) / 100))],
    0.0002,
  );
  // A saved lower bound can become larger than the new segment's 95th
  // percentile. In auto mode, fall back to zero instead of reversing the range
  // and making the entire map nearly transparent.
  const lo = Math.max(0, h.auto && h.vmin >= autoHi ? 0 : h.vmin);
  // Calibrated values live in noise units, so the backend VMAX wins.
  const hi = srv?.vmax
    ? Math.max(srv.vmax, lo + 0.00001)
    : h.auto
      ? autoHi
      : Math.max(h.vmax, lo + 0.00001);
  const max = sorted[n - 1] || 0,
    p95 = sorted[Math.floor(n * 0.95)] || 0,
    mean = values.reduce((s, v) => s + v, 0) / n;
  const hist = Array(36).fill(0);
  for (const v of values)
    hist[Math.min(35, Math.floor((v / Math.max(max, 1e-8)) * 35))]++;
  const alphaAt = (v: number) =>
    !h.enabled ? 0 : v <= lo ? (h.onlyAbove ? 0 : h.outsideOpacity) : h.opacity;
  for (let i = 0; i < n; i++) {
    const v = values[i];
    const colorA = paletteColor((startValues[i] - lo) / (hi - lo), h),
      colorB = paletteColor((endValues[i] - lo) / (hi - lo), h),
      color = morphing
        ? colorA.map((c, k) => c * (1 - t) + colorB[k] * t)
        : paletteColor((v - lo) / (hi - lo), h),
      alphaA = alphaAt(startValues[i]),
      alphaB = alphaAt(endValues[i]),
      rawAlpha = morphing ? alphaA * (1 - t) + alphaB * t : alphaAt(v);
    // Blend endpoint colors and alpha, not just scalar magnitudes. This makes
    // A start transparent and fade into ΔAB, while B starts with ΔAB and
    // continuously morphs that existing map into ΔBC.
    const alpha = h.photoTexture ? rawAlpha * 0.72 : rawAlpha;
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
    stats: {
      hist, mean, p95, max, hi, lo, vertices: n,
      iodCurrent, iodReference, scaleChangePct,
    } as HeatStats,
  };
}
