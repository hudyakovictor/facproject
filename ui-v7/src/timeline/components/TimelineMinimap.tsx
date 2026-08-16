import { useMemo } from 'react';
import type { TimelinePhoto, Viewport, TimeBounds } from '../../types/timeline';

/**
 * Timeline minimap component.
 * Shows overview of photo density and current viewport position.
 */

interface TimelineMinimapProps {
  photos: TimelinePhoto[];
  viewport: Viewport;
  bounds: TimeBounds;
  width: number;
  onBrush: (start: number, end: number) => void;
}

const BUCKETS = 200;

export function TimelineMinimap({
  photos,
  viewport,
  bounds,
  width,
  onBrush,
}: TimelineMinimapProps) {
  const density = useMemo(() => {
    const totals = new Array<number>(BUCKETS).fill(0);
    const flagged = new Array<number>(BUCKETS).fill(0);
    const span = Math.max(bounds.max - bounds.min, 1);

    for (const photo of photos) {
      const time = photo.t;
      if (time == null) continue;
      const index = Math.min(BUCKETS - 1, Math.floor(((time - bounds.min) / span) * BUCKETS));
      totals[index]! += 1;
      if (photo.flags.length > 0) flagged[index]! += 1;
    }

    const max = Math.max(...totals, 1);
    return totals.map((total, index) => ({
      index,
      total,
      findings: flagged[index]!,
      height: total === 0 ? 0 : Math.max(8, (total / max) * 100),
    })).filter((cell) => cell.total > 0);
  }, [photos, bounds]);

  const viewportLeft = ((viewport.start - bounds.min) / Math.max(bounds.max - bounds.min, 1)) * 100;
  const viewportWidth = ((viewport.end - viewport.start) / Math.max(bounds.max - bounds.min, 1)) * 100;

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const startRatio = (e.clientX - rect.left) / rect.width;
    const startTime = bounds.min + startRatio * (bounds.max - bounds.min);

    const handleMove = (moveEvent: MouseEvent) => {
      const moveRatio = (moveEvent.clientX - rect.left) / rect.width;
      const endTime = bounds.min + moveRatio * (bounds.max - bounds.min);
      const start = Math.min(startTime, endTime);
      const end = Math.max(startTime, endTime);
      if (end - start > 86_400_000) {
        onBrush(start, end);
      }
    };

    const handleUp = () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };

    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
  };

  return (
    <div className="timeline-minimap" style={{ width }} onMouseDown={handleMouseDown}>
      {density.map((cell) => (
        <div
          key={cell.index}
          className="minimap-bar"
          style={{
            left: `${((cell.index + 0.5) / BUCKETS) * 100}%`,
            height: `${cell.height}%`,
            backgroundColor: cell.findings > 0 ? 'var(--color-synthetic)' : 'var(--border-strong)',
          }}
          title={`${cell.total} кадров${cell.findings > 0 ? `, ${cell.findings} аномалий` : ''}`}
        />
      ))}
      <div
        className="minimap-viewport"
        style={{
          left: `${viewportLeft}%`,
          width: `${viewportWidth}%`,
        }}
      />
    </div>
  );
}
