import React, { useMemo } from "react";
import { useTimeline } from "../../shared/api/queries";
import { type ResearchPhoto } from "../../shared/researchApi";
import { poseLabel, sortPoseBins } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";
import { formatDate, formatYear } from "../../shared/time";
import { useAnalysisStore } from "../../shared/state/analysisStore";

const palette = ["#34d399", "#fbbf24", "#22d3ee", "#a78bfa", "#fb7185", "#60a5fa"];

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
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4">
        <div>
          <div className="font-mono text-sm font-bold text-cyan-300 uppercase">ХРОНОЛОГИЧЕСКОЕ РАСПРЕДЕЛЕНИЕ · {stageLabel(stage)}</div>
          <div className="text-xs text-slate-400">Реальные наблюдения · {photos.length.toLocaleString("ru-RU")} фото · отображаются измерения, не вердикт</div>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={includeAllPoses} onChange={(e) => setIncludeAllPoses(e.target.checked)} className="accent-cyan-500 h-4 w-4" /> все ракурсы</label>
          {!includeAllPoses && <select aria-label="Бин ракурса" value={selectedPose} onChange={(e) => setSelectedPose(e.target.value)} className="rounded bg-[#141e27] px-2.5 py-1 text-cyan-300 border border-[#1f2d3d]">{poses.map((pose) => <option key={pose} value={pose}>{poseLabel(pose)}</option>)}</select>}
        </div>
      </div>

      <StageBanner stage={stage} note={query.data?.note} />

      <div className="rounded-lg border border-cyan-800/60 bg-[#0b1117] px-4 py-3 text-xs font-mono flex items-center justify-between">
        <span className="text-slate-300">Временной диапазон: {formatDate(minT)} — {formatDate(maxT)}</span>
        <span className="text-amber-300">границы смен: {changePointCount ? changePointCount.toLocaleString("ru-RU") : "недоступно"} · без автоматического вывода о причине</span>
      </div>

      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 text-xs font-mono text-slate-400"><span>ОСЬ X: дата съёмки</span><span>ГРУППИРОВКА: бин ракурса</span></div>
        {groups.map(([bucket, bucketPhotos], index) => (
          <div key={bucket} className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono"><span className="font-bold" style={{ color: palette[index % palette.length] }}>{poseLabel(bucket)}</span><span className="text-slate-400">{bucketPhotos.length.toLocaleString("ru-RU")} фото</span></div>
            <div className="relative h-9 w-full rounded bg-[#101820] border border-[#1f2d3d]">
              {bucketPhotos.map(({ photo: p, t }) => <span key={p.id} className="absolute top-1 h-7 w-px" style={{ left: `${(t - minT) / span * 100}%`, backgroundColor: palette[index % palette.length] }} title={`${p.date ?? p.id} · quality ${p.quality ?? "н/д"}`} />)}
            </div>
          </div>
        ))}
        <div className="flex items-center justify-between px-2 py-2 bg-[#101820] rounded border border-[#1f2d3d] text-xs font-mono text-slate-400"><span>{formatYear(minT)}</span><span>{formatYear(maxT)}</span></div>
      </div>

      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-3">
        <div className="font-mono text-xs font-bold text-cyan-300 uppercase">ДИАГНОСТИКА ГРАНИЦ</div>
        <p className="text-xs text-slate-400">API сообщает число change-point событий, но не отдаёт в текущем контракте дат, кластеров, ΔSNR или confidence для карточек. Поэтому эти значения не подменяются демонстрационными.</p>
        <div className="font-mono text-xs text-amber-300">доступно событий: {changePointCount ? changePointCount.toLocaleString("ru-RU") : "н/д"}</div>
      </div>
    </div>
  );
};
