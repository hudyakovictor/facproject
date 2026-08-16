import React, { useMemo } from "react";
import { useTimeline } from "../../shared/api/queries";
import { ShieldCheck } from "lucide-react";
import { poseLabel } from "../../shared/poseBins";
import { substantiveFlags } from "../../shared/findings";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { QueryState } from "../../shared/ui/QueryState";
import { PhotoImage } from "../../shared/ui/PhotoImage";
import { useAnalysisStore } from "../../shared/state/analysisStore";

const value = (v: unknown) => v === null || v === undefined || v === "" ? "н/д" : String(v);

export const PhotoInspectorPage: React.FC = () => {
  const query = useTimeline();
  const photos = useMemo(() => query.data?.photos ?? [], [query.data]);
  /** Кадр берётся из общего стора: выбор на таймлайне или в палитре ⌘K
   *  открывает здесь ту же запись. */
  const { selectedPhoto: selectedId, setSelectedPhoto: setSelectedId } = useAnalysisStore();
  const selected = useMemo(() => photos.find((p) => p.id === (selectedId ?? photos[0]?.id)) ?? null, [photos, selectedId]);

  const stage = resolveStage(query.data);
  return (
    <QueryState
      query={query}
      loadingText="Загрузка записей фотографий…"
      errorTitle="Инспектор недоступен"
      isEmpty={(data) => data.photos.length === 0 || selected === null}
      emptyTitle="Записей нет"
      emptyDescription="API вернул пустой список фотографий, показывать в инспекторе нечего."
    >
      {() => selected && (<div className="flex flex-col h-workspace w-full bg-surface-canvas text-ink-primary overflow-y-auto p-6 space-y-5">
    <StageBanner stage={stage} note={query.data?.note} />
    <header className="rounded-lg border border-line-default bg-surface-base p-4 flex flex-wrap gap-4 items-center justify-between">
      <div><div className="font-mono text-sm font-bold text-cyan-300">ИНСПЕКТОР ФОТОГРАФИИ: {selected.id}</div><div className="text-xs text-ink-muted">{stageLabel(stage)} · {value(selected.date)} · источник: {selected.sourceMode}</div></div>
      <div className="flex gap-2 text-xs font-mono"><span className="rounded border border-line-default px-2 py-1">Ракурс: {poseLabel(selected.bucket)}</span><span className="rounded border border-line-default px-2 py-1">Q: {value(selected.quality)}</span><span className="rounded border border-green-500 bg-green-soft px-2 py-1 text-green-300"><ShieldCheck className="inline h-3 w-3" /> доказательство: {value(selected.evidenceState)}</span></div>
    </header>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <section className="rounded-lg border border-line-default bg-surface-base p-4"><div className="flex justify-between mb-3 font-mono text-xs text-ink-secondary"><span>ИСХОДНЫЙ КАДР STAGE 2</span><select aria-label="Выбор фотографии" value={selected.id} onChange={(e) => setSelectedId(e.target.value)} className="bg-surface-raised border border-line-default rounded px-2 py-1 max-w-[60%]">{photos.slice(0, 500).map((p) => <option key={p.id} value={p.id}>{p.date ?? p.id} · {p.id}</option>)}</select></div><div className="h-[380px] bg-surface-raised rounded border border-line-default flex items-center justify-center"><PhotoImage photoId={selected.id} alt={`Кадр ${selected.id}`} variant="contain" className="max-h-full max-w-full" /></div></section>
      <section className="rounded-lg border border-line-default bg-surface-base p-4"><div className="mb-3 font-mono text-xs text-cyan-300">ПРЕВЬЮ РЕАЛЬНОГО КАДРА</div><div className="h-[380px] rounded border border-line-default bg-surface-raised flex items-center justify-center"><PhotoImage photoId={selected.id} alt={`Реальный кадр ${selected.id}`} variant="contain" className="max-h-full max-w-full" /></div><p className="mt-2 text-xs text-amber-300">Mesh-артефакт отсутствует в API. Синтетическая 3D-модель не показывается.</p></section>
    </div>
    <section className="rounded-lg border border-line-default bg-surface-base p-4"><h2 className="font-mono text-xs font-bold text-cyan-300 mb-3">ФАКТЫ ИЗ API, БЕЗ ПРОИЗВОДНЫХ ЗАГЛУШЕК</h2><div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">{[["Дата", selected.date],["Yaw", selected.yaw], ["Pitch", selected.pitch], ["Roll", selected.roll], ["Качество", selected.quality], ["Измерения", selected.measurementStatus], ["Пар Stage 2", selected.stage2PairCount ?? null], ["Флаги", substantiveFlags(selected).length ? substantiveFlags(selected).join(", ") : "нет"]].map(([k,v]) => <div key={String(k)} className="rounded bg-surface-raised p-3"><div className="text-ink-muted">{k}</div><div className="text-ink-primary mt-1">{value(v)}</div></div>)}</div></section>
  </div>)}
    </QueryState>
  );
};

