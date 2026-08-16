import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, waitFor, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createRouter,
  createRootRoute,
  createRoute,
} from "@tanstack/react-router";
import { validateAnalysisSearch } from "../shared/state/urlState";
import { DataManagerPage } from "../features/data-manager/DataManagerPage";
import { useAnalysisStore } from "../shared/state/analysisStore";
import { parseFilename, isAcceptable } from "../features/data-manager/ingest";
import { buildCsv } from "../features/data-manager/exportRows";
import { DATA_COLUMNS } from "../features/data-manager/columns";
import type { ResearchPhoto } from "../shared/researchApi";

/**
 * Экран данных (§7 ТЗ), дефекты BUG-3 и D11.
 *
 * Проверяется главное: таблица не держит весь архив в разметке, числа под ней
 * посчитаны, а колонки без источника данных не изображают результат проверки,
 * которой не было.
 */

const photos: ResearchPhoto[] = Array.from({ length: 900 }, (_, i) => ({
  id: `2010_01_${String((i % 28) + 1).padStart(2, "0")}_${i}`,
  date: `20${String(10 + (i % 10)).padStart(2, "0")}-01-01`,
  t: null,
  bucket: i % 2 === 0 ? "frontal" : "left_mid",
  era: "E",
  quality: i % 7 === 0 ? null : (i % 100) / 100,
  yaw: i - 400,
  pitch: 1,
  roll: 2,
  fuzzy: "",
  measurementStatus: "compared",
  flags: i % 11 === 0 ? ["coherent_jump_candidate"] : [],
  sourceMode: "research",
  analysisStage: "stage2",
  dateProvenanceStatus: "exif",
}));

const jobsBody = {
  jobs: [
    {
      id: "j1",
      kind: "extract",
      status: "blocked",
      progress: { done: 0, total: 0 },
      logs: ["нет весов"],
      error: "3DDFA_V3 weights missing",
    },
    {
      id: "j2",
      kind: "extract",
      status: "running",
      progress: { done: 3, total: 10 },
      logs: [],
    },
  ],
};

const initial = useAnalysisStore.getState();

