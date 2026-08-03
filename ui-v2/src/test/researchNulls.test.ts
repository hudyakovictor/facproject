import { describe, expect, it, vi, afterEach } from "vitest";
import { loadTimeline } from "../api";
import { fmt, fmtPercent, hasValue, NO_DATA } from "../format";

afterEach(() => vi.unstubAllGlobals());

/** Реальная форма строки research-режима: research_timeline.py отдаёт
 * 18 числовых полей как None. */
const researchRow = {
  id: "P1", date: "2015-06-02", t: Date.parse("2015-06-02"),
  bucket: "frontal", era: "STAGE2_2015", flags: [], fuzzy: "INSUFFICIENT_DATA",
  quality: 1.0, boneScore: 0.4, p0: 0.5, p1: 0.3, p2: 0.2,   // критичные есть
  confidence: null, orbit: null, chin: null, jaw: null, cheek: null,
  symmetry: null, yaw: null, siliconeProb: null, specular: null,
  lbpEntropy: null, frangi: null, wrinkle: null, subsurface: null,
  visualAge: null, calendarAge: null, dominant: null,
};

function mockTimeline(photos: unknown[]) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({
      source_mode: "research",
      era_meta: { STAGE2_2015: { label: "s", start: "2015-01-01", end: "2015-12-31" } },
      photos,
    }),
  }));
}

describe("research-mode null handling", () => {
  it("REGRESSION: null metrics no longer crash .toFixed()", async () => {
    mockTimeline([researchRow]);
    const result = await loadTimeline();
    expect(result.photos).toHaveLength(1);
    const photo = result.photos[0];
    // Раньше здесь падало: TypeError: Cannot read properties of null.
    expect(() => fmt(photo.confidence, 2)).not.toThrow();
    expect(fmt(photo.confidence, 2)).toBe(NO_DATA);
    expect(fmt(photo.yaw, 1)).toBe(NO_DATA);
  });

  it("normalises null to NaN, never to 0", async () => {
    mockTimeline([researchRow]);
    const photo = (await loadTimeline()).photos[0];
    // Ноль означал бы измеренное нулевое значение — подмена недопустима.
    expect(photo.confidence).not.toBe(0);
    expect(Number.isNaN(photo.confidence)).toBe(true);
    expect(hasValue(photo.confidence)).toBe(false);
  });

  it("keeps genuinely measured values intact", async () => {
    mockTimeline([researchRow]);
    const photo = (await loadTimeline()).photos[0];
    expect(photo.quality).toBe(1.0);
    expect(photo.boneScore).toBe(0.4);
    expect(fmt(photo.boneScore, 3)).toBe("0.400");
  });

  it("keeps a Stage 1 inventory row before comparative metrics exist", async () => {
    // Stage 1 уже содержит реальный кадр, дату и ракурс. Отсутствие метрик
    // Stage 2 не должно скрывать такой кадр из интерфейса.
    mockTimeline([
      researchRow,
      { ...researchRow, id: "STAGE1", quality: null, boneScore: null,
        p0: null, p1: null, p2: null },
    ]);
    const result = await loadTimeline();
    expect(result.photos.map(p => p.id)).toEqual(["P1", "STAGE1"]);
    expect(result.rejected).toHaveLength(0);
    expect(Number.isNaN(result.photos[1].boneScore)).toBe(true);
  });

  it("formats percentages and missing values consistently", () => {
    expect(fmtPercent(0.421)).toBe("42.1%");
    expect(fmtPercent(null)).toBe(NO_DATA);
    expect(fmtPercent(NaN)).toBe(NO_DATA);
    expect(fmt(undefined)).toBe(NO_DATA);
  });
});
