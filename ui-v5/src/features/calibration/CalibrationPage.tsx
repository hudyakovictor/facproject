import React from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, AlertTriangle } from "lucide-react";
import { calibrationHealth } from "../../shared/researchApi";

export const CalibrationPage: React.FC = () => {
  const q = useQuery({ queryKey: ["calibration-health"], queryFn: calibrationHealth });
  if (q.isLoading) return <div className="p-8 text-slate-300">Загрузка калибровки…</div>;
  if (q.isError || !q.data) return <div className="p-8 text-amber-300">Калибровочный endpoint недоступен.</div>;
  const d = q.data;
  return <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-5"><header className="rounded-lg border border-cyan-800/70 bg-[#0b1117] p-5"><div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300"><ShieldCheck className="h-5 w-5"/> КАЛИБРОВОЧНЫЙ ПУЛ · РЕАЛЬНЫЙ API</div><p className="text-xs text-slate-300 mt-2">Источник: {d.source}. Это описание состава калибровочного индекса, а не статистический verdict.</p></header><section className="grid grid-cols-2 md:grid-cols-4 gap-3">{[["Записей",d.total_records],["Персон",d.total_persons],["Корзин",Object.keys(d.buckets).length],["Надёжность",JSON.stringify(d.confidence_counts)]].map(([k,v])=><div key={String(k)} className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><div className="text-xs text-slate-500">{k}</div><div className="mt-2 text-lg font-mono text-cyan-300">{String(v)}</div></div>)}</section><section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5"><h2 className="font-mono text-xs text-cyan-300 mb-3">РАКУРСНЫЕ КОРЗИНЫ</h2><div className="grid md:grid-cols-3 gap-2">{Object.values(d.buckets).map(b=><div key={b.pose_bin} className="rounded bg-[#101820] p-3 text-xs"><div className="font-mono text-cyan-300">{b.pose_bin}</div><div className="text-slate-300 mt-1">кадров: {b.frame_count} · персон: {b.person_count}</div><div className="text-slate-400">{b.confidence} · {b.runtime_usable ? "доступна" : "недоступна"}</div></div>)}</div></section><div className="rounded border border-amber-800/60 bg-amber-950/20 p-4 text-xs text-amber-200"><AlertTriangle className="inline h-4 w-4 mr-1"/>SNR, FDR, LOPO и параметры шумовой модели не входят в ответ текущего endpoint, поэтому старые числовые карточки удалены.</div></div>;
};
