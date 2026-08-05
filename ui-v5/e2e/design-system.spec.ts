import { expect, test } from "@playwright/test";

test("design system route renders the canonical timeline grammar", async ({ page }) => {
  await page.goto("/design-system");
  await expect(page.getByRole("heading", { name: "Грамматика таймлайна" })).toBeVisible();
  await expect(page.getByText("Photo point")).toBeVisible();
  await expect(page.getByText("ДАННЫЕ · НЕ ВЕРДИКТ")).toBeVisible();
});
