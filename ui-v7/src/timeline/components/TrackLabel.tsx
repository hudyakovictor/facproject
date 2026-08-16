import type { TrackDescriptor } from '../../types/timeline';

/**
 * Track label component.
 * Displays the label for a track on the left side.
 */

interface TrackLabelProps {
  track: TrackDescriptor;
  height: number;
}

export function TrackLabel({ track, height }: TrackLabelProps) {
  return (
    <div className="track-label" style={{ height }}>
      <div className="track-label-content">
        <span
          className="track-label-swatch"
          style={{ backgroundColor: track.color }}
        />
        <span className="track-label-text">{track.label}</span>
        {track.unit && (
          <span className="track-label-unit">{track.unit}</span>
        )}
      </div>
    </div>
  );
}
