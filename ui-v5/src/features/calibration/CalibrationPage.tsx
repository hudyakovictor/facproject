import React from "react";
import { useCalibrationHealth } from "../../shared/api/queries";
import { ShieldCheck, AlertTriangle } from "lucide-react";
import { poseLabel } from "../../shared/poseBins";
import { QueryState } from "../../shared/ui/QueryState";

export const CalibrationPage: React.FC = () => {
  const q = useCalibrationHealth();
  return (
    <QueryState
      query={q}
      loadingText="Загрузка состояния калибровки…"
      errorTitle="Калибровка недоступна"
      isEmpty={(data) => data.total_records === 0}
      emptyTitle="Калибровочный индекс пуст"
      emptyDescription="Endpoint ответил, но калибровочный пул не содержит ни одной записи. Пороги надёжности без него не рассчитываются."
    >
      {(d) => (<div className="flex flex-col h-workspace w-full bg-surface-canvas text-ink-primary overflow-y-auto p-6 space-y-5"><header className="rounded-lg border border-cyan-600 bg-surface-base p-5"><div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300"><ShieldCheck className="h-5 w-5"/> КАЛИБРОВОЧНЫЙ ПУЛ · РЕАЛЬНЫЙ API</div><p className="text-xs text-ink-secondary mt-2">Источник: {d.source}. Это описание состава калибровочного индекса, а не статистический verdict.</p></header><section className="grid grid-cols-2 md:grid-cols-4 gap-3">{[["Записей",d.total_records],["Персон",d.total_persons],["Корзин",Object.keys(d.buckets).length],["Надёжность", Object.entries(d.confidence_counts).map(([k, v]) => `${k}: ${v}`).join(" · ") || "н/д"]].map(([k,v])=><div key={String(k)} className="rounded-lg border border-line-default bg-surface-base p-4"><div className="text-xs text-ink-muted">{k}</div><div className="mt-2 text-lg font-mono text-cyan-300">{String(v)}</div></div>)}</section><section className="rounded-lg border border-line-default bg-surface-base p-5"><h2 className="font-mono text-xs text-cyan-300 mb-3">РАКУРСНЫЕ КОРЗИНЫ</h2><div className="grid md:grid-cols-3 gap-2">{Object.values(d.buckets).map(b=><div key={b.pose_bin} className="rounded bg-surface-raised p-3 text-xs"><div className="font-mono text-cyan-300">{poseLabel(b.pose_bin)}</div><div className="text-ink-secondary mt-1">кадров: {b.frame_count} · персон: {b.person_count}</div><div className="text-ink-muted">{b.confidence} · {b.runtime_usable ? "доступна" : "недоступна"}</div></div>)}</div></section><div className="rounded border border-amber-500 bg-amber-soft p-4 text-xs text-amber-300"><AlertTriangle className="inline h-4 w-4 mr-1"/>SNR, FDR, LOPO и параметры шумовой модели не входят в ответ текущего endpoint, поэтому старые числовые карточки удалены.</div></div>)}
    </QueryState>
  );
};
