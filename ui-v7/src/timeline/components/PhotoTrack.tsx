import type { TimelinePhoto, Viewport } from '../../types/timeline';
import { photosInColumns, timeOf, timeToX } from '../viewport';
import { photoThumbnailUrl } from '../../api/timelineApi';

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
  const sortedPhotos = photosInColumns(photos, viewport);
  const spacing = sortedPhotos.length > 1 ? width / sortedPhotos.length : width;
  const thumbnailSize = Math.min(100, Math.max(50, spacing * 0.82));

  return (
    <div className="photo-track" style={{ height }}>
      {sortedPhotos.map((photo) => {
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
            style={{
              left: `${timeToX(viewport, timeOf(photo) ?? viewport.start, width) - thumbnailSize / 2}px`,
              width: `${thumbnailSize}px`,
              height: `${thumbnailSize}px`,
            }}
            onClick={(e) => onPhotoClick(photo, e.shiftKey)}
            title={`${photo.date ?? 'н/д'} · ${photo.bucket} · q:${(photo.quality ?? 0).toFixed(2)}`}
          >
            <img
              className="photo-thumb-image"
              src={photoThumbnailUrl(photo.id)}
              alt=""
              loading="lazy"
            />
            {isPairA && <span className="photo-thumb-pin pin-a">A</span>}
            {isPairB && <span className="photo-thumb-pin pin-b">B</span>}
          </button>
        );
      })}
    </div>
  );
}
