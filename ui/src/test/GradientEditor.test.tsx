import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GradientEditor from "../components/GradientEditor";
import { DEFAULT_GRADIENT, evaluateGradient, toHex } from "../gradient";

describe("GradientEditor", () => {
  it("renders one row per stop with colour and position controls", () => {
    render(<GradientEditor model={DEFAULT_GRADIENT} onChange={() => undefined} />);
    expect(screen.getByText(/ОСТАНОВКИ · 5/)).toBeInTheDocument();
    expect(screen.getByLabelText("позиция 1")).toBeInTheDocument();
    expect(screen.getByLabelText("цвет 1")).toBeInTheDocument();
  });

  it("offers sharpness for every segment except the last stop", () => {
    render(<GradientEditor model={DEFAULT_GRADIENT} onChange={() => undefined} />);
    // 5 остановок → 4 перехода.
    expect(screen.getByLabelText("резкость 1")).toBeInTheDocument();
    expect(screen.getByLabelText("резкость 4")).toBeInTheDocument();
    expect(screen.queryByLabelText("резкость 5")).toBeNull();
  });

  it("adds a stop into the widest gap without stacking points", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    const sparse = { maxReference: 1, stops: [
      { position: 0, color: "#000000", sharpness: 0 },
      { position: 0.1, color: "#111111", sharpness: 0 },
      { position: 1, color: "#ffffff", sharpness: 0 },
    ]};
    render(<GradientEditor model={sparse} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /Добавить/ }));
    const next = onChange.mock.calls[0][0];
    // Новая точка попала в разрыв 0.1..1, а не в 0..0.1.
    expect(next.stops.some((s: { position: number }) =>
      s.position > 0.3 && s.position < 0.8)).toBe(true);
  });

  it("refuses to drop below two stops", () => {
    const onChange = vi.fn();
    const minimal = { maxReference: 1, stops: [
      { position: 0, color: "#000000", sharpness: 0 },
      { position: 1, color: "#ffffff", sharpness: 0 },
    ]};
    render(<GradientEditor model={minimal} onChange={onChange} />);
    const buttons = screen.getAllByLabelText("Удалить остановку");
    expect(buttons[0]).toBeDisabled();
  });

  it("shows the metric value for each stop, not just a 0..1 position", () => {
    render(<GradientEditor model={{ ...DEFAULT_GRADIENT, maxReference: 0.2 }}
      onChange={() => undefined} />);
    // Остановка на 0.5 при maxReference 0.2 = значение 0.1
    expect(screen.getByText("0.1000")).toBeInTheDocument();
  });

  it("renders external threshold marks on the preview scale", () => {
    const { container } = render(
      <GradientEditor model={DEFAULT_GRADIENT} onChange={() => undefined}
        marks={[{ value: 0.06, label: "порог", color: "#ff0000" }]} />);
    expect(container.querySelector('[title^="порог"]')).toBeTruthy();
  });

  it("applies a preset while preserving the current scale top", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<GradientEditor model={{ ...DEFAULT_GRADIENT, maxReference: 0.33 }}
      onChange={onChange} />);
    await user.selectOptions(screen.getByLabelText("Пресет"), "hardThreshold");
    const next = onChange.mock.calls[0][0];
    expect(next.maxReference).toBe(0.33);
    // Жёсткий пресет содержит ступенчатый переход.
    expect(next.stops.some((s: { sharpness: number }) => s.sharpness >= 0.9)).toBe(true);
  });

  it("preview colours match what the mesh renderer will produce", () => {
    // Ключевой инвариант: редактор и раскраска меша используют одну функцию,
    // иначе настройка не соответствовала бы результату.
    const model = DEFAULT_GRADIENT;
    expect(toHex(evaluateGradient(model, 0))).toBe(model.stops[0].color);
    expect(toHex(evaluateGradient(model, 1))).toBe(model.stops[model.stops.length - 1].color);
  });
});
