import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowLeftRight,
  Check,
  Filter,
  Hand,
  Maximize2,
  Minus,
  Plus,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { useTimeline } from "../../shared/api/queries";
import { type ResearchPhoto } from "../../shared/researchApi";
import { isFinding, substantiveFlags } from "../../shared/findings";
import { poseLabel } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";
import { PhotoImage } from "../../shared/ui/PhotoImage";
import { METRIC_COLORS } from "../../shared/ui/tokenColors";
import { frameLabel } from "../../shared/blind";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import {
  METRIC_GROUP_LABELS,
  metricById,
  type MetricDescriptor,
} from "../../shared/metrics";
import { TrackCanvas, type TrackSpec } from "./TrackCanvas";
import { pickRepresentatives } from "./representative";
import {
  boundsOf,
  clampViewport,
  fitViewport,
  panBy,
  ticksFor,
  timeOf,
  timeToRatio,
  xToTime,
  zoomAt,
  zoomLevel,
  type Viewport,
} from "./viewport";
import { PoseLanes } from "./PoseLanes";
import { ExportMenu } from "./ExportMenu";
import { FiltersMenu } from "./FiltersMenu";
import { MetricsMenu } from "./MetricsMenu";
import { ANOMALY_LANES, collectAnomalies } from "./anomalies";
import { exclusionReasons } from "./filters";
import styles from "./timeline.module.css";

const pct = (v: number | null | undefined) => (v == null ? "н/д" : `${Math.round(v * 100)}%`);
const metric = (v: number | null | undefined) => (v == null ? "н/д" : v.toFixed(1));
const scalar = (v: number | null | undefined) => (v == null ? "н/д" : v.toFixed(2));

/**
 * Дорожки метрик. Нормализация переводит величину в [0,1] для вертикальной
 * оси; сама величина при этом не изменяется и в подсказке показывается как есть.
 */
/**
 * Дорожка строится по описанию метрики из каталога: подпись, единица и статус
 * берутся оттуда же, откуда их читает меню, поэтому легенда дорожки не может
 * разойтись с легендой в списке метрик.
 *
 * Нормализация переводит величину в [0,1] для вертикальной оси; сама величина
 * не изменяется и в подсказке показывается как есть. Для метрик без
 * объявленного диапазона он считается по видимым данным — иначе дорожка
 * z-оценок с размахом в доли сигмы выглядела бы прямой линией.
 */
function trackFor(
  descriptor: MetricDescriptor,
  photos: readonly ResearchPhoto[],
): TrackSpec {
  let lo: number;
  let hi: number;
  if (descriptor.domain) {
    [lo, hi] = descriptor.domain;
  } else {
    lo = Number.POSITIVE_INFINITY;
    hi = Number.NEGATIVE_INFINITY;
    for (const photo of photos) {
      const value = descriptor.valueOf(photo);
      if (value === null) continue;
      if (value < lo) lo = value;
      if (value > hi) hi = value;
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
      lo = 0;
      hi = 1;
    }
    if (lo === hi) {
      lo -= 0.5;
      hi += 0.5;
    }
  }
  const span = hi - lo || 1;
  const digits = Math.abs(hi) >= 100 ? 0 : Math.abs(hi) >= 10 ? 1 : 2;
  return {
    key: descriptor.id,
    label: descriptor.id === "quality"
      ? "КАЧЕСТВО"
      : `${METRIC_GROUP_LABELS[descriptor.group].toUpperCase()} · ${descriptor.label.toUpperCase()}`,
    range: `${lo.toFixed(digits)} · ${((lo + hi) / 2).toFixed(digits)} · ${hi.toFixed(digits)}${descriptor.unit ?? ""}`,
    color: METRIC_COLORS[descriptor.id] ?? "var(--text-muted)",
    value: descriptor.valueOf,
    normalize: (v) => (v - lo) / span,
  };
}

const TRACK_HEIGHT = 68;
/** Столбцов плотности на минимапе: достаточно для формы распределения. */
const DENSITY_BUCKETS = 160;
const THUMB_SLOT = 62;
/** Ширина колонки подписей: должна совпадать с grid-template-columns в .row. */
const LABEL_COLUMN_PX = 136;
const ANOMALY_GLYPHS: Record<string, string> = {
  persistent_change: "◆",
  return: "↩",
  change_point: "╳",
  rapid_rate: "↗",
  same_day: "▦",
  provenance: "⌁",
  review: "!",
};

