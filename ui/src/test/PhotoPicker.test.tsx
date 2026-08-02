import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PhotoPicker from "../components/PhotoPicker";
import { type Photo } from "../data";
import { buildDemoPhotos } from "../demoData";

/** Демо-набор как тестовая фикстура: генератор вынесен из основного
 * бандла (аудит №27), поэтому строим его явно. */
const DEMO_PHOTOS = buildDemoPhotos();

const many: Photo[] = Array.from({ length: 1700 }, (_, i) => ({
  ...DEMO_PHOTOS[i % DEMO_PHOTOS.length],
  id: `P${String(i).padStart(4, "0")}`,
  date: `20${String(10 + (i % 15)).padStart(2, "0")}-01-01`,
}));

describe("PhotoPicker", () => {
  it("reports the full archive size, not just the visible page", () => {
    render(<PhotoPicker photos={many} value={many[0].id} onChange={() => undefined} label="A" />);
    // Раньше .slice(0,500) молча скрывал 1200 кадров.
    expect(screen.getByText(/из 1700/)).toBeInTheDocument();
  });

  it("warns that the list is truncated and by how much", () => {
    render(<PhotoPicker photos={many} value={many[0].id} onChange={() => undefined} label="A" />);
    expect(screen.getByText(/Список усечён/)).toBeInTheDocument();
    expect(screen.getByText(/\+1500/)).toBeInTheDocument();
  });

  it("filters by query so distant photos become reachable", async () => {
    const user = userEvent.setup();
    render(<PhotoPicker photos={many} value={many[0].id} onChange={() => undefined} label="A" />);
    await user.type(screen.getByLabelText(/Поиск по ID/), "P1699");
    expect(screen.getByRole("option", { name: /P1699/ })).toBeInTheDocument();
  });

  it("always keeps the selected photo present even if it is off-page", () => {
    // Выбран кадр за пределами первой страницы — select обязан его показать,
    // иначе отобразилось бы чужое значение.
    render(<PhotoPicker photos={many} value="P1699" onChange={() => undefined} label="A" />);
    expect(screen.getByRole("option", { name: /P1699/ })).toBeInTheDocument();
  });

  it("states when nothing matches instead of showing an empty control", async () => {
    const user = userEvent.setup();
    render(<PhotoPicker photos={many} value="" onChange={() => undefined} label="A" />);
    await user.type(screen.getByLabelText(/Поиск по ID/), "zzz-нет-такого");
    expect(screen.getByText("Ничего не найдено")).toBeInTheDocument();
  });

  it("propagates the chosen id", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<PhotoPicker photos={many.slice(0, 5)} value={many[0].id} onChange={onChange} label="A" />);
    await user.selectOptions(screen.getByLabelText("A"), many[2].id);
    expect(onChange).toHaveBeenCalledWith(many[2].id);
  });
});
