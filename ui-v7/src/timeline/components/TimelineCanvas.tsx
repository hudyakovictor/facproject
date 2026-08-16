import { useRef, useEffect, useCallback, useState } from 'react';
import type { TimelinePhoto, Viewport, TrackDescriptor } from '../../types/timeline';
import { photosInColumns, timeOf, timeToX } from '../viewport';
import { Tooltip } from './Tooltip';
import { useTrackData } from '../useTrackData';

/**
 * Canvas-based track renderer for the timeline.
 * Renders metric data as line charts on HTML5 Canvas.
 */

interface TimelineCanvasProps {
  track: TrackDescriptor;
  photos: TimelinePhoto[];
  viewport: Viewport;
  width: number;
  height: number;
  hoverTime: number | null;
  selectedPhotoId: string | null;
  onPhotoClick: (photo: TimelinePhoto, asPair: boolean) => void;
}

function resolveColor(token: string): string {
  const match = /^var\((--[^),]+)\)$/.exec(token.trim());
  if (match) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(match[1]!).trim();
    return value || '#69cce0';
  }
  return token;
}

export function TimelineCanvas({
  track,
  photos,
  viewport,
  width,
  height,
  hoverTime,
  selectedPhotoId,
  onPhotoClick,
}: TimelineCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hitPointsRef = useRef<Array<{ x: number; photo: TimelinePhoto }>>([]);
  const [tooltip, setTooltip] = useState<{ photo: TimelinePhoto; x: number; y: number } | null>(null);
  
  // Use optimized track data computation
  const trackData = useTrackData(track, photos, viewport, width, height);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || width <= 0) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const color = resolveColor(trackData.descriptor.color);
    const padding = 8;
    const usableHeight = height - padding * 2;
    const [lo, hi] = trackData.domain;

    // Draw baseline
    ctx.strokeStyle = 'var(--border-subtle)';
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(0, padding + usableHeight / 2);
    ctx.lineTo(width, padding + usableHeight / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw min/max labels
    ctx.fillStyle = 'var(--text-muted)';
    ctx.font = '10px var(--font-mono)';
    ctx.textAlign = 'left';
    ctx.fillText(hi.toFixed(1), 4, padding + 10);
    ctx.fillText(((lo + hi) / 2).toFixed(1), 4, padding + usableHeight / 2 + 4);
    ctx.fillText(lo.toFixed(1), 4, height - padding);

    const points = trackData.points;

    const columns = photosInColumns(photos, viewport);
    ctx.strokeStyle = 'var(--border-subtle)';
    ctx.globalAlpha = 0.28;
    ctx.lineWidth = 1;
    for (let index = 0; index < columns.length; index += 1) {
      const x = timeToX(viewport, timeOf(columns[index]!) ?? viewport.start, width);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Draw line
    if (points.length > 1) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.globalAlpha = 0.7;
      ctx.beginPath();

      for (const [index, point] of points.entries()) {
        const y = Math.max(2, Math.min(height - 2, point.y));
        if (index === 0) ctx.moveTo(point.x, y);
        else ctx.lineTo(point.x, y);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Draw points
    for (const point of points) {
      const isSelected = point.photo.id === selectedPhotoId;
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(point.x, point.y, isSelected ? 4 : 2, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? color : 'var(--bg-canvas)';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = isSelected ? 2 : 1;
      ctx.stroke();
    }

    // Draw hover line
    if (hoverTime != null) {
      const hx = timeToX(viewport, hoverTime, width);
      if (hx >= 0 && hx <= width) {
        ctx.strokeStyle = 'var(--border-focus)';
        ctx.globalAlpha = 0.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(hx, 0);
        ctx.lineTo(hx, height);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
      }
    }

    hitPointsRef.current = points.map(p => ({ x: p.x, photo: p.photo }));
  }, [trackData, width, height, hoverTime, selectedPhotoId, viewport]);

  useEffect(() => {
    draw();
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver(() => {
      draw();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [draw]);

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;

    let nearest: { d: number; photo: TimelinePhoto } | null = null;
    for (const hit of hitPointsRef.current) {
      const d = Math.abs(hit.x - x);
      if (d > 12) continue;
      if (!nearest || d < nearest.d) nearest = { d, photo: hit.photo };
    }

    if (nearest) {
      onPhotoClick(nearest.photo, false);
    }
  };

  const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;

    let nearest: { d: number; photo: TimelinePhoto } | null = null;
    for (const hit of hitPointsRef.current) {
      const d = Math.abs(hit.x - x);
      if (d > 16) continue;
      if (!nearest || d < nearest.d) nearest = { d, photo: hit.photo };
    }

    if (nearest) {
      setTooltip({ photo: nearest.photo, x: event.clientX, y: event.clientY });
    } else {
      setTooltip(null);
    }
  };

  const handleMouseLeave = () => {
    setTooltip(null);
  };

  return (
    <div ref={containerRef} className="timeline-canvas-container" style={{ width: '100%', height }}>
      <canvas
        ref={canvasRef}
        className="timeline-canvas"
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{ display: 'block', cursor: 'pointer' }}
      />
      {tooltip && <Tooltip photo={tooltip.photo} x={tooltip.x} y={tooltip.y} />}
    </div>
  );
}
