import { useEffect, useMemo, useState } from "react";

import type { Photo } from "../data";
import Icon from "./Icon";
import { t } from "../i18n";
import {
  comparePhotos, comparePhotosFullMesh, fetchPhotoDetail, fetchSettings,
  type CompareResult, type FullMeshCompareResult, type AppSettings,
} from "../api";
import MeshViewer from "./MeshViewer";
import SettingsModal from "./SettingsModal";

interface Props {
  photos: Photo[];
}

/** Реальная попарная страница сравнения (ТЗ: "выбрать фото A и фото B").
 * Использует уже извлечённые landmarks через `/api/v1/compare` — не
 * извлекает 3D-модель заново (умное кэширование из ТЗ обеспечивается тем,
 * что backend переиспользует Record без повторного inference). При наличии
 * BFM-геометрии на backend доступен также режим "полный меш" —
 * `/api/v1/compare/full_mesh` — настоящая топология 35 709 вершин вместо
 * landmark-подмножества, ближе к "морфингу двух 3D-моделей" из ТЗ. Тепловая
 * карта настраивается тем же попапом настроек, что и остальной интерфейс. */
export default function PairCompareView({ photos }: Props) {
  const [photoAId, setPhotoAId] = useState<string>(photos[0]?.id ?? "");
  const [photoBId, setPhotoBId] = useState<string>(photos[1]?.id ?? "");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [fullMeshResult, setFullMeshResult] = useState<FullMeshCompareResult | null>(null);
  const [useFullMesh, setUseFullMesh] = useState(false);
  const [fullMeshUnavailable, setFullMeshUnavailable] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => { fetchSettings().then(setSettings).catch(() => undefined); }, []);

  const options = useMemo(() => photos.slice(0, 500).map(p => ({ id: p.id, label: `${p.id} · ${p.date} · ${p.bucket}` })), [photos]);

  const runCompare = async () => {
    setStatus("loading");
    setResult(null);
    setFullMeshResult(null);
    try {
      const compareResult = await comparePhotos(photoAId, photoBId);
      setResult(compareResult);
      if (useFullMesh && compareResult.status === "measured") {
        try {
          const meshResult = await comparePhotosFullMesh(photoAId, photoBId);
          setFullMeshResult(meshResult);
          setFullMeshUnavailable(false);
        } catch {
          setFullMeshUnavailable(true);
        }
      }
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  const stops = settings ? {
    blueCyan: settings.heatmap.stop_blue_cyan, cyanGreen: settings.heatmap.stop_cyan_green,
    greenRed: settings.heatmap.stop_green_red, saturatedRed: settings.heatmap.stop_saturated_red,
    maxReference: settings.heatmap.max_residual_reference,
  } : undefined;

  return (
    <section className="h-full overflow-auto bg-bg p-5 scanlines" data-scroll>
      <header className="mb-5 flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl tracking-forensic">{t.pairCompareTitle}</h1>
          <p className="font-mono text-[10px] text-text-muted mt-1">{t.pairCompareSub}</p>
        </div>
        <button onClick={() => setShowSettings(true)}
          className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-border bg-surface-2 hover:bg-surface-3 flex items-center gap-1.5">
          <Icon name="sliders" size={12} /> {t.openSettingsForHeatmap}
        </button>
      </header>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1">{t.choosePhotoA}</div>
          <select value={photoAId} onChange={e => setPhotoAId(e.target.value)}
            className="w-full bg-surface-2 border border-border p-2 font-mono text-[10px]">
            {options.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1">{t.choosePhotoB}</div>
          <select value={photoBId} onChange={e => setPhotoBId(e.target.value)}
            className="w-full bg-surface-2 border border-border p-2 font-mono text-[10px]">
            {options.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-5">
        <button onClick={runCompare} disabled={status === "loading" || !photoAId || !photoBId}
          className="px-4 py-2 font-mono text-[10px] tracking-forensic border border-info/50 bg-info/20 hover:bg-info/40 disabled:opacity-50">
          {status === "loading" ? t.comparing : t.runCompare}
        </button>
        <label className="flex items-center gap-2 font-mono text-[10px] text-text-muted cursor-pointer">
          <input type="checkbox" checked={useFullMesh} onChange={e => setUseFullMesh(e.target.checked)} />
          {t.fullMeshToggle}
        </label>
      </div>

      {status === "error" && (
        <div className="bg-critical/15 border border-critical p-2 font-mono text-[10px] text-critical mb-4">{errorMessage}</div>
      )}
      {fullMeshUnavailable && (
        <div className="bg-warning/15 border border-warning p-2 font-mono text-[10px] text-warning mb-4">{t.fullMeshUnavailable}</div>
      )}

      {result && result.status === "pose_mismatch" && (
        <div className="bg-warning/15 border border-warning p-3 font-mono text-[10px] text-warning flex items-start gap-2 mb-4">
          <Icon name="alert-triangle" size={14} color="#e8af34" className="mt-0.5 flex-shrink-0" />
          {t.poseMismatchWarning}
        </div>
      )}
      {result && result.status === "insufficient_visibility" && (
        <div className="bg-warning/15 border border-warning p-3 font-mono text-[10px] text-warning flex items-start gap-2 mb-4">
          <Icon name="alert-triangle" size={14} color="#e8af34" className="mt-0.5 flex-shrink-0" />
          {t.insufficientVisibility}
        </div>
      )}

      {result && result.status === "measured" && (
        <div className="grid grid-cols-[1fr_320px] gap-4">
          <div className="bg-surface border border-border" style={{ height: 480 }}>
            {fullMeshResult ? (
              <MeshViewer
                fullMesh={{
                  vertices: fullMeshResult.vertices_a,
                  triangles: fullMeshResult.triangles,
                  vertexValues: fullMeshResult.residuals,
                }}
                heatmapStops={stops}
                wireframe
              />
            ) : (
              <MeshViewer
                heatmapPoints={result.heatmap_points.map(p => ({ x: p.x, y: p.y, z: p.z, value: p.residual }))}
                heatmapStops={stops}
                wireframe
              />
            )}
          </div>
          <aside className="space-y-3">
            <div className="bg-surface border border-border p-3">
              <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-1">
                {t.heatmapView} {fullMeshResult && <span className="text-info">· BFM {fullMeshResult.vertex_count}v</span>}
              </div>
              {(fullMeshResult?.residual_stats ?? result.heatmap_stats) && (
                <div className="font-mono text-[10px] space-y-1">
                  {(() => {
                    const stats = fullMeshResult?.residual_stats ?? result.heatmap_stats!;
                    return (
                      <>
                        <div className="flex justify-between"><span className="text-text-muted">min</span><span>{stats.min.toFixed(4)}</span></div>
                        <div className="flex justify-between"><span className="text-text-muted">median</span><span>{stats.median.toFixed(4)}</span></div>
                        <div className="flex justify-between"><span className="text-text-muted">p95</span><span>{stats.p95.toFixed(4)}</span></div>
                        <div className="flex justify-between"><span className="text-text-muted">max</span><span>{stats.max.toFixed(4)}</span></div>
                      </>
                    );
                  })()}
                </div>
              )}
            </div>
            <div className="bg-surface border border-border p-3">
              <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-2">{t.perMetricDifference}</div>
              <div className="space-y-1 font-mono text-[10px]">
                {Object.entries(result.metrics).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="text-text-muted">{key}</span>
                    <span>{typeof value === "number" ? value.toFixed(5) : String(value)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-surface-2 border border-border p-2 font-mono text-[9px] text-text-faint">
              not_a_verdict: {String(result.not_a_verdict)}
              {fullMeshResult && <div className="mt-1">{fullMeshResult.note}</div>}
            </div>
          </aside>
        </div>
      )}

      {showSettings && (
        <SettingsModal onClose={() => setShowSettings(false)} onApplied={setSettings} />
      )}
    </section>
  );
}

// Экспорт для повторного использования в тестах/сторибуке при необходимости.
export { fetchPhotoDetail };
