import { describe, expect, it } from "vitest";
import { fitTrend, trendDeviation } from "../trend";

const DAY = 86400000;
const series = (vals: number[], step = 30) =>
  vals.map((v, i) => ({ t: Date.parse("2000-01-01") + i * step * DAY, v }));

describe("Theil–Sen trend", () => {
  it("recovers a known linear slope", () => {
    // +0.01 единиц за 30 дней
    const pts = series([0.5, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57]);
    const model = fitTrend(pts);
    expect(model.usable).toBe(true);
    const perMonth = model.slope * 30 * DAY;
    expect(perMonth).toBeCloseTo(0.01, 4);
  });

  it("is not dragged by a single gross outlier", () => {
    const clean = series([0.5, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57]);
    const dirty = [...clean];
    dirty[4] = { ...dirty[4], v: 99 };            // испорченный кадр
    const a = fitTrend(clean).slope;
    const b = fitTrend(dirty).slope;
    // МНК развернуло бы наклон на порядки; Тейл–Сен держится.
    expect(Math.abs(b - a)).toBeLessThan(Math.abs(a) * 0.5);
  });

  it("refuses to fit an insufficient sample instead of guessing", () => {
    const model = fitTrend(series([0.5, 0.6, 0.7]));
    expect(model.usable).toBe(false);
    expect(trendDeviation(model, { t: Date.now(), v: 0.9 })).toBeNull();
  });

  it("flags a step change as a large deviation from the trend", () => {
    const pts = series([0.50, 0.505, 0.51, 0.515, 0.52, 0.525, 0.53, 0.535]);
    const model = fitTrend(pts);
    const onTrend = { t: Date.parse("2000-01-01") + 8 * 30 * DAY, v: 0.54 };
    const jump = { t: Date.parse("2000-01-01") + 8 * 30 * DAY, v: 0.80 };
    expect(Math.abs(trendDeviation(model, onTrend)!)).toBeLessThan(3);
    expect(Math.abs(trendDeviation(model, jump)!)).toBeGreaterThan(10);
  });

  it("ignores duplicate timestamps that cannot define a slope", () => {
    const t = Date.parse("2000-01-01");
    const pts = [
      { t, v: 0.5 }, { t, v: 0.6 },
      ...series([0.5, 0.52, 0.54, 0.56, 0.58]).map(p => ({ ...p, t: p.t + 10 * DAY })),
    ];
    expect(fitTrend(pts).usable).toBe(true);
  });
});
