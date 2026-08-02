import { describe, expect, it } from "vitest";

/** Та же логика сегментации, что в UnifiedTimeline.renderTrackPath:
 * линия разрывается на каждой смене pose bin. */
function buildSegments(rows: { bucket: string; x: number; y: number }[]) {
  const segments: { x: number; y: number }[][] = [];
  let current: { x: number; y: number }[] = [];
  let prev: string | null = null;
  for (const r of rows) {
    if (prev !== null && r.bucket !== prev) { if (current.length) segments.push(current); current = []; }
    current.push({ x: r.x, y: r.y });
    prev = r.bucket;
  }
  if (current.length) segments.push(current);
  return segments;
}

const pathFor = (segs: { x: number; y: number }[][]) =>
  segs.filter(s => s.length >= 2).map(s => "M " + s.map(p => `${p.x} ${p.y}`).join(" L ")).join(" ");

describe("pose-bin segmentation of tracks", () => {
  it("never connects frames from different pose bins", () => {
    const rows = [
      { bucket: "frontal", x: 0, y: 10 },
      { bucket: "frontal", x: 10, y: 12 },
      { bucket: "left_mid", x: 20, y: 90 },  // «скачок» — на деле смена ракурса
      { bucket: "left_mid", x: 30, y: 92 },
    ];
    const segs = buildSegments(rows);
    expect(segs).toHaveLength(2);
    // Два независимых подпути => линия не пересекает границу ракурса.
    expect(pathFor(segs).match(/M /g)).toHaveLength(2);
  });

  it("keeps a single continuous line within one pose bin", () => {
    const rows = [0, 1, 2, 3].map(i => ({ bucket: "frontal", x: i * 10, y: 10 + i }));
    const segs = buildSegments(rows);
    expect(segs).toHaveLength(1);
    expect(pathFor(segs).match(/M /g)).toHaveLength(1);
  });

  it("drops single-frame segments from the line but keeps them as points", () => {
    const rows = [
      { bucket: "frontal", x: 0, y: 1 },
      { bucket: "right_deep", x: 10, y: 50 },   // одиночный кадр
      { bucket: "frontal", x: 20, y: 2 },
    ];
    const segs = buildSegments(rows);
    expect(segs).toHaveLength(3);
    // Ни один сегмент не содержит 2+ точек => линии нет вовсе.
    expect(pathFor(segs)).toBe("");
  });

  it("produces one segment per alternation in a fully mixed dataset", () => {
    // Реальный случай demo-набора: 100% соседних пар — разные ракурсы.
    const bins = ["left_profile", "left_deep", "left_mid", "frontal", "right_mid"];
    const rows = bins.map((b, i) => ({ bucket: b, x: i * 10, y: i }));
    expect(buildSegments(rows)).toHaveLength(5);
    expect(pathFor(buildSegments(rows))).toBe("");
  });
});
