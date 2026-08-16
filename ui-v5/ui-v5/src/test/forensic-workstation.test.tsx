import { describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TimelinePage } from "../features/timeline/TimelinePage";
import { ClusteringPage } from "../features/clustering/ClusteringPage";
import { ArticlesPage } from "../features/articles/ArticlesPage";

const timeline = { source_mode: "research", not_a_verdict: true, photos: [{ id: "photo_001", date: "2020-01-01", t: 1577836800000, bucket: "frontal", era: "2020", quality: 0.8, yaw: 0, pitch: 0, roll: 0, fuzzy: "", evidenceState: "available", measurementStatus: "complete", flags: [], stage2PairCount: 2, stage2StatusCounts: {}, stage2EvidenceCounts: {}, sourceMode: "research", analysisStage: "stage2" }], era_meta: {} };
const summary = { source_mode: "research", not_a_verdict: true, technical_summary: { change_point_count: 1, status_counts: {}, evidence_state_counts: {} } };

vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
  const body = String(input).includes("run/summary") ? summary : timeline;
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}));

function renderWithApi(ui: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>);
}

describe("v5 real-data UI contract", () => {
  test("timeline renders API-backed observation", async () => {
    const { container } = renderWithApi(<TimelinePage />);
    await waitFor(() => expect(screen.getByRole("button", { name: /Кадр 2020-01-01/ })).toBeInTheDocument());
    expect(container.querySelector('img[src*="photo_001"]')).toBeInTheDocument();
  });

  test("clustering does not invent cluster verdicts", async () => {
    renderWithApi(<ClusteringPage />);
    await waitFor(() => expect(screen.getByText(/РЕАЛЬНЫЕ НАБЛЮДЕНИЯ/i)).toBeInTheDocument());
    expect(screen.getByText(/не подменяются демонстрационными/i)).toBeInTheDocument();
  });

  test("articles page states the current API boundaries", async () => {
    renderWithApi(<ArticlesPage />);
    await waitFor(() => expect(screen.getByText(/МАТЕРИАЛЫ ПО ИССЛЕДОВАТЕЛЬСКОМУ ЗАПУСКУ/i)).toBeInTheDocument());
    expect(screen.getByText(/SNR, гипотезами, хешами/i)).toBeInTheDocument();
  });
});
