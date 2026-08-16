import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTimelineStore } from '../../timeline/store';
import { TRACK_DEFINITIONS } from '../../timeline/tracks';
import { zoomAt, panBy } from '../../timeline/viewport';
import { fetchTimeline, transformApiResponse } from '../../api/timelineApi';
import { TimelineCanvas } from '../../timeline/components/TimelineCanvas';
import { TimelineRuler } from '../../timeline/components/TimelineRuler';
import { PhotoTrack } from '../../timeline/components/PhotoTrack';
import { AnomalyTrack } from '../../timeline/components/AnomalyTrack';
import { TrackLabel } from '../../timeline/components/TrackLabel';
import { TimelineToolbar } from '../../timeline/components/TimelineToolbar';
import { TimelineMinimap } from '../../timeline/components/TimelineMinimap';
import { PhotoDetailCard } from '../../timeline/components/PhotoDetailCard';
import { FilterPanel } from '../../timeline/components/FilterPanel';
import { BiologicalImpossibilityTrack } from '../../timeline/components/BiologicalImpossibilityTrack';
import { useUrlSync } from '../../timeline/useUrlSync';
import { ModelViewer3D } from '../../timeline/components/ModelViewer3D';
import { FilterPresets } from '../../timeline/components/FilterPresets';
import { HelpOverlay } from '../../timeline/components/HelpOverlay';
import { DataLogger } from '../../timeline/components/DataLogger';
import type { TimelinePhoto, AnomalyEvent, TimelineResponse } from '../../types/timeline';
import './timeline.css';

/**
 * Main Timeline Page component.
 * Adobe Premiere-style forensic timeline interface.
 * Iteration 2: Enhanced with tooltips, detail card, filters, keyboard nav.
 */

const LABEL_COLUMN_WIDTH = 180;

