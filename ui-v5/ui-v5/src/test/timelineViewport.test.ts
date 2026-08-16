import { describe, expect, test } from "vitest";
import {
  boundsOf,
  clampViewport,
  fitViewport,
  panBy,
  ticksFor,
  timeOf,
  timeToRatio,
  xToTime,
  zoomAt,
  zoomLevel,
} from "../features/timeline/viewport";
import { pickRepresentatives } from "../features/timeline/representative";
import type { ResearchPhoto } from "../shared/researchApi";

const photo = (over: Partial<ResearchPhoto> = {}): ResearchPhoto => ({
  id: "p",
  date: "2010-01-01",
  t: null,
  bucket: "frontal",
  era: "2008-2013",
  quality: 0.5,
  yaw: 0,
  pitch: 0,
  roll: 0,
  fuzzy: "",
  measurementStatus: "compared",
  flags: [],
  sourceMode: "research",
  analysisStage: "stage2",
  ...over,
});

const DAY = 86_400_000;
const bounds = { min: Date.UTC(2000, 0, 1), max: Date.UTC(2020, 0, 1) };

describe("время кадра", () => {
  test("дата имеет приоритет над полем t", () => {
    // `ui_fields.normalized_t` отдаёт долю [0,1], а не метку времени: принять
    // её за timestamp значило бы поместить все кадры в 1970 год.
    expect(timeOf(photo({ date: "2014-03-01", t: 0.42 }))).toBe(Date.parse("2014-03-01"));
  });

  test("доля вместо timestamp не принимается за время", () => {
    expect(timeOf(photo({ date: null, t: 0.42 }))).toBeNull();
  });

  test("настоящий timestamp принимается, когда даты нет", () => {
    const t = Date.UTC(2014, 2, 1);
    expect(timeOf(photo({ date: null, t }))).toBe(t);
  });

  test("кадр без даты и без времени не попадает на шкалу", () => {
    expect(timeOf(photo({ date: null, t: null }))).toBeNull();
  });
});

describe("границы диапазона", () => {
  test("одиночный кадр не даёт нулевой диапазон", () => {
    const result = boundsOf([photo({ date: "2010-05-05" })]);
    expect(result).not.toBeNull();
    expect(result!.max - result!.min).toBeGreaterThan(0);
  });

  test("кадры без даты игнорируются", () => {
    const result = boundsOf([photo({ date: "2005-01-01" }), photo({ id: "x", date: null, t: null })]);
    expect(result!.min).toBe(Date.parse("2005-01-01"));
  });

  test("пустой список даёт null, а не искусственный диапазон", () => {
    expect(boundsOf([])).toBeNull();
  });
});

describe("зум от курсора", () => {
  test("точка под курсором остаётся на месте", () => {
    const viewport = fitViewport(bounds);
    const anchor = Date.UTC(2015, 0, 1);
    const ratioBefore = timeToRatio(viewport, anchor);

    const zoomed = zoomAt(viewport, bounds, anchor, 0.5);
    const ratioAfter = timeToRatio(zoomed, anchor);

    // Иначе при каждом повороте колеса содержимое уезжает из-под курсора.
    expect(ratioAfter).toBeCloseTo(ratioBefore, 5);
  });

  test("приближение сужает окно", () => {
    const viewport = fitViewport(bounds);
    const zoomed = zoomAt(viewport, bounds, Date.UTC(2010, 0, 1), 0.5);
    expect(zoomed.end - zoomed.start).toBeLessThan(viewport.end - viewport.start);
    expect(zoomLevel(zoomed, bounds)).toBeGreaterThan(1);
  });

  test("отдаление не выходит за пределы данных", () => {
    const viewport = fitViewport(bounds);
    const zoomed = zoomAt(viewport, bounds, Date.UTC(2010, 0, 1), 100);
    expect(zoomed.start).toBeGreaterThanOrEqual(bounds.min);
    expect(zoomed.end).toBeLessThanOrEqual(bounds.max);
  });

  test("приближение ограничено сутками", () => {
    let viewport = fitViewport(bounds);
    for (let i = 0; i < 100; i += 1) {
      viewport = zoomAt(viewport, bounds, Date.UTC(2010, 0, 1), 0.5);
    }
    expect(viewport.end - viewport.start).toBeGreaterThanOrEqual(DAY - 1);
  });
});

describe("панорамирование", () => {
  test("сдвиг сохраняет ширину окна", () => {
    const viewport = zoomAt(fitViewport(bounds), bounds, Date.UTC(2010, 0, 1), 0.25);
    const span = viewport.end - viewport.start;
    const moved = panBy(viewport, bounds, 0.3);
    expect(moved.end - moved.start).toBeCloseTo(span, 3);
  });

  test("сдвиг за левый край упирается в границу данных", () => {
    const viewport = zoomAt(fitViewport(bounds), bounds, bounds.min, 0.25);
    const moved = panBy(viewport, bounds, -10);
    expect(moved.start).toBe(bounds.min);
  });

  test("clampViewport не растягивает окно шире данных", () => {
    const clamped = clampViewport({ start: bounds.min - 1e12, end: bounds.max + 1e12 }, bounds);
    expect(clamped.start).toBeGreaterThanOrEqual(bounds.min);
    expect(clamped.end).toBeLessThanOrEqual(bounds.max);
  });
});

