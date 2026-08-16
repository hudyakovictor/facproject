import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, Database, ShieldCheck, type LucideIcon } from "lucide-react";
import { researchTimeline, runSummary } from "../../shared/researchApi";

const poseLabels: Record<string, string> = {
  frontal: "Фронтальный",
  left_light: "Левый лёгкий",
  left_mid: "Левый средний",
  left_deep: "Левый глубокий",
  right_light: "Правый лёгкий",
  right_mid: "Правый средний",
  right_deep: "Правый глубокий",
  unknown: "Не классифицирован",
};

export function OverviewPage() {
  const timeline = useQuery({ queryKey: ["research-timeline"], queryFn: researchTimeline });
  const summary = useQuery({ queryKey: ["run-summary"], queryFn: runSummary });
  const photos = timeline.data?.photos ?? [];
  const poses = [...new Set(photos.map((photo) => photo.bucket))].sort();
  const flagged = photos.filter((photo) => photo.flags.length > 0).length;
  const changePoints = summary.data?.technical_summary?.change_point_count ?? "—";
  const loading = timeline.isLoading || summary.isLoading;
  const error = timeline.error || summary.error;

  return <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
    <section className="rounded-lg border border-cyan-800/60 bg-[#0b1117] p-5">
      <div className="flex items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300 uppercase"><ShieldCheck className="h-5 w-5 text-cyan-400" />РЕАЛЬНЫЙ RESEARCH RUN · DEEPUTIN V5</div>
          <div className="text-xs text-slate-300 mt-1">Данные загружены из Stage 2 через `/api/v1/timeline`; это не вердикт.</div>
        </div>
        <div className={`rounded px-3 py-2 font-mono text-xs ${error ? "bg-rose-950 text-rose-300" : "bg-emerald-950 text-emerald-300"}`}>{loading ? "ЗАГРУЗКА…" : error ? "ОШИБКА API" : "SOURCE_MODE: RESEARCH"}</div>
      </div>
      {error && <div className="mt-4 rounded border border-rose-800 bg-rose-950/40 p-3 font-mono text-xs text-rose-300">{String(error)}</div>}
    </section>

    <section className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono">
      {([ ["ФОТОГРАФИИ", photos.length, Database], ["POSE BIN", poses.length, Activity], ["КАДРЫ С ФЛАГАМИ", flagged, AlertTriangle], ["CHANGE POINTS", changePoints, Activity] ] as [string, string | number, LucideIcon][]).map(([label, value, Glyph]) => {
        return <div key={String(label)} className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4"><div className="flex items-center gap-2 text-[10px] text-slate-400"><Glyph className="h-4 w-4 text-cyan-400" />{label}</div><div className="mt-2 text-2xl font-bold text-white">{value}</div></div>;
      })}
    </section>

    <section className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
      <div className="border-b border-[#1f2d3d] pb-2 font-mono text-xs font-bold text-cyan-300 uppercase">ПОКРЫТИЕ РЕАЛЬНЫХ ДАННЫХ ПО POSE BIN</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
        {poses.map((pose) => { const count = photos.filter((photo) => photo.bucket === pose).length; return <div key={pose} className="rounded-lg border border-[#1f2d3d] bg-[#101820] p-4"><div className="flex justify-between gap-2"><span className="font-bold text-white">{poseLabels[pose] ?? pose}</span><span className="text-cyan-400">{count}</span></div><div className="mt-2 text-slate-400">{pose}</div></div>; })}
      </div>
    </section>

    {timeline.data?.note && <div className="rounded border border-amber-800/60 bg-amber-950/20 p-4 font-mono text-xs text-amber-200">{timeline.data.note}</div>}
  </div>;
}
