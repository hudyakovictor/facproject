import { describe, expect, test } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OverviewPage } from "../features/overview/OverviewPage";
import { TimelinePage } from "../features/timeline/TimelinePage";
import { DataManagerPage } from "../features/data-manager/DataManagerPage";
import { PhotoInspectorPage } from "../features/photo-inspector/PhotoInspectorPage";
import { MorphingPage } from "../features/morphing/MorphingPage";
import { PairAnalysisPage } from "../features/pair-analysis/PairAnalysisPage";
import { ClusteringPage } from "../features/clustering/ClusteringPage";
import { CalibrationPage } from "../features/calibration/CalibrationPage";
import { HypothesisValidationPage } from "../features/hypotheses/HypothesisValidationPage";
import { ReportsPage } from "../features/reports/ReportsPage";
import { MonetizationPage } from "../features/monetization/MonetizationPage";
import { AuditLogPage } from "../features/audit/AuditLogPage";
import { ArticlesPage } from "../features/articles/ArticlesPage";
import { ConsoleLogDrawer } from "../features/shell/ConsoleLogDrawer";

describe("DEEPUTIN v5.0 Forensic Workstation Component & Integration Tests", () => {
  test("01. OverviewPage renders pose coverage matrix and LOPO 7/7 status", () => {
    render(<OverviewPage />);
    expect(screen.getByText(/ОБЗОР ГОТОВНОСТИ ПАЙПЛАЙНА/i)).toBeInTheDocument();
    expect(screen.getByText("1,900")).toBeInTheDocument();
    expect(screen.getByText("7 / 7 HIGH")).toBeInTheDocument();
    expect(screen.getByText("100% ГОТОВО")).toBeInTheDocument();
  });

  test("02. TimelinePage renders 6-row metric matrix, minimap, pose bar, and Bézier bridge", () => {
    render(<TimelinePage activePose="FRONTAL" qualityThreshold={45} mouthThreshold={0.35} />);
    expect(screen.getByText(/МЕТРИКИ 6\/24/i)).toBeInTheDocument();
    expect(screen.getByText("кач")).toBeInTheDocument();
    expect(screen.getByText("bone")).toBeInTheDocument();
    expect(screen.getByText("орб")).toBeInTheDocument();
    expect(screen.getByText("Δ орбита +12%")).toBeInTheDocument();
    expect(screen.getByText("минимап")).toBeInTheDocument();
    expect(screen.getByText(/ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ/i)).toBeInTheDocument();
  });

  test("03. DataManagerPage renders metadata table, conflict badges, and Sidecar inspector", () => {
    render(<DataManagerPage />);
    expect(screen.getByText(/DEEPUTIN V5 · ДАННЫЕ И PROVENANCE/i)).toBeInTheDocument();
    expect(screen.getAllByText("1999_08_16_1.jpg").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("конфликт дат · EXIF ≠ имя").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("без sidecar")).toBeInTheDocument();
    expect(screen.getByText("РИА Новости")).toBeInTheDocument();
  });

  test("04. PhotoInspectorPage renders Split-View with 3D BFM Mesh canvas and 6 facts", () => {
    render(<PhotoInspectorPage />);
    expect(screen.getByText(/ИНСПЕКТОР ФОТОГРАФИИ/i)).toBeInTheDocument();
    expect(screen.getByText("1. ИСХОДНЫЙ АРХИВНЫЙ КАДР С НАЛОЖЕНИЕМ 21 КОСТНОЙ ЗОНЫ")).toBeInTheDocument();
    expect(screen.getByText("3D-каркас (Wireframe)")).toBeInTheDocument();
    expect(screen.getByText("Костно-геометрический SNR")).toBeInTheDocument();
    expect(screen.getByText("HIGH CONFIDENCE")).toBeInTheDocument();
  });

  test("05. MorphingPage renders range zoom presets and combination checkboxes", () => {
    render(<MorphingPage />);
    expect(screen.getByText(/ИНТЕРАКТИВНЫЙ 3D-МОРФИНГ И ХРОНОЛОГИЯ/i)).toBeInTheDocument();
    expect(screen.getByText("2009–2012 (Зум аномалий)")).toBeInTheDocument();
    expect(screen.getByText("Тепловая карта костных отклонений")).toBeInTheDocument();
    expect(screen.getByText(/ВОСПРОИЗВЕСТЬ МОРФИНГ/i)).toBeInTheDocument();
  });

  test("06. PairAnalysisPage renders 95/100 score badge, thumbnail strip, and Early Reference 1999-2005 bar", () => {
    render(<PairAnalysisPage />);
    expect(screen.getByText(/НАУЧНЫЙ РЕЙТИНГ: 95 \/ 100 БАЛЛОВ/i)).toBeInTheDocument();
    expect(screen.getByText(/Размер миниатюр: 44px/i)).toBeInTheDocument();
    expect(screen.getByText("ФОТО А (ЭТАЛОН СРАВНЕНИЯ)")).toBeInTheDocument();
    expect(screen.getByText("ФОТО В (СРАВНИВАЕМЫЙ ОБРАЗЕЦ)")).toBeInTheDocument();
    expect(screen.getByText(/Сверка с ранним эталоном 1999–2005 гг./i)).toBeInTheDocument();
  });

  test("07. ClusteringPage renders 1999–2026 chronology tracks and Boundary Detector", () => {
    render(<ClusteringPage />);
    expect(screen.getByText(/ХРОНОЛОГИЧЕСКОЕ РАСПРЕДЕЛЕНИЕ КЛАСТЕРОВ/i)).toBeInTheDocument();
    expect(screen.getByText(/Включить все 9 ракурсов/i)).toBeInTheDocument();
    expect(screen.getByText(/КЛАСТЕР #1: Основной исторический профиль/i)).toBeInTheDocument();
    expect(screen.getByText(/ВЫЯВЛЕННЫЕ ГРАНИЦЫ ХРОНОЛОГИЧЕСКИХ СМЕН/i)).toBeInTheDocument();
  });

  test("08. CalibrationPage renders LOPO 7 Reference Persons and Anisotropic Covariance noise X/Y/Z", () => {
    render(<CalibrationPage />);
    expect(screen.getByText(/КАЛИБРОВКА НУЛЕВОЙ ГИПОТЕЗЫ H0 И АУДИТ LOPO/i)).toBeInTheDocument();
    expect(screen.getByText("7 / 7 HIGH")).toBeInTheDocument();
    expect(screen.getByText("Эталон #1 (Анатомический)")).toBeInTheDocument();
    expect(screen.getByText("Z (Глубина 3DDFA)")).toBeInTheDocument();
    expect(screen.getByText("5 / 5 PASSED")).toBeInTheDocument();
  });

  test("09. HypothesisValidationPage renders 99/100 score badge, ISO banner, 90+ tiles, and Shift Bias sliders", () => {
    render(<HypothesisValidationPage />);
    expect(screen.getByText(/РАЗДЕЛ: ВАЛИДАЦИЯ ГИПОТЕЗ \(ИЗОЛИРОВАННЫЙ РЕЖИМ ПРОВЕРКИ/i)).toBeInTheDocument();
    expect(screen.getByText(/НАУЧНАЯ ВАЛИДНОСТЬ: 99 \/ 100 БАЛЛОВ/i)).toBeInTheDocument();
    expect(screen.getByText(/Панель калибровки порогов и компенсации раннего смещения/i)).toBeInTheDocument();
    expect(screen.getByText(/БЛОК 1: Отличия `putin` от `udmurt` и `vasilich`/i)).toBeInTheDocument();
    expect(screen.getByText(/БЛОК 2: Отличия `udmurt` от `vasilich`/i)).toBeInTheDocument();
    expect(screen.getByText(/БЛОК 3: Попарные сопоставительные признаки/i)).toBeInTheDocument();
  });

  test("10. ReportsPage renders 3 draft tabs, EvidenceLink citations, and Skeptic panel", () => {
    render(<ReportsPage />);
    expect(screen.getByText(/ПУБЛИКАЦИОННЫЙ РЕДАКТОР ЖУРНАЛИСТА/i)).toBeInTheDocument();
    expect(screen.getByText("Технический отчет (Для биометристов)")).toBeInTheDocument();
    expect(screen.getByText("Публичная статья для СМИ (DEEPUTIN)")).toBeInTheDocument();
    expect(screen.getByText("ПАНЕЛЬ «СКЕПТИК»")).toBeInTheDocument();
    expect(screen.getByText("Критика: «Искажение объектива 2008 г.»")).toBeInTheDocument();
  });

  test("11. MonetizationPage renders 99/100 score, 3-tier funnel, 1,900 NFT cards, and Arweave status", () => {
    render(<MonetizationPage />);
    expect(screen.getByText(/БЛОКЧЕЙН-ПРОВЕНАНС, NFT-АРТЕФАКТЫ И ВОРОНКА МОНЕТИЗАЦИИ/i)).toBeInTheDocument();
    expect(screen.getByText("УРОВЕНЬ 1: ОТКРЫТЫЙ КАНАЛ")).toBeInTheDocument();
    expect(screen.getByText("УРОВЕНЬ 2: ЗАКРЫТЫЙ КАНАЛ")).toBeInTheDocument();
    expect(screen.getByText("УРОВЕНЬ 3: NFT МАРКЕТПЛЕЙС")).toBeInTheDocument();
    expect(screen.getByText("QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco")).toBeInTheDocument();
  });

  test("12. AuditLogPage renders Stage 1 Immutability Certificate and session action ledger", () => {
    render(<AuditLogPage />);
    expect(screen.getByText(/АУДИТ-ЖУРНАЛ СЕССИИ И ВЕРИФИКАЦИЯ НЕИЗМЕНЯЕМОСТИ STAGE 1/i)).toBeInTheDocument();
    expect(screen.getByText("STAGE 1 INTEGRITY: 100% OK")).toBeInTheDocument();
    expect(screen.getByText("1,900 FILES MATCHED ✓")).toBeInTheDocument();
    expect(screen.getByText("HYPOTHESIS_SHIFT_BIAS")).toBeInTheDocument();
    expect(screen.getByText("VERIFY_STAGE1_INTEGRITY")).toBeInTheDocument();
  });

  test("13. ArticlesPage renders 10-article monograph showcase, render preview, and EvidenceLink", () => {
    render(<ArticlesPage />);
    expect(screen.getByText(/СЕРИЯ СТАТЕЙ ДЛЯ ШИРОКОЙ АУДИТОРИИ И НАУЧНЫХ РЕЦЕНЗЕНТОВ/i)).toBeInTheDocument();
    expect(screen.getByText("10 СТАТЕЙ · 85 МИН ЧТЕНИЯ")).toBeInTheDocument();
    expect(screen.getByText("4 НАГЛЯДНЫХ РЕНДЕРА")).toBeInTheDocument();
    expect(screen.getAllByText("Археология цифрового портрета").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/01_archaeology_provenance_render\.jpg/i).length).toBeGreaterThanOrEqual(1);

    // Click EvidenceLink interactive button to test modal opening
    const btn = screen.getByText(/\[Открыть проверку EvidenceLink #1999_1231\]/i);
    fireEvent.click(btn);
    expect(screen.getByText(/ИНТЕРАКТИВНОЕ ДОКАЗАТЕЛЬСТВО: DEEPUTIN_1999_1231_001/i)).toBeInTheDocument();
    expect(screen.getByText("Скачать CSV фрагмент измерений")).toBeInTheDocument();
  });

  test("14. ConsoleLogDrawer renders bottom bar, expands console, and handles test error logging", () => {
    render(<ConsoleLogDrawer />);
    // Check collapsed bottom bar is present
    expect(screen.getByText(/КОНСОЛЬ ОШИБОК И ЛОГОВ/i)).toBeInTheDocument();
    expect(screen.getByText(/STAGE 1 INTEGRITY: OK/i)).toBeInTheDocument();

    // Click bottom bar to expand console drawer
    const toggleBtn = screen.getByText(/КОНСОЛЬ ОШИБОК И ЛОГОВ/i);
    fireEvent.click(toggleBtn);

    // Check expanded panel controls are visible
    expect(screen.getByText(/КОНСОЛЬ ОШИБОК И ЛОГОВ РАБОЧЕЙ СТАНЦИИ/i)).toBeInTheDocument();
    expect(screen.getByText("JSON-дамп")).toBeInTheDocument();

    // Click "+Тест ошибки" to generate an error log entry
    const testErrorBtn = screen.getByText("+Тест ошибки");
    fireEvent.click(testErrorBtn);
    expect(screen.getByText(/Имитация сетевого сбоя: таймаут ответа/i)).toBeInTheDocument();
  });
});
