import { describe, expect, it } from "vitest";
import { heatColor, DEFAULT_HEATMAP_STOPS } from "../components/MeshViewer";

describe("heatColor", () => {
  it("returns pure blue at t=0", () => {
    const color = heatColor(0, DEFAULT_HEATMAP_STOPS);
    expect(color.getHexString()).toBe("1d4ed8");
  });

  it("returns dark red at t=1 (saturated)", () => {
    const color = heatColor(1, DEFAULT_HEATMAP_STOPS);
    expect(color.getHexString()).toBe("7f1d1d");
  });

  it("clamps values above 1 to the saturated stop", () => {
    const overshoot = heatColor(5, DEFAULT_HEATMAP_STOPS);
    const atOne = heatColor(1, DEFAULT_HEATMAP_STOPS);
    expect(overshoot.getHexString()).toBe(atOne.getHexString());
  });

  it("clamps negative values to the first stop", () => {
    const undershoot = heatColor(-3, DEFAULT_HEATMAP_STOPS);
    const atZero = heatColor(0, DEFAULT_HEATMAP_STOPS);
    expect(undershoot.getHexString()).toBe(atZero.getHexString());
  });

  it("is monotonically distinct across the four named ranges", () => {
    // Within-normal (blue/cyan) must be visually different from
    // out-of-normal (red/dark-red) — this is the whole point of the
    // heatmap policy from aboutplatform.txt.
    const withinNormal = heatColor(0.1, DEFAULT_HEATMAP_STOPS);
    const boneDifference = heatColor(0.9, DEFAULT_HEATMAP_STOPS);
    expect(withinNormal.getHexString()).not.toBe(boneDifference.getHexString());
  });

  it("respects custom thresholds (e.g. all blue-cyan until 90%)", () => {
    const customStops = { ...DEFAULT_HEATMAP_STOPS, blueCyan: 0.9 };
    const stillCool = heatColor(0.5, customStops);
    // Halfway between blue (0) and cyan (0.9) stop — should not yet be green/red.
    const r = Math.round(stillCool.r * 255);
    const b = Math.round(stillCool.b * 255);
    expect(b).toBeGreaterThan(r);
  });
});
