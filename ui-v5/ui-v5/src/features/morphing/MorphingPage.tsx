import { Suspense, lazy, useCallback, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Camera, ChevronLeft, ChevronRight, Crosshair } from "lucide-react";
import { useTimeline } from "../../shared/api/queries";
import { poseLabel } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { QueryState } from "../../shared/ui/QueryState";
import { Button } from "../../shared/ui/primitives";
import { BlockedState, EmptyState, LoadingState } from "../../shared/ui/states";
import { describeError } from "../../shared/ui/errorDetail";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { consoleLogger } from "../../shared/logger";
import type { HeatmapSettings, LayerState } from "./MorphCanvas";
import {
  buildAnchors,
  fetchMeshPair,
  nearestAnchor,
  segmentAt,
  type Anchor,
} from "./meshData";
import styles from "./morphing.module.css";

/**
 * Морфинг и 3D-хронология (§12).
 *
 * Было: слайд-шоу исходных JPEG по таймеру 700 мс — смена картинок, не морфинг.
 * Стало: настоящая интерполяция геометрии между реальными реконструкциями через
 * `/api/v1/compare/full_mesh` (35 709 вершин, 70 789 треугольников).
 *
 * 🚨 WARNING: главный инвариант страницы — **морфинг это визуализация, а не
 * доказательство** (`AGENTS.md`). Между двумя снимками наблюдений нет; любое
 * промежуточное положение вершины построено интерполяцией. Поэтому:
 *  - подпись «промежуточный кадр построен интерполяцией» видна постоянно;
 *  - экспортируются только кадры, совпадающие с реальным якорем, а
 *    промежуточный кадр помечается в имени файла и метаданных;
 *  - ни одно число отсюда не попадает в метрики пары.
 */

const DAY = 86_400_000;

/** Three.js подгружается только когда есть что показывать (см. инспектор). */
const MorphCanvas = lazy(() =>
  import("./MorphCanvas").then((module) => ({ default: module.MorphCanvas })),
);

