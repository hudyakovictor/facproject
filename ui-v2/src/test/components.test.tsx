import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ErrorBoundary from "../components/ErrorBoundary";
import { Spinner, Skeleton } from "../components/Loading";
import ZoneCatalog from "../components/ZoneCatalog";
import ChronologyAnomalies from "../components/ChronologyAnomalies";
import Icon from "../components/Icon";
import * as api from "../api";

afterEach(() => vi.restoreAllMocks());

// --- ErrorBoundary ----------------------------------------------------------

function Boom({ fail }: { fail: boolean }) {
  if (fail) throw new Error("рендер упал");
  return <div>содержимое</div>;
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // React логирует пойманную ошибку в консоль — это ожидаемо и не
    // должно засорять вывод теста.
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  it("пропускает исправный поддерева без изменений", () => {
    render(<ErrorBoundary label="X"><Boom fail={false} /></ErrorBoundary>);
    expect(screen.getByText("содержимое")).toBeTruthy();
  });

  it("перехватывает ошибку и называет упавший компонент", () => {
    render(<ErrorBoundary label="UnifiedTimeline"><Boom fail /></ErrorBoundary>);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("UnifiedTimeline");
  });

  it("показывает текст ошибки, а не скрывает его", () => {
    // Скрытая причина превращает диагностику в угадывание: в forensic-
    // интерфейсе пользователь должен видеть, что именно сломалось.
    render(<ErrorBoundary label="X"><Boom fail /></ErrorBoundary>);
    expect(screen.getByText(/рендер упал/)).toBeTruthy();
  });

  it("кнопка перезапуска доступна с клавиатуры и имеет имя", () => {
    render(<ErrorBoundary label="X"><Boom fail /></ErrorBoundary>);
    const button = screen.getByRole("button");
    expect(button.getAttribute("aria-label")).toBeTruthy();
  });

  it("вызывает onReset при перезапуске", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(<ErrorBoundary label="X" onReset={onReset}><Boom fail /></ErrorBoundary>);
    await user.click(screen.getByRole("button"));
    expect(onReset).toHaveBeenCalled();
  });
});

// --- Loading ----------------------------------------------------------------

describe("Loading", () => {
  it("Spinner объявляет статус для screen reader", () => {
    render(<Spinner />);
    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-live")).toBe("polite");
  });

  it("Spinner принимает собственную подпись", () => {
    render(<Spinner label="Загрузка метрик" />);
    expect(screen.getByText("Загрузка метрик")).toBeTruthy();
  });

  it("Skeleton рендерит заданное число полос", () => {
    const { container } = render(<Skeleton lines={5} />);
    // Полосы — прямые потомки контейнера со статусом.
    const status = container.querySelector('[role="status"]');
    expect(status?.children.length).toBe(5);
  });
});

// --- Icon -------------------------------------------------------------------

describe("Icon", () => {
  it("скрыт от screen reader как декоративный", () => {
    // Имя даёт кнопка-контейнер; сама иконка не должна зачитываться.
    const { container } = render(<Icon name="check" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(svg?.getAttribute("focusable")).toBe("false");
  });

  it("размер и цвет применяются", () => {
    const { container } = render(<Icon name="x" size={20} color="#ff0000" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("20");
    expect(svg?.getAttribute("stroke")).toBe("#ff0000");
  });
});

// --- ZoneCatalog ------------------------------------------------------------

const catalog: api.ZoneCatalogEntry[] = [
  {
    zone_id: "Z01", name: "forehead_center", label_ru: "лоб центр",
    group: "forehead", side: "midline", seed_uv: [0.5, 0.2], scale_uv: [0.1, 0.1],
    excluded_by_segmentation: false,
  },
  {
    zone_id: "Z13", name: "upper_eyelid_left", label_ru: "верхнее веко слева",
    group: "eye", side: "left", seed_uv: [0.3, 0.4], scale_uv: [0.05, 0.05],
    excluded_by_segmentation: true,
  },
];

describe("ZoneCatalog", () => {
  it("показывает зоны, сгруппированные по атласу", async () => {
    vi.spyOn(api, "fetchZoneCatalog").mockResolvedValue(
      { zone_count: 2, zones: catalog });
    render(<ZoneCatalog />);
    await waitFor(() => expect(screen.getByText("лоб центр")).toBeTruthy());
  });

  it("зоны, исключённые сегментацией, визуально помечены", async () => {
    // Иначе отсутствие зоны в отчёте неотличимо от её отсутствия в атласе.
    vi.spyOn(api, "fetchZoneCatalog").mockResolvedValue(
      { zone_count: 2, zones: catalog });
    render(<ZoneCatalog />);
    const excluded = await screen.findByText("верхнее веко слева");
    const normal = screen.getByText("лоб центр");
    // Исключённая зона получает предупреждающий цвет, обычная — нет.
    // jsdom нормализует #e8af34 в rgb(232, 175, 52).
    expect(excluded.getAttribute("style")).toContain("rgb(232, 175, 52)");
    expect(normal.getAttribute("style") ?? "").not.toContain("rgb(232, 175, 52)");
  });

  it("ошибка загрузки показывается, а не проглатывается", async () => {
    vi.spyOn(api, "fetchZoneCatalog").mockRejectedValue(new Error("нет атласа"));
    render(<ZoneCatalog />);
    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());
  });
});

// --- ChronologyAnomalies ----------------------------------------------------

describe("ChronologyAnomalies", () => {
  it("пустые сводки не рендерят пустую секцию", () => {
    const { container } = render(<ChronologyAnomalies summaries={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it("сводка с нулевыми ключами тоже считается пустой", () => {
    const { container } = render(<ChronologyAnomalies summaries={{ baseline_return: {} }} />);
    expect(container.firstChild).toBeNull();
  });

  it("показывает число событий и годы", async () => {
    vi.spyOn(api, "fetchRunSummary").mockRejectedValue(new Error("no stage2"));
    const { container } = render(<ChronologyAnomalies summaries={{
      baseline_return: { event_count: 3, years: [2011, 2012] },
    }} />);
    expect(container.textContent).toContain("3");
    expect(container.textContent).toContain("2011, 2012");
  });

  it("несёт оговорку о необходимости независимой проверки", async () => {
    vi.spyOn(api, "fetchRunSummary").mockRejectedValue(new Error("no stage2"));
    render(<ChronologyAnomalies summaries={{ chronology_rate: { event_count: 1 } }} />);
    expect(screen.getByText(/независимой проверки|independent verification/)).toBeTruthy();
  });

  it("отсутствие Stage 2 не ломает панель", async () => {
    // Артефакты хронологии необязательны: без прогона блок просто не
    // появляется, а сводки из таймлайна продолжают показываться.
    vi.spyOn(api, "fetchRunSummary").mockRejectedValue(new Error("HTTP 409"));
    const { container } = render(
      <ChronologyAnomalies summaries={{ cumulative_drift: { event_count: 2 } }} />);
    // Панель осталась отрисованной, несмотря на провал запроса артефактов.
    await waitFor(() => expect(container.querySelector("section")).toBeTruthy());
    expect(container.textContent).toContain("2");
  });
});
