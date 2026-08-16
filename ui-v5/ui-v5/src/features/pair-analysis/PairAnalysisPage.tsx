import { useCallback, useMemo, useState } from "react";
import { ArrowLeftRight, Link2, RotateCcw } from "lucide-react";
import { usePairMetrics, useTimeline } from "../../shared/api/queries";
import type { ResearchPhoto } from "../../shared/researchApi";
import { poseLabel } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { QueryState } from "../../shared/ui/QueryState";
import { Button } from "../../shared/ui/primitives";
import { BlockedState, EmptyState } from "../../shared/ui/states";
import { describeError } from "../../shared/ui/errorDetail";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { ABCanvas } from "./ABCanvas";
import { LandmarkOverlay } from "./LandmarkOverlay";
import { PairZones } from "./PairZones";
import { MetricsPanel } from "./MetricsPanel";
import { RangeSelector, type RangeValue } from "./RangeSelector";
import { ReviewerWorkspace } from "./ReviewerWorkspace";
import { ThumbnailBrowser, type ThumbnailItem } from "./ThumbnailBrowser";
import { VERDICT_LABELS, applicability, flattenMetrics } from "./applicability";
import { tintLevel } from "./metricGroups";
import styles from "./pair.module.css";

/**
 * Парное сравнение (§11).
 *
 * Раньше страница состояла из двух `<select>`, двух превью и абзаца «endpoint
 * требует подключения» — при том что `/api/v1/pairs/{a}/{b}/metrics` существует
 * и отдаёт 208 колонок Stage 2.
 *
 * Порядок разделов повторяет спеку и логику работы: сначала шапка и
 * применимость (можно ли вообще мерить эту пару), затем холст, и только потом
 * числа. Метрики, поставленные раньше применимости, читаются как результат,
 * даже когда пара исключена по качеству.
 */

const yearOf = (photo: ResearchPhoto): number | null => {
  if (!photo.date) return null;
  const year = Number(photo.date.slice(0, 4));
  return Number.isFinite(year) ? year : null;
};

