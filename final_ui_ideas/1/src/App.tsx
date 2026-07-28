/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo } from 'react';
import { generateDataset, EVENT_PINS, ERAS } from './data';
import { Photo, EventPin, PoseBucket, Hypothesis } from './types';
import HeaderBar from './components/HeaderBar';
import TimelineTracks from './components/TimelineTracks';
import Filmstrip from './components/Filmstrip';
import LeftPanel from './components/LeftPanel';
import HypothesisLegend from './components/HypothesisLegend';
import ComparisonMode from './components/ComparisonMode';
import { 
  FileText, ShieldAlert, Sparkles, Activity, Layers, Grid, BarChart3, 
  HelpCircle, Info, Download, Trash, Award, Volume2, Calendar, BookOpen, X 
} from 'lucide-react';

export default function App() {
  // 1. Core dataset loaded and maintained in state to allow hiding/deleting
  const rawDataset = useMemo(() => generateDataset(), []);
  const [photos, setPhotos] = useState<Photo[]>(rawDataset);

  // 2. Active selection states
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(rawDataset[0]);
  const [playheadIndex, setPlayheadIndex] = useState<number>(0);
  const [isLeftPanelOpen, setIsLeftPanelOpen] = useState<boolean>(true);
  const [activeEventPin, setActiveEventPin] = useState<EventPin | null>(null);
  const [selectedRange, setSelectedRange] = useState<Photo[]>([rawDataset[0]]);

  // 3. Global Filters and Settings from Header
  const [currentDataset, setDataset] = useState<'main' | 'calibration'>('main');
  const [currentBucket, setBucket] = useState<PoseBucket | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLocked, setIsLocked] = useState<boolean>(true);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [darkMode, setDarkMode] = useState<boolean>(true);
  const [showAnomaliesOnly, setShowAnomaliesOnly] = useState<boolean>(false);
  const [qualityThreshold, setQualityThreshold] = useState<number>(0.0);

  // 4. Custom View Modes (Timeline, Era Comparison Grid, PCA Cluster scatter)
  const [viewMode, setViewMode] = useState<'timeline' | 'eraCompare' | 'clusterView'>('timeline');

  // Multi Doubleclick Fullsize mesh toggle overlay
  const [activeMeshOverlayPhoto, setActiveMeshOverlayPhoto] = useState<Photo | null>(null);

  // 5. Dynamic Filtering Computation
  const filteredPhotos = useMemo(() => {
    return photos.filter((photo) => {
      // Alphanumeric Search by photo_id or year
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesId = photo.id.toLowerCase().includes(query);
        const matchesDate = photo.date.includes(query);
        const matchesYear = String(photo.year).includes(query);
        const matchesFuzzy = photo.fuzzyLabel.toLowerCase().includes(query);
        if (!matchesId && !matchesDate && !matchesYear && !matchesFuzzy) return false;
      }

      // Pose yaw filter
      if (currentBucket !== 'all' && photo.poseBucket !== currentBucket) {
        return false;
      }

      // Quality threshold
      if (photo.quality.overallScore < qualityThreshold) {
        return false;
      }

      // Show Anomalies only
      if (showAnomaliesOnly) {
        const hasFlags = photo.flags.length > 0;
        const isSuspicious = photo.dominantHypothesis !== 'H0';
        if (!hasFlags && !isSuspicious) return false;
      }

      return true;
    });
  }, [photos, searchQuery, currentBucket, qualityThreshold, showAnomaliesOnly]);

  // Bulk Hide poor resolution/bad yaw points Section 13
  const handleBulkHide = () => {
    if (isLocked) {
      alert('Ошибка: Редактирование датасета заблокировано! Разблокируйте замок (LOCKED в левом углу) для выполнения операции.');
      return;
    }
    const confirmed = window.confirm(
      'Скрыть аномально заблюренные и некачественные кадры (Overall Quality < 0.35)?'
    );
    if (confirmed) {
      const updated = photos.map((p) => {
        if (p.quality.overallScore < 0.35) {
          return { ...p, isHidden: true };
        }
        return p;
      });
      setPhotos(updated);
      alert('Операция выполнена. Кадры низкого качества заблокированы в филмстрипе.');
    }
  };

  // Toggle hiding single photo Section 10
  const handleToggleHideSinglePhoto = (photoId: string) => {
    if (isLocked) {
      alert('Редактирование заблокировано! Снимите блокировку LOCKED в левом углу.');
      return;
    }
    const updated = photos.map((p) => {
      if (p.id === photoId) {
        return { ...p, isHidden: !p.isHidden };
      }
      return p;
    });
    setPhotos(updated);
    // Sync current
    const found = updated.find((p) => p.id === photoId);
    if (found) setSelectedPhoto(found);
  };

  // Select photo from timeline adjacent slider or clicking points
  const handleSelectPhoto = (photo: Photo) => {
    setSelectedPhoto(photo);
    // Find index to sync playhead
    const idx = photos.findIndex((p) => p.id === photo.id);
    if (idx !== -1) {
      setPlayheadIndex(idx);
    }
  };

  // Export report generator Section 16
  const handleExportReport = () => {
    const reportData = {
      artifact_version: "2.1.0",
      timestamp: new Date().toISOString(),
      dataset_type: currentDataset,
      total_photos_analyzed: photos.length,
      filtered_subset_count: filteredPhotos.length,
      priors: {
        SAME_PERSON: 0.65,
        COSMETOLOGY: 0.33,
        IDENTITY_SWAP: 0.02
      },
      detected_critical_anomalies: photos.filter((p) => p.flags.includes('TEMPORAL_IMPOSSIBILITY')).map(p => ({
        photo_id: p.id,
        date: p.date,
        bone_score: p.geometry.geometry_score,
        silicone_prob: p.texture.texture_silicone_prob
      })),
      publication_events: EVENT_PINS.map(ep => ({
        label: ep.label,
        source: ep.source,
        description: ep.description
      }))
    };

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(reportData, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `forensic_report_deeputin_${currentDataset}_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // Split selected range for Comparison mode Section 11
  const comparePhotoA = selectedRange[0] || null;
  const comparePhotoB = selectedRange.length > 1 ? selectedRange[selectedRange.length - 1] : null;

  return (
    <div className={`min-h-screen font-sans flex flex-col ${darkMode ? 'bg-[#0d0d0f] text-[#e2e2e8]' : 'bg-[#f4f4f7] text-[#13131a]'}`}>
      
      {/* SECTION 4: HEADER CONTROLS BAR */}
      <HeaderBar
        currentDataset={currentDataset}
        setDataset={setDataset}
        currentBucket={currentBucket}
        setBucket={setBucket}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        isLocked={isLocked}
        setIsLocked={setIsLocked}
        zoomLevel={zoomLevel}
        setZoomLevel={setZoomLevel}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        onExport={handleExportReport}
        onBulkHide={handleBulkHide}
        showAnomaliesOnly={showAnomaliesOnly}
        setShowAnomaliesOnly={setShowAnomaliesOnly}
        qualityThreshold={qualityThreshold}
        setQualityThreshold={setQualityThreshold}
      />

      {/* VIEW MODES SELECTOR UTILITY BAR (Section 13) */}
      <div className="h-[36px] bg-[#111116] border-b border-white/5 px-4 flex items-center justify-between text-[10px] font-mono select-none">
        <div className="flex items-center space-x-2">
          <Layers className="w-3.5 h-3.5 text-[#4f98a3]" />
          <span className="text-white/40 uppercase">ВЫБОР РЕЖИМА АНАЛИЗА:</span>
          
          <div className="flex bg-[#1a1a24] border border-white/10 p-0.5 rounded ml-2">
            <button
              onClick={() => setViewMode('timeline')}
              className={`px-3 py-0.5 rounded flex items-center gap-1.5 transition cursor-pointer ${
                viewMode === 'timeline' 
                  ? 'bg-[#4f98a3]/25 text-[#4f98a3] font-bold border border-[#4f98a3]/30' 
                  : 'text-white/40 hover:text-white'
              }`}
            >
              <Activity className="w-3 h-3" />
              <span>ХРОНОЛОГИЯ (Сюита)</span>
            </button>
            <button
              onClick={() => setViewMode('eraCompare')}
              className={`px-3 py-0.5 rounded flex items-center gap-1.5 transition cursor-pointer ${
                viewMode === 'eraCompare' 
                  ? 'bg-[#e8af34]/25 text-[#e8af34] font-bold border border-[#e8af34]/30' 
                  : 'text-white/40 hover:text-white'
              }`}
            >
              <Grid className="w-3 h-3" />
              <span>МАТРИЦА (Эпохи)</span>
            </button>
            <button
              onClick={() => setViewMode('clusterView')}
              className={`px-3 py-0.5 rounded flex items-center gap-1.5 transition cursor-pointer ${
                viewMode === 'clusterView' 
                  ? 'bg-[#a86fdf]/25 text-[#a86fdf] font-bold border border-[#a86fdf]/30' 
                  : 'text-white/40 hover:text-white'
              }`}
            >
              <BarChart3 className="w-3 h-3" />
              <span>КЛАССИФИКАТОР (Кластеры)</span>
            </button>
          </div>
        </div>

        <div className="flex items-center space-x-3 text-white/50 text-[9px]">
          <span>ПОКАЗАНО: <strong className="text-white">{filteredPhotos.length}</strong> / 1,809 СНИМКОВ</span>
          <span>•</span>
          <span>ВЕЛИЧИНА ПОВЕРКИ: <strong className="text-[#6daa45]">99.1%</strong> ACC</span>
        </div>
      </div>

      {/* CORE WORKSPACE PANEL */}
      <div className="flex-1 flex items-stretch relative overflow-hidden">
        
        {/* VIEW 1: MAIN FORENSIC TIMELINE & TRACKS (Sections 5, 8, 9, 7) */}
        {viewMode === 'timeline' && (
          <div className="flex-1 flex flex-col overflow-y-auto overflow-x-hidden min-w-0">
            
            {/* Upper: Canvas metrics tracks & linear scales */}
            <div className="flex-1 min-h-[400px]">
              <TimelineTracks
                photos={filteredPhotos}
                selectedPhoto={selectedPhoto}
                onSelectPhoto={handleSelectPhoto}
                playheadIndex={playheadIndex}
                setPlayheadIndex={setPlayheadIndex}
                zoomLevel={zoomLevel}
                activeEventPin={activeEventPin}
                setActiveEventPin={setActiveEventPin}
              />
            </div>

            {/* Central: Continuous chronopicture strip list */}
            <Filmstrip
              photos={filteredPhotos}
              selectedPhoto={selectedPhoto}
              onSelectPhoto={handleSelectPhoto}
              playheadIndex={playheadIndex}
              setPlayheadIndex={setPlayheadIndex}
              onDoubleSelectPhoto={(p) => setActiveMeshOverlayPhoto(p)}
              selectedRange={selectedRange}
              setSelectedRange={setSelectedRange}
            />

          </div>
        )}

        {/* VIEW 2: ERA GRID MATRIX COMPARER (Section 13) */}
        {viewMode === 'eraCompare' && (
          <div className="flex-1 p-4 overflow-x-auto select-none bg-black/30 flex gap-4 min-w-0">
            {ERAS.map((era) => {
              // Extract all photos in this specific interval
              const eraPhotos = filteredPhotos.filter(
                (p) => p.date >= era.start && p.date <= era.end
              );

              return (
                <div key={era.id} className="w-[320px] min-w-[280px] bg-[#13131a] border border-white/10 rounded-md p-3 flex flex-col h-full">
                  
                  {/* Era details header */}
                  <div className="border-b border-white/10 pb-2 mb-3">
                    <div className="flex items-center justify-between">
                      <h4 className="font-display font-medium text-xs tracking-wider uppercase text-white" style={{ color: era.color }}>
                        {era.name}
                      </h4>
                      <span className="text-[10px] font-mono text-white/50 bg-white/5 px-1.5 py-0.2 rounded-sm border border-white/5">
                        {eraPhotos.length} фото
                      </span>
                    </div>
                    <p className="text-[8px] font-mono text-white/40 mt-1 leading-relaxed">{era.description}</p>
                  </div>

                  {/* Scrollable list of photos in this ERA */}
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 select-none">
                    {eraPhotos.map((photo) => {
                      const isSelected = selectedPhoto?.id === photo.id;
                      return (
                        <div
                          key={photo.id}
                          onClick={() => handleSelectPhoto(photo)}
                          className={`p-2 bg-black/40 border rounded flex items-center justify-between transition cursor-pointer select-none ${
                            isSelected ? 'border-[#4f98a3] bg-white/5' : 'border-white/5 hover:border-white/20 hover:bg-white/5'
                          }`}
                        >
                          <div className="flex items-center space-x-2">
                            {/* Miniature pose wireframe vector */}
                            <div className="w-8 h-8 rounded-sm bg-white/5 border border-white/5 flex items-center justify-center text-[7px] font-mono">
                              {photo.poseBucket.slice(0, 10)}
                            </div>
                            <div className="font-mono text-[9px]">
                              <p className="font-semibold text-white/80">{photo.id}</p>
                              <p className="text-white/40 text-[8px]">{photo.date}</p>
                            </div>
                          </div>

                          <div className="text-right font-mono text-[9px]">
                            <p className="font-bold text-[#4f98a3]">{photo.geometry.geometry_score.toFixed(2)}σ</p>
                            <span className="text-[7.5px] px-1 bg-white/5 text-white/65 font-bold rounded">
                              {photo.dominantHypothesis}
                            </span>
                          </div>
                        </div>
                      );
                    })}

                    {eraPhotos.length === 0 && (
                      <div className="text-center py-10 text-white/20 text-[9px] font-mono uppercase">
                        Снимки не обнаружены
                      </div>
                    )}
                  </div>

                </div>
              );
            })}
          </div>
        )}

        {/* VIEW 3: PCA COGNITIVE SCATTER PLOT VIEW (Section 13) */}
        {viewMode === 'clusterView' && (
          <div className="flex-1 p-6 flex flex-col min-w-0 bg-[#0c0c10]">
            
            {/* Headline explanations */}
            <div className="mb-4 bg-[#13131a] border border-white/10 p-3 rounded font-mono text-[10px] leading-relaxed select-none">
              <span className="text-[#a86fdf] font-bold uppercase tracking-widest block mb-1">Ортонормированная PCA Проекция Снимков (ID-Vector Scatter)</span>
              Когнитивная кластеризация 1,809 снимков лица по двум главным компонентам двумерного пространства признаков. Каждый вектор отражает остеологию черепа. Наглядно выявляет обособление независимых личностных популяций. Клик на точку открывает детальный разбор в левой панели.
            </div>

            {/* Interactive 2D scatter coordinates canvas mapped with SVG */}
            <div className="flex-1 bg-black/50 border border-white/15 rounded relative overflow-hidden flex items-center justify-center p-4">
              
              <svg className="w-full h-full min-h-[400px]" viewBox="0 0 1000 600">
                {/* Axes lines with metrics */}
                <line x1="100" y1="500" x2="900" y2="500" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
                <line x1="100" y1="100" x2="100" y2="500" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
                
                {/* Labels axis */}
                <text x="500" y="540" fill="rgba(255,255,255,0.4)" fontSize="9" textAnchor="middle" fontFamily="monospace">ГЛАВНАЯ КОМПОНЕНТА 1 (ОСТЕОЛОГИЯ ЛИЦА PC1)</text>
                <text x="60" y="300" fill="rgba(255,255,255,0.4)" fontSize="9" textAnchor="middle" transform="rotate(-90 60 300)" fontFamily="monospace">ГЛАВНАЯ КОМПОНЕНТА 2 (ТЕКСТУРА PC2)</text>

                {/* Plot the photos coordinates dynamically */}
                {filteredPhotos.map((p, idx) => {
                  // Fictional deterministic PC mapping based on actual bone scores
                  let x = 150 + (p.geometry.orbit_depth + 2) * 110;
                  let y = 450 - (p.texture.texture_silicone_prob * 300 + p.geometry.chin_projection * 30);

                  // Constraints checks
                  x = Math.max(120, Math.min(x, 880));
                  y = Math.max(120, Math.min(y, 480));

                  const isSelected = selectedPhoto?.id === p.id;

                  let dotColor = '#6daa45'; // green (H0)
                  if (p.dominantHypothesis === 'H1') dotColor = '#fdab43'; // orange (H1)
                  if (p.dominantHypothesis === 'H2') dotColor = '#dd6974'; // red-pink (H2)

                  return (
                    <circle
                      key={p.id}
                      cx={x}
                      cy={y}
                      r={isSelected ? 6 : 3}
                      fill={dotColor}
                      stroke={isSelected ? '#ffffff' : 'none'}
                      strokeWidth={isSelected ? 1.5 : 0}
                      className="cursor-pointer transition-all hover:r-8 hover:opacity-100 opacity-70"
                      onClick={() => handleSelectPhoto(p)}
                    >
                      <title>{`${p.id} (${p.date})\nFuzzy Label: ${p.fuzzyLabel}\nH0:${p.posteriors.H0} H1:${p.posteriors.H1} H2:${p.posteriors.H2}`}</title>
                    </circle>
                  );
                })}

                {/* Sub-areas coordinates circles labels */}
                <rect x="180" y="380" width="180" height="80" rx="3" fill="rgba(109,170,69,0.04)" stroke="rgba(109,170,69,0.2)" strokeWidth="1" strokeDasharray="2,2" />
                <text x="270" y="405" fill="#6daa45" fontSize="8" textAnchor="middle" fontFamily="monospace" fontWeight="bold">ЭТАЛОННЫЙ КЛАСС (H0)</text>
                <text x="270" y="420" fill="rgba(255,255,255,0.4)" fontSize="7" textAnchor="middle" fontFamily="monospace">Период: 1999 - 2011</text>

                <rect x="620" y="150" width="220" height="90" rx="3" fill="rgba(168,111,223,0.04)" stroke="rgba(168,111,223,0.2)" strokeWidth="1" strokeDasharray="2,2" />
                <text x="730" y="175" fill="#a86fdf" fontSize="8" textAnchor="middle" fontFamily="monospace" fontWeight="bold">ЭПОХА АНОМАЛИЙ (H2)</text>
                <text x="730" y="190" fill="rgba(255,255,255,0.4)" fontSize="7" textAnchor="middle" fontFamily="monospace">Период: 2023 - 2026</text>
              </svg>

            </div>
          </div>
        )}

        {/* SECTION 10: LEFT DETAILS sliding inspect panel */}
        <LeftPanel
          photo={selectedPhoto}
          isOpen={isLeftPanelOpen}
          onClose={() => setIsLeftPanelOpen(false)}
          onToggleHidePhoto={handleToggleHideSinglePhoto}
          onSelectAdjacentPhoto={handleSelectPhoto}
          allPhotos={photos}
        />

        {/* Side bar dock switcher if left panel has been closed */}
        {!isLeftPanelOpen && (
          <div className="w-[44px] bg-[#0c0c10] border-l border-white/5 flex flex-col items-center py-4 space-y-4">
            <button
              onClick={() => setIsLeftPanelOpen(true)}
              className="p-2 text-white/50 hover:text-white hover:bg-white/5 rounded transition cursor-pointer"
              title="Развернуть боковую панель"
            >
              <Activity className="w-5 h-5 text-[#4f98a3]" />
            </button>
            <span className="text-[7.5px] font-mono text-white/35 origin-center rotate-90 whitespace-nowrap pt-8 uppercase tracking-widest leading-none">
              ИНСПЕКТОР ПОДРОБНОСТЕЙ
            </span>
          </div>
        )}

      </div>

      {/* HISTORICAL PUBLIC EXCERPTS SOURCES BAR DOCK (Section 15) */}
      {activeEventPin && (
        <div className="bg-[#1a1a24] border-t border-white/10 p-3 flex justify-between items-start font-mono text-[9px] select-none text-white animate-in slide-in-from-bottom duration-200 shrink-0">
          <div className="flex items-start space-x-2 w-full max-w-[90%]">
            <div className="bg-[#e8af34]/20 p-1 rounded-sm border border-[#e8af34]/40 mt-0.5 text-glow-yellow shrink-0">
              <BookOpen className="w-4 h-4 text-[#e8af34]" />
            </div>
            <div>
              <p className="font-bold text-white text-[10px] tracking-wider uppercase flex items-center gap-2">
                <span>АРХИВНЫЙ ИСТОЧНИК: {activeEventPin.label}</span>
                <span className="text-white/40 text-[8px]">({activeEventPin.date})</span>
              </p>
              <p className="text-white/50 text-[8px] uppercase mt-0.5">Классификация СМИ: {activeEventPin.source} · ВЕРДИКТ: НАРОДНАЯ КАТЕГОРИЗАЦИЯ (НЕ НАУЧНАЯ)</p>
              <p className="text-white/95 text-[10.5px] italic mt-1 pb-1 leading-relaxed">
                "{activeEventPin.description}"
              </p>
            </div>
          </div>
          <button
            onClick={() => setActiveEventPin(null)}
            className="text-white/40 hover:text-white hover:bg-white/5 rounded p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* SECTION 11: SPLIT COMPARISON MODE DRAWER PANEL */}
      <ComparisonMode
        photoA={comparePhotoA}
        photoB={comparePhotoB}
        onClear={() => {
          setSelectedRange([rawDataset[0]]);
        }}
      />

      {/* SECTION 12: HYPOTHESIS OVERLAY FLOAT BLOCK */}
      <HypothesisLegend />

      {/* DOUBLE CLICK FULLSCREEN BIOMETRIC WIREFRAME INTERACTIVE MODAL OVERLAY */}
      {activeMeshOverlayPhoto && (
        <div 
          className="fixed inset-0 bg-black/95 backdrop-blur z-50 flex flex-col items-center justify-center p-6"
          onClick={() => setActiveMeshOverlayPhoto(null)}
        >
          <div 
            className="w-full max-w-[640px] bg-[#13131a] border border-white/15 rounded-md p-5 flex flex-col font-mono text-white relative shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center border-b border-white/10 pb-2 mb-4 select-none">
              <span className="font-display font-bold text-xs tracking-wider text-[#4f98a3] flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-[#4f98a3] animate-pulse" />
                <span>3D-СЕТКА АНАТОМИЧЕСКИХ ТОЧЕК ЛИЦА (ПРОЕКЦИЯ ПО 3DDFA-V3)</span>
              </span>
              <button
                onClick={() => setActiveMeshOverlayPhoto(null)}
                className="text-white/40 hover:text-white p-1 hover:bg-white/5 rounded cursor-pointer transition text-[9px] font-bold"
              >
                [ESC ЗАКРЫТЬ]
              </button>
            </div>

            {/* Central glowing SVG drawing on high fidelity */}
            <div className="aspect-square w-full max-w-[400px] mx-auto bg-black/50 border border-white/5 rounded-full flex items-center justify-center p-8 relative overflow-hidden my-3">
              <svg className="absolute inset-0 w-full h-full text-indigo-500" viewBox="0 0 100 100">
                {/* Simulated anatomical wires */}
                <path
                  d="M 50,15 L 36,44 M 50,15 L 64,44 M 36,44 L 64,44 M 36,44 L 50,48 M 64,44 L 50,48 M 50,48 L 50,73 M 36,44 L 24,66 L 50,92 L 76,66 L 64,44"
                  fill="none"
                  stroke="rgba(79, 152, 163, 0.3)"
                  strokeWidth="0.8"
                />
                
                {/* 106 Wire points plotted */}
                {((activeMeshOverlayPhoto as any).meshVertices as [number, number, string][]).map((pt, i) => {
                  const isChin = pt[2] === 'chin';
                  const isOrbit = pt[2].includes('orbit');
                  return (
                    <circle
                      key={i}
                      cx={pt[0]}
                      cy={pt[1]}
                      r={isChin || isOrbit ? 1.5 : 1.0}
                      fill={isChin ? '#ff3b30' : isOrbit ? '#e8af34' : '#4f98a3'}
                    />
                  );
                })}
              </svg>

              <div className="absolute bottom-4 bg-[#0d0d0f] border border-[#ff3b30]/30 px-3 py-1 rounded text-[9px] font-semibold text-[#ff3b30] flex items-center gap-1.5 critical-pulse leading-none">
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>{(activeMeshOverlayPhoto.confidence * 100).toFixed(0)}% ОСТЕОЛОГИЧЕСКОЕ СОВПАДЕНИЕ НЕДОСТАТОЧНО ДЛЯ H0</span>
              </div>
            </div>

            <div className="border-t border-white/10 pt-3 flex justify-between text-[9px] text-white/50 select-none">
              <p>ФАЙЛ ДАННЫХ СНИМКА: FSC_1809_MAPPED_3D.JSON</p>
              <p>ЗОНЫ: 21 АКТИВНАЯ · 106 АНАТОМИЧЕСКИХ ТОЧЕК</p>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
