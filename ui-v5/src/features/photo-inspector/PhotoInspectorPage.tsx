import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { researchTimeline } from "../../shared/researchApi";
import { poseLabel } from "../../shared/poseBins";
import { substantiveFlags } from "../../shared/findings";
import { normalizeStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";

const imageUrl = (id: string) => `/api/v1/photos/${encodeURIComponent(id)}/image`;
const value = (v: unknown) => v === null || v === undefined || v === "" ? "н/д" : String(v);

export const PhotoInspectorPage: React.FC = () => {
  const query = useQuery({ queryKey: ["research-timeline"], queryFn: researchTimeline });
  const photos = useMemo(() => query.data?.photos ?? [], [query.data]);
  const [selectedId, setSelectedId] = useState<string>();
  const selected = useMemo(() => photos.find((p) => p.id === (selectedId ?? photos[0]?.id)) ?? null, [photos, selectedId]);

  const stage = normalizeStage(query.data?.analysis_stage);
  if (query.isLoading) return <LoadingState text="Загрузка записей фотографий…" />;
  if (query.isError) return <ErrorState title="Инспектор недоступен" error={query.error} onRetry={() => void query.refetch()} />;
  if (!selected) return <EmptyState title="Записей нет" description="API вернул пустой список фотографий, показывать в инспекторе нечего." />;

  return <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-5">
    <StageBanner stage={stage} note={query.data?.note} />
    <header className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4 flex flex-wrap gap-4 items-center justify-between">
      <div><div className="font-mono text-sm font-bold text-cyan-300">ИНСПЕКТОР ФОТОГРАФИИ: {selected.id}</div><div className="text-xs text-slate-400">{stageLabel(stage)} · {value(selected.date)} · источник: {selected.sourceMode}</div></div>
      <div className="flex gap-2 text-xs font-mono"><span className="rounded border border-[#1f2d3d] px-2 py-1">Ракурс: {poseLabel(selected.bucket)}</span><span className="rounded border border-[#1f2d3d] px-2 py-1">Q: {value(selected.quality)}</span><span className="rounded border border-emerald-800 bg-emerald-950 px-2 py-1 text-emerald-300"><ShieldCheck className="inline h-3 w-3" /> доказательство: {value(selected.evidenceState)}</span></div>
    </header>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><div className="flex justify-between mb-3 font-mono text-xs text-slate-300"><span>ИСХОДНЫЙ КАДР STAGE 2</span><select aria-label="Выбор фотографии" value={selected.id} onChange={(e) => setSelectedId(e.target.value)} className="bg-[#101820] border border-[#1f2d3d] rounded px-2 py-1 max-w-[60%]">{photos.slice(0, 500).map((p) => <option key={p.id} value={p.id}>{p.date ?? p.id} · {p.id}</option>)}</select></div><div className="h-[380px] bg-[#101820] rounded border border-[#1f2d3d] flex items-center justify-center"><img src={imageUrl(selected.id)} alt={selected.id} className="max-h-full max-w-full object-contain" /></div></section>
      <section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><div className="mb-3 font-mono text-xs text-cyan-300">ПРЕВЬЮ РЕАЛЬНОГО КАДРА</div><div className="h-[380px] rounded border border-[#1f2d3d] bg-[#101820] flex items-center justify-center"><img src={imageUrl(selected.id)} alt={`Реальный кадр ${selected.id}`} className="max-h-full max-w-full object-contain" /></div><p className="mt-2 text-xs text-amber-300">Mesh-артефакт отсутствует в API. Синтетическая 3D-модель не показывается.</p></section>
    </div>
    <section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><h2 className="font-mono text-xs font-bold text-cyan-300 mb-3">ФАКТЫ ИЗ API, БЕЗ ПРОИЗВОДНЫХ ЗАГЛУШЕК</h2><div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">{[["Дата", selected.date],["Yaw", selected.yaw], ["Pitch", selected.pitch], ["Roll", selected.roll], ["Качество", selected.quality], ["Измерения", selected.measurementStatus], ["Пар Stage 2", selected.stage2PairCount ?? null], ["Флаги", substantiveFlags(selected).length ? substantiveFlags(selected).join(", ") : "нет"]].map(([k,v]) => <div key={String(k)} className="rounded bg-[#101820] p-3"><div className="text-slate-500">{k}</div><div className="text-slate-100 mt-1">{value(v)}</div></div>)}</div></section>
  </div>;
};

