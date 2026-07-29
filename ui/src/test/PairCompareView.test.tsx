import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PairCompareView from "../components/PairCompareView";
import * as api from "../api";
import type { Photo } from "../data";

// jsdom has no WebGL context, so the real three.js MeshViewer would throw.
// These tests exercise data flow (which API calls happen, in what order),
// not 3D rendering — that's covered by manual/production verification and
// the pure-function heatColor tests. Mocking here keeps the test honest
// about what it verifies instead of silently disabling WebGL globally.
vi.mock("../components/MeshViewer", () => ({
  default: () => null,
  heatColor: vi.fn(),
  DEFAULT_HEATMAP_STOPS: { blueCyan: 0.25, cyanGreen: 0.5, greenRed: 0.75, saturatedRed: 1, maxReference: 0.12 },
}));

afterEach(() => vi.restoreAllMocks());


function samplePhoto(id: string, bucket: Photo["bucket"]): Photo {
  return {
    id, date: "1999-01-01", t: 0, era: "ERA_1_BASELINE", bucket, quality: 0.8, hidden: false,
    boneScore: 0.8, orbit: 0.8, chin: 0.8, jaw: 0.8, cheek: 0.8, symmetry: 0.8, yaw: 0,
    siliconeProb: 0.1, specular: 0.2, lbpEntropy: 0.5, frangi: 0.3, wrinkle: 0.3, subsurface: 0.4,
    visualAge: 45, calendarAge: 45, p0: 0.8, p1: 0.1, p2: 0.1, dominant: "H0", fuzzy: "CONSISTENT",
    confidence: 0.9, flags: [], exifAnomaly: false, zOrbitDepth: 0, zChinProj: 0, zJawWidth: 0, zCheek: 0,
  };
}

