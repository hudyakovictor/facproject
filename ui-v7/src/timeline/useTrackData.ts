import { useMemo } from 'react';
import type { TimelinePhoto, Viewport, TrackDescriptor } from '../types/timeline';
import { timeToX } from './viewport';

/**
 * Optimized track data computation with memoization.
 * Pre-computes points and domains for canvas rendering.
 */

export interface ComputedTrackData {
  descriptor: TrackDescriptor;
  points: Array<{ x: number; y: number; photo: TimelinePhoto }>;
  domain: [number, number];
}

export function useTrackData(
  track: TrackDescriptor,
  photos: readonly TimelinePhoto[],
  viewport: Viewport,
  width: number,
  height: number
): ComputedTrackData {
  return useMemo(() => {
    const padding = 8;
    const usableHeight = height - padding * 2;
    
    // Calculate domain
    let lo: number;
    let hi: number;
    if (track.domain) {
      [lo, hi] = track.domain;
    } else {
      lo = Number.POSITIVE_INFINITY;
      hi = Number.NEGATIVE_INFINITY;
      for (const photo of photos) {
        const value = photo[track.dataKey as keyof TimelinePhoto];
        if (typeof value !== 'number' || !Number.isFinite(value)) continue;
        if (value < lo) lo = value;
        if (value > hi) hi = value;
      }
      if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
        lo = 0;
        hi = 1;
      }
      if (lo === hi) {
        lo -= 0.5;
        hi += 0.5;
      }
    }
    
    const span = hi - lo || 1;
    
    // Compute points
    const points: Array<{ x: number; y: number; photo: TimelinePhoto }> = [];
    
    for (const photo of photos) {
      const time = photo.t;
      const value = photo[track.dataKey as keyof TimelinePhoto];
      if (time == null || typeof value !== 'number') continue;
      
      const x = timeToX(viewport, time, width);
      if (x < -10 || x > width + 10) continue;
      
      const normalized = (value - lo) / span;
      const y = padding + (1 - normalized) * usableHeight;
      points.push({ x, y, photo });
    }
    
    // Sort by x for line drawing
    points.sort((a, b) => a.x - b.x);
    
    return {
      descriptor: track,
      points,
      domain: [lo, hi],
    };
  }, [track, photos, viewport, width, height]);
}

/**
 * Filter photos by viewport for performance.
 * Only returns photos visible in the current viewport.
 */
export function useViewportPhotos(
  photos: readonly TimelinePhoto[],
  viewport: Viewport,
  bufferRatio: number = 0.1
): TimelinePhoto[] {
  return useMemo(() => {
    const span = viewport.end - viewport.start;
    const buffer = span * bufferRatio;
    const minTime = viewport.start - buffer;
    const maxTime = viewport.end + buffer;
    
    return photos.filter(p => {
      const t = p.t;
      return t != null && t >= minTime && t <= maxTime;
    });
  }, [photos, viewport, bufferRatio]);
}