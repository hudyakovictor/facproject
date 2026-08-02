import { describe, expect, it, vi, afterEach } from "vitest";
import { pingBackend } from "../api";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

/** Проверка связи с backend — эндпоинт `/api/v1/health` (аудит №11).
 *
 * Отдельно от `loadTimeline`: тот описывает происхождение данных
 * (demo/research), а пинг — живо ли соединение прямо сейчас. Демо-режим
 * при работающем сервере и потеря связи раньше выглядели одинаково.
 */
describe("pingBackend", () => {
  it("возвращает true при status: ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ schema: "s", status: "ok", not_a_verdict: true }),
    }));
    expect(await pingBackend()).toBe(true);
  });

  it("возвращает false при не-ok ответе", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }));
    expect(await pingBackend()).toBe(false);
  });

  it("возвращает false при сетевой ошибке, а не бросает", async () => {
    // Вызывающему коду нужен факт доступности, а не разбор причины:
    // исключение здесь заставило бы каждый вызов оборачивать в try.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    expect(await pingBackend()).toBe(false);
  });

  it("возвращает false, если тело ответа не подтверждает готовность", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ status: "degraded" }),
    }));
    expect(await pingBackend()).toBe(false);
  });

  it("не падает на невалидном JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => { throw new SyntaxError("unexpected token"); },
    }));
    expect(await pingBackend()).toBe(false);
  });

  it("передаёт AbortSignal", async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) });
    vi.stubGlobal("fetch", spy);
    const controller = new AbortController();
    await pingBackend(controller.signal);
    expect(spy.mock.calls[0][1]).toMatchObject({ signal: controller.signal });
  });
});

// --- ErrorBoundary вокруг ключевых панелей (аудит №4, №5) -------------------

import { render, screen } from "@testing-library/react";
import ErrorBoundary from "../components/ErrorBoundary";

describe("изоляция сбоев панелей", () => {
  it("падение одной панели не уносит соседнюю", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    function Bad(): React.ReactElement { throw new Error("панель упала"); }

    render(
      <div>
        <ErrorBoundary label="UnifiedTimeline"><Bad /></ErrorBoundary>
        <div>соседняя панель жива</div>
      </div>,
    );

    // Сбойная панель показала ошибку с именем...
    expect(screen.getByRole("alert").textContent).toContain("UnifiedTimeline");
    // ...а соседняя продолжает работать. Раньше падение таймлайна
    // оставляло белый экран вместо всего режима.
    expect(screen.getByText("соседняя панель жива")).toBeTruthy();
  });

  it("boundary называет каждую панель отдельно", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    function Bad(): React.ReactElement { throw new Error("x"); }
    render(<ErrorBoundary label="HeatmapWorkbench"><Bad /></ErrorBoundary>);
    expect(screen.getByRole("alert").textContent).toContain("HeatmapWorkbench");
  });
});
