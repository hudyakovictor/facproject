import { useTimeline, useRunSummary } from "../../shared/api/queries";
import { Activity, AlertTriangle, Database, ShieldCheck, type LucideIcon } from "lucide-react";
import { poseFullLabel, sortPoseBins } from "../../shared/poseBins";
import { countFindings } from "../../shared/findings";
import { resolveStage, stageDescription, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { describeError } from "../../shared/ui/errorDetail";
import { DataContractBanner } from "../../shared/ui/DataContractBanner";


export function OverviewPage() {
  const timeline = useTimeline();
  const summary = useRunSummary();
  const photos = timeline.data?.photos ?? [];
  const poses = sortPoseBins([...new Set(photos.map((photo) => photo.bucket))]);
  const flagged = countFindings(photos);
  const stage = resolveStage(timeline.data);
  const changePoints = summary.data?.technical_summary?.change_point_count ?? "н/д";
  const loading = timeline.isLoading || summary.isLoading;
  const error = timeline.error ?? summary.error;
  const errorDetail = error ? describeError(error) : null;

  return <div className="flex flex-col h-workspace w-full bg-surface-canvas text-ink-primary overflow-y-auto p-6 space-y-6">
    <section className="rounded-lg border border-cyan-600 bg-surface-base p-5">
      <div className="flex items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300 uppercase"><ShieldCheck className="h-5 w-5 text-cyan-400" />ИССЛЕДОВАТЕЛЬСКИЙ ЗАПУСК · DEEPUTIN V5 · {stageLabel(stage)}</div>
          <div className="text-xs text-ink-secondary mt-1">{stageDescription(stage)}</div>
        </div>
        <div className={`rounded px-3 py-2 font-mono text-xs ${error ? "bg-red-soft text-red-300" : "bg-green-soft text-green-300"}`}>{loading ? "ЗАГРУЗКА…" : error ? "ОШИБКА API" : "SOURCE_MODE: RESEARCH"}</div>
      </div>
      {errorDetail && <div className="mt-4 rounded border border-red-500 bg-red-soft p-3 font-mono text-xs text-red-300">{errorDetail.status ? `HTTP ${errorDetail.status} · ` : ""}{errorDetail.message}</div>}
    </section>

    <section className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono">
      {([ ["ФОТОГРАФИИ", photos.length, Database], ["POSE BIN", poses.length, Activity], ["НАХОДКИ", flagged, AlertTriangle], ["CHANGE POINTS", changePoints, Activity] ] as [string, string | number, LucideIcon][]).map(([label, value, Glyph]) => {
        return <div key={String(label)} className="rounded-lg border border-line-default bg-surface-base p-4"><div className="flex items-center gap-2 text-[10px] text-ink-muted"><Glyph className="h-4 w-4 text-cyan-400" />{label}</div><div className="mt-2 text-2xl font-bold text-ink-primary">{value}</div></div>;
      })}
    </section>

    <section className="rounded-lg border border-line-default bg-surface-base p-5 space-y-4">
      <div className="border-b border-line-default pb-2 font-mono text-xs font-bold text-cyan-300 uppercase">ПОКРЫТИЕ РЕАЛЬНЫХ ДАННЫХ ПО POSE BIN</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
        {poses.map((pose) => { const count = photos.filter((photo) => photo.bucket === pose).length; return <div key={pose} className="rounded-lg border border-line-default bg-surface-raised p-4"><div className="flex justify-between gap-2"><span className="font-bold text-ink-primary">{poseFullLabel(pose)}</span><span className="text-cyan-400">{count}</span></div><div className="mt-2 text-ink-muted">{pose}</div></div>; })}
      </div>
    </section>

    <StageBanner stage={stage} note={timeline.data?.note} />
    <DataContractBanner
      photos={photos}
      totalPhotos={photos.length}
      completeCount={timeline.data?.ui_fields_complete_photo_count}
      violationsByField={timeline.data?.ui_fields_violations_by_field}
      schema={timeline.data?.ui_fields_schema}
    />
  </div>;
}
