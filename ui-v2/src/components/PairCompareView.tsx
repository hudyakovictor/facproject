import { useEffect, useRef, useState } from "react";
import PhotoPicker from "./PhotoPicker";

import type { Photo } from "../data";
import Icon from "./Icon";
import { t } from "../i18n";
import {
  comparePhotos, comparePhotosFullMesh, fetchCalibrationMatchForPhoto, fetchPhotoDetail, fetchSettings, saveSettings,
  type CalibrationMatch, type CompareResult, type FullMeshCompareResult, type AppSettings,
} from "../api";
import MeshViewer from "./LazyMeshViewer";
import { DEFAULT_HEATMAP_STOPS } from "../heatscale";
import SettingsModal from "./SettingsModal";
import { AlignmentDiagnostics, HeatmapLegend, MetricsTable, PhotoPair, ZoneBreakdown } from "./ComparePanels";
import LandmarkPanel from "./LandmarkPanel";
import NoiseCalibrationPanel from "./NoiseCalibrationPanel";
import HeatmapWorkbench from "./HeatmapWorkbench";
import PairKeysPanel from "./PairKeysPanel";
import ErrorBoundary from "./ErrorBoundary";
import { DEFAULT_SHIFT_THRESHOLDS, type ShiftThresholds } from "../landmarks";


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
  const [showVectors, setShowVectors] = useState(false);
  const [fullMeshUnavailable, setFullMeshUnavailable] = useState(false);
  const [morphT, setMorphT] = useState(0);
  const [calibrationA, setCalibrationA] = useState<CalibrationMatch | null>(null);
  const [calibrationB, setCalibrationB] = useState<CalibrationMatch | null>(null);


  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  const [settingsFailed, setSettingsFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then(value => { if (!cancelled) { setSettings(value); setSettingsFailed(false); } })
      .catch(() => { if (!cancelled) setSettingsFailed(true); });
    return () => { cancelled = true; };
  }, []);

  /** P2.3 (DEV_FIX_TZ 3.3): счётчик запусков сравнения. Каждый запуск получает
   * свой номер; результат применяется только если он всё ещё актуален. Раньше
   * calibration-запросы были fire-and-forget, и ответ старого сравнения мог
   * перезаписать данные нового. */
  const runIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => () => abortRef.current?.abort(), []);

  // Селекторы работают со ВСЕМ архивом через PhotoPicker (поиск + честное
  // усечение). Прежний `.slice(0, 500)` молча скрывал остальные кадры.
  const hasPhotos = photos.length > 0;
  const stage2Available = photos.some(
    p => p.analysisStage !== "stage1_inventory" && p.measurementStatus !== "not_compared"
  );

  const runCompare = async () => {
    if (!stage2Available) {
      setStatus("error");
      setErrorMessage("Попарное геометрическое сравнение доступно только после расчёта Stage 2. Сейчас загружен только инвентарь Stage 1.");
      return;
    }
    // Отменяем всё, что осталось от предыдущего запуска, и помечаем новый.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const runId = ++runIdRef.current;
    const isStale = () => runId !== runIdRef.current || controller.signal.aborted;

    setStatus("loading");
    setResult(null);
    setFullMeshResult(null);
    setFullMeshUnavailable(false);
    setMorphT(0);
    setCalibrationA(null);
    setCalibrationB(null);
    try {
      const compareResult = await comparePhotos(photoAId, photoBId);
      if (isStale()) return;
      setResult(compareResult);

      if (useFullMesh && compareResult.status === "measured") {
        try {
          const meshResult = await comparePhotosFullMesh(photoAId, photoBId);
          if (isStale()) return;
          setFullMeshResult(meshResult);
          setFullMeshUnavailable(false);
        } catch {
          if (isStale()) return;
          setFullMeshUnavailable(true);
        }
      }

      // Калибровочные подборы дожидаются здесь же: статус "idle" не должен
      // выставляться раньше, чем панель действительно готова.
      const [calA, calB] = await Promise.all([
        fetchCalibrationMatchForPhoto(photoAId).catch(() => null),
        fetchCalibrationMatchForPhoto(photoBId).catch(() => null),
      ]);
      if (isStale()) return;
      setCalibrationA(calA);
      setCalibrationB(calB);
      setStatus("idle");
    } catch (err) {
      if (isStale()) return;
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  /** Пороги классификации точек сохраняются в настройки backend, чтобы
   * калибровка порогов не терялась между сеансами. Ошибка сохранения не
   * должна ломать анализ — она лишь не переживёт перезагрузку. */
  const [thresholdSaveFailed, setThresholdSaveFailed] = useState(false);
  const handleThresholdsChange = (next: ShiftThresholds) => {
    setSettings(prev => (prev ? { ...prev, landmark_shift: next } : prev));
    if (!settings) return;
    // 🔧 Раньше ошибка глушилась `.catch(() => undefined)`: анализ
    // действительно продолжал работать, но пользователь был уверен, что
    // откалиброванные пороги сохранены, — а они терялись при перезагрузке.
    saveSettings({ ...settings, landmark_shift: next })
      .then(() => setThresholdSaveFailed(false))
      .catch(() => setThresholdSaveFailed(true));
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

      {!stage2Available && (
        <div role="status" className="mb-4 border border-warning/50 bg-warning/10 p-4 font-mono text-[11px] text-warning">
          Попарное геометрическое сравнение пока недоступно: реальные записи Stage 1 содержат фото, даты, ракурсы и качество, но не содержат измеренных landmarks. Сначала выполните Stage 2.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1">{t.choosePhotoA}</div>
          {hasPhotos
            ? <PhotoPicker photos={photos} value={photoAId} onChange={setPhotoAId} label={t.choosePhotoA} />
            : <div className="font-mono text-[10px] text-text-muted">{t.noPhotosToCompare}</div>}
        </div>
        <div>
          <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1">{t.choosePhotoB}</div>
          {hasPhotos
            ? <PhotoPicker photos={photos} value={photoBId} onChange={setPhotoBId} label={t.choosePhotoB} />
            : <div className="font-mono text-[10px] text-text-muted">{t.noPhotosToCompare}</div>}
        </div>
      </div>

      <div className="flex items-center gap-4 mb-5">
        <button onClick={runCompare} disabled={status === "loading" || !stage2Available || !photoAId || !photoBId}
          className="px-4 py-2 font-mono text-[10px] tracking-forensic border border-info/50 bg-info/20 hover:bg-info/40 disabled:opacity-50">
          {status === "loading" ? t.comparing : t.runCompare}
        </button>
        <label className="flex items-center gap-2 font-mono text-[10px] text-text-muted cursor-pointer">
          <input type="checkbox" checked={useFullMesh} onChange={e => setUseFullMesh(e.target.checked)}
            aria-label={t.fullMeshToggle} />
          {t.fullMeshToggle}
        </label>
      </div>

      {settingsFailed && (
        <div role="status" className="bg-warning/15 border border-warning p-2 font-mono text-[10px] text-warning mb-4">{t.settingsLoadFailed}</div>
      )}
      {status === "error" && (
        <div role="alert" className="bg-critical/15 border border-critical p-2 font-mono text-[10px] text-critical mb-4">{errorMessage}</div>
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
          <div className="flex flex-col gap-2">
            {/* ТЗ: «визуализацией обоих изображений рядом» */}
            <PhotoPair a={result.photo_a} b={result.photo_b} />
            <div className="bg-surface border border-border" style={{ height: 480 }}>
              {fullMeshResult ? (
                <MeshViewer
                  fullMesh={{
                    vertices: fullMeshResult.vertices_a,
                    verticesTarget: fullMeshResult.vertices_b_aligned,
                    triangles: fullMeshResult.triangles,
                    vertexValues: fullMeshResult.residuals,
                  }}
                  morphT={morphT}
                  heatmapStops={stops}
                  wireframe
                  showVectors={showVectors}
                />
              ) : (
                <MeshViewer
                  heatmapPoints={result.heatmap_points
                    .filter(p => p.visible !== false && p.x !== null && p.residual !== null)
                    .map(p => ({ x: p.x as number, y: p.y as number, z: p.z as number, value: p.residual as number }))}
                  heatmapStops={stops}
                  wireframe
                />
              )}
            </div>
            {fullMeshResult && (
              <div className="bg-[#0a0a0a] border border-[#333] p-2 flex flex-col gap-2">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[9px] tracking-forensic text-[#5591c7] w-6 text-center">A</span>
                  <input type="range" min={0} max={1} step={0.01} value={morphT}
                    onChange={e => setMorphT(+e.target.value)} className="flex-1"
                    aria-label={t.morphSliderLabel} />
                  <span className="font-mono text-[9px] tracking-forensic text-[#e8af34] w-6 text-center">B</span>
                  <span className="font-mono text-[10px] text-[#797876] w-12 text-right">{(morphT * 100).toFixed(0)}%</span>
                </div>
                <div className="flex items-center justify-between border-t border-[#222] pt-2">
                  <label className="font-mono text-[9px] tracking-forensic text-[#e2e2e8] flex items-center gap-2 cursor-pointer uppercase">
                    <input type="checkbox" checked={showVectors} onChange={e => setShowVectors(e.target.checked)} className="accent-[#5591c7]" />
                    3D Vector Fields
                  </label>
                  <span className="text-[8px] text-[#797876]">Displays direction & magnitude of 35k vertices</span>
                </div>
              </div>
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
              <div className="mt-2 pt-2 border-t border-border">
                <HeatmapLegend stops={stops ?? DEFAULT_HEATMAP_STOPS} />
              </div>
            </div>
            <div className="bg-surface border border-border p-3">
              <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-2">{t.perMetricDifference}</div>
              <MetricsTable metrics={result.metrics} />
            </div>
            <div className="bg-surface border border-border p-3">
              <ZoneBreakdown zones={result.zones} />
            </div>
            <div className="bg-surface border border-border p-3">
              <AlignmentDiagnostics diagnostics={result.diagnostics} />
            </div>
            <div className="bg-surface border border-border p-3">
              <NoiseCalibrationPanel photoA={photoAId} photoB={photoBId} />
            </div>
            <div className="bg-surface-2 border border-border p-2 font-mono text-[9px] text-text-faint">
              not_a_verdict: {String(result.not_a_verdict)}
              {fullMeshResult && <div className="mt-1">{fullMeshResult.note}</div>}
            </div>
            {(calibrationA || calibrationB) && (
              <div className="bg-surface border border-border p-3">
                <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-2">{t.calibrationMatchTitle}</div>
                {[["A", calibrationA], ["B", calibrationB]].map(([label, match]) => (
                  match && (match as CalibrationMatch).candidates.length > 0 ? (
                    <div key={label as string} className="font-mono text-[10px] mb-2">
                      <div className="text-text-muted">{t.calibrationMatchFor} {label as string}:</div>
                      {(match as CalibrationMatch).candidates.slice(0, 2).map(c => (
                        <div key={c.record_id} className="flex justify-between pl-2">
                          <span>{c.dataset_id}/{c.record_id}</span>
                          <span className="text-text-faint">Δ{c.angle_distance.toFixed(2)}°</span>
                        </div>
                      ))}
                    </div>
                  ) : null
                ))}
              </div>
            )}
          </aside>
        </div>
      )}

      {/* Полные метрики Stage 2 по категориям A–G. Размещены сразу под
          сравнением и ВЫШЕ тепловой карты: поправка на множественные
          сравнения и корроборация по ракурсам должны прочитываться раньше,
          чем величина расхождения, иначе вывод делается по сырому числу. */}
      {photoAId && photoBId && (
        <div className="mt-4 bg-surface border border-border p-4">
          <PairKeysPanel photoA={photoAId} photoB={photoBId} />
        </div>
      )}

      {result && result.status === "measured" && result.heatmap_points.length > 0 && (
        <div className="mt-4 bg-surface border border-border p-4">
          <ErrorBoundary label="HeatmapWorkbench">
            <HeatmapWorkbench result={result} fullMeshResult={fullMeshResult} />
          </ErrorBoundary>
        </div>
      )}

      {result && result.status === "measured" && result.heatmap_points.length > 0 && (
        <div className="mt-4 bg-surface border border-border p-4">
          {thresholdSaveFailed && (
            <div role="status" className="mb-2 bg-warning/10 border border-warning/40 px-2 py-1 font-mono text-[9px] text-warning">
              {t.thresholdSaveFailed}
            </div>
          )}
          <ErrorBoundary label="LandmarkPanel">
          <LandmarkPanel
            result={result}
            thresholds={settings?.landmark_shift ?? DEFAULT_SHIFT_THRESHOLDS}
            onThresholdsChange={handleThresholdsChange}
          />
          </ErrorBoundary>
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
