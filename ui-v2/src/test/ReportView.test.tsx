import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReportView from "../components/ReportView";
import * as api from "../api";

afterEach(() => vi.restoreAllMocks());

const summary: api.ReportSummary = {
  schema: "s", not_a_verdict: true, source_mode: "research",
  report_schema_version: "deeputin-stage3-v1.4",
  stage2_schema_version: "deeputin-stage2-v1",
  created_at_utc: "2026-07-29T00:00:00Z",
  summary: { pair_count: 25, change_count: 2 },
  narrative: ["Исследование охватывает 520 фотографий."],
  methodology: { stage1: "single inference" },
  validation: { status: "complete", errors: [] },
  sections: [
    { name: "pairs", title: "Все сравнения", present: true, size: 250, paged: true },
    { name: "change_points", title: "Кандидаты изменений", present: false, size: null, paged: true },
  ],
  status_semantics: {
    status: "evidence_state Stage 2",
    measurement_status: "исходный status Stage 2",
    note: "Stage 3 публикует evidence_state под именем status.",
  },
  withheld_column_prefixes: ["texture_", "uv_"],
  withheld_note: "Колонки texture_* и uv_* исключены политикой Stage 3.",
};

const page = (offset: number, returned: number): api.ReportSection => ({
  schema: "s", name: "pairs", title: "Все сравнения", present: true,
  total: 250, offset, returned, paged: true,
  payload: Array.from({ length: returned }, (_, i) => ({ pair_id: `p${offset + i}` })),
});

describe("ReportView", () => {
  it("показывает нарратив Stage 3", async () => {
    vi.spyOn(api, "fetchReportSummary").mockResolvedValue(summary);
    render(<ReportView />);
    await waitFor(() => expect(screen.getByText(/520 фотографий/)).toBeTruthy());
  });

  it("предупреждает о разной семантике поля status", async () => {
    vi.spyOn(api, "fetchReportSummary").mockResolvedValue(summary);
    render(<ReportView />);
    await waitFor(() => expect(screen.getByText(/evidence_state под именем status/)).toBeTruthy());
  });

  it("объясняет, что texture_/uv_ скрыты политикой, а не потеряны", async () => {
    vi.spyOn(api, "fetchReportSummary").mockResolvedValue(summary);
    render(<ReportView />);
    await waitFor(() => expect(screen.getByText(/исключены политикой Stage 3/)).toBeTruthy());
  });

  it("статус валидации виден", async () => {
    vi.spyOn(api, "fetchReportSummary").mockResolvedValue(summary);
    render(<ReportView />);
    await waitFor(() => expect(screen.getByText(/Валидация отчёта|Report validation/)).toBeTruthy());
  });

  it("отсутствие report_validation.json не выдаётся за успешную валидацию", async () => {
    vi.spyOn(api, "fetchReportSummary").mockResolvedValue({ ...summary, validation: null });
    render(<ReportView />);
    await waitFor(() => expect(screen.getByText(/не подтверждена|unconfirmed/)).toBeTruthy());
  });

  it("отсутствующая секция перечисляется явно", async () => {
    vi.spyOn(api, "fetchReportSummary").mockResolvedValue(summary);
    render(<ReportView />);
    await waitFor(() => expect(screen.getByText("Кандидаты изменений")).toBeTruthy());
    expect(screen.getByText(/нет секции|no section/)).toBeTruthy();
  });

  it("секция открывается и листается страницами", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "fetchReportSummary").mockResolvedValue(summary);
    const spy = vi.spyOn(api, "fetchReportSection")
      .mockResolvedValueOnce(page(0, 100))
      .mockResolvedValueOnce(page(100, 100));
    render(<ReportView />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Все сравнения" })).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "Все сравнения" }));
    await waitFor(() => expect(screen.getByText(/1–100 \/ 250/)).toBeTruthy());

    await user.click(screen.getByRole("button", { name: /Следующая страница|Next page/ }));
    await waitFor(() => expect(screen.getByText(/101–200 \/ 250/)).toBeTruthy());
    expect(spy).toHaveBeenLastCalledWith("pairs", 100);
  });

  it("кнопка назад заблокирована на первой странице", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "fetchReportSummary").mockResolvedValue(summary);
    vi.spyOn(api, "fetchReportSection").mockResolvedValue(page(0, 100));
    render(<ReportView />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Все сравнения" })).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "Все сравнения" }));
    await waitFor(() => expect(screen.getByText(/1–100 \/ 250/)).toBeTruthy());
    const prev = screen.getByRole("button", { name: /Предыдущая страница|Previous page/ });
    expect((prev as HTMLButtonElement).disabled).toBe(true);
  });

  it("отсутствие Stage 3 объясняется, а не выглядит поломкой", async () => {
    vi.spyOn(api, "fetchReportSummary").mockRejectedValue(new Error("HTTP 409"));
    render(<ReportView />);
    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());
    expect(screen.getByText(/после прогона Stage 3|after a Stage 3 run/)).toBeTruthy();
  });

  it("сетевая ошибка отличается от отсутствия отчёта", async () => {
    vi.spyOn(api, "fetchReportSummary").mockRejectedValue(new Error("network down"));
    render(<ReportView />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  });
});
