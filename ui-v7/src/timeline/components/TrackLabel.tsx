import type { TrackDescriptor } from '../../types/timeline';

/**
 * Track label component.
 * Displays the label for a track on the left side.
 */

interface TrackLabelProps {
  track: TrackDescriptor;
  height: number;
  onMove?: (sourceId: string, targetId: string) => void;
}

const ICONS: Partial<Record<TrackDescriptor['kind'], string>> = {
  quality: '◉',
  texture: '◌',
  geometry: '◇',
  pca: '∿',
  calibration: '⌁',
  pose: '◐',
  chronology: '↗',
  ldm_difference: '△',
  anomaly: '⚑',
  photo: '▧',
};

export function TrackLabel({ track, height, onMove }: TrackLabelProps) {
  return (
    <div
      className="track-label"
      style={{ height }}
      draggable={Boolean(onMove)}
      title={`${track.label}${track.unit ? ` · ${track.unit}` : ''}`}
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', track.id);
      }}
      onDragOver={(event) => {
        if (onMove) event.preventDefault();
      }}
      onDrop={(event) => {
        event.preventDefault();
        const sourceId = event.dataTransfer.getData('text/plain');
        if (sourceId && sourceId !== track.id) onMove?.(sourceId, track.id);
      }}
    >
      <div className="track-label-content">
        <span
          className="track-label-swatch"
          style={{ backgroundColor: track.color }}
        />
        <span className="track-label-icon" aria-hidden="true">{ICONS[track.kind] ?? '◌'}</span>
        <span className="track-label-text">{track.label}</span>
        {track.unit && (
          <span className="track-label-unit">{track.unit}</span>
        )}
      </div>
    </div>
  );
}
