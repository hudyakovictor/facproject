import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import SkinZonesPanel from "../components/SkinZonesPanel";
import * as api from "../api";

const report: api.SkinZoneReport = {
  schema: "s", not_a_verdict: true, source_mode: "research", photo_id: "P1",
  pose_bin: "frontal", skin_mask_coverage: 0.46,
  global_texture_quality: { status: "usable", texture_score_0_1: 0.92 },
  mask_quality: { status: "ok" },
  zone_count: 2, active_zone_count: 1, excluded_zone_count: 0, no_data_zone_count: 1,
  zones: [
    {
      zone_id: "Z01", name: "forehead_center", label_ru: "лоб центр", group: "forehead", side: "midline",
      status: "active", exclusion_reasons: [], visible_fraction: 0.98, skin_pixels: 29801,
      quality: 0.98, bbox_original: [1, 2, 3, 4], texture_score: 1, texture_usable: true,
      quality_class: "good", laplacian_var: 540.9, tenengrad_mean: 2366.3,
      highlight_fraction: 0, shadow_fraction: 0, skin_fraction: 1, texture_pixels: 34429,
      roi_source: "landmark_skin_fallback", wrinkle: null,
    },
    {
      zone_id: "Z02", name: "chin", label_ru: "подбородок", group: "chin", side: "midline",
      status: "no_data", exclusion_reasons: [], visible_fraction: null, skin_pixels: null,
      quality: null, bbox_original: null, texture_score: null, texture_usable: null,
      quality_class: null, laplacian_var: null, tenengrad_mean: null,
      highlight_fraction: null, shadow_fraction: null, skin_fraction: null,
      texture_pixels: null, roi_source: null, wrinkle: null,
    },
  ],
  available_sources: { skin_zone_quality: true, per_zone_quality: true, wrinkle_zones: false, wrinkle_note: null },
};

afterEach(() => vi.restoreAllMocks());

describe("SkinZonesPanel", () => {
  it("renders zones from Stage 1 artifacts", async () => {
    vi.spyOn(api, "fetchSkinZones").mockResolvedValue(report);
    render(<SkinZonesPanel photoId="P1" />);
    await waitFor(() => expect(screen.getByText("лоб центр")).toBeInTheDocument());
    expect(screen.getByText("подбородок")).toBeInTheDocument();
  });

  it("shows an em dash for missing values, never 0", async () => {
    vi.spyOn(api, "fetchSkinZones").mockResolvedValue(report);
    const { container } = render(<SkinZonesPanel photoId="P1" />);
    await waitFor(() => expect(screen.getByText("подбородок")).toBeInTheDocument());
    // Зона без данных не должна показывать числовой ноль как измерение.
    const row = screen.getByText("подбородок").closest("summary")!;
    expect(row.textContent).toContain("—");
    expect(row.textContent).not.toMatch(/0\.000/);
    expect(container.textContent).toContain("НЕТ ДАННЫХ");
  });

  it("explains unavailability instead of rendering synthetic numbers", async () => {
    vi.spyOn(api, "fetchSkinZones").mockRejectedValue(new Error("HTTP 409 demo mode"));
    render(<SkinZonesPanel photoId="P1" />);
    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    expect(screen.getByRole("status").textContent).toContain("Stage 1");
    expect(screen.getByRole("status").textContent).toContain("HTTP 409");
  });
});
