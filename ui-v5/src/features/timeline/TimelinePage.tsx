import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowLeftRight,
  Check,
  Filter,
  Maximize2,
  Minus,
  Plus,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { useTimeline } from "../../shared/api/queries";
import { type ResearchPhoto } from "../../shared/researchApi";
import { countFindings, isFinding, substantiveFlags } from "../../shared/findings";
import { poseLabel } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { DataContractBanner } from "../../shared/ui/DataContractBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";
import { PhotoImage } from "../../shared/ui/PhotoImage";
import { METRIC_COLORS } from "../../shared/ui/tokenColors";
import { frameLabel, frameTitle } from "../../shared/blind";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import {
  METRIC_GROUP_LABELS,
  metricById,
  type MetricDescriptor,
} from "../../shared/metrics";
import { TrackCanvas, type TrackSpec } from "./TrackCanvas";
import { PhotoTooltip } from "./PhotoTooltip";
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
import { PoseMenu } from "./PoseMenu";
import { PoseLanes } from "./PoseLanes";
import { MetricsMenu } from "./MetricsMenu";
import { FiltersMenu } from "./FiltersMenu";
import { ExportMenu } from "./ExportMenu";
import styles from "./timeline.module.css";

const pct = (v: number | null | undefined) => (v == null ? "н/д" : `${Math.round(v * 100)}%`);
const metric = (v: number | null | undefined) => (v == null ? "н/д" : v.toFixed(1));

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
    label: `${METRIC_GROUP_LABELS[descriptor.group].toUpperCase()} · ${descriptor.label.toUpperCase()}`,
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