export function TimelinePage() {
  const store = useTimelineStore();
  const [areaWidth, setAreaWidth] = useState(1200);
  const containerRef = useRef<HTMLDivElement>(null);
  const trackAreaRef = useRef<HTMLDivElement>(null);
  const [showFilterPanel, setShowFilterPanel] = useState(false);
  const [show3DView, setShow3DView] = useState(true);
  const [showPresets, setShowPresets] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [timelineData, setTimelineData] = useState<TimelineResponse | null>(null);
  
  // URL state synchronization
  useUrlSync();

  // Initialize with API data (fallback to mock)
  useEffect(() => {
    fetchTimeline().then(data => {
      setTimelineData(data);
      const photos = transformApiResponse(data);
      store.setPhotos(photos);
    
    // Generate anomalies from data
    const anomalies: AnomalyEvent[] = [];
    const manifest = data.analysis_manifest ?? {};
    const chronology = data.chronology_anomalies ?? {};
    
    // Change points
    const changePoints = (manifest.change_points as { years?: number[] })?.years ?? [];
    for (const year of changePoints) {
      anomalies.push({
        id: `cp-${year}`,
        kind: 'change_point' as const,
        label: `Точка перелома · ${year}`,
        time: Date.UTC(year, 6, 1),
        year,
      });
    }
    
    // Returns
    const returns = (chronology.baseline_return as { years?: number[] })?.years ?? [];
    for (const year of returns) {
      anomalies.push({
        id: `rt-${year}`,
        kind: 'return' as const,
        label: `Возврат к базе · ${year}`,
        time: Date.UTC(year, 6, 1),
        year,
      });
    }
    
    // Rapid rate
    const rapidRate = (chronology.chronology_rate as { years?: number[] })?.years ?? [];
    for (const year of rapidRate) {
      anomalies.push({
        id: `rr-${year}`,
        kind: 'rapid_rate' as const,
        label: `Аномальный темп · ${year}`,
        time: Date.UTC(year, 6, 1),
        year,
      });
    }
    
    useTimelineStore.setState({ anomalies });
    });
  }, []);

  // Filter photos based on store state
  const filteredPhotos = useMemo(() => {
    return store.photos.filter((photo) => {
      // Quality filter
      if (photo.quality != null && photo.quality < store.qualityThreshold) {
        return false;
      }
      
      // Pose angle filter
      const residualValues = [photo.residualYaw, photo.residualPitch, photo.residualRoll]
        .filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
        .map((v) => Math.abs(v));
      const residual = residualValues.length > 0 ? Math.max(...residualValues) : null;
      if (residual !== null && residual > store.poseAngleThreshold) {
        return false;
      }
      
      // Mouth filter
      if (photo.jawOpenRatio != null && photo.jawOpenRatio > store.mouthThreshold) {
        return false;
      }
      
      // Skin authenticity filter
      if (photo.skinAuthenticity != null && photo.skinAuthenticity < store.skinAuthenticityThreshold) {
        return false;
      }
      
      // Silicone probability filter
      if (photo.siliconeProb != null && photo.siliconeProb > store.siliconeProbThreshold) {
        return false;
      }
      
      // Shape difference filter
      if (photo.ldmShapeDifference != null && photo.ldmShapeDifference > store.shapeDifferenceThreshold) {
        return false;
      }
      
      // Pose bin filter
      if (!store.showMultiPose && store.activePoseBin && photo.bucket !== store.activePoseBin) {
        return false;
      }
      
      // Search filter
      if (store.searchQuery) {
        const query = store.searchQuery.toLowerCase();
        const haystack = [
          photo.id,
          photo.date ?? '',
          photo.bucket,
          photo.era,
          photo.fuzzy,
          ...photo.flags,
        ].join(' ').toLowerCase();
        if (!haystack.includes(query)) {
          return false;
        }
      }
      
      // Findings mode
      if (store.findingsMode) {
        const hasFinding = photo.flags.some((f) => 
          ['coherent_jump_candidate', 'persistent_geometric_change'].includes(f)
        );
        if (!hasFinding) return false;
      }
      
      return true;
    });
  }, [store.photos, store.qualityThreshold, store.poseAngleThreshold, store.mouthThreshold, 
      store.searchQuery, store.findingsMode, store.skinAuthenticityThreshold, 
      store.siliconeProbThreshold, store.shapeDifferenceThreshold, store.activePoseBin, 
      store.showMultiPose]);

  // Get visible tracks
  const visibleTracks = useMemo(() => {
    return TRACK_DEFINITIONS.filter((t) => t.visible);
  }, []);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateSize = () => {
      setAreaWidth(container.clientWidth - LABEL_COLUMN_WIDTH);
    };
    updateSize();

    const observer = new ResizeObserver(updateSize);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Wheel zoom
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onWheel = (e: WheelEvent) => {
      if (!store.viewport || !store.bounds) return;
      e.preventDefault();

      const rect = container.getBoundingClientRect();
      const localX = e.clientX - rect.left - LABEL_COLUMN_WIDTH;
      const anchorTime = store.viewport.start + (localX / areaWidth) * (store.viewport.end - store.viewport.start);

      if (e.deltaX !== 0 || e.shiftKey) {
        store.setUserViewport(panBy(store.viewport, store.bounds, (e.deltaX !== 0 ? e.deltaX : e.deltaY) / areaWidth));
      } else {
        store.setUserViewport(zoomAt(store.viewport, store.bounds, anchorTime, e.deltaY > 0 ? 1.15 : 0.87));
      }
    };

    container.addEventListener('wheel', onWheel, { passive: false });
    return () => container.removeEventListener('wheel', onWheel);
  }, [store.viewport, store.bounds, areaWidth]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && /input|textarea|select/i.test(target.tagName)) return;

      switch (e.key) {
        case '+':
        case '=':
          handleZoomIn();
          break;
        case '-':
          handleZoomOut();
          break;
        case '0':
          handleFitView();
          break;
        case 'f':
          if (!e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            setShowFilterPanel(p => !p);
          }
          break;
        case '?':
          e.preventDefault();
          setShowHelp(p => !p);
          break;
        case 'Escape':
          if (showFilterPanel) {
            setShowFilterPanel(false);
          } else if (store.selectedPhotoId) {
            store.setSelectedPhoto(null);
          }
          break;
        case 'ArrowLeft':
          handlePreviousPhoto();
          break;
        case 'ArrowRight':
          handleNextPhoto();
          break;
        case 'a':
          if (store.selectedPhotoId && !e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            store.assignToPair(store.selectedPhotoId);
          }
          break;
        case 'Tab':
          e.preventDefault();
          if (e.shiftKey) {
            handlePreviousFinding();
          } else {
            handleNextFinding();
          }
          break;
      }
    };

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const handleZoomIn = useCallback(() => {
    if (!store.viewport || !store.bounds) return;
    const center = (store.viewport.start + store.viewport.end) / 2;
    store.setUserViewport(zoomAt(store.viewport, store.bounds, center, 0.8));
  }, [store.viewport, store.bounds]);

  const handleZoomOut = useCallback(() => {
    if (!store.viewport || !store.bounds) return;
    const center = (store.viewport.start + store.viewport.end) / 2;
    store.setUserViewport(zoomAt(store.viewport, store.bounds, center, 1.25));
  }, [store.viewport, store.bounds]);

  const handleFitView = useCallback(() => {
    store.resetViewport();
  }, []);

  const handlePreviousPhoto = useCallback(() => {
    if (!store.viewport) return;
    const currentTime = (store.viewport.start + store.viewport.end) / 2;
    const sortedPhotos = [...filteredPhotos].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
    const prevPhoto = sortedPhotos.reverse().find(p => (p.t ?? 0) < currentTime);
    if (prevPhoto) store.setSelectedPhoto(prevPhoto.id);
  }, [filteredPhotos, store.viewport]);

  const handleNextPhoto = useCallback(() => {
    if (!store.viewport) return;
    const currentTime = (store.viewport.start + store.viewport.end) / 2;
    const sortedPhotos = [...filteredPhotos].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
    const nextPhoto = sortedPhotos.find(p => (p.t ?? 0) > currentTime);
    if (nextPhoto) store.setSelectedPhoto(nextPhoto.id);
  }, [filteredPhotos, store.viewport]);

  const handlePreviousFinding = useCallback(() => {
    const findingPhotos = filteredPhotos.filter(p => 
      p.flags.some(f => ['coherent_jump_candidate', 'persistent_geometric_change'].includes(f))
    ).sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
    
    const currentIndex = findingPhotos.findIndex(p => p.id === store.selectedPhotoId);
    if (currentIndex > 0) {
      store.setSelectedPhoto(findingPhotos[currentIndex - 1]!.id);
    } else if (findingPhotos.length > 0) {
      store.setSelectedPhoto(findingPhotos[findingPhotos.length - 1]!.id);
    }
  }, [filteredPhotos, store.selectedPhotoId]);

  const handleNextFinding = useCallback(() => {
    const findingPhotos = filteredPhotos.filter(p => 
      p.flags.some(f => ['coherent_jump_candidate', 'persistent_geometric_change'].includes(f))
    ).sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
    
    const currentIndex = findingPhotos.findIndex(p => p.id === store.selectedPhotoId);
    if (currentIndex >= 0 && currentIndex < findingPhotos.length - 1) {
      store.setSelectedPhoto(findingPhotos[currentIndex + 1]!.id);
    } else if (findingPhotos.length > 0) {
      store.setSelectedPhoto(findingPhotos[0]!.id);
    }
  }, [filteredPhotos, store.selectedPhotoId]);

  const handlePhotoClick = useCallback((photo: TimelinePhoto, asPair: boolean) => {
    store.setSelectedPhoto(photo.id);
    if (asPair) {
      store.assignToPair(photo.id);
    }
  }, []);

  const handleAnomalyClick = useCallback((anomaly: AnomalyEvent) => {
    if (anomaly.photoId) {
      store.setSelectedPhoto(anomaly.photoId);
    }
  }, []);

  const handleMinimapBrush = useCallback((start: number, end: number) => {
    store.setUserViewport({ start, end });
  }, []);

  const handleExportCSV = useCallback(() => {
    const headers = ['id', 'date', 'bucket', 'quality', 'skin_authenticity', 'silicone_prob', 
                     'bone_score', 'symmetry', 'ldm_shape_difference', 'yaw', 'pitch', 'roll'];
    const rows = filteredPhotos.map(p => [
      p.id, p.date ?? '', p.bucket, 
      p.quality?.toFixed(3) ?? '', p.skinAuthenticity?.toFixed(3) ?? '',
      p.siliconeProb?.toFixed(3) ?? '', p.boneScore?.toFixed(3) ?? '',
      p.symmetry?.toFixed(3) ?? '', p.ldmShapeDifference?.toFixed(3) ?? '',
      p.yaw?.toFixed(2) ?? '', p.pitch?.toFixed(2) ?? '', p.roll?.toFixed(2) ?? ''
    ].join(','));
    
    const csv = ['#' + 'НЕ ВЕРДИКТ: технический результат измерений', headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `timeline-export-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }, [filteredPhotos]);

  const selectedPhoto = useMemo(() => {
    return store.photos.find(p => p.id === store.selectedPhotoId) ?? null;
  }, [store.photos, store.selectedPhotoId]);

  if (!store.viewport || !store.bounds) {
    return <div className="timeline-loading">Загрузка таймлайна...</div>;
  }

  return (
    <div className="timeline-page" ref={containerRef}>
      <TimelineToolbar
        viewport={store.viewport}
        bounds={store.bounds}
        photoCount={store.photos.length}
        filteredCount={filteredPhotos.length}
        qualityThreshold={store.qualityThreshold}
        findingsMode={store.findingsMode}
        searchQuery={store.searchQuery}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onFitView={handleFitView}
        onQualityChange={store.setQualityThreshold}
        onFindingsToggle={() => store.setFindingsMode(!store.findingsMode)}
        onSearchChange={store.setSearchQuery}
        onToggleFilters={() => setShowFilterPanel(!showFilterPanel)}
        onExportCSV={handleExportCSV}
        onToggle3D={() => setShow3DView(!show3DView)}
        show3D={show3DView}
        onShowPresets={() => setShowPresets(true)}
      />

      <div className={`timeline-content ${show3DView ? 'with-3d' : ''}`}>
        {/* Ruler row */}
        <div className="timeline-row">
          <div className="timeline-row-label" style={{ width: LABEL_COLUMN_WIDTH }}>
            <span>ВРЕМЯ</span>
          </div>
          <div className="timeline-row-content">
            <TimelineRuler viewport={store.viewport!} />
          </div>
        </div>

        {/* Metric tracks */}
        <div className="timeline-tracks" ref={trackAreaRef}>
          {visibleTracks.map((track) => (
            <div key={track.id} className="timeline-row" style={{ height: track.height }}>
              <div className="timeline-row-label" style={{ width: LABEL_COLUMN_WIDTH }}>
                <TrackLabel track={track} height={track.height} />
              </div>
              <div className="timeline-row-content">
                <TimelineCanvas
                  track={track}
                  photos={filteredPhotos}
                  viewport={store.viewport!}
                  width={areaWidth}
                  height={track.height}
                  hoverTime={store.hoverTime}
                  selectedPhotoId={store.selectedPhotoId}
                  onPhotoClick={handlePhotoClick}
                />
              </div>
            </div>
          ))}

          {/* Photo track */}
          <div className="timeline-row" style={{ height: 60 }}>
            <div className="timeline-row-label" style={{ width: LABEL_COLUMN_WIDTH }}>
              <span>ФОТО</span>
            </div>
            <div className="timeline-row-content">
              <PhotoTrack
                photos={filteredPhotos}
                viewport={store.viewport!}
                width={areaWidth}
                height={60}
                selectedPhotoId={store.selectedPhotoId}
                pairAId={store.pairAId}
                pairBId={store.pairBId}
                onPhotoClick={(photo) => handlePhotoClick(photo, false)}
              />
            </div>
          </div>

          {/* Anomaly track */}
          <div className="timeline-row" style={{ height: 40 }}>
            <div className="timeline-row-label" style={{ width: LABEL_COLUMN_WIDTH }}>
              <span>АНОМАЛИИ</span>
            </div>
            <div className="timeline-row-content">
              <AnomalyTrack
                anomalies={store.anomalies}
                viewport={store.viewport!}
                height={40}
                activeKinds={store.activeAnomalyKinds}
                onAnomalyClick={handleAnomalyClick}
              />
            </div>
          </div>

          {/* Biological Impossibility track */}
          <div className="timeline-row" style={{ height: 70 }}>
            <div className="timeline-row-label" style={{ width: LABEL_COLUMN_WIDTH }}>
              <span>БИОЛОГИЯ</span>
            </div>
            <div className="timeline-row-content">
              <BiologicalImpossibilityTrack
                photos={filteredPhotos}
                viewport={store.viewport!}
                width={areaWidth}
                height={70}
                onPhotoClick={(photo) => handlePhotoClick(photo, false)}
              />
            </div>
          </div>
        </div>

        {/* Minimap row */}
        <div className="timeline-row">
          <div className="timeline-row-label" style={{ width: LABEL_COLUMN_WIDTH }}>
            <span>МАСШТАБ</span>
          </div>
          <div className="timeline-row-content">
            <TimelineMinimap
              photos={store.photos}
              viewport={store.viewport}
              bounds={store.bounds}
              width={areaWidth}
              onBrush={handleMinimapBrush}
            />
          </div>
        </div>
      </div>

      {/* 3D Viewer Panel */}
      {show3DView && selectedPhoto && (
        <div className="timeline-3d-panel">
          <div className="timeline-3d-header">
            <span>3D МОДЕЛЬ · {selectedPhoto.date ?? 'н/д'}</span>
            <button onClick={() => setShow3DView(false)} aria-label="Закрыть 3D">×</button>
          </div>
          <ModelViewer3D
            photo={selectedPhoto}
            width={300}
            height={280}
          />
        </div>
      )}

      {/* Legend */}
      <div className="timeline-legend">
        <span className="legend-title">ЛЕГЕНДА</span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: 'var(--metric-quality)' }} />
          Качество
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: 'var(--metric-texture)' }} />
          Текстура кожи
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: 'var(--metric-geometry)' }} />
          Геометрия
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: 'var(--metric-anomaly)' }} />
          Различие формы (LDM)
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: 'var(--color-synthetic)' }} />
          Аномалия
        </span>
        <span className="legend-note">Цвет не является выводом о личности</span>
        <span className="legend-shortcuts">
          <kbd>←</kbd><kbd>→</kbd> навигация · 
          <kbd>Tab</kbd> находки · 
          <kbd>+/-</kbd> зум · 
          <kbd>F</kbd> фильтры · 
          <kbd>?</kbd> <button className="legend-help-btn" onClick={() => setShowHelp(true)}>справка</button>
        </span>
      </div>

      {/* Photo Detail Card */}
      {selectedPhoto && (
        <PhotoDetailCard
          photo={selectedPhoto}
          onClose={() => store.setSelectedPhoto(null)}
          onAssignPair={() => store.assignToPair(selectedPhoto.id)}
          onClearPair={store.clearPair}
          pairAId={store.pairAId}
          pairBId={store.pairBId}
        />
      )}

      {/* Filter Panel */}
      {showFilterPanel && (
        <FilterPanel
          onClose={() => setShowFilterPanel(false)}
        />
      )}

      {/* Filter Presets */}
      {showPresets && (
        <FilterPresets
          onClose={() => setShowPresets(false)}
        />
      )}

      {/* Help Overlay */}
      {showHelp && (
        <HelpOverlay
          onClose={() => setShowHelp(false)}
        />
      )}

      {/* Data Logger */}
      <DataLogger data={timelineData} photos={store.photos} />
    </div>
  );
}
