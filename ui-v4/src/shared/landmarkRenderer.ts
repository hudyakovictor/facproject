/**
 * Canvas 2D renderer for the Landmark Comparison workspace (Iteration 08).
 *
 * Projects 3D landmark points (chronology-aligned) with a perspective camera.
 * Point fill color is a CONTINUOUS displacement gradient:
 *
 *   зелёный (min/в пределах допуска) → жёлтый → красный (аномально) →
 *   бордовый (максимальное смещение)
 *
 * Points that exceed the calibrated same-person p95 (when a Stage 2 run
 * exists) get a white ring — the fill still encodes the gradient.
 * Supports overlay, side-by-side and blink modes, displacement vectors,
 * region filtering and orbit camera.
 */
import type { LandmarkComparePayload } from "./api";

export type CompareDisplayMode = "overlay" | "side_by_side" | "blink";

export interface CompareViewSettings {
  mode: CompareDisplayMode;
  showVectors: boolean;
  showLabels: boolean;
  showCalibrated: boolean; // ring highlight for points beyond calibrated p95
  tolerance: number;       // green → yellow boundary
  suspect: number;         // red anchor (anomalous)
  regions: Set<string>;    // empty = all
  blinkPhase?: number;     // 0..1 for blink mode
}

const COLORS = {
  hidden: "#3a4654",
  vector: "rgba(120,180,255,0.75)",
  label: "#9fb4c8",
  ring: "#e8f2ff",
  a: "#7ea8ff",
  b: "#ff9a68",
};

/**
 * Color ramp: green → yellow → red → burgundy (dark red).
 * Stops: 0 → #2ecc71, 0.25 → #ffe14d, 0.5 → #ff5c5c, 1 → #7f1d1d.
 */
const RAMP_STOPS: Array<[number, [number, number, number]]> = [
  [0.0, [46, 204, 113]],
  [0.25, [255, 225, 77]],
  [0.5, [255, 92, 92]],
  [1.0, [127, 29, 29]],
];

export function displacementRamp(t: number): [number, number, number] {
  const clamped = Math.min(1, Math.max(0, t));
  for (let i = 1; i < RAMP_STOPS.length; i++) {
    const [t0, c0] = RAMP_STOPS[i - 1];
    const [t1, c1] = RAMP_STOPS[i];
    if (clamped <= t1) {
      const f = (clamped - t0) / Math.max(1e-6, t1 - t0);
      return [
        Math.round(c0[0] + (c1[0] - c0[0]) * f),
        Math.round(c0[1] + (c1[1] - c0[1]) * f),
        Math.round(c0[2] + (c1[2] - c0[2]) * f),
      ];
    }
  }
  return RAMP_STOPS[RAMP_STOPS.length - 1][1];
}

function rgb(css: [number, number, number]): string {
  return `rgb(${css[0]},${css[1]},${css[2]})`;
}

/** Map a displacement magnitude onto the ramp.
 *  Scale anchor: max(suspect × 2, observed p95 × 1.2) — so "suspect" lands
 *  around orange-red and the biggest observed values saturate into burgundy.
 */
export function displacementColor(magnitude: number | null, suspect: number, observedP95: number | null): string {
  if (magnitude === null || !Number.isFinite(magnitude)) return COLORS.hidden;
  const scale = Math.max(suspect * 2, (observedP95 ?? 0) * 1.2, 1e-6);
  return rgb(displacementRamp(magnitude / scale));
}

function project(p: [number, number, number], yawDeg: number, elevDeg: number, dist: number, viewport: { w: number; h: number }): [number, number, number] {
  const yaw = (yawDeg * Math.PI) / 180;
  const elev = (elevDeg * Math.PI) / 180;
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const ce = Math.cos(elev), se = Math.sin(elev);
  const eye: [number, number, number] = [dist * cy * ce, dist * se, dist * sy * ce];
  const forward = norm(sub([0, 0, 0], eye));
  const up: [number, number, number] = [0, 1, 0];
  const right = norm(cross(up, forward));
  const camUp = cross(forward, right);
  const rel = sub(p, eye);
  const x = dot(rel, right);
  const y = dot(rel, camUp);
  const z = dot(rel, forward);
  if (z <= 0.02) return [NaN, NaN, z];
  const fov = (46 * Math.PI) / 180;
  const scale = viewport.h / (2 * Math.tan(fov / 2));
  const sx = viewport.w / 2 + (x / z) * scale;
  const sy2 = viewport.h / 2 - (y / z) * scale;
  return [sx, sy2, z];
}

