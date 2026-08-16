import { beforeEach, describe, expect, test, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { TimelinePage } from "../features/timeline/TimelinePage";
import { ClusteringPage } from "../features/clustering/ClusteringPage";
import { DataManagerPage } from "../features/data-manager/DataManagerPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { PairAnalysisPage } from "../features/pair-analysis/PairAnalysisPage";
import { MorphingPage } from "../features/morphing/MorphingPage";
import { PhotoInspectorPage } from "../features/photo-inspector/PhotoInspectorPage";
import { isFinding } from "../shared/findings";
import { poseLabel } from "../shared/poseBins";
import { sortPhotosByTime, timeBounds } from "../shared/time";
import type { ResearchPhoto } from "../shared/researchApi";

/**
 * Регрессионный набор на сценарии отказа.
 *
 * Все проверки здесь соответствуют дефектам, найденным аудитом: пустые данные,
 * ошибка API, null-метрики и режим Stage 1. Существовавшие раньше тесты
 * проверяли только наличие строкового литерала на happy path и оставались
 * зелёными при всех этих дефектах.
 */

const photo = (over: Partial<ResearchPhoto> = {}): ResearchPhoto => ({
  id: "p1",
  date: "2020-01-01",
  t: 1577836800000,
  bucket: "frontal",
  era: "2020-2026",
  quality: 0.8,
  yaw: 1,
  pitch: 2,
  roll: 3,
  fuzzy: "",
  measurementStatus: "compared",
  flags: [],
  sourceMode: "research",
  analysisStage: "stage2",
  evidenceState: "available",
  stage2PairCount: 1,
  stage2StatusCounts: {},
  stage2EvidenceCounts: {},
  ...over,
});

/** Строка ровно такой формы, какую отдаёт app6/api/stage1_timeline.py. */
const stage1Photo = (over: Partial<ResearchPhoto> = {}): ResearchPhoto => ({
  id: "DEEPUTIN_1999_0816_001",
  date: "1999-08-16",
  t: 934761600000,
  era: "1999-2007",
  bucket: "frontal",
  quality: 0.73,
  qualityBasis: "combined_visible_fraction",
  boneScore: null,
  p0: null,
  p1: null,
  p2: null,
  yaw: 3.1,
  pitch: -1.2,
  roll: 0.4,
  dominant: "UNAVAILABLE",
  fuzzy: "INSUFFICIENT_DATA",
  confidence: null,
  flags: ["STAGE1_INVENTORY_ONLY"],
  sourceMode: "research",
  analysisStage: "stage1_inventory",
  bayesianProjectionAvailable: false,
  measurementStatus: "not_compared",
  dateProvenanceStatus: "unknown",
  uiContractViolations: ["boneScore", "p0", "p1", "p2"],
  uiFieldsSchema: "deeputin-ui-fields-v1.0",
  // evidenceState / stage2* намеренно отсутствуют — их нет и в ответе backend
  ...over,
});

function mockApi(timeline: unknown, summary: unknown = { source_mode: "research", not_a_verdict: true, technical_summary: {} }) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      new Response(JSON.stringify(String(input).includes("run/summary") ? summary : timeline), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

function mockFailure(status: number, detail = "boom") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ detail }), { status, headers: { "Content-Type": "application/json" } })),
  );
}

const body = (photos: ResearchPhoto[], over: Record<string, unknown> = {}) => ({
  source_mode: "research",
  not_a_verdict: true,
  analysis_stage: "stage2",
  photos,
  era_meta: {},
  ...over,
});

const stage1Body = (photos: ResearchPhoto[]) => ({
  schema: "deeputin-stage1-timeline",
  source_mode: "research",
  not_a_verdict: true,
  analysis_stage: "stage1_inventory",
  era_meta: { "1999-2007": { label: "1999-2007", start: "1999-01-01", end: "2007-12-31" } },
  photos,
  ui_fields_schema: "deeputin-ui-fields-v1.0",
  ui_fields_complete_photo_count: 0,
  ui_fields_violations_by_field: { boneScore: photos.length, p0: photos.length, p1: photos.length, p2: photos.length },
  note: "Реальный инвентарь Stage 1: сравнительные метрики появятся только после Stage 2.",
});

function renderPage(ui: ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {ui}
    </QueryClientProvider>,
  );
}

