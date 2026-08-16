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
  return <div className="flex h-workspace w-full flex-col gap-5 overflow-y-auto bg-surface-canvas p-6 text-ink-primary">
    <StageBanner stage={stage} note={timeline.data?.note} />
    <header className="rounded-xl border border-amber-500/60 bg-surface-base p-5">
      <div className="font-mono text-sm font-bold text-amber-300">ГИПОТЕЗЫ · {stageLabel(stage)}</div>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink-secondary">Здесь появятся проверяемые гипотезы только после расчёта backend. Сейчас экран показывает факты запуска и честно отмечает, что научный вывод ещё не сформирован.</p>
    </header>
    <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {[["Записей", photos.length], ["Точек перелома", technical?.change_point_count], ["Источник", summary.data?.source_mode], ["Статус", "расчёт не выполнен"]].map(([k, v]) => <div key={String(k)} className="rounded-xl border border-line-default bg-surface-base p-4"><div className="text-xs text-ink-muted">{k}</div><div className="mt-2 truncate font-mono text-lg text-cyan-300">{v ?? "н/д"}</div></div>)}
    </section>
    <section className="rounded-xl border border-line-default bg-surface-base p-5">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-mono text-xs text-cyan-300">ЧТО УЖЕ ДОСТУПНО</h2><span className="text-xs text-ink-muted">без интерпретации</span></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg bg-surface-raised p-4 text-sm text-ink-secondary"><div className="text-xs text-ink-muted">Диапазон</div><div className="mt-1 font-mono text-ink-primary">{photos[0]?.date ?? "н/д"} — {photos.at(-1)?.date ?? "н/д"}</div></div>
        <div className="rounded-lg bg-surface-raised p-4 text-sm text-ink-secondary"><div className="text-xs text-ink-muted">Статусы измерений</div><CountList counts={technical?.status_counts} /></div>
        <div className="rounded-lg bg-surface-raised p-4 text-sm text-ink-secondary"><div className="text-xs text-ink-muted">Состояние evidence</div><CountList counts={technical?.evidence_state_counts} /></div>
        <div className="rounded-lg bg-surface-raised p-4 text-sm text-ink-secondary"><div className="text-xs text-ink-muted">Поля</div><div className="mt-1">качество, ракурс, флаги, статус и связи пар</div></div>
      </div>
    </section>
    <div className="rounded-xl border border-amber-500/60 bg-amber-soft p-4 text-sm text-amber-300">H0/H1/H2, SNR, similarity и confidence не подменяются демонстрационными значениями. Они станут доступны после появления соответствующего расчёта и схемы доказательств в API.</div>
  </div>;
};
