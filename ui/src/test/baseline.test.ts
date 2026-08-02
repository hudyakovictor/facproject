import { describe, expect, it } from "vitest";
import { computeBaselineRefs, MIN_BASELINE_SAMPLE } from "../baseline";
import { REF, type Photo } from "../data";
import { buildDemoPhotos } from "../demoData";

/** Демо-набор как тестовая фикстура: генератор вынесен из основного
 * бандла (аудит №27), поэтому строим его явно. */
const DEMO_PHOTOS = buildDemoPhotos();

function photo(era: string, t: number, boneScore: number): Photo {
  return { ...DEMO_PHOTOS[0], id: `${era}-${t}`, era, t, boneScore };
}

describe("baseline refs", () => {
  it("derives refs from loaded photos, not from the built-in demo constant", () => {
    const photos = Array.from({ length: 12 }, (_, i) =>
      photo("SEG_A", Date.parse("2000-01-01") + i * 86400000, 0.9 + i * 0.001));
    const baseline = computeBaselineRefs(photos);
    expect(baseline.source).toBe("api");
    expect(baseline.refs.boneScore.median).toBeCloseTo(0.9055, 3);
    // Ключевая регрессия: раньше здесь всегда оказывалась медиана демо-набора.
    expect(baseline.refs.boneScore.median).not.toBeCloseTo(REF.boneScore.median, 6);
  });

  it("uses the earliest segment as the baseline", () => {
    const photos = [
      ...Array.from({ length: 10 }, (_, i) => photo("LATE", Date.parse("2020-01-01") + i * 1000, 0.2)),
      ...Array.from({ length: 10 }, (_, i) => photo("EARLY", Date.parse("1999-01-01") + i * 1000, 0.8)),
    ];
    const baseline = computeBaselineRefs(photos);
    expect(baseline.baselineEra).toBe("EARLY");
    expect(baseline.refs.boneScore.median).toBeCloseTo(0.8, 6);
  });

  it("flags an insufficient sample instead of inventing a spread", () => {
    const photos = Array.from({ length: MIN_BASELINE_SAMPLE - 1 }, (_, i) =>
      photo("TINY", Date.parse("2000-01-01") + i * 1000, 0.5));
    const baseline = computeBaselineRefs(photos);
    expect(baseline.sampleSize).toBe(MIN_BASELINE_SAMPLE - 1);
    expect(baseline.sufficient).toBe(false);
  });

  it("uses a robust spread that one outlier cannot inflate", () => {
    const clean = Array.from({ length: 20 }, (_, i) =>
      photo("S", Date.parse("2000-01-01") + i * 1000, 0.5 + (i % 2) * 0.01));
    const withOutlier = [...clean, photo("S", Date.parse("2000-02-01"), 99)];
    const a = computeBaselineRefs(clean).refs.boneScore.std;
    const b = computeBaselineRefs(withOutlier).refs.boneScore.std;
    // Обычное σ выросло бы на порядки; MAD остаётся сопоставимым.
    expect(b).toBeLessThan(a * 3);
  });

  it("falls back to the built-in reference for an empty dataset", () => {
    const baseline = computeBaselineRefs([]);
    expect(baseline.source).toBe("builtin-demo");
    expect(baseline.sufficient).toBe(false);
  });
});
