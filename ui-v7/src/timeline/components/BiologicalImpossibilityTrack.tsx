import type { TimelinePhoto, Viewport } from '../../types/timeline';
import { timeToRatio } from '../viewport';

/**
 * Biological Impossibility Track.
 * Highlights photos with biologically impossible changes.
 * 
 * Criteria:
 * - Visual age decreases over time (rejuvenation without explanation)
 * - Bone structure changes dramatically in short period
 * - Symmetry inversion between consecutive photos
 */

interface BiologicalImpossibilityTrackProps {
  photos: TimelinePhoto[];
  viewport: Viewport;
  width: number;
  height: number;
  onPhotoClick: (photo: TimelinePhoto) => void;
}

interface ImpossibilityEvent {
  photo: TimelinePhoto;
  type: 'age_regression' | 'bone_change' | 'symmetry_inversion';
  severity: 'high' | 'medium' | 'low';
  description: string;
}

const TYPE_ICONS: Record<string, string> = {
  age_regression: '↺',
  bone_change: '◇',
  symmetry_inversion: '⇄',
};

function detectImpossibilities(photos: TimelinePhoto[]): ImpossibilityEvent[] {
  const events: ImpossibilityEvent[] = [];
  const sorted = [...photos].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));

  for (let i = 1; i < sorted.length; i++) {
    const current = sorted[i]!;
    const previous = sorted[i - 1]!;
    
    const timeDiff = (current.t ?? 0) - (previous.t ?? 0);
    const daysDiff = timeDiff / (1000 * 60 * 60 * 24);
    
    if (daysDiff < 30 || daysDiff > 365 * 2) continue; // Skip too close or too far
    if (current.bucket !== previous.bucket) continue; // Same pose only

    // Check age regression
    if (current.visualAge != null && previous.visualAge != null) {
      const ageDiff = current.visualAge - previous.visualAge;
      const expectedAging = daysDiff / 365.25;
      
      if (ageDiff < -3 && expectedAging > 0.5) {
        // Person appears younger despite significant time passing
        events.push({
          photo: current,
          type: 'age_regression',
          severity: ageDiff < -5 ? 'high' : 'medium',
          description: `Возраст уменьшился на ${Math.abs(ageDiff).toFixed(0)} лет за ${Math.round(daysDiff)} дней`,
        });
      }
    }

    // Check bone score dramatic change
    if (current.boneScore != null && previous.boneScore != null) {
      const boneDiff = Math.abs(current.boneScore - previous.boneScore);
      if (boneDiff > 0.4 && daysDiff < 180) {
        events.push({
          photo: current,
          type: 'bone_change',
          severity: boneDiff > 0.6 ? 'high' : 'medium',
          description: `Изменение костной основы: ${(boneDiff * 100).toFixed(0)}% за ${Math.round(daysDiff)} дней`,
        });
      }
    }

    // Check symmetry inversion
    if (current.symmetry != null && previous.symmetry != null) {
      const symDiff = Math.abs(current.symmetry - previous.symmetry);
      if (symDiff > 0.5) {
        events.push({
          photo: current,
          type: 'symmetry_inversion',
          severity: symDiff > 0.7 ? 'high' : 'medium',
          description: `Инверсия симметрии: ${(symDiff * 100).toFixed(0)}%`,
        });
      }
    }
  }

  return events;
}

export function BiologicalImpossibilityTrack({
  photos,
  viewport,
  height,
  onPhotoClick,
}: BiologicalImpossibilityTrackProps) {
  const events = detectImpossibilities(photos);

  return (
    <div className="biological-track" style={{ height }}>
      <div className="biological-track-header">
        <span className="biological-track-title">БИОЛОГИЧЕСКАЯ НЕВОЗМОЖНОСТЬ</span>
        <span className="biological-track-count">{events.length} обнаружено</span>
      </div>
      <div className="biological-track-events">
        {events.map((event, index) => {
          const time = event.photo.t ?? 0;
          const ratio = timeToRatio(viewport, time);
          const left = ratio * 100;

          return (
            <button
              key={`${event.photo.id}-${index}`}
              className={`bio-event bio-severity-${event.severity}`}
              style={{ left: `${left}%` }}
              onClick={() => onPhotoClick(event.photo)}
              title={event.description}
            >
              <span className="bio-event-icon">{TYPE_ICONS[event.type]}</span>
            </button>
          );
        })}
      </div>
      <div className="biological-track-legend">
        <span className="bio-legend-item">
          <span className="bio-legend-icon">↺</span> Регресс возраста
        </span>
        <span className="bio-legend-item">
          <span className="bio-legend-icon">◇</span> Изменение костей
        </span>
        <span className="bio-legend-item">
          <span className="bio-legend-icon">⇄</span> Инверсия симметрии
        </span>
      </div>
    </div>
  );
}
