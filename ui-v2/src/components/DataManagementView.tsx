import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import {
  uploadPhoto, listJobs, submitJob, cancelJob, clearExtractedData, fetchSystemHealth,
  deletePhotoExtraction, type JobRow, type SystemHealth,
} from "../api";
import { useNotify } from "./Notifications";
import type { JobStatus } from "../api";

const JOB_STATUS_COLOR: Record<JobStatus, string> = {
  queued: "#797876", running: "#5591c7", complete: "#6daa45",
  blocked: "#e8af34", failed: "#ff3b30", cancelled: "#797876",
};
const JOB_STATUS_KEY: Record<JobStatus, keyof typeof t> = {
  queued: "jobStatusQueued", running: "jobStatusRunning", complete: "jobStatusComplete",
  blocked: "jobStatusBlocked", failed: "jobStatusFailed", cancelled: "jobStatusCancelled",
};

export default function DataManagementView() {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [system, setSystem] = useState<SystemHealth | null>(null);
  const [clearConfirming, setClearConfirming] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const notify = useNotify();

  const [analyzeLimit, setAnalyzeLimit] = useState<string>("0");

  const refreshJobs = () => {
    listJobs()
      .then(rows => setJobs(rows))
      .catch((err: unknown) => notify("critical", "Network Error", err instanceof Error ? err.message : String(err)));
  };

  useEffect(() => {
    refreshJobs();
    fetchSystemHealth()
      .then(setSystem)
      .catch((err: unknown) => notify("critical", "System Health Failed", err instanceof Error ? err.message : String(err)));
    const interval = setInterval(refreshJobs, 2000);
    return () => clearInterval(interval);
  }, [notify]);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    for (const file of Array.from(files)) {
      try {
        const result = await uploadPhoto(file);
        notify("success", "Upload Success", `${result.stored ? "Stored" : "Duplicate"}: ${result.photo_id}`);
      } catch (err) {
        notify("critical", "Upload Failed", err instanceof Error ? err.message : String(err));
      }
    }
  };

  const handleSubmitJob = async (kind: "extract" | "recompute_metrics") => {
    try {
      const extra = kind === "recompute_metrics" ? { limit: parseInt(analyzeLimit) || 0 } : {};
      const id = await submitJob(kind, extra);
      notify("success", "Job Submitted", `${kind} - ${id}`);
    } catch (err) {
      notify("critical", "Job Submission Failed", err instanceof Error ? err.message : String(err));
    }
    refreshJobs();
  };

  const handleCancelJob = async (jobId: string) => {
    try {
      await cancelJob(jobId);
      notify("info", "Job Cancelled", jobId);
    } catch (err) {
      notify("critical", "Cancel Failed", err instanceof Error ? err.message : String(err));
    }
    refreshJobs();
  };

  const handleDeleteExtraction = async () => {
    const photoId = deleteTarget.trim();
    if (!photoId) return;
    if (!window.confirm(t.deleteExtractionConfirm)) return;
    try {
      await deletePhotoExtraction(photoId);
      notify("success", "Extraction Deleted", photoId);
      setDeleteTarget("");
    } catch (err) {
      notify("critical", "Deletion Failed", err instanceof Error ? err.message : String(err));
    }
  };

  const handleClear = async () => {
    try {
      await clearExtractedData();
      notify("success", "Data Cleared", "All extracted data has been removed.");
    } catch (err) {
      notify("critical", "Clear Failed", err instanceof Error ? err.message : String(err));
    }
    setClearConfirming(false);
  };

  return (
    <section className="h-full overflow-auto bg-[#000000] p-6 scanlines" data-scroll>
      <header className="mb-8 border-b border-[#222] pb-4">
        <h1 className="font-mono text-sm tracking-[0.2em] text-[#e2e2e8] uppercase">{t.dataManagementTitle}</h1>
        <p className="font-mono text-[10px] text-[#797876] mt-1">{t.dataManagementSub}</p>
      </header>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="border border-[#333] bg-[#0a0a0a] p-4 flex flex-col justify-between">
          <div>
            <div className="font-mono text-[10px] tracking-forensic mb-2 text-[#e2e2e8] uppercase flex items-center gap-2">
              <Icon name="activity" size={12} color="#5591c7" /> {t.jobsTitle}
            </div>
            <p className="font-mono text-[9px] text-[#797876] mb-4">
              Launch backend Stage 1 (Extract) or Stage 2 (Metrics) processing pipelines.
            </p>
            <div className="flex gap-2 items-center mb-3">
              <span className="font-mono text-[9px] text-[#797876] w-16">LIMIT (0=ALL):</span>
              <input type="number" min="0" value={analyzeLimit} onChange={e => setAnalyzeLimit(e.target.value)}
                className="bg-[#141414] border border-[#333] px-2 py-1 font-mono text-[10px] text-white w-20 outline-none focus:border-[#5591c7]" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => handleSubmitJob("extract")}
              className="flex-1 px-3 py-2 font-mono text-[9px] tracking-forensic border border-[#333] hover:border-[#5591c7] hover:bg-[#5591c7]/10 transition-colors uppercase">
              {t.jobKindExtract}
            </button>
            <button onClick={() => handleSubmitJob("recompute_metrics")}
              className="flex-1 px-3 py-2 font-mono text-[9px] tracking-forensic border border-[#5591c7] bg-[#5591c7]/10 hover:bg-[#5591c7]/25 text-[#5591c7] transition-colors uppercase">
              {t.jobKindRecompute}
            </button>
          </div>
        </div>

        <div className="border border-[#333] bg-[#0a0a0a] p-4 flex flex-col justify-between">
          <div>
            <div className="font-mono text-[10px] tracking-forensic mb-2 text-[#dd6974] uppercase flex items-center gap-2">
              <Icon name="trash" size={12} /> {t.clearDataTitle}
            </div>
            <p className="font-mono text-[9px] text-[#797876] mb-4">
              {t.clearDataHint}
            </p>
          </div>
          <div className="space-y-3 border-t border-[#222] pt-3">
            {clearConfirming ? (
              <div className="flex gap-2">
                <button onClick={handleClear} className="flex-1 px-3 py-1.5 font-mono text-[9px] tracking-forensic border border-[#ff3b30] bg-[#ff3b30]/10 hover:bg-[#ff3b30]/20 text-[#ff3b30] uppercase">
                  {t.clearDataConfirm}
                </button>
                <button onClick={() => setClearConfirming(false)} className="px-3 py-1.5 font-mono text-[9px] tracking-forensic border border-[#333] text-[#797876] hover:text-white uppercase">
                  {t.cancel}
                </button>
              </div>
            ) : (
              <button onClick={() => setClearConfirming(true)}
                className="w-full px-3 py-1.5 font-mono text-[9px] tracking-forensic border border-[#333] hover:border-[#ff3b30] hover:bg-[#ff3b30]/10 text-[#797876] hover:text-[#ff3b30] transition-colors uppercase">
                {t.clearDataButton}
              </button>
            )}
            <div className="flex gap-2">
              <input value={deleteTarget} onChange={e => setDeleteTarget(e.target.value)}
                placeholder={t.deleteExtraction}
                className="flex-1 bg-[#141414] border border-[#333] px-2 py-1 font-mono text-[9px] text-white outline-none focus:border-[#ff3b30]" />
              <button onClick={handleDeleteExtraction} disabled={!deleteTarget.trim()}
                className="px-3 py-1.5 font-mono text-[9px] tracking-forensic border border-[#333] hover:border-[#ff3b30] text-[#797876] hover:text-[#ff3b30] disabled:opacity-30 uppercase transition-colors">
                {t.deleteExtraction}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="border border-[#333] bg-[#0a0a0a] p-4 mb-4">
        <div className="font-mono text-[10px] tracking-forensic mb-4 text-[#e2e2e8] uppercase flex items-center justify-between">
          <span className="flex items-center gap-2"><Icon name="list" size={12} color="#797876" /> Background Jobs</span>
          <span className="text-[9px] text-[#797876]">({jobs.length} jobs)</span>
        </div>
        {jobs.length === 0 ? (
          <div className="font-mono text-[9px] text-[#797876] text-center py-4 border border-dashed border-[#333]">{t.noJobsYet}</div>
        ) : (
          <div className="space-y-2">
            {jobs.map(job => (
              <div key={job.id} className="border border-[#333] p-2 font-mono text-[9px] bg-[#141414]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span style={{ color: JOB_STATUS_COLOR[job.status] }}>●</span>
                    <span className="text-white uppercase">{job.kind}</span>
                    <span className="text-[#4d4d4d]">{job.id}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span style={{ color: JOB_STATUS_COLOR[job.status] }}>{t[JOB_STATUS_KEY[job.status]] as string}</span>
                    {(job.status === "queued" || job.status === "running") && (
                      <button onClick={() => handleCancelJob(job.id)} className="text-[#ff3b30] hover:underline uppercase">
                        Abort
                      </button>
                    )}
                  </div>
                </div>
                {job.progress.total > 0 && (
                  <div className="h-0.5 bg-[#000] mt-2 relative overflow-hidden">
                    <div className="h-full bg-[#5591c7]" style={{ width: `${(job.progress.done / job.progress.total) * 100}%` }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {system && (
          <div className="border border-[#333] bg-[#0a0a0a] p-4">
            <div className="font-mono text-[10px] tracking-forensic mb-3 text-[#e2e2e8] uppercase flex items-center gap-2">
              <Icon name="database" size={12} color="#6daa45" /> System Health
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 font-mono text-[9px]">
              <div className="flex justify-between border-b border-[#222] pb-1">
                <span className="text-[#797876]">{t.cpuUsage}</span>
                <span className="text-white">{system.resources.available ? `${system.resources.cpu_percent?.toFixed(0)}%` : "—"}</span>
              </div>
              <div className="flex justify-between border-b border-[#222] pb-1">
                <span className="text-[#797876]">{t.memoryUsage}</span>
                <span className="text-white">{system.resources.available ? `${system.resources.process_rss_mb?.toFixed(0)} MB` : "—"}</span>
              </div>
              <div className="flex justify-between border-b border-[#222] pb-1 col-span-2">
                <span className="text-[#797876]">{t.gpuStatus}</span>
                <span className="text-[#6daa45]">{system.gpu.available ? (system.gpu.cuda_available ? system.gpu.device_name : "CPU only") : "n/a"}</span>
              </div>
              <div className="flex justify-between border-b border-[#222] pb-1">
                <span className="text-[#797876]">{t.modelWeights}</span>
                <span style={{ color: system.model_assets.ready ? "#6daa45" : "#e8af34" }}>{system.model_assets.ready ? "OK" : "MISSING"}</span>
              </div>
              <div className="flex justify-between border-b border-[#222] pb-1">
                <span className="text-[#797876]">{t.bfmGeometry}</span>
                <span style={{ color: system.bfm_geometry_available ? "#6daa45" : "#e8af34" }}>{system.bfm_geometry_available ? "OK" : "MISSING"}</span>
              </div>
            </div>
          </div>
        )}

        <div className="border border-[#333] bg-[#0a0a0a] p-4 flex flex-col justify-between">
          <div>
            <div className="font-mono text-[10px] tracking-forensic mb-2 text-[#e2e2e8] uppercase flex items-center gap-2">
              <Icon name="upload" size={12} color="#5591c7" /> {t.uploadPhoto}
            </div>
            <p className="font-mono text-[9px] text-[#797876] mb-4">
              {t.uploadHint}
            </p>
          </div>
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
            className="flex-1 border border-dashed border-[#444] bg-[#050505] hover:bg-[#111] flex items-center justify-center cursor-pointer font-mono text-[9px] text-[#797876] transition-colors py-8"
          >
            {t.uploadDropHint}
          </div>
          <input ref={fileInputRef} type="file" accept="image/jpeg,image/png" multiple className="hidden"
            onChange={e => handleFiles(e.target.files)} />
        </div>
      </div>

    </section>
  );
}
