import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import {
  DEFAULT_THRESHOLDS, DETAIL_LEVELS, SettingsProvider, isVisibleAt, useDetailLevel, useThresholds,
} from "../settings";
import PairKeysPanel from "../components/PairKeysPanel";
import * as api from "../api";

afterEach(() => vi.restoreAllMocks());

const settings = (overrides: Partial<api.AppSettings> = {}): api.AppSettings => ({
  schema: "s",
  heatmap: {
    stop_blue_cyan: 0.25, stop_cyan_green: 0.5, stop_green_red: 0.75,
    stop_saturated_red: 1, max_residual_reference: 0.12,
  },
  thresholds: { ...DEFAULT_THRESHOLDS },
  detail_level: "standard",
  language: "ru",
  ...overrides,
});

function Probe() {
  const thresholds = useThresholds();
  const level = useDetailLevel();
  return (
    <div>
      <span data-testid="geom">{thresholds.geometry_zone_delta_limit}</span>
      <span data-testid="quality">{thresholds.quality_min}</span>
      <span data-testid="level">{level}</span>
    </div>
  );
}

describe("контракт значений по умолчанию", () => {
  it("дефолты совпадают с контрактом backend", () => {
    // Значения продублированы в UI как fallback при недоступном backend.
    // Расхождение означало бы, что интерфейс молча считает по другим
    // порогам, чем пайплайн, — см. app6/api/settings.DEFAULT_SETTINGS.
    expect(DEFAULT_THRESHOLDS).toEqual({
      confidence_min: 0,
      quality_min: 0,
      geometry_zone_delta_limit: 0.018,
      texture_zone_delta_limit: 0.04,
      expression_smile: 0.92,
      expression_jaw_open: 0.28,
    });
  });

  it("три уровня детализации по возрастанию", () => {
    expect(DETAIL_LEVELS).toEqual(["simple", "standard", "expert"]);
  });
});

describe("isVisibleAt", () => {
  it("простой блок виден на всех уровнях", () => {
    for (const level of DETAIL_LEVELS) expect(isVisibleAt("simple", level)).toBe(true);
  });

  it("экспертный блок виден только на экспертном уровне", () => {
    expect(isVisibleAt("expert", "simple")).toBe(false);
    expect(isVisibleAt("expert", "standard")).toBe(false);
    expect(isVisibleAt("expert", "expert")).toBe(true);
  });
});

describe("SettingsProvider", () => {
  it("раздаёт пороги с backend", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(settings({
      thresholds: { ...DEFAULT_THRESHOLDS, geometry_zone_delta_limit: 0.005 },
    }));
    render(<SettingsProvider><Probe /></SettingsProvider>);
    await waitFor(() => expect(screen.getByTestId("geom").textContent).toBe("0.005"));
  });

  it("при недоступном backend работает на встроенных значениях", async () => {
    vi.spyOn(api, "fetchSettings").mockRejectedValue(new Error("offline"));
    render(<SettingsProvider><Probe /></SettingsProvider>);
    await waitFor(() => expect(screen.getByTestId("geom").textContent).toBe("0.018"));
  });

  it("нулевой порог сохраняется, а не подменяется дефолтом", async () => {
    // 0 означает «не фильтровать» — это осознанный выбор пользователя.
    // Наивное `value || default` превратило бы его в 0.35.
    vi.spyOn(api, "fetchSettings").mockResolvedValue(settings({
      thresholds: { ...DEFAULT_THRESHOLDS, quality_min: 0 },
    }));
    render(<SettingsProvider><Probe /></SettingsProvider>);
    await waitFor(() => expect(screen.getByTestId("quality").textContent).toBe("0"));
  });

  it("некорректный detail_level нормализуется в standard", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(
      settings({ detail_level: "bogus" }));
    render(<SettingsProvider><Probe /></SettingsProvider>);
    await waitFor(() => expect(screen.getByTestId("level").textContent).toBe("standard"));
  });

  it("нечисловой порог заменяется встроенным значением", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(settings({
      thresholds: { ...DEFAULT_THRESHOLDS, geometry_zone_delta_limit: Number.NaN },
    }));
    render(<SettingsProvider><Probe /></SettingsProvider>);
    await waitFor(() => expect(screen.getByTestId("geom").textContent).toBe("0.018"));
  });
});

const metrics: api.PairMetrics = {
  schema: "s", not_a_verdict: true, source_mode: "research",
  photo_a: "A", photo_b: "B", reversed_order: false,
  column_count: 4, available_count: 4,
  category_titles: {
    A: { ru: "Статзначимость", en: "Significance" },
    B: { ru: "Меш", en: "Mesh" },
    G: { ru: "Провенанс", en: "Provenance" },
  },
  categories: {
    A: { multiple_testing: { mt_q_value: 0.4 } },
    B: { status: { mesh_status: "ok" } },
    G: { source: { source_digest_a: "abc" } },
  },
};

describe("detail_level управляет составом вкладок", () => {
  it("простой уровень скрывает меш и провенанс", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(settings({ detail_level: "simple" }));
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<SettingsProvider><PairKeysPanel photoA="A" photoB="B" /></SettingsProvider>);
    await waitFor(() => expect(screen.getAllByRole("tab")).toHaveLength(1));
    expect(screen.queryByRole("tab", { name: /Меш|Mesh/ })).toBeNull();
  });

  it("стандартный уровень показывает меш, но не провенанс", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(settings({ detail_level: "standard" }));
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<SettingsProvider><PairKeysPanel photoA="A" photoB="B" /></SettingsProvider>);
    await waitFor(() => expect(screen.getAllByRole("tab")).toHaveLength(2));
    expect(screen.queryByRole("tab", { name: /Провенанс|Provenance/ })).toBeNull();
  });

  it("экспертный уровень показывает все категории", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(settings({ detail_level: "expert" }));
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<SettingsProvider><PairKeysPanel photoA="A" photoB="B" /></SettingsProvider>);
    await waitFor(() => expect(screen.getAllByRole("tab")).toHaveLength(3));
  });
});

describe("пороги влияют на сравнение диапазонов", () => {
  it("ComparisonPanel берёт лимит из настроек, а не из константы", async () => {
    const { default: ComparisonPanel } = await import("../components/ComparisonPanel");
    const { buildDemoPhotos } = await import("../demoData");
    const DEMO_PHOTOS = buildDemoPhotos();
    vi.spyOn(api, "fetchSettings").mockResolvedValue(settings({
      thresholds: { ...DEFAULT_THRESHOLDS, geometry_zone_delta_limit: 0.123 },
    }));
    const range = { t0: 0, t1: 1, photos: DEMO_PHOTOS.slice(0, 5) };
    render(
      <SettingsProvider>
        <ComparisonPanel rangeA={range} rangeB={{ ...range, photos: DEMO_PHOTOS.slice(5, 10) }}
          onClose={() => undefined} onSetSide={() => undefined} activeSide="A" />
      </SettingsProvider>);
    await waitFor(() => expect(screen.getAllByText("±0.123").length).toBeGreaterThan(0));
  });
});
