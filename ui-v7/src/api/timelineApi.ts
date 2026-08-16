import type { TimelineResponse, TimelinePhoto } from '../types/timeline';

/**
 * API client for the timeline.
 * Connects to the FastAPI backend.
 */

const API_BASE = '/api/v1';

export async function fetchTimeline(): Promise<TimelineResponse> {
  try {
    const response = await fetch(`${API_BASE}/timeline`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn('Failed to fetch timeline, using mock data:', error);
    // Fallback to mock data
    const { generateMockTimeline } = await import('../data/mockTimeline');
    return generateMockTimeline(1709);
  }
}

export async function fetchPhotoInfo(photoId: string): Promise<Record<string, unknown>> {
  try {
    const response = await fetch(`${API_BASE}/photos/${encodeURIComponent(photoId)}/info`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn(`Failed to fetch photo info for ${photoId}:`, error);
    return {};
  }
}

export async function fetchLandmarks(photoId: string, count: number = 106, space: string = 'raw'): Promise<{
  points: number[][];
  columns: string[];
}> {
  try {
    const response = await fetch(
      `${API_BASE}/photos/${encodeURIComponent(photoId)}/landmarks/${count}/${space}`
    );
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn(`Failed to fetch landmarks for ${photoId}:`, error);
    return { points: [], columns: [] };
  }
}

export async function fetchPairMetrics(photoA: string, photoB: string): Promise<Record<string, unknown>> {
  try {
    const response = await fetch(
      `${API_BASE}/pairs/${encodeURIComponent(photoA)}/${encodeURIComponent(photoB)}/metrics`
    );
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn(`Failed to fetch pair metrics:`, error);
    return {};
  }
}

export async function fetchCalibrationHealth(): Promise<{
  total_records: number;
  total_persons: number;
  confidence_counts: Record<string, number>;
  buckets: Record<string, unknown>;
}> {
  try {
    const response = await fetch(`${API_BASE}/calibration/health`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn('Failed to fetch calibration health:', error);
    return { total_records: 0, total_persons: 0, confidence_counts: {}, buckets: {} };
  }
}

/**
 * Transform API response to internal format.
 */
export function transformApiResponse(data: TimelineResponse): TimelinePhoto[] {
  return data.photos.map(photo => ({
    ...photo,
    // Ensure all fields have proper defaults
    quality: photo.quality ?? null,
    alignmentQuality: photo.alignmentQuality ?? null,
    skinAuthenticity: photo.skinAuthenticity ?? null,
    siliconeProb: photo.siliconeProb ?? null,
    boneScore: photo.boneScore ?? null,
    symmetry: photo.symmetry ?? null,
    ldmShapeDifference: photo.ldmShapeDifference ?? null,
    ldm106Difference: photo.ldm106Difference ?? null,
    ldm134Difference: photo.ldm134Difference ?? null,
  }));
}