const settled = async (container: HTMLElement) => {
  await waitFor(() => expect(container.textContent).not.toMatch(/Загрузка/), { timeout: 4000 });
  return container.textContent ?? "";
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("пустые данные не приводят к пустому экрану", () => {
  test("таймлайн объясняет отсутствие записей", async () => {
    mockApi(body([]));
    const { container } = renderPage(<TimelinePage />);
    const text = await settled(container);
    expect(text).toMatch(/Записей нет/);
    expect(text).not.toMatch(/NaN|Infinity|undefined/);
  });

  test("кластеризация не падает на Math.min пустого массива", async () => {
    mockApi(body([]));
    const { container } = renderPage(<ClusteringPage />);
    const text = await settled(container);
    // Раньше здесь рендерилось 0 байт: Math.min(...[]) → Infinity → RangeError.
    expect(text.trim().length).toBeGreaterThan(0);
    expect(text).toMatch(/Записей нет/);
    expect(text).not.toMatch(/Invalid Date|NaN/);
  });

  test("кластеризация объясняет отсутствие дат", async () => {
    mockApi(body([photo({ date: null, t: null })]));
    const { container } = renderPage(<ClusteringPage />);
    const text = await settled(container);
    expect(text).toMatch(/нет даты/i);
  });

  test("парное сравнение отличает нехватку записей от ошибки", async () => {
    mockApi(body([photo()]));
    const { container } = renderPage(<PairAnalysisPage />);
    const text = await settled(container);
    expect(text).toMatch(/Недостаточно записей/);
  });

  test("морфинг объясняет отсутствие датированных кадров", async () => {
    mockApi(body([]));
    const { container } = renderPage(<MorphingPage />);
    const text = await settled(container);
    expect(text).toMatch(/Нет датированных кадров/);
  });

  test("инспектор не называет пустые данные ошибкой", async () => {
    mockApi(body([]));
    const { container } = renderPage(<PhotoInspectorPage />);
    const text = await settled(container);
    expect(text).toMatch(/Записей нет/);
    expect(text).not.toMatch(/^Ошибка\./);
  });
});

describe("ошибка API отличима от нехватки данных", () => {
  test("парное сравнение показывает код и причину", async () => {
    mockFailure(500, "internal boom");
    const { container } = renderPage(<PairAnalysisPage />);
    const text = await settled(container);
    expect(text).toMatch(/HTTP 500/);
    expect(text).toMatch(/internal boom/);
    expect(text).not.toMatch(/минимум две записи/);
  });

  test("таймлайн показывает код ответа", async () => {
    mockFailure(503, "backend down");
    const { container } = renderPage(<TimelinePage />);
    const text = await settled(container);
    expect(text).toMatch(/HTTP 503/);
    expect(text).toMatch(/backend down/);
  });

  test("каталог данных различает 409 и пустоту", async () => {
    mockFailure(409, "stage 1 отсутствует");
    const { container } = renderPage(<DataManagerPage />);
    const text = await settled(container);
    expect(text).toMatch(/HTTP 409/);
    expect(text).toMatch(/stage 1 отсутствует/);
  });
});

describe("null не превращается в ноль", () => {
  test("пустые quality и yaw печатаются как н/д", async () => {
    mockApi(body([photo({ quality: null, yaw: null })]));
    const { container } = renderPage(<DataManagerPage />);
    await settled(container);
    const cells = [...(container.querySelector("tbody tr")?.querySelectorAll("td") ?? [])].map((c) => c.textContent);
    expect(cells).not.toContain("0.00");
    expect(cells).not.toContain("0°");
    expect(cells.filter((c) => c === "н/д").length).toBeGreaterThanOrEqual(2);
  });

  test("карточка кадра показывает н/д вместо нулей", async () => {
    mockApi(body([photo({ quality: null, yaw: null, pitch: null, roll: null })]));
    const { container } = renderPage(<TimelinePage />);
    await settled(container);
    const thumb = container.querySelector("img")?.closest("button");
    thumb?.click();
    await waitFor(() => expect(container.querySelector("aside")).toBeTruthy());
    const aside = container.querySelector("aside")?.textContent ?? "";
    expect(aside).toMatch(/н\/д/);
    expect(aside).not.toMatch(/0\.0/);
  });
});

describe("режим Stage 1 не выдаётся за Stage 2", () => {
  test("заголовок таймлайна называет реальную стадию", async () => {
    mockApi(stage1Body([stage1Photo()]));
    const { container } = renderPage(<TimelinePage />);
    const text = await settled(container);
    expect(text).toMatch(/STAGE 1/);
    expect(text).not.toMatch(/STAGE 2 · РЕАЛЬНЫЕ ДАННЫЕ/);
  });

  test("обзор не утверждает загрузку из Stage 2", async () => {
    mockApi(stage1Body([stage1Photo()]));
    const { container } = renderPage(<OverviewPage />);
    const text = await settled(container);
    expect(text).not.toMatch(/Данные загружены из Stage 2/);
    expect(text).toMatch(/STAGE 1/);
  });

  test("технический флаг Stage 1 не считается находкой", async () => {
    mockApi(stage1Body([stage1Photo(), stage1Photo({ id: "b", date: "2003-01-01", t: 1041379200000 })]));
    const { container } = renderPage(<TimelinePage />);
    const text = await settled(container);
    expect(text).toMatch(/Находки · 0/);
  });

  test("нарушения контракта полей выводятся из данных", async () => {
    mockApi(stage1Body([stage1Photo()]));
    const { container } = renderPage(<TimelinePage />);
    const text = await settled(container);
    expect(text).toMatch(/boneScore/);
    expect(text).toMatch(/Полнота полей/);
  });

  test("страницы не падают без полей Stage 2", async () => {
    mockApi(stage1Body([stage1Photo()]));
    const { container } = renderPage(<DataManagerPage />);
    const text = await settled(container);
    expect(text.length).toBeGreaterThan(0);
  });
});

describe("порядок и время", () => {
  test("несортированный ответ не инвертирует шкалу", async () => {
    const late = photo({ id: "late", date: "2024-01-01", t: 1704067200000 });
    const early = photo({ id: "early", date: "1999-01-01", t: 915148800000 });
    mockApi(body([late, early]));
    const { container } = renderPage(<TimelinePage />);
    const text = await settled(container);
    expect(text).toMatch(/1999—2024/);
    expect(text).not.toMatch(/2024—1999/);
  });

  test("кадры без даты не приписываются к началу шкалы", async () => {
    mockApi(body([photo(), photo({ id: "nodate", date: null, t: null })]));
    const { container } = renderPage(<TimelinePage />);
    const text = await settled(container);
    expect(text).toMatch(/без даты: 1/);
  });

  test("sortPhotosByTime разделяет датированные и недатированные", () => {
    const { dated, undated } = sortPhotosByTime([
      photo({ id: "b", t: 200 }),
      photo({ id: "x", t: null }),
      photo({ id: "a", t: 100 }),
    ]);
    expect(dated.map((p) => p.id)).toEqual(["a", "b"]);
    expect(undated.map((p) => p.id)).toEqual(["x"]);
  });

  test("timeBounds возвращает null без датированных кадров", () => {
    expect(timeBounds([photo({ t: null })])).toBeNull();
  });
});

describe("пагинация отражает реальность", () => {
  test("в DOM ровно столько строк, сколько обещает подпись", async () => {
    const photos = Array.from({ length: 137 }, (_, i) =>
      photo({ id: `p${i}`, date: `20${String(10 + (i % 15)).padStart(2, "0")}-01-01`, t: 1577836800000 + i * 86400000 }),
    );
    mockApi(body(photos));
    const { container } = renderPage(<DataManagerPage />);
    await settled(container);
    const rows = container.querySelectorAll("tbody tr").length;
    const footer = container.textContent ?? "";
    expect(rows).toBe(50);
    expect(footer).toMatch(/1–50 из 137/);
    expect(footer).not.toMatch(/10 на странице/);
  });
});

describe("инварианты научной достоверности", () => {
  test("технические флаги исключены из находок", () => {
    expect(isFinding(photo({ flags: ["STAGE1_INVENTORY_ONLY"] }))).toBe(false);
    expect(isFinding(photo({ flags: ["date_conflict"] }))).toBe(true);
  });

  test("справочник ракурсов покрывает оба профиля", () => {
    expect(poseLabel("left_profile")).toBe("Лево · профиль");
    expect(poseLabel("right_profile")).toBe("Право · профиль");
  });

  test("маркировка «не вердикт» присутствует на экране", async () => {
    mockApi(body([photo()]));
    const { container } = renderPage(<TimelinePage />);
    await settled(container);
    // Маркер живёт в RootLayout; здесь проверяем, что страница его не отменяет
    expect(container.textContent).not.toMatch(/ВЕРДИКТ:/);
  });
});
