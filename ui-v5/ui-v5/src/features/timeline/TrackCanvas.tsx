import { useEffect, useRef } from "react";
import type { ResearchPhoto } from "../../shared/researchApi";
import { resolveToken } from "../../shared/ui/tokenColors";
import { timeToX, type Viewport } from "./viewport";

/**
 * Отрисовка дорожек метрик на Canvas 2D (задача З4.1, дефект D12).
 *
 * Раньше каждая дорожка была SVG с отдельным `<circle>` на кадр: при 1909 фото
 * получалось 10 244 DOM-узла и 7 637 кругов, ~1.8 с на первичный рендер. DOM
 * здесь не нужен — точки не интерактивны поштучно, взаимодействие идёт через
 * перекрестие и общий hit-test, поэтому Canvas даёт тот же результат за
 * постоянное число узлов.
 *
 * Что обязательно сохранено из прежней реализации:
 *  - разрыв полилинии на `null`. Отсутствующее измерение нельзя соединять
 *    линией с соседним: получилась бы нарисованная динамика, которой не
 *    измеряли (единственное, что старый код делал правильно — A39);
 *  - `null` не превращается в ноль ни на одном шаге.
 */

export interface TrackSpec {
  key: string;
  label: string;
  /** Подпись диапазона оси. */
  range: string;
  /** CSS-переменная цвета, например `var(--cyan-400)`. */
  color: string;
  value: (photo: ResearchPhoto) => number | null;
  /** Приведение значения к [0,1] для вертикальной оси. */
  normalize: (value: number) => number;
}

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

/** `var(--x)` → вычисленный цвет: Canvas не понимает CSS-переменные. */
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
}: {
  track: TrackSpec;
  photos: readonly ResearchPhoto[];
  times: ReadonlyMap<string, number>;
  viewport: Viewport;
  height: number;
  /** Приглушённые кадры режима находок: рисуются, но бледнее (§8.8). */
  dimmed?: (photo: ResearchPhoto) => boolean;
  hoverTime?: number | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const box = boxRef.current;
    if (!canvas || !box) return;

    const draw = () => {
      const width = box.clientWidth;
      if (width <= 0) return;

      // Canvas масштабируется под плотность экрана, иначе линии мылятся.
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

      // Осевая линия середины диапазона.
      ctx.strokeStyle = resolveToken("--border-subtle", "#1d2a34");
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(0, top + usable / 2);
      ctx.lineTo(width, top + usable / 2);
      ctx.stroke();
      ctx.setLineDash([]);

      /*
       * Полилиния сегментами. Сегмент обрывается там, где нет измерения:
       * пропуск данных обязан выглядеть как пропуск, а не как прямая.
       */
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = "round";
      ctx.beginPath();
      let drawing = false;

      for (const photo of photos) {
        const time = times.get(photo.id);
        const value = time == null ? null : track.value(photo);
        if (time == null || value == null) {
          drawing = false;
          continue;
        }
        const px = timeToX(viewport, time, width);
        const py = y(value);
        if (!drawing) {
          ctx.moveTo(px, py);
          drawing = true;
        } else {
          ctx.lineTo(px, py);
        }
      }
      ctx.stroke();

      // Точки измерений. Приглушённые рисуются полупрозрачными, но остаются.
      const base = resolveToken("--surface-canvas", "#080d12");
      for (const photo of photos) {
        const time = times.get(photo.id);
        const value = time == null ? null : track.value(photo);
        if (time == null || value == null) continue;

        const px = timeToX(viewport, time, width);
        if (px < -4 || px > width + 4) continue;

        ctx.globalAlpha = dimmed?.(photo) ? 0.18 : 1;
        ctx.beginPath();
        ctx.arc(px, y(value), 2.4, 0, Math.PI * 2);
        ctx.fillStyle = base;
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // Перекрестие (§8.4): одна вертикаль через все дорожки.
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

    // Перерисовка при изменении ширины: масштаб зависит от неё.
    const observer = new ResizeObserver(draw);
    observer.observe(box);
    return () => observer.disconnect();
  }, [track, photos, times, viewport, height, dimmed, hoverTime]);

  return (
    <div ref={boxRef} className="relative w-full" style={{ height }}>
      <canvas ref={canvasRef} className="block" role="presentation" />
    </div>
  );
}