export function MorphingPage() {
  const timeline = useTimeline();
  const photos = useMemo(() => timeline.data?.photos ?? [], [timeline.data]);
  const { activePose } = useAnalysisStore();

  /** Бин выбирается явно: интерполировать между ракурсами нельзя (§12.1). */
  const buckets = useMemo(() => {
    const counts = new Map<string, number>();
    for (const photo of photos) {
      if (!photo.date) continue;
      counts.set(photo.bucket, (counts.get(photo.bucket) ?? 0) + 1);
    }
    return [...counts.entries()].sort((left, right) => right[1] - left[1]);
  }, [photos]);

  const [bucket, setBucket] = useState<string | null>(null);
  const effectiveBucket = bucket ?? activePose ?? buckets[0]?.[0] ?? null;

  const [qualityFloor, setQualityFloor] = useState<number | null>(null);
  const anchors = useMemo(
    () => buildAnchors(photos, { bucket: effectiveBucket, qualityFloor }),
    [photos, effectiveBucket, qualityFloor],
  );
  const usable = useMemo(() => anchors.filter((anchor) => !anchor.excluded), [anchors]);

  /** Диапазон времени: полный, пока пользователь не сузил его (§12.7). */
  const fullRange = useMemo(() => {
    if (usable.length === 0) return null;
    return { from: usable[0].time, to: usable[usable.length - 1].time };
  }, [usable]);
  const [zoom, setZoom] = useState<{ from: number; to: number } | null>(null);
  const [zoomHistory, setZoomHistory] = useState<Array<{ from: number; to: number }>>([]);
  const range = zoom ?? fullRange;

  const [time, setTime] = useState<number | null>(null);
  /*
   * Позиция скраббера — производное состояние: пока пользователь не двигал
   * ползунок и когда диапазон сузился так, что прежняя позиция вышла за его
   * границы, она приводится к началу диапазона. Считается на месте, а не
   * записывается обратно через эффект: `setState` в эффекте вызывает каскад
   * перерисовок и запрещён правилом `react-hooks/set-state-in-effect`.
   */
  const effectiveTime = useMemo(() => {
    if (!range) return time ?? 0;
    if (time === null || time < range.from || time > range.to) return range.from;
    return time;
  }, [time, range]);

  const segment = useMemo(() => segmentAt(anchors, effectiveTime), [anchors, effectiveTime]);

  const [layers, setLayers] = useState<LayerState>({
    mesh: true,
    wireframe: false,
    heatmap: true,
    landmarks: false,
  });
  const [heatmapScale, setHeatmapScale] = useState<HeatmapSettings["scale"]>("linear");
  const [heatmapMax, setHeatmapMax] = useState<number | null>(null);
  const [lightIntensity, setLightIntensity] = useState(1);
  const [contextLost, setContextLost] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  /** Меш грузится для отрезка, а не для позиции: внутри отрезка данные те же. */
  const meshQuery = useQuery({
    queryKey: ["morph-mesh", segment?.from.id ?? null, segment?.to.id ?? null],
    queryFn: () => fetchMeshPair(segment!.from.id, segment!.to.id),
    enabled: segment !== null,
    retry: (count, error) => {
      const status = (error as { status?: number }).status;
      if (typeof status === "number" && status >= 400 && status < 500) return false;
      return count < 1;
    },
    staleTime: Infinity,
  });

  const payload = meshQuery.data ?? null;
  const effectiveMax = heatmapMax ?? payload?.stats.p95 ?? 1;

  const stepAnchor = useCallback(
    (delta: number) => {
      if (usable.length === 0) return;
      const current = nearestAnchor(usable, effectiveTime);
      const index = current ? usable.findIndex((anchor) => anchor.id === current.id) : 0;
      const next = usable[Math.min(usable.length - 1, Math.max(0, index + delta))];
      if (next) setTime(next.time);
    },
    [usable, effectiveTime],
  );

  /** Клавиатура §12.6: шаг по якорям и точный шаг по дням. */
  const onScrubberKey = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "PageUp" || event.key === "PageDown") {
        event.preventDefault();
        stepAnchor(event.key === "PageUp" ? 1 : -1);
      }
    },
    [stepAnchor],
  );

  const snap = useCallback(() => {
    const anchor = nearestAnchor(usable, effectiveTime);
    if (anchor) setTime(anchor.time);
  }, [usable, effectiveTime]);

  const zoomAround = useCallback(
    (anchor: Anchor) => {
      if (range) setZoomHistory((history) => [...history, range]);
      setZoom({ from: anchor.time - 365 * DAY, to: anchor.time + 365 * DAY });
      setTime(anchor.time);
    },
    [range],
  );

  const zoomBack = useCallback(() => {
    setZoomHistory((history) => {
      const previous = history[history.length - 1];
      setZoom(previous ?? null);
      return history.slice(0, -1);
    });
  }, []);

  /**
   * Экспорт кадра (§12.9). В имя файла и в подпись попадает, совпадает ли кадр
   * с реальным снимком: промежуточный кадр не должен уйти в отчёт как
   * наблюдение.
   */
  const exportFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !segment) return;
    const atAnchor = segment.t === 0 || segment.t === 1;
    const label = atAnchor
      ? segment.t === 0
        ? segment.from.id
        : segment.to.id
      : `interpolated_${segment.from.id}__${segment.to.id}_t${segment.t.toFixed(3)}`;
    canvas.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${atAnchor ? "anchor" : "VISUALIZATION_NOT_MEASUREMENT"}_${label}.png`;
      link.click();
      URL.revokeObjectURL(url);
      consoleLogger.addLog(
        "INFO",
        "morphing",
        atAnchor ? "Экспортирован кадр реального якоря" : "Экспортирован интерполированный кадр",
        atAnchor
          ? label
          : "промежуточное состояние построено интерполяцией и не является измерением",
      );
    }, "image/png");
  }, [segment]);

  return (
    <QueryState
      query={timeline}
      loadingText="Загрузка последовательности кадров…"
      errorTitle="Последовательность недоступна"
      isEmpty={(data) => data.photos.length === 0}
      emptyTitle="Нет кадров"
      emptyDescription="API вернул пустой список фотографий."
    >
      {() => (
        <div className="flex h-workspace w-full flex-col gap-4 overflow-y-auto bg-surface-canvas p-6 text-ink-primary">
          <StageBanner stage={resolveStage(timeline.data)} note={timeline.data?.note} />

          <header className={styles.header}>
            <div className={styles.headerMain}>
              <span className={styles.headerTitle}>
                3D-ХРОНОЛОГИЯ · {effectiveBucket ? poseLabel(effectiveBucket) : "ракурс не выбран"}
              </span>
              <span className={styles.headerMeta}>
                {stageLabel(resolveStage(timeline.data))} · якорей пригодных: {usable.length} из{" "}
                {anchors.length}
                {segment && ` · отрезок ${segment.from.date} → ${segment.to.date}`}
              </span>
            </div>
            <div className={styles.headerActions}>
              <label className={styles.inlineField}>
                Ракурс
                <select
                  value={effectiveBucket ?? ""}
                  onChange={(event) => {
                    setBucket(event.target.value);
                    setTime(null);
                    setZoom(null);
                  }}
                  aria-label="Бин ракурса"
                >
                  {buckets.map(([name, count]) => (
                    <option key={name} value={name}>
                      {poseLabel(name)} · {count}
                    </option>
                  ))}
                </select>
              </label>
              <Button size="sm" variant="ghost" onClick={exportFrame} disabled={!payload}>
                <Camera className="h-3.5 w-3.5" /> PNG кадра
              </Button>
            </div>
          </header>

          <p className={styles.invariant}>
            Морфинг — визуализация, а не доказательство. Между реальными снимками
            наблюдений нет: промежуточные положения вершин построены интерполяцией и
            не являются измерением. Числа для выводов берутся из парного сравнения,
            а не отсюда.
          </p>

          {usable.length < 2 ? (
            <EmptyState
              title="Недостаточно якорей"
              description={`Для интерполяции нужны минимум два датированных кадра одного ракурса. Пригодных якорей: ${usable.length}.`}
            />
          ) : (
            <>
              <div className={styles.workArea}>
                <section className={styles.canvasPanel} aria-label="3D-модель">
                  {contextLost && (
                    <p className={styles.warn}>
                      Контекст WebGL потерян: браузер освободил видеопамять. Модель
                      будет перерисована после восстановления контекста.
                    </p>
                  )}
                  {meshQuery.isPending && <LoadingState text="Загрузка геометрии пары…" />}
                  {meshQuery.isError && <MeshError error={meshQuery.error} />}
                  {payload && (
                    <>
                      <Suspense fallback={<LoadingState text="Загрузка трёхмерного просмотра…" />}>
                      <MorphCanvas
                        payload={payload}
                        t={segment?.t ?? 0}
                        layers={layers}
                        heatmap={{ max: effectiveMax, scale: heatmapScale }}
                        lightIntensity={lightIntensity}
                        onContextLost={setContextLost}
                        canvasRef={canvasRef}
                      />
                      </Suspense>
                      <p className={styles.canvasCaption}>
                        {segment && (segment.t === 0 || segment.t === 1)
                          ? `Реальный якорь: ${segment.t === 0 ? segment.from.id : segment.to.id}`
                          : `Промежуточный кадр построен интерполяцией (t = ${(segment?.t ?? 0).toFixed(3)})`}{" "}
                        · {payload.vertexCount.toLocaleString("ru-RU")} вершин ·{" "}
                        {payload.triangleCount.toLocaleString("ru-RU")} треугольников
                      </p>
                    </>
                  )}
                </section>

                <aside className={styles.sidePanel}>
                  <section className={styles.panel} aria-label="Слои">
                    <span className={styles.panelTitle}>СЛОИ</span>
                    {(
                      [
                        ["mesh", "Поверхность"],
                        ["wireframe", "Каркас"],
                        ["heatmap", "Тепловая карта отклонений"],
                      ] as Array<[keyof LayerState, string]>
                    ).map(([key, label]) => (
                      <label key={key} className={styles.checkboxRow}>
                        <input
                          type="checkbox"
                          checked={layers[key]}
                          onChange={(event) =>
                            setLayers((current) => ({ ...current, [key]: event.target.checked }))
                          }
                        />
                        {label}
                      </label>
                    ))}
                    <p className={styles.note}>
                      Точки LDM и зоны на 3D-модели не накладываются: их координаты
                      заданы в системе кадра, а меш — в системе модели. Совмещение
                      без матрицы проекции от backend дало бы смещённые точки,
                      выглядящие как измерение.
                    </p>
                  </section>

                  {payload && layers.heatmap && (
                    <section className={styles.panel} aria-label="Настройки тепловой карты">
                      <span className={styles.panelTitle}>ТЕПЛОВАЯ КАРТА</span>
                      <label className={styles.sliderRow}>
                        Верхняя граница
                        <input
                          type="range"
                          min={payload.stats.median}
                          max={payload.stats.max}
                          step={(payload.stats.max - payload.stats.median) / 100 || 0.001}
                          value={effectiveMax}
                          onChange={(event) => setHeatmapMax(Number(event.target.value))}
                          aria-label="Верхняя граница тепловой карты"
                        />
                        <span className={styles.value}>{effectiveMax.toFixed(4)}</span>
                      </label>
                      <div className={styles.modeBar} role="group" aria-label="Шкала">
                        {(["linear", "log"] as const).map((scale) => (
                          <button
                            key={scale}
                            type="button"
                            className={styles.modeButton}
                            aria-pressed={heatmapScale === scale}
                            onClick={() => setHeatmapScale(scale)}
                          >
                            {scale === "linear" ? "линейная" : "логарифм."}
                          </button>
                        ))}
                        <button
                          type="button"
                          className={styles.modeButton}
                          onClick={() => {
                            setHeatmapMax(null);
                            setHeatmapScale("linear");
                          }}
                        >
                          сброс
                        </button>
                      </div>
                      <dl className={styles.stats}>
                        {(
                          [
                            ["минимум", payload.stats.min],
                            ["медиана", payload.stats.median],
                            ["p95", payload.stats.p95],
                            ["максимум", payload.stats.max],
                          ] as Array<[string, number]>
                        ).map(([label, value]) => (
                          <div key={label} className={styles.statRow}>
                            <dt>{label}</dt>
                            <dd>{value.toFixed(4)}</dd>
                          </div>
                        ))}
                      </dl>
                      <p className={styles.note}>
                        Настройки отображения не меняют результат: границы и шкала
                        влияют только на цвет. Значения выше границы прижимаются к
                        ней — иначе один выброс перекрасил бы всю модель.
                      </p>
                    </section>
                  )}

                  <section className={styles.panel} aria-label="Освещение">
                    <span className={styles.panelTitle}>ОСВЕЩЕНИЕ</span>
                    <label className={styles.sliderRow}>
                      Яркость
                      <input
                        type="range"
                        min={0.2}
                        max={2}
                        step={0.1}
                        value={lightIntensity}
                        onChange={(event) => setLightIntensity(Number(event.target.value))}
                        aria-label="Интенсивность освещения"
                      />
                      <span className={styles.value}>{lightIntensity.toFixed(1)}</span>
                    </label>
                    <p className={styles.note}>
                      Свет влияет только на показ. Текстура на модель не
                      накладывается: снимки сделаны при разном освещении, и
                      смешивание двух текстур создало бы несуществующую кожу.
                    </p>
                  </section>
                </aside>
              </div>

              <section className={styles.panel} aria-label="Временной скраббер">
                <div className={styles.panelHeader}>
                  <span className={styles.panelTitle}>ВРЕМЕННАЯ ШКАЛА</span>
                  <span className={styles.headerMeta}>
                    {new Date(effectiveTime).toISOString().slice(0, 10)}
                    {range &&
                      ` · диапазон ${new Date(range.from).toISOString().slice(0, 10)} — ${new Date(range.to).toISOString().slice(0, 10)}`}
                  </span>
                </div>

                <div className={styles.scrubberRow}>
                  <Button size="sm" variant="ghost" onClick={() => stepAnchor(-1)}>
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </Button>
                  <input
                    type="range"
                    className={styles.scrubber}
                    min={range?.from ?? 0}
                    max={range?.to ?? 1}
                    step={DAY}
                    value={effectiveTime}
                    onChange={(event) => setTime(Number(event.target.value))}
                    onKeyDown={onScrubberKey}
                    aria-label="Положение на временной шкале"
                    aria-valuetext={new Date(effectiveTime).toISOString().slice(0, 10)}
                  />
                  <Button size="sm" variant="ghost" onClick={() => stepAnchor(1)}>
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={snap}>
                    <Crosshair className="h-3.5 w-3.5" /> К ближайшему снимку
                  </Button>
                  {zoomHistory.length > 0 && (
                    <Button size="sm" variant="ghost" onClick={zoomBack}>
                      Назад к диапазону
                    </Button>
                  )}
                </div>
                <p className={styles.note}>
                  Ползунок перемещается вручную. PageUp и PageDown переходят к
                  соседнему реальному снимку. Автоматического воспроизведения нет:
                  анимация, которую нельзя остановить на нужном кадре, мешает
                  разглядыванию, а зацикленный ролик выглядит как «наблюдение
                  изменения».
                </p>
              </section>

              <section className={styles.panel} aria-label="Последовательность якорей">
                <div className={styles.panelHeader}>
                  <span className={styles.panelTitle}>ЯКОРЯ</span>
                  <label className={styles.inlineField}>
                    Порог качества
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.05}
                      value={qualityFloor ?? ""}
                      placeholder="нет"
                      onChange={(event) =>
                        setQualityFloor(event.target.value === "" ? null : Number(event.target.value))
                      }
                      aria-label="Минимальное качество якоря"
                    />
                  </label>
                </div>
                <ul className={styles.anchorList}>
                  {anchors.map((anchor) => (
                    <li key={anchor.id}>
                      <button
                        type="button"
                        className={styles.anchorItem}
                        data-excluded={anchor.excluded}
                        data-current={segment?.from.id === anchor.id || segment?.to.id === anchor.id}
                        onClick={() => (anchor.excluded ? undefined : setTime(anchor.time))}
                        onDoubleClick={() => zoomAround(anchor)}
                        disabled={anchor.excluded}
                        title={
                          anchor.reason
                            ? `Исключён: ${anchor.reason}`
                            : "Клик — перейти, двойной клик — приблизить диапазон"
                        }
                      >
                        <span className={styles.anchorDate}>{anchor.date}</span>
                        <span className={styles.anchorId}>{anchor.id.slice(0, 14)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                <p className={styles.note}>
                  Исключённые якоря показаны, но в интерполяции не участвуют: скрыть
                  их значило бы скрыть, что часть периода не покрыта пригодными
                  снимками.
                </p>
              </section>
            </>
          )}
        </div>
      )}
    </QueryState>
  );
}

/** Отказ загрузки меша: 409 и 503 здесь содержательны, а не «что-то сломалось». */
function MeshError({ error }: { error: unknown }) {
  const detail = describeError(error);
  if (detail.status === 503) {
    return (
      <BlockedState
        title="Геометрия модели недоступна"
        description="Полная реконструкция требует весов модели BFM, которых нет в этом окружении. Показывать интерполяцию по приблизительной форме нельзя."
      />
    );
  }
  if (detail.status === 409) {
    return (
      <BlockedState
        title="Кадры несовместимы для интерполяции"
        description={detail.message}
      />
    );
  }
  return <BlockedState title="Геометрия пары не загрузилась" description={detail.message} />;
}
