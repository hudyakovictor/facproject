import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter, createRootRoute, createRoute } from "@tanstack/react-router";
import { validateAnalysisSearch } from "../shared/state/urlState";
import { TimelinePage } from "../features/timeline/TimelinePage";
import { useAnalysisStore } from "../shared/state/analysisStore";
import type { ResearchPhoto } from "../shared/researchApi";

/**
 * Бюджет таймлайна на полном архиве (Gate Ф4).
 *
 * До перехода на Canvas 2D экран строил 10 244 DOM-узла и 7 637 элементов
 * `<circle>` при 1909 фотографиях: по узлу на каждое измерение каждой дорожки.
 * Тест фиксирует, что рендер остаётся ограниченным по числу узлов независимо
 * от размера архива — иначе следующая «маленькая» правка вернёт D12.
 *
 * jsdom не измеряет layout и paint, поэтому проверяется структура, а не fps:
 * число узлов — та величина, которая определяла деградацию.
 */

const BINS = [
  "frontal", "left_light", "left_mid", "left_deep", "left_profile",
  "right_light", "right_mid", "right_deep", "right_profile",
];

const photos: ResearchPhoto[] = Array.from({ length: 1909 }, (_, i) => {
  const date = new Date(Date.UTC(1999, 0, 1) + i * 5.1 * 86_400_000);
  return {
    id: `DEEPUTIN_${i}`,
    date: date.toISOString().slice(0, 10),
    t: date.getTime(),
    bucket: BINS[i % 9],
    era: "2014-2019",
    quality: (i % 100) / 100,
    yaw: (i % 180) - 90,
    pitch: (i % 90) - 45,
    roll: (i % 90) - 45,
    fuzzy: "",
    measurementStatus: "compared",
    flags: i % 40 === 0 ? ["coherent_jump_candidate"] : [],
    sourceMode: "research",
    analysisStage: "stage2",
    evidenceState: "available",
    stage2PairCount: 2,
    stage2StatusCounts: (i % 40 === 0 ? { coherent_jump_candidate: 1 } : {}) as Record<string, number>,
    stage2EvidenceCounts: {},
    boneScore: 0.5,
    p0: 0.1,
    p1: 0.2,
    p2: 0.3,
  };
});

const body = {
  schema: "deeputin-api-research-timeline-v1.0",
  source_mode: "research",
  not_a_verdict: true,
  photos,
  era_meta: {},
};

const initial = useAnalysisStore.getState();

beforeEach(() => {
  useAnalysisStore.setState(initial, true);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      new Response(
        JSON.stringify(
          String(input).includes("summary")
            ? { source_mode: "research", not_a_verdict: true }
            : body,
        ),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );
});

function wrap(ui: React.ReactNode) {
  const rootRoute = createRootRoute({
    component: () => <>{ui}</>,
    validateSearch: validateAnalysisSearch,
  });
  const idx = createRoute({ getParentRoute: () => rootRoute, path: "/", component: () => null });
  const router = createRouter({ routeTree: rootRoute.addChildren([idx]) });
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router as never} />
    </QueryClientProvider>
  );
}

async function renderTimeline(multiPose: boolean) {
  const { container } = render(wrap(<TimelinePage />));
  await waitFor(
    () => expect(container.textContent?.toLowerCase()).not.toMatch(/загрузка/),
    { timeout: 20_000 },
  );
  if (multiPose) {
    await act(async () => {
      useAnalysisStore.getState().setMultiPose(true);
      await new Promise((r) => setTimeout(r, 300));
    });
  }
  return container;
}

describe("бюджет рендера таймлайна на 1909 фото", () => {
  test("число DOM-узлов ограничено независимо от размера архива", async () => {
    const container = await renderTimeline(true);
    const nodes = container.querySelectorAll("*").length;
    // До Canvas было 10 244. Порог с запасом, но на порядок ниже прежнего.
    expect(nodes).toBeLessThan(1200);
  }, 40_000);

  test("дорожки метрик не создают узел на измерение", async () => {
    const container = await renderTimeline(true);
    // Раньше здесь было 7 637 <circle>. Точки рисует Canvas.
    expect(container.querySelectorAll("circle").length).toBeLessThan(10);
    expect(container.querySelectorAll("canvas").length).toBeGreaterThan(0);
  }, 40_000);

  test("превью прореживаются, а не рендерятся все подряд", async () => {
    const container = await renderTimeline(true);
    const images = container.querySelectorAll("img").length;
    expect(images).toBeGreaterThan(0);
    expect(images).toBeLessThan(120);
  }, 40_000);
});
