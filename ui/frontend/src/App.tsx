import { useEffect, useState } from "react";
import { loadHealth } from "./api";
import type { DatasetHealth, ProjectHealth, RunRecord, StorageState } from "./types";
import { FunctionCatalog } from "./Catalog";
import { PipelineCanvas } from "./PipelineCanvas";
import { RuntimePanel } from "./RuntimePanel";
import { ScenarioLab } from "./ScenarioLab";
import { InvestigationPanel } from "./InvestigationPanel";
import { TimelinePanel } from "./TimelinePanel";
import { CalibrationPanel } from "./CalibrationPanel";
import { LogConsole } from "./LogConsole";
import { GuidedSetup } from "./GuidedSetup";
import { InvestigationWorkspace } from "./InvestigationWorkspace";
import { uiLog } from "./logStore";
import "./styles.css";

type ViewId = "guide" | "investigation" | "pipeline" | "runs" | "functions" | "calibration" | "developer";
type NavItem = { id: ViewId; icon: string; title: string; hint: string };

const navigation: NavItem[] = [
  { id: "guide", icon: "➜", title: "Следующий шаг", hint: "Обязательный пошаговый маршрут" },
  { id: "investigation", icon: "◫", title: "Расследование", hint: "Фотографии и хронология" },
  { id: "pipeline", icon: "⌘", title: "Карта pipeline", hint: "Архитектура и readiness" },
  { id: "runs", icon: "▶", title: "Запуски", hint: "Сценарии, выполнение и replay" },
  { id: "functions", icon: "ƒ", title: "Функции", hint: "Каталог исходного кода" },
  { id: "calibration", icon: "◎", title: "Калибровка", hint: "Run groups и pose policy" },
  { id: "developer", icon: "◇", title: "Developer Ops", hint: "Сбои, patches и rollback" },
];

const POSES = [
  ["LP", "Левый профиль"], ["LD", "Левый глубокий"], ["LM", "Левый средний"],
  ["LL", "Левый лёгкий"], ["F", "Фронтальный"], ["RL", "Правый лёгкий"],
  ["RM", "Правый средний"], ["RD", "Правый глубокий"], ["RP", "Правый профиль"],
];

const storageLabels: Record<StorageState, string> = {
  ready: "Хранилище готово", volume_missing: "SDCARD не подключена", heavy_root_missing: "Корень данных не создан",
  wrong_volume: "Подключён другой диск", not_writable: "Нет доступа на запись", low_space: "Недостаточно места",
  unsafe_path: "Небезопасный путь", storage_interrupted: "Диск отключён",
};

