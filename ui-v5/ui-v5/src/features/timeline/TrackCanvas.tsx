import { useEffect, useRef } from "react";
import type { ResearchPhoto } from "../../shared/researchApi";
import { resolveToken } from "../../shared/ui/tokenColors";
import { timeToX, type Viewport } from "./viewport";

/**
 * Дорожка метрик: линия соединяет только соседние реально измеренные значения.
 * Пропуски разрывают линию — отсутствующие значения никогда не интерполируются.
 */

export interface TrackSpec {
  key: string;
  label: string;
  range: string;
  color: string;
  value: (photo: ResearchPhoto) => number | null;
  normalize: (value: number) => number;
}

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

function cssColor(token: string): string {
  const match = /^var\((--[^),]+)\)$/.exec(token.trim());
  return match ? resolveToken(match[1], "#69cce0") : token;
}

export function TrackCanvas({
  track,
  photos,
  times,
  viewport,
  height,
  dimmed,
  hoverTime,
  selectedId,
  onPick,
}: {
  track: TrackSpec;
  photos: readonly ResearchPhoto[];
  times: ReadonlyMap<string, number>;
  viewport: Viewport;
  height: number;
  dimmed?: (photo: ResearchPhoto) => boolean;
  hoverTime?: number | null;
  selectedId?: string | null;
  onPick?: (photo: ResearchPhoto) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const hitRef = useRef<Array<{ x: number; photo: ResearchPhoto }>>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const box = boxRef.current;
    if (!canvas || !box) return;

    const draw = () => {
      const width = box.clientWidth;
      if (width <= 0) return;

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      const color = cssColor(track.color);
      const top = 8;
      const usable = height - 16;
      const y = (value: number) => top + (1 - clamp01(track.normalize(value))) * usable;

      ctx.strokeStyle = resolveToken("--border-subtle", "#1d2a34");
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(0, top + usable / 2);
      ctx.lineTo(width, top + usable / 2);
      ctx.stroke();
      ctx.setLineDash([]);

      const base = resolveToken("--surface-canvas", "#080d12");
      const hits: Array<{ x: number; photo: ResearchPhoto }> = [];
      const points: Array<{ x: number; y: number; photo: ResearchPhoto }> = [];
      let lineOpen = false;

      ctx.strokeStyle = color;
      ctx.lineWidth = 1.7;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.globalAlpha = 0.78;
      ctx.beginPath();

      for (const photo of photos) {
        const time = times.get(photo.id);
        const value = time == null ? null : track.value(photo);
        if (time == null || value == null) {
          lineOpen = false;
          continue;
        }

        const px = timeToX(viewport, time, width);
        if (px < -6 || px > width + 6) {
          lineOpen = false;
          continue;
        }
        hits.push({ x: px, photo });
        const py = y(value);
        points.push({ x: px, y: py, photo });
        if (!lineOpen) {
          ctx.moveTo(px, py);
          lineOpen = true;
        } else {
          ctx.lineTo(px, py);
        }
      }
      ctx.stroke();
      ctx.globalAlpha = 1;

      for (const point of points) {
        const { x: px, y: py, photo } = point;
        const selected = photo.id === selectedId;
        ctx.globalAlpha = dimmed?.(photo) ? 0.18 : 1;
        ctx.beginPath();
        ctx.arc(px, py, selected ? 4 : 1.8, 0, Math.PI * 2);
        ctx.fillStyle = selected ? color : base;
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = selected ? 2 : 1.2;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      hitRef.current = hits;

      if (hoverTime != null) {
        const hx = timeToX(viewport, hoverTime, width);
        if (hx >= 0 && hx <= width) {
          ctx.strokeStyle = resolveToken("--border-focus", "#69cce0");
          ctx.globalAlpha = 0.5;
          ctx.beginPath();
          ctx.moveTo(hx, 0);
          ctx.lineTo(hx, height);
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
      }
    };

    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(box);
    return () => observer.disconnect();
  }, [track, photos, times, viewport, height, dimmed, hoverTime, selectedId]);

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onPick) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    let nearest: { d: number; photo: ResearchPhoto } | null = null;
    for (const hit of hitRef.current) {
      const d = Math.abs(hit.x - x);
      if (d > 8) continue;
      if (!nearest || d < nearest.d) nearest = { d, photo: hit.photo };
    }
    if (nearest) onPick(nearest.photo);
  };

  return (
    <div ref={boxRef} className="relative w-full" style={{ height }}>
      <canvas
        ref={canvasRef}
        className="block"
        role="img"
        aria-label={track.label}
        onClick={handleClick}
      />
    </div>
  );
}
