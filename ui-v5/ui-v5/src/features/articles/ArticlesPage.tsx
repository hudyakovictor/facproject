import React from "react";
import { useTimeline, useRunSummary } from "../../shared/api/queries";
import { BookOpen, AlertTriangle } from "lucide-react";

export const ArticlesPage: React.FC = () => {
  const timeline = useTimeline();
  const summary = useRunSummary();
  const photos = timeline.data?.photos ?? [];
  const years = photos.map(p => p.date?.slice(0, 4)).filter(Boolean);
  const first = years[0] ?? "н/д";
  const last = years.at(-1) ?? "н/д";
  return <div className="flex flex-col h-workspace w-full bg-surface-canvas text-ink-primary overflow-y-auto p-6 space-y-5"><header className="rounded-lg border border-cyan-600 bg-surface-base p-5"><div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300"><BookOpen className="h-5 w-5"/> МАТЕРИАЛЫ ПО ИССЛЕДОВАТЕЛЬСКОМУ ЗАПУСКУ</div><p className="text-xs text-ink-secondary mt-2">Страница собирает факты из локального Stage 2 API и не превращает отсутствующие расчёты в готовые научные тезисы.</p></header><section className="grid grid-cols-2 md:grid-cols-4 gap-3">{[["Наблюдений",photos.length],["Диапазон",`${first}—${last}`],["Источник",summary.data?.source_mode],["Change-point",summary.data?.technical_summary?.change_point_count]].map(([k,v])=><div key={String(k)} className="rounded-lg border border-line-default bg-surface-base p-4"><div className="text-xs text-ink-muted">{k}</div><div className="mt-2 text-lg font-mono text-cyan-300">{v ?? "н/д"}</div></div>)}</section><div className="grid md:grid-cols-3 gap-4">{[["Что реально измерено","Идентификатор записи, дата, ракурс, качество, флаги, статус измерения и связи Stage 2."],["Как читать timeline","Каждая строка — наблюдение из API. Смена даты или ракурса сама по себе не является выводом о личности."],["Что нужно подключить","Stage 3 report_data.json, артефакты mesh и отдельные проверенные метрики сравнений — если они будут рассчитаны backend."]].map(([title,text])=><article key={title} className="rounded-lg border border-line-default bg-surface-base p-5"><h2 className="font-mono text-xs text-cyan-300">{title}</h2><p className="mt-3 text-sm leading-relaxed text-ink-secondary">{text}</p></article>)}</div><div className="rounded border border-amber-500 bg-amber-soft p-4 text-xs text-amber-300"><AlertTriangle className="inline h-4 w-4 mr-1"/>Старые карточки с SNR, гипотезами, хешами и публикационными обещаниями удалены: в текущем API для них нет подтверждающих данных.</div></div>;
};
