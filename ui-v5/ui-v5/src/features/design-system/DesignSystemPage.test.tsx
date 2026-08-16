import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import DesignSystemPage from "./DesignSystemPage";

describe("DesignSystemPage", () => {
  it("documents the core forensic states and timeline grammar", () => {
    render(<DesignSystemPage />);
    expect(screen.getByRole("heading", { name: "Грамматика таймлайна" })).toBeInTheDocument();
    expect(screen.getAllByText("Candidate").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/ДАННЫЕ · НЕ ВЕРДИКТ/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Photo point")).toBeInTheDocument();
    expect(screen.getByText("Pair bridge")).toBeInTheDocument();
  });

  it("toggles the density mode", async () => {
    const user = userEvent.setup();
    render(<DesignSystemPage />);
    await user.click(screen.getByRole("button", { name: /Compact/i }));
    expect(document.documentElement.dataset.density).toBe("compact");
  });

  it("opens the preview dialog", async () => {
    const user = userEvent.setup();
    render(<DesignSystemPage />);
    await user.click(screen.getByRole("button", { name: /Открыть dialog/i }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Stage 1 не изменяется/i)).toBeInTheDocument();
  });
});
