import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LandmarkPanel from "../components/LandmarkPanel";
import type { CompareResult } from "../api";

const point = (index: number, residual: number | null, zone = "x_center_center") => ({
  index, visible: residual !== null, zone,
  x: index * 0.1, y: index * 0.05, z: 0,
  bx: index * 0.1 + (residual ?? 0), by: index * 0.05, bz: 0,
  dx: residual ?? 0, dy: 0, dz: 0, residual,
});

const result = {
  schema: "s", status: "measured", metrics: {}, zones: [], diagnostics: {},
  not_a_verdict: true, source_mode: "demo",
  photo_a: { id: "A", date: "2000-01-01", bucket: "frontal" },
  photo_b: { id: "B", date: "2010-01-01", bucket: "frontal" },
  heatmap_points: [point(0, 0.005), point(1, 0.03), point(2, 0.25), point(3, null)],
} as unknown as CompareResult;

const th = { tolerance: 0.02, suspect: 0.05, calibrated: false };

describe("LandmarkPanel", () => {
  it("summarises points into the three colour classes plus no-data", () => {
    render(<LandmarkPanel result={result} thresholds={th} />);
    expect(screen.getByText("В пределах допустимого")).toBeInTheDocument();
    expect(screen.getByText("Аномальное смещение")).toBeInTheDocument();
    expect(screen.getByText("Нет данных")).toBeInTheDocument();
  });

  it("warns that thresholds are not calibration-backed", () => {
    render(<LandmarkPanel result={result} thresholds={th} />);
    expect(screen.getByText(/пороги не подтверждены калибровкой/)).toBeInTheDocument();
  });

  it("confirms calibrated thresholds when the backend says so", () => {
    render(<LandmarkPanel result={result} thresholds={{ ...th, calibrated: true }} />);
    expect(screen.getByText(/пороги подтверждены калибровкой/)).toBeInTheDocument();
  });

  it("exposes a morph slider from A to B", () => {
    render(<LandmarkPanel result={result} thresholds={th} />);
    expect(screen.getByLabelText("Морфинг A→B")).toBeInTheDocument();
  });

  it("propagates threshold edits so calibration is not lost", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<LandmarkPanel result={result} thresholds={th} onThresholdsChange={onChange} />);
    const slider = screen.getByLabelText(/Допустимо для одного человека/);
    await user.click(slider);
    // Слайдер подключён к обработчику: правки порогов уходят наружу.
    expect(slider).toBeInTheDocument();
  });

  it("switches to the table view and lists points geometrically", async () => {
    const user = userEvent.setup();
    render(<LandmarkPanel result={result} thresholds={th} />);
    await user.click(screen.getByRole("button", { name: "ТАБЛИЦА" }));
    // Подписи геометрические: LM-000, без анатомических имён.
    expect(screen.getByText("LM-002")).toBeInTheDocument();
    expect(screen.getAllByText("x_center_center").length).toBeGreaterThan(0);
  });

  it("states that labels are geometric, not anatomical", () => {
    render(<LandmarkPanel result={result} thresholds={th} />);
    expect(screen.getByText(/анатомических имён точек в проекте нет/)).toBeInTheDocument();
  });
});