function sub(a: number[], b: number[]): number[] { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function cross(a: number[], b: number[]): number[] {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}
function dot(a: number[], b: number[]): number { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function norm(v: number[]): number[] {
  const len = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / len, v[1] / len, v[2] / len];
}

/** Draw the gradient colorbar with threshold markers. */
function drawLegend(ctx: CanvasRenderingContext2D, viewport: { w: number; h: number }, tolerance: number, suspect: number, calibrated: boolean) {
  const x0 = 10;
  const y = viewport.h - 18;
  const width = Math.min(240, viewport.w - 60);
  const height = 10;
  const gradient = ctx.createLinearGradient(x0, 0, x0 + width, 0);
  for (const [t, color] of RAMP_STOPS) gradient.addColorStop(t, rgb(color));
  ctx.fillStyle = gradient;
  ctx.fillRect(x0, y, width, height);
  ctx.strokeStyle = "#2b3541";
  ctx.strokeRect(x0, y, width, height);

  const markerX = (t: number) => x0 + t * width;
  ctx.font = "9px ui-monospace, monospace";
  ctx.fillStyle = "#9fb4c8";
  const labels: Array<[number, string]> = [
    [0, "min"],
    [tolerance / Math.max(suspect * 2, 1e-6), "допустимо"],
    [0.5, "подозрительно"],
    [1, "макс"],
  ];
  for (const [t, label] of labels) {
    const x = markerX(Math.min(1, Math.max(0, t)));
    ctx.fillStyle = "#7e8a98";
    ctx.beginPath();
    ctx.moveTo(x, y + height);
    ctx.lineTo(x, y + height + 4);
    ctx.stroke();
    ctx.fillStyle = "#9fb4c8";
    ctx.fillText(label, Math.max(0, Math.min(viewport.w - 60, x - 14)), y + height + 14);
  }
  if (calibrated) {
    ctx.fillStyle = "#e8f2ff";
    ctx.fillText("○ — превышение cal. p95", x0 + width + 8, y + 8);
  }
}

export function drawLandmarkComparison(
  canvas: HTMLCanvasElement,
  data: LandmarkComparePayload,
  settings: CompareViewSettings,
  camera: { yaw: number; elev: number; dist: number },
): void {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.max(1, Math.floor(canvas.clientWidth * dpr));
  const h = Math.max(1, Math.floor(canvas.clientHeight * dpr));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  ctx.fillStyle = "#0a0e13";
  ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);

  const viewport = { w: canvas.clientWidth, h: canvas.clientHeight };
  const regionFiltered = settings.regions.size > 0;
  const points = data.points;
  const observedP95 = data.summary.p95;

  const projected = points.map((p, index) => {
    const pa: [number, number, number] = [p.x_a, p.y_a, p.z_a];
    const pb: [number, number, number] = [p.x_b, p.y_b, p.z_b];
    const projA = project(pa, camera.yaw, camera.elev, camera.dist, viewport);
    const projB = project(pb, camera.yaw, camera.elev, camera.dist, viewport);
    return { p, index, projA, projB, z: Math.min(projA[2], projB[2]) };
  }).sort((x, y) => x.z - y.z);

  const drawPoint = (x: number, y: number, color: string, radius: number, label?: string, dx?: number, dy?: number, ring = false) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    if (settings.showVectors && dx !== undefined && dy !== undefined) {
      ctx.strokeStyle = COLORS.vector;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + dx, y + dy);
      ctx.stroke();
    }
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    if (ring) {
      ctx.strokeStyle = COLORS.ring;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(x, y, radius + 2.2, 0, Math.PI * 2);
      ctx.stroke();
    }
    if (settings.showLabels && label !== undefined) {
      ctx.fillStyle = COLORS.label;
      ctx.font = "9px ui-monospace, monospace";
      ctx.fillText(label, x + 6, y - 4);
    }
  };

  const vectorScale = 26 / (settings.suspect || 0.05);

  const drawSide = (side: "a" | "b", label: string) => {
    ctx.save();
    if (settings.mode === "side_by_side") {
      ctx.translate(side === "a" ? 0 : viewport.w / 2, 0);
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.fillRect(0, 0, viewport.w / 2, viewport.h);
      ctx.fillStyle = COLORS[side];
      ctx.font = "11px ui-monospace, monospace";
      ctx.fillText(label, 8, 16);
    }
    for (const row of projected) {
      const { p, index } = row;
      if (regionFiltered && !settings.regions.has(p.region)) continue;
      if (side === "a" && !p.visible_a) continue;
      if (side === "b" && !p.visible_b) continue;
      const proj = side === "a" ? row.projA : row.projB;
      const [x, y] = proj;
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      const color = displacementColor(p.magnitude, settings.suspect, observedP95);
      const ring = settings.showCalibrated && Boolean(p.exceeds_calibration_p95);
      const dx = settings.showVectors ? (side === "a" ? p.dx * vectorScale : -p.dx * vectorScale) : undefined;
      const dy = settings.showVectors ? (side === "a" ? -p.dy * vectorScale : p.dy * vectorScale) : undefined;
      drawPoint(x, y, color, side === "a" ? 2.6 : 3.4, undefined, dx, dy, ring);
    }
    ctx.restore();
  };

  switch (settings.mode) {
    case "side_by_side":
      drawSide("a", `A · ${data.photo_a}`);
      drawSide("b", `B · ${data.photo_b}`);
      break;
    case "blink": {
      const showA = (settings.blinkPhase ?? 0) < 0.5;
      drawSide(showA ? "a" : "b", showA ? `A · ${data.photo_a}` : `B · ${data.photo_b}`);
      break;
    }
    case "overlay":
    default: {
      for (const row of projected) {
        const { p, index } = row;
        if (regionFiltered && !settings.regions.has(p.region)) continue;
        const [x, y] = row.projA;
        if (!Number.isFinite(x) || !Number.isFinite(y) || !p.visible_a) continue;
        drawPoint(x, y, COLORS.a, 2.2);
      }
      for (const row of projected) {
        const { p, index } = row;
        if (regionFiltered && !settings.regions.has(p.region)) continue;
        const [x, y] = row.projB;
        if (!Number.isFinite(x) || !Number.isFinite(y) || !p.visible_b) continue;
        const color = displacementColor(p.magnitude, settings.suspect, observedP95);
        const ring = settings.showCalibrated && Boolean(p.exceeds_calibration_p95);
        const dx = settings.showVectors ? p.dx * vectorScale : undefined;
        const dy = settings.showVectors ? -p.dy * vectorScale : undefined;
        drawPoint(x, y, color, 3.6, settings.showLabels ? String(index) : undefined, dx, dy, ring);
      }
    }
  }

  drawLegend(ctx, viewport, settings.tolerance, settings.suspect, Boolean(settings.showCalibrated && data.summary.calibrated));
}
