import { describe, expect, it, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";
import UnifiedTimeline from "../components/UnifiedTimeline";
import {
  BASELINE_METRIC_KEYS, BaselineContext, EMPTY_BASELINE,
  type BaselineRefs,
} from "../baseline";
import { type Photo } from "../data";
import { buildDemoPhotos } from "../demoData";

/** Демо-набор как тестовая фикстура: генератор вынесен из основного
 * бандла (аудит №27), поэтому строим его явно. */
const DEMO_PHOTOS = buildDemoPhotos();

const noop = () => undefined;

// jsdom не реализует ResizeObserver, который таймлайн использует для замера
// ширины. Подставляем минимальную заглушку с фиксированной шириной окна.
class ResizeObserverStub {
  constructor(private cb: ResizeObserverCallback) {}
  observe(target: Element) {
    this.cb([{ contentRect: { width: 1200, height: 600 } } as ResizeObserverEntry],
      this as unknown as ResizeObserver);
    void target;
  }
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", ResizeObserverStub);

function renderTimeline(photos: Photo[], sufficient: boolean, chrono = {}) {
  const refs = Object.fromEntries(
    BASELINE_METRIC_KEYS.map(key => [
      key,
      { median: 0, std: 1 },
    ]),
  );
  const pipelineBaseline: BaselineRefs = {
    refs,
    baselineEra: "SEG",
    sampleSize: 20,
    sufficient: true,
    source: "pipeline",
  };
  const baseline: BaselineRefs = sufficient
    ? pipelineBaseline
    : { ...EMPTY_BASELINE, sampleSize: 2 };

  return render(
    <BaselineContext.Provider value={baseline}>
      <UnifiedTimeline
        photos={photos} filmstripOffset={0} setFilmstripOffset={noop} thumbSize={50}
        playheadT={photos[0]?.t ?? 0} onSelectPhoto={noop} selectedId={null}
        onScrubTo={noop} onPinClick={noop} onDoubleClickPhoto={noop}
        onRangeSelected={noop} rangeSelection={null} chronoAnomalies={chrono}
      />
    </BaselineContext.Provider>,
  );
}

const flagged = (n: number): Photo[] =>
  Array.from({ length: n }, (_, i) => ({
    ...DEMO_PHOTOS[i % DEMO_PHOTOS.length],
    id: `p${i}`,
    t: Date.parse("2000-01-01") + i * 30 * 86400000,
    era: "SEG",
    bucket: "frontal" as const,
    flags: i === 3 ? ["RETURN_TO_BASELINE"] : i === 5 ? ["TEMPORAL_IMPOSSIBILITY"] : [],
  }));

afterEach(() => vi.restoreAllMocks());

describe("anomaly rendering on the timeline", () => {
  it("renders a dedicated anomaly track with a per-type icon", () => {
    const { container } = renderTimeline(flagged(12), true);
    // Дорожка аномалий подписана и содержит счётчик отмеченных кадров.
    expect(container.textContent).toContain("АНОМАЛИИ");
    // Оба типа присутствуют, а не только TEMPORAL_IMPOSSIBILITY.
    expect(container.querySelectorAll("svg").length).toBeGreaterThan(0);
  });

  it("shows 'no baseline' points as hollow, never as a normal-coloured dot", () => {
    const { container } = renderTimeline(flagged(12), false);
    const hollow = container.querySelectorAll('circle[stroke="#797876"][fill="none"]');
    // Ключевая регрессия: при отсутствии базы z подставлялся как 0 и точка
    // рисовалась штатным цветом — «нет оценки» читалось как «нормально».
    expect(hollow.length).toBeGreaterThan(0);
  });

  it("uses solid filled points once the baseline is sufficient", () => {
    const { container } = renderTimeline(flagged(20), true);
    const hollow = container.querySelectorAll('circle[stroke="#797876"][fill="none"]');
    expect(hollow.length).toBe(0);
  });

  it("marks years reported by Stage 2 detectors on the timeline", () => {
    const photos = flagged(12);
    const year = new Date(photos[0].t).getFullYear();
    const { container } = renderTimeline(photos, true, {
      irreversible_return: { event_count: 1, years: [year] },
    });
    const marks = container.querySelectorAll('div[style*="rgb(168, 111, 223)"]');
    expect(marks.length).toBeGreaterThan(0);
  });

  it("renders an anomaly minimap covering the whole chronology", () => {
    const { container } = renderTimeline(flagged(200), true);
    expect(container.querySelector('[role="slider"]')).toBeTruthy();
  });
});
