import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingsModal from "../components/SettingsModal";
import * as api from "../api";

afterEach(() => vi.restoreAllMocks());

const SAMPLE_SETTINGS: api.AppSettings = {
  schema: "deeputin-api-settings-v1.0",
  heatmap: { stop_blue_cyan: 0.25, stop_cyan_green: 0.5, stop_green_red: 0.75, stop_saturated_red: 1.0, max_residual_reference: 0.12 },
  thresholds: { confidence_min: 0, quality_min: 0, geometry_zone_delta_limit: 0.018, texture_zone_delta_limit: 0.04, expression_smile: 0.92, expression_jaw_open: 0.28 },
  detail_level: "standard",
  language: "ru",
};

describe("SettingsModal", () => {
  it("loads settings from the API and renders heatmap thresholds", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(SAMPLE_SETTINGS);
    render(<SettingsModal onClose={() => undefined} onApplied={() => undefined} />);

    await waitFor(() => expect(screen.getByText(/25%/)).toBeInTheDocument());
  });

  it("shows an error banner when the API is unreachable, not a silent blank screen", async () => {
    vi.spyOn(api, "fetchSettings").mockRejectedValue(new Error("connection refused"));
    render(<SettingsModal onClose={() => undefined} onApplied={() => undefined} />);

    await waitFor(() => expect(screen.getByText(/connection refused/)).toBeInTheDocument());
  });

  it("calls onApplied with the saved settings after clicking apply", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(SAMPLE_SETTINGS);
    const saveSpy = vi.spyOn(api, "saveSettings").mockResolvedValue({ ...SAMPLE_SETTINGS, heatmap: { ...SAMPLE_SETTINGS.heatmap, stop_blue_cyan: 0.4 } });
    const onApplied = vi.fn();
    const user = userEvent.setup();

    render(<SettingsModal onClose={() => undefined} onApplied={onApplied} />);
    await waitFor(() => expect(screen.getByText(/25%/)).toBeInTheDocument());

    const applyButton = await screen.findByRole("button", { name: /ПРИМЕНИТЬ И СОХРАНИТЬ/i });
    await user.click(applyButton);

    await waitFor(() => expect(saveSpy).toHaveBeenCalled());
    await waitFor(() => expect(onApplied).toHaveBeenCalledWith(expect.objectContaining({ heatmap: expect.objectContaining({ stop_blue_cyan: 0.4 }) })));
  });

  it("calls onClose when the close button is clicked", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(SAMPLE_SETTINGS);
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<SettingsModal onClose={onClose} onApplied={() => undefined} />);
    await waitFor(() => expect(screen.getByText(/25%/)).toBeInTheDocument());

    const closeButtons = screen.getAllByRole("button");
    await user.click(closeButtons[0]);
    expect(onClose).toHaveBeenCalled();
  });
});
