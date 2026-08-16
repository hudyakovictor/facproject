import type { Viewport, TimeBounds, TimelinePhoto } from '../types/timeline';

/**
 * Viewport utilities for the timeline.
 * Handles time-to-pixel conversions, zoom, and pan operations.
 */

const MIN_SPAN_MS = 86_400_000; // 1 day in ms
const YEAR_MS = 365.25 * 86_400_000;

/**
 * Get time value from a photo.
 * Prioritizes date string, falls back to t field if it looks like a timestamp.
 */
export function timeOf(photo: Pick<TimelinePhoto, 'date' | 't'>): number | null {
  if (photo.date) {
    const parsed = Date.parse(photo.date);
    if (Number.isFinite(parsed)) return parsed;
  }
  if (typeof photo.t === 'number' && Number.isFinite(photo.t) && Math.abs(photo.t) > 1e6) {
    return photo.t;
  }
  return null;
}

/**
 * Calculate time bounds from a list of photos.
 */
export function boundsOf(photos: readonly TimelinePhoto[]): TimeBounds | null {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  
  for (const photo of photos) {
    const t = timeOf(photo);
    if (t == null) continue;
    if (t < min) min = t;
    if (t > max) max = t;
  }
  
  if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
  
  // Ensure minimum span
  if (max - min < MIN_SPAN_MS) {
    max = min + MIN_SPAN_MS;
  }
  
  return { min, max };
}

/**
 * Get the span of a viewport.
 */
export function spanOf(viewport: Viewport): number {
  return Math.max(viewport.end - viewport.start, 1);
}

/**
 * Convert time to ratio [0, 1] within viewport.
 */
export function timeToRatio(viewport: Viewport, time: number): number {
  return (time - viewport.start) / spanOf(viewport);
}

/**
 * Convert time to x pixel coordinate.
 */
export function timeToX(viewport: Viewport, time: number, width: number): number {
  return timeToRatio(viewport, time) * width;
}

/**
 * Convert x pixel coordinate to time.
 */
export function xToTime(viewport: Viewport, x: number, width: number): number {
  return viewport.start + (x / Math.max(width, 1)) * spanOf(viewport);
}

/**
 * Clamp viewport to bounds while preserving span.
 */
export function clampViewport(viewport: Viewport, bounds: TimeBounds): Viewport {
  const total = bounds.max - bounds.min;
  const span = Math.min(Math.max(spanOf(viewport), MIN_SPAN_MS), total);
  
  let start = viewport.start;
  if (start < bounds.min) start = bounds.min;
  if (start + span > bounds.max) start = bounds.max - span;
  
  return { start, end: start + span };
}

/**
 * Zoom viewport anchored at a specific time.
 */
export function zoomAt(
  viewport: Viewport,
  bounds: TimeBounds,
  anchorTime: number,
  factor: number
): Viewport {
  const span = spanOf(viewport);
  const total = bounds.max - bounds.min;
  const nextSpan = Math.min(Math.max(span * factor, MIN_SPAN_MS), total);
  
  // Preserve anchor position
  const anchorRatio = (anchorTime - viewport.start) / span;
  const start = anchorTime - anchorRatio * nextSpan;
  
  return clampViewport({ start, end: start + nextSpan }, bounds);
}

/**
 * Pan viewport by a ratio of its span.
 */
export function panBy(viewport: Viewport, bounds: TimeBounds, ratio: number): Viewport {
  const delta = spanOf(viewport) * ratio;
  return clampViewport({ start: viewport.start + delta, end: viewport.end + delta }, bounds);
}

/**
 * Create a viewport that fits the entire bounds.
 */
export function fitViewport(bounds: TimeBounds): Viewport {
  return { start: bounds.min, end: bounds.max };
}

/**
 * Calculate zoom level relative to full bounds.
 */
export function zoomLevel(viewport: Viewport, bounds: TimeBounds): number {
  return (bounds.max - bounds.min) / spanOf(viewport);
}

/**
 * Generate tick marks for the ruler.
 */
export interface Tick {
  time: number;
  label: string;
  major: boolean;
}

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];

export function ticksFor(viewport: Viewport): Tick[] {
  const span = spanOf(viewport);
  const ticks: Tick[] = [];
  const startDate = new Date(viewport.start);
  
  // Decade or 5-year steps for very large spans
  if (span > 40 * YEAR_MS) {
    const step = 10;
    let year = Math.floor(startDate.getUTCFullYear() / step) * step;
    while (Date.UTC(year, 0, 1) <= viewport.end) {
      const time = Date.UTC(year, 0, 1);
      if (time >= viewport.start) ticks.push({ time, label: String(year), major: true });
      year += step;
    }
    return ticks;
  }
  
  // 5-year steps for large spans
  if (span > 12 * YEAR_MS) {
    const step = 5;
    let year = Math.floor(startDate.getUTCFullYear() / step) * step;
    while (Date.UTC(year, 0, 1) <= viewport.end) {
      const time = Date.UTC(year, 0, 1);
      if (time >= viewport.start) ticks.push({ time, label: String(year), major: true });
      year += step;
    }
    return ticks;
  }
  
  // Year steps for medium spans
  if (span > 2 * YEAR_MS) {
    let year = startDate.getUTCFullYear();
    while (Date.UTC(year, 0, 1) <= viewport.end) {
      const time = Date.UTC(year, 0, 1);
      if (time >= viewport.start) ticks.push({ time, label: String(year), major: true });
      year += 1;
    }
    return ticks;
  }
  
  // Quarter steps for smaller spans
  if (span > 120 * 86_400_000) {
    let year = startDate.getUTCFullYear();
    let quarter = Math.floor(startDate.getUTCMonth() / 3);
    while (Date.UTC(year, quarter * 3, 1) <= viewport.end) {
      const time = Date.UTC(year, quarter * 3, 1);
      if (time >= viewport.start) {
        ticks.push({
          time,
          label: quarter === 0 ? String(year) : `Q${quarter + 1}`,
          major: quarter === 0,
        });
      }
      quarter += 1;
      if (quarter > 3) {
        quarter = 0;
        year += 1;
      }
    }
    return ticks;
  }
  
  // Month steps for detailed view
  let year = startDate.getUTCFullYear();
  let month = startDate.getUTCMonth();
  while (Date.UTC(year, month, 1) <= viewport.end) {
    const time = Date.UTC(year, month, 1);
    if (time >= viewport.start) {
      ticks.push({
        time,
        label: month === 0 ? String(year) : MONTHS[month] ?? '',
        major: month === 0,
      });
    }
    month += 1;
    if (month > 11) {
      month = 0;
      year += 1;
    }
  }
  
  return ticks;
}