export function PairAnalysisPage() {
  const timeline = useTimeline();
  const photos = useMemo(() => timeline.data?.photos ?? [], [timeline.data]);
  const { pairA, pairB, assignToPair, swapPair, clearPair } = useAnalysisStore();

  const years = useMemo(() => {
    const set = new Set<number>();
    for (const photo of photos) {
      const year = yearOf(photo);
      if (year !== null) set.add(year);
    }
    return [...set].sort((a, b) => a - b);
  }, [photos]);

  const [range, setRange] = useState<RangeValue | null>(null);
  const [onlyCurrentPose, setOnlyCurrentPose] = useState(true);
  const [rows, setRows] = useState(4);
  const [size, setSize] = useState(40);
  const [pairRejection, setPairRejection] = useState<string | null>(null);
  const [copyCount, setCopyCount] = useState(0);

  /** Пока пользователь не трогал ползунки, диапазон покрывает весь архив. */
  const effectiveRange = useMemo<RangeValue>(
    () => range ?? { from: years[0] ?? 1999, to: years[years.length - 1] ?? 2026 },
    [range, years],
  );

  const photoA = useMemo(() => photos.find((photo) => photo.id === pairA) ?? null, [photos, pairA]);
  const photoB = useMemo(() => photos.find((photo) => photo.id === pairB) ?? null, [photos, pairB]);

  const metrics = usePairMetrics(pairA, pairB);

  /**
   * Кадр пары может отсутствовать в текущей ленте: Stage 2 строит пары по
   * своему прогону, а `/timeline` отдаёт то, что попало в текущую выборку.
   * Тогда бин и даты берутся из самой пары — иначе шапка писала бы «ракурс не
   * задан» при полностью определённой паре.
   */
  const pairFacts = useMemo(() => {
    if (!metrics.data) return null;
    const flat = flattenMetrics(metrics.data);
    const text = (key: string) => {
      const value = flat.get(key);
      return value === null || value === undefined || value === "" ? null : String(value);
    };
    return { bucket: text("pose_bin"), dateA: text("date_a"), dateB: text("date_b") };
  }, [metrics.data]);

  /** Бин, внутри которого ведётся работа: он задан кадром A, если тот выбран. */
  const activeBucket = photoA?.bucket ?? pairFacts?.bucket ?? null;

  const inRange = useMemo(
    () =>
      photos.filter((photo) => {
        const year = yearOf(photo);
        if (year === null) return false;
        if (year < effectiveRange.from || year > effectiveRange.to) return false;
        if (onlyCurrentPose && activeBucket && photo.bucket !== activeBucket) return false;
        return true;
      }),
    [photos, effectiveRange, onlyCurrentPose, activeBucket],
  );


  /**
   * Порог для A-relative подсветки берётся из калибровки пары, а не
   * назначается интерф��йсом. Без калибровочного значения уровень остаётся
   * «не измерено»: раскрасить плитки по произвольной шкале значило бы
   * выдумать меру.
   */
  const tintBasis = useMemo(() => {
    if (!metrics.data) return { threshold: null as number | null, label: null as string | null };
    const flat = flattenMetrics(metrics.data);
    const p95 = flat.get("primary_calibration_p95");
    return {
      threshold: typeof p95 === "number" ? p95 : null,
      label: "первичная метрика относительно калибровочного p95",
    };
  }, [metrics.data]);

  const items = useMemo<ThumbnailItem[]>(
    () =>
      inRange.map((photo) => ({
        photo,
        // Расхождение конкретного кадра с A backend отдаёт только для
        // построенных пар. Массового A-relative эндпоинта нет (B-04), поэтому
        // уровень известен лишь для текущей пары, а не для всей ленты.
        tint:
          photo.id === pairB && metrics.data
            ? tintLevel(
                (() => {
                  const value = flattenMetrics(metrics.data).get("primary_robust_z");
                  return typeof value === "number" ? value : null;
                })(),
                1,
                true,
              )
            : photo.id === pairA
              ? "near"
              : activeBucket && photo.bucket !== activeBucket
                ? "inapplicable"
                : "unknown",
        relative: null,
      })),
    [inRange, pairA, pairB, metrics.data, activeBucket],
  );

  const pick = useCallback(
    (photoId: string) => {
      const photo = photos.find((item) => item.id === photoId);
      if (!photo) return;
      setPairRejection(
        assignToPair(photoId, photo.bucket, (id) => photos.find((item) => item.id === id)?.bucket),
      );
    },
    [assignToPair, photos],
  );

  const copyPermalink = useCallback(() => {
    const url = new URL(window.location.href);
    if (pairA) url.searchParams.set("a", pairA);
    if (pairB) url.searchParams.set("b", pairB);
    void navigator.clipboard
      ?.writeText(url.toString())
      .then(() => setCopyCount((count) => count + 1))
      .catch(() => setCopyCount(0));
  }, [pairA, pairB]);

  return (
    <QueryState
      query={timeline}
      loadingText="Загрузка записей для сравнения…"
      errorTitle="Парное сравнение недоступно"
      isEmpty={(data) => data.photos.length < 2}
      emptyTitle="Недостаточно записей для пары"
      emptyDescription="Для сравнения нужно минимум две фотографии."
    >
      {() => (
        <div className="flex h-workspace w-full flex-col gap-4 overflow-y-auto bg-surface-canvas p-6 text-ink-primary">
          <StageBanner stage={resolveStage(timeline.data)} note={timeline.data?.note} />

          <header className={styles.header}>
            <div className={styles.headerMain}>
              <span className={styles.headerIds}>
                A: {pairA ?? "не выбран"} · B: {pairB ?? "не выбран"}
              </span>
              <span className={styles.headerMeta}>
                {stageLabel(resolveStage(timeline.data))} ·{" "}
                {photoA?.date ?? pairFacts?.dateA ?? "дата н/д"} →{" "}
                {photoB?.date ?? pairFacts?.dateB ?? "дата н/д"} · ракурс:{" "}
                {activeBucket ? poseLabel(activeBucket) : "не задан"}
              </span>
            </div>
            <div className={styles.headerActions}>
              <Button size="sm" variant="ghost" onClick={swapPair} disabled={!pairA || !pairB}>
                <ArrowLeftRight className="h-3.5 w-3.5" /> Поменять местами
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  clearPair();
                  setPairRejection(null);
                }}
                disabled={!pairA && !pairB}
              >
                <RotateCcw className="h-3.5 w-3.5" /> Сбросить
              </Button>
              <Button size="sm" variant="ghost" onClick={copyPermalink} disabled={!pairA || !pairB}>
                <Link2 className="h-3.5 w-3.5" /> Ссылка
              </Button>
              {copyCount > 0 && (
                <span key={copyCount} className={styles.hint} role="status">
                  Скопировано
                </span>
              )}
            </div>
          </header>

          {pairRejection && (
            <p className={styles.warn} role="status">
              {pairRejection}
            </p>
          )}

          <RangeSelector
            years={years}
            value={effectiveRange}
            onChange={setRange}
            countInRange={inRange.length}
            totalCount={photos.length}
            onlyCurrentPose={onlyCurrentPose}
            onToggleOnlyCurrentPose={setOnlyCurrentPose}
            poseLabelText={activeBucket ? poseLabel(activeBucket) : "ракурс задаст кадр A"}
          />

          <section className={styles.panel} aria-label="Кадры диапазона">
            <div className={styles.panelHeader}>
              <span className={styles.panelTitle}>КАДРЫ ДИАПАЗОНА</span>
              <div className={styles.sliderRow}>
                <label className={styles.rangeField}>
                  Рядов
                  <input
                    type="range"
                    min={1}
                    max={6}
                    value={rows}
                    onChange={(event) => setRows(Number(event.target.value))}
                    aria-label="Число рядов миниатюр"
                  />
                  <span className={styles.sliderValue}>{rows}</span>
                </label>
                <label className={styles.rangeField}>
                  Размер
                  <input
                    type="range"
                    min={28}
                    max={96}
                    step={4}
                    value={size}
                    onChange={(event) => setSize(Number(event.target.value))}
                    aria-label="Размер миниатюры"
                  />
                  <span className={styles.sliderValue}>{size}px</span>
                </label>
              </div>
            </div>

            {items.length === 0 ? (
              <EmptyState
                title="В диапазоне нет кадров"
                description="Расширьте диапазон дат или снимите ограничение по ракурсу."
              />
            ) : (
              <ThumbnailBrowser
                items={items}
                rows={rows}
                size={size}
                pairA={pairA}
                pairB={pairB}
                onPick={pick}
                metricLabel={tintBasis.label}
              />
            )}

            <p className={styles.note}>
              Подсветка показывает расхождение относительно калибровочного порога и
              не является вероятностью совпадения личности. Массовый расчёт
              «все кадры относительно A» backend не отдаёт (задача B-04), поэтому
              уровень известен только для текущей пары; остальные плитки помечены
              как неизмеренные, а кадры чужого ракурса — как неприменимые.
            </p>
          </section>

          {pairA && pairB ? (
            <div className={styles.columns}>
              <div className="flex flex-col gap-4">
                <ABCanvas
                  photoA={pairA}
                  photoB={pairB}
                  labelA={photoA?.date ?? pairFacts?.dateA ?? pairA}
                  labelB={photoB?.date ?? pairFacts?.dateB ?? pairB}
                />
                <LandmarkOverlay
                  photoA={pairA}
                  photoB={pairB}
                  labelA={photoA?.date ?? pairFacts?.dateA ?? pairA}
                  labelB={photoB?.date ?? pairFacts?.dateB ?? pairB}
                />
                <PairZones
                  photoA={pairA}
                  photoB={pairB}
                  labelA={photoA?.date ?? pairFacts?.dateA ?? pairA}
                  labelB={photoB?.date ?? pairFacts?.dateB ?? pairB}
                />
                <PairMetricsSection queryResult={metrics} />
              </div>
              <div className="flex flex-col gap-4">
                <ReviewerWorkspace photoA={pairA} photoB={pairB} />
              </div>
            </div>
          ) : (
            <EmptyState
              title="Пара не выбрана"
              description="Выберите кадр в ленте: первый становится A, второй — B. Ракурс должен совпадать."
            />
          )}
        </div>
      )}
    </QueryState>
  );
}