beforeEach(() => {
  useAnalysisStore.setState({ ...initial, multiPose: true, search: "", selectedPhoto: null }, true);

  vi.stubGlobal(
    "fetch",
    vi.fn(async (u: RequestInfo | URL) => {
      const url = String(u);
      const json = (body: unknown) =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("/jobs")) return json(jobsBody);
      if (url.includes("summary")) return json({ source_mode: "research", not_a_verdict: true });
      return json({
        schema: "deeputin-api-research-timeline-v1.0",
        source_mode: "research",
        not_a_verdict: true,
        photos,
        era_meta: {},
      });
    }),
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
  const view = render(wrap(<DataManagerPage />));
  await waitFor(() => expect(view.container.textContent).toMatch(/ДАННЫЕ И PROVENANCE/), {
    timeout: 15_000,
  });
  await waitFor(
    () => expect(view.container.querySelectorAll('[role="row"]').length).toBeGreaterThan(1),
    { timeout: 15_000 },
  );
  return view;
}

describe("таблица данных (D11, BUG-3)", () => {
  test("в разметку попадают только видимые строки", async () => {
    const { container } = await mount();
    const rows = container.querySelectorAll('[role="row"]').length;
    // 900 записей: прежняя таблица держала в DOM все строки сразу.
    expect(rows).toBeLessThan(60);
    expect(container.querySelectorAll("*").length).toBeLessThan(700);
  }, 40_000);

  test("счётчики посчитаны, а не написаны литералом", async () => {
    const { container } = await mount();
    // Раньше подпись «1–10 из 137» не зависела от данных.
    expect(container.textContent).toMatch(/Всего в архиве: 900/);
    expect(container.textContent).toMatch(/Строк: 900/);
  }, 40_000);

  test("сортировка по столбцу переставляет строки в обе стороны", async () => {
    const user = userEvent.setup();
    const { container } = await mount();
    const firstId = () =>
      container
        .querySelector('[role="row"][aria-selected]')
        ?.textContent?.match(/2010_\d\d_\d\d_\d+/)?.[0];

    const header = screen.getByRole("columnheader", { name: /Идентификатор/ });

    await user.click(header);
    const ascending = firstId();
    await user.click(header);
    const descending = firstId();

    expect(ascending).toBeTruthy();
    expect(descending).toBeTruthy();
    // Второе нажатие обязано перевернуть порядок, а не сбросить его.
    expect(descending).not.toBe(ascending);
  }, 40_000);

  test("заголовок сообщает направление сортировки", async () => {
    const user = userEvent.setup();
    await mount();
    const header = screen.getByRole("columnheader", { name: /Идентификатор/ });
    await user.click(header);
    await waitFor(() => expect(header).toHaveAttribute("aria-sort", "ascending"));
  }, 40_000);
});

describe("колонки без источника данных", () => {
  test("SHA-256 и дубликаты помечены и не показывают результат", async () => {
    const user = userEvent.setup();
    const { container } = await mount();

    await user.click(screen.getByRole("button", { name: /Колонки/ }));
    const menu = screen.getByRole("group", { name: "Выбор колонок" });
    await user.click(within(menu).getByRole("checkbox", { name: /SHA-256/ }));

    // Прежняя версия писала «недоступен в API» и рядом рисовала галочку
    // совпадения хеша — результат сверки, которой не было.
    await waitFor(() => {
      expect(container.textContent).toMatch(/нет источника/);
    });
  }, 40_000);

  test("каталог колонок объявляет происхождение каждой величины", () => {
    const absent = DATA_COLUMNS.filter((column) => column.origin === "absent");
    expect(absent.map((column) => column.id).sort()).toEqual([
      "duplicate",
      "rights",
      "sha256",
    ]);
    // У каждой колонки без источника должно быть объяснение причины.
    for (const column of absent) expect(column.note).toBeTruthy();
  });
});

describe("очередь заданий (§7.7)", () => {
  test("статус blocked отличается от сбоя и объясняет причину", async () => {
    const { container } = await mount();
    await waitFor(() => expect(container.textContent).toMatch(/невозможно/));
    // «Заблокировано» не должно читаться ни как «готово», ни как «упало».
    expect(container.textContent).toMatch(/Это не сбой расчёта — расчёт не запускался/);
    expect(container.textContent).toMatch(/3DDFA_V3 weights missing/);
  }, 40_000);

  test("прогресс показывается только когда объём работы известен", async () => {
    const { container } = await mount();
    await waitFor(() => expect(container.textContent).toMatch(/3 из 10/));
    expect(container.textContent).toMatch(/объём неизвестен/);
  }, 40_000);
});

describe("разбор имени файла (§7.2)", () => {
  test("дата читается из имени и предлагается идентификатор", () => {
    const parsed = parseFilename("2014_03_18_2.jpg");
    expect(parsed.date).toBe("2014-03-18");
    expect(parsed.sequence).toBe(2);
    expect(parsed.proposedId).toBe("2014_03_18_2");
    expect(isAcceptable(parsed)).toBe(true);
  });

  test("неподходящее имя не получает подставленную дату", () => {
    const parsed = parseFilename("photo-final(2).jpg");
    // Молча «исправить» дату значило бы утверждать время съёмки.
    expect(parsed.date).toBeNull();
    expect(parsed.proposedId).toBeNull();
    expect(isAcceptable(parsed)).toBe(false);
  });

  test("несуществующая календарная дата отвергается", () => {
    const parsed = parseFilename("2014_02_31.jpg");
    expect(parsed.date).toBeNull();
    expect(parsed.problems.join(" ")).toMatch(/не существует/);
  });

  test("дата в будущем помечается, а не отбрасывается молча", () => {
    const parsed = parseFilename("2100_01_01.jpg", new Date("2026-01-01T00:00:00Z"));
    expect(parsed.date).toBe("2100-01-01");
    expect(parsed.problems.join(" ")).toMatch(/будущем/);
    expect(isAcceptable(parsed)).toBe(false);
  });

  test("неподдерживаемое расширение названо явно", () => {
    const parsed = parseFilename("2014_03_18.tiff");
    expect(parsed.problems.join(" ")).toMatch(/\.tiff/);
  });
});

describe("экспорт выборки", () => {
  test("«н/д» сохраняется как «н/д», а не как пустая ячейка", () => {
    const csv = buildCsv([{ ...photos[0], quality: null }], ["id", "quality"]);
    const dataRow = csv.split("\n").at(-1)!;
    // Пустая ячейка в файле неотличима от измеренного пустого значения.
    expect(dataRow).toMatch(/н\/д$/);
  });

  test("файл несёт пометку «не вердикт»", () => {
    const csv = buildCsv(photos.slice(0, 2), ["id"]);
    expect(csv).toMatch(/НЕ ВЕРДИКТ/);
  });
});