export function TimelinePage() {
  const query = useTimeline();
  const areaRef = useRef<HTMLDivElement>(null);
  const [areaWidth, setAreaWidth] = useState(1000);
  const [hover, setHover] = useState<{ time: number; x: number; y: number } | null>(null);

  const {
    activePose,
    setActivePose,
    qualityThreshold,
    search,
    setSearch,
    findingsMode,
    setFindingsMode,
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

  const filtered = useMemo(
    () =>
      dated.filter((photo) => {
        const poseOk =
          multiPose || photo.bucket.toLowerCase() === activePose.toLowerCase();
        const q = search.trim().toLowerCase();
        const text = [photo.id, photo.date, photo.bucket, photo.era, photo.fuzzy, ...photo.flags]
          .join(" ")
          .toLowerCase();
        // null-качество не отбрасывается порогом: отсутствие оценки — не ноль.
        const qualityOk = photo.quality == null || photo.quality >= qualityThreshold;
        return poseOk && qualityOk && (!q || text.includes(q));
      }),
    [dated, multiPose, activePose, search, qualityThreshold],
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

  const representatives = useMemo(
    () =>
      viewport
        ? pickRepresentatives(filtered, times, {
            viewport,
            width: areaWidth,
            slotWidth: THUMB_SLOT,
            pinned: [aId, bId, selected],
          })
        : [],
    [filtered, times, viewport, areaWidth, aId, bId, selected],
  );

  const findings = useMemo(() => filtered.filter(isFinding), [filtered]);

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
  const aPhoto = dated.find((photo) => photo.id === aId) ?? null;
  const bPhoto = dated.find((photo) => photo.id === bId) ?? null;

  const [pairRejection, setPairRejection] = useState<string | null>(null);
  const bucketOf = useCallback(
    (id: string) => dated.find((item) => item.id === id)?.bucket,
    [dated],
  );
  const selectPhoto = (photo: ResearchPhoto) => {
    setSelected(photo.id);
    setPairRejection(assignToPair(photo.id, photo.bucket, bucketOf));
  };
  const resetPair = () => {
    clearPair();
    setPairRejection(null);
  };

  /** Зум привязан к курсору: точка под ним остаётся на месте (§8.6). */
  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (!viewport || !bounds) return;
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const localX = event.clientX - rect.left;

    if (event.ctrlKey || event.metaKey || !event.shiftKey) {
      const anchor = xToTime(viewport, localX, rect.width);
      setViewport(zoomAt(viewport, bounds, anchor, event.deltaY > 0 ? 1.15 : 0.87));
    } else {
      setViewport(panBy(viewport, bounds, event.deltaX !== 0 ? event.deltaX / rect.width : event.deltaY / rect.width));
    }
  };

  const handleMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!viewport) return;
    const rect = event.currentTarget.getBoundingClientRect();
    setHover({
      time: xToTime(viewport, event.clientX - rect.left, rect.width),
      x: event.clientX,
      y: event.clientY,
    });
  };

  /** Кадр, ближайший к курсору по времени — для подсказки. */
  const hovered = useMemo(() => {
    if (!hover || !viewport) return null;
    const tolerance = (viewport.end - viewport.start) / Math.max(areaWidth / 12, 1);
    let best: ResearchPhoto | null = null;
    let bestDelta = Infinity;
    for (const photo of inViewport) {
      const t = times.get(photo.id);
      if (t == null) continue;
      const delta = Math.abs(t - hover.time);
      if (delta < bestDelta) {
        bestDelta = delta;
        best = photo;
      }
    }
    return bestDelta <= tolerance ? best : null;
  }, [hover, viewport, inViewport, times, areaWidth]);

  // Клавиатура (§8.6): масштаб и перемещение без мыши.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!viewport || !bounds) return;
      const target = event.target as HTMLElement | null;
      if (target && /input|textarea|select/i.test(target.tagName)) return;

      const center = (viewport.start + viewport.end) / 2;
      if (event.key === "+" || event.key === "=") setViewport(zoomAt(viewport, bounds, center, 0.8));
      else if (event.key === "-") setViewport(zoomAt(viewport, bounds, center, 1.25));
      else if (event.key === "ArrowLeft") setViewport(panBy(viewport, bounds, -0.15));
      else if (event.key === "ArrowRight") setViewport(panBy(viewport, bounds, 0.15));
      else if (event.key === "0") setViewport(fitViewport(bounds));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [viewport, bounds, setViewport]);

  /** Перетаскивание окна по минимапе (brush, §8.6). */
  const onMinimap = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!bounds || !viewport) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    const center = bounds.min + ratio * (bounds.max - bounds.min);
    const span = viewport.end - viewport.start;
    setViewport(clampViewport({ start: center - span / 2, end: center + span / 2 }, bounds));
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

        <button
          type="button"
          onClick={() => setFindingsMode(!findingsMode)}
          aria-pressed={findingsMode}
          className={`rounded-sm border px-2 py-1 text-xs ${findingsMode ? "border-red-500 bg-red-soft text-red-300" : "border-line-default text-ink-secondary"}`}
        >
          <Filter className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
          Находки · {countFindings(filtered)}
        </button>

        <PoseMenu
          photos={dated}
          activePose={activePose}
          onSelect={setActivePose}
          multiPose={multiPose}
          onMultiPose={setMultiPose}
        />

        <MetricsMenu photos={filtered} visible={visibleMetrics} onChange={setVisibleMetrics} />

        <FiltersMenu photos={dated} />

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
        <DataContractBanner
          photos={rawPhotos}
          totalPhotos={rawPhotos.length}
          completeCount={query.data?.ui_fields_complete_photo_count}
          violationsByField={query.data?.ui_fields_violations_by_field}
          schema={query.data?.ui_fields_schema}
        />
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
          <div className={styles.rowLabel}>
            <span>ПЕРИОД</span>
            <small>{new Date(viewport.start).getUTCFullYear()}—{new Date(viewport.end).getUTCFullYear()}</small>
          </div>
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
          onWheel={handleWheel}
          onMouseMove={handleMove}
          onMouseLeave={() => setHover(null)}
        >
          {multiPose ? (
            <PoseLanes
              photos={inViewport}
              times={times}
              viewport={viewport}
              tracks={visibleTracks}
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

          {!multiPose && visibleTracks.map((track) => (
            <div key={track.key} className={styles.row}>
              <div className={styles.rowLabel}>
                <span>{track.label}</span>
                <small>{track.range}</small>
              </div>
              <div className={styles.canvasArea}>
                <TrackCanvas
                  track={track}
                  photos={inViewport}
                  times={times}
                  viewport={viewport}
                  height={TRACK_HEIGHT}
                  dimmed={dimmed}
                  hoverTime={hover?.time ?? null}
                />
              </div>
            </div>
          ))}

          {!multiPose && visibleTracks.length === 0 && (
            <div className={styles.row}>
              <div className={styles.rowLabel}>
                <span>МЕТРИКИ</span>
              </div>
              <div className="px-3 py-4 text-2xs text-ink-muted">
                Ни одна дорожка не выбрана. Включите метрики в верхней панели.
              </div>
            </div>
          )}

          {/* Строка фотографий: один кадр — одна координата X. */}
          <div className={styles.row} hidden={multiPose}>
            <div className={styles.rowLabel}>
              <span>PHOTO ROW</span>
              <small>лучший кадр на бакет</small>
            </div>
            <div className={styles.photoRow} style={{ height: 104 }}>
              {aPhoto && bPhoto && (
                <div
                  className={styles.bridge}
                  style={{
                    left: `${Math.min(timeToRatio(viewport, times.get(aPhoto.id) ?? 0), timeToRatio(viewport, times.get(bPhoto.id) ?? 0)) * 100}%`,
                    width: `${Math.abs(timeToRatio(viewport, times.get(bPhoto.id) ?? 0) - timeToRatio(viewport, times.get(aPhoto.id) ?? 0)) * 100}%`,
                  }}
                >
                  <span className={styles.bridgeLabel} style={{ left: "50%" }}>
                    {Math.round(
                      Math.abs((times.get(bPhoto.id) ?? 0) - (times.get(aPhoto.id) ?? 0)) /
                        86_400_000,
                    ).toLocaleString("ru-RU")}{" "}
                    дн.
                  </span>
                </div>
              )}

              {representatives.map((photo) => {
                const ratio = timeToRatio(viewport, times.get(photo.id) ?? 0);
                const state =
                  photo.id === aId
                    ? styles.thumbA
                    : photo.id === bId
                      ? styles.thumbB
                      : isFinding(photo)
                        ? styles.thumbFinding
                        : "";
                return (
                  <button
                    key={photo.id}
                    type="button"
                    onClick={() => selectPhoto(photo)}
                    title={frameTitle(
                      { id: photo.id, date: photo.date, order: order.get(photo.id) ?? 0 },
                      blindMode,
                    )}
                    className={`${styles.thumb} ${state} ${photo.id === selected ? styles.thumbSelected : ""} ${dimmed(photo) ? styles.thumbDimmed : ""}`}
                    style={{ left: `${ratio * 100}%` }}
                  >
                    <PhotoImage photoId={photo.id} alt="" className="aspect-square w-full" />
                    <span className={styles.thumbCaption}>{labelOf(photo)}</span>
                  </button>
                );
              })}

              {aPhoto && (
                <span
                  className={`${styles.pin} ${styles.pinA}`}
                  style={{ left: `${timeToRatio(viewport, times.get(aPhoto.id) ?? 0) * 100}%` }}
                >
                  A
                </span>
              )}
              {bPhoto && (
                <span
                  className={`${styles.pin} ${styles.pinB}`}
                  style={{ left: `${timeToRatio(viewport, times.get(bPhoto.id) ?? 0) * 100}%` }}
                >
                  B
                </span>
              )}
            </div>
          </div>

          {/* Три дорожки событий вместо одной строки ромбов (§8.2). */}
          {(
            [
              ["ИЗМЕНЕНИЯ", (p: ResearchPhoto) => (p.stage2StatusCounts?.coherent_jump_candidate ?? 0) > 0, styles.eventChange],
              ["ОГРАНИЧЕНИЯ", (p: ResearchPhoto) => substantiveFlags(p).length > 0, styles.eventLimited],
              ["ПРОВЕНАНС", (p: ResearchPhoto) => p.dateProvenanceStatus === "conflict" || p.exifAnomaly === true, styles.eventProvenance],
            ] as const
          ).map(([label, predicate, cls]) => {
            const events = inViewport.filter(predicate);
            return (
              <div key={label} className={styles.row}>
                <div className={styles.rowLabel}>
                  <span>{label}</span>
                  <small>{events.length}</small>
                </div>
                <div className="relative h-6">
                  {events.map((photo) => (
                    <button
                      key={photo.id}
                      type="button"
                      onClick={() => selectPhoto(photo)}
                      aria-label={`${label}: ${photo.date ?? photo.id}`}
                      title={substantiveFlags(photo).join(", ") || photo.fuzzy || label}
                      className={`${styles.event} ${cls}`}
                      style={{ left: `${timeToRatio(viewport, times.get(photo.id) ?? 0) * 100}%` }}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Минимапа: полный диапазон и окно текущего вида. */}
        <div className={styles.row}>
          <div className={styles.rowLabel}>
            <span>ОБЗОР</span>
            <small>перетащите окно</small>
          </div>
          <div
            className={styles.minimap}
            style={{ height: 40 }}
            onMouseDown={onMinimap}
            onMouseMove={(event) => event.buttons === 1 && onMinimap(event)}
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

      {hovered && hover && (
        <PhotoTooltip
          photo={hovered}
          x={Math.min(hover.x + 16, window.innerWidth - 290)}
          y={Math.min(hover.y + 16, window.innerHeight - 240)}
          blind={blindMode}
          label={labelOf(hovered)}
        />
      )}

      {selectedPhoto && (
        <aside className="fixed right-4 top-20 z-30 w-[min(430px,calc(100vw-2rem))] rounded-md border border-cyan-600 bg-surface-base p-4 shadow-popover">
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
                ["yaw", metric(selectedPhoto.yaw)],
                ["pitch", metric(selectedPhoto.pitch)],
                ["roll", metric(selectedPhoto.roll)],
                ["evidence", selectedPhoto.evidenceState ?? "н/д"],
                ["measurement", selectedPhoto.measurementStatus],
                ["pairs", selectedPhoto.stage2PairCount ?? "н/д"],
                ["provenance", selectedPhoto.dateProvenanceStatus ?? "н/д"],
              ] as [string, string | number][]
            ).map(([key, value]) => (
              <div key={key} className="rounded-sm border border-line-subtle p-2">
                <div className="text-ink-muted">{key}</div>
                <div className="mt-1 text-ink-primary">{String(value)}</div>
              </div>
            ))}
          </div>

          {selectedPhoto.uiContractViolations && selectedPhoto.uiContractViolations.length > 0 && (
            <div className="mt-3 rounded-sm border border-amber-500 bg-amber-soft p-2 text-2xs text-amber-300">
              <div className="text-ink-muted">Недоступные поля этой записи</div>
              <div className="mt-1 font-mono">{selectedPhoto.uiContractViolations.join(", ")}</div>
            </div>
          )}

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
              onClick={() => selectPhoto(selectedPhoto)}
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
          </div>
        </aside>
      )}
    </main>
  );
}
