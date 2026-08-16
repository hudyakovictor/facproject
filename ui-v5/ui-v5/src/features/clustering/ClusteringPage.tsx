import React, { useMemo } from "react";
import { useReportSection, useTimeline } from "../../shared/api/queries";
import { type ResearchPhoto } from "../../shared/researchApi";
import { poseLabel, sortPoseBins } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";
import { formatDate, formatYear } from "../../shared/time";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { CATEGORY_COLORS } from "../../shared/ui/tokenColors";

/** Цвета различают бины между собой и не означают оценку (правило 11). */
const palette = CATEGORY_COLORS;

/**
 * Перечень точек перелома формирует Stage 3, и его внутренняя форма в контракте
 * не зафиксирована: `/report/sections/change_points` отдаёт payload как есть.
 * Поэтому здесь не предполагаются конкретные имена полей: берётся то, что есть,
 * и недостающие поля остаются пустыми, а не заменяются выдуманными.
 */
const CHANGE_POINT_LIMIT = 200;

type ChangePointRow = {
  key: string;
  when: string | null;
  title: string;
  fields: Array<[string, string]>;
};

function asRecordArray(payload: unknown): Array<Record<string, unknown>> {
  const container = payload as Record<string, unknown> | null;
  const source = Array.isArray(payload)
    ? payload
    : container && typeof container === "object"
      ? container.items ?? container.change_points ?? container.rows ?? container.records
      : null;
  if (!Array.isArray(source)) return [];
  return source.filter(
    (item): item is Record<string, unknown> => Boolean(item) && typeof item === "object",
  );
}

function firstValue(record: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return null;
}

function scalarFields(record: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(record)
    .filter(([, value]) => typeof value === "number" || typeof value === "boolean" || typeof value === "string")
    .slice(0, 8)
    .map(([key, value]) => [
      key,
      typeof value === "number" ? String(Number(value.toFixed(6))) : String(value),
    ]);
}

function toChangePointRows(payload: unknown): ChangePointRow[] {
  return asRecordArray(payload).map((record, index) => {
    const when = firstValue(record, [
      "date",
      "date_utc",
      "timestamp",
      "datetime",
      "photo_date",
      "capture_date",
      "year",
    ]);
    const title = firstValue(record, [
      "metric",
      "metric_name",
      "channel",
      "name",
      "column",
      "kind",
      "photo_id",
    ]);
    return {
      key: `${String(title ?? "cp")}-${String(when ?? index)}-${index}`,
      when: when == null ? null : String(when),
      title: title == null ? `событие ${index + 1}` : String(title),
      fields: scalarFields(record),
    };
  });
}

