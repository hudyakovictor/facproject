import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Play, Pause } from "lucide-react";
import { researchTimeline } from "../../shared/researchApi";
import { poseLabel } from "../../shared/poseBins";
import { normalizeStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";
import { sortPhotosByTime } from "../../shared/time";

export const MorphingPage: React.FC = () => {
  const q = useQuery({ queryKey: ["research-timeline"], queryFn: researchTimeline });
  const photos = useMemo(() => sortPhotosByTime(q.data?.photos ?? []).dated, [q.data]);
  const stage = normalizeStage(q.data?.analysis_stage);
  const [index, setIndex] = useState(0); const [playing, setPlaying] = useState(false);
  const photo = useMemo(() => photos[Math.min(index, Math.max(photos.length - 1, 0))], [photos, index]);
  React.useEffect(() => { if (!playing || photos.length < 2) return; const timer = window.setInterval(() => setIndex((current) => (current + 1) % photos.length), 700); return () => window.clearInterval(timer); }, [playing, photos.length]);
  if (q.isLoading) return <LoadingState text="Загрузка последовательности кадров…" />;
  if (q.isError) return <ErrorState title="Последовательность недоступна" error={q.error} onRetry={() => void q.refetch()} />;
  if (!photo) return <EmptyState title="Нет датированных кадров" description="Для покадрового просмотра нужны фотографии с датой съёмки; в ответе таких нет." />;
  const date = photo.date ?? "дата н/д";
  return <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-5"><StageBanner stage={stage} note={q.data?.note} /><header className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><div className="font-mono text-sm font-bold text-cyan-300">ПОКАДРОВЫЙ ПРОСМОТР · {stageLabel(stage)}</div><p className="text-xs text-slate-400 mt-1">Это последовательный просмотр исходных фотографий из timeline. Деформация mesh не выполняется: соответствующий артефакт отсутствует в API.</p></header><div className="grid grid-cols-1 lg:grid-cols-3 gap-5"><section className="lg:col-span-2 rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><div className="flex justify-between mb-3 text-xs font-mono"><span className="text-cyan-300">КАДР {index + 1} / {photos.length} · {date}</span><span className="text-slate-400">{photo.id}</span></div><div className="h-[390px] rounded border border-[#1f2d3d] bg-[#101820] flex items-center justify-center"><img src={`/api/v1/photos/${encodeURIComponent(photo.id)}/image`} alt={`Реальный кадр ${photo.id}`} className="max-h-full max-w-full object-contain" /></div><div className="mt-2 text-xs text-slate-500">Источник: `/api/v1/photos/{photo.id}/image` · без синтетической деформации</div></section><section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><h2 className="font-mono text-xs text-cyan-300 mb-3">ПОЛЯ ТЕКУЩЕЙ ЗАПИСИ</h2><div className="space-y-2 text-xs font-mono">{([["Дата",photo.date],["Ракурс",poseLabel(photo.bucket)],["Q",photo.quality],["Yaw",photo.yaw],["Pitch",photo.pitch],["Roll",photo.roll],["Измерения",photo.measurementStatus],["Evidence",photo.evidenceState ?? null]] as [string,unknown][]).map(([k,v])=><div key={k} className="flex justify-between gap-3 border-b border-[#1f2d3d] py-2"><span className="text-slate-500">{k}</span><span>{v === null || v === undefined ? "н/д" : String(v)}</span></div>)}</div><div className="mt-4 rounded border border-amber-800/60 bg-amber-950/20 p-3 text-xs text-amber-200">ΔSNR и геометрические отклонения текущим endpoint timeline не возвращаются.</div></section></div><section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><div className="flex items-center gap-3"><button onClick={()=>setPlaying(!playing)} className="rounded bg-cyan-700 px-3 py-1.5 text-xs">{playing?<Pause className="inline h-3 w-3"/>:<Play className="inline h-3 w-3"/>} {playing?"Пауза":"Воспроизвести"}</button><input aria-label="Позиция кадра" type="range" min="0" max={Math.max(photos.length-1,0)} value={index} onChange={e=>setIndex(Number(e.target.value))} className="flex-1 accent-cyan-500"/><span className="text-xs font-mono text-slate-400">{index+1}/{photos.length}</span></div></section></div>;
};
