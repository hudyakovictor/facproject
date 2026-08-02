import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AlignmentDiagnostics, HeatmapLegend, MetricsTable, ZoneBreakdown } from "../components/ComparePanels";
import { DEFAULT_HEATMAP_STOPS } from "../components/MeshViewer";

const zones = [
  { zone: "x_center_center", status: "measured", point_count: 20, rmse: 0.0337, median: 0.031, p95: 0.054, signed_x: 0.0009, signed_y: -0.0203, signed_z: -0.0028 },
  { zone: "x_center_high", status: "insufficient_visibility", point_count: 3 },
  { zone: "x_center_low", status: "measured", point_count: 21, rmse: 0.0458, median: 0.038, p95: 0.070, signed_x: 0.0023, signed_y: -0.0077, signed_z: -0.0009 },
];

describe("comparison panels", () => {
  it("ranks zones by RMSE and shows signed shifts", () => {
    render(<ZoneBreakdown zones={zones} />);
    const rows = screen.getAllByRole("row").slice(1); // без заголовка
    // Худшая зона первой — аналитик видит, где расхождение сильнее всего.
    expect(rows[0].textContent).toContain("x_center_low");
    // Знак смещения сохраняется: -0.008 это направление, а не модуль.
    expect(rows[0].textContent).toContain("-0.008");
    expect(rows[1].textContent).toContain("+0.001");
  });

  it("lists visibility-excluded zones separately instead of hiding them", () => {
    render(<ZoneBreakdown zones={zones} />);
    expect(screen.getByText(/x_center_high \(3\)/)).toBeInTheDocument();
  });

  it("renders a numeric scale for the heatmap", () => {
    render(<HeatmapLegend stops={{ ...DEFAULT_HEATMAP_STOPS, maxReference: 0.12 }} />);
    // Крайние подписи шкалы: 0 и maxReference.
    expect(screen.getByText("0.000")).toBeInTheDocument();
    expect(screen.getByText("0.120")).toBeInTheDocument();
  });

  it("surfaces alignment quality so the number can be judged", () => {
    render(<AlignmentDiagnostics diagnostics={{
      coverage134: 1.0, common_visible134: 134, anchor134_count: 47,
      anchor134_policy: "central_quantile_anchor_v1", alignment134_trimmed_count: 7,
      alignment134_residual_before_median: 0.0337, alignment134_residual_after_median: 0.0338,
      pose_distance: 0.0765,
    }} />);
    expect(screen.getByText(/47 · central_quantile_anchor_v1/)).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("labels metrics in human terms instead of dumping raw keys", () => {
    render(<MetricsTable metrics={{ ldm134_rmse: 0.045309, alpha_exp_l2: 0.56687 }} />);
    expect(screen.getByText(/RMSE 134 точек/)).toBeInTheDocument();
    // Мимика явно отделена от идентичности.
    expect(screen.getByText(/мимика, не идентичность/)).toBeInTheDocument();
    expect(screen.getByText("0.0453")).toBeInTheDocument();
  });

  it("explains an empty metric set rather than rendering a blank block", () => {
    render(<MetricsTable metrics={{}} />);
    expect(screen.getByText(/Метрики недоступны/)).toBeInTheDocument();
  });
});
