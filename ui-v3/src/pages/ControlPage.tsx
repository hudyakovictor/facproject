import { useCallback, useEffect, useState } from "react";
import type { JobInfo } from "../lib/types";
import { cancelJob, clearExtractedData, getJob, listJobs, submitJob } from "../lib/api";
import { pct } from "../lib/format";
import { Banner, Button, Chip, Input, Modal, Panel, Progress, Select } from "../components/ui";
export default function ControlPage({ onRefreshTimeline, pushToast }: {
  onRefreshTimeline: () => void;
  pushToast: (kind: "ok" | "warn" | "bad" | "info", text: string) => void;
}) {
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [limitMode, setLimitMode] = useState<"all" | "limit">("limit");
  const [limit, setLimit] = useState(10);
  const [device, setDevice] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [active, setActive] = useState<JobInfo | null>(null);
  const [err, setErr] = useState("");
  const refreshJobs = useCallback(async () => {
    try { setJobs(await listJobs()); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }, []);
  useEffect(() => { void refreshJobs(); const t = window.setInterval(() => void refreshJobs(), 4000); return () => window.clearInterval(t); }, [refreshJobs]);
  useEffect(() => {
    if (!activeId) { setActive(null); return; }
    let dead = false;
    const tick = async () => {
      try {
        const j = await getJob(activeId);
        if (!dead) setActive(j);
        if (j.status === "complete") { pushToast("ok", `Задание ${j.kind} завершено`); onRefreshTimeline(); }
        else if (j.status === "failed" || j.status === "blocked") pushToast("bad", j.error || `Задание ${j.status}`);
      } catch { /* ignore */ }
    };
    void tick(); const t = window.setInterval(() => void tick(), 2000);
    return () => { dead = true; window.clearInterval(t); };
  }, [activeId, onRefreshTimeline, pushToast]);
  const startExtract = async () => {
    setBusy(true);
    try {
      const res = await submitJob({ kind: "extract", device, limit: limitMode === "all" ? 0 : Math.max(1, Number(limit) || 1) });
      setActiveId(res.job_id); pushToast("info", `Stage 1 extract · job ${res.job_id}`); await refreshJobs();
    } catch (e) { pushToast("bad", e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const startRecompute = async () => {
    setBusy(true);
    try {
      const res = await submitJob({ kind: "recompute_metrics" });
      setActiveId(res.job_id); pushToast("info", `Stage 2 recompute · job ${res.job_id}`); await refreshJobs();
    } catch (e) { pushToast("bad", e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const doClear = async () => {
    setBusy(true);
    try {
      const res = await clearExtractedData();
      pushToast("warn", `Очищено: ${(res.removed || []).join(", ") || "ничего"}. ${res.note || ""}`);
      setConfirmClear(false); onRefreshTimeline(); await refreshJobs();
    } catch (e) { pushToast("bad", e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const prog = active?.progress ? pct(active.progress.done || 0, active.progress.total || 0) : 0;
  return (
    <div className="page">
      <div className="page-hd"><div><h1>Управление анализом</h1><p>Запуск Stage 1 extract, пересчёт Stage 2, очистка производных данных. Исходные фото не удаляются.</p></div></div>
      {err && <Banner kind="warn" title="Jobs API">{err}</Banner>}
      <div className="grid-2">
        <Panel title="Запуск Stage 1 · extract">
          <div className="stack">
            <div className="field"><label>Объём прогона</label>
              <div className="seg">
                <button type="button" className={limitMode==="limit"?"active":""} onClick={() => setLimitMode("limit")}>лимит фото</button>
                <button type="button" className={limitMode==="all"?"active":""} onClick={() => setLimitMode("all")}>все фото</button>
              </div>
            </div>
            {limitMode === "limit" && <div className="field"><label>Максимум фото</label><Input type="number" min={1} value={limit} onChange={e => setLimit(Number(e.target.value))} /></div>}
            <div className="field"><label>Device</label>
              <Select value={device} onChange={e => setDevice(e.target.value)}><option value="auto">auto</option><option value="cpu">cpu</option><option value="cuda">cuda</option></Select>
            </div>
            <Banner kind="info" title="Smoke → gate → full">10 фото → 100 фото → полный прогон. limit=0 = все фото.</Banner>
            <Button variant="primary" disabled={busy} onClick={() => void startExtract()}>{busy ? "запуск…" : "запустить extract"}</Button>
          </div>
        </Panel>
        <Panel title="Stage 2 · recompute + очистка">
          <div className="stack">
            <p className="muted">Пересчёт pair metrics по уже извлечённому Stage 1 без net_recon.</p>
            <Button disabled={busy} onClick={() => void startRecompute()}>пересчитать метрики</Button>
            <div className="danger-zone">
              <strong>Опасная зона</strong>
              <p className="muted">Удаляет api_stage1 / api_stage2. Uploads не трогаются.</p>
              <Button variant="danger" disabled={busy} onClick={() => setConfirmClear(true)}>очистить извлечённые данные</Button>
            </div>
          </div>
        </Panel>
      </div>
      {active && (
        <Panel title={`Активное задание · ${active.id}`} right={<Chip kind={active.status==="complete"?"ok":active.status==="failed"||active.status==="blocked"?"bad":"info"}>{active.status}</Chip>}>
          <div className="stack">
            <div className="row-wrap">
              <Chip>{active.kind}</Chip>
              <span className="mono faint">{active.progress?.done || 0}/{active.progress?.total || 0}</span>
              <div className="spacer" />
              {(active.status === "queued" || active.status === "running") && (
                <Button size="sm" variant="danger" onClick={() => void cancelJob(active.id).then(refreshJobs)}>отменить</Button>
              )}
            </div>
            <Progress value={prog} />
            {active.error && <Banner kind="bad">{active.error}</Banner>}
            <div className="logs">{(active.logs || []).join("\n") || "логов пока нет"}</div>
          </div>
        </Panel>
      )}
      <Panel title="История jobs" right={<Button size="sm" onClick={() => void refreshJobs()}>обновить</Button>}>
        {!jobs.length ? <div className="muted">Нет заданий.</div> : (
          <div className="stack">{jobs.map(j => (
            <button key={j.id} type="button" className="job-card" style={{ textAlign: "left", width: "100%" }} onClick={() => setActiveId(j.id)}>
              <div className="row-wrap">
                <strong className="mono">{j.id}</strong><Chip>{j.kind}</Chip>
                <Chip kind={j.status==="complete"?"ok":j.status==="failed"||j.status==="blocked"?"bad":j.status==="running"?"info":""}>{j.status}</Chip>
                <span className="faint mono">{j.created_at}</span>
              </div>
              {j.error && <div className="muted" style={{ marginTop: 6 }}>{j.error}</div>}
            </button>
          ))}</div>
        )}
      </Panel>
      {confirmClear && (
        <Modal title="Очистить извлечённые данные?" onClose={() => setConfirmClear(false)}
          footer={<><Button onClick={() => setConfirmClear(false)}>отмена</Button><Button variant="danger" disabled={busy} onClick={() => void doClear()}>да, очистить</Button></>}>
          <Banner kind="bad" title="Необратимо для производных артефактов">Будут удалены api_stage1 и api_stage2. Исходные фото останутся.</Banner>
        </Modal>
      )}
    </div>
  );
}
