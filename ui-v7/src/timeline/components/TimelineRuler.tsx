import type { Viewport } from '../../types/timeline';
import { timeToRatio, ticksFor } from '../viewport';

/**
 * Timeline ruler component.
 * Displays time axis with adaptive tick marks.
 */

interface TimelineRulerProps {
  viewport: Viewport;
}

export function TimelineRuler({ viewport }: TimelineRulerProps) {
  const ticks = ticksFor(viewport);

  return (
    <div className="timeline-ruler">
      <div className="timeline-ruler-track">
        {ticks.map((tick) => {
          const ratio = timeToRatio(viewport, tick.time);
          const left = ratio * 100;
          return (
            <div
              key={tick.time}
              className={`timeline-ruler-tick ${tick.major ? 'major' : ''}`}
              style={{ left: `${left}%` }}
            >
              <span className="timeline-ruler-label">{tick.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
