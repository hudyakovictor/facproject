import { describe, expect, it } from "vitest";
import {
  computeBaselineRefs,
  EMPTY_BASELINE,
  MIN_BASELINE_SAMPLE,
} from "../baseline";
import type { Photo } from "../data";
import { buildDemoPhotos } from "../demoData";

const DEMO_PHOTOS = buildDemoPhotos();

function photo(era: string, t: number, boneScore: number): Photo {
  return { ...DEMO_PHOTOS[0], id: `${era}-${t}`, era, t, boneScore };
}

describe("baseline refs", () => {
  it("не вычисляет forensic baseline в браузере", () => {
    const photos = Array.from({ length: 12 }, (_, i) =>
      photo("SEG_A", Date.parse("2000-01-01") + i * 86400000, 0.9 + i * 0.001));
    const baseline = computeBaselineRefs(photos);
    expect(baseline.source).toBe("unavailable");
    expect(baseline.sufficient).toBe(false);
    expect(baseline.refs).toEqual({});
    expect(baseline.baselineEra).toBeNull();
  });

  it("не изобретает baseline даже при достаточном числе строк", () => {
    const photos = Array.from({ length: MIN_BASELINE_SAMPLE - 1 }, (_, i) =>
      photo("TINY", Date.parse("2000-01-01") + i * 1000, 0.5));
    const baseline = computeBaselineRefs(photos);
    expect(baseline.sampleSize).toBe(0);
    expect(baseline.sufficient).toBe(false);
  });

  it("пустой набор совпадает с EMPTY_BASELINE", () => {
    const baseline = computeBaselineRefs([]);
    expect(baseline).toEqual(EMPTY_BASELINE);
  });
});
