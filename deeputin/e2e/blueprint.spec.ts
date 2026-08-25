import { expect, test } from '@playwright/test';

test('the initial page is a data-free blueprint', async ({ page }) => {
  await page.goto('/#/timeline');

  await expect(page).toHaveTitle('DEEPUTIN — Forensic Workbench');
  await expect(page.getByRole('heading', { name: 'Timeline' })).toBeVisible();
  await expect(page.getByText('NO SOURCE DATA')).toBeVisible();
  await expect(
    page.getByText('Данные не подключены. Реализация этого блока выполняется отдельно.'),
  ).toBeVisible();
});
