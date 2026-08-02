import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { modalProps, useModal } from "../useModal";
import ProvenancePopup from "../components/ProvenancePopup";
import * as api from "../api";

afterEach(() => vi.restoreAllMocks());

/** Минимальный диалог на хуке — проверяем сам механизм, а не вёрстку. */
function Harness({ onClose }: { onClose: () => void }) {
  const ref = useModal<HTMLDivElement>(onClose);
  return (
    <div ref={ref} {...modalProps("Тестовый диалог")}>
      <button>первая</button>
      <button>вторая</button>
      <button>третья</button>
    </div>
  );
}

function App() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>открыть</button>
      <button>фоновая</button>
      {open && <Harness onClose={() => setOpen(false)} />}
    </>
  );
}

describe("useModal", () => {
  it("объявляет себя диалогом с именем", () => {
    render(<Harness onClose={() => undefined} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-label")).toBe("Тестовый диалог");
  });

  it("переводит фокус внутрь при открытии", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByText("открыть"));
    await waitFor(() => expect(document.activeElement?.textContent).toBe("первая"));
  });

  it("закрывается по Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Tab с последнего элемента возвращается на первый, а не уходит в фон", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByText("открыть"));
    await waitFor(() => expect(document.activeElement?.textContent).toBe("первая"));

    await user.tab();
    await user.tab();
    expect(document.activeElement?.textContent).toBe("третья");

    await user.tab();
    expect(document.activeElement?.textContent).toBe("первая");
  });

  it("Shift+Tab с первого элемента уходит на последний", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByText("открыть"));
    await waitFor(() => expect(document.activeElement?.textContent).toBe("первая"));

    await user.tab({ shift: true });
    expect(document.activeElement?.textContent).toBe("третья");
  });

  it("возвращает фокус на открывшую кнопку после закрытия", async () => {
    const user = userEvent.setup();
    render(<App />);
    const opener = screen.getByText("открыть");
    await user.click(opener);
    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());

    await user.keyboard("{Escape}");
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});

describe("ProvenancePopup", () => {
  it("является диалогом с именем кадра", async () => {
    vi.spyOn(api, "fetchPhotoInfoKeys").mockRejectedValue(new Error("HTTP 409"));
    render(<ProvenancePopup photoId="2001_01_10__p01" onClose={() => undefined} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-label")).toContain("2001_01_10__p01");
  });

  it("закрывается по Escape", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "fetchPhotoInfoKeys").mockRejectedValue(new Error("HTTP 409"));
    const onClose = vi.fn();
    render(<ProvenancePopup photoId="P1" onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
