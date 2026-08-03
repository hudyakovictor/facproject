import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Shell from "./components/Shell";
import OverviewPage from "./pages/OverviewPage";
import GalleryPage from "./pages/GalleryPage";
import InspectorPage from "./pages/InspectorPage";
import TimelinePage from "./pages/TimelinePage";
import ControlPage from "./pages/ControlPage";
import PairsPage from "./pages/PairsPage";
import RunPage from "./pages/RunPage";
import ReportPage from "./pages/ReportPage";
import CalibrationPage from "./pages/CalibrationPage";
import SettingsPage from "./pages/SettingsPage";
import { loadTimeline, pingBackend } from "./lib/api";
import type { RouteId, TimelineResult, ToastItem } from "./lib/types";

const EMPTY: TimelineResult = {
  photos: [], mode: "loading", message: "загрузка…", eraMeta: {}, rejected: [], chronologyAnomalies: {},
};

export default function App() {
  const [route, setRoute] = useState<RouteId>("overview");
  const [timeline, setTimeline] = useState<TimelineResult>(EMPTY);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = useCallback((kind: ToastItem["kind"], text: string) => {
    const id = Math.random().toString(36).slice(2, 10);
    setToasts(t => [...t, { id, kind, text }]);
    window.setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 5000);
  }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    const res = await loadTimeline();
    setTimeline(res);
    setSelectedId(prev => {
      if (res.photos.length && (!prev || !res.photos.some(p => p.id === prev))) return res.photos[0].id;
      return prev;
    });
    setRefreshing(false);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => { void pingBackend(ctrl.signal).then(setBackendUp); };
    tick();
    const t = window.setInterval(tick, 30000);
    return () => { ctrl.abort(); window.clearInterval(t); };
  }, []);

  const anomalyCount = useMemo(
    () => timeline.photos.filter(p => (p.flags?.length || 0) > 0 || p.exifAnomaly).length,
    [timeline.photos],
  );

  const openPhoto = (id: string) => { setSelectedId(id); setRoute("inspector"); };

  let body: ReactNode = null;
  switch (route) {
    case "overview": body = <OverviewPage timeline={timeline} onOpenGallery={() => setRoute("gallery")} onOpenControl={() => setRoute("control")} onOpenPhoto={openPhoto} />; break;
    case "gallery": body = <GalleryPage photos={timeline.photos} onOpen={openPhoto} />; break;
    case "inspector": body = <InspectorPage photos={timeline.photos} selectedId={selectedId} onSelect={setSelectedId} />; break;
    case "timeline": body = <TimelinePage photos={timeline.photos} selectedId={selectedId} onSelect={openPhoto} chronoAnomalies={timeline.chronologyAnomalies} />; break;
    case "pairs": body = <PairsPage photos={timeline.photos} />; break;
    case "calibration": body = <CalibrationPage />; break;
    case "run": body = <RunPage />; break;
    case "report": body = <ReportPage />; break;
    case "control": body = <ControlPage onRefreshTimeline={() => void refresh()} pushToast={pushToast} />; break;
    case "settings": body = <SettingsPage pushToast={pushToast} />; break;
  }

  return (
    <Shell
      route={route} setRoute={setRoute} backendUp={backendUp}
      photoCount={timeline.photos.length} anomalyCount={anomalyCount} dataMode={timeline.mode}
      onRefresh={() => void refresh()} refreshing={refreshing}
      toasts={toasts} onDismissToast={id => setToasts(t => t.filter(x => x.id !== id))}
    >{body}</Shell>
  );
}
