import { useEffect, useMemo, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import MeshViewer from "./LazyMeshViewer";
import GradientEditor from "./GradientEditor";
import { HeatmapLegend } from "./ComparePanels";
import {
  DEFAULT_GRADIENT, evaluateGradient, sanitizeGradient, toHex,
  type GradientModel,
} from "../gradient";
import { DEFAULT_SHIFT_THRESHOLDS, classifyShift, type ShiftThresholds } from "../landmarks";
import {
  fetchSettings, saveSettings,
  type AppSettings, type CompareResult, type FullMeshCompareResult,
} from "../api";

interface Props {
  result: CompareResult;
  fullMeshResult?: FullMeshCompareResult | null;
}

/** Пересчёт формата настроек ↔ модели градиента. */
function gradientFromSettings(settings: AppSettings | null): GradientModel {
  const raw = (settings as unknown as { gradient?: unknown })?.gradient as
    | { max_reference?: number; stops?: { position: number; color: string; sharpness: number; label?: string }[] }
    | undefined;
  if (!raw?.stops?.length) return DEFAULT_GRADIENT;
  return sanitizeGradient({
    maxReference: raw.max_reference ?? DEFAULT_GRADIENT.maxReference,
    stops: raw.stops.map(s => ({
      position: s.position, color: s.color, sharpness: s.sharpness, label: s.label,
    })),
  });
}

function gradientToSettings(model: GradientModel) {
  return {
    max_reference: model.maxReference,
    stops: model.stops.map(s => ({
      position: s.position, color: s.color, sharpness: s.sharpness,
      ...(s.label ? { label: s.label } : {}),
    })),
  };
}

/** 🔥 Рабочее место тепловой карты: карта различий A↔B и редактор градиента
 * рядом, так что эффект настройки виден немедленно.
 *
 * Тепловая карта и редактор используют ОДНУ функцию `evaluateGradient`,
 * поэтому превью в редакторе буквально совпадает с раскраской меша — нет
 * расхождения между «как настроено» и «как выглядит».
 */
export default function HeatmapWorkbench({ result, fullMeshResult }: Props) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [gradient, setGradient] = useState<GradientModel>(DEFAULT_GRADIENT);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error">("idle");
  const [showEditor, setShowEditor] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then(value => {
        if (cancelled) return;
        setSettings(value);
        setGradient(gradientFromSettings(value));
      })
      .catch(() => undefined);   // редактор работает и на умолчаниях
    return () => { cancelled = true; };
  }, []);

  const thresholds: ShiftThresholds = settings?.landmark_shift ?? DEFAULT_SHIFT_THRESHOLDS;

  const persist = (next: GradientModel) => {
    setGradient(next);
    if (!settings) return;
    const payload = { ...settings, gradient: gradientToSettings(next) } as AppSettings;
    saveSettings(payload)
      .then(() => setSaveState("saved"))
      .catch(() => setSaveState("error"));
  };

  const points = useMemo(
    () => result.heatmap_points.filter(
      p => p.visible !== false && p.x !== null && p.residual !== null),
    [result.heatmap_points]);

  /** Распределение точек по цветовым диапазонам: показывает, сколько кадров
   * попадает в каждую зону градиента при текущих настройках. */
  const histogram = useMemo(() => {
    const buckets = new Array(24).fill(0);
    const max = Math.max(1e-9, gradient.maxReference);
    for (const p of points) {
      const idx = Math.min(buckets.length - 1,
        Math.floor(((p.residual as number) / max) * buckets.length));
      buckets[Math.max(0, idx)] += 1;
    }
    const peak = Math.max(1, ...buckets);
    return buckets.map((count, i) => ({
      count, height: count / peak,
      color: toHex(evaluateGradient(gradient, (i + 0.5) / buckets.length)),
    }));
  }, [points, gradient]);

  const classCounts = useMemo(() => {
    const counts = { within: 0, suspect: 0, anomalous: 0 };
    for (const p of points) {
      const cls = classifyShift(p.residual, thresholds);
      if (cls === "within" || cls === "suspect" || cls === "anomalous") counts[cls] += 1;
    }
    return counts;
  }, [points, thresholds]);

  return (
    <section className="space-y-3">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-sm tracking-forensic">{t.heatmapWorkbenchTitle}</h2>
          <p className="font-mono text-[9px] text-text-faint mt-0.5 leading-snug">
            {t.heatmapWorkbenchSub}
          </p>
        </div>
        <button onClick={() => setShowEditor(v => !v)} aria-pressed={showEditor} aria-label={t.a11yToggleEditor}
          className={`px-2 py-1 font-mono text-[9px] tracking-forensic border flex-shrink-0 ${showEditor ? "bg-info/25 border-info text-text" : "border-border text-text-muted hover:text-text"}`}>
          <Icon name="sliders" size={10} className="inline mr-1" />
          {t.heatmapToggleEditor}
        </button>
      </header>

      <div className={showEditor ? "grid grid-cols-[1fr_340px] gap-3" : ""}>
        {/* Тепловая карта различий A↔B */}
        <div className="space-y-2">
          <div className="bg-surface border border-border" style={{ height: 420 }}>
            {fullMeshResult ? (
              <MeshViewer
                fullMesh={{
                  vertices: fullMeshResult.vertices_a,
                  verticesTarget: fullMeshResult.vertices_b_aligned,
                  triangles: fullMeshResult.triangles,
                  vertexValues: fullMeshResult.residuals,
                }}
                gradient={gradient}
                wireframe
              />
            ) : points.length ? (
              <MeshViewer
                heatmapPoints={points.map(p => ({
                  x: p.x as number, y: p.y as number, z: p.z as number,
                  value: p.residual as number,
                }))}
                gradient={gradient}
                wireframe
              />
            ) : (
              <div className="h-full flex items-center justify-center font-mono text-[10px] text-text-muted">
                {t.lmNoData}
              </div>
            )}
          </div>

          {/* Гистограмма распределения различий, окрашенная тем же градиентом */}
          <div className="bg-surface border border-border p-2">
            <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-1">
              {t.heatmapHistogram} · {points.length}
            </div>
            <div className="flex items-end gap-px h-12">
              {histogram.map((bar, i) => (
                <div key={i} className="flex-1" title={`${bar.count}`}
                  style={{
                    height: `${Math.max(2, bar.height * 100)}%`,
                    background: bar.color,
                    opacity: bar.count ? 1 : 0.25,
                  }} />
              ))}
            </div>
            <div className="flex justify-between font-mono text-[8px] text-text-faint mt-0.5">
              <span>0.000</span>
              <span>{gradient.maxReference.toFixed(3)}</span>
            </div>
            <div className="flex gap-3 font-mono text-[9px] mt-1.5 pt-1.5 border-t border-border">
              <span style={{ color: "#6daa45" }}>{t.shiftWithin}: {classCounts.within}</span>
              <span style={{ color: "#e8af34" }}>{t.shiftSuspect}: {classCounts.suspect}</span>
              <span style={{ color: "#ff3b30" }}>{t.shiftAnomalous}: {classCounts.anomalous}</span>
            </div>
          </div>

          <div className="bg-surface border border-border p-2">
            <HeatmapLegend stops={{
              blueCyan: 0.25, cyanGreen: 0.5, greenRed: 0.75,
              saturatedRed: 1, maxReference: gradient.maxReference,
            }} />
          </div>
        </div>

        {/* Редактор градиента */}
        {showEditor && (
          <aside className="bg-surface border border-border p-3 overflow-auto max-h-[720px]" data-scroll>
            <GradientEditor
              model={gradient}
              onChange={persist}
              marks={[
                { value: thresholds.tolerance, label: `${t.gradThresholdMark}: ${t.shiftWithin}`, color: "#6daa45" },
                { value: thresholds.suspect, label: `${t.gradThresholdMark}: ${t.shiftAnomalous}`, color: "#ff3b30" },
              ]}
            />
            {saveState === "saved" && (
              <div role="status" className="mt-2 font-mono text-[9px] text-nominal">{t.gradSaved}</div>
            )}
            {saveState === "error" && (
              <div role="alert" className="mt-2 font-mono text-[9px] text-warning">{t.gradSaveFailed}</div>
            )}
          </aside>
        )}
      </div>
    </section>
  );
}
