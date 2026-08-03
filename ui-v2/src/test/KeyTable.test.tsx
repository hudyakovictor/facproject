import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KeyCategory, KeyGroup } from "../components/KeyTable";
import PairKeysPanel from "../components/PairKeysPanel";
import * as api from "../api";

afterEach(() => vi.restoreAllMocks());

describe("KeyGroup", () => {
  it("показывает отсутствие данных прочерком, а не скрывает строку", () => {
    render(<KeyGroup id="multiple_testing" values={{ mt_q_value: null, mt_role: "primary" }} />);
    expect(screen.getByText("q value")).toBeTruthy();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("счётчик отражает реальную заполненность", () => {
    render(<KeyGroup id="coverage" values={{ a: 1, b: null, c: null }} />);
    expect(screen.getByText("1/3")).toBeTruthy();
  });

  it("скрытие пустых подписывается явно", async () => {
    const user = userEvent.setup();
    render(<KeyGroup id="coverage" values={{ a: 1, b: null, c: null }} />);
    await user.click(screen.getByRole("button", { name: /СКРЫТЬ ПУСТЫЕ|HIDE EMPTY/ }));
    expect(screen.getByText(/скрыто без измерения: 2|hidden, not measured: 2/)).toBeTruthy();
  });

  it("переключатель скрытия не появляется, когда всё измерено", () => {
    render(<KeyGroup id="coverage" values={{ a: 1, b: 2 }} />);
    expect(screen.queryByRole("button", { name: /СКРЫТЬ ПУСТЫЕ|HIDE EMPTY/ })).toBeNull();
  });

  it("сворачивается по клику на заголовок", async () => {
    const user = userEvent.setup();
    render(<KeyGroup id="coverage" values={{ alpha_value: 1 }} />);
    const header = screen.getByRole("button", { expanded: true });
    await user.click(header);
    expect(screen.queryByText("alpha value")).toBeNull();
  });

  it("пустая группа не рендерится", () => {
    const { container } = render(<KeyGroup id="coverage" values={{}} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("KeyCategory", () => {
  it("суммирует заполненность по всем подгруппам", () => {
    render(<KeyCategory title="Тест" groups={{ g1: { a: 1, b: null }, g2: { c: 3 } }} />);
    expect(screen.getByText("2/3")).toBeTruthy();
  });
});

const metrics: api.PairMetrics = {
  schema: "s", not_a_verdict: true, source_mode: "research",
  photo_a: "A", photo_b: "B", reversed_order: false,
  column_count: 6, available_count: 5,
  category_titles: {
    A: { ru: "Статзначимость", en: "Statistical significance" },
    B: { ru: "Меш", en: "Mesh" },
  },
  categories: {
    A: {
      multiple_testing: { mt_q_value: 0.42, mt_significant_fdr10: false },
      limits: { calibration_limited: true, pose_leakage_limited: false },
      corroboration: { cross_bin_support_count: 0 },
    },
    B: { status: { mesh_status: "measured_uncalibrated" } },
  },
};

describe("PairKeysPanel", () => {
  it("предупреждает, когда расхождение не проходит FDR", async () => {
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByText(/FDR-10/)).toBeTruthy());
  });

  it("предупреждает об ограничении калибровки и отсутствии корроборации", async () => {
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByText(/калибровкой|calibration-limited/)).toBeTruthy());
    expect(screen.getByText(/не подтверждается|not corroborated/)).toBeTruthy();
  });

  it("не показывает предупреждение об утечке позы, когда её нет", async () => {
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByText(/FDR-10/)).toBeTruthy());
    expect(screen.queryByText(/коррелирует с позой|correlates with pose/)).toBeNull();
  });

  it("показывает честный охват колонок", async () => {
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByText(/5\/6/)).toBeTruthy());
  });

  it("вкладки строятся по категориям ответа", async () => {
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getAllByRole("tab")).toHaveLength(2));
  });

  it("переключение вкладки показывает другую категорию", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue(metrics);
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getAllByRole("tab")).toHaveLength(2));
    await user.click(screen.getByRole("tab", { name: /Меш|Mesh/ }));
    expect(screen.getByText("mesh status")).toBeTruthy();
  });

  it("отсутствие Stage 2 объясняется, а не выглядит поломкой", async () => {
    vi.spyOn(api, "fetchPairMetrics").mockRejectedValue(new Error("HTTP 409: нет Stage 2"));
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());
    expect(screen.getByText(/только для вывода Stage 2|only for Stage 2/)).toBeTruthy();
  });

  it("сетевая ошибка отличается от отсутствия данных", async () => {
    vi.spyOn(api, "fetchPairMetrics").mockRejectedValue(new Error("network down"));
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  });

  it("перевёрнутый порядок пары обозначается", async () => {
    vi.spyOn(api, "fetchPairMetrics").mockResolvedValue({ ...metrics, reversed_order: true });
    render(<PairKeysPanel photoA="A" photoB="B" />);
    await waitFor(() => expect(screen.getByText(/ПЕРЕВЁРНУТ|REVERSED/)).toBeTruthy());
  });
});
