// Итерация 5, §4.5–4.6: проверка таймлайна в браузере + скриншот.
// Открывает metrics-таймлайн на реальном корпусе, считает data-testid и
// сохраняет reports/figures/v5-timeline-ui.png.
import { chromium } from "@playwright/test";

const GROUP = process.env.V5_GROUP || "person_04";
const SHOT = new URL("../reports/figures/v5-timeline-ui.png", import.meta.url);
const OUT = new URL("../reports/calibration/timeline-ui-v5.json", import.meta.url);
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--enable-unsafe-swiftshader",
    "--use-gl=angle", "--use-angle=swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 1040 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

const report = { group: GROUP, errors };
try {
  await page.goto("http://127.0.0.1:5173", { waitUntil: "domcontentloaded" });
  // Выбрать группу корпуса, если плеер стартовал на демо.
  try {
    await page.getByText(GROUP, { exact: true }).first().click({ timeout: 5000 });
  } catch { /* уже выбрана или список не показан */ }
  await page.waitForSelector('[data-testid="metrics-timeline"]', { timeout: 20000 });
  const panel = page.locator('[data-testid="metrics-timeline"]');
  await panel.waitFor({ state: "visible", timeout: 20000 });
  await page.waitForSelector('[data-testid="chart-track"]', { timeout: 20000 });
  await page.waitForTimeout(800);

  const chartTracks = await page.locator('[data-testid="chart-track"]').count();
  const metricOnly = await page.locator(".metric-track:not(.chart-track)").count();
  const allMetric = await page.locator(".metric-track").count();
  const chartMode = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="metrics-timeline"] .track-label');
    return el ? el.textContent.trim() : null;
  });
  report.checks = {
    chart_track_count: chartTracks,
    metric_track_not_chart_count: metricOnly,
    metric_track_total: allMetric,
    chart_track_pass: chartTracks === 1,
    no_extra_metric_tracks_pass: metricOnly === 0,
  };
  report.pass = report.checks.chart_track_pass && report.checks.no_extra_metric_tracks_pass;

  await page.screenshot({ path: fileURLToPath(SHOT) });
  await fs.writeFile(fileURLToPath(OUT), JSON.stringify(report, null, 1));
  console.log("checks", JSON.stringify(report.checks), "pass", report.pass);
  console.log("screenshot", fileURLToPath(SHOT));
} catch (e) {
  report.failure = String(e);
  try { await page.screenshot({ path: fileURLToPath(SHOT) }); } catch {}
  console.error("FAIL", e);
} finally {
  await browser.close();
}
process.exit(report.pass ? 0 : 1);