/**
 * Применимость и метрики. Вынесено отдельно, потому что 404 здесь — не ошибка
 * интерфейса, а содержательный ответ: Stage 2 такую пару не строил.
 */
function PairMetricsSection({
  queryResult,
}: {
  queryResult: ReturnType<typeof usePairMetrics>;
}) {
  if (queryResult.isPending) {
    return <p className={styles.note}>Загрузка метрик пары…</p>;
  }

  if (queryResult.isError) {
    const detail = describeError(queryResult.error);
    if (detail.status === 404) {
      return (
        <BlockedState
          title="Пара отсутствует в прогоне Stage 2"
          description="Stage 2 строит пары не для всех сочетаний кадров. Чтобы получить метрики, эту пару нужно включить в профиль анализа и выполнить прогон."
        />
      );
    }
    return (
      <BlockedState
        title="Метрики пары недоступны"
        description={detail.message}
      />
    );
  }

  const data = queryResult.data;
  if (!data) return null;
  const verdict = applicability(data);

  return (
    <>
      <section className={styles.panel} aria-label="Применимость пары">
        <div className={styles.panelHeader}>
          <span className={styles.panelTitle}>ПРИМЕНИМОСТЬ</span>
          <span className={styles.panelMeta}>решение: {VERDICT_LABELS[verdict.verdict]}</span>
        </div>
        <p className={styles.verdictBanner} data-verdict={verdict.verdict}>
          {verdict.summary}
        </p>
        <div className={styles.checkList}>
          {verdict.checks.map((check) => (
            <div key={check.id} className={styles.checkItem} data-verdict={check.verdict}>
              <span className={styles.checkLabel}>{check.label}</span>
              <span className={styles.checkValue} data-null={check.value === null}>
                {check.value ?? "н/д"}
              </span>
              <span className={styles.checkReason}>{check.reason}</span>
            </div>
          ))}
        </div>
      </section>

      <MetricsPanel data={data} />
    </>
  );
}
