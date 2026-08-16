import type { AnomalyEvent, AnomalyKind, Viewport } from '../../types/timeline';
import { timeToRatio } from '../viewport';

/**
 * Anomaly track component.
 * Displays detected anomalies as markers on the timeline.
 */

interface AnomalyTrackProps {
  anomalies: AnomalyEvent[];
  viewport: Viewport;
  height: number;
  activeKinds: Set<AnomalyKind>;
  onAnomalyClick: (anomaly: AnomalyEvent) => void;
}

const ANOMALY_ICONS: Record<AnomalyKind, string> = {
  persistent_change: '◆',
  return: '↩',
  change_point: '╳',
  rapid_rate: '↗',
  same_day: '▦',
  provenance: '⌁',
  review: '!',
};

const ANOMALY_COLORS: Record<AnomalyKind, string> = {
  persistent_change: 'var(--color-synthetic)',
  return: 'var(--color-info)',
  change_point: 'var(--color-warning)',
  rapid_rate: 'var(--color-warning)',
  same_day: 'var(--metric-texture)',
  provenance: 'var(--metric-texture)',
  review: 'var(--color-synthetic)',
};

export function AnomalyTrack({
  anomalies,
  viewport,
  height,
  activeKinds,
  onAnomalyClick,
}: AnomalyTrackProps) {
  const filteredAnomalies = anomalies.filter(
    (a) => a.time != null && activeKinds.has(a.kind)
  );

  return (
    <div className="anomaly-track" style={{ height }}>
      {filteredAnomalies.map((anomaly) => {
        const time = anomaly.time ?? 0;
        const ratio = timeToRatio(viewport, time);
        const left = ratio * 100;

        return (
          <button
            key={anomaly.id}
            className={`anomaly-marker anomaly-${anomaly.kind}`}
            style={{
              left: `${left}%`,
              '--anomaly-color': ANOMALY_COLORS[anomaly.kind],
            } as React.CSSProperties}
            onClick={() => onAnomalyClick(anomaly)}
            title={anomaly.label}
          >
            <span className="anomaly-icon">{ANOMALY_ICONS[anomaly.kind]}</span>
          </button>
        );
      })}
    </div>
  );
}
