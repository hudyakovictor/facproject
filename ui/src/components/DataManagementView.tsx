import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import {
  uploadPhoto, listJobs, submitJob, cancelJob, clearExtractedData, fetchSystemHealth,
  type JobRow, type SystemHealth,
} from "../api";

const JOB_STATUS_COLOR: Record<string, string> = {
  queued: "#797876", running: "#5591c7", complete: "#6daa45",
  blocked: "#e8af34", failed: "#ff3b30", cancelled: "#797876",
};
const JOB_STATUS_KEY: Record<string, keyof typeof t> = {
  queued: "jobStatusQueued", running: "jobStatusRunning", complete: "jobStatusComplete",
  blocked: "jobStatusBlocked", failed: "jobStatusFailed", cancelled: "jobStatusCancelled",
};

/** Раздел "Управление данными": загрузка фото (реальный POST /api/v1/photos/upload),
 * пакетные задания (JobManager из ТЗ), очистка извлечённых данных, системное
 * здоровье. Задания честно показывают статус `blocked`, если в окружении нет
 * весов 3DDFA_V3 — не притворяются завершёнными. */
export default function DataManagementView() {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [system, setSystem] = useState<SystemHealth | null>(null);
  const [clearConfirming, setClearConfirming] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshJobs = () => { listJobs().then(setJobs).catch(() => undefined); };

  useEffect(() => {
    refreshJobs();
    fetchSystemHealth().then(setSystem).catch(() => undefined);
    const interval = setInterval(refreshJobs, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    for (const file of Array.from(files)) {
      setUploadStatus(`${t.uploading} ${file.name}`);
      try {
        const result = await uploadPhoto(file);
        setUploadStatus(`${result.stored ? t.uploadSuccess : t.uploadDuplicate}: ${result.photo_id}`);
      } catch (err) {
        setUploadStatus(err instanceof Error ? err.message : String(err));
      }
    }
  };

  const handleSubmitJob = async (kind: "extract" | "recompute_metrics") => {
    await submitJob(kind);
    refreshJobs();
  };

  const handleClear = async () => {
    await clearExtractedData();
    setClearConfirming(false);
  };

  return (
    <section className="h-full overflow-auto bg-bg p-5 scanlines" data-scroll>
      <header className="mb-5">
        <h1 className="font-display text-xl tracking-forensic">{t.dataManagementTitle}</h1>
        <p className="font-mono text-[10px] text-text-muted mt-1">{t.dataManagementSub}</p>
      </header>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-surface border border-border p-4">
          <div className="font-display text-xs tracking-forensic mb-2 flex items-center gap-2">
            <Icon name="upload" size={14} color="#5591c7" /> {t.uploadPhoto}
          </div>
          <div className="font-mono text-[9px] text-text-muted mb-3">{t.uploadHint}</div>
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
            role="button"
            tabIndex={0}
            aria-label={t.uploadPhoto}
            onKeyDown={e => { if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click(); }}
            className="border border-dashed border-border-strong bg-surface-2 p-6 text-center cursor-pointer hover:bg-surface-3 font-mono text-[10px] text-text-muted"
          >
            {t.uploadDropHint}
          </div>
          <input ref={fileInputRef} type="file" accept="image/jpeg,image/png" multiple className="hidden" aria-label={t.uploadPhoto}
            onChange={e => handleFiles(e.target.files)} />
          {uploadStatus && <div className="mt-2 font-mono text-[10px] text-text">{uploadStatus}</div>}
        </div>

        <div className="bg-surface border border-border p-4">
          <div className="font-display text-xs tracking-forensic mb-2 flex items-center gap-2">
            <Icon name="trash" size={14} color="#dd6974" /> {t.clearDataTitle}
          </div>
          <div className="font-mono text-[9px] text-text-muted mb-3">{t.clearDataHint}</div>
          {clearConfirming ? (
            <div className="space-y-2">
              <div className="font-mono text-[10px] text-warning">{t.clearDataConfirm}</div>
              <div className="flex gap-2">
                <button onClick={handleClear} className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-critical bg-critical/20 hover:bg-critical/40">
                  {t.clearDataButton}
                </button>
                <button onClick={() => setClearConfirming(false)} className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-border text-text-muted">
                  {t.cancel}
                </button>
              </div>
            </div>
          ) : (
            <button onClick={() => setClearConfirming(true)}
              className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-critical/50 bg-critical/10 hover:bg-critical/25">
              {t.clearDataButton}
            </button>
          )}
        </div>
      </div>

      <div className="bg-surface border border-border p-4 mb-6">
        <div className="font-display text-xs tracking-forensic mb-3">{t.jobsTitle}</div>
        <div className="flex gap-2 mb-4">
          <button onClick={() => handleSubmitJob("extract")}
            className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-info/50 bg-info/10 hover:bg-info/25">
            {t.jobKindExtract}
          </button>
          <button onClick={() => handleSubmitJob("recompute_metrics")}
            className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-info/50 bg-info/10 hover:bg-info/25">
            {t.jobKindRecompute}
          </button>
        </div>

        {jobs.length === 0 ? (
          <div className="font-mono text-[10px] text-text-muted">{t.noJobsYet}</div>
        ) : (
          <div className="space-y-2">
            {jobs.map(job => (
              <div key={job.id} className="border border-border p-2 font-mono text-[10px]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span style={{ color: JOB_STATUS_COLOR[job.status] }}>●</span>
                    <span>{job.kind}</span>
                    <span className="text-text-faint">{job.id}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span style={{ color: JOB_STATUS_COLOR[job.status] }}>{t[JOB_STATUS_KEY[job.status]] as string}</span>
                    {(job.status === "queued" || job.status === "running") && (
                      <button onClick={() => cancelJob(job.id).then(refreshJobs)} className="text-critical hover:underline">
                        {t.cancelJob}
                      </button>
                    )}
                  </div>
                </div>
                {job.progress.total > 0 && (
                  <div className="h-1 bg-surface-2 mt-1.5">
                    <div className="h-full bg-info" style={{ width: `${(job.progress.done / job.progress.total) * 100}%` }} />
                  </div>
                )}
                {job.error && <div className="mt-1 text-critical">{job.error}</div>}
              </div>
            ))}
          </div>
        )}
      </div>

      {system && (
        <div className="bg-surface border border-border p-4">
          <div className="font-display text-xs tracking-forensic mb-3 flex items-center gap-2">
            <Icon name="activity" size={14} color="#5591c7" /> {t.systemHealthTitle}
          </div>
          <div className="grid grid-cols-4 gap-3 font-mono text-[10px]">
            <div>
              <div className="text-text-muted">{t.cpuUsage}</div>
              <div className="text-text text-base">{system.resources.available ? `${system.resources.cpu_percent?.toFixed(0)}%` : "—"}</div>
            </div>
            <div>
              <div className="text-text-muted">{t.memoryUsage}</div>
              <div className="text-text text-base">{system.resources.available ? `${system.resources.process_rss_mb?.toFixed(0)} MB` : "—"}</div>
            </div>
            <div>
              <div className="text-text-muted">{t.gpuStatus}</div>
              <div className="text-text text-base">{system.gpu.available ? (system.gpu.cuda_available ? system.gpu.device_name : "CPU only") : "n/a"}</div>
            </div>
            <div>
              <div className="text-text-muted">{t.modelWeights}</div>
              <div style={{ color: system.model_assets.ready ? "#6daa45" : "#e8af34" }} className="text-base">
                {system.model_assets.ready ? t.weightsReady : t.weightsMissing}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
