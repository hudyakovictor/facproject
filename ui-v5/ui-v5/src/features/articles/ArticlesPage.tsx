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
  return <div className="flex h-workspace w-full flex-col gap-5 overflow-y-auto bg-surface-canvas p-6 text-ink-primary"><header className="rounded-xl border border-cyan-600 bg-surface-base p-5"><div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300"><BookOpen className="h-5 w-5"/> СТАТЬИ И МАТЕРИАЛЫ</div><p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink-secondary">Короткая навигация по тому, что действительно есть в текущем запуске. Это не готовые научные выводы и не публикационные тезисы.</p></header><section className="grid grid-cols-2 gap-3 md:grid-cols-4">{[["Наблюдений",photos.length],["Диапазон",`${first} — ${last}`],["Источник",summary.data?.source_mode],["Точек перелома",summary.data?.technical_summary?.change_point_count]].map(([k,v])=><div key={String(k)} className="rounded-xl border border-line-default bg-surface-base p-4"><div className="text-xs text-ink-muted">{k}</div><div className="mt-2 truncate font-mono text-lg text-cyan-300">{v ?? "н/д"}</div></div>)}</section><div className="grid gap-4 md:grid-cols-3">{[["01 · Наблюдения","Идентификатор, дата, ракурс, качество, флаги и статус измерения. Открывайте кадр на таймлайне, чтобы перейти к подробностям."],["02 · Сравнение","Парный экран показывает только рассчитанные поля и явно отмечает ограничения. Отсутствующие 3D-артефакты не заменяются картинкой-заглушкой."],["03 · Ограничения","Если Stage 3, калибровка или BFM-меш не доступны, интерфейс показывает причину. Это ограничение запуска, а не скрытый результат."]].map(([title,text])=><article key={title} className="rounded-xl border border-line-default bg-surface-base p-5"><h2 className="font-mono text-xs text-cyan-300">{title}</h2><p className="mt-3 text-sm leading-relaxed text-ink-secondary">{text}</p></article>)}</div><div className="rounded-xl border border-amber-500/60 bg-amber-soft p-4 text-sm text-amber-300"><AlertTriangle className="mr-1 inline h-4 w-4"/>В интерфейсе не показываются SNR, гипотезы, хеши и другие неподтверждённые значения: в текущем API для них нет расчёта.</div></div>;
};