function formatBytes(value: number | null): string {
  if (value == null) return "—";
  const units = ["Б", "КБ", "МБ", "ГБ", "ТБ"];
  let size = value, unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${size.toFixed(unit > 1 ? 1 : 0)} ${units[unit]}`;
}

function DatasetSummary({ title, data }: { title: string; data?: DatasetHealth }) {
  return <div className="dataset-summary">
    <span className={`state-dot ${data?.available ? "ok" : "warn"}`} />
    <div><b>{title}</b><small>{data?.available ? `${data.file_count} файлов · ${formatBytes(data.total_bytes)}` : data?.reasons?.[0] ?? "не настроен"}</small></div>
  </div>;
}

function InvestigationHome({ health }: { health: ProjectHealth | null }) {
  const total = health?.datasets.main?.file_count ?? 0;
  return <div className="investigation-workbench">
    <header className="view-header">
      <div><p className="eyebrow">FORENSIC FACE / SKIN CONSISTENCY</p><h1>Хронология расследования</h1><p>Фотоархив, девять ракурсов, геометрия, кожа и временные аномалии.</p></div>
      <div className="view-actions"><span className="mode-chip">1999–2026</span><span className="mode-chip">{total} фотографий</span></div>
    </header>

    <div className="investigation-layout">
      <section className="chronology-panel">
        <div className="analysis-toolbar">
          <div className="segmented"><button className="active">Хронология</button><button disabled>Матрица</button><button disabled>Кластеры</button></div>
          <div className="analysis-filters"><span>Все годы</span><span>9 ракурсов</span><span>Все качества</span></div>
        </div>
        <div className="metric-legend"><span className="geometry">Геометрия</span><span className="texture">Кожа/текстура</span><span className="quality">Качество</span><span className="anomaly">Аномалии</span></div>
        <div className="photo-timeline-empty">
          <div className="year-axis"><span>1999</span><span>2005</span><span>2010</span><span>2015</span><span>2020</span><span>2026</span></div>
          <div className="pose-lanes">
            {POSES.map(([code, name]) => <div className="pose-lane" key={code}><b>{code}</b><span>{name}</span><i /></div>)}
          </div>
          <div className="honest-empty">
            <b>Индекс фотографий ещё не подключён к UI</b>
            <p>Backend сейчас сообщает только количество файлов, но не отдаёт карточки фото, даты, pose и метрики. Интерфейс не рисует выдуманные результаты.</p>
          </div>
        </div>
      </section>

      <aside className="analysis-inspector">
        <div className="inspector-tabs"><button className="active">Фото</button><button disabled>Пара A/B</button><button disabled>3D</button></div>
        <div className="inspector-empty"><span>＋</span><b>Выберите фотографию</b><p>Здесь появятся исходник, pose, качество, 3D/UV и результаты анализа.</p></div>
        <div className="evidence-boundary"><b>Граница доказательств</b><p>Визуальное сходство и UV сами по себе не подтверждают личность. Выводы должны учитывать качество, pose, калибровку и альтернативные объяснения.</p></div>
      </aside>
    </div>
  </div>;
}

function RunsView({ run, onRunChange }: { run: RunRecord | null; onRunChange: (run: RunRecord | null) => void }) {
  return <div className="stack-view"><header className="view-header"><div><p className="eyebrow">VALIDATION & EXECUTION</p><h1>Запуски и сценарии</h1><p>Раздельно от аналитической рабочей станции.</p></div></header><div className="two-column-view"><div><ScenarioLab /><RuntimePanel onRunChange={onRunChange} /></div><TimelinePanel run={run} /></div></div>;
}

export default function App() {
  const [health, setHealth] = useState<ProjectHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<RunRecord | null>(null);
  const [view, setView] = useState<ViewId>("guide");
  const [sidebarCompact, setSidebarCompact] = useState(false);
  const [foundationComplete, setFoundationComplete] = useState(false);
  const [analysisUnlocked, setAnalysisUnlocked] = useState(false);
  const expertOverride = new URLSearchParams(window.location.search).get("expert") === "1";

  function canOpen(id: ViewId) {
    if (id === "guide" || expertOverride) return true;
    if (["pipeline", "runs", "functions", "calibration", "developer"].includes(id)) return foundationComplete;
    return analysisUnlocked;
  }

  function openView(id: ViewId) {
    if (!canOpen(id)) {
      uiLog("warning", "navigation", `Раздел «${navigation.find((x) => x.id === id)?.title ?? id}» заблокирован текущим обязательным шагом`);
      setView("guide");
      return;
    }
    uiLog("info", "navigation", `Открыт раздел: ${id}`);
    setView(id);
  }

  useEffect(() => {
    const controller = new AbortController();
    loadHealth(controller.signal).then(setHealth).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "API недоступен");
    });
    return () => controller.abort();
  }, []);

  const title = navigation.find((x) => x.id === view)?.title ?? "DEEPUTIN";

  return <div className={`app-shell-v2 ${sidebarCompact ? "compact" : ""}`}>
    <header className="topbar-v2">
      <div className="brand"><strong>D</strong><div><b>DEEPUTIN</b><small>Investigation Workbench</small></div></div>
      <div className="topbar-context"><span>{title}</span><i>app6 · read only</i></div>
      <div className="system-state"><span className={`state-dot ${error ? "warn" : foundationComplete ? "ok" : "warn"}`} /><b>{error ? "Backend недоступен" : foundationComplete ? "Базовые проверки завершены" : "Пошаговая настройка"}</b></div>
    </header>

    <aside className="sidebar-v2">
      <button className="sidebar-collapse" onClick={() => setSidebarCompact((x) => !x)} aria-label="Свернуть навигацию">{sidebarCompact ? "›" : "‹"}</button>
      <nav>{navigation.map((item) => { const allowed = canOpen(item.id); return <button key={item.id} className={`${view === item.id ? "active" : ""} ${allowed ? "" : "locked"}`} onClick={() => openView(item.id)} aria-disabled={!allowed} title={allowed ? item.hint : "Сначала завершите текущий обязательный шаг"}><i>{allowed ? item.icon : "⌁"}</i><span><b>{item.title}</b><small>{allowed ? item.hint : "заблокировано мастером"}</small></span></button>; })}</nav>
      <div className="sidebar-health">
        <DatasetSummary title="Основной архив" data={health?.datasets.main} />
        <DatasetSummary title="Калибровка" data={health?.datasets.calibration} />
        <small>{health ? storageLabels[health.storage.state] : "Проверка хранилища…"}</small>
      </div>
    </aside>

    <main className="workspace-v2">
      {error && <div className="floating-error"><b>Backend недоступен</b><span>{error}</span></div>}
      {view === "guide" && <GuidedSetup onGateChange={(foundation, analysis) => { setFoundationComplete(foundation); setAnalysisUnlocked(analysis); }} />}
      {view === "investigation" && <InvestigationWorkspace health={health} />}
      {view === "pipeline" && <div className="canvas-view"><header className="view-header compact-header"><div><p className="eyebrow">ARCHITECTURE EXPLORER</p><h1>Карта pipeline</h1><p>Поэтапное раскрытие вместо одновременного рендера 559 узлов.</p></div></header><PipelineCanvas /></div>}
      {view === "runs" && <RunsView run={activeRun} onRunChange={setActiveRun} />}
      {view === "functions" && <div className="stack-view"><FunctionCatalog /></div>}
      {view === "calibration" && <div className="stack-view"><CalibrationPanel /></div>}
      {view === "developer" && <div className="stack-view"><header className="view-header"><div><p className="eyebrow">DEVELOPER OPERATIONS</p><h1>Сбои, patches и rollback</h1><p>Технические операции вынесены из рабочего пространства журналиста.</p></div></header><InvestigationPanel run={activeRun} /></div>}
    </main>
    <LogConsole />
  </div>;
}
