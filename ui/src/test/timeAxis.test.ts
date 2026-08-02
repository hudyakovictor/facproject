import { describe, expect, it } from "vitest";

/** Проверка самой формулы шкалы (та же, что в UnifiedTimeline.xForIdxLocal).
 * Держим её отдельно от DOM: важна арифметика соответствия дат и пикселей. */
function xForTime(t: number, startT: number, span: number, trackAreaW: number, thumb: number) {
  return ((t - startT) / span) * (trackAreaW - thumb);
}

describe("time-proportional X axis", () => {
  const startT = Date.parse("2000-01-01");
  const span = Date.parse("2001-01-01") - startT; // 366 дней
  const W = 1000, thumb = 50;

  it("places a photo at the midpoint of the window at the middle of the track", () => {
    const mid = startT + span / 2;
    expect(xForTime(mid, startT, span, W, thumb)).toBeCloseTo((W - thumb) / 2, 6);
  });

  it("makes distance proportional to the time gap, not to the index", () => {
    // Три кадра: +1 день, затем +100 дней. Раньше они были равноудалены.
    const a = startT;
    const b = startT + 1 * 86400000;
    const c = startT + 101 * 86400000;
    const xa = xForTime(a, startT, span, W, thumb);
    const xb = xForTime(b, startT, span, W, thumb);
    const xc = xForTime(c, startT, span, W, thumb);
    const gap1 = xb - xa;
    const gap2 = xc - xb;
    expect(gap2 / gap1).toBeCloseTo(100, 0);
  });

  it("keeps chronological order monotonic", () => {
    const ts = [0, 5, 40, 200, 366].map(d => startT + d * 86400000);
    const xs = ts.map(t => xForTime(t, startT, span, W, thumb));
    for (let i = 1; i < xs.length; i++) expect(xs[i]).toBeGreaterThan(xs[i - 1]);
  });
});
