import { describe, expect, test } from "vitest";
import { exclusionReasons, histogramOf, isSmallSample } from "../features/timeline/filters";
import type { ResearchPhoto } from "../shared/researchApi";

const photo = (over: Partial<ResearchPhoto> = {}): ResearchPhoto => ({
  id: "p", date: "2010-01-01", t: null, bucket: "frontal", era: "e",
  quality: 0.5, yaw: 0, pitch: 0, roll: 0, fuzzy: "",
  measurementStatus: "compared", flags: [], sourceMode: "research",
  analysisStage: "stage2", ...over,
});

const base = {
  qualityThreshold: 0.5,
  poseAngleThreshold: 6,
  findingsMode: false,
  search: "",
  activePose: "frontal",
  multiPose: false,
};

describe("причины исключения (§9.5)", () => {
  test("порог качества назван вместе с обеими величинами", () => {
    const [reason] = exclusionReasons(photo({ quality: 0.31 }), base);
    expect(reason.text).toBe("quality 0.31 < 0.50");
    expect(reason.control).toBe("quality");
  });

  test("кадр без оценки качества не отбрасывается порогом", () => {
    // Отсутствие измерения — не нулевое измерение.
    expect(exclusionReasons(photo({ quality: null }), base)).toEqual([]);
  });

  test("перечисляются все причины сразу, а не первая", () => {
    const reasons = exclusionReasons(
      photo({ quality: 0.1, bucket: "left_mid" }),
      { ...base, search: "нет-такого" },
    );
    expect(reasons.map((r) => r.control).sort()).toEqual(["poseBin", "quality", "search"]);
  });

  test("в мультиракурсе бин не является причиной", () => {
    const reasons = exclusionReasons(photo({ bucket: "left_mid" }), { ...base, multiPose: true });
    expect(reasons.some((r) => r.control === "poseBin")).toBe(false);
  });

  test("подходящий кадр не имеет причин исключения", () => {
    expect(exclusionReasons(photo({ quality: 0.9 }), base)).toEqual([]);
  });
});

describe("гистограмма порога (§9.4)", () => {
  const photos = [
    photo({ id: "a", quality: 0.1 }),
    photo({ id: "b", quality: 0.4 }),
    photo({ id: "c", quality: 0.8 }),
    photo({ id: "d", quality: null }),
  ];

  test("считает, сколько останется и сколько уйдёт", () => {
    const result = histogramOf(photos, (p) => p.quality ?? null, {
      min: 0, max: 1, bins: 10, threshold: 0.5,
    });
    expect(result.dropped).toBe(2);
    // 0.8 проходит порог, кадр без оценки остаётся видимым.
    expect(result.kept).toBe(2);
  });

  test("кадры без значения вынесены отдельно, а не в корзину нуля", () => {
    const result = histogramOf(photos, (p) => p.quality ?? null, {
      min: 0, max: 1, bins: 10, threshold: 0,
    });
    expect(result.withoutValue).toBe(1);
    expect(result.bins.reduce((sum, bin) => sum + bin.total, 0)).toBe(3);
  });

  test("предупреждение о малой выборке", () => {
    expect(isSmallSample(3)).toBe(true);
    expect(isSmallSample(0)).toBe(false);
    expect(isSmallSample(50)).toBe(false);
  });
});
