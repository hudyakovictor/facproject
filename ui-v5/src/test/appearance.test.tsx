import { describe, expect, test, beforeEach } from "vitest";
import { render, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  useAppearanceStore,
  applyAppearance,
  resolveTheme,
} from "../shared/state/appearanceStore";
import { SettingsPage } from "../features/settings/SettingsPage";

/**
 * Тема и плотность объявлены в `tokens.css` с самого начала, но ни один
 * атрибут никогда не выставлялся: оба режима были мёртвым CSS. Эти проверки
 * фиксируют, что переключатель действительно доходит до корня документа.
 */

beforeEach(() => {
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-density");
  localStorage.clear();
  useAppearanceStore.setState({ theme: "dark", density: "comfortable" });
});

const renderSettings = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SettingsPage />
    </QueryClientProvider>,
  );

describe("тема и плотность", () => {
  test("выставляются именно те атрибуты, которые читает tokens.css", () => {
    applyAppearance("light", "compact");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.dataset.density).toBe("compact");
  });

  test("системная тема разрешается в конкретную, а не остаётся строкой system", () => {
    expect(["dark", "light"]).toContain(resolveTheme("system"));
    applyAppearance("system", "comfortable");
    expect(["dark", "light"]).toContain(document.documentElement.dataset.theme);
  });

  test("переключение темы в настройках доходит до документа и переживает перезагрузку", async () => {
    const { getByText } = renderSettings();
    await act(async () => getByText("Светлая").click());

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("deeputin.theme")).toBe("light");
  });

  test("плотность переключается независимо от темы", async () => {
    const { getByText } = renderSettings();
    await act(async () => getByText("Плотная").click());

    expect(document.documentElement.dataset.density).toBe("compact");
    expect(useAppearanceStore.getState().theme).toBe("dark");
  });

  test("сброс возвращает тёмную тему и обычную плотность", async () => {
    const { getByText } = renderSettings();
    await act(async () => getByText("Светлая").click());
    await act(async () => getByText("Плотная").click());
    await act(async () => getByText("Сбросить настройки").click());

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.dataset.density).toBe("comfortable");
  });

  test("настройки не содержат параметров анализа (§25.6)", () => {
    const { container } = renderSettings();
    const text = container.textContent ?? "";
    // Пороги и параметры кластеризации влияют на результат и живут на своих
    // экранах: здесь они не должны появиться даже как «удобная копия».
    expect(text).not.toMatch(/Минимальное качество|Порог активности рта|Допуск угла/);
  });
});
