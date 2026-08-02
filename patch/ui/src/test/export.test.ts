import { describe, expect, it } from "vitest";
import { buildAnalysisExport, ANALYSIS_EXPORT_SCHEMA } from "../export";

import { buildDemoPhotos } from "../demoData";

/** Демо-набор как тестовая фикстура: генератор вынесен из основного
 * бандла (аудит №27), поэтому строим его явно. */
const DEMO_PHOTOS = buildDemoPhotos();

const base = {
  photos: DEMO_PHOTOS.slice(0, 12),
  totalPhotos: DEMO_PHOTOS.length,
  dataMessage: "test",
  filters: { dataset: "main" },
};

describe("analysis JSON export", () => {
  it("always carries source_mode and not_a_verdict", () => {
    const out = buildAnalysisExport({ ...base, dataMode: "demo" });
    expect(out.schema).toBe(ANALYSIS_EXPORT_SCHEMA);
    expect(out.source_mode).toBe("demo");
    expect(out.not_a_verdict).toBe(true);
    expect(String(out.disclaimer)).toContain("не установление личности");
  });

  it("uses a true median for aggregates, not a mean", () => {
    const out = buildAnalysisExport({ ...base, dataMode: "research" }) as any;
    const values = base.photos.map(p => p.boneScore).sort((a, b) => a - b);
    const mid = Math.floor(values.length / 2);
    const expected = values.length % 2 === 0 ? (values[mid - 1] + values[mid]) / 2 : values[mid];
    expect(out.aggregates_median.boneScore).toBeCloseTo(expected, 10);
  });

  it("preserves filters so numbers stay reproducible", () => {
    const filters = { dataset: "calibration", bucketFilter: "frontal" };
    const out = buildAnalysisExport({ ...base, dataMode: "demo", filters }) as any;
    expect(out.selection.filters).toEqual(filters);
    expect(out.selection.photos_in_selection).toBe(12);
    expect(out.selection.photos_total).toBe(DEMO_PHOTOS.length);
  });

  it("lists anomaly photo ids consistently with the count", () => {
    const out = buildAnalysisExport({ ...base, dataMode: "demo" }) as any;
    expect(out.anomalies.photo_ids).toHaveLength(out.anomalies.count);
  });

  it("returns null medians for an empty selection instead of 0", () => {
    const out = buildAnalysisExport({ ...base, photos: [], dataMode: "demo" }) as any;
    expect(out.aggregates_median.boneScore).toBeNull();
  });
});

// --- печатный отчёт ---------------------------------------------------------

import { buildPrintReport } from "../export";

const printInput = {
  photos: [] as never[],
  totalPhotos: 0,
  dataMode: "demo" as const,
  dataMessage: "демо-набор",
  filters: { dataset: "main" },
  playheadT: Date.parse("2004-05-01"),
  currentEra: "ERA_2",
  events: [],
};

describe("печатный отчёт", () => {
  it("экранирует разметку в подписях событий", () => {
    const html = buildPrintReport({
      ...printInput,
      events: [{
        t: Date.parse("2001-01-01"),
        title: '<script>alert("x")</script>',
        tooltip: "a < b & c",
        source: '"кавычки"',
      }],
    });
    expect(html).not.toContain("<script>alert");
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("a &lt; b &amp; c");
  });

  it("содержит правила печати", () => {
    const html = buildPrintReport(printInput);
    expect(html).toContain("@media print");
    expect(html).toContain("page-break-inside: avoid");
    expect(html).toContain("@page");
  });

  it("демо-срез помечается в напечатанном виде", () => {
    const html = buildPrintReport(printInput);
    expect(html).toContain("Демонстрационные данные");
  });

  it("research-срез не получает демо-баннера", () => {
    const html = buildPrintReport({ ...printInput, dataMode: "research" });
    expect(html).not.toContain("Демонстрационные данные");
  });

  it("несёт оговорку not_a_verdict", () => {
    expect(buildPrintReport(printInput)).toContain("not_a_verdict: true");
  });

  it("фильтры сохраняются целиком для воспроизводимости", () => {
    const html = buildPrintReport({ ...printInput, filters: { dataset: "main", eras: ["ERA_1"] } });
    expect(html).toContain("dataset");
    expect(html).toContain("ERA_1");
  });
});
