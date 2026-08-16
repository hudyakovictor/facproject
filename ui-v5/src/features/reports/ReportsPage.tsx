import React from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText, AlertTriangle } from "lucide-react";
import { researchTimeline, runSummary } from "../../shared/researchApi";

export const ReportsPage: React.FC = () => {
  const timeline = useQuery({ queryKey: ["research-timeline"], queryFn: researchTimeline });
  const summary = useQuery({ queryKey: ["run-summary"], queryFn: runSummary });
  const photos = timeline.data?.photos ?? [];
  const technical = summary.data?.technical_summary;
  return <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-5">
    <header className="rounded-lg border border-cyan-800/70 bg-[#0b1117] p-5"><div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300"><FileText className="h-5 w-5"/> ОТЧЁТ ПО РЕАЛЬНОМУ ЗАПУСКУ</div><p className="text-xs text-slate-300 mt-2">Экран показывает только сведения, которые возвращает локальный API. Публичный Stage 3-отчёт пока не сформирован.</p></header>
    <section className="grid grid-cols-2 md:grid-cols-4 gap-3">{[["Фото",photos.length],["Change-point",technical?.change_point_count], ["Источник",summary.data?.source_mode], ["Статус",summary.data?.not_a_verdict ? "не verdict" : "н/д"]].map(([k,v])=><div key={String(k)} className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><div className="text-xs text-slate-500">{k}</div><div className="mt-2 text-lg font-mono text-cyan-300">{v ?? "н/д"}</div></div>)}</section>
    <section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5"><h2 className="font-mono text-xs text-cyan-300">ФАКТЫ И ОГРАНИЧЕНИЯ</h2><div className="mt-3 space-y-2 text-sm text-slate-300"><p>Диапазон наблюдений: {photos[0]?.date ?? "н/д"} — {photos.at(-1)?.date ?? "н/д"}.</p><p>Доступны: идентификатор, дата, ракурс, качество, флаги, статус измерения и связи Stage 2.</p><p className="text-amber-200"><AlertTriangle className="inline h-4 w-4 mr-1"/>Криптографические хеши, SNR, verdict и экспорт публикационного bundle этим API не подтверждены и не отображаются.</p></div></section>
  </div>;
};
