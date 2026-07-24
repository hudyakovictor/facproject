import { useEffect, useState } from "react";
import { loadHealth } from "./api";
import type { DatasetHealth, ProjectHealth, StorageState } from "./types";
import { FunctionCatalog } from "./Catalog";
import { PipelineCanvas } from "./PipelineCanvas";
import { RuntimePanel } from "./RuntimePanel";
import { ScenarioLab } from "./ScenarioLab";
import { InvestigationPanel } from "./InvestigationPanel";
import { TimelinePanel } from "./TimelinePanel";
import { CalibrationPanel } from "./CalibrationPanel";
import type { RunRecord } from "./types";
import "./styles.css";

const OVERALL_READINESS_PERCENT = 80;

const storageLabels: Record<StorageState, string> = {
  ready: "Съёмный диск готов",
  volume_missing: "SDCARD не подключена",
  heavy_root_missing: "Тяжёлый корень не создан",
  wrong_volume: "Подключён другой диск",
  not_writable: "Нет доступа на запись",
  low_space: "Недостаточно места",
  unsafe_path: "Небезопасный путь",
  storage_interrupted: "Диск отключён во время работы",
};

type NavItem = { id: string; title: string; hint: string };

const navigation: NavItem[] = [
  { id: "overview", title: "Обзор", hint: "Текущее состояние проекта" },
  { id: "scenario-lab", title: "Сценарии", hint: "Synthetic 3D и Fresh-5" },
  { id: "runtime-panel", title: "Запуски", hint: "Безопасный запуск раннеров" },
  { id: "investigation-panel", title: "Patches", hint: "Разбор сбоев и применение патчей" },
  { id: "pipeline-canvas", title: "Pipeline", hint: "Карта функций и readiness" },
  { id: "catalog-section", title: "Функции", hint: "Каталог функций проекта" },
  { id: "timeline-panel", title: "таймлайн", hint: "Replay из событий запуска" },
  { id: "calibration-panel", title: "калибровка", hint: "Run Group целостность" },
];


function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function formatBytes(value: number | null): string {
  if (value == null) return "неизвестно";
  const units = ["б", "Кб", "Мб", "Гб", "Тб"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit > 1 ? 1 : 0)} ${units[unit]}`;
}

function DatasetCard({ title, data }: { title: string; data?: DatasetHealth }) {
  const available = Boolean(data?.available);
  return (
    <article className="card">
      <div className="card-heading">
        <span className={`state-dot ${available ? "ok" : "warn"}`} aria-hidden="true" />
        <div>
          <h3>{title}</h3>
          <code>{data?.root ?? "Путь не задан"}</code>
        </div>
      </div>
      <dl>
        <div><dt>Состояние</dt><dd>{available ? "Доступен" : "требует настройки"}</dd></div>
        <div><dt>Фотографий</dt><dd>{data?.file_count ?? 0}</dd></div>
        <div><dt>Размер</dt><dd>{formatBytes(data?.total_bytes ?? 0)}</dd></div>
      </dl>
      {!available && <p className="reason">{data?.reasons?.[0] ?? "Причина не указана"}</p>}
    </article>
  );
}

function LoadingCard() {
  return <div className="loading" role="status">Проверяем проект, SDCARD и датасеты…</div>;
}

export default function App() {
  const [health, setHealth] = useState<ProjectHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<RunRecord | null>(null);
  const [activeNav, setActiveNav] = useState("overview");

  useEffect(() => {
    const controller = new AbortController();
    loadHealth(controller.signal).then(setHealth).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "API недоступен");
    });
    return () => controller.abort();
  }, []);

  function goTo(id: string) {
    setActiveNav(id);
    scrollToSection(id);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <strong>DEEPUTIN</strong>
          <span>Pipeline Observatory</span>
        </div>
        <div className={`overall ${health?.status === "ready" ? "ready" : "setup"}`}>
          {health?.status === "ready" ? "Система готова" : "требуется настройка"}
        </div>
      </header>

      <aside className="sidebar" aria-label="Основная навигация">
        <p className="eyebrow">Рабочее пространство</p>
        <nav>
          {navigation.map((item) => (
            <button className={activeNav === item.id ? "active" : ""} key={item.id} title={item.hint} onClick={() => goTo(item.id)}>
              <span>{item.title}</span><small>{activeNav === item.id ? "открыто" : "перейти"}</small>
            </button>
          ))}
        </nav>
        <div className="read-only-note"><b>app6: только чтение</b><span>Прямые изменения запрещены. Патчи применяются через <button className="read-only-note-link" onClick={() => goTo("investigation-panel")}>Patch Center</button> ниже.</span></div>
      </aside>

      <main className="workspace">
        <section className="hero" id="overview">
          <div><p className="eyebrow">Ops-работая станция · отдельный TZ-интерфейс будет сделан после 100%</p><h1>Состояние проекта</h1><p>Понятная проверка кода, внешнего диска и фотографий перед запуском тяжёлого анализа.</p></div>
          <div className="progress" title="См. ui/PROGRESS.md для разбивки по итерациям"><span>Общая готовность ops-workbench</span><strong>{OVERALL_READINESS_PERCENT}%</strong><div><i style={{ width: `${OVERALL_READINESS_PERCENT}%` }} /></div></div>
        </section>

        {error && <section className="error-panel"><b>Backend пока недоступен</b><span>{error}</span><code>pip install -e 'ui[dev]' · uvicorn dpo.main:app</code></section>}
        {!health && !error && <LoadingCard />}

        {health && <>
          <section className="status-banner">
            <span className={`state-icon ${health.storage.ready ? "ok" : "warn"}`} aria-hidden="true">{health.storage.ready ? "✓" : "!"}</span>
            <div><h2>{storageLabels[health.storage.state]}</h2><code>{health.storage.heavy_root}</code><p>{health.storage.reasons[0] ?? `Свободно ${formatBytes(health.storage.free_bytes)}`}</p></div>
          </section>

          <section className="cards">
            <article className="card">
              <div className="card-heading"><span className={`state-dot ${health.app6.available ? "ok" : "bad"}`} /><div><h3>Основной pipeline</h3><code>{health.app6.root}</code></div></div>
              <dl><div><dt>Режим UI</dt><dd>только чтение</dd></div><div><dt>Python-функции</dt><dd>{health.app6.python_file_count} файлов</dd></div></dl>
            </article>
            <DatasetCard title="Основной датасет" data={health.datasets.main} />
            <DatasetCard title="Калибровка · 7 лиц" data={health.datasets.calibration} />
          </section>

          <section className="explanation">
            <h2>Что это значит</h2>
            <div className="explanation-grid">
              <p><b>Долгие результаты</b><span>Записываются только на SDCARD. Автоматического fallback на системный диск нет.</span></p>
              <p><b>Координаты из таблицы</b><span>Не используются. Геометрия заново извлекается из исходных фотографий.</span></p>
              <p><b>Архив разработчику</b><span>Будет содержать только компактные логи, JSON, CSV и описание ошибки.</span></p>
            </div>
          </section>
          <div id="scenario-lab"><ScenarioLab /></div>
          <div id="runtime-panel"><RuntimePanel onRunChange={setActiveRun} /></div>
          <div id="investigation-panel"><InvestigationPanel run={activeRun} /></div>
          <div id="pipeline-canvas"><PipelineCanvas /></div>
          <div id="catalog-section"><FunctionCatalog /></div>
          <div id="timeline-panel"><TimelinePanel run={activeRun} /></div>
          <div id="calibration-panel"><CalibrationPanel /></div>
        </>}
      </main>
    </div>
  );
}
