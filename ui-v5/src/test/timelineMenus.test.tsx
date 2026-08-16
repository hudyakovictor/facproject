import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, waitFor, act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createRouter,
  createRootRoute,
  createRoute,
} from "@tanstack/react-router";
import { validateAnalysisSearch } from "../shared/state/urlState";
import { TimelinePage } from "../features/timeline/TimelinePage";
import { useAnalysisStore } from "../shared/state/analysisStore";
import { buildCsv, buildViewState } from "../features/timeline/exportView";
import type { ResearchPhoto } from "../shared/researchApi";

/**
 * Верхнее меню таймлайна (§8.1), мультиракурс (§8.9) и экспорт (§8.10).
 *
 * Проверяется не наличие кнопок, а то, что меню сообщает правду о данных:
 * метрика без значений помечена как недоступная, статус калибровки не
 * приписывается сырому признаку, а мультиракурс не соединяет разные бины одной
 * линией.
 */

const photos: ResearchPhoto[] = Array.from({ length: 40 }, (_, i) => ({
  id: `P${i}`,
  date: `20${String(10 + (i % 10)).padStart(2, "0")}-0${(i % 9) + 1}-01`,
  t: null,
  bucket: i % 3 === 0 ? "frontal" : i % 3 === 1 ? "left_mid" : "right_deep",
  era: "2014-2019",
  quality: i % 5 === 0 ? null : (i % 100) / 100,
  yaw: i - 20,
  pitch: 1,
  roll: 2,
  fuzzy: "",
  measurementStatus: "compared",
  flags: i % 7 === 0 ? ["coherent_jump_candidate"] : [],
  sourceMode: "research",
  analysisStage: "stage2",
  zOrbitDepth: i % 4 === 0 ? i / 40 : null,
  skinQuality: 0.4,
}));

const initial = useAnalysisStore.getState();

beforeEach(() => {
  useAnalysisStore.setState(initial, true);
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (u: RequestInfo | URL) =>
        new Response(
          JSON.stringify(
            String(u).includes("summary")
              ? { source_mode: "research", not_a_verdict: true }
              : {
                  schema: "deeputin-api-research-timeline-v1.0",
                  source_mode: "research",
                  not_a_verdict: true,
                  photos,
                  era_meta: {},
                },
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
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider router={router as never} />
    </QueryClientProvider>
  );
}

async function mount() {
  const view = render(wrap(<TimelinePage />));
  await waitFor(
    () => {
      expect(view.container.textContent).toMatch(/ТАЙМЛАЙН/);
      expect(view.container.textContent?.toLowerCase()).not.toMatch(/загрузка/);
    },
    { timeout: 15_000 },
  );
  return view;
}

describe("меню «Ракурс» (§8.1)", () => {
  test("показывает количество, медиану качества и поддержку калибровки", async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole("button", { name: /Ракурс/ }));

    const menu = screen.getByRole("group", { name: "Выбор ракурса" });
    const row = within(menu).getByRole("row", { name: /Фронтальный/ });
    // 14 фронтальных кадров, у 4 из них есть калиброванная z-оценка.
    expect(within(row).getByText("14")).toBeTruthy();
    expect(within(row).getByText(/4 из 14/)).toBeTruthy();
  }, 30_000);

  test("пустой бин нельзя выбрать, но он остаётся видимым", async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole("button", { name: /Ракурс/ }));

    const menu = screen.getByRole("group", { name: "Выбор ракурса" });
    // Скрыть пустой бин значило бы скрыть факт отсутствия данных в нём.
    const empty = within(menu).getByRole("button", { name: "Левый профиль" });
    expect(empty).toBeDisabled();
  }, 30_000);

  test("медиана качества не подменяется нулём при отсутствии оценок", async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole("button", { name: /Ракурс/ }));

    const menu = screen.getByRole("group", { name: "Выбор ракурса" });
    const row = within(menu).getByRole("row", { name: /Левый профиль/ });
    expect(within(row).getByText("н/д")).toBeTruthy();
  }, 30_000);
});

