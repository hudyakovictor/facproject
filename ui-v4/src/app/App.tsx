import { useEffect, useRef, useState } from "react";
import { subscribeLogs } from "../shared/logger";
import LogPanel from "../features/logs/LogPanel";
import RecommendationsPanel from "../features/recommendations/RecommendationsPanel";
import TimelineView from "../features/timeline/TimelineView";
import DataManager from "../features/data-manager/DataManager";
import SettingsPage from "../features/settings/SettingsPage";
import PhotoPage from "../features/photo-lab/PhotoPage";
import ProfilesPage from "../features/profiles/ProfilesPage";
import RunManagerPage from "../features/runs/RunManagerPage";
import CalibrationPage from "../features/calibration/CalibrationPage";
import MorphingWorkspace from "../features/morphing/MorphingWorkspace";
import LandmarkCompareWorkspace from "../features/landmarks/LandmarkCompareWorkspace";

type View = "timeline" | "data" | "profiles" | "settings" | "runs" | "calibration";

export interface CompareRequest {
  kind: "morphing" | "landmarks";
  pose?: string | null;
  photoA?: string | null;
  photoB?: string | null;
}

export default function App() {
  const [view, setView] = useState<View>("timeline");
  const [photoId, setPhotoId] = useState<string | null>(null);
  const [compare, setCompare] = useState<CompareRequest | null>(null);
  const [logsOpen, setLogsOpen] = useState(false);
  const [unreadLogs, setUnreadLogs] = useState(0);
  const [recsOpen, setRecsOpen] = useState(false);
  const [recCount, setRecCount] = useState<number | null>(null);
  const seenRef = useRef(0);
  useEffect(() => {
    const unsubscribe = subscribeLogs(events => {
      if (logsOpen) {
        seenRef.current = events.length;
        setUnreadLogs(0);
      } else {
        const fresh = events.filter(event => event.level === "warn" || event.level === "error").length;
        setUnreadLogs(Math.max(0, fresh - Math.min(seenRef.current, events.length)));
      }
    });
    return unsubscribe;
  }, [logsOpen]);
  const openPhoto = (id: string) => { setPhotoId(id); };
  const closePhoto = () => { setPhotoId(null); };
  const openCompare = (request: CompareRequest) => { setCompare(request); };
  const closeCompare = () => { setCompare(null); };
  const navigateFromRecommendation = (kind: string, extra?: Record<string, unknown>) => {
    setRecsOpen(false);
    const pose = (extra?.pose as string) || null;
    const runId = (extra?.run_id as string) || null;
    const profileId = (extra?.profile_id as string) || null;
    switch (kind) {
      case "open_runs": setView("runs"); break;
      case "open_reports": setView("runs"); break;
      case "open_calibration": setView("calibration"); break;
      case "open_profiles": setView("profiles"); break;
      case "open_integrity": setView("data"); break;
      case "open_logs": setLogsOpen(true); break;
      case "open_timeline": setView("timeline"); break;
      case "open_dense_zone": setView("timeline"); break;
      case "open_landmarks":
        setView("timeline");
        setCompare({ kind: "landmarks", pose });
        break;
      case "open_run":
        setView("runs");
        if (runId) setTimeout(() => window.dispatchEvent(new CustomEvent("deeputin:open-run", { detail: { run_id: runId } })), 50);
        break;
      case "open_profile":
        setView("profiles");
        if (profileId) setTimeout(() => window.dispatchEvent(new CustomEvent("deeputin:open-profile", { detail: { profile_id: profileId } })), 50);
        break;
      default: setView("timeline");
    }
  };
  useEffect(() => {
    const onNavigate = (event: Event) => {
      const detail = (event as CustomEvent).detail as { view?: string } | undefined;
      if (detail?.view) setView(detail.view as View);
    };
    window.addEventListener("deeputin:navigate", onNavigate);
    return () => window.removeEventListener("deeputin:navigate", onNavigate);
  }, []);

  useEffect(() => {
    const onCompare = (event: Event) => {
      const detail = (event as CustomEvent).detail as { kind?: string; photo_a?: string; photo_b?: string } | undefined;
      if (!detail?.kind) return;
      if (detail.kind === "morphing" || detail.kind === "landmarks") {
        setCompare({ kind: detail.kind, photoA: detail.photo_a ?? null, photoB: detail.photo_b ?? null });
      }
    };
    window.addEventListener("deeputin:open-compare", onCompare);
    return () => window.removeEventListener("deeputin:open-compare", onCompare);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "l") {
        event.preventDefault();
        setLogsOpen(value => !value);
      }
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "r") {
        event.preventDefault();
        setRecsOpen(value => !value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return <div className="root-shell">
    <aside className="app-nav">
      <div className="nav-logo"><i>D</i><span>V4</span></div>
      <nav>
        <button className={view === "timeline" ? "active" : ""} onClick={() => setView("timeline")} title="Timeline"><span>⌁</span><b>Timeline</b></button>
        <button className={view === "runs" ? "active" : ""} onClick={() => setView("runs")} title="Run Manager"><span>▶</span><b>Run Manager</b></button>
        <button className={`${logsOpen ? "active" : ""} nav-logs`} onClick={() => setLogsOpen(value => !value)} title="Журнал событий (Ctrl+Shift+L)"><span>⌑</span><b>Logs</b>{unreadLogs > 0 && <i className="nav-badge">{unreadLogs > 99 ? "99+" : unreadLogs}</i>}</button>
        <button className={`${recsOpen ? "active" : ""} nav-recs`} onClick={() => setRecsOpen(value => !value)} title="Рекомендации (Ctrl+Shift+R)"><span>💡</span><b>Advisor</b>{recCount !== null && recCount > 0 && <i className="nav-badge rec-badge">{recCount > 99 ? "99+" : recCount}</i>}</button>
        <button className={view === "calibration" ? "active" : ""} onClick={() => setView("calibration")} title="Calibration"><span>⌗</span><b>Calibration</b></button>
        <button className={view === "data" ? "active" : ""} onClick={() => setView("data")} title="Data Manager"><span>▦</span><b>Data Manager</b></button>
        <button className={view === "profiles" ? "active" : ""} onClick={() => setView("profiles")} title="Profiles"><span>▣</span><b>Profiles</b></button>
        <button className={view === "settings" ? "active" : ""} onClick={() => setView("settings")} title="Настройки"><span>⚙</span><b>Settings</b></button>
        <button className={photoId !== null ? "active" : ""} onClick={() => setPhotoId("")} title="Фото"><span>◫</span><b>Photo Lab</b></button>
      </nav>
      <small>APP6<br />CONTROL</small>
    </aside>
    <div className="app-content">
      {view === "timeline" && <TimelineView openPhoto={openPhoto} openCompare={openCompare} />}
      {view === "data" && <DataManager />}
      {view === "profiles" && <ProfilesPage />}
      {view === "settings" && <SettingsPage openPhoto={openPhoto} />}
      {view === "runs" && <RunManagerPage />}
      {view === "calibration" && <CalibrationPage />}
    </div>
    {photoId !== null && (
      <div className="photo-modal-backdrop" onClick={closePhoto}>
        <div className="photo-modal" onClick={event => event.stopPropagation()}>
          <button className="photo-modal-close" onClick={closePhoto} title="Закрыть">×</button>
          <PhotoPage initialId={photoId} />
        </div>
      </div>
    )}
    <LogPanel open={logsOpen} onClose={() => setLogsOpen(false)} />
    <RecommendationsPanel
      open={recsOpen}
      onClose={() => setRecsOpen(false)}
      onNavigate={navigateFromRecommendation}
    />
    <RecBadge onCount={setRecCount} />
    {compare !== null && (
      <div className="workspace-backdrop" onClick={closeCompare}>
        <div className="workspace-modal-shell" onClick={event => event.stopPropagation()}>
          {compare.kind === "morphing" ? (
            <MorphingWorkspace initialPose={compare.pose} initialA={compare.photoA} initialB={compare.photoB} onClose={closeCompare} />
          ) : (
            <LandmarkCompareWorkspace initialPose={compare.pose} initialA={compare.photoA} initialB={compare.photoB} onClose={closeCompare} />
          )}
        </div>
      </div>
    )}
  </div>;
}


function RecBadge({ onCount }: { onCount: (count: number | null) => void }) {
  useEffect(() => {
    let dead = false;
    let timer: number | null = null;
    const tick = async () => {
      try {
        const response = await fetch("/api/v1/recommendations", { headers: { Accept: "application/json" } });
        if (response.ok) {
          const payload = await response.json() as { count?: number };
          if (!dead) onCount(payload.count ?? null);
        }
      } catch { if (!dead) onCount(null); }
      timer = window.setTimeout(tick, 60_000);
    };
    void tick();
    return () => { dead = true; if (timer !== null) window.clearTimeout(timer); };
  }, [onCount]);
  return null;
}
