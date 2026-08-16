import type { TimelinePhoto, Viewport } from '../../types/timeline';
import { timeToRatio } from '../viewport';

/**
 * Photo track component.
 * Displays photo thumbnails along the timeline.
 */

interface PhotoTrackProps {
  photos: TimelinePhoto[];
  viewport: Viewport;
  width: number;
  height: number;
  selectedPhotoId: string | null;
  pairAId: string | null;
  pairBId: string | null;
  onPhotoClick: (photo: TimelinePhoto, asPair: boolean) => void;
}

export function PhotoTrack({
  photos,
  viewport,
  width,
  height,
  selectedPhotoId,
  pairAId,
  pairBId,
  onPhotoClick,
}: PhotoTrackProps) {
  const slotWidth = 50;
  const slotCount = Math.max(1, Math.floor(width / slotWidth));
  
  // Pick representatives for each slot
  const representatives = new Map<number, TimelinePhoto>();
  
  for (const photo of photos) {
    const time = photo.t;
    if (time == null) continue;
    
    const ratio = timeToRatio(viewport, time);
    if (ratio < 0 || ratio > 1) continue;
    
    const slot = Math.min(slotCount - 1, Math.floor(ratio * slotCount));
    const existing = representatives.get(slot);
    
    if (!existing || (photo.quality ?? 0) > (existing.quality ?? 0)) {
      representatives.set(slot, photo);
    }
  }

  // Always include pinned photos
  const pinnedIds = [pairAId, pairBId, selectedPhotoId].filter(Boolean) as string[];
  for (const photo of photos) {
    if (pinnedIds.includes(photo.id)) {
      const time = photo.t;
      if (time == null) continue;
      const ratio = timeToRatio(viewport, time);
      if (ratio < 0 || ratio > 1) continue;
      const slot = Math.min(slotCount - 1, Math.floor(ratio * slotCount));
      representatives.set(slot, photo);
    }
  }

  const sortedPhotos = [...representatives.values()].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));

  return (
    <div className="photo-track" style={{ height }}>
      {sortedPhotos.map((photo) => {
        const time = photo.t ?? 0;
        const ratio = timeToRatio(viewport, time);
        const left = ratio * 100;
        const isSelected = photo.id === selectedPhotoId;
        const isPairA = photo.id === pairAId;
        const isPairB = photo.id === pairBId;
        const hasFinding = photo.flags.some((f) => 
          ['coherent_jump_candidate', 'persistent_geometric_change'].includes(f)
        );

        let className = 'photo-thumb';
        if (isSelected) className += ' selected';
        if (isPairA) className += ' pair-a';
        if (isPairB) className += ' pair-b';
        if (hasFinding) className += ' finding';

        return (
          <button
            key={photo.id}
            className={className}
            style={{ left: `${left}%` }}
            onClick={(e) => onPhotoClick(photo, e.shiftKey)}
            title={`${photo.date ?? 'н/д'} · ${photo.bucket} · q:${(photo.quality ?? 0).toFixed(2)}`}
          >
            <span className="photo-thumb-label">
              {photo.date?.slice(0, 10) ?? 'н/д'}
            </span>
            {isPairA && <span className="photo-thumb-pin pin-a">A</span>}
            {isPairB && <span className="photo-thumb-pin pin-b">B</span>}
          </button>
        );
      })}
    </div>
  );
}
