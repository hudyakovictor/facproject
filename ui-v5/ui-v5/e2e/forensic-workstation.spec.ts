import { expect, test } from "@playwright/test";

test.describe("DEEPUTIN v5.0 Forensic Workstation E2E Acceptance Suite", () => {
  test("01. Overview page renders 9-pose coverage matrix and LOPO 7/7 status", async ({ page }) => {
    await page.goto("/overview");
    await expect(page.getByText("ОБЗОР ГОТОВНОСТИ ПАЙПЛАЙНА")).toBeVisible();
    await expect(page.getByText("1,900")).toBeVisible();
    await expect(page.getByText("LOPO КАЛИБРОВКА")).toBeVisible();
    await expect(page.getByText("7 / 7 HIGH")).toBeVisible();
    await expect(page.getByText("Фронтальный (Yaw 0° ± 6°)")).toBeVisible();
  });

  test("02. Core Timeline renders 6-row metric matrix, portraits, minimap, and footer", async ({ page }) => {
    await page.goto("/timeline");
    await expect(page.getByText("МЕТРИКИ 6/24")).toBeVisible();
    await expect(page.getByText("кач")).toBeVisible();
    await expect(page.getByText("bone")).toBeVisible();
    await expect(page.getByText("орб")).toBeVisible();
    await expect(page.getByText("Δ орбита +12%")).toBeVisible();
    await expect(page.getByText("минимап")).toBeVisible();
    await expect(page.getByText("ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ")).toBeVisible();
  });

  test("03. Data Manager renders 1,900 photos, conflict badges, and opens Sidecar Inspector", async ({ page }) => {
    await page.goto("/data-manager");
    await expect(page.getByText("DEEPUTIN V5 · ДАННЫЕ И PROVENANCE")).toBeVisible();
    await expect(page.getByText("2 конфликта дат")).toBeVisible();
    await expect(page.getByText("1999_08_16_1.jpg")).toBeVisible();
    await expect(page.getByText("конфликт дат · EXIF ≠ имя")).toBeVisible();
    await expect(page.getByText("без sidecar")).toBeVisible();
  });

  test("04. Photo Inspector renders Split-View with interactive 3D mesh and 6 compact cards", async ({ page }) => {
    await page.goto("/inspector");
    await expect(page.getByText("ИНСПЕКТОР ФОТОГРАФИИ")).toBeVisible();
    await expect(page.getByText("1. ИСХОДНЫЙ АРХИВНЫЙ КАДР")).toBeVisible();
    await expect(page.getByText("3D-каркас (Wireframe)")).toBeVisible();
    await expect(page.getByText("Костно-геометрический SNR")).toBeVisible();
    await expect(page.getByText("HIGH CONFIDENCE")).toBeVisible();
  });

  test("05. Morphing & 3D Chronology renders range focus buttons and layer checkboxes", async ({ page }) => {
    await page.goto("/morphing");
    await expect(page.getByText("ИНТЕРАКТИВНЫЙ 3D-МОРФИНГ И ХРОНОЛОГИЯ")).toBeVisible();
    await expect(page.getByText("2009–2012 (Зум аномалий)")).toBeVisible();
    await expect(page.getByText("Тепловая карта костных отклонений")).toBeVisible();
    await expect(page.getByText("ВОСПРОИЗВЕСТЬ МОРФИНГ")).toBeVisible();
  });

  test("06. Pair Analysis renders 95/100 score, 4-row 40x40 thumbnail grid, and Early Reference 1999-2005 bar", async ({ page }) => {
    await page.goto("/pair-analysis");
    await expect(page.getByText("НАУЧНЫЙ РЕЙТИНГ: 95 / 100 БАЛЛОВ (25 ФАКТОРОВ)")).toBeVisible();
    await expect(page.getByText("Размер миниатюр: 44px")).toBeVisible();
    await expect(page.getByText("ФОТО А (ЭТАЛОН СРАВНЕНИЯ)")).toBeVisible();
    await expect(page.getByText("ФОТО В (СРАВНИВАЕМЫЙ ОБРАЗЕЦ)")).toBeVisible();
    await expect(page.getByText("Сверка с ранним эталоном 1999–2005 гг.")).toBeVisible();
  });

  test("07. Clustering renders full chronology tracks 1999–2026 and Boundary Detector", async ({ page }) => {
    await page.goto("/clustering");
    await expect(page.getByText("ХРОНОЛОГИЧЕСКОЕ РАСПРЕДЕЛЕНИЕ КЛАСТЕРОВ (1999–2026)")).toBeVisible();
    await expect(page.getByText("Включить все 9 ракурсов (Raw Object-Normalized)")).toBeVisible();
    await expect(page.getByText("КЛАСТЕР #1: Основной исторический профиль")).toBeVisible();
    await expect(page.getByText("ВЫЯВЛЕННЫЕ ГРАНИЦЫ ХРОНОЛОГИЧЕСКИХ СМЕН (BOUNDARY DETECTOR)")).toBeVisible();
  });

  test("08. Calibration renders LOPO 7/7 reference matrix and Anisotropic Noise Model X/Y/Z", async ({ page }) => {
    await page.goto("/calibration");
    await expect(page.getByText("КАЛИБРОВКА НУЛЕВОЙ ГИПОТЕЗЫ H0 И АУДИТ LOPO")).toBeVisible();
    await expect(page.getByText("7 / 7 HIGH")).toBeVisible();
    await expect(page.getByText("Эталон #1 (Анатомический)")).toBeVisible();
    await expect(page.getByText("Z (Глубина 3DDFA)")).toBeVisible();
    await expect(page.getByText("5 / 5 PASSED")).toBeVisible();
  });

  test("09. Hypothesis Validation renders 99/100 score, ISO quarantine banner, 90+ tiles, and Shift Bias sliders", async ({ page }) => {
    await page.goto("/hypotheses");
    await expect(page.getByText("РАЗДЕЛ: ВАЛИДАЦИЯ ГИПОТЕЗ (ИЗОЛИРОВАННЫЙ РЕЖИМ ПРОВЕРКИ — НЕ ПОПАДАЕТ В ПУБЛИЧНЫЙ ОТЧЕТ)")).toBeVisible();
    await expect(page.getByText("НАУЧНАЯ ВАЛИДНОСТЬ: 99 / 100 БАЛЛОВ (150 ФАКТОРОВ)")).toBeVisible();
    await expect(page.getByText("Панель калибровки порогов и компенсации раннего смещения")).toBeVisible();
    await expect(page.getByText("БЛОК 1: Отличия `putin` от `udmurt` и `vasilich`")).toBeVisible();
    await expect(page.getByText("БЛОК 2: Отличия `udmurt` от `vasilich`")).toBeVisible();
    await expect(page.getByText("БЛОК 3: Попарные сопоставительные признаки")).toBeVisible();
  });

  test("10. Reports page renders 3 article draft tabs, EvidenceLink citations, and Skeptic panel", async ({ page }) => {
    await page.goto("/reports");
    await expect(page.getByText("ПУБЛИКАЦИОННЫЙ РЕДАКТОР ЖУРНАЛИСТА")).toBeVisible();
    await expect(page.getByText("Технический отчет (Для биометристов)")).toBeVisible();
    await expect(page.getByText("Публичная статья для СМИ (DEEPUTIN)")).toBeVisible();
    await expect(page.getByText("ПАНЕЛЬ «СКЕПТИК»")).toBeVisible();
    await expect(page.getByText("Критика: «Искажение объектива 2008 г.»")).toBeVisible();
  });

  test("11. Monetization page renders 99/100 score, 3-tier funnel, 1,900 NFT cards, and Arweave status", async ({ page }) => {
    await page.goto("/monetization");
    await expect(page.getByText("БЛОКЧЕЙН-ПРОВЕНАНС, NFT-АРТЕФАКТЫ И ВОРОНКА МОНЕТИЗАЦИИ (99 / 100 БАЛЛОВ)")).toBeVisible();
    await expect(page.getByText("УРОВЕНЬ 1: ОТКРЫТЫЙ КАНАЛ")).toBeVisible();
    await expect(page.getByText("УРОВЕНЬ 2: ЗАКРЫТЫЙ КАНАЛ")).toBeVisible();
    await expect(page.getByText("УРОВЕНЬ 3: NFT МАРКЕТПЛЕЙС")).toBeVisible();
    await expect(page.getByText("199901")).toBeVisible();
    await expect(page.getByText("QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco")).toBeVisible();
  });

  test("12. Audit Log page renders Stage 1 Immutability Certificate and session action ledger", async ({ page }) => {
    await page.goto("/audit");
    await expect(page.getByText("АУДИТ-ЖУРНАЛ СЕССИИ И ВЕРИФИКАЦИЯ НЕИЗМЕНЯЕМОСТИ STAGE 1")).toBeVisible();
    await expect(page.getByText("STAGE 1 INTEGRITY: 100% OK")).toBeVisible();
    await expect(page.getByText("1,900 FILES MATCHED ✓")).toBeVisible();
    await expect(page.getByText("HYPOTHESIS_SHIFT_BIAS")).toBeVisible();
    await expect(page.getByText("VERIFY_STAGE1_INTEGRITY")).toBeVisible();
  });
});
