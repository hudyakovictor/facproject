import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RunSummaryView from "../components/RunSummaryView";
import * as api from "../api";

afterEach(() => vi.restoreAllMocks());

const summary: api.RunSummary = {
  schema: "s", not_a_verdict: true, source_mode: "research",
  category_titles: {
    A: { ru: "Статзначимость", en: "Statistical significance" },
    I: { ru: "Сводка прогона", en: "Run summary" },
  },
  categories: {
    A: { coverage: { multiple_testing_pair_count: 25 } },
    I: {
      summary: {
        limitations: ["mesh calibration incomplete"],
        skipped_pair_counts: { pose_mismatch: 4 },
        missing_mandatory_qc_record_count: 2,
      },
    },
  },
  technical_summary: { status_counts: { measured: 20 } },
  metric_catalog: null,
  artifacts: [
    { name: "multiple_testing", category: "A", purpose: "Таблица q-value", present: true, size_bytes: 2048 },
    { name: "evidence_packets", category: "A", purpose: "Пакеты доказательств", present: false, size_bytes: null },
  ],
};

describe("RunSummaryView", () => {
  it("ограничения прогона показываются", async () => {
    vi.spyOn(api, "fetchRunSummary").mockResolvedValue(summary);
    render(<RunSummaryView />);
    await waitFor(() => expect(screen.getByText(/mesh calibration incomplete/)).toBeTruthy());
  });

  it("пропущенные пары перечислены с причиной", async () => {
    vi.spyOn(api, "fetchRunSummary").mockResolvedValue(summary);
    render(<RunSummaryView />);
    await waitFor(() => expect(screen.getByText(/pose mismatch/)).toBeTruthy());
  });

  it("записи без обязательного QC учтены", async () => {
    vi.spyOn(api, "fetchRunSummary").mockResolvedValue(summary);
    render(<RunSummaryView />);
    await waitFor(() => expect(screen.getByText(/без обязательного QC|without mandatory QC/)).toBeTruthy());
  });

  it("несозданный артефакт перечисляется явно, а не пропускается", async () => {
    vi.spyOn(api, "fetchRunSummary").mockResolvedValue(summary);
    render(<RunSummaryView />);
    await waitFor(() => expect(screen.getByText("evidence_packets")).toBeTruthy());
    expect(screen.getByText(/не создан|not produced/)).toBeTruthy();
  });

  it("существующий артефакт открывается по клику", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "fetchRunSummary").mockResolvedValue(summary);
    vi.spyOn(api, "fetchRunArtifact").mockResolvedValue({
      schema: "s", name: "multiple_testing", category: "A", purpose: "p",
      size_bytes: 2048, truncated: false, payload: { rows: 25 },
    });
    render(<RunSummaryView />);
    await waitFor(() => expect(screen.getByRole("button", { name: "multiple_testing" })).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "multiple_testing" }));
    await waitFor(() => expect(screen.getByText(/"rows": 25/)).toBeTruthy());
  });

  it("слишком крупный артефакт не рендерится целиком", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "fetchRunSummary").mockResolvedValue(summary);
    vi.spyOn(api, "fetchRunArtifact").mockResolvedValue({
      schema: "s", name: "multiple_testing", category: "A", purpose: "p",
      size_bytes: 40 * 1024 * 1024, truncated: true, payload: null,
    });
    render(<RunSummaryView />);
    await waitFor(() => expect(screen.getByRole("button", { name: "multiple_testing" })).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "multiple_testing" }));
    await waitFor(() => expect(screen.getByText(/слишком велик|too large/)).toBeTruthy());
  });

  it("отсутствие Stage 2 объясняется", async () => {
    vi.spyOn(api, "fetchRunSummary").mockRejectedValue(new Error("HTTP 409"));
    render(<RunSummaryView />);
    await waitFor(() => expect(screen.getByText(/только для вывода Stage 2|only for Stage 2/)).toBeTruthy());
  });

  it("прогон без ограничений сообщает об этом явно", async () => {
    vi.spyOn(api, "fetchRunSummary").mockResolvedValue({
      ...summary, categories: { I: { summary: {} } },
    });
    render(<RunSummaryView />);
    await waitFor(() => expect(screen.getByText(/не сообщил об ограничениях|reported no limitations/)).toBeTruthy());
  });
});
