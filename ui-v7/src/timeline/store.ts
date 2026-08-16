import { create } from 'zustand';
import type { TimelinePhoto, Viewport, TimeBounds, AnomalyEvent, AnomalyKind } from '../types/timeline';
import { timeOf, boundsOf, fitViewport } from './viewport';

/**
 * Timeline state management with Zustand.
 */

export interface TimelineState {
  // Data
  photos: TimelinePhoto[];
  filteredPhotos: TimelinePhoto[];
  anomalies: AnomalyEvent[];
  
  // Viewport
  viewport: Viewport | null;
  bounds: TimeBounds | null;
  userViewport: Viewport | null;
  
  // Selection
  selectedPhotoId: string | null;
  pairAId: string | null;
  pairBId: string | null;
  hoverTime: number | null;
  
  // Filters
  qualityThreshold: number;
  poseAngleThreshold: number;
  mouthThreshold: number;
  skinAuthenticityThreshold: number;
  siliconeProbThreshold: number;
  shapeDifferenceThreshold: number;
  findingsMode: boolean;
  activePoseBin: string | null;
  showMultiPose: boolean;
  activeAnomalyKinds: Set<AnomalyKind>;
  isDragging: boolean;
  isPanning: boolean;
  showFilters: boolean;
  showMetrics: boolean;
  
  // Actions
  setPhotos: (photos: TimelinePhoto[]) => void;
  setViewport: (viewport: Viewport) => void;
  setUserViewport: (viewport: Viewport | null) => void;
  resetViewport: () => void;
  setSelectedPhoto: (id: string | null) => void;
  setPairA: (id: string | null) => void;
  setPairB: (id: string | null) => void;
  assignToPair: (id: string) => void;
  clearPair: () => void;
  swapPair: () => void;
  setHoverTime: (time: number | null) => void;
  setQualityThreshold: (value: number) => void;
  setPoseAngleThreshold: (value: number) => void;
  setMouthThreshold: (value: number) => void;
  setSkinAuthenticityThreshold: (value: number) => void;
  setSiliconeProbThreshold: (value: number) => void;
  setShapeDifferenceThreshold: (value: number) => void;
  setFindingsMode: (value: boolean) => void;
  setActivePoseBin: (value: string | null) => void;
  setShowMultiPose: (value: boolean) => void;
  toggleAnomalyKind: (kind: AnomalyKind) => void;
  setIsDragging: (value: boolean) => void;
  setIsPanning: (value: boolean) => void;
  setShowFilters: (value: boolean) => void;
  setShowMetrics: (value: boolean) => void;
}

