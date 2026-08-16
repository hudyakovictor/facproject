import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { researchTimeline, type ResearchPhoto } from "../../shared/researchApi";

const palette = ["#34d399", "#fbbf24", "#22d3ee", "#a78bfa", "#fb7185", "#60a5fa"];

export const ClusteringPage: React.FC = () => {
  const [includeAllPoses, setIncludeAllPoses] = useState(true);
  const [selectedPose, setSelectedPose] = useState("all");
  const query = useQuery({ queryKey: ["research-timeline"], queryFn: researchTimeline });
  const photos = query.data?.photos ?? [];
  const poses = useMemo(() => Array.from(new Set(photos.map((p) => p.bucket))).sort(), [photos]);
  const visible = includeAllPoses || selectedPose === "all" ? photos : photos.filter((p) => p.bucket === selectedPose);
  const timeOf = (photo: ResearchPhoto) => photo.date ? Date.parse(photo.date) : (photo.t ?? 0);
  const minT = Math.min(...visible.map(timeOf));
  const maxT = Math.max(...visible.map(timeOf), minT + 86400000);
  const groups = useMemo(() => {
    const counts = new Map<string, ResearchPhoto[]>();
    visible.forEach((photo) => counts.set(photo.bucket, [...(counts.get(photo.bucket) ?? []), photo]));
    return Array.from(counts.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [visible]);
  const changePointCount = Number(query.data?.analysis_manifest?.change_point_count ?? 0);

  if (query.isLoading) return <div className="p-6 font-mono text-sm text-cyan-300">Загрузка реального Stage 2…</div>;
  if (query.error) return <div className="p-6 font-mono text-sm text-rose-300">Не удалось загрузить данные Stage 2.</div>;

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4">
        <div>
          <div className="font-mono text-sm font-bold text-cyan-300 uppercase">ХРОНОЛОГИЧЕСКОЕ РАСПРЕДЕЛЕНИЕ</div>
          <div className="text-xs text-slate-400">Реальные наблюдения Stage 2 · {photos.length.toLocaleString("ru-RU")} фото · отображаются измерения, не вердикт</div>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={includeAllPoses} onChange={(e) => setIncludeAllPoses(e.target.checked)} className="accent-cyan-500 h-4 w-4" /> все ракурсы</label>
          {!includeAllPoses && <select value={selectedPose} onChange={(e) => setSelectedPose(e.target.value)} className="rounded bg-[#141e27] px-2.5 py-1 text-cyan-300 border border-[#1f2d3d]"><option value="all">все бины</option>{poses.map((pose) => <option key={pose} value={pose}>{pose}</option>)}</select>}
        </div>
      </div>

      <div className="rounded-lg border border-cyan-800/60 bg-[#0b1117] px-4 py-3 text-xs font-mono flex items-center justify-between">
        <span className="text-slate-300">Временной диапазон: {new Date(minT).toISOString().slice(0, 10)} — {new Date(maxT).toISOString().slice(0, 10)}</span>
        <span className="text-amber-300">границы смен: {changePointCount ? changePointCount.toLocaleString("ru-RU") : "недоступно"} · без автоматического вывода о причине</span>
      </div>

      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 text-xs font-mono text-slate-400"><span>ОСЬ X: дата съёмки</span><span>ГРУППИРОВКА: бин ракурса</span></div>
        {groups.map(([bucket, bucketPhotos], index) => (
          <div key={bucket} className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono"><span className="font-bold" style={{ color: palette[index % palette.length] }}>{bucket}</span><span className="text-slate-400">{bucketPhotos.length.toLocaleString("ru-RU")} фото</span></div>
            <div className="relative h-9 w-full rounded bg-[#101820] border border-[#1f2d3d]">
              {bucketPhotos.map((p) => <span key={p.id} className="absolute top-1 h-7 w-px" style={{ left: `${(timeOf(p) - minT) / (maxT - minT) * 100}%`, backgroundColor: palette[index % palette.length] }} title={`${p.date ?? p.id} · quality ${p.quality ?? "н/д"}`} />)}
            </div>
          </div>
        ))}
        <div className="flex items-center justify-between px-2 py-2 bg-[#101820] rounded border border-[#1f2d3d] text-xs font-mono text-slate-400"><span>{new Date(minT).getUTCFullYear()}</span><span>{new Date(maxT).getUTCFullYear()}</span></div>
      </div>

      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-3">
        <div className="font-mono text-xs font-bold text-cyan-300 uppercase">ДИАГНОСТИКА ГРАНИЦ</div>
        <p className="text-xs text-slate-400">API сообщает число change-point событий, но не отдаёт в текущем контракте дат, кластеров, ΔSNR или confidence для карточек. Поэтому эти значения не подменяются демонстрационными.</p>
        <div className="font-mono text-xs text-amber-300">доступно событий: {changePointCount ? changePointCount.toLocaleString("ru-RU") : "н/д"}</div>
      </div>
    </div>
  );
};
