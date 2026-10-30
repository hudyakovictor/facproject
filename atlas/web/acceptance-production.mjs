import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
const browser = await chromium.launch({
  headless: true,
  args: [
    "--no-sandbox",
    "--enable-unsafe-swiftshader",
    "--use-gl=angle",
    "--use-angle=swiftshader",
  ],
});
const report = { checks: [], errors: [] };
const check = (label, pass) => {
  report.checks.push({ label, pass });
  if (!pass) throw Error(label);
};
async function isolated(cpu = false) {
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1040 },
  });
  const page = await context.newPage();
  await page.route("**/api/workspace", (r) =>
    r.fulfill({
      status: 200,
      contentType: "application/json",
      body: r.request().method() === "GET" ? "null" : '{"ok":true}',
    }),
  );
  await page.route("**/api/library", async (r) => {
    const response = await r.fetch(),
      data = await response.json();
    data.photos = data.photos.filter((p) => p.demo);
    data.groups = [...new Set(data.photos.map((p) => p.group))];
    await r.fulfill({ response, json: data });
  });
  if (cpu)
    await page.addInitScript(() => {
      const get = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (name, ...args) {
        return String(name).includes("webgl")
          ? null
          : get.call(this, name, ...args);
      };
    });
  page.on("pageerror", (e) => report.errors.push(e.stack));
  page.on("response", (r) => {
    if (r.status() >= 400) report.errors.push(`HTTP ${r.status()} ${r.url()}`);
  });
  page.on("console", (m) => {
    if (m.type() === "error") report.errors.push(m.text());
  });
  return { page, context };
}
let page;
try {
  let session = await isolated();
  page = session.page;
  await page.goto("http://127.0.0.1:5173", { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".scene-node .photo-keyframe", { timeout: 30000 });
  await page
    .locator('.scene-node button[title="Параметры тепловой карты"]')
    .click();
  await page.waitForSelector(".heat-controls");
  const heatSwitch = page.getByRole("switch", {
    name: "Включить тепловую карту",
  });
  if ((await heatSwitch.getAttribute("aria-checked")) !== "true")
    await heatSwitch.click();
  await page.waitForFunction(
    () =>
      parseFloat(document.querySelector(".heat-summary b")?.textContent) > 0,
  );
  await page.screenshot({
    path: "../reports/working-interface.png",
    fullPage: true,
  });
  await page
    .locator(".navigation-dock")
    .getByRole("button", { name: /Кластеры/ })
    .click();
  await page.waitForSelector(".cluster-node");
  await page.waitForSelector(".cluster-legend");
  check(
    "Production: real PCA result",
    await page
      .locator(".cluster-summary")
      .innerText()
      .then((s) => s.includes("PCA")),
  );
  check(
    "Production: five dated frames",
    (await page.locator(".photo-keyframe").count()) === 5,
  );
  check(
    "Production: three measured metric tracks",
    (await page.locator(".metric-track").count()) === 3,
  );
  await page
    .locator(".cluster-node")
    .getByRole("button", { name: "3D", exact: true })
    .click();
  await page.waitForSelector(".cluster-node canvas");
  check("Production: true 3D cluster view", true);
  await page
    .locator(".cluster-node")
    .getByRole("button", { name: "2D", exact: true })
    .click();
  await page.waitForSelector(".cluster-node .scatter-container > svg");
  await page
    .locator(".navigation-dock")
    .getByRole("button", { name: /3D/ })
    .first()
    .click();
  await page.waitForSelector(".scene-node .photo-keyframe");
  const first = await page
    .locator(".scene-node canvas")
    .evaluate((c) => c.toDataURL());
  await page
    .getByRole("slider", { name: "Верхний порог", exact: true })
    .fill("0.02");
  await page.waitForTimeout(300);
  check(
    "Production: live WebGL heat threshold",
    first !==
      (await page.locator(".scene-node canvas").evaluate((c) => c.toDataURL())),
  );
  await page.locator(".photo-keyframe").nth(3).click();
  await page.waitForFunction(() =>
    document
      .querySelector(".source-badge")
      ?.textContent?.includes("2021-02-12"),
  );
  check("Production: exact photo selection", true);
  await page
    .locator(".photo-keyframe")
    .nth(1)
    .click({ modifiers: ["Control"] });
  check(
    "Production: Ctrl multiple selection",
    (await page.locator(".route-selected").count()) === 2,
  );
  await page.locator(".transition-hit").nth(1).click();
  await page.waitForFunction(() =>
    document.querySelector(".morph-badge")?.textContent?.includes("50%"),
  );
  check("Production: transition morph", true);
  await page
    .getByRole("slider", { name: "Позиция морфинга", exact: true })
    .fill("0.7");
  await page.waitForFunction(() =>
    document.querySelector(".morph-badge")?.textContent?.includes("78%"),
  );
  check("Production: eased scrub matches timeline", true);
  await page
    .getByTestId("morph-panel")
    .getByRole("button", { name: "Воспроизвести морфинг", exact: true })
    .click();
  await page.waitForFunction(
    () =>
      +document.querySelector('input[aria-label="Позиция морфинга"]')?.value >
      0.7,
  );
  check("Production: playback advances", true);
  await page
    .getByTestId("morph-panel")
    .locator(".play-button")
    .evaluate((el) => {
      if (el.classList.contains("playing")) el.click();
    });
  await page
    .getByRole("button", { name: "Ракурсы", exact: true })
    .first()
    .click();
  await page.waitForSelector(".pose-range-row");
  check(
    "Production: five pose editors",
    (await page.locator(".pose-range-row").count()) === 5,
  );
  await page
    .getByRole("button", { name: "Реестр", exact: true })
    .first()
    .click();
  await page.waitForSelector(".metric-editor");
  check(
    "Production: model × pose configuration",
    (await page.locator(".metric-editor").count()) >= 3,
  );
  await session.context.close();
  session = await isolated(true);
  page = session.page;
  const frames = [];
  page.on("request", (r) => {
    if (r.url().includes("/preview?"))
      frames.push(new URL(r.url()).searchParams.get("t"));
  });
  await page.goto("http://127.0.0.1:5173", { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".cpu-preview img", { timeout: 20000 });
  await page
    .locator('.scene-node button[title="Параметры тепловой карты"]')
    .click();
  await page.waitForSelector(".heat-controls");
  const cpuHeatSwitch = page.getByRole("switch", {
    name: "Включить тепловую карту",
  });
  if ((await cpuHeatSwitch.getAttribute("aria-checked")) !== "true")
    await cpuHeatSwitch.click();
  await page.waitForFunction(
    () => document.querySelector(".cpu-preview img")?.naturalWidth === 512,
  );
  check(
    "CPU: no WebGL required",
    (await page.locator(".scene-node canvas").count()) === 0,
  );
  await page
    .locator(".navigation-dock")
    .getByRole("button", { name: /Кластеры/ })
    .click();
  await page
    .locator(".cluster-node")
    .getByRole("button", { name: "3D", exact: true })
    .click();
  await page.waitForFunction(() =>
    document
      .querySelector(".cluster-footer")
      ?.textContent?.includes("нет WebGL"),
  );
  check(
    "CPU: 3D cluster safely shows marked XY projection without WebGL",
    true,
  );
  await page
    .locator(".navigation-dock")
    .getByRole("button", { name: /3D/ })
    .first()
    .click();
  await page.waitForFunction(() => {
    const r = document.querySelector(".scene-node")?.getBoundingClientRect();
    return !!r && r.left > 0 && r.top > 50 && r.bottom < window.innerHeight;
  });
  await page.waitForSelector(".cpu-preview img");
  check(
    "CPU: percentile/histogram statistics computed",
    await page
      .locator(".heat-summary b")
      .first()
      .innerText()
      .then((t) => parseFloat(t) > 0),
  );
  check(
    "CPU: actual 3D landmark overlay",
    (await page.locator(".cpu-landmarks circle").count()) > 20,
  );
  for (const name of ["ldm68", "ldm106", "ldm134"]) {
    const control = page.getByRole("switch", {
      name: "Точки " + name,
      exact: true,
    });
    if ((await control.getAttribute("aria-checked")) !== "true")
      await control.click();
  }
  await page.waitForTimeout(250);
  check(
    "CPU: simultaneous independent landmark layers",
    (await page.locator(".cpu-landmarks g").count()) >= 2,
  );
  await page
    .getByRole("slider", { name: "Верхний порог", exact: true })
    .fill("0.02");
  await page.waitForTimeout(500);
  check(
    "CPU: manual heat range applied",
    await page
      .locator(".cpu-preview img")
      .getAttribute("src")
      .then(
        (s) => new URL(s, "http://test").searchParams.get("vmax") === "0.02",
      ),
  );
  await page.locator(".transition-hit").nth(0).click();
  await page
    .getByRole("slider", { name: "Позиция морфинга", exact: true })
    .fill("0.05");
  frames.length = 0;
  await page
    .getByTestId("morph-panel")
    .getByRole("button", { name: "Воспроизвести морфинг", exact: true })
    .click();
  await page.waitForTimeout(1600);
  await page
    .getByTestId("morph-panel")
    .locator(".play-button")
    .evaluate((el) => {
      if (el.classList.contains("playing")) el.click();
    });
  check(
    "CPU: morph produces intermediate frames, not a starving debounce",
    new Set(frames).size >= 4 && frames.some((t) => +t > 0.1 && +t < 0.9),
  );
  report.cpuFrameSamples = frames;
  const box = await page.locator(".cpu-image-wrap").boundingBox();
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.45);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width * 0.55 + 45,
    box.y + box.height * 0.45 + 20,
    { steps: 4 },
  );
  await page.mouse.up();
  await page.waitForTimeout(600);
  check(
    "CPU: 3D orbit updates render",
    await page
      .locator(".cpu-preview img")
      .getAttribute("src")
      .then((s) => +new URL(s, "http://test").searchParams.get("yaw") > 5),
  );
  await page.screenshot({
    path: "../reports/cpu-interface.png",
    fullPage: true,
  });
  await session.context.close();
  check("Production and CPU: no browser errors", report.errors.length === 0);
} catch (e) {
  report.failure = String(e);
  if (page && !page.isClosed())
    await page.screenshot({
      path: "../reports/production-failure.png",
      fullPage: true,
    });
} finally {
  await fs.writeFile(
    "../reports/production-acceptance.json",
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
}
if (report.failure) process.exit(1);