describe("PairCompareView", () => {
  it("renders photo selectors and a compare button", async () => {
    const photos = [samplePhoto("A1", "frontal"), samplePhoto("A2", "frontal")];
    vi.spyOn(api, "fetchSettings").mockResolvedValue({
      schema: "s", heatmap: { stop_blue_cyan: 0.25, stop_cyan_green: 0.5, stop_green_red: 0.75, stop_saturated_red: 1, max_residual_reference: 0.12 },
      thresholds: { confidence_min: 0, quality_min: 0, geometry_zone_delta_limit: 0.018, texture_zone_delta_limit: 0.04, expression_smile: 0.92, expression_jaw_open: 0.28 },
      detail_level: "standard", language: "ru",
    });
    render(<PairCompareView photos={photos} />);
    expect(screen.getByRole("button", { name: /СРАВНИТЬ/i })).toBeInTheDocument();
    await waitFor(() => expect(api.fetchSettings).toHaveBeenCalled());
  });


  it("shows an honest pose-mismatch warning instead of fabricating a result", async () => {
    const photos = [samplePhoto("A1", "frontal"), samplePhoto("B1", "left_profile")];
    vi.spyOn(api, "fetchSettings").mockResolvedValue({
      schema: "s", heatmap: { stop_blue_cyan: 0.25, stop_cyan_green: 0.5, stop_green_red: 0.75, stop_saturated_red: 1, max_residual_reference: 0.12 },
      thresholds: { confidence_min: 0, quality_min: 0, geometry_zone_delta_limit: 0.018, texture_zone_delta_limit: 0.04, expression_smile: 0.92, expression_jaw_open: 0.28 },
      detail_level: "standard", language: "ru",
    });
    vi.spyOn(api, "comparePhotos").mockResolvedValue({
      schema: "s", status: "pose_mismatch", metrics: {}, zones: [], diagnostics: {}, not_a_verdict: true,
      heatmap_points: [], source_mode: "demo",
      photo_a: { id: "A1", date: "1999-01-01", bucket: "frontal" },
      photo_b: { id: "B1", date: "1999-01-01", bucket: "left_profile" },
    });

    const user = userEvent.setup();
    render(<PairCompareView photos={photos} />);
    await user.click(screen.getByRole("button", { name: /СРАВНИТЬ/i }));

    await waitFor(() => expect(screen.getByText(/Pазные ракурсы|Разные ракурсы/)).toBeInTheDocument());
  });

  it("fetches the full BFM mesh only when the toggle is enabled", async () => {
    const photos = [samplePhoto("A1", "frontal"), samplePhoto("A2", "frontal")];
    vi.spyOn(api, "fetchSettings").mockResolvedValue({
      schema: "s", heatmap: { stop_blue_cyan: 0.25, stop_cyan_green: 0.5, stop_green_red: 0.75, stop_saturated_red: 1, max_residual_reference: 0.12 },
      thresholds: { confidence_min: 0, quality_min: 0, geometry_zone_delta_limit: 0.018, texture_zone_delta_limit: 0.04, expression_smile: 0.92, expression_jaw_open: 0.28 },
      detail_level: "standard", language: "ru",
    });
    vi.spyOn(api, "comparePhotos").mockResolvedValue({
      schema: "s", status: "measured", metrics: { ldm134_rmse: 0.01 }, zones: [], diagnostics: {}, not_a_verdict: true,
      heatmap_points: [{ index: 0, x: 0, y: 0, z: 0, residual: 0.01 }],
      heatmap_stats: { min: 0, max: 0.01, median: 0.005, p95: 0.009 },
      source_mode: "demo",
      photo_a: { id: "A1", date: "1999-01-01", bucket: "frontal" },
      photo_b: { id: "A2", date: "1999-01-01", bucket: "frontal" },
    });
    const fullMeshSpy = vi.spyOn(api, "comparePhotosFullMesh").mockResolvedValue({
      schema: "s-full-mesh", vertex_count: 4, triangle_count: 1,
      vertices_a: [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
      vertices_b_aligned: [[0.1, 0, 0], [1.1, 0, 0], [0.1, 1, 0], [0.1, 0, 1]],
      residuals: [0.01, 0.02, 0.03, 0.04],
      triangles: [[0, 1, 2]],
      primary_zone_ids: ["A01"], primary_zone_names: ["forehead_left"], primary_triangle_zone: [0],
      residual_stats: { min: 0.01, max: 0.04, median: 0.025, p95: 0.038 },
      not_a_verdict: true, note: "test", source_mode: "demo",
      photo_a: { id: "A1", date: "1999-01-01", bucket: "frontal" },
      photo_b: { id: "A2", date: "1999-01-01", bucket: "frontal" },
    });

    const user = userEvent.setup();
    render(<PairCompareView photos={photos} />);

    // Without the toggle, full mesh must not be requested.
    await user.click(screen.getByRole("button", { name: /СРАВНИТЬ/i }));
    await waitFor(() => expect(api.comparePhotos).toHaveBeenCalled());
    expect(fullMeshSpy).not.toHaveBeenCalled();

    // With the toggle enabled, full mesh must be requested.
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /СРАВНИТЬ/i }));
    await waitFor(() => expect(fullMeshSpy).toHaveBeenCalledWith("A1", "A2"));

    // The morph slider must appear once the full mesh result is available.
    await waitFor(() => expect(screen.getByRole("slider")).toBeInTheDocument());
  });

  it("shows calibration match candidates after a successful comparison", async () => {
    const photos = [samplePhoto("A1", "frontal"), samplePhoto("A2", "frontal")];
    vi.spyOn(api, "fetchSettings").mockResolvedValue({
      schema: "s", heatmap: { stop_blue_cyan: 0.25, stop_cyan_green: 0.5, stop_green_red: 0.75, stop_saturated_red: 1, max_residual_reference: 0.12 },
      thresholds: { confidence_min: 0, quality_min: 0, geometry_zone_delta_limit: 0.018, texture_zone_delta_limit: 0.04, expression_smile: 0.92, expression_jaw_open: 0.28 },
      detail_level: "standard", language: "ru",
    });
    vi.spyOn(api, "comparePhotos").mockResolvedValue({
      schema: "s", status: "measured", metrics: { ldm134_rmse: 0.01 }, zones: [], diagnostics: {}, not_a_verdict: true,
      heatmap_points: [{ index: 0, x: 0, y: 0, z: 0, residual: 0.01 }],
      heatmap_stats: { min: 0, max: 0.01, median: 0.005, p95: 0.009 },
      source_mode: "demo",
      photo_a: { id: "A1", date: "1999-01-01", bucket: "frontal" },
      photo_b: { id: "A2", date: "1999-01-01", bucket: "frontal" },
    });
    vi.spyOn(api, "fetchCalibrationMatchForPhoto").mockImplementation(async (photoId: string) => ({
      schema: "s", not_a_verdict: true, query: { yaw: 0, pitch: 0, roll: 0, pose_bin: "frontal" },
      candidate_count: 1,
      candidates: [{ dataset_id: "person_01", record_id: `frame_for_${photoId}`, pose_bin: "frontal", yaw: 0, pitch: 0, roll: 0, angle_distance: 0.5, source_filename: "x.jpg" }],
      note: "test",
    }));

    const user = userEvent.setup();
    render(<PairCompareView photos={photos} />);
    await user.click(screen.getByRole("button", { name: /СРАВНИТЬ/i }));

    await waitFor(() => expect(screen.getByText(/frame_for_A1/)).toBeInTheDocument());
    expect(screen.getByText(/frame_for_A2/)).toBeInTheDocument();
  });
});
