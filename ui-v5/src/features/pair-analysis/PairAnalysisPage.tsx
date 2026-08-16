import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { researchTimeline, type ResearchPhoto } from "../../shared/researchApi";

const imageUrl = (id: string) => `/api/v1/photos/${encodeURIComponent(id)}/image`;
const show = (v: unknown) => v === null || v === undefined || v === "" ? "н/д" : String(v);
export const PairAnalysisPage: React.FC = () => {
  const q = useQuery({ queryKey: ["research-timeline"], queryFn: researchTimeline });
  const photos = q.data?.photos ?? [];
  const [aId, setAId] = useState<string>(); const [bId, setBId] = useState<string>();
  const a = useMemo(() => photos.find(p => p.id === (aId ?? photos[0]?.id)), [photos, aId]);
  const b = useMemo(() => photos.find(p => p.id === (bId ?? photos[1]?.id)) ?? photos[1], [photos, bId]);
  if (q.isLoading) return <div className="p-8 text-slate-300">Загрузка реальных записей Stage 2…</div>;
  if (q.isError || !a || !b) return <div className="p-8 text-amber-300">Парное сравнение недоступно: API не вернул минимум две записи.</div>;
  const field = (p: ResearchPhoto, k: keyof ResearchPhoto) => show(p[k]);
  const selector = (label: string, current: string, onChange: (v: string) => void) => <label className="text-xs text-slate-400">{label}<select value={current} onChange={e => onChange(e.target.value)} className="block mt-1 w-full bg-[#101820] border border-[#1f2d3d] rounded px-2 py-1 text-slate-200">{photos.slice(0, 500).map(p => <option key={p.id} value={p.id}>{p.date ?? p.id} · {p.id}</option>)}</select></label>;
  const cards: Array<{ label: string; photo: ResearchPhoto; setter: React.Dispatch<React.SetStateAction<string | undefined>>; border: string }> = [{ label: "A", photo: a, setter: setAId, border: "border-cyan-800" }, { label: "B", photo: b, setter: setBId, border: "border-amber-800" }];
  return <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-5"><header className="rounded-lg border border-cyan-800/60 bg-[#0b1117] p-4"><div className="font-mono text-sm font-bold text-cyan-300">СРАВНЕНИЕ ДВУХ РЕАЛЬНЫХ ЗАПИСЕЙ STAGE 2</div><p className="text-xs text-slate-400 mt-1">Клиент показывает поля, которые реально возвращает API. Байесовский verdict, SNR и similarity не подставляются: отдельный endpoint метрик не подключён к этому экрану.</p></header><div className="grid grid-cols-1 md:grid-cols-2 gap-5">{cards.map(({ label, photo, setter, border }) => <section key={label} className={`rounded-lg border ${border} bg-[#0b1117] p-4`}><div className="flex justify-between items-end mb-3"><b className="font-mono text-cyan-300">ФОТО {label}</b>{selector("Запись", photo.id, setter)}</div><div className="h-64 rounded bg-[#101820] flex items-center justify-center"><img src={imageUrl(photo.id)} alt={photo.id} className="max-h-full max-w-full object-contain" /></div><div className="grid grid-cols-2 gap-2 mt-3 text-xs font-mono">{([["Дата",photo.date],["Ракурс",photo.bucket],["Q",photo.quality],["Yaw",photo.yaw],["Pitch",photo.pitch],["Roll",photo.roll],["Evidence",photo.evidenceState],["Pairs",photo.stage2PairCount]] as [string,unknown][]).map(([k,v])=><div key={k} className="rounded bg-[#101820] p-2"><span className="text-slate-500">{k}: </span>{show(v)}</div>)}</div></section>)}</div><section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4 text-sm"><h2 className="font-mono text-xs text-cyan-300 mb-2">РЕАЛЬНЫЕ МЕТРИКИ ПАРЫ</h2><p className="text-slate-300">Для пары <code>{a.id}</code> ↔ <code>{b.id}</code> текущий UI не выдумывает результат. API endpoint <code>/api/v1/pairs/&lt;a&gt;/&lt;b&gt;/metrics</code> требует отдельного подключения и проверки схемы ответа.</p></section></div>;
};
