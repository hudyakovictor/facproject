import { useEffect, useRef } from 'react';
import { useTimelineStore } from './store';

/**
 * URL state synchronization for the timeline.
 * Allows sharing links with specific viewport and filter state.
 */

export interface UrlState {
  start?: number;
  end?: number;
  photo?: string;
  pose?: string;
  q?: number;
  findings?: boolean;
}

export function parseUrlState(searchParams: URLSearchParams): UrlState {
  const state: UrlState = {};
  
  const start = searchParams.get('start');
  const end = searchParams.get('end');
  if (start && end) {
    const s = parseInt(start, 10);
    const e = parseInt(end, 10);
    if (!isNaN(s) && !isNaN(e)) {
      state.start = s;
      state.end = e;
    }
  }
  
  const photo = searchParams.get('photo');
  if (photo) state.photo = photo;
  
  const pose = searchParams.get('pose');
  if (pose) state.pose = pose;
  
  const q = searchParams.get('q');
  if (q) {
    const qVal = parseFloat(q);
    if (!isNaN(qVal)) state.q = qVal;
  }
  
  const findings = searchParams.get('findings');
  if (findings === '1') state.findings = true;
  
  return state;
}

export function toUrlState(store: ReturnType<typeof useTimelineStore.getState>): URLSearchParams {
  const params = new URLSearchParams();
  
  if (store.viewport) {
    params.set('start', String(Math.round(store.viewport.start)));
    params.set('end', String(Math.round(store.viewport.end)));
  }
  
  if (store.selectedPhotoId) {
    params.set('photo', store.selectedPhotoId);
  }
  
  if (store.activePoseBin) {
    params.set('pose', store.activePoseBin);
  }
  
  if (store.qualityThreshold > 0) {
    params.set('q', store.qualityThreshold.toFixed(2));
  }
  
  if (store.findingsMode) {
    params.set('findings', '1');
  }
  
  return params;
}

export function useUrlSync() {
  const store = useTimelineStore();
  const hydrated = useRef(false);
  
  // Parse URL on mount
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    
    const params = new URLSearchParams(window.location.search);
    const urlState = parseUrlState(params);
    
    if (urlState.start && urlState.end) {
      store.setUserViewport({ start: urlState.start, end: urlState.end });
    }
    if (urlState.photo) store.setSelectedPhoto(urlState.photo);
    if (urlState.pose) store.setActivePoseBin(urlState.pose);
    if (urlState.q !== undefined) store.setQualityThreshold(urlState.q);
    if (urlState.findings) store.setFindingsMode(true);
  }, []);
  
  // Sync store to URL
  useEffect(() => {
    if (!hydrated.current) return;
    
    const params = toUrlState(store);
    const newSearch = params.toString();
    const currentSearch = window.location.search.slice(1);
    
    if (newSearch !== currentSearch) {
      window.history.replaceState(null, '', newSearch ? `?${newSearch}` : window.location.pathname);
    }
  }, [
    store.viewport,
    store.selectedPhotoId,
    store.activePoseBin,
    store.qualityThreshold,
    store.findingsMode,
  ]);
}
