import { useMemo, useState, useEffect, useRef, useCallback } from "react";
import {
  Photo, Era, type EraMeta,
  HYPOTHESIS_COLORS, EventPin, FUZZY_COLORS, Hypothesis, PoseBucket, POSE_BUCKETS, POSE_LABELS,
} from "./data";
import LeftPanel from "./components/LeftPanel";
import Icon from "./components/Icon";
import FullPhotoOverlay from "./components/FullPhotoOverlay";
import ComparisonPanel from "./components/ComparisonPanel";
import { ClusterView, EraCompareView } from "./components/AltViews";
import UnifiedTimeline from "./components/UnifiedTimeline";
import { t, useLanguage, type Language } from "./i18n";
import AnalysisViews from "./components/AnalysisViews";
import SettingsModal from "./components/SettingsModal";
import CalibrationView from "./components/CalibrationView";
import DataManagementView from "./components/DataManagementView";
import RunSummaryView from "./components/RunSummaryView";
import { modalProps, useModal } from "./useModal";
import ReportView from "./components/ReportView";
import PairCompareView from "./components/PairCompareView";
import MorphPlayerOverlay from "./components/MorphPlayerOverlay";
import { exportFixCapsule, loadTimeline, type DataMode } from "./api";
import { openPrintReport, exportAnalysisJson } from "./export";
import { pingBackend } from "./api";
import ErrorBoundary from "./components/ErrorBoundary";
import { BaselineContext, computeBaselineRefs, useBaseline } from "./baseline";
import { SettingsProvider, useSettings, useThresholds } from "./settings";
import { SEVERITY_COLOR, anomalyCounts, isQualityFlag, type AnomalyKind } from "./anomalies";
import { NotificationProvider } from "./components/Notifications";


type ViewMode = "FULL" | "MATRIX" | "CLUSTER" | "ERA_COMPARE" | "COMPARE" | "INSPECTOR" | "DRIFT" | "METRICS" | "STATS" | "PAIR_COMPARE" | "CALIBRATION" | "RUN" | "REPORT" | "DATA";


interface Filters {
  showOnlyAnomalies: boolean;
  confidenceThreshold: number;
  hideLowQuality: boolean;
  eras: Set<Era>;
  hypotheses: Set<Hypothesis>;
  flags: Set<string>;
  buckets: Set<PoseBucket>;
  dataset: "main" | "calibration";
  bucketFilter: "all" | PoseBucket;
  search: string;
}

const ALL_FLAGS = ["IMPOSSIBLE_SHORT", "RETURN_TO_BASELINE", "TRANSITION", "TEXTURE_SPIKE", "TEMPORAL_IMPOSSIBILITY", "IDENTITY_ANOMALY"];

/** Виды, обслуживаемые компонентом AnalysisViews (в отличие от FULL/CLUSTER/
 * PAIR_COMPARE/CALIBRATION/DATA, у которых собственные компоненты).
 * Set, а не массив с `includes(x as any)` — сужение типа без обхода проверок. */
type AnalysisViewMode = "MATRIX" | "COMPARE" | "INSPECTOR" | "DRIFT" | "METRICS" | "STATS";
const ANALYSIS_VIEWS: ReadonlySet<ViewMode> = new Set<ViewMode>(
  ["MATRIX", "COMPARE", "INSPECTOR", "DRIFT", "METRICS", "STATS"],
);
const isAnalysisView = (mode: ViewMode): mode is AnalysisViewMode => ANALYSIS_VIEWS.has(mode);

/** Статистика шапки: считается в App, отображается в HeaderBar. */
interface HeaderStats { total: number; filtered: number; anomalies: number; }

/** P1.1 (DEV_FIX_TZ 2.1): полностью типизированные пропсы шапки вместо `any`.
 * `any` отключал проверку всех 20+ пропсов — опечатка в имени пропса или
 * несовпадение типа проходили молча. */
interface HeaderBarProps {
  thumbSize: number;
  setThumbSize: (size: number) => void;
  filters: Filters;
  setFilters: React.Dispatch<React.SetStateAction<Filters>>;
  onSources: () => void;
  onExport: () => void;
  onExportJson: () => void;
  onToggleTheme: () => void;
  theme: "dark" | "light";
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  stats: HeaderStats;
  dataMode: DataMode;
  dataMessage: string;
  lastRunLabel: string;
  onFixCapsule: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  backendUp: boolean | null;
  leftPanelOpen: boolean;
  onToggleLeftPanel: () => void;
  onOpenFilters: () => void;
  onOpenSettings: () => void;
  onToggleLanguage: () => void;
  language: Language;
  onShowMorphPlayer: () => void;
}

/** Корневой компонент: только провайдеры.
 *
 * Настройки читаются хуком `useThresholds` внутри `AppInner`, поэтому
 * провайдер обязан быть НАД ним. Пока `App` был единым компонентом и сам
 * рендерил `<SettingsProvider>`, его собственные хуки оказывались вне
 * контекста и всегда получали встроенные значения. */
export default function App() {
  return (
    <NotificationProvider>
      <SettingsProvider>
        <AppInner />
      </SettingsProvider>
    </NotificationProvider>
  );
}

