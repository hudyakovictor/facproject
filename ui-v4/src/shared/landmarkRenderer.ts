/**
 * Canvas 2D renderer for the Landmark Comparison workspace (Iteration 08).
 *
 * Projects 3D landmark points (chronology-aligned) with a perspective camera
 * and draws them colored by per-point displacement against the reviewer
 * thresholds (tolerance / suspect). Supports overlay, side-by-side and blink
 * comparison modes, displacement vectors, region filtering and orbit camera.
 */
import type { LandmarkComparePayload } from "./api";

export type CompareDisplayMode = "overlay" | "side_by_side" | "blink";

export interface CompareViewSettings {
  mode: CompareDisplayMode;
  showVectors: boolean;
  showLabels: boolean;
  showCalibrated: boolean; // highlight points beyond calibrated p95 (if available)
  tolerance: number;       // green → orange boundary
  suspect: number;         // orange → red boundary
  regions: Set<string>;    // empty = all
  blinkPhase?: number;     // 0..1 for blink mode
}

const COLORS = {
  good: "#5fd68a",
  warn: "#f0b84d",
  bad: "#f0656f",
  hidden: "#3a4654",
  vector: "rgba(120,180,255,0.75)",
  label: "#9fb4c8",
  calibrated: "#e878ff",
  a: "#7ea8ff",
  b: "#ff9a68",
};

function project(p: [number, number, number], yawDeg: number, elevDeg: number, dist: number, viewport: { w: number; h: number }): [number, number, number] {
  const yaw = (yawDeg * Math.PI) / 180;
  const elev = (elevDeg * Math.PI) / 180;
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const ce = Math.cos(elev), se = Math.sin(elev);
  const eye: [number, number, number] = [dist * cy * ce, dist * se, dist * sy * ce];
  // camera basis
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

  // draw order: sort by depth so nearer points are on top
  const projected = points.map((p, index) => {
    const pa: [number, number, number] = [p.x_a, p.y_a, p.z_a];
    const pb: [number, number, number] = [p.x_b, p.y_b, p.z_b];
    const projA = project(pa, camera.yaw, camera.elev, camera.dist, viewport);
    const projB = project(pb, camera.yaw, camera.elev, camera.dist, viewport);
    return { p, index, projA, projB, z: Math.min(projA[2], projB[2]) };
  }).sort((x, y) => x.z - y.z);

  const drawPoint = (x: number, y: number, color: string, radius: number, label?: string, dx?: number, dy?: number) => {
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
      const mag = p.magnitude;
      let color = COLORS.good;
      if (settings.showCalibrated && p.exceeds_calibration_p95) color = COLORS.calibrated;
      else if (mag !== null) {
        if (mag > settings.suspect) color = COLORS.bad;
        else if (mag > settings.tolerance) color = COLORS.warn;
      }
      const dx = settings.showVectors ? (side === "a" ? p.dx * vectorScale : -p.dx * vectorScale) : undefined;
      const dy = settings.showVectors ? (side === "a" ? -p.dy * vectorScale : p.dy * vectorScale) : undefined;
      drawPoint(x, y, color, 2.6, String(index), dx, dy);
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
      // draw A points small, B points large with magnitude coloring
      for (const row of projected) {
        const { p, index } = row;
        if (regionFiltered && !settings.regions.has(p.region)) continue;
        const [x, y] = row.projA;
        if (!Number.isFinite(x) || !Number.isFinite(y) || !p.visible_a) continue;
        drawPoint(x, y, COLORS.a, 2.2, undefined);
      }
      for (const row of projected) {
        const { p, index } = row;
        if (regionFiltered && !settings.regions.has(p.region)) continue;
        const [x, y] = row.projB;
        if (!Number.isFinite(x) || !Number.isFinite(y) || !p.visible_b) continue;
        const mag = p.magnitude;
        let color = COLORS.good;
        if (settings.showCalibrated && p.exceeds_calibration_p95) color = COLORS.calibrated;
        else if (mag !== null) {
          if (mag > settings.suspect) color = COLORS.bad;
          else if (mag > settings.tolerance) color = COLORS.warn;
        }
        const dx = settings.showVectors ? p.dx * vectorScale : undefined;
        const dy = settings.showVectors ? -p.dy * vectorScale : undefined;
        drawPoint(x, y, color, 3.4, settings.showLabels ? String(index) : undefined, dx, dy);
      }
    }
  }

  // legend
  const legendY = viewport.h - 26;
  ctx.font = "10px ui-monospace, monospace";
  ctx.fillStyle = COLORS.good; ctx.fillRect(10, legendY, 10, 10);
  ctx.fillStyle = "#cfe0ef"; ctx.fillText("≤ tolerance", 24, legendY + 10);
  ctx.fillStyle = COLORS.warn; ctx.fillRect(110, legendY, 10, 10);
  ctx.fillStyle = "#cfe0ef"; ctx.fillText("> tolerance", 124, legendY + 10);
  ctx.fillStyle = COLORS.bad; ctx.fillRect(210, legendY, 10, 10);
  ctx.fillStyle = "#cfe0ef"; ctx.fillText("> suspect", 224, legendY + 10);
  if (settings.showCalibrated && data.summary.calibrated) {
    ctx.fillStyle = COLORS.calibrated; ctx.fillRect(300, legendY, 10, 10);
    ctx.fillStyle = "#cfe0ef"; ctx.fillText("> cal p95", 314, legendY + 10);
  }
}
