import React from "react";
import { useTimeline, useRunSummary } from "../../shared/api/queries";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { ErrorState, LoadingState } from "../../shared/ui/states";
import { sortPhotosByTime } from "../../shared/time";

/** Пары «ключ: значение» вместо JSON.stringify в разметке. */
const CountList: React.FC<{ counts?: Record<string, number> | null }> = ({ counts }) => {
  const entries = Object.entries(counts ?? {});
  if (entries.length === 0) return <span className="text-ink-muted">н/д</span>;
  return (
    <ul className="mt-1 flex flex-wrap gap-1.5">
      {entries.map(([key, value]) => (
        <li key={key} className="rounded bg-surface-raised px-2 py-0.5 font-mono text-[11px]">
          <span className="text-ink-muted">{key}: </span>
          <span className="text-ink-primary">{value.toLocaleString("ru-RU")}</span>
        </li>
      ))}
    </ul>
  );
};

export const HypothesisValidationPage: React.FC = () => {
  const timeline = useTimeline();
  const summary = useRunSummary();
  const photos = sortPhotosByTime(timeline.data?.photos ?? []).dated;
  const technical = summary.data?.technical_summary;
  const stage = resolveStage(timeline.data);
  if (timeline.isLoading || summary.isLoading) return <LoadingState text="Загрузка результатов запуска…" />;
  if (timeline.error || summary.error) return <ErrorState title="Данные запуска недоступны" error={timeline.error ?? summary.error} onRetry={() => { void timeline.refetch(); void summary.refetch(); }} />;
  return <div className="flex flex-col h-workspace w-full bg-surface-canvas text-ink-primary overflow-y-auto p-6 space-y-5"><StageBanner stage={stage} note={timeline.data?.note} /><header className="rounded-lg border border-amber-500 bg-surface-base p-5"><div className="font-mono text-sm font-bold text-amber-300">ВАЛИДАЦИЯ ГИПОТЕЗ · {stageLabel(stage)}</div><p className="text-xs text-ink-secondary mt-2">В текущем backend-контракте нет рассчитанных карточек H0/H1/H2, SNR, similarity или confidence. Поэтому старые демонстрационные гипотезы удалены из экрана и не заменяются синтетическими.</p></header><section className="grid grid-cols-2 md:grid-cols-4 gap-3">{[["Записей",photos.length],["Change-point",technical?.change_point_count],["Источник",summary.data?.source_mode],["Вердикт",summary.data?.not_a_verdict ? "не verdict" : "н/д"]].map(([k,v])=><div key={String(k)} className="rounded-lg border border-line-default bg-surface-base p-4"><div className="text-xs text-ink-muted">{k}</div><div className="mt-2 text-lg font-mono text-cyan-300">{v ?? "н/д"}</div></div>)}</section><section className="rounded-lg border border-line-default bg-surface-base p-5"><h2 className="font-mono text-xs text-cyan-300">ДОСТУПНЫЕ ФАКТЫ ВМЕСТО ВЫДУМАННЫХ ГИПОТЕЗ</h2><div className="mt-3 grid md:grid-cols-2 gap-3 text-xs text-ink-secondary"><div>Диапазон: {photos[0]?.date ?? "н/д"} — {photos.at(-1)?.date ?? "н/д"}</div><div>Статусы:<CountList counts={technical?.status_counts} /></div><div>Evidence:<CountList counts={technical?.evidence_state_counts} /></div><div>Поля анализа: качество, ракурс, флаги, статус измерений и пары.</div></div><div className="mt-5 rounded border border-amber-500 bg-amber-soft p-3 text-xs text-amber-300">Чтобы показывать H0/H1/H2, backend должен вернуть их расчёт и схему доказательств. До этого экран намеренно не делает научных выводов.</div></section></div>;
};