function AppInner() {
  const thresholds = useThresholds();
  // Применение настроек обязано доехать до контекста: иначе пороги
  // сохранятся на диск, но текущий сеанс продолжит считать по старым.
  const { apply: applySettings } = useSettings();
  const [filmstripOffset, setFilmstripOffset] = useState(0);
  const [thumbSize, setThumbSize] = useState(50);

  const [playheadT, setPlayheadT] = useState(Date.parse("2015-03-06"));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [showMorphPlayer, setShowMorphPlayer] = useState(false);
  const [showPin, setShowPin] = useState<EventPin | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("FULL");
  // Пустой массив, а не встроенный демо-набор: показывать синтетические
  // кадры до ответа backend означало бы выдавать их за данные. Реальное
  // содержимое приходит из `refreshTimeline`, а при недоступном сервере
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [dataMode, setDataMode] = useState<DataMode>("loading");
  const [dataMessage, setDataMessage] = useState("Загрузка /api/v1/timeline");
  /** Сегменты хронологии приходят от backend (`era_meta`); встроенный
   * ERA_META — только fallback, пока API не ответил. */
  const [eraMeta, setEraMeta] = useState<Record<string, EraMeta>>({});
  /** Доступность backend: `null` — ещё не проверяли (аудит №11).
   *
   * Отличается от `dataMode`: тот описывает ПРОИСХОЖДЕНИЕ показанных
   * данных (source/research), а это — живо ли соединение прямо сейчас.
   * Демо-режим при работающем сервере и потеря связи с ним — разные
   * ситуации, которые раньше выглядели одинаково. */
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [timelineRefreshing, setTimelineRefreshing] = useState(false);
  const [timelineError, setTimelineError] = useState("");
  const [rejectedRows, setRejectedRows] = useState<{ id: string; reason: string }[]>([]);
  /** Сводки хронологических детекторов Stage 2 (пусто в неисследовательском режиме). */
  const [chronoAnomalies, setChronoAnomalies] = useState<Record<string, Record<string, unknown>>>({});
  const [hypLegendOpen, setHypLegendOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [leftPanelOpen, setLeftPanelOpen] = useState(false);
  const [fullPhoto, setFullPhoto] = useState<Photo | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [language, setLanguage] = useLanguage();

  const [rangeA, setRangeA] = useState<{ t0: number; t1: number; photos: Photo[] } | null>(null);
  const [rangeB, setRangeB] = useState<{ t0: number; t1: number; photos: Photo[] } | null>(null);
  const [compareSide, setCompareSide] = useState<"A" | "B">("A");
  const [showCompare, setShowCompare] = useState(false);

  const [filters, setFilters] = useState<Filters>({
    showOnlyAnomalies: false,
    confidenceThreshold: 0,
    hideLowQuality: false,
    // Инициализация из встроенного набора; после ответа API заменяется
    // фактическими сегментами (см. loadTimeline ниже).
    eras: new Set<string>(),
    hypotheses: new Set(["H0", "H1", "H2"] as Hypothesis[]),
    flags: new Set(),
    buckets: new Set(POSE_BUCKETS),
    dataset: "main",
    bucketFilter: "all",
    search: "",
  });

  /** Перечитать хронологию с backend.
   *
   * Вынесено из `useEffect` в именованный коллбэк (аудит №26): после
   * завершения задания извлечения или пересчёта метрик данные на диске
   * меняются, а интерфейс продолжал показывать снимок, сделанный при
   * загрузке страницы. Единственным способом увидеть новый результат была
   * перезагрузка вкладки.
   */
  const refreshTimeline = useCallback((signal?: AbortSignal) => {
    setTimelineRefreshing(true);
    return loadTimeline(signal).then(result => {
      if (signal?.aborted) return;
      setPhotos(result.photos);
      setDataMode(result.mode);
      setDataMessage(result.message);
      setEraMeta(result.eraMeta);
      setRejectedRows(result.rejected);
      setChronoAnomalies(result.chronologyAnomalies);
      // Фильтр эпох переинициализируется ФАКТИЧЕСКИМИ сегментами ответа.
      // Прежний жёсткий список ERA_* не совпадал с `backend segment` из API,
      // и условие `filters.eras.has(p.era)` отбрасывало все строки.
      setFilters(prev => ({ ...prev, eras: new Set(Object.keys(result.eraMeta)) }));
      setTimelineError("");
    }).catch((err: unknown) => {
      if (signal?.aborted) return;
      // 🔧 Раньше здесь стоял `.catch(() => undefined)`: при недоступном
      // backend интерфейс молча оставался с прежними (или пустыми) данными,
      // и отличить «нет новых кадров» от «сервер не ответил» было нельзя.
      const message = err instanceof Error ? err.message : String(err);
      setTimelineError(message); setDataMode("error"); setDataMessage(message); setPhotos([]); setEraMeta({}); setRejectedRows([]); setChronoAnomalies({});
    }).finally(() => {
      if (!signal?.aborted) setTimelineRefreshing(false);
    });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refreshTimeline(controller.signal);
    return () => controller.abort();
  }, [refreshTimeline]);

  // Периодический пинг: 30 с — компромисс между свежестью индикатора и
  // нагрузкой. Эндпоинт дешёвый, тело ответа — три поля.
  useEffect(() => {
    const controller = new AbortController();
    const check = () => { void pingBackend(controller.signal).then(ok => {
      if (!controller.signal.aborted) setBackendUp(ok);
    }); };
    check();
    const timer = window.setInterval(check, 30_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, []);

  // Нормативный порог качества из настроек; 0.35 остаётся значением по
  // умолчанию для переключателя «скрыть низкое качество», когда порог не
  // задан явно (0 означает «не фильтровать»).
  const qualityFloor = thresholds.quality_min > 0 ? thresholds.quality_min : 0.35;
  const filteredPhotos = useMemo(() => {
    return photos.filter(p => {
      if (filters.bucketFilter !== "all" && p.bucket !== filters.bucketFilter) return false;
      if (!filters.eras.has(p.era)) return false;
      if (p.dominant !== "UNAVAILABLE" && !filters.hypotheses.has(p.dominant)) return false;
      if (!filters.buckets.has(p.bucket)) return false;
      // Пороги из настроек, а не из констант: `quality_min` задаёт границу
      // «низкого качества», `confidence_min` — минимально допустимую
      // уверенность. Ползунок фильтра ужесточает их, но не может ослабить
      // ниже нормативного порога прогона.
      const confidenceFloor = Math.max(filters.confidenceThreshold, thresholds.confidence_min);
      if (confidenceFloor > 0 && p.confidence < confidenceFloor) return false;
      if (filters.hideLowQuality && p.quality < qualityFloor) return false;
      if (thresholds.quality_min > 0 && p.quality < thresholds.quality_min) return false;
      if (filters.showOnlyAnomalies && (p.fuzzy === "CONSISTENT" || p.fuzzy === "STRONGLY_MATCHING")) return false;
      if (filters.flags.size > 0 && !p.flags.some(f => filters.flags.has(f))) return false;
      if (filters.search && !p.id.toLowerCase().includes(filters.search.toLowerCase()) && !p.date.includes(filters.search)) return false;
      return true;
    });
  }, [filters, photos, thresholds, qualityFloor]);

  const photosWithHidden = useMemo(() =>
    filteredPhotos.map(p => hiddenIds.has(p.id) ? { ...p, hidden: true } : p), [filteredPhotos, hiddenIds]);

  const selectedPhoto = selectedId ? photos.find(p => p.id === selectedId) || null : null;

  useEffect(() => { if (selectedId) setLeftPanelOpen(true); }, [selectedId]);

  const currentEra: Era = useMemo(() => {
    const ids = Object.keys(eraMeta);
    for (const era of ids) {
      const m = eraMeta[era];
      if (playheadT >= Date.parse(m.start) && playheadT <= Date.parse(m.end)) return era;
    }
    return ids[0] ?? "";
  }, [playheadT, eraMeta]);

  const stats = useMemo(() => {
    const total = photos.length;
    const filtered = filteredPhotos.length;
    const anomalies = filteredPhotos.filter(p => p.fuzzy === "IDENTITY_ANOMALY" || p.fuzzy === "GEOMETRIC_MISMATCH" || p.fuzzy === "TEMPORAL_IMPOSSIBILITY").length;
    return { total, filtered, anomalies };
  }, [filteredPhotos, photos.length]);

  /** P3.9 (DEV_FIX_TZ): дата последнего прогона больше не зашита литералом.
   * Research-режим: самый поздний кадр реального вывода Stage 2. Loading/error:
   * честное «—», а не выдуманная дата. */
  const lastRunLabel = useMemo(() => {
    if (dataMode !== "research" || photos.length === 0) return "—";
    const latest = photos.reduce((max, p) => (p.t > max ? p.t : max), photos[0].t);
    return new Date(latest).toLocaleDateString("ru-RU");
  }, [dataMode, photos]);

  /** Референсы z-score пересчитываются из ФАКТИЧЕСКИ загруженных фото.
   * Модульная константа REF (демо-набор) больше не является источником
   * истины для данных из API. */
  const baseline = useMemo(() => computeBaselineRefs(photos), [photos]);

  const appRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tgt = e.target as HTMLElement;
      if (tgt.tagName === "INPUT" || tgt.tagName === "TEXTAREA") return;
      if (e.key === "f" && !showFilters) setShowFilters(true);
      if (e.key === "c" && rangeA) setShowCompare(true);
      if (e.key === "Escape") {
        setShowFilters(false); setShowPin(null); setShowSources(false);
        if (fullPhoto) setFullPhoto(null);
        else if (showCompare) setShowCompare(false);
        else { setSelectedId(null); setLeftPanelOpen(false); }
      }
      if (e.key === "ArrowLeft") setFilmstripOffset(o => Math.max(0, o - 5));
      if (e.key === "ArrowRight") setFilmstripOffset(o => o + 5);
      if (e.key === "+" || e.key === "=") setThumbSize(s => Math.min(120, s + 10));
      if (e.key === "-") setThumbSize(s => Math.max(20, s - 10));
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showFilters, rangeA, fullPhoto, showCompare]);

  const toggleHide = (id: string) => {
    setHiddenIds(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  };

  const onRangeSelected = useCallback((range: { t0: number; t1: number; photos: Photo[] } | null) => {
    if (!range) return;
    if (compareSide === "A") setRangeA(range);
    else setRangeB(range);
    setShowCompare(true);
    setCompareSide(side => side === "A" ? "B" : "A");
  }, [compareSide]);

  const isLight = theme === "light";
  const themeVars = isLight ? {
    "--color-bg": "#f4f4f6", "--color-surface": "#ffffff", "--color-surface-2": "#eceef2",
    "--color-surface-3": "#dde0e6", "--color-border": "rgba(0,0,0,0.1)", "--color-border-strong": "rgba(0,0,0,0.22)",
    "--color-text": "#0d0d0f", "--color-text-muted": "#5a5a6a", "--color-text-faint": "#9a9aa8",
  } as React.CSSProperties : {};

  const highlightIds = useMemo(() => {
    if (showCompare && rangeA) {
      const ids = new Set<string>();
      for (const p of rangeA.photos) ids.add(p.id);
      if (rangeB) for (const p of rangeB.photos) ids.add(p.id);
      return ids;
    }
    return undefined;
  }, [showCompare, rangeA, rangeB]);

  return (
    <BaselineContext.Provider value={baseline}>
      <div className="small-viewport-notice fixed inset-0 z-[200] bg-bg text-text items-center justify-center p-8 text-center font-mono">
        <div>
          <div className="font-display text-lg mb-3">{t.smallViewportTitle}</div>
          <p className="text-sm text-text-muted max-w-sm mx-auto">{t.smallViewportText}</p>
        </div>
      </div>
      <div ref={appRef} className="app-shell w-screen h-screen flex flex-col text-text font-sans overflow-hidden relative" style={themeVars}>
      <HeaderBar
        thumbSize={thumbSize} setThumbSize={setThumbSize}
        filters={filters} setFilters={setFilters}
        onSources={() => setShowSources(s => !s)}
        onExport={() => {
          // Печатный HTML-документ вместо прежнего `document.write` в пустое
          // окно: тот собирал разметку конкатенацией без экранирования и
          // блокируется частью браузеров как устаревший API.
          const ok = openPrintReport({
            photos: filteredPhotos, totalPhotos: photos.length,
            dataMode, dataMessage,
            filters: { ...filters, eras: [...filters.eras], hypotheses: [...filters.hypotheses],
              flags: [...filters.flags], buckets: [...filters.buckets] },
            playheadT, currentEra,
            events: [],
          });
          if (!ok) window.alert(t.printBlocked);
        }}
        onExportJson={() => exportAnalysisJson({
          photos: filteredPhotos, totalPhotos: photos.length, dataMode, dataMessage,
          filters: {
            dataset: filters.dataset, bucketFilter: filters.bucketFilter, search: filters.search,
            showOnlyAnomalies: filters.showOnlyAnomalies, hideLowQuality: filters.hideLowQuality,
            confidenceThreshold: filters.confidenceThreshold,
            eras: [...filters.eras], hypotheses: [...filters.hypotheses],
            flags: [...filters.flags], buckets: [...filters.buckets],
          },
        })}
        onToggleTheme={() => setTheme(t => t === "dark" ? "light" : "dark")}
        theme={theme}
        viewMode={viewMode} setViewMode={setViewMode}
        stats={stats} dataMode={dataMode} dataMessage={dataMessage} lastRunLabel={lastRunLabel}
        onFixCapsule={() => exportFixCapsule(selectedPhoto, dataMode)}
        onRefresh={() => void refreshTimeline()}
        refreshing={timelineRefreshing}
        backendUp={backendUp}
        leftPanelOpen={leftPanelOpen}
        onToggleLeftPanel={() => setLeftPanelOpen(!leftPanelOpen)}
        onOpenFilters={() => setShowFilters(true)}
        onOpenSettings={() => setShowSettings(true)}
        onToggleLanguage={() => setLanguage(language === "ru" ? "en" : "ru")}
        language={language}
        onShowMorphPlayer={() => setShowMorphPlayer(true)}
      />

      {timelineError && (
        <div role="alert" className="flex-shrink-0 bg-critical/15 border-b border-critical px-3 py-1.5 font-mono text-[10px] text-critical flex items-start gap-2">
          <Icon name="alert-triangle" size={12} color="#ff3b30" className="mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            <span className="font-semibold">{t.timelineLoadFailed}</span>
            <span className="text-text-faint"> · {timelineError}</span>
          </div>
          <button onClick={() => void refreshTimeline()} className="ml-auto flex-shrink-0 underline hover:no-underline">
            {t.retry}
          </button>
        </div>
      )}

      {rejectedRows.length > 0 && (
        <div role="alert" className="flex-shrink-0 bg-critical/15 border-b border-critical px-3 py-1.5 font-mono text-[10px] text-critical flex items-start gap-2">
          <Icon name="alert-triangle" size={12} color="#ff3b30" className="mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            <span className="font-semibold">{t.rejectedRowsTitle}: {rejectedRows.length}</span>
            <span className="text-text-muted"> · {t.rejectedRowsHint}</span>
            <div className="text-text-faint truncate">
              {rejectedRows.slice(0, 3).map(r => `${r.id}: ${r.reason}`).join(" · ")}
              {rejectedRows.length > 3 && ` … +${rejectedRows.length - 3}`}
            </div>
          </div>
          <button onClick={() => setRejectedRows([])} aria-label={t.closeLabel}
            className="ml-auto flex-shrink-0 text-text-muted hover:text-text"><Icon name="x" size={12} /></button>
        </div>
      )}

      <div className="flex-1 flex flex-col overflow-hidden relative">
        {viewMode === "FULL" && (
          <div className="flex-1 relative overflow-hidden">
            {/* Таймлайн — центральный элемент ТЗ: его падение не должно
                уносить весь режим вместе с панелями и оверлеями. */}
            <ErrorBoundary label="UnifiedTimeline">
            <UnifiedTimeline
              photos={photosWithHidden}
              filmstripOffset={filmstripOffset}
              setFilmstripOffset={setFilmstripOffset}
              thumbSize={thumbSize}
              playheadT={playheadT}
              onSelectPhoto={setSelectedId}
              selectedId={selectedId}
              onScrubTo={setPlayheadT}
              onPinClick={setShowPin}
              onDoubleClickPhoto={setFullPhoto}
              onRangeSelected={onRangeSelected}
              rangeSelection={compareSide === "B" && rangeB ? rangeB : rangeA}
              highlightIds={highlightIds}
              eraMeta={eraMeta}
              chronoAnomalies={chronoAnomalies}
            />
            </ErrorBoundary>

            {(rangeA || rangeB) && !showCompare && (
              <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 bg-surface-2 border border-border-strong shadow-2xl flex items-center gap-1 p-1 rounded">
                <button onClick={() => setShowCompare(true)} className="px-3 py-1.5 font-mono text-[10px] tracking-forensic bg-info/20 hover:bg-info/40 border border-info/40 flex items-center gap-1.5">
                  <Icon name="compare" size={12} /> {t.compareSelected}
                </button>
                <button onClick={() => {
                  const photos = (rangeA?.photos || []).concat(rangeB?.photos || []);
                  alert(`${t.exportRange}\n${photos.length} фото\n${photos.slice(0, 5).map(p => p.id).join(", ")}…`);
                }} className="px-3 py-1.5 font-mono text-[10px] tracking-forensic bg-surface-3 hover:bg-surface border border-border flex items-center gap-1.5">
                  <Icon name="download" size={12} /> {t.exportRange}
                </button>
                <button onClick={() => {
                  const ids = new Set(hiddenIds);
                  (rangeA?.photos || []).concat(rangeB?.photos || []).forEach(p => ids.add(p.id));
                  setHiddenIds(ids);
                }} className="px-3 py-1.5 font-mono text-[10px] tracking-forensic bg-surface-3 hover:bg-critical/30 border border-border flex items-center gap-1.5">
                  <Icon name="eye-off" size={12} /> {t.hideRange}
                </button>
                <button onClick={() => { setRangeA(null); setRangeB(null); setShowCompare(false); }} className="px-2 py-1.5 font-mono text-[10px] text-text-muted hover:text-text">
                  <Icon name="x" size={12} />
                </button>
              </div>
            )}

            <div
              className="absolute top-0 bottom-0 left-0 transition-all duration-200 z-30"
              style={{ transform: leftPanelOpen ? "translateX(0)" : "translateX(-100%)" }}
            >
              {leftPanelOpen && (
                <ErrorBoundary label="LeftPanel" onReset={() => setLeftPanelOpen(false)}>
                <LeftPanel
                  photo={selectedPhoto}
                  photos={photosWithHidden}
                  onClose={() => { setSelectedId(null); setLeftPanelOpen(false); }}
                  onHide={toggleHide}
                  onExpandMesh={() => selectedPhoto && setFullPhoto(selectedPhoto)}
                />
                </ErrorBoundary>
              )}
            </div>

            {!leftPanelOpen && (
              <button onClick={() => setLeftPanelOpen(true)}
                className="absolute top-3 left-2 z-30 w-8 h-20 bg-surface-2 border border-border-strong flex flex-col items-center justify-center gap-2 hover:bg-surface-3" title={t.detailPanel}>
                <Icon name="panel-left" size={14} />
                <div className="font-mono text-[8px] tracking-forensic text-text-muted [writing-mode:vertical-rl] rotate-180">{t.detailsRail}</div>
              </button>
            )}
          </div>
        )}

        {viewMode === "CLUSTER" && (
          <ErrorBoundary label="ClusterView">
            <ClusterView photos={photosWithHidden} onSelectPhoto={setSelectedId} onDoubleClick={setFullPhoto} selectedId={selectedId} />
          </ErrorBoundary>
        )}

        {/* Колонки по сегментам хронологии с распределением гипотез.
            Компонент был реализован, но не подключён ни к одному режиму. */}
        {viewMode === "ERA_COMPARE" && (
          <ErrorBoundary label="EraCompareView">
            <EraCompareView photos={photosWithHidden} onSelectPhoto={setSelectedId} onDoubleClick={setFullPhoto} selectedId={selectedId} />
          </ErrorBoundary>
        )}

        {isAnalysisView(viewMode) && (
          <ErrorBoundary label="AnalysisViews">
            <AnalysisViews kind={viewMode} photos={photosWithHidden} selected={selectedPhoto} onSelect={setSelectedId} onInspect={setFullPhoto} onCompare={() => rangeA && setShowCompare(true)} chronoAnomalies={chronoAnomalies} />
          </ErrorBoundary>
        )}

        {viewMode === "PAIR_COMPARE" && <ErrorBoundary label="PairCompareView"><PairCompareView photos={photosWithHidden} /></ErrorBoundary>}
        {viewMode === "CALIBRATION" && <ErrorBoundary label="CalibrationView"><CalibrationView /></ErrorBoundary>}
        {/* Категория I карты размещения ключей: свойства вычислительного
            прогона (охват, ограничения, целостность артефактов). Отдельный
            раздел, а не блок в STATS: STATS описывает выборку фотографий. */}
        {viewMode === "RUN" && <ErrorBoundary label="RunSummaryView"><RunSummaryView /></ErrorBoundary>}
        {/* Stage 3 — единственный этап пайплайна, итог которого не был
            виден в рабочей станции: отчёт существовал только файлом на диске. */}
        {viewMode === "REPORT" && <ErrorBoundary label="ReportView"><ReportView /></ErrorBoundary>}
        {viewMode === "DATA" && <ErrorBoundary label="DataManagementView"><DataManagementView /></ErrorBoundary>}
      </div>

      <CurrentStateBar era={currentEra} eraMeta={eraMeta} playheadT={playheadT} photos={photosWithHidden} hiddenCount={hiddenIds.size} thumbSize={thumbSize} />

      <HypothesisLegend open={hypLegendOpen} onToggle={() => setHypLegendOpen(!hypLegendOpen)}
        anomalyStats={anomalyCounts(photosWithHidden)} />

      {showFilters && <FilterPanel filters={filters} setFilters={setFilters} eraMeta={eraMeta} onClose={() => setShowFilters(false)} />}
      {showPin && <PinCard pin={showPin} onClose={() => setShowPin(null)} onJump={() => { setPlayheadT(showPin.t); setShowPin(null); }} />}
      {showSources && <SourcesPanel onClose={() => setShowSources(false)} onJump={tt => setPlayheadT(tt)} />}
      {fullPhoto && (
        <ErrorBoundary label="FullPhotoOverlay" onReset={() => setFullPhoto(null)}>
          <FullPhotoOverlay photo={fullPhoto} onClose={() => setFullPhoto(null)} />
        </ErrorBoundary>
      )}
      {showCompare && rangeA && (
        <ErrorBoundary label="ComparisonPanel" onReset={() => setShowCompare(false)}>
          <ComparisonPanel rangeA={rangeA} rangeB={rangeB} onClose={() => setShowCompare(false)} activeSide={compareSide} onSetSide={setCompareSide} />
        </ErrorBoundary>
      )}
      {showSettings && (
        <ErrorBoundary label="SettingsModal" onReset={() => setShowSettings(false)}>
          <SettingsModal onClose={() => setShowSettings(false)} onApplied={applySettings} />
        </ErrorBoundary>
      )}
      {showMorphPlayer && (
        <MorphPlayerOverlay photos={photosWithHidden} onClose={() => setShowMorphPlayer(false)} />
      )}
      </div>
    </BaselineContext.Provider>
  );
}

function HeaderBar({ thumbSize, setThumbSize, filters, setFilters, onSources, onExport, onExportJson, onToggleTheme, theme, viewMode, setViewMode, stats, dataMode, dataMessage, lastRunLabel, onFixCapsule, onRefresh, refreshing, backendUp, leftPanelOpen, onToggleLeftPanel, onOpenFilters, onOpenSettings, onToggleLanguage, language, onShowMorphPlayer }: HeaderBarProps) {
  return (
    <div data-no-pan className="h-12 bg-surface border-b border-border-strong flex items-center px-3 gap-3 flex-shrink-0">
      <div className="flex items-center gap-2">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <rect x="2" y="2" width="20" height="20" stroke="#dd6974" strokeWidth="1.5" />
          <path d="M6 6 L18 18 M18 6 L6 18" stroke="#4f98a3" strokeWidth="0.6" />
          <circle cx="12" cy="12" r="3" stroke="#fdab43" strokeWidth="0.8" fill="none" />
          <circle cx="12" cy="12" r="1" fill="#ff3b30" />
        </svg>
        <div>
          <div className="font-mono text-xs font-bold tracking-forensic">{t.appName}</div>
          <div className="font-mono text-[8px] text-text-faint -mt-0.5">{t.appSubtitle}</div>
        </div>
      </div>

      <div className="h-6 w-px bg-border" />

      <div className="font-mono text-[10px] text-text-muted whitespace-nowrap">
        <span className="text-text-faint">{t.artifact}</span> <span className="text-info">v2.1.0</span>
        <span className="mx-1.5 text-text-faint">·</span>
        <span className="text-text-faint">{t.photos}</span> <span>{stats.filtered}/{stats.total}</span>
        <span className="mx-1.5 text-text-faint">·</span>
        <span className="text-text-faint">{t.anomalies}</span> <span className="text-critical">{stats.anomalies}</span>
        <span className="mx-1.5 text-text-faint">·</span>
        <span className="text-text-faint">{t.lastRun}</span> <span>{lastRunLabel}</span>
      </div>

      <button className="text-text-muted hover:text-text" title={t.datasetLocked}><Icon name="lock" size={14} /></button>

      <div className="flex-1 min-w-2" />

      <button onClick={onShowMorphPlayer} aria-label="Chronological Morph" className="px-2 py-1 flex items-center gap-1 font-mono text-[10px] tracking-forensic border border-border bg-surface-2 text-text hover:bg-surface-3 transition-colors" title="Play Morph Sequence">
        <Icon name="play" size={11} color="#5591c7" /> MORPH
      </button>

      <button onClick={onToggleLeftPanel} aria-label={t.detailPanel} className={`w-8 h-7 flex items-center justify-center border ${leftPanelOpen ? "bg-info/20 border-info" : "border-border text-text-muted hover:text-text bg-surface-2"}`} title={t.detailPanel}>
        <Icon name="panel-left" size={14} />
      </button>

      <div className="flex items-center gap-px bg-surface-2 border border-border overflow-hidden">
        {(["main", "calibration"] as const).map(d => (
          <button key={d} onClick={() => setFilters(prev => ({ ...prev, dataset: d }))}
            aria-pressed={filters.dataset === d}
            className={`px-2 py-1 font-mono text-[10px] tracking-forensic ${filters.dataset === d ? "bg-info/30 text-text" : "text-text-muted hover:text-text"}`}>
            {d === "main" ? t.datasetMain : t.datasetCalibration}
          </button>
        ))}
      </div>

      <select value={filters.bucketFilter} aria-label={t.bucket}
        onChange={e => {
          const value = e.target.value;
          const next: "all" | PoseBucket = value === "all" ? "all" : (value as PoseBucket);
          setFilters(prev => ({ ...prev, bucketFilter: next }));
        }}
        className="bg-surface-2 border border-border px-2 py-1 font-mono text-[10px] text-text">
        <option value="all">{t.bucket}: {t.bucketAll}</option>
        {POSE_BUCKETS.map((bucket: PoseBucket) => <option key={bucket} value={bucket}>{POSE_LABELS[bucket]}</option>)}
      </select>

      <div className="relative">
        <Icon name="search" size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="text" placeholder={t.searchPlaceholder}
          value={filters.search}
          onChange={e => { const value = e.target.value; setFilters(prev => ({ ...prev, search: value })); }}
          aria-label={t.searchPlaceholder}
          className="bg-surface-2 border border-border pl-7 pr-2 py-1 font-mono text-[10px] text-text w-48 focus:outline-none focus:border-info"
        />
      </div>

      <div className="flex items-center gap-px bg-surface-2 border border-border overflow-hidden">
        {([
          { v: "FULL", l: t.navTimeline },
          { v: "MATRIX", l: t.navMatrix },
          { v: "CLUSTER", l: t.navClusters },
          { v: "ERA_COMPARE", l: t.navEraCompare },
          { v: "COMPARE", l: t.navCompare },
          { v: "PAIR_COMPARE", l: t.navPairCompare },
          { v: "INSPECTOR", l: t.navInspector },
          { v: "DRIFT", l: t.navDrift },
          { v: "METRICS", l: t.navMetrics },
          { v: "STATS", l: t.navStats },
          { v: "CALIBRATION", l: t.navCalibration },
          { v: "RUN", l: t.navRunSummary },
          { v: "REPORT", l: t.navReport },
          { v: "DATA", l: t.navData },
        ] satisfies { v: ViewMode; l: string }[]).map(m => (
          <button key={m.v} onClick={() => setViewMode(m.v)} className={`px-2 py-1 font-mono text-[10px] tracking-forensic ${viewMode === m.v ? "bg-info/30 text-text" : "text-text-muted hover:text-text"}`}>{m.l}</button>
        ))}
      </div>

      <button onClick={onOpenSettings} aria-label={t.openSettings} className="px-2 py-1 font-mono text-[10px] tracking-forensic text-text-muted hover:text-text border border-border bg-surface-2 flex items-center gap-1" title={t.openSettings}>
        <Icon name="sliders" size={11} />
      </button>

      <button onClick={onToggleLanguage} aria-label={t.languageToggle} className="px-2 py-1 font-mono text-[10px] tracking-forensic text-text-muted hover:text-text border border-border bg-surface-2" title={t.languageToggle}>
        {language.toUpperCase()}
      </button>

      {/* Индикатор связи с backend (аудит №11): GET /api/v1/health не имел
          ни одного потребителя, и потеря соединения выглядела так же, как
          демо-режим. */}
      {backendUp === false && (
        <div role="status" title={t.backendDownHint}
          className="px-2 py-1 border border-critical/60 text-critical font-mono text-[9px] tracking-forensic flex items-center gap-1">
          <Icon name="alert-octagon" size={10} color="#ff3b30" />
          {t.backendDown}
        </div>
      )}

      {/* Ручное обновление (аудит №26): после задания извлечения или
          пересчёта метрик данные на диске меняются, а интерфейс показывал
          снимок момента загрузки страницы. */}
      <button onClick={onRefresh} disabled={refreshing}
        aria-label={t.refreshTimeline} title={t.refreshTimelineHint}
        className="px-2 py-1 border border-border font-mono text-[9px] tracking-forensic text-text-muted hover:text-text disabled:opacity-40 flex items-center gap-1">
        <Icon name="rotate" size={10} />
        {refreshing ? t.refreshing : t.refreshTimeline}
      </button>
      <div title={dataMessage} className={`px-2 py-1 border font-mono text-[9px] tracking-forensic ${dataMode === "research" ? "border-nominal/50 text-nominal" : dataMode === "loading" ? "border-info/50 text-info" : "border-warning/50 text-warning"}`}>{dataMode === "research" ? t.dataModeResearch : dataMode === "loading" ? t.dataModeLoading : "ERROR"} · {t.notAVerdict}</div>

      <button onClick={onFixCapsule} className="px-2 py-1 font-mono text-[9px] tracking-forensic border border-info/50 bg-info/10 hover:bg-info/25">FIX CAPSULE</button>

      <button onClick={onOpenFilters} className="px-2 py-1 font-mono text-[10px] tracking-forensic text-text-muted hover:text-text border border-border bg-surface-2 flex items-center gap-1">
        <Icon name="filter" size={11} /> {t.filters}
      </button>
      <button onClick={onSources} className="px-2 py-1 font-mono text-[10px] tracking-forensic text-text-muted hover:text-text border border-border bg-surface-2 flex items-center gap-1">
        <Icon name="file-text" size={11} /> {t.sources}
      </button>
      <button onClick={onExport} className="px-2 py-1 font-mono text-[10px] tracking-forensic bg-info/20 hover:bg-info/40 border border-info/40 text-text flex items-center gap-1">
        <Icon name="download" size={11} /> {t.exportReport}
      </button>
      <button onClick={onExportJson} title={t.exportJsonHint}
        className="px-2 py-1 font-mono text-[10px] tracking-forensic bg-surface-2 hover:bg-surface-3 border border-border text-text flex items-center gap-1">
        <Icon name="file-text" size={11} /> {t.exportJson}
      </button>

      <button onClick={onToggleTheme} aria-label={t.toggleTheme} className="w-7 h-7 flex items-center justify-center border border-border bg-surface-2 text-text-muted hover:text-text" title={t.toggleTheme}>
        <Icon name={theme === "dark" ? "sun" : "moon"} size={13} />
      </button>

      {/* Thumb size control (zoom for filmstrip + tracks) */}
      <div className="flex items-center gap-px bg-surface-2 border border-border" title={t.thumbSizeTitle}>
        <button onClick={() => setThumbSize(Math.max(20, thumbSize - 10))} className="w-6 h-6 flex items-center justify-center text-text-muted hover:text-text"><Icon name="minus" size={11} /></button>
        <span className="font-mono text-[10px] w-10 text-center">{thumbSize}px</span>
        <button onClick={() => setThumbSize(Math.min(120, thumbSize + 10))} className="w-6 h-6 flex items-center justify-center text-text-muted hover:text-text"><Icon name="plus" size={11} /></button>
        <button onClick={() => setThumbSize(50)} className="px-1.5 py-0.5 font-mono text-[9px] text-text-muted hover:text-text border-l border-border">50</button>
      </div>
    </div>
  );
}

function CurrentStateBar({ era, eraMeta, playheadT, photos, hiddenCount, thumbSize }: { era: Era; eraMeta: Record<string, EraMeta>; playheadT: number; photos: Photo[]; hiddenCount: number; thumbSize: number }) {
  const baseline = useBaseline();
  const meta = eraMeta[era] ?? { label: era, color: "#797876", short: era, start: "", end: "" };
  const nearest = useMemo(() => {
    let best: Photo | null = null; let bd = Infinity;
    for (const p of photos) { const d = Math.abs(p.t - playheadT); if (d < bd) { bd = d; best = p; } }
    return best;
  }, [playheadT, photos]);

  return (
    <div data-no-pan className="h-6 bg-surface-2 border-t border-border flex items-center px-2 gap-3 flex-shrink-0 font-mono text-[10px]">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
        <span className="text-text-muted tracking-forensic">{t.era}</span>
        <span style={{ color: meta.color }}>{t.eraNames[era] ?? meta.label}</span>
      </div>
      <div className="h-3 w-px bg-border" />
      <div className="text-text-muted">{t.playhead} <span className="text-text">{new Date(playheadT).toLocaleDateString("ru-RU")}</span></div>
      {nearest && (
        <>
          <div className="h-3 w-px bg-border" />
          <div className="text-text-muted">{t.nearest} <span className="text-text">{nearest.id}</span> · <span style={{ color: HYPOTHESIS_COLORS[nearest.dominant] }}>{nearest.dominant}</span> · <span style={{ color: FUZZY_COLORS[nearest.fuzzy] }}>{t.fuzzy[nearest.fuzzy]}</span></div>
        </>
      )}
      <div className="flex-1" />
      {hiddenCount > 0 && <div className="text-warning">{hiddenCount} {t.hidden}</div>}
      <div className="h-3 w-px bg-border" />
      <div title={t.baselineTooltip} className="flex items-center gap-1">
        <span className="text-text-muted">{t.baselineLabel}</span>
        <span style={{ color: baseline.sufficient ? "#6daa45" : "#e8af34" }}>
          {baseline.source === "pipeline" ? t.baselineFromApi : "baseline unavailable"}
          {baseline.baselineEra ? ` · ${baseline.baselineEra}` : ""}
          {` · n=${baseline.sampleSize}`}
        </span>
        {!baseline.sufficient && <span className="text-warning">· {t.baselineInsufficient}</span>}
      </div>
      <div className="h-3 w-px bg-border" />
      <div className="text-text-faint">{t.cardSizeLabel} {thumbSize}px</div>
      <div className="h-3 w-px bg-border" />
      <div className="text-text-faint">{t.shortcutsHint}</div>
    </div>
  );
}

function HypothesisLegend({ open, onToggle, anomalyStats }: {
  open: boolean; onToggle: () => void;
  anomalyStats: { kind: AnomalyKind; count: number }[];
}) {
  return (
    <div data-no-pan className="absolute right-3 bottom-9 z-50">
      {open && (
        <div className="mb-2 w-80 bg-surface-2 border border-border-strong p-3 shadow-2xl font-mono text-[10px]">
          {/* Расшифровка иконок дорожки аномалий: без неё маркеры нечитаемы. */}
          {anomalyStats.length > 0 && (
            <div className="mb-3 pb-3 border-b border-border">
              <div className="font-display tracking-forensic mb-2 text-text">{t.anomalyTrackLabel}</div>
              <div className="space-y-1">
                {anomalyStats.filter(s => !isQualityFlag(s.kind)).map(({ kind, count }) => (
                  <div key={kind.id} className="flex items-center gap-2" title={t[kind.reasonKey as keyof typeof t] as string}>
                    <span className="flex items-center justify-center flex-shrink-0"
                      style={{
                        width: 14, height: 14,
                        background: `${SEVERITY_COLOR[kind.severity]}22`,
                        border: `1px solid ${SEVERITY_COLOR[kind.severity]}`,
                      }}>
                      <Icon name={kind.icon} size={9} color={SEVERITY_COLOR[kind.severity]} strokeWidth={2.2} />
                    </span>
                    <span className="flex-1 truncate" style={{ color: SEVERITY_COLOR[kind.severity] }}>
                      {(t[kind.labelKey as keyof typeof t] as string) ?? kind.id}
                    </span>
                    <span className="text-text-muted">{count}</span>
                  </div>
                ))}
              </div>
              {/* Ограничения применимости — отдельной группой, чтобы их не
                  читали как признаки подмены личности. */}
              {anomalyStats.some(s => isQualityFlag(s.kind)) && (
                <div className="mt-2 pt-2 border-t border-border/60">
                  <div className="text-text-faint text-[9px] tracking-forensic mb-1">{t.anomQualityGroup}</div>
                  <div className="space-y-1">
                    {anomalyStats.filter(s => isQualityFlag(s.kind)).map(({ kind, count }) => (
                      <div key={kind.id} className="flex items-center gap-2" title={t[kind.reasonKey as keyof typeof t] as string}>
                        <span className="flex items-center justify-center flex-shrink-0"
                          style={{ width: 14, height: 14, border: `1px solid ${SEVERITY_COLOR.quality}` }}>
                          <Icon name={kind.icon} size={9} color={SEVERITY_COLOR.quality} strokeWidth={2.2} />
                        </span>
                        <span className="flex-1 truncate" style={{ color: SEVERITY_COLOR.quality }}>
                          {(t[kind.labelKey as keyof typeof t] as string) ?? kind.id}
                        </span>
                        <span className="text-text-muted">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <div className="font-display tracking-forensic mb-2 text-text">{t.hypTitle}</div>
          <p className="text-text-muted mb-2 leading-snug">{t.hypIntro}</p>
          <div className="space-y-1.5 mb-2">
            <div><span style={{ color: HYPOTHESIS_COLORS.H0 }}>H0</span> · {t.hypH0}</div>
            <div><span style={{ color: HYPOTHESIS_COLORS.H1 }}>H1</span> · {t.hypH1}</div>
            <div><span style={{ color: HYPOTHESIS_COLORS.H2 }}>H2</span> · {t.hypH2}</div>
          </div>
          <div className="text-text-faint">{t.hypFlags}</div>
        </div>
      )}
      <button onClick={onToggle} className="bg-surface-2 border border-border-strong w-36 p-2 hover:border-info shadow-lg">
        <div className="font-display text-[9px] tracking-forensic text-text-muted mb-1">{t.hypShort}</div>
        <div className="space-y-1 font-mono text-[10px]">
          {(["H0", "H1", "H2"] as Hypothesis[]).map(h => (
            <div key={h} className="flex items-center gap-2">
              <div className="w-6 h-2" style={{ background: HYPOTHESIS_COLORS[h] }} />
              <span style={{ color: HYPOTHESIS_COLORS[h] }}>{h}</span>
              <span className="text-text-muted text-[9px] truncate">{t.hypothesisShort[h]}</span>
            </div>
          ))}
        </div>
      </button>
    </div>
  );
}

function FilterPanel({ filters, setFilters, eraMeta, onClose }: { filters: Filters; setFilters: (f: Filters) => void; eraMeta: Record<string, EraMeta>; onClose: () => void }) {
  // Focus trap + Escape + возврат фокуса на кнопку «Фильтры».
  const dialogRef = useModal<HTMLDivElement>(onClose);
  const eras: Era[] = Object.keys(eraMeta);
  const hyps: Hypothesis[] = ["H0", "H1", "H2"];
  const buckets: PoseBucket[] = POSE_BUCKETS;

  const toggle = <T,>(set: Set<T>, v: T): Set<T> => {
    const n = new Set(set); if (n.has(v)) n.delete(v); else n.add(v); return n;
  };

  return (
    <div data-no-pan className="absolute inset-0 z-[60] flex items-center justify-center bg-black/60" onClick={onClose}>
      <div ref={dialogRef} {...modalProps(t.filtersDialogLabel)}
        className="bg-surface border border-border-strong w-[680px] p-5 shadow-2xl outline-none" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4">
          <div className="font-display text-lg tracking-forensic flex items-center gap-2"><Icon name="filter" size={16} /> {t.filtersTitle}</div>
          <button onClick={onClose} aria-label={t.closeLabel} className="text-text-muted hover:text-text"><Icon name="x" size={18} /></button>
        </div>

        <div className="grid grid-cols-2 gap-5">
          <div>
            <Section title={t.sectionToggles}>
              <Check label={t.showOnlyAnomalies} v={filters.showOnlyAnomalies} onChange={v => setFilters({ ...filters, showOnlyAnomalies: v })} />
              <Check label={t.hideLowQuality} v={filters.hideLowQuality} onChange={v => setFilters({ ...filters, hideLowQuality: v })} />
            </Section>
            <Section title={t.sectionConfidence}>
              <div className="flex items-center gap-2">
                <input type="range" min={0} max={1} step={0.05} value={filters.confidenceThreshold}
                  onChange={e => setFilters({ ...filters, confidenceThreshold: +e.target.value })}
                  aria-label={t.sectionConfidence} className="flex-1" />
                <span className="font-mono text-[10px] w-8">{filters.confidenceThreshold.toFixed(2)}</span>
              </div>
            </Section>
            <Section title={t.sectionEra}>
              {eras.map(e => (
                <Check key={e} label={t.eraNames[e] ?? eraMeta[e].label} color={eraMeta[e].color} v={filters.eras.has(e)}
                  onChange={() => setFilters({ ...filters, eras: toggle(filters.eras, e) })} />
              ))}
            </Section>
          </div>

          <div>
            <Section title={t.sectionHyp}>
              {hyps.map(h => (
                <Check key={h} label={`${h} · ${t.hypothesisShort[h]}`} color={HYPOTHESIS_COLORS[h]} v={filters.hypotheses.has(h)}
                  onChange={() => setFilters({ ...filters, hypotheses: toggle(filters.hypotheses, h) })} />
              ))}
            </Section>
            <Section title={t.sectionFlags}>
              {ALL_FLAGS.map(f => (
                <Check key={f} label={f} v={filters.flags.has(f)}
                  onChange={() => setFilters({ ...filters, flags: toggle(filters.flags, f) })} />
              ))}
            </Section>
            <Section title={t.sectionPose}>
              {buckets.map(b => (
                <Check key={b} label={b} v={filters.buckets.has(b)}
                  onChange={() => setFilters({ ...filters, buckets: toggle(filters.buckets, b) })} />
              ))}
            </Section>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-border flex justify-between font-mono text-[10px] text-text-muted">
          <div>{t.pressEsc} <span className="text-text">ESC</span> {t.toClose} · <span className="text-text">F</span> {t.toOpen} · <span className="text-text">C</span> {t.toCompare}</div>
          <button onClick={() => setFilters({
            ...filters,
            showOnlyAnomalies: false, confidenceThreshold: 0, hideLowQuality: false,
            eras: new Set(eras), hypotheses: new Set(hyps), flags: new Set(), buckets: new Set(buckets),
          })} className="text-info hover:underline">{t.resetAll}</button>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-2">{title}</div>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function Check({ label, v, onChange, color }: { label: string; v: boolean; onChange: (v: boolean) => void; color?: string }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer text-[11px] font-mono" onClick={() => onChange(!v)}>
      <div className={`w-3.5 h-3.5 border ${v ? "bg-info border-info" : "border-border-strong"} flex items-center justify-center`}>
        {v && <Icon name="check" size={10} color="#fff" strokeWidth={3} />}
      </div>
      {color && <div className="w-2 h-2" style={{ background: color }} />}
      <span className="text-text">{label}</span>
    </label>
  );
}

function PinCard({ pin, onClose, onJump }: { pin: EventPin; onClose: () => void; onJump: () => void }) {
  return (
    <div data-no-pan className="absolute right-3 top-16 z-50 w-96 bg-surface border-l-4 shadow-2xl animate-[slideInRight_0.18s_ease-out]" style={{ borderLeftColor: pin.color }}>
      <div className="p-4">
        <div className="flex justify-between items-start mb-2">
          <div className="font-mono text-[9px] text-text-muted tracking-forensic">{t.pinEvent} · {pin.type}</div>
          <button onClick={onClose} aria-label={t.closeLabel} className="text-text-muted hover:text-text"><Icon name="x" size={14} /></button>
        </div>
        <div className="flex items-center gap-2 mb-1">
          <div className="w-7 h-7 flex items-center justify-center" style={{ background: pin.color }}>
            <Icon name={pin.iconName} size={14} color="#0d0d0f" strokeWidth={2.2} />
          </div>
          <div className="font-display text-lg font-semibold" style={{ color: pin.color }}>{pin.title}</div>
        </div>
        <div className="font-mono text-[10px] text-text-muted mb-3">{new Date(pin.t).toLocaleDateString("ru-RU")} · {pin.source}</div>
        <p className="text-sm text-text leading-relaxed mb-3">{pin.tooltip}</p>
        {pin.folkTag && (
          <div className="font-mono text-[10px] italic text-text-muted bg-surface-2 p-2 border-l-2 border-warning">
            ↳ {pin.folkTag}
            <div className="text-text-faint mt-0.5 not-italic">{t.folkDisclaimer}</div>
          </div>
        )}
        <div className="mt-3 pt-3 border-t border-border flex gap-2">
          <button className="flex-1 font-mono text-[10px] py-1.5 bg-surface-2 border border-border hover:bg-surface-3 tracking-forensic flex items-center justify-center gap-1.5">
            <Icon name="external" size={11} /> {t.pinViewSource}
          </button>
          <button onClick={onJump} className="flex-1 font-mono text-[10px] py-1.5 bg-info/20 border border-info/40 hover:bg-info/40 tracking-forensic flex items-center justify-center gap-1.5">
            <Icon name="crosshair" size={11} /> {t.pinJump}
          </button>
        </div>
      </div>
    </div>
  );
}

type SourceFilter = "all" | "Media" | "AI Research" | "Political" | "Forensic";

function SourcesPanel({ onClose, onJump }: { onClose: () => void; onJump: (t: number) => void }) {
  // Боковая панель, а не оверлей: фон остаётся рабочим, поэтому
  // `aria-modal` был бы неверен. Даём имя региону и закрытие по Escape.
  const dialogRef = useModal<HTMLDivElement>(onClose);
  const [filter, setFilter] = useState<SourceFilter>("all");
  const typeMap: Record<string, "Media" | "AI Research" | "Political" | "Forensic"> = {
    DISAPPEARANCE: "Media", POLITICAL: "Political", AI_RESEARCH: "AI Research", REPORT: "Forensic", ERA_START: "Forensic", RTR: "Forensic",
  };
  const typeLabel: Record<string, string> = {
    Media: t.filterMedia, "AI Research": t.filterAI, Political: t.filterPolitical, Forensic: t.filterForensic,
  };
  const list: EventPin[] = ([] as EventPin[]).filter(p => filter === "all" || typeMap[p.type] === filter).sort((a, b) => a.t - b.t);
  const T_MIN = Date.parse("1999-01-01");
  const T_SPAN = Date.parse("2026-06-30") - T_MIN;

  return (
    <div ref={dialogRef} data-no-pan role="complementary" aria-label={t.sourcesDialogLabel} tabIndex={-1}
      className="absolute right-0 top-12 bottom-0 z-40 w-[360px] bg-surface border-l border-border-strong shadow-2xl flex flex-col animate-[slideInRight_0.18s_ease-out] outline-none">
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="font-display tracking-forensic flex items-center gap-2"><Icon name="file-text" size={14} /> {t.sourcesTitle}</div>
        <button onClick={onClose} aria-label={t.closeLabel} className="text-text-muted hover:text-text"><Icon name="x" size={14} /></button>
      </div>
      <div className="flex gap-1 p-2 border-b border-border bg-surface-2">
        {([
          { v: "all", l: t.filterAll },
          { v: "Media", l: t.filterMedia },
          { v: "AI Research", l: t.filterAI },
          { v: "Political", l: t.filterPolitical },
          { v: "Forensic", l: t.filterForensic },
        ] satisfies { v: SourceFilter; l: string }[]).map(f => (
          <button key={f.v} onClick={() => setFilter(f.v)}
            className={`flex-1 px-1 py-1 font-mono text-[9px] tracking-forensic border ${filter === f.v ? "bg-info/20 border-info text-text" : "border-border text-text-muted hover:text-text"}`}>
            {f.l}
          </button>
        ))}
      </div>
      <div className="px-3 py-2 border-b border-border">
        <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1">{t.sourcesTimeline}</div>
        <div className="relative h-6 bg-surface-2 border border-border">
          {([] as EventPin[]).map(p => {
            const x = ((p.t - T_MIN) / T_SPAN) * 100;
            return <div key={p.id} className="absolute top-0 bottom-0 w-0.5 cursor-pointer hover:w-1 transition-all" style={{ left: `${x}%`, background: p.color }} title={p.title} onClick={() => onJump(p.t)} />;
          })}
        </div>
        <div className="flex justify-between font-mono text-[8px] text-text-faint mt-0.5">
          <span>1999</span><span>2012</span><span>2024</span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto" data-scroll>
        {list.length === 0 && (
          <div className="p-4 font-mono text-[10px] text-text-muted">{t.noEventsToShow}</div>
        )}
        {list.map(p => (
          <div key={p.id} onClick={() => onJump(p.t)} className="p-3 border-b border-border hover:bg-surface-2 cursor-pointer">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: p.color }} />
              <div className="font-mono text-[10px] text-text-muted">{new Date(p.t).toLocaleDateString("ru-RU")}</div>
              <div className="ml-auto font-mono text-[8px] px-1.5 py-0.5 bg-surface-3 text-text-muted">{typeLabel[typeMap[p.type]]}</div>
            </div>
            <div className="font-display text-xs font-semibold mb-1" style={{ color: p.color }}>{p.title}</div>
            <div className="font-mono text-[10px] text-text leading-relaxed mb-1">{p.tooltip}</div>
            <div className="font-mono text-[9px] text-text-faint">— {p.source}</div>
            {p.folkTag && <div className="font-mono text-[9px] italic text-text-muted mt-1">↳ {p.folkTag}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
