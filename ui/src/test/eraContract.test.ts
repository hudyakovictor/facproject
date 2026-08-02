import { describe, expect, it, vi, afterEach } from "vitest";
import { loadTimeline } from "../api";
import { buildEraMeta } from "../data";

/** Реальная форма ответа `/api/v1/timeline` в demo-режиме: идентификаторы
 * сегментов `DEMO_SEGMENT_*`, а НЕ `ERA_*` встроенного набора. */
function apiRow(id: string, era: string, t: number, bucket = "frontal") {
  return {
    id, era, t, bucket, date: new Date(t).toISOString().slice(0, 10),
    quality: 0.8, boneScore: 0.5, p0: 0.6, p1: 0.3, p2: 0.1,
  };
}

function mockTimeline(payload: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => payload,
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe("era contract", () => {
  it("accepts backend segment ids that differ from the built-in ERA_* set", async () => {
    mockTimeline({
      source_mode: "demo",
      era_meta: {
        DEMO_SEGMENT_1: { label: "Демо-сегмент 1", start: "1999-08-09", end: "2011-12-31" },
        DEMO_SEGMENT_2: { label: "Демо-сегмент 2", start: "2012-01-01", end: "2014-12-31" },
      },
      photos: [
        apiRow("A", "DEMO_SEGMENT_1", Date.parse("2000-01-01")),
        apiRow("B", "DEMO_SEGMENT_2", Date.parse("2013-01-01")),
      ],
    });
    const result = await loadTimeline();
    // Раньше такие строки проходили isPhoto, а затем молча отбрасывались
    // фильтром эпох — таймлайн оставался пустым.
    expect(result.photos).toHaveLength(2);
    expect(result.rejected).toHaveLength(0);
    expect(Object.keys(result.eraMeta)).toEqual(["DEMO_SEGMENT_1", "DEMO_SEGMENT_2"]);
    expect(result.eraMeta.DEMO_SEGMENT_1.color).not.toBe(result.eraMeta.DEMO_SEGMENT_2.color);
  });

  it("rejects unknown era with a visible reason instead of dropping it silently", async () => {
    mockTimeline({
      source_mode: "demo",
      era_meta: { DEMO_SEGMENT_1: { label: "s1", start: "1999-01-01", end: "2011-12-31" } },
      photos: [
        apiRow("good", "DEMO_SEGMENT_1", Date.parse("2000-01-01")),
        apiRow("bad", "NOT_IN_META", Date.parse("2001-01-01")),
      ],
    });
    const result = await loadTimeline();
    expect(result.photos.map(p => p.id)).toEqual(["good"]);
    expect(result.rejected).toHaveLength(1);
    expect(result.rejected[0].id).toBe("bad");
    expect(result.rejected[0].reason).toContain("era_meta");
    expect(result.message).toContain("отвергнуто");
  });

  it("rejects an unknown pose bin", async () => {
    mockTimeline({
      source_mode: "demo",
      era_meta: { S1: { label: "s", start: "1999-01-01", end: "2026-01-01" } },
      photos: [
        apiRow("ok", "S1", Date.parse("2000-01-01"), "frontal"),
        apiRow("weird", "S1", Date.parse("2000-02-01"), "diagonal_upside_down"),
      ],
    });
    const result = await loadTimeline();
    expect(result.photos.map(p => p.id)).toEqual(["ok"]);
    expect(result.rejected[0].reason).toContain("pose bin");
  });

  it("derives segment bounds from photo dates when era_meta is absent", () => {
    const photos = [
      apiRow("a", "SEG", Date.parse("2005-03-04")),
      apiRow("b", "SEG", Date.parse("2009-11-20")),
    ] as never as import("../data").Photo[];
    const meta = buildEraMeta(undefined, photos);
    expect(meta.SEG.start).toBe("2005-03-04");
    expect(meta.SEG.end).toBe("2009-11-20");
  });
});