export const ClusteringPage: React.FC = () => {
  /** Ракурс общий для всей станции, а не локальный для экрана (BUG-1). */
  const {
    multiPose: includeAllPoses,
    setMultiPose: setIncludeAllPoses,
    activePose: selectedPose,
    setActivePose: setSelectedPose,
  } = useAnalysisStore();
  const query = useTimeline();
  const photos = useMemo(() => query.data?.photos ?? [], [query.data]);
  const stage = resolveStage(query.data);
  const poses = useMemo(() => sortPoseBins(Array.from(new Set(photos.map((p) => p.bucket)))), [photos]);
  const visible = includeAllPoses ? photos : photos.filter((p) => p.bucket === selectedPose);
  /** Только кадры с известным временем: без этого Math.min даёт Infinity. */
  const timed = useMemo(
    () => visible
      .map((photo) => ({ photo, t: photo.date ? Date.parse(photo.date) : photo.t }))
      .filter((item): item is { photo: ResearchPhoto; t: number } => typeof item.t === "number" && Number.isFinite(item.t)),
    [visible],
  );
  const minT = timed.length ? Math.min(...timed.map((item) => item.t)) : null;
  const maxT = minT == null ? null : Math.max(...timed.map((item) => item.t), minT + 86400000);
  const span = minT != null && maxT != null ? Math.max(maxT - minT, 1) : 1;
  const groups = useMemo(() => {
    const counts = new Map<string, { photo: ResearchPhoto; t: number }[]>();
    timed.forEach((item) => counts.set(item.photo.bucket, [...(counts.get(item.photo.bucket) ?? []), item]));
    return sortPoseBins(Array.from(counts.keys())).map((bucket) => [bucket, counts.get(bucket) ?? []] as const);
  }, [timed]);
  const changePointCount = Number(query.data?.analysis_manifest?.change_point_count ?? 0);
  /** Реальные записи Stage 3, а не одно число из манифеста. */
  const changePoints = useReportSection("change_points", 0, CHANGE_POINT_LIMIT);
  const changePointRows = useMemo(
    () => toChangePointRows(changePoints.data?.payload),
    [changePoints.data],
  );

  if (query.isLoading) return <LoadingState text="Загрузка распределения по времени…" />;
  if (query.error) return <ErrorState title="Данные распределения недоступны" error={query.error} onRetry={() => void query.refetch()} />;
  if (photos.length === 0)
    return (
      <EmptyState
        title="Записей нет"
        description="API вернул пустой список фотографий, строить хронологическое распределение не по чему."
      />
    );
  if (minT == null || maxT == null)
    return (
      <EmptyState
        title="Ни у одной записи нет даты"
        description={`Получено ${photos.length.toLocaleString("ru-RU")} записей, но ни в одной нет времени съёмки — хронологическую ось построить невозможно.`}
      />
    );

  return (
    <div className="flex flex-col h-workspace w-full bg-surface-canvas text-ink-primary overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-line-default bg-surface-base p-4">
        <div>
          <div className="font-mono text-sm font-bold text-cyan-300 uppercase">ХРОНОЛОГИЧЕСКОЕ РАСПРЕДЕЛЕНИЕ · {stageLabel(stage)}</div>
          <div className="text-xs text-ink-muted">Реальные наблюдения · {photos.length.toLocaleString("ru-RU")} фото · отображаются измерения, не вердикт · не подменяются демонстрационными</div>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={includeAllPoses} onChange={(e) => setIncludeAllPoses(e.target.checked)} className="accent-cyan-500 h-4 w-4" /> все ракурсы</label>
          {!includeAllPoses && <select aria-label="Бин ракурса" value={selectedPose} onChange={(e) => setSelectedPose(e.target.value)} className="rounded bg-surface-overlay px-2.5 py-1 text-cyan-300 border border-line-default">{poses.map((pose) => <option key={pose} value={pose}>{poseLabel(pose)}</option>)}</select>}
        </div>
      </div>

      <StageBanner stage={stage} note={query.data?.note} />

      <div className="rounded-lg border border-cyan-600 bg-surface-base px-4 py-3 text-xs font-mono flex items-center justify-between">
        <span className="text-ink-secondary">Временной диапазон: {formatDate(minT)} — {formatDate(maxT)}</span>
        <span className="text-amber-300">границы смен: {changePointCount ? changePointCount.toLocaleString("ru-RU") : "недоступно"} · без автоматического вывода о причине</span>
      </div>

      <div className="rounded-lg border border-line-default bg-surface-base p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-line-default pb-2 text-xs font-mono text-ink-muted"><span>ОСЬ X: дата съёмки</span><span>ГРУППИРОВКА: бин ракурса</span></div>
        {groups.map(([bucket, bucketPhotos], index) => (
          <div key={bucket} className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono"><span className="font-bold" style={{ color: palette[index % palette.length] }}>{poseLabel(bucket)}</span><span className="text-ink-muted">{bucketPhotos.length.toLocaleString("ru-RU")} фото</span></div>
            <div className="relative h-12 w-full overflow-hidden rounded bg-surface-raised border border-line-default" aria-label={`Кластер ${poseLabel(bucket)}`}>
              {bucketPhotos.map(({ photo: p, t }, pointIndex) => (
                <span
                  key={p.id}
                  className="absolute h-2 w-2 -translate-x-1/2 rounded-full"
                  style={{
                    left: `${(t - minT) / span * 100}%`,
                    top: `${6 + (pointIndex % 5) * 8}px`,
                    backgroundColor: palette[index % palette.length],
                    opacity: 0.82,
                  }}
                  title={`${p.date ?? p.id} · качество ${p.quality ?? "н/д"}`}
                />
              ))}
              <span className="pointer-events-none absolute inset-x-0 bottom-1 border-t border-dashed border-line-default" aria-hidden="true" />
            </div>
          </div>
        ))}
        <div className="flex items-center justify-between px-2 py-2 bg-surface-raised rounded border border-line-default text-xs font-mono text-ink-muted"><span>{formatYear(minT)}</span><span>{formatYear(maxT)}</span></div>
      </div>

      <div className="rounded-lg border border-line-default bg-surface-base p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="font-mono text-xs font-bold text-cyan-300 uppercase">ТОЧКИ ПЕРЕЛОМА ХРОНОЛОГИИ</div>
          <div className="font-mono text-2xs text-ink-muted">
            манифест: {changePointCount ? changePointCount.toLocaleString("ru-RU") : "н/д"}
            {changePoints.data?.total != null
              ? ` · в отчёте: ${changePoints.data.total.toLocaleString("ru-RU")}`
              : ""}
          </div>
        </div>

        {changePoints.isPending && <p className="text-xs text-ink-muted">Загрузка точек перелома…</p>}

        {changePoints.error ? (
          <p className="text-xs text-amber-300">
            Список точек перелома недоступен:{" "}
            {String((changePoints.error as { message?: string }).message ?? changePoints.error)}.
            Манифест сообщает{" "}
            {changePointCount ? changePointCount.toLocaleString("ru-RU") : "0"} событий, но их
            содержание даёт только отчёт Stage 3.
          </p>
        ) : null}

        {changePoints.data && !changePoints.data.present && (
          <p className="text-xs text-ink-muted">
            Секция change_points есть в контракте, но в текущем выводе отсутствует.
          </p>
        )}

        {changePointRows.length > 0 && (
          <ul className="space-y-2">
            {changePointRows.map((row) => (
              <li key={row.key} className="rounded border border-line-default px-3 py-2">
                <div className="flex flex-wrap items-baseline justify-between gap-2 font-mono text-xs">
                  <span className="text-cyan-300">{row.title}</span>
                  <span className="text-ink-muted">{row.when ?? "дата н/д"}</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 font-mono text-2xs text-ink-secondary">
                  {row.fields.map(([key, value]) => (
                    <span key={key}>
                      <span className="text-ink-muted">{key}:</span> {value}
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}

        {changePoints.data?.present && changePointRows.length === 0 && (
          <p className="text-xs text-ink-muted">
            Секция вернула данные в форме, которую не удалось разобрать как список
            событий. Полный payload доступен на экране отчёта.
          </p>
        )}

        <p className="text-2xs text-ink-muted">
          Показаны записи из `/report/sections/change_points` без интерпретации причины:
          точка перелома — это статистическое событие в ряду измерений, а не вывод о
          смене человека или о вмешательстве.
        </p>
      </div>
    </div>
  );
};
