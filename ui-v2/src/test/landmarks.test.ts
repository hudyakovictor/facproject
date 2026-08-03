import { describe, expect, it } from "vitest";
import {
  DEFAULT_SHIFT_THRESHOLDS, classifyShift, morphPosition,
  summarizeByZone, summarizeShifts, toLandmarkRows,
} from "../landmarks";
import type { HeatmapPoint } from "../api";

const th = { tolerance: 0.02, suspect: 0.05, calibrated: false };

const pt = (index: number, residual: number | null, zone = "x_center_center"): HeatmapPoint => ({
  index, visible: residual !== null, zone,
  x: 0, y: 0, z: 0,
  bx: residual ?? 0, by: 0, bz: 0,
  dx: residual ?? 0, dy: 0, dz: 0,
  residual,
});

describe("landmark shift classification", () => {
  it("maps residual to the three user-facing classes", () => {
    expect(classifyShift(0.01, th)).toBe("within");
    expect(classifyShift(0.02, th)).toBe("within");     // граница включительно
    expect(classifyShift(0.035, th)).toBe("suspect");
    expect(classifyShift(0.05, th)).toBe("suspect");
    expect(classifyShift(0.09, th)).toBe("anomalous");
  });

  it("treats a missing measurement as no_data, never as 'within'", () => {
    // Точка, невидимая на одном из кадров, не должна читаться как «совпала».
    expect(classifyShift(null, th)).toBe("no_data");
    expect(classifyShift(undefined, th)).toBe("no_data");
    expect(classifyShift(NaN, th)).toBe("no_data");
  });

  it("reclassifies points when the user moves the thresholds", () => {
    const strict = { ...th, tolerance: 0.005, suspect: 0.02 };
    expect(classifyShift(0.01, th)).toBe("within");
    expect(classifyShift(0.01, strict)).toBe("suspect");
  });
});

describe("landmark rows and summary", () => {
  const rows = toLandmarkRows(
    [pt(0, 0.01), pt(1, 0.03), pt(2, 0.2), pt(3, null)], th);

  it("preserves invisible points instead of dropping them", () => {
    expect(rows).toHaveLength(4);
    expect(rows[3].shiftClass).toBe("no_data");
    expect(rows[3].residual).toBeNull();
  });

  it("computes the anomalous share among MEASURED points only", () => {
    const s = summarizeShifts(rows);
    expect(s.within).toBe(1);
    expect(s.suspect).toBe(1);
    expect(s.anomalous).toBe(1);
    expect(s.no_data).toBe(1);
    // 1 аномальная из 3 измеренных, а не из 4 всего.
    expect(s.anomalousShare).toBeCloseTo(1 / 3, 6);
    expect(s.medianResidual).toBeCloseTo(0.03, 6);
  });

  it("ranks zones by number of anomalous points", () => {
    const mixed = toLandmarkRows(
      [pt(0, 0.3, "x_low_low"), pt(1, 0.001, "x_high_high"), pt(2, 0.4, "x_low_low")], th);
    const zones = summarizeByZone(mixed);
    expect(zones[0].zone).toBe("x_low_low");
    expect(zones[0].anomalous).toBe(2);
  });
});

describe("A→B morphing", () => {
  const row = toLandmarkRows([{
    index: 0, visible: true, zone: "z",
    x: 0, y: 0, z: 0, bx: 10, by: 20, bz: 30,
    dx: 10, dy: 20, dz: 30, residual: 0.1,
  }], th)[0];

  it("returns position A at t=0 and B at t=1", () => {
    expect(morphPosition(row, 0)).toEqual([0, 0, 0]);
    expect(morphPosition(row, 1)).toEqual([10, 20, 30]);
  });

  it("interpolates linearly in between", () => {
    expect(morphPosition(row, 0.5)).toEqual([5, 10, 15]);
  });

  it("clamps out-of-range slider values", () => {
    expect(morphPosition(row, -5)).toEqual([0, 0, 0]);
    expect(morphPosition(row, 99)).toEqual([10, 20, 30]);
  });

  it("keeps a point static when the B position is unknown", () => {
    // Точка видна в A, но выровненной позиции B нет: она обязана остаться на
    // месте, а не «уехать» в ноль при движении ползунка.
    const staticRow = toLandmarkRows([{
      index: 9, visible: true, zone: "z",
      x: 1, y: 2, z: 3, bx: null, by: null, bz: null,
      dx: null, dy: null, dz: null, residual: null,
    }], DEFAULT_SHIFT_THRESHOLDS)[0];
    expect(morphPosition(staticRow, 1)).toEqual([1, 2, 3]);
  });

  it("returns null when the point has no position at all", () => {
    const missing = toLandmarkRows([{
      index: 10, visible: false, zone: null,
      x: null, y: null, z: null, bx: null, by: null, bz: null,
      dx: null, dy: null, dz: null, residual: null,
    }], DEFAULT_SHIFT_THRESHOLDS)[0];
    expect(morphPosition(missing, 1)).toBeNull();
  });
});