describe("меню «Метрики» (§8.1)", () => {
  test("метрика без данных отключена и помечена", async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole("button", { name: /Метрики/ }));

    const menu = screen.getByRole("group", { name: "Выбор метрик" });
    // Дорожка по нулю кадров выглядит на экране так же уверенно, как полная.
    expect(within(menu).getAllByText("нет данных").length).toBeGreaterThan(0);
    const pc0 = within(menu).getByRole("checkbox", { name: /PC 0/ });
    expect(pc0).toBeDisabled();
  }, 30_000);

  test("калиброванные и диагностические величины различаются", async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole("button", { name: /Метрики/ }));

    const menu = screen.getByRole("group", { name: "Выбор метрик" });
    expect(within(menu).getAllByText("калибр.").length).toBeGreaterThan(0);
    expect(within(menu).getAllByText("диагн.").length).toBeGreaterThan(0);
  }, 30_000);

  test("включение метрики добавляет дорожку", async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole("button", { name: /Метрики/ }));

    const menu = screen.getByRole("group", { name: "Выбор метрик" });
    await user.click(within(menu).getByRole("checkbox", { name: /Качество кожи/ }));
    expect(useAnalysisStore.getState().visibleMetrics).toContain("skinQuality");
  }, 30_000);

  test("solo оставляет одну дорожку и возвращает набор обратно", async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole("button", { name: /Метрики/ }));

    const before = [...useAnalysisStore.getState().visibleMetrics];
    const solo = screen.getByRole("button", { name: "Показать только Yaw" });
    await user.click(solo);
    expect(useAnalysisStore.getState().visibleMetrics).toEqual(["yaw"]);

    await user.click(solo);
    expect(useAnalysisStore.getState().visibleMetrics).toEqual(before);
  }, 30_000);

  test("порядок дорожек меняется с клавиатуры, а не только мышью", async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole("button", { name: /Метрики/ }));

    const before = [...useAnalysisStore.getState().visibleMetrics];
    await user.click(screen.getByRole("button", { name: /Опустить дорожку Yaw/ }));
    const after = useAnalysisStore.getState().visibleMetrics;
    expect(after).not.toEqual(before);
    expect([...after].sort()).toEqual([...before].sort());
  }, 30_000);
});

describe("мультиракурс (§8.9)", () => {
  test("каждый бин получает собственные дорожки", async () => {
    const { container } = await mount();
    await act(async () => {
      useAnalysisStore.getState().setMultiPose(true);
      await new Promise((resolve) => setTimeout(resolve, 200));
    });

    // Три бина по четыре метрики: полосы не сливаются в одну кривую.
    expect(container.querySelectorAll("canvas").length).toBe(12);
    expect(container.textContent).toMatch(/3 ракурсов/);
    expect(container.textContent).toMatch(/Линии не соединяются между полосами/);
  }, 30_000);

  test("в одиночном режиме полос нет", async () => {
    const { container } = await mount();
    expect(container.textContent).not.toMatch(/Линии не соединяются/);
    expect(container.querySelectorAll("canvas").length).toBe(4);
  }, 30_000);
});

describe("экспорт (§8.10)", () => {
  const context = {
    photos: photos.slice(0, 3),
    metrics: ["quality", "yaw"],
    viewport: { start: Date.UTC(2010, 0, 1), end: Date.UTC(2019, 0, 1) },
    pose: "frontal",
    multiPose: false,
    schema: "deeputin-api-research-timeline-v1.0",
    sourceMode: "research",
    permalink: "https://example.test/timeline?pose=frontal",
  };

  test("CSV несёт пометку «не вердикт» и происхождение среза", () => {
    const csv = buildCsv(context);
    // Файл переживает интерфейс: без пометки таблица читается как заключение.
    expect(csv).toMatch(/НЕ ВЕРДИКТ/);
    expect(csv).toMatch(/deeputin-api-research-timeline-v1\.0/);
    expect(csv).toMatch(/viewport: 2010-01-01 … 2019-01-01/);
  });

  test("отсутствующее измерение остаётся пустым, а не нулём", () => {
    const csv = buildCsv({
      ...context,
      photos: [{ ...photos[0], quality: null }],
      metrics: ["quality"],
    });
    const dataRow = csv.split("\n").at(-1)!;
    expect(dataRow.endsWith(",")).toBe(true);
    expect(dataRow).not.toMatch(/,0$/);
  });

  test("JSON вида описывает происхождение каталога метрик", () => {
    const state = JSON.parse(buildViewState(context));
    expect(state.not_a_verdict).toMatch(/НЕ ВЕРДИКТ/);
    expect(state.view.visible_metrics).toEqual(["quality", "yaw"]);
    // Каталог ведётся в интерфейсе: backend его не отдаёт, и файл это признаёт.
    expect(state.metric_catalog[0].catalog_source).toMatch(/backend каталога не отдаёт/);
  });

  test("CSV экранирует разделители в значениях", () => {
    const csv = buildCsv({
      ...context,
      photos: [{ ...photos[0], id: 'P,0 "x"' }],
      metrics: [],
    });
    expect(csv).toMatch(/"P,0 ""x"""/);
  });
});
