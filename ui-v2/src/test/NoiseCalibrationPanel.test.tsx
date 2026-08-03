import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import NoiseCalibrationPanel from "../components/NoiseCalibrationPanel";
import * as api from "../api";

const model: api.NoiseModelInfo = {
  schema: "s", tolerance: { yaw: 2, pitch: 1, roll: 1 },
  index_size: 924, pairs_per_pose_bin: { frontal: 100 },
  coverage: {
    pair_count: 29, compensated_count: 20, coverage: 20 / 29,
    uncompensated_reasons: { "нет калибровочной пары в допусках по углам": 9 },
    median_noise_removed: 0.0123,
  },
  note: "n",
};

const preview: api.NoiseSubtractionResult = {
  schema: "s", status: "measured", source_mode: "demo",
  tolerance: { yaw: 2, pitch: 1, roll: 1 },
  angle_delta: { yaw: 0, pitch: 3.76, roll: 0.86 },
  uncompensated: false, degenerate_match: false, reason: "",
  match: { dataset_id: "carrier_0", record_a: "R1", record_b: "R2", delta: {}, match_distance: 0.12 },
  metrics: { ldm134_rmse: { raw: 0.0466, noise: 0.0301, compensated: 0.0165 } },
};

afterEach(() => vi.restoreAllMocks());

describe("NoiseCalibrationPanel", () => {
  it("shows compensation coverage so the mode toggle is not misleading", async () => {
    vi.spyOn(api, "fetchNoiseModel").mockResolvedValue(model);
    render(<NoiseCalibrationPanel />);
    await waitFor(() => expect(screen.getByText(/20 из 29/)).toBeInTheDocument());
    expect(screen.getByText("924")).toBeInTheDocument();
  });

  it("lists why compensation was rejected instead of hiding it", async () => {
    vi.spyOn(api, "fetchNoiseModel").mockResolvedValue(model);
    render(<NoiseCalibrationPanel />);
    await waitFor(() =>
      expect(screen.getByText(/нет калибровочной пары в допусках/)).toBeInTheDocument());
  });

  it("warns that a drop after compensation is not proof of no anomaly", async () => {
    vi.spyOn(api, "fetchNoiseModel").mockResolvedValue(model);
    render(<NoiseCalibrationPanel />);
    expect(screen.getByText(/НЕ является доказательством отсутствия аномалии/)).toBeInTheDocument();
  });

  it("shows raw and compensated values side by side", async () => {
    vi.spyOn(api, "fetchNoiseModel").mockResolvedValue(model);
    vi.spyOn(api, "subtractAngleNoise").mockResolvedValue(preview);
    render(<NoiseCalibrationPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByText("0.04660")).toBeInTheDocument());
    expect(screen.getByText("0.01650")).toBeInTheDocument();   // компенсированное
    expect(screen.getByText("0.03010")).toBeInTheDocument();   // сам шум
  });

  it("flags a degenerate match as a calibration defect, not 'no difference'", async () => {
    vi.spyOn(api, "fetchNoiseModel").mockResolvedValue(model);
    vi.spyOn(api, "subtractAngleNoise").mockResolvedValue({
      ...preview, degenerate_match: true,
      metrics: { ldm134_rmse: { raw: 0.0466, noise: 0.0481, compensated: 0 } },
    });
    render(<NoiseCalibrationPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert").textContent).toContain("Вырожденный подбор");
    expect(screen.getByRole("alert").textContent).toContain("не отсутствия различий");
  });

  it("reports an unapplied compensation with its reason", async () => {
    vi.spyOn(api, "fetchNoiseModel").mockResolvedValue(model);
    vi.spyOn(api, "subtractAngleNoise").mockResolvedValue({
      ...preview, uncompensated: true, reason: "нет калибровочной пары в допусках по углам",
      match: null, metrics: { ldm134_rmse: { raw: 0.0466, noise: null, compensated: null } },
    });
    render(<NoiseCalibrationPanel photoA="A" photoB="B" />);
    await waitFor(() =>
      expect(screen.getByText(/Компенсация не применена/)).toBeInTheDocument());
  });

  it("exposes tolerance sliders for all three axes", async () => {
    vi.spyOn(api, "fetchNoiseModel").mockResolvedValue(model);
    render(<NoiseCalibrationPanel />);
    expect(screen.getByLabelText(/Δyaw/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Δpitch/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Δroll/)).toBeInTheDocument();
  });
});
