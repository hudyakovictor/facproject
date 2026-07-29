import { useEffect, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import { fetchCalibrationHealth, type CalibrationHealth } from "../api";

const CONFIDENCE_COLOR: Record<string, string> = {
  invalid: "#ff3b30", low: "#e8af34", medium: "#5591c7", high: "#6daa45",
};
const CONFIDENCE_LABEL_KEY: Record<string, "calibrationConfidenceInvalid" | "calibrationConfidenceLow" | "calibrationConfidenceMedium" | "calibrationConfidenceHigh"> = {
  invalid: "calibrationConfidenceInvalid", low: "calibrationConfidenceLow",
  medium: "calibrationConfidenceMedium", high: "calibrationConfidenceHigh",
};

/** Раздел "Калибровка": здоровье реальной калибровочной базы
 * (`/api/v1/calibration/health` → `calibration_dataset/all_calibration_index.csv`,
 * 7 персон × 9 ракурсов, известная идентичность). Не мок — если API недоступен
 * или калибровочный контур отсутствует, страница явно об этом сообщает. */
export default function CalibrationView() {
  const [health, setHealth] = useState<CalibrationHealth | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    fetchCalibrationHealth()
      .then(h => { setHealth(h); setStatus("ready"); })
      .catch(err => { setStatus("error"); setErrorMessage(err instanceof Error ? err.message : String(err)); });
  }, []);

  return (
    <section className="h-full overflow-auto bg-bg p-5 scanlines" data-scroll>
      <header className="mb-5">
        <h1 className="font-display text-xl tracking-forensic">{t.calibrationTitle}</h1>
        <p className="font-mono text-[10px] text-text-muted mt-1">{t.calibrationSub}</p>
      </header>

      {status === "loading" && <div className="font-mono text-[10px] text-text-muted">{t.loading}…</div>}
      {status === "error" && (
        <div className="bg-warning/15 border border-warning p-3 font-mono text-[10px] text-warning flex items-start gap-2">
          <Icon name="alert-triangle" size={14} color="#e8af34" className="mt-0.5 flex-shrink-0" />
          <div>{t.calibrationUnavailable}<br /><span className="text-text-faint">{errorMessage}</span></div>
        </div>
      )}

      {health && (
        <>
          <div className="grid grid-cols-4 gap-3 mb-5">
            <article className="bg-surface border border-border p-3">
              <div className="font-mono text-[9px] tracking-forensic text-text-muted">TOTAL RECORDS</div>
              <div className="font-display text-2xl mt-2" style={{ color: "#5591c7" }}>{health.total_records}</div>
            </article>
            <article className="bg-surface border border-border p-3">
              <div className="font-mono text-[9px] tracking-forensic text-text-muted">PERSONS</div>
              <div className="font-display text-2xl mt-2" style={{ color: "#5591c7" }}>{health.total_persons}</div>
            </article>
            {(["high", "medium"] as const).map(level => (
              <article key={level} className="bg-surface border border-border p-3">
                <div className="font-mono text-[9px] tracking-forensic text-text-muted">{t[CONFIDENCE_LABEL_KEY[level]]}</div>
                <div className="font-display text-2xl mt-2" style={{ color: CONFIDENCE_COLOR[level] }}>{health.confidence_counts[level] ?? 0}</div>
              </article>
            ))}
          </div>

          <div className="mb-3 font-mono text-[10px] text-text-muted tracking-forensic">{t.calibrationBuckets}</div>
          <div className="overflow-auto border border-border mb-6">
            <table className="w-full min-w-[720px] border-collapse font-mono text-[10px]">
              <thead>
                <tr>
                  <th className="bg-surface p-2 text-left">POSE BIN</th>
                  <th className="bg-surface p-2 text-right">FRAMES</th>
                  <th className="bg-surface p-2 text-right">PERSONS</th>
                  <th className="bg-surface p-2 text-center">CONFIDENCE</th>
                  <th className="bg-surface p-2 text-center">RUNTIME</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(health.buckets).map(bucket => (
                  <tr key={bucket.pose_bin} className="border-t border-border">
                    <td className="p-2">{bucket.pose_bin}</td>
                    <td className="p-2 text-right">{bucket.frame_count}</td>
                    <td className="p-2 text-right">{bucket.person_count}</td>
                    <td className="p-2 text-center">
                      <span className="px-2 py-0.5" style={{ color: CONFIDENCE_COLOR[bucket.confidence], border: `1px solid ${CONFIDENCE_COLOR[bucket.confidence]}55` }}>
                        {t[CONFIDENCE_LABEL_KEY[bucket.confidence]]}
                      </span>
                    </td>
                    <td className="p-2 text-center text-text-faint">
                      {bucket.runtime_usable ? t.calibrationRuntimeUsable : t.calibrationRuntimeBlocked}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mb-3 font-mono text-[10px] text-text-muted tracking-forensic">{t.calibrationRecommendations}</div>
          {health.recommendations.length === 0 ? (
            <div className="bg-surface border border-border p-3 font-mono text-[10px] text-text-muted">
              {t.calibrationNoRecommendations}
            </div>
          ) : (
            <div className="space-y-2">
              {health.recommendations.map(rec => (
                <div key={rec.pose_bin} className="bg-surface border border-warning/40 p-3 font-mono text-[10px] flex items-start gap-2">
                  <Icon name="alert-triangle" size={12} color="#e8af34" className="mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="text-text">{rec.pose_bin} · {rec.reason}</div>
                    <div className="text-text-muted mt-0.5">{rec.action}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-6 font-mono text-[9px] text-text-faint">{t.source}: {health.source}</div>
        </>
      )}
    </section>
  );
}
