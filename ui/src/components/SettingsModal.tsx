import { useEffect, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import { fetchSettings, saveSettings, resetSettings, type AppSettings } from "../api";
import { DEFAULT_HEATMAP_STOPS, heatColor } from "./MeshViewer";

interface Props {
  onClose: () => void;
  onApplied: (settings: AppSettings) => void;
}

/** Попап настроек (большой, не покидая текущую страницу — как требовалось в ТЗ):
 * пороги перехода тепловой карты, пороги фильтров/QC, уровень детализации. */
export default function SettingsModal({ onClose, onApplied }: Props) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "saving" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    fetchSettings()
      .then(s => { setSettings(s); setStatus("ready"); })
      .catch(err => { setStatus("error"); setErrorMessage(err instanceof Error ? err.message : String(err)); });
  }, []);

  const update = (path: (s: AppSettings) => void) => {
    setSettings(prev => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      path(next);
      return next;
    });
  };

  const handleSave = async () => {
    if (!settings) return;
    setStatus("saving");
    try {
      const saved = await saveSettings(settings);
      setSettings(saved);
      onApplied(saved);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  const handleReset = async () => {
    setStatus("saving");
    try {
      const fresh = await resetSettings();
      setSettings(fresh);
      onApplied(fresh);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  const stops = settings ? {
    blueCyan: settings.heatmap.stop_blue_cyan, cyanGreen: settings.heatmap.stop_cyan_green,
    greenRed: settings.heatmap.stop_green_red, saturatedRed: settings.heatmap.stop_saturated_red,
    maxReference: settings.heatmap.max_residual_reference,
  } : DEFAULT_HEATMAP_STOPS;

  return (
    <div data-no-pan className="fixed inset-0 z-[110] bg-black/70 flex items-center justify-center p-6">
      <div className="w-full max-w-3xl max-h-[85vh] overflow-y-auto bg-surface border border-border-strong shadow-2xl" data-scroll>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-2 sticky top-0 z-10">
          <div className="flex items-center gap-2">
            <Icon name="sliders" size={16} color="#5591c7" />
            <div className="font-display tracking-forensic text-sm">{t.settingsTitle}</div>
          </div>
          <button onClick={onClose} aria-label="Закрыть" className="w-7 h-7 flex items-center justify-center border border-border hover:bg-critical/30">
            <Icon name="x" size={14} />
          </button>
        </div>

        <div className="p-4 space-y-5">
          {status === "loading" && <div className="font-mono text-[10px] text-text-muted">{t.loading}…</div>}
          {status === "error" && (
            <div className="bg-critical/15 border border-critical p-2 font-mono text-[10px] text-critical">
              {errorMessage}
            </div>
          )}

          {settings && (
            <>
              <section>
                <div className="font-display text-xs tracking-forensic mb-2">{t.heatmapSectionTitle}</div>
                <div className="font-mono text-[10px] text-text-muted mb-3">{t.heatmapSectionHint}</div>

                <div className="h-6 w-full mb-3 border border-border" style={{
                  background: `linear-gradient(to right, ${Array.from({ length: 41 }, (_, i) => `#${heatColor(i / 40, stops).getHexString()} ${(i / 40) * 100}%`).join(", ")})`,
                }} />

                {([
                  ["stop_blue_cyan", t.stopBlueCyan],
                  ["stop_cyan_green", t.stopCyanGreen],
                  ["stop_green_red", t.stopGreenRed],
                  ["stop_saturated_red", t.stopSaturatedRed],
                ] as const).map(([key, label]) => (
                  <div key={key} className="flex items-center gap-3 mb-2">
                    <span className="font-mono text-[10px] text-text-muted w-40">{label}</span>
                    <input type="range" min={0} max={1} step={0.01} value={settings.heatmap[key]}
                      onChange={e => update(s => { s.heatmap[key] = +e.target.value; })}
                      className="flex-1" />
                    <span className="font-mono text-[10px] w-12 text-right">{(settings.heatmap[key] * 100).toFixed(0)}%</span>
                  </div>
                ))}
                <div className="flex items-center gap-3 mt-3">
                  <span className="font-mono text-[10px] text-text-muted w-40">{t.maxResidualReference}</span>
                  <input type="range" min={0.01} max={0.5} step={0.005} value={settings.heatmap.max_residual_reference}
                    onChange={e => update(s => { s.heatmap.max_residual_reference = +e.target.value; })}
                    className="flex-1" />
                  <span className="font-mono text-[10px] w-16 text-right">{settings.heatmap.max_residual_reference.toFixed(3)}</span>
                </div>
              </section>

              <section>
                <div className="font-display text-xs tracking-forensic mb-2">{t.thresholdsSectionTitle}</div>
                {([
                  ["confidence_min", t.thresholdConfidenceMin, 0, 1, 0.01],
                  ["quality_min", t.thresholdQualityMin, 0, 1, 0.01],
                  ["geometry_zone_delta_limit", t.thresholdGeometryLimit, 0, 0.2, 0.001],
                  ["texture_zone_delta_limit", t.thresholdTextureLimit, 0, 0.3, 0.001],
                  ["expression_smile", t.thresholdSmile, 0, 2, 0.01],
                  ["expression_jaw_open", t.thresholdJawOpen, 0, 1, 0.01],
                ] as const).map(([key, label, min, max, step]) => (
                  <div key={key} className="flex items-center gap-3 mb-2">
                    <span className="font-mono text-[10px] text-text-muted w-56">{label}</span>
                    <input type="range" min={min} max={max} step={step} value={settings.thresholds[key]}
                      onChange={e => update(s => { s.thresholds[key] = +e.target.value; })}
                      className="flex-1" />
                    <span className="font-mono text-[10px] w-14 text-right">{settings.thresholds[key].toFixed(3)}</span>
                  </div>
                ))}
              </section>

              <section>
                <div className="font-display text-xs tracking-forensic mb-2">{t.detailLevelTitle}</div>
                <div className="flex gap-2">
                  {(["simple", "standard", "expert"] as const).map(level => (
                    <button key={level} onClick={() => update(s => { s.detail_level = level; })}
                      className={`px-3 py-1.5 font-mono text-[10px] tracking-forensic border ${settings.detail_level === level ? "bg-info/20 border-info" : "border-border text-text-muted"}`}>
                      {t.detailLevelLabel[level]}
                    </button>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>

        <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-surface-2 sticky bottom-0">
          <button onClick={handleReset} disabled={status === "saving"}
            className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-border hover:bg-critical/20 disabled:opacity-50">
            {t.resetDefaults}
          </button>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-border text-text-muted">
              {t.cancel}
            </button>
            <button onClick={handleSave} disabled={status === "saving" || !settings}
              className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-info/50 bg-info/20 hover:bg-info/40 disabled:opacity-50">
              {status === "saving" ? `${t.saving}…` : t.applyAndSave}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