export function TimelinePage() {
  const query = useTimeline();
  const areaRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; viewport: Viewport } | null>(null);
  const [areaWidth, setAreaWidth] = useState(1000);
  const [hover, setHover] = useState<{ time: number; x: number } | null>(null);

  const {
    activePose,
    setActivePose,
    qualityThreshold,
    mouthThreshold,
    poseAngleThreshold,
    search,
    setSearch,
    findingsMode,
    multiPose,
    setMultiPose,
    visibleMetrics,
    setVisibleMetrics,
    selectedPhoto: selected,
    setSelectedPhoto: setSelected,
    pairA: aId,
    pairB: bId,
    assignToPair,
    swapPair,
    clearPair,
    blindMode,
  } = useAnalysisStore();

  const rawPhotos = useMemo(() => query.data?.photos ?? [], [query.data]);
  const stage = resolveStage(query.data);

  /**
   * Время каждого кадра считается один раз. Кадры без даты на шкалу не
   * попадают: подставлять им начало диапазона значило бы утверждать дату,
   * которой нет.
   */
  const times = useMemo(() => {
    const map = new Map<string, number>();
    for (const photo of rawPhotos) {
      const t = timeOf(photo);
      if (t != null) map.set(photo.id, t);
    }
    return map;
  }, [rawPhotos]);

  const dated = useMemo(
    () =>
      rawPhotos
        .filter((photo) => times.has(photo.id))
        .sort((a, b) => (times.get(a.id) ?? 0) - (times.get(b.id) ?? 0)),
    [rawPhotos, times],
  );
  const undatedCount = rawPhotos.length - dated.length;

  const bounds = useMemo(() => boundsOf(dated), [dated]);

  /**
   * Вьюпорт хранится как «пользовательский выбор или ничего». Пока выбора нет,
   * показывается весь диапазон, и он выводится прямо при рендере, а не
   * присваивается из эффекта: присваивание в эффекте давало бы лишний каскадный
   * рендер при каждом изменении данных.
   */
  const [userViewport, setUserViewport] = useState<Viewport | null>(null);
  const [handTool, setHandTool] = useState(false);
  const spaceHeld = useRef(false);
  const brushRef = useRef<{ start: number } | null>(null);
  const viewport = useMemo(
    () => (bounds ? (userViewport ? clampViewport(userViewport, bounds) : fitViewport(bounds)) : null),
    [bounds, userViewport],
  );
  const setViewport = setUserViewport;

  useEffect(() => {
    const area = areaRef.current;
    if (!area) return;
    const update = () => setAreaWidth(area.clientWidth || 1000);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(area);
    return () => observer.disconnect();
  }, []);

  const filterSettings = useMemo(
    () => ({
      qualityThreshold,
      poseAngleThreshold,
      mouthThreshold,
      findingsMode,
      search,
      activePose,
      multiPose,
    }),
    [qualityThreshold, poseAngleThreshold, mouthThreshold, findingsMode, search, activePose, multiPose],
  );
  const filtered = useMemo(
    () => dated.filter((photo) => exclusionReasons(photo, filterSettings).length === 0),
    [dated, filterSettings],
  );

  /** §8.8: находки приглушают остальное, а не удаляют его из выборки. */
  const dimmed = useCallback(
    (photo: ResearchPhoto) => findingsMode && !isFinding(photo),
    [findingsMode],
  );

  const order = useMemo(
    () => new Map(dated.map((photo, index) => [photo.id, index])),
    [dated],
  );
  const labelOf = useCallback(
    (photo: ResearchPhoto) =>
      frameLabel({ id: photo.id, date: photo.date, order: order.get(photo.id) ?? 0 }, blindMode),
    [order, blindMode],
  );

  const visibleTracks = useMemo(
    () =>
      visibleMetrics
        .map((key) => metricById(key))
        .filter((d): d is MetricDescriptor => Boolean(d))
        .map((d) => trackFor(d, filtered)),
    [visibleMetrics, filtered],
  );
  const timelineTracks = useMemo(
    () => visibleTracks.filter((track) => !["yaw", "pitch", "roll", "residualYaw"].includes(track.key)),
    [visibleTracks],
  );

  const representatives = useMemo(
    () =>
      viewport
        ? pickRepresentatives(filtered, times, {
            viewport,
            width: Math.max(areaWidth - LABEL_COLUMN_PX, 320),
            slotWidth: THUMB_SLOT,
            pinned: [aId, bId, selected],
          })
        : [],
    [filtered, times, viewport, areaWidth, aId, bId, selected],
  );

  const findings = useMemo(() => filtered.filter(isFinding), [filtered]);
  /**
   * Зафиксированные аномалии Stage 2 — отдельный слой над метриками:
   * читаем уже посчитанные chronology_anomalies, ничего не считаем заново.
   */
  const anomalies = useMemo(
    () => collectAnomalies(query.data, dated, times),
    [query.data, dated, times],
  );

  /**
   * Плотность для минимапы. Раньше здесь рисовался отдельный элемент на каждый
   * кадр — 1909 узлов ради полосы высотой 40 px. Агрегация в фиксированное
   * число бакетов даёт ту же картину распределения за постоянную цену и
   * дополнительно показывает, где сгущаются находки.
   */
  const density = useMemo(() => {
    if (!bounds) return [];
    const span = Math.max(bounds.max - bounds.min, 1);
    const totals = new Array<number>(DENSITY_BUCKETS).fill(0);
    const flagged = new Array<number>(DENSITY_BUCKETS).fill(0);
    for (const photo of dated) {
      const t = times.get(photo.id);
      if (t == null) continue;
      const index = Math.min(
        DENSITY_BUCKETS - 1,
        Math.floor(((t - bounds.min) / span) * DENSITY_BUCKETS),
      );
      totals[index] += 1;
      if (isFinding(photo)) flagged[index] += 1;
    }
    const max = Math.max(...totals, 1);
    return totals
      .map((total, index) => ({
        index,
        total,
        findings: flagged[index],
        height: total === 0 ? 0 : Math.max(12, (total / max) * 100),
      }))
      .filter((cell) => cell.total > 0);
  }, [dated, times, bounds]);
  const inViewport = useMemo(() => {
    if (!viewport) return filtered;
    return filtered.filter((photo) => {
      const ratio = timeToRatio(viewport, times.get(photo.id) ?? 0);
      return ratio >= 0 && ratio <= 1;
    });
  }, [filtered, times, viewport]);

  const selectedPhoto = dated.find((photo) => photo.id === selected) ?? null;

  const [pairRejection, setPairRejection] = useState<string | null>(null);
  const bucketOf = useCallback(
    (id: string) => dated.find((item) => item.id === id)?.bucket,
    [dated],
  );
  const selectPhoto = (photo: ResearchPhoto, asPair = false) => {
    setSelected(photo.id);
    if (asPair) setPairRejection(assignToPair(photo.id, photo.bucket, bucketOf));
  };
  const resetPair = () => {
    clearPair();
    setPairRejection(null);
  };

  /** Зум привязан к курсору. Слушатель не passive — иначе preventDefault молчит. */
  useEffect(() => {
    const area = areaRef.current;
    if (!area) return;
    const onWheel = (event: WheelEvent) => {
      if (!viewport || !bounds) return;
      event.preventDefault();
      const body = area.querySelector<HTMLElement>("[data-timeline-body]");
      const rect = (body ?? area).getBoundingClientRect();
      const localX = event.clientX - rect.left;
      if (event.deltaX !== 0 || event.shiftKey) {
        setViewport(panBy(viewport, bounds, (event.deltaX !== 0 ? event.deltaX : event.deltaY) / rect.width));
      } else {
        const anchor = xToTime(viewport, localX, rect.width);
        setViewport(zoomAt(viewport, bounds, anchor, event.deltaY > 0 ? 1.15 : 0.87));
      }
    };
    area.addEventListener("wheel", onWheel, { passive: false });
    return () => area.removeEventListener("wheel", onWheel);
  }, [viewport, bounds, setViewport]);

  const handleMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!viewport) return;
    const area = event.currentTarget;
    const body = area.querySelector<HTMLElement>("[data-timeline-body]");
    const rect = (body ?? area).getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
    const areaRect = area.getBoundingClientRect();
    const stackX = Math.max(0, Math.min(areaRect.width, event.clientX - areaRect.left));
    setHover({ time: xToTime(viewport, x, rect.width), x: stackX });
  };

  const canPan = (event: React.PointerEvent<HTMLDivElement>) =>
    event.button === 1 || event.altKey || handTool || spaceHeld.current;

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!viewport) return;
    if (!canPan(event) && event.button !== 0) return;
    if (!canPan(event)) return;
    event.preventDefault();
    dragRef.current = { x: event.clientX, viewport };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    handleMove(event);
    const drag = dragRef.current;
    if (!drag || !bounds) return;
    const body = event.currentTarget.querySelector<HTMLElement>("[data-timeline-body]");
    const rect = (body ?? event.currentTarget).getBoundingClientRect();
    setViewport(panBy(drag.viewport, bounds, -(event.clientX - drag.x) / Math.max(rect.width, 1)));
  };

  const handlePointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && /input|textarea|select/i.test(target.tagName)) return;
      if (event.code === "Space") {
        spaceHeld.current = event.type === "keydown";
        if (event.type === "keydown") event.preventDefault();
      }
      if (event.type !== "keydown" || !viewport || !bounds) return;
      const center = (viewport.start + viewport.end) / 2;
      if (event.key === "+" || event.key === "=") setViewport(zoomAt(viewport, bounds, center, 0.8));
      else if (event.key === "-") setViewport(zoomAt(viewport, bounds, center, 1.25));
      else if (event.key === "ArrowLeft") setViewport(panBy(viewport, bounds, -0.15));
      else if (event.key === "ArrowRight") setViewport(panBy(viewport, bounds, 0.15));
      else if (event.key === "0") setViewport(fitViewport(bounds));
      else if (event.key === "h" || event.key === "H") setHandTool((value) => !value);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKey);
    };
  }, [viewport, bounds, setViewport]);

  const onMinimapDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!bounds) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    brushRef.current = { start: bounds.min + ratio * (bounds.max - bounds.min) };
  };
  const onMinimapMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!bounds || !brushRef.current || event.buttons !== 1) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    const end = bounds.min + ratio * (bounds.max - bounds.min);
    const start = Math.min(brushRef.current.start, end);
    const stop = Math.max(brushRef.current.start, end);
    if (stop - start < 86_400_000) return;
    setViewport(clampViewport({ start, end: stop }, bounds));
  };
  const onMinimapUp = () => {
    brushRef.current = null;
  };
  const jumpEra = (startIso: string, endIso: string) => {
    if (!bounds) return;
    const start = Date.parse(startIso);
    const end = Date.parse(endIso);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return;
    setViewport(clampViewport({ start, end: end + 86_400_000 }, bounds));
  };

  const focusPhoto = (photo: ResearchPhoto) => {
    const t = times.get(photo.id);
    if (t == null || !bounds || !viewport) return;
    const span = Math.min(viewport.end - viewport.start, bounds.max - bounds.min);
    setViewport(clampViewport({ start: t - span / 2, end: t + span / 2 }, bounds));
    setSelected(photo.id);
  };

  if (query.isLoading) return <LoadingState text="Загрузка временной шкалы…" />;
  if (query.error)
    return (
      <ErrorState
        title="Временная шкала недоступна"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  if (rawPhotos.length === 0)
    return (
      <EmptyState
        title="Записей нет"
        description="API вернул пустой список фотографий. Проверьте, что Stage 1 выполнен и каталог данных смонтирован."
      />
    );
  if (!bounds || !viewport)
    return (
      <EmptyState
        title="Ни у одной записи нет даты"
        description={`Получено ${rawPhotos.length.toLocaleString("ru-RU")} записей, но ни одна не содержит времени съёмки — построить временную шкалу не по чему.`}
      />
    );

  const ticks = ticksFor(viewport);
  const zoom = zoomLevel(viewport, bounds);

  return (
    <main className={styles.page}>
      <header className={styles.toolbar}>
        <Activity className="h-4 w-4 text-cyan-300" aria-hidden="true" />
        <div>
          <div className="font-mono text-sm font-bold text-cyan-300">
            ТАЙМЛАЙН · {stageLabel(stage)}
          </div>
          <div className="text-2xs text-ink-muted">
            {dated.length.toLocaleString("ru-RU")} с датой
            {undatedCount > 0 && ` · ${undatedCount.toLocaleString("ru-RU")} без даты`} ·{" "}
            {multiPose ? "все ракурсы" : poseLabel(activePose)} · в окне{" "}
            {inViewport.length.toLocaleString("ru-RU")}
          </div>
        </div>

        <label className="ml-auto flex w-56 items-center gap-2 rounded-sm border border-line-default bg-surface-raised px-2 text-xs text-ink-muted">
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="sr-only">Поиск по кадрам</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="ID, дата, flag…"
            className="w-full bg-transparent py-1 text-ink-primary outline-none"
          />
        </label>

        <MetricsMenu photos={dated} visible={visibleMetrics} onChange={setVisibleMetrics} />
        <FiltersMenu photos={dated} />
        <button
          type="button"
          onClick={() => setHandTool((value) => !value)}
          aria-pressed={handTool}
          title="Рука: перетаскивание шкалы. Пробел — временно."
          className={`rounded-sm border p-1 ${handTool ? "border-cyan-500 text-cyan-300" : "border-line-default text-ink-secondary"}`}
        >
          <Hand className="h-3.5 w-3.5" />
        </button>
        {Object.entries(query.data?.era_meta ?? {}).slice(0, 6).map(([id, era]) => (
          <button
            key={id}
            type="button"
            className="rounded-sm border border-line-default px-1.5 py-1 font-mono text-2xs text-ink-muted"
            onClick={() => jumpEra(era.start, era.end)}
          >
            {era.label}
          </button>
        ))}
        <ExportMenu
          photos={inViewport}
          metrics={visibleMetrics}
          viewport={viewport}
          pose={activePose}
          multiPose={multiPose}
          schema={query.data?.schema ?? null}
          sourceMode={query.data?.source_mode ?? null}
        />

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setViewport(zoomAt(viewport, bounds, (viewport.start + viewport.end) / 2, 0.8))}
            aria-label="Приблизить"
            className="rounded-sm border border-line-default p-1 text-ink-secondary"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setViewport(zoomAt(viewport, bounds, (viewport.start + viewport.end) / 2, 1.25))}
            aria-label="Отдалить"
            className="rounded-sm border border-line-default p-1 text-ink-secondary"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setViewport(fitViewport(bounds))}
            aria-label="Показать весь период"
            className="rounded-sm border border-line-default p-1 text-ink-secondary"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
          <span className="font-mono text-2xs text-ink-muted">×{zoom.toFixed(1)}</span>
        </div>

        <button
          type="button"
          onClick={() => void query.refetch()}
          aria-label="Обновить данные"
          className="rounded-sm border border-line-default p-1 text-ink-secondary"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </header>

      <div className={styles.banners}>
        <StageBanner stage={stage} note={query.data?.note} />
        {pairRejection && (
          <div
            role="alert"
            className="rounded-sm border border-amber-500 bg-amber-soft px-3 py-2 text-xs text-amber-300"
          >
            {pairRejection}
          </div>
        )}
        {undatedCount > 0 && (
          <div className="rounded-sm border border-line-default bg-surface-raised px-3 py-2 text-2xs text-ink-muted">
            {undatedCount.toLocaleString("ru-RU")} кадров без даты не размещены на шкале:
            подставлять им время начала диапазона означало бы утверждать дату, которой нет.
          </div>
        )}
      </div>

      <div className={styles.grid}>
        {/* Линейка: шаг подстраивается под масштаб (§8.2). */}
        <div className={styles.row}>
          <div className={styles.rowLabel} aria-hidden="true" />
          <div className="relative h-8">
            <div className={styles.ruler}>
              {ticks.map((tick) => (
                <span
                  key={tick.time}
                  className={`${styles.tickLabel} ${tick.major ? styles.tickLabelMajor : ""}`}
                  style={{ left: `${timeToRatio(viewport, tick.time) * 100}%` }}
                >
                  {tick.label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Дорожки метрик на Canvas. */}
        <div
          ref={areaRef}
          className={styles.trackStack}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          onMouseLeave={() => {
            setHover(null);
          }}
        >
          {/*
            Единая вертикаль через все дорожки (§8.4). Перекрестие внутри
            отдельного canvas обрывается на его границе, и сопоставить значение
            метрики с кадром в соседней дорожке на глаз невозможно.
          */}
          {hover ? (
            <div
              className={styles.playhead}
              style={{
                left: `${hover.x}px`,
              }}
              aria-hidden="true"
            >
              <span className={styles.playheadLabel}>
                {new Date(hover.time).toISOString().slice(0, 10)}
              </span>
            </div>
          ) : null}
          {multiPose ? (
            <PoseLanes
              photos={inViewport}
              times={times}
              viewport={viewport}
              tracks={timelineTracks}
              width={areaWidth}
              activePose={activePose}
              pairA={aId}
              pairB={bId}
              selected={selected}
              dimmed={dimmed}
              hoverTime={hover?.time ?? null}
              onSelect={selectPhoto}
              labelOf={labelOf}
              onFocusPose={(pose) => {
                setActivePose(pose);
                setMultiPose(false);
              }}
            />
          ) : null}

          {!multiPose && timelineTracks.map((track) => (
            <div key={track.key} className={styles.row}>
              <div className={styles.rowLabel}>
                <span>{track.label}</span>
              </div>
              <div className={styles.canvasArea} data-timeline-body>
                <TrackCanvas
                  track={track}
                  photos={inViewport}
                  times={times}
                  viewport={viewport}
                  height={TRACK_HEIGHT}
                  dimmed={dimmed}
                  hoverTime={hover?.time ?? null}
                  selectedId={selected}
                  onPick={selectPhoto}
                />
              </div>
            </div>
          ))}

          {!multiPose && timelineTracks.length === 0 && (
            <div className={styles.row}>
              <div className={styles.rowLabel}>
                <span>МЕТРИКИ</span>
              </div>
              <div className="px-3 py-4 text-2xs text-ink-muted">
                Ни одна дорожка не выбрана. Включите метрики в верхней панели.
              </div>
            </div>
          )}

          {/* Плотная горизонтальная лента миниатюр без подписей и служебных накладок. */}
          <div className={styles.row} hidden={multiPose}>
            <div className={styles.rowLabel}>
              <span>ФОТО</span>
            </div>
            <div className={styles.photoRow} data-timeline-body>
              {representatives.map((photo) => {
                const ratio = timeToRatio(viewport, times.get(photo.id) ?? 0);
                return (
                  <button
                    key={photo.id}
                    type="button"
                    onClick={(event) => selectPhoto(photo, event.shiftKey)}
                    style={{ left: `${ratio * 100}%` }}
                    aria-label={`Кадр ${labelOf(photo)}`}
                    className={`${styles.thumb} ${photo.id === selected ? styles.thumbSelected : ""} ${dimmed(photo) ? styles.thumbDimmed : ""}`}
                  >
                    <PhotoImage photoId={photo.id} alt="" loading="eager" className="block h-full w-full object-cover" />
                  </button>
                );
              })}

            </div>
          </div>

          {/*
            Слой аномалий: дорожки строятся из chronology_anomalies и флагов
            кадров, а не из пересчёта на клиенте (§8.2).
          */}
          {ANOMALY_LANES.map(({ kind, title }) => {
            const events = anomalies.filter((event) => {
              if (event.kind !== kind) return false;
              if (event.time == null || !viewport) return false;
              const ratio = timeToRatio(viewport, event.time);
              return ratio >= 0 && ratio <= 1;
            });
            return (
              <div key={kind} className={styles.row}>
                <div className={styles.rowLabel}>
                  <span>{title}</span>
                </div>
                <div className="relative h-6">
                  {events.map((event) => (
                    <button
                      key={event.id}
                      type="button"
                      onClick={(mouse) => {
                        const photo = event.photoId
                          ? dated.find((item) => item.id === event.photoId)
                          : null;
                        if (photo) selectPhoto(photo, mouse.shiftKey);
                      }}
                      aria-label={event.label}
                      title={event.label}
                      className={`${styles.event} ${styles[`event_${kind}`] ?? styles.eventChange} ${events.length > 80 ? styles.eventDense : ""}`}
                      style={{ left: `${timeToRatio(viewport, event.time ?? 0) * 100}%` }}
                    >
                      <span aria-hidden="true">{ANOMALY_GLYPHS[kind] ?? "•"}</span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Минимапа: полный диапазон и окно текущего вида. */}
        <div className={styles.row}>
          <div className={styles.rowLabel}>
            <span>МАСШТАБ</span>
          </div>
          <div
            className={styles.minimap}
            style={{ height: 40 }}
            onMouseDown={onMinimapDown}
            onMouseMove={onMinimapMove}
            onMouseUp={onMinimapUp}
            onMouseLeave={onMinimapUp}
            role="presentation"
          >
            {density.map((cell) => (
              <span
                key={cell.index}
                className={styles.minimapBar}
                title={`${cell.total} кадров${cell.findings ? `, находок: ${cell.findings}` : ""}`}
                style={{
                  left: `${((cell.index + 0.5) / DENSITY_BUCKETS) * 100}%`,
                  height: `${cell.height}%`,
                  background: cell.findings
                    ? "var(--red-400)"
                    : "var(--border-strong)",
                }}
              />
            ))}
            <div
              className={styles.minimapWindow}
              style={{
                left: `${((viewport.start - bounds.min) / Math.max(bounds.max - bounds.min, 1)) * 100}%`,
                width: `${((viewport.end - viewport.start) / Math.max(bounds.max - bounds.min, 1)) * 100}%`,
              }}
            />
          </div>
        </div>

        <div className={styles.timelineLegend} aria-label="Легенда таймлайна">
          <span className={styles.legendTitle}>ЛЕГЕНДА</span>
          <span><i className={`${styles.legendSwatch} ${styles.legendFinding}`} /> приоритет проверки</span>
          <span><i className={`${styles.legendSwatch} ${styles.legendDate}`} /> датировка / EXIF</span>
          <span><i className={`${styles.legendSwatch} ${styles.legendLimited}`} /> ограниченные данные</span>
          <span><i className={`${styles.legendSwatch} ${styles.legendSelected}`} /> выбранный кадр</span>
          <span className={styles.legendNote}>цвет не является выводом о личности</span>
        </div>
      </div>

      {/* Панель находок (§8.8): список с переходом к кадру. */}
      {findingsMode && (
        <div className={styles.findingsPanel}>
          <div className={styles.findingsHead}>
            <Filter className="h-3 w-3" aria-hidden="true" />
            Находки: {findings.length.toLocaleString("ru-RU")} из{" "}
            {filtered.length.toLocaleString("ru-RU")} кадров выборки
            <span className="ml-auto text-amber-300">
              Маркер означает приоритет проверки, а не вывод о личности
            </span>
          </div>
          {findings.slice(0, 200).map((photo) => (
            <button
              key={photo.id}
              type="button"
              className={styles.findingRow}
              onClick={() => focusPhoto(photo)}
            >
              <span>{blindMode ? labelOf(photo) : (photo.date ?? "н/д")}</span>
              <span>{poseLabel(photo.bucket)}</span>
              <span>{substantiveFlags(photo).join(", ") || photo.evidenceState || "—"}</span>
              <span>{pct(photo.quality)}</span>
            </button>
          ))}
          {findings.length === 0 && (
            <div className="px-4 py-3 text-2xs text-ink-muted">
              В текущей выборке находок нет. Это результат фильтра, а не утверждение об
              отсутствии изменений в архиве.
            </div>
          )}
        </div>
      )}

      {selectedPhoto && (
        <>
          <div className="fixed inset-0 z-30 bg-black/50" onClick={() => setSelected(null)} aria-hidden="true" />
          <aside className="fixed left-1/2 top-1/2 z-40 max-h-[calc(100vh-2rem)] w-[min(760px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-cyan-600 bg-surface-base p-5 shadow-popover">
          <div className="flex items-start justify-between">
            <div>
              <div className="font-mono text-xs font-bold text-cyan-300">
                КАРТОЧКА КАДРА · {blindMode ? labelOf(selectedPhoto) : selectedPhoto.id}
              </div>
              <div className="mt-1 text-xs text-ink-muted">
                {blindMode
                  ? "дата скрыта слепым режимом"
                  : (selectedPhoto.date ?? "дата отсутствует")}{" "}
                · {poseLabel(selectedPhoto.bucket)}
              </div>
            </div>
            <button type="button" onClick={() => setSelected(null)} aria-label="Закрыть карточку">
              <X className="h-4 w-4 text-ink-muted" />
            </button>
          </div>

          <PhotoImage
            photoId={selectedPhoto.id}
            alt={`Фото ${selectedPhoto.id}`}
            variant="contain"
            className="mt-3 max-h-44 w-full rounded-sm border border-line-subtle"
          />

          <div className="mt-4 grid grid-cols-2 gap-2 font-mono text-2xs">
            {(
              [
                ["quality", pct(selectedPhoto.quality)],
                ["align", pct(selectedPhoto.alignmentQuality)],
                ["ракурс", poseLabel(selectedPhoto.bucket)],
                ["кожа", pct(selectedPhoto.skinQuality)],
                ["рот", metric(selectedPhoto.jawOpenDegree)],
                ["выражение", selectedPhoto.expressionMagnitude == null ? "н/д" : selectedPhoto.expressionMagnitude.toFixed(1)],
                ["pose conf.", pct(selectedPhoto.poseConfidence)],
                ["bone", scalar(selectedPhoto.boneScore)],
                ["evidence", selectedPhoto.evidenceState ?? "н/д"],
                ["status", selectedPhoto.measurementStatus || "н/д"],
                ["LDM106", selectedPhoto.visibleLdm106 ?? "н/д"],
                ["UV", pct(selectedPhoto.uvCoverage)],
                ["provenance", selectedPhoto.dateProvenanceStatus ?? "н/д"],
              ] as [string, string | number][]
            ).map(([key, value]) => (
              <div key={key} className="rounded-sm border border-line-subtle p-2">
                <div className="text-ink-muted">{key}</div>
                <div className="mt-1 text-ink-primary">{String(value)}</div>
              </div>
            ))}
          </div>

          <div className="mt-3 rounded-sm border border-line-subtle p-2 text-xs">
            <div className="text-ink-muted">Находки и ограничения</div>
            <div className="mt-1 text-ink-primary">
              {substantiveFlags(selectedPhoto).length
                ? substantiveFlags(selectedPhoto).join(", ")
                : selectedPhoto.fuzzy || "нет"}
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => selectPhoto(selectedPhoto, true)}
              className="rounded-sm border border-cyan-600 px-2 py-1 text-xs text-cyan-300"
            >
              {aId === selectedPhoto.id ? (
                <>
                  <Check className="mr-1 inline h-3 w-3" />A назначен
                </>
              ) : bId === selectedPhoto.id ? (
                <>
                  <Check className="mr-1 inline h-3 w-3" />B назначен
                </>
              ) : (
                "Назначить A/B"
              )}
            </button>
            <button
              type="button"
              onClick={swapPair}
              disabled={!aId || !bId}
              className="rounded-sm border border-line-default px-2 py-1 text-xs text-ink-secondary disabled:opacity-40"
            >
              <ArrowLeftRight className="mr-1 inline h-3 w-3" />
              Поменять A и B
            </button>
            <button
              type="button"
              onClick={resetPair}
              disabled={!aId && !bId}
              className="rounded-sm border border-line-default px-2 py-1 text-xs text-ink-secondary disabled:opacity-40"
            >
              Сбросить пару
            </button>
            <a
              href={`/photos/${encodeURIComponent(selectedPhoto.id)}`}
              className="rounded-sm border border-cyan-600 px-2 py-1 text-xs text-cyan-300"
            >
              Страница фото
            </a>
          </div>
          </aside>
        </>
      )}

    </main>
  );
}