describe("перевод координат", () => {
  test("xToTime обратен timeToRatio", () => {
    const viewport = fitViewport(bounds);
    const t = xToTime(viewport, 500, 1000);
    expect(timeToRatio(viewport, t)).toBeCloseTo(0.5, 6);
  });
});

describe("деления шкалы", () => {
  test("на полном архиве подписи — годы", () => {
    const ticks = ticksFor(fitViewport(bounds));
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks.every((tick) => /^\d{4}$/.test(tick.label))).toBe(true);
  });

  test("при зуме в месяцы появляются подписи месяцев, а не пустая шкала", () => {
    const start = Date.UTC(2014, 0, 1);
    const ticks = ticksFor({ start, end: start + 60 * DAY });
    // Прежняя реализация рисовала только годы: при таком окне не было ни одной.
    expect(ticks.length).toBeGreaterThan(0);
  });

  test("кварталы появляются на среднем масштабе", () => {
    const start = Date.UTC(2014, 0, 1);
    const ticks = ticksFor({ start, end: start + 400 * DAY });
    expect(ticks.some((tick) => /^Q\d$/.test(tick.label))).toBe(true);
  });
});

describe("отбор превью", () => {
  const viewport = fitViewport(bounds);
  const build = (items: ResearchPhoto[]) => {
    const times = new Map(items.map((item) => [item.id, timeOf(item) ?? 0]));
    return { items, times };
  };

  test("на бакет приходится не больше одного превью", () => {
    const items = Array.from({ length: 500 }, (_, i) =>
      photo({ id: `p${i}`, date: new Date(bounds.min + i * 14 * DAY).toISOString().slice(0, 10) }),
    );
    const { times } = build(items);
    const picked = pickRepresentatives(items, times, {
      viewport,
      width: 1000,
      slotWidth: 62,
    });
    expect(picked.length).toBeLessThanOrEqual(Math.floor(1000 / 62));
  });

  test("находка вытесняет обычный кадр из своего бакета", () => {
    const items = [
      photo({ id: "plain", date: "2010-01-01", quality: 0.99 }),
      photo({ id: "finding", date: "2010-01-02", quality: 0.1, flags: ["coherent_jump_candidate"] }),
    ];
    const { times } = build(items);
    const picked = pickRepresentatives(items, times, {
      viewport: { start: Date.parse("2010-01-01"), end: Date.parse("2010-01-03") },
      width: 60,
      slotWidth: 62,
    });
    // Потерять находку при прореживании — потерять информацию; потерять
    // рядовой кадр — только плотность.
    expect(picked.map((p) => p.id)).toContain("finding");
  });

  test("среди равных выбирается кадр лучшего качества", () => {
    const items = [
      photo({ id: "low", date: "2010-01-01", quality: 0.2 }),
      photo({ id: "high", date: "2010-01-02", quality: 0.9 }),
    ];
    const { times } = build(items);
    const picked = pickRepresentatives(items, times, {
      viewport: { start: Date.parse("2010-01-01"), end: Date.parse("2010-01-03") },
      width: 60,
      slotWidth: 62,
    });
    expect(picked.map((p) => p.id)).toContain("high");
  });

  test("кадр без оценки качества не считается нулевым", () => {
    const items = [
      photo({ id: "zero", date: "2010-01-01", quality: 0 }),
      photo({ id: "unknown", date: "2010-01-02", quality: null }),
    ];
    const { times } = build(items);
    const picked = pickRepresentatives(items, times, {
      viewport: { start: Date.parse("2010-01-01"), end: Date.parse("2010-01-03") },
      width: 60,
      slotWidth: 62,
    });
    // Честная оценка 0.0 — это измерение, а отсутствие оценки им не является.
    expect(picked.map((p) => p.id)).toContain("zero");
  });

  test("закреплённые A и B не исчезают при прореживании", () => {
    const items = Array.from({ length: 300 }, (_, i) =>
      photo({ id: `p${i}`, date: new Date(bounds.min + i * 20 * DAY).toISOString().slice(0, 10) }),
    );
    const { times } = build(items);
    const picked = pickRepresentatives(items, times, {
      viewport,
      width: 400,
      slotWidth: 62,
      pinned: ["p7", "p123"],
    });
    const ids = picked.map((p) => p.id);
    expect(ids).toContain("p7");
    expect(ids).toContain("p123");
  });

  test("кадры вне окна не попадают в выборку", () => {
    const items = [
      photo({ id: "inside", date: "2010-01-01" }),
      photo({ id: "outside", date: "2019-01-01" }),
    ];
    const { times } = build(items);
    const picked = pickRepresentatives(items, times, {
      viewport: { start: Date.parse("2009-01-01"), end: Date.parse("2011-01-01") },
      width: 500,
      slotWidth: 62,
    });
    expect(picked.map((p) => p.id)).toEqual(["inside"]);
  });

  test("превью упорядочены по времени", () => {
    const items = Array.from({ length: 50 }, (_, i) =>
      photo({ id: `p${i}`, date: new Date(bounds.min + i * 100 * DAY).toISOString().slice(0, 10) }),
    );
    const { times } = build(items);
    const picked = pickRepresentatives(items, times, { viewport, width: 900, slotWidth: 62 });
    const stamps = picked.map((p) => times.get(p.id) ?? 0);
    expect([...stamps].sort((a, b) => a - b)).toEqual(stamps);
  });
});
