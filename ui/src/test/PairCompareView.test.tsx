import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PairCompareView from "../components/PairCompareView";
import * as api from "../api";
import type { Photo } from "../data";

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
});