export const useTimelineStore = create<TimelineState>((set, get) => ({
  // Initial state
  photos: [],
  filteredPhotos: [],
  anomalies: [],
  viewport: null,
  bounds: null,
  userViewport: null,
  selectedPhotoId: null,
  pairAId: null,
  pairBId: null,
  hoverTime: null,
  qualityThreshold: 0,
  poseAngleThreshold: 6,
  mouthThreshold: 0.35,
  skinAuthenticityThreshold: 0,
  siliconeProbThreshold: 1,
  shapeDifferenceThreshold: 1,
  findingsMode: false,
  activePoseBin: null,
  showMultiPose: false,
  activeAnomalyKinds: new Set(['change_point', 'persistent_change', 'return', 'rapid_rate', 'same_day', 'provenance', 'review']),
  isDragging: false,
  isPanning: false,
  showFilters: false,
  showMetrics: false,

  // Actions
  setPhotos: (photos) => {
    const bounds = boundsOf(photos);
    const viewport = bounds ? fitViewport(bounds) : null;
    set({
      photos,
      filteredPhotos: photos,
      bounds,
      viewport,
    });
  },

  setViewport: (viewport) => set({ viewport }),
  
  setUserViewport: (userViewport) => {
    const { bounds } = get();
    if (!userViewport || !bounds) {
      set({ userViewport, viewport: bounds ? fitViewport(bounds) : null });
      return;
    }
    // Clamp to bounds
    const span = Math.max(userViewport.end - userViewport.start, 86_400_000);
    let start = userViewport.start;
    if (start < bounds.min) start = bounds.min;
    if (start + span > bounds.max) start = bounds.max - span;
    const viewport = { start, end: start + span };
    set({ userViewport, viewport });
  },

  resetViewport: () => {
    const { bounds } = get();
    set({
      userViewport: null,
      viewport: bounds ? fitViewport(bounds) : null,
    });
  },

  setSelectedPhoto: (selectedPhotoId) => set({ selectedPhotoId }),
  
  setPairA: (pairAId) => set({ pairAId }),
  setPairB: (pairBId) => set({ pairBId }),
  
  assignToPair: (id) => {
    const { pairAId, photos } = get();
    const photo = photos.find((p) => p.id === id);
    if (!photo) return;
    
    if (!pairAId) {
      set({ pairAId: id });
      return;
    }
    if (pairAId === id) return;
    
    const pairAPhoto = photos.find((p) => p.id === pairAId);
    if (pairAPhoto && pairAPhoto.bucket !== photo.bucket) {
      // Different pose bins - reject
      return;
    }
    
    set({ pairBId: id });
  },

  clearPair: () => set({ pairAId: null, pairBId: null }),
  
  swapPair: () => {
    const { pairAId, pairBId } = get();
    set({ pairAId: pairBId, pairBId: pairAId });
  },

  setHoverTime: (hoverTime) => set({ hoverTime }),
  
  setQualityThreshold: (qualityThreshold) => set({ qualityThreshold }),
  setPoseAngleThreshold: (poseAngleThreshold) => set({ poseAngleThreshold }),
  setMouthThreshold: (mouthThreshold) => set({ mouthThreshold }),
  setSkinAuthenticityThreshold: (skinAuthenticityThreshold) => set({ skinAuthenticityThreshold }),
  setSiliconeProbThreshold: (siliconeProbThreshold) => set({ siliconeProbThreshold }),
  setShapeDifferenceThreshold: (shapeDifferenceThreshold) => set({ shapeDifferenceThreshold }),
  setFindingsMode: (findingsMode) => set({ findingsMode }),
  setActivePoseBin: (activePoseBin) => set({ activePoseBin }),
  setShowMultiPose: (showMultiPose) => set({ showMultiPose }),
  
  toggleAnomalyKind: (kind) => {
    const { activeAnomalyKinds } = get();
    const next = new Set(activeAnomalyKinds);
    if (next.has(kind)) {
      next.delete(kind);
    } else {
      next.add(kind);
    }
    set({ activeAnomalyKinds: next });
  },

  setIsDragging: (isDragging) => set({ isDragging }),
  setIsPanning: (isPanning) => set({ isPanning }),
  setShowFilters: (showFilters) => set({ showFilters }),
  setShowMetrics: (showMetrics) => set({ showMetrics }),
}));

/**
 * Helper to get time from photo
 */
export function getTimeFromPhoto(photo: TimelinePhoto): number | null {
  return timeOf(photo);
}

/**
 * Helper to check if photo passes filters
 */
export function photoPassesFilters(photo: TimelinePhoto, state: TimelineState): boolean {
  // Quality filter
  if (photo.quality != null && photo.quality < state.qualityThreshold) {
    return false;
  }
  
  // Pose angle filter
  const residualValues = [photo.residualYaw, photo.residualPitch, photo.residualRoll]
    .filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
    .map((v) => Math.abs(v));
  const residual = residualValues.length > 0 ? Math.max(...residualValues) : null;
  if (residual !== null && residual > state.poseAngleThreshold) {
    return false;
  }
  
  // Mouth filter
  if (photo.jawOpenRatio != null && photo.jawOpenRatio > state.mouthThreshold) {
    return false;
  }
  
  // Pose bin filter
  if (!state.showMultiPose && state.activePoseBin && photo.bucket !== state.activePoseBin) {
    return false;
  }
  
  // Findings mode
  if (state.findingsMode) {
    const hasFinding = photo.flags.some((f) => 
      ['coherent_jump_candidate', 'persistent_geometric_change'].includes(f)
    );
    if (!hasFinding) return false;
  }
  
  return true;
}
