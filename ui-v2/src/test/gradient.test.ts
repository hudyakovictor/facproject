import { describe, expect, it } from "vitest";
import {
  DEFAULT_GRADIENT, applySharpness, evaluateGradient, fromLegacyStops,
  parseHex, positionOf, sanitizeGradient, toHex, valueAt,
} from "../gradient";

describe("sharpness transfer function", () => {
  it("is linear when sharpness is 0", () => {
    for (const v of [0, 0.25, 0.5, 0.75, 1]) {
      expect(applySharpness(v, 0)).toBeCloseTo(v, 10);
    }
  });

  it("compresses the transition toward the middle as sharpness grows", () => {
    // При sharpness=0.8 активная полоса — 20% ширины вокруг середины.
    expect(applySharpness(0.3, 0.8)).toBe(0);      // ещё до полосы
    expect(applySharpness(0.5, 0.8)).toBeCloseTo(0.5, 6);
    expect(applySharpness(0.7, 0.8)).toBe(1);      // уже после
  });

  it("becomes a step at sharpness 1", () => {
    expect(applySharpness(0.49, 1)).toBe(0);
    expect(applySharpness(0.51, 1)).toBe(1);
  });
});

describe("gradient evaluation", () => {
  it("returns the first colour at t=0 and the last at t=1", () => {
    expect(toHex(evaluateGradient(DEFAULT_GRADIENT, 0))).toBe("#1d4ed8");
    expect(toHex(evaluateGradient(DEFAULT_GRADIENT, 1))).toBe("#7f1d1d");
  });

  it("clamps out-of-range input instead of extrapolating", () => {
    expect(toHex(evaluateGradient(DEFAULT_GRADIENT, -5)))
      .toBe(toHex(evaluateGradient(DEFAULT_GRADIENT, 0)));
    expect(toHex(evaluateGradient(DEFAULT_GRADIENT, 9)))
      .toBe(toHex(evaluateGradient(DEFAULT_GRADIENT, 1)));
  });

  it("survives a malformed colour without throwing", () => {
    const broken = { maxReference: 1, stops: [
      { position: 0, color: "not-a-colour", sharpness: 0 },
      { position: 1, color: "#ffffff", sharpness: 0 },
    ]};
    expect(() => evaluateGradient(broken, 0.5)).not.toThrow();
  });

  it("keeps a smooth ramp gentle and a sharp ramp abrupt", () => {
    const smooth = { maxReference: 1, stops: [
      { position: 0, color: "#000000", sharpness: 0 },
      { position: 1, color: "#ffffff", sharpness: 0 },
    ]};
    const sharp = { maxReference: 1, stops: [
      { position: 0, color: "#000000", sharpness: 0.9 },
      { position: 1, color: "#ffffff", sharpness: 0 },
    ]};
    // На 30% шкалы плавный градиент уже посветлел, резкий — ещё нет.
    expect(evaluateGradient(smooth, 0.3).r).toBeCloseTo(0.3, 2);
    expect(evaluateGradient(sharp, 0.3).r).toBe(0);
    // Обе версии сходятся на краях.
    expect(evaluateGradient(sharp, 1).r).toBe(1);
  });

  it("treats a zero-width segment as an instant colour jump", () => {
    const model = { maxReference: 1, stops: [
      { position: 0, color: "#000000", sharpness: 0 },
      { position: 0.5, color: "#000000", sharpness: 0 },
      { position: 0.5, color: "#ff0000", sharpness: 0 },
      { position: 1, color: "#ff0000", sharpness: 0 },
    ]};
    expect(toHex(evaluateGradient(model, 0.49))).toBe("#000000");
    expect(toHex(evaluateGradient(model, 0.51))).toBe("#ff0000");
  });

  it("orders unsorted stops instead of producing garbage", () => {
    const shuffled = { maxReference: 1, stops: [
      { position: 1, color: "#ffffff", sharpness: 0 },
      { position: 0, color: "#000000", sharpness: 0 },
    ]};
    expect(toHex(evaluateGradient(shuffled, 0))).toBe("#000000");
    expect(toHex(evaluateGradient(shuffled, 1))).toBe("#ffffff");
  });
});

describe("scale mapping", () => {
  it("maps position to metric value and back", () => {
    const m = { ...DEFAULT_GRADIENT, maxReference: 0.2 };
    expect(valueAt(m, 0.5)).toBeCloseTo(0.1, 10);
    expect(positionOf(m, 0.1)).toBeCloseTo(0.5, 10);
  });

  it("clamps a value beyond the reference to the end of the scale", () => {
    expect(positionOf(DEFAULT_GRADIENT, 999)).toBe(1);
  });
});

describe("sanitize and legacy migration", () => {
  it("extends coverage to the full [0,1] range", () => {
    const partial = { maxReference: 1, stops: [
      { position: 0.3, color: "#111111", sharpness: 0 },
      { position: 0.7, color: "#222222", sharpness: 0 },
    ]};
    const fixed = sanitizeGradient(partial);
    expect(fixed.stops[0].position).toBe(0);
    expect(fixed.stops[fixed.stops.length - 1].position).toBe(1);
  });

  it("clamps out-of-range sharpness and positions", () => {
    const wild = { maxReference: 1, stops: [
      { position: -2, color: "#000000", sharpness: 5 },
      { position: 8, color: "#ffffff", sharpness: -3 },
    ]};
    const fixed = sanitizeGradient(wild);
    expect(fixed.stops.every(s => s.position >= 0 && s.position <= 1)).toBe(true);
    expect(fixed.stops.every(s => s.sharpness >= 0 && s.sharpness <= 1)).toBe(true);
  });

  it("migrates the legacy four-stop settings shape", () => {
    const migrated = fromLegacyStops({
      blueCyan: 0.25, cyanGreen: 0.5, greenRed: 0.75,
      saturatedRed: 1, maxReference: 0.12,
    });
    expect(migrated.maxReference).toBe(0.12);
    expect(migrated.stops).toHaveLength(5);
    expect(toHex(evaluateGradient(migrated, 0))).toBe("#1d4ed8");
  });

  it("round-trips colour parsing", () => {
    expect(toHex(parseHex("#22d3ee"))).toBe("#22d3ee");
  });
});
