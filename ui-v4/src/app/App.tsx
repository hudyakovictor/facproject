import { useState } from "react";
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
  const openPhoto = (id: string) => { setPhotoId(id); };
  const closePhoto = () => { setPhotoId(null); };
  const openCompare = (request: CompareRequest) => { setCompare(request); };
  const closeCompare = () => { setCompare(null); };
  return <div className="root-shell">
    <aside className="app-nav">
      <div className="nav-logo"><i>D</i><span>V4</span></div>
      <nav>
        <button className={view === "timeline" ? "active" : ""} onClick={() => setView("timeline")} title="Timeline"><span>⌁</span><b>Timeline</b></button>
        <button className={view === "runs" ? "active" : ""} onClick={() => setView("runs")} title="Run Manager"><span>▶</span><b>Run Manager</b></button>
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
