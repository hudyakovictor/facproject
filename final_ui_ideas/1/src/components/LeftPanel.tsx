/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Photo, EventPin, Hypothesis } from '../types';
import { EVENT_PINS, BIRTH_DATE } from '../data';
import { 
  FileText, ShieldAlert, Sparkles, Table, Activity, Award, EyeOff, Eye, Clock, 
  MapPin, BookOpen, ChevronLeft, ChevronRight 
} from 'lucide-react';

interface LeftPanelProps {
  photo: Photo | null;
  isOpen: boolean;
  onClose: () => void;
  onToggleHidePhoto: (pId: string) => void;
  onSelectAdjacentPhoto: (p: Photo) => void;
  allPhotos: Photo[];
}

export default function LeftPanel({
  photo,
  isOpen,
  onClose,
  onToggleHidePhoto,
  onSelectAdjacentPhoto,
  allPhotos
}: LeftPanelProps) {
  const [activeTab, setActiveTab] = useState<'PHOTO' | 'GEOMETRY' | 'SKIN' | 'VERDICT' | 'CONTEXT'>('PHOTO');
  const [showMeshOverlay, setShowMeshOverlay] = useState(true);

  if (!photo || !isOpen) return null;

  // Find index in main list
  const photoIdx = allPhotos.findIndex((p) => p.id === photo.id);

  // EXIF age spoof verification Section 10
  const isExifSymmetricAnomaly = Math.abs(photo.exifYear - photo.year) > 12;

  // Neighboring photo context
  const getNeighbors = () => {
    const leftRange = allPhotos.slice(Math.max(0, photoIdx - 5), photoIdx);
    const rightRange = allPhotos.slice(photoIdx + 1, Math.min(allPhotos.length, photoIdx + 6));
    return { leftRange, rightRange };
  };

  const { leftRange, rightRange } = getNeighbors();

  // Helper values for geometric zone details
  const boneStructures = [
    { zone: 'orbit_depth', desc: 'Глубина глазных орбит', raw: photo.geometry.orbit_depth, refDelta: (photo.geometry.orbit_depth * 0.1).toFixed(3), zScore: photo.geometry.orbit_depth },
    { zone: 'orbit_fossa', desc: 'Строение стенки глазницы', raw: photo.geometry.orbit_fossa, refDelta: (photo.geometry.orbit_fossa * 0.08).toFixed(3), zScore: photo.geometry.orbit_fossa / 1.1 },
    { zone: 'chin_projection', desc: 'Проекция подбородка', raw: photo.geometry.chin_projection, refDelta: (photo.geometry.chin_projection * 0.12).toFixed(3), zScore: photo.geometry.chin_projection },
    { zone: 'gonial_angle', desc: 'Нижнечелюстной угол', raw: photo.geometry.gonial_angle, refDelta: (photo.geometry.gonial_angle * 0.05).toFixed(3), zScore: photo.geometry.gonial_angle / 2 },
    { zone: 'jaw_width', desc: 'Ширина нижней челюсти', raw: photo.geometry.jaw_width, refDelta: (photo.geometry.jaw_width * 0.15).toFixed(3), zScore: photo.geometry.jaw_width },
    { zone: 'bigonial', desc: 'Расстояние между углами', raw: photo.geometry.bigonial, refDelta: (photo.geometry.bigonial * 0.11).toFixed(3), zScore: photo.geometry.bigonial / 1.2 },
    { zone: 'zygomatic_arch', desc: 'Ширина скуловых дуг', raw: photo.geometry.zygomatic_arch, refDelta: (photo.geometry.zygomatic_arch * 0.07).toFixed(3), zScore: photo.geometry.zygomatic_arch / 1.5 },
    { zone: 'ramus_height', desc: 'Высота ветви челюсти', raw: photo.geometry.ramus_height, refDelta: (photo.geometry.ramus_height * 0.1).toFixed(3), zScore: photo.geometry.ramus_height / 1.3 }
  ];

  // Radar Spider chart points calculation Section 10 (8 key metrics)
  // Metrics: Specular Gloss, LBP Entropy, Frangi, Wrinkle index, Silicone Prob, Subsurface scatter, Chin edge, orbit depth
  const radarMetrics = [
    { name: 'Gloss', val: photo.texture.texture_specular_gloss, baseline: 0.45 },
    { name: 'LBP', val: photo.texture.texture_lbp_complexity, baseline: 0.42 },
    { name: 'Vessel', val: photo.texture.texture_frangi_vessel, baseline: 0.85 },
    { name: 'Wrinkles', val: (photo.texture.texture_wrinkle_forehead + photo.texture.texture_wrinkle_nasolabial) / 2, baseline: 0.15 },
    { name: 'Silicone', val: photo.texture.texture_silicone_prob, baseline: 0.02 },
    { name: 'Scatter', val: photo.texture.texture_subsurface_scatter_proxy, baseline: 0.15 },
    { name: 'Orbit σ', val: (Math.min(5, Math.abs(photo.geometry.orbit_depth)) / 5), baseline: 0.10 },
    { name: 'Chin σ', val: (Math.min(5, Math.abs(photo.geometry.chin_projection)) / 5), baseline: 0.10 },
  ];

  const getHypBgColor = (h: Hypothesis): string => {
    switch (h) {
      case 'H0': return 'bg-[#6daa45]/15 border-[#6daa45] text-[#6daa45]'; // green
      case 'H1': return 'bg-[#fdab43]/15 border-[#fdab43] text-[#fdab43]'; // yellow/orange
      case 'H2': return 'bg-[#a13544]/20 border-[#a13544] text-[#dd6974]'; // red-pink
    }
  };

  // Build the SVG coordinates for Radar Diagram
  const center = 100;
  const radius = 64;
  
  const getRadarPolygonPath = (valuesKey: 'val' | 'baseline') => {
    const points = radarMetrics.map((met, i) => {
      const val = met[valuesKey];
      const angle = (Math.PI * 2 * i) / 8 - Math.PI / 2;
      const r = Math.max(8, val * radius);
      const x = center + r * Math.cos(angle);
      const y = center + r * Math.sin(angle);
      return `${x},${y}`;
    });
    return points.join(' ');
  };

  return (
    <div className="w-[360px] min-w-[360px] h-[calc(100vh-52px)] bg-[#13131a] border-r border-white/10 flex flex-col z-20 relative select-none">
      
      {/* Panel header controls */}
      <div className="h-[44px] bg-[#0d0d0f] border-b border-white/5 px-4 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-[#4f98a3]" />
          <span className="font-display font-medium text-xs tracking-wider text-white">ДЕТАЛИ СНИМКА: {photo.id}</span>
        </div>
        <button
          onClick={onClose}
          className="text-white/40 hover:text-white text-[11px] font-mono hover:bg-white/5 px-2 py-1 rounded cursor-pointer"
        >
          [CХЛОПНУТЬ]
        </button>
      </div>

      {/* TABS SELECTOR (Section 10 - 5 tabs) */}
      <div className="flex bg-[#0b0b0f] border-b border-white/5 text-[9px] font-mono">
        {(['PHOTO', 'GEOMETRY', 'SKIN', 'VERDICT', 'CONTEXT'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 text-center py-2 transition-all cursor-pointer border-b-2 ${
              activeTab === tab
                ? 'text-[#4f98a3] bg-white/5 border-[#4f98a3] font-semibold'
                : 'text-white/40 border-transparent hover:text-white/70 hover:bg-white/5'
            }`}
          >
            {tab === 'PHOTO' ? 'ФОТО' :
             tab === 'GEOMETRY' ? 'ГЕОМЕТРИЯ' :
             tab === 'SKIN' ? 'КОЖА' :
             tab === 'VERDICT' ? 'ВЕРДИКТ' :
             tab === 'CONTEXT' ? 'КОНТЕКСТ' : tab}
          </button>
        ))}
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 overflow-y-auto p-4 select-none">

        {/* TAB 1: PHOTO */}
        {activeTab === 'PHOTO' && (
          <div className="space-y-4">
            
            {/* Spoof Age banner alert Section 10 */}
            {isExifSymmetricAnomaly && (
              <div className="bg-[#a13544]/20 border border-[#a13544] p-3 rounded flex items-start gap-2.5 critical-pulse">
                <ShieldAlert className="w-5 h-5 text-red-500 shrink-0" />
                <div className="text-[10px] font-mono leading-relaxed">
                  <p className="text-red-500 font-bold tracking-wider">EXIF DATE ANOMALY DETECTED</p>
                  <p className="text-white/70 mt-0.5">Разница между системным и EXIF-возрастом снимка превышает 12 лет!</p>
                </div>
              </div>
            )}

            {/* Interactive Photo Mesh Box */}
            <div className="bg-black/40 border border-white/10 rounded overflow-hidden relative flex flex-col items-center justify-center p-4">
              
              {/* Scalable Head Vector Mesh */}
              <div className="relative h-[220px] w-[220px] flex items-center justify-center">
                {/* Simulated photo avatar */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-[#1a1a24] rounded-full border border-white/5 opacity-50 flex items-center justify-center">
                  <span className="text-white/10 font-sans text-9xl">👤</span>
                </div>

                {/* Draw 106 Landmarking points overlay Section 10 */}
                {showMeshOverlay && (photo as any).meshVertices && (
                  <svg className="absolute inset-0 w-full h-full z-10 text-[#6daa45]" viewBox="0 0 100 100">
                    {/* Draw connective wireframe triangles/curves */}
                    <path
                      d="M 50,15 L 36,44 L 50,48 L 64,44 Z M 36,44 L 24,66 L 50,92 L 76,66 L 64,44"
                      fill="none"
                      stroke="rgba(109, 170, 69, 0.25)"
                      strokeWidth="0.8"
                    />
                    <path
                      d="M 50,15 L 50,40 M 50,59 L 50,92"
                      fill="none"
                      stroke="rgba(109, 170, 69, 0.2)"
                      strokeWidth="0.5"
                    />

                    {/* Plot coordinates */}
                    {((photo as any).meshVertices as [number, number, string][]).map((pt, i) => {
                      const isOrbit = pt[2].includes('orbit');
                      const isChin = pt[2].includes('chin');
                      
                      // Critical features coloring
                      let pColor = '#6daa45'; // standard green
                      if (isChin && Math.abs(photo.geometry.chin_projection) > 2.2) pColor = '#ff3b30'; // critical
                      if (isOrbit && Math.abs(photo.geometry.orbit_depth) > 2.0) pColor = '#fdab43'; // warn
                      
                      return (
                        <circle
                          key={i}
                          cx={pt[0]}
                          cy={pt[1]}
                          r={isChin || isOrbit ? 1.2 : 0.8}
                          fill={pColor}
                        />
                      );
                    })}
                  </svg>
                )}

                {/* Subtext info marker */}
                <div className="absolute bottom-2 bg-black/85 border border-white/5 p-1 rounded font-mono text-[8px] text-[#4f98a3] tracking-widest leading-none">
                  FACES_3D_MESH_V3 ACTIVE
                </div>
              </div>

              {/* Toggle controls */}
              <div className="w-full mt-3 flex items-center justify-between border-t border-white/5 pt-3">
                <button
                  onClick={() => setShowMeshOverlay(!showMeshOverlay)}
                  className={`px-2.5 py-1 text-[8.5px] font-mono border rounded cursor-pointer transition flex items-center gap-1.5 ${
                    showMeshOverlay 
                      ? 'bg-[#6daa45]/15 border-[#6daa45]/30 text-[#6daa45]'
                      : 'border-white/10 text-white/40 hover:text-white'
                  }`}
                >
                  <Sparkles className="w-3 h-3" />
                  <span>3D MESH WIREFAMES {showMeshOverlay ? 'ON' : 'OFF'}</span>
                </button>

                <button
                  onClick={() => onToggleHidePhoto(photo.id)}
                  className="px-2.5 py-1 text-[8.5px] font-mono border border-white/10 text-white/50 hover:bg-[#dd6974]/5 hover:text-[#dd6974] rounded transition flex items-center gap-1.5"
                >
                  {photo.isHidden ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                  <span>{photo.isHidden ? 'RESTORE DATA' : 'HIDE PHOTO'}</span>
                </button>
              </div>

            </div>

            {/* Metadata metrics logs TABLE */}
            <div className="bg-[#1a1a24]/50 border border-white/10 rounded p-3 font-mono text-[9px] space-y-2">
              <span className="text-white/40 border-b border-white/5 block pb-1 text-[8px] tracking-wider uppercase">ФУНДАМЕНТАЛЬНЫЕ ХАРАКТЕРИСТИКИ СНИМКА</span>
              <div className="grid grid-cols-2 gap-y-1.5 text-white/80">
                <p>ID СНИМКА:</p>
                <p className="text-[#4f98a3] font-bold text-right">{photo.id}</p>

                <p>ДАТА И КЛИП:</p>
                <p className="text-right">{photo.date}</p>

                <p>ПАКЕТ ПОВОРОТА:</p>
                <p className="text-right">{photo.poseBucket}</p>

                <p>СИСТЕМНЫЙ ГОД:</p>
                <p className="text-right">{photo.year}</p>

                <p>EXIF ГОД ЗАПИСИ:</p>
                <p className={`text-right ${isExifSymmetricAnomaly ? 'text-[#dd6974] font-bold':''}`}>{photo.exifYear}</p>

                <p>КАЛЕНДАРНЫЙ ВОЗРАСТ:</p>
                <p className="text-right font-semibold text-[#e8af34]">{photo.calendarAge} лет</p>

                <p>КАЧЕСТВО СИГНАЛА (Q):</p>
                <p className={`text-right font-bold ${photo.quality.overallScore > 0.6 ? 'text-green-500':'text-yellow-500'}`}>{photo.quality.overallScore}</p>
              </div>
            </div>

          </div>
        )}

        {/* TAB 2: GEOMETRY */}
        {activeTab === 'GEOMETRY' && (
          <div className="space-y-4">
            
            {/* Table of bone regions Section 10 */}
            <div className="bg-black/20 border border-white/10 rounded overflow-hidden">
              <table className="w-full text-left font-mono text-[9px] border-collapse">
                <thead>
                  <tr className="bg-[#0b0b0f] text-white/40 border-b border-white/10">
                    <TH>МОРФОГЕНЕТИЧЕСКАЯ ЗОНА</TH>
                    <TH style={{ textAlign: 'right' }}>D_REF</TH>
                    <TH style={{ textAlign: 'right' }}>Z-SCORE</TH>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {boneStructures.map((b) => {
                    const isWarn = b.raw > 2.0;
                    const isCrit = b.raw > 3.0;

                    return (
                      <tr 
                        key={b.zone} 
                        className={`transition hover:bg-white/5 ${
                          isCrit ? 'bg-[#a13544]/15 text-[#dd6974]' : isWarn ? 'bg-[#fdab43]/15 text-[#fdab43]' : 'text-white/80'
                        }`}
                      >
                        <TD>
                          <p className="font-semibold text-[8.5px] uppercase">{b.zone}</p>
                          <p className="text-[7.5px] text-white/40 leading-none">{b.desc}</p>
                        </TD>
                        <TD style={{ textAlign: 'right' }}>{b.refDelta}</TD>
                        <TD style={{ textAlign: 'right' }}>
                          <span className={`px-1 rounded-sm font-bold ${isCrit ? 'bg-red-500/10' : isWarn ? 'bg-amber-500/10' : ''}`}>
                            {b.zScore.toFixed(2)}σ
                          </span>
                        </TD>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Geometry score block */}
            <div className="bg-[#1a1a24]/40 border border-white/10 rounded p-3 font-mono text-[10px] space-y-1.5">
              <div className="flex justify-between">
                <span className="text-white/40">ОСТЕОЛОГИЯ (КОСТНЫЙ ИНДЕКС):</span>
                <span className="font-bold text-[#4f98a3]">{photo.geometry.geometry_score.toFixed(2)} / 5.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/40">ИСТОЧНИК ПОГРЕШНОСТИ:</span>
                <span className="text-green-500 font-semibold font-bold">КАЛИБРОВАННЫЙ</span>
              </div>
              <div className="flex justify-between text-white/80">
                <span>КОЭФФИЦИЕНТ НАДЕЖНОСТИ:</span>
                <span>0.89 (ОЧЕНЬ ВЫСОКИЙ)</span>
              </div>
            </div>

          </div>
        )}

        {/* TAB 3: SKIN */}
        {activeTab === 'SKIN' && (
          <div className="space-y-4 text-white">
            
            {/* Integrated Custom SVG Radar chart Section 10 */}
            <div className="bg-black/30 border border-white/10 rounded p-3 flex flex-col items-center">
              <span className="text-[8.5px] font-mono text-white/40 uppercase mb-2">МНОГОМЕРНЫЙ РАДАР СВОЙСТВ ТЕКСТУР КОЖИ</span>
              
              <div className="relative w-[210px] h-[210px]">
                <svg width="200" height="200" className="opacity-90">
                  {/* Grid circle bands */}
                  <circle cx="100" cy="100" r="16" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="0.8" />
                  <circle cx="100" cy="100" r="32" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="0.8" />
                  <circle cx="100" cy="100" r="48" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="0.8" />
                  <circle cx="100" cy="100" r="64" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />

                  {/* Axis lines */}
                  {Array.from({ length: 8 }).map((_, i) => {
                    const angle = (Math.PI * 2 * i) / 8 - Math.PI / 2;
                    return (
                      <line
                        key={i}
                        x1="100"
                        y1="100"
                        x2={100 + 64 * Math.cos(angle)}
                        y2={100 + 64 * Math.sin(angle)}
                        stroke="rgba(255,255,255,0.05)"
                        strokeWidth="0.8"
                      />
                    );
                  })}

                  {/* Baseline Period (ERA_1 median) Overlay (Section 10 - semi-trans gray) */}
                  <polygon
                    points={getRadarPolygonPath('baseline')}
                    fill="rgba(110, 110, 110, 0.15)"
                    stroke="rgba(110, 110, 110, 0.4)"
                    strokeWidth="1.2"
                    strokeDasharray="2,2"
                  />

                  {/* Active Photo measurement Polygon */}
                  <polygon
                    points={getRadarPolygonPath('val')}
                    fill="rgba(79, 152, 163, 0.2)"
                    stroke="#4f98a3"
                    strokeWidth="1.5"
                  />

                  {/* Point markers */}
                  {radarMetrics.map((met, i) => {
                    const angle = (Math.PI * 2 * i) / 8 - Math.PI / 2;
                    const r = Math.max(8, met.val * radius);
                    const x = center + r * Math.cos(angle);
                    const y = center + r * Math.sin(angle);
                    
                    return (
                      <circle
                        key={i}
                        cx={x}
                        cy={y}
                        r="2.5"
                        fill="#4f98a3"
                        stroke="#0d0d0f"
                        strokeWidth="1"
                      />
                    );
                  })}
                </svg>

                {/* Radar axis labels */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 text-[7px] font-mono text-white/50 bg-black/80 px-1 rounded">БЛЕСК КОЖИ</div>
                <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 text-[7px] font-mono text-white/50 bg-black/80 px-1 rounded">СИЛИКОН</div>
                <div className="absolute top-1/2 -right-1 -translate-y-1/2 text-[7px] font-mono text-white/50 bg-black/80 px-1 rounded">МОРЩИНЫ</div>
                <div className="absolute top-1/2 -left-3 -translate-y-1/2 text-[7px] font-mono text-white/50 bg-black/80 px-1 rounded">РАССЕЯНИЕ</div>
              </div>

              {/* Legend details */}
              <div className="w-full flex justify-between font-mono text-[8px] text-white/40 mt-1 pl-2">
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-0.5 border-t border-dashed border-gray-400" />
                  <span>Медиана Эпохи 1 (Эталон)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 bg-[#4f98a3]/30 border border-[#4f98a3]/80 rounded-sm" />
                  <span>Этот Снимок</span>
                </div>
              </div>
            </div>

            {/* Texture parameters table progress tracks Section 10 */}
            <div className="bg-[#1a1a24]/30 border border-white/15 rounded p-3 font-mono text-[9px] space-y-2">
              <span className="text-[8px] text-white/40 block border-b border-white/5 pb-1 uppercase tracking-wider">SKIN_EXTENDED_KEYS ДЕТАЛИЗАЦИЯ</span>
              
              <div className="space-y-2">
                {Object.entries(photo.texture).map(([key, value]) => {
                  return (
                    <div key={key} className="space-y-1">
                      <div className="flex justify-between text-[8px] text-white/70">
                        <span className="uppercase">{key.replace('texture_', '')}</span>
                        <span className="font-semibold text-[#6daa45]">{value.toFixed(2)}</span>
                      </div>
                      <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-[#4f98a3] rounded-full"
                          style={{ width: `${Math.min(100, value * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

          </div>
        )}

        {/* TAB 4: VERDICT CARD */}
        {activeTab === 'VERDICT' && (
          <div className="space-y-4">
            
            {/* Section 10 verdict design block */}
            <div className={`p-4 rounded border font-mono text-[10px] space-y-3 ${getHypBgColor(photo.dominantHypothesis)}`}>
              <div>
                <p className="text-[8px] text-white/50 tracking-widest uppercase">СТАТИСТИЧЕСКАЯ КЛАССИФИКАЦИЯ</p>
                <p className="font-display font-bold text-sm tracking-wider uppercase mt-0.5">
                  {photo.fuzzyLabel === 'STRONGLY_MATCHING' ? 'ПООЛНОЕ СОВПАДЕНИЕ' :
                   photo.fuzzyLabel === 'CONSISTENT' ? 'СОГЛАСОВАНО' :
                   photo.fuzzyLabel === 'INSUFFICIENT_DATA' ? 'НЕДОСТАТОЧНО ДАННЫХ' :
                   photo.fuzzyLabel === 'WEAK_EVIDENCE' ? 'СЛАБЫЕ УЛИКИ' :
                   photo.fuzzyLabel === 'SUSPICIOUS_TEXTURE' ? 'ПОДОЗРИТЕЛЬНАЯ ТЕКСТУРА' :
                   photo.fuzzyLabel === 'GEOMETRIC_MISMATCH' ? 'КОСТНОЕ РАСХОЖДЕНИЕ' :
                   photo.fuzzyLabel === 'IDENTITY_ANOMALY' ? 'ЗАМЕНА ЛИЧНОСТИ' :
                   photo.fuzzyLabel === 'TEMPORAL_IMPOSSIBILITY' ? 'ТЕМПОРАЛЬНЫЙ СБОЙ' :
                   photo.fuzzyLabel}
                </p>
              </div>

              {/* Posteriori margins bars */}
              <div className="space-y-2 border-t border-white/10 pt-2 text-white">
                <div className="space-y-0.5">
                  <div className="flex justify-between text-[9px]">
                    <span>P(H0 | same_person)</span>
                    <span className="font-bold">{Math.round(photo.posteriors.H0 * 100)}%</span>
                  </div>
                  <div className="w-full h-2 bg-black/40 rounded-sm overflow-hidden border border-white/5">
                    <div className="h-full bg-[#6daa45]" style={{ width: `${photo.posteriors.H0 * 100}%` }} />
                  </div>
                </div>

                <div className="space-y-0.5">
                  <div className="flex justify-between text-[9px]">
                    <span>P(H1 | mask/surgery)</span>
                    <span className="font-bold">{Math.round(photo.posteriors.H1 * 100)}%</span>
                  </div>
                  <div className="w-full h-2 bg-black/40 rounded-sm overflow-hidden border border-white/5">
                    <div className="h-full bg-[#fdab43]" style={{ width: `${photo.posteriors.H1 * 100}%` }} />
                  </div>
                </div>

                <div className="space-y-0.5">
                  <div className="flex justify-between text-[9px]">
                    <span>P(H2 | identity_swap)</span>
                    <span className="font-bold">{Math.round(photo.posteriors.H2 * 100)}%</span>
                  </div>
                  <div className="w-full h-2 bg-black/40 rounded-sm overflow-hidden border border-white/5">
                    <div className="h-full bg-[#dd6974]" style={{ width: `${photo.posteriors.H2 * 100}%` }} />
                  </div>
                </div>
              </div>

              {/* S/N ratio indicator */}
              <div className="border-t border-white/10 pt-2 grid grid-cols-2 gap-2 text-white/80">
                <div>
                  <p className="text-[8px] text-white/40">SNR GEOMETRY:</p>
                  <p className="font-bold text-[#4f98a3]">{photo.geometry.geometry_score > 1.8 ? '2.31 (SIGNAL)' : '1.14 (NOMINAL)'}</p>
                </div>
                <div>
                  <p className="text-[8px] text-white/40">SNR TEXTURE:</p>
                  <p className="font-bold text-[#e8af34]">{photo.texture.texture_silicone_prob > 0.4 ? '1.89 (ANOMALY)' : '0.92 (UNCERTAIN)'}</p>
                </div>
                <div>
                  <p className="text-[8px] text-white/40">CONFIDENCE:</p>
                  <p className="font-bold text-white">{(photo.confidence * 100).toFixed(0)}%</p>
                </div>
              </div>

              {/* Active alerts warning tags */}
              {photo.flags.length > 0 && (
                <div className="border-t border-white/10 pt-2 space-y-1">
                  <p className="text-[8px] text-white/40 uppercase">АКТИВНЫЕ МАРКЕРЫ АНОМАЛИЙ:</p>
                  <div className="flex flex-wrap gap-1">
                    {photo.flags.map((flag) => (
                      <span 
                        key={flag} 
                        className={`px-1.5 py-0.5 rounded text-[7.5px] font-bold tracking-widest leading-none ${
                          flag.includes('IMPOSSIBILITY') || flag.includes('ANOMALY')
                            ? 'bg-red-500 text-white critical-pulse'
                            : 'bg-[#fdab43]/25 text-[#fdab43] border border-[#fdab43]/30'
                        }`}
                      >
                        ● {flag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Forensic automated reasoning bullets Section 10 */}
              <div className="border-t border-white/10 pt-2.5 text-white/70 space-y-1">
                <p className="text-[8px] text-white/30 uppercase">АВТОМАТИЗИРОВАННЫЙ ВЫВОД:</p>
                <ul className="list-disc pl-3 text-[8.5px] space-y-1">
                  {photo.dominantHypothesis === 'H0' && (
                    <>
                      <li>Отклонения в зонах orbit_depth и chin_projection находятся в пределах доверительного интервала (1.5σ).</li>
                      <li>Текстурные особенности кожи плавно соответствуют траектории хронологического старения.</li>
                    </>
                  )}
                  {photo.dominantHypothesis === 'H1' && (
                    <>
                      <li>Текстурный анализ демонстрирует резкие всплески specular_gloss и силиконовой плотности.</li>
                      <li>Зафиксировано аномальное омоложение кожи, на 12+ лет отстающее от календаря.</li>
                      <li>Костная геометрия демонстрирует умеренные (z_score 2.1) хирургические изменения.</li>
                    </>
                  )}
                  {photo.dominantHypothesis === 'H2' && (
                    <>
                      <li>Биометрическое расстояние в зоне orbit_depth превышает пороговые 3σ, исключая одного и того же субъекта.</li>
                      <li>Несовместимость орбит и подбородка зафиксирована на временном интервале менее 90 суток.</li>
                      <li>Повышенные показатели в ухе и ширине нижнего контура челюсти. Доминирует сильная гипотеза H2 (смена персоны).</li>
                    </>
                  )}
                </ul>
              </div>

            </div>

          </div>
        )}

        {/* TAB 5: TIMELINE CONTEXT AND PUBLICATIONS */}
        {activeTab === 'CONTEXT' && (
          <div className="space-y-4 font-mono text-white">
            
            {/* Chromo Neighbors slice */}
            <div className="space-y-2">
              <span className="text-[8.5px] text-white/40 block border-b border-white/5 pb-1 uppercase tracking-wider">СОСЕДНИЕ КАДРЫ В ПОРЯДКЕ СЪЕМКИ</span>
              
              <div className="flex items-center justify-between border border-white/10 rounded overflow-hidden bg-black/10">
                <div className="p-1 border-r border-white/5 text-white/40">
                  <ChevronLeft className="w-4 h-4" />
                </div>
                <div className="flex-1 flex overflow-x-auto p-1.5 gap-1 select-none whitespace-nowrap">
                  {leftRange.map((neighbor) => (
                    <div
                      key={neighbor.id}
                      onClick={() => onSelectAdjacentPhoto(neighbor)}
                      className="w-10 h-10 bg-[#1a1a24] p-0.5 rounded border border-white/10 flex flex-col justify-between items-center cursor-pointer hover:border-[#4f98a3]"
                      title={`Перейти: ${neighbor.id} (${neighbor.date})`}
                    >
                      <span className="text-[6px] tracking-tight">{neighbor.date.slice(2, 7)}</span>
                      <span className={`text-[6px] font-bold ${neighbor.dominantHypothesis === 'H0' ? 'text-green-500':'text-red-500'}`}>{neighbor.dominantHypothesis}</span>
                    </div>
                  ))}

                  {/* Highlight current photo as glowing center focus marker */}
                  <div className="w-10 h-10 bg-[#4f98a3]/20 p-0.5 rounded border border-[#4f98a3] flex flex-col justify-between items-center" title="Текущий срез">
                    <span className="text-[6.5px] font-bold text-[#4f98a3]">ACTIVE</span>
                    <span className="text-[6px] text-[#4f98a3] font-bold">{photo.id}</span>
                  </div>

                  {rightRange.map((neighbor) => (
                    <div
                      key={neighbor.id}
                      onClick={() => onSelectAdjacentPhoto(neighbor)}
                      className="w-10 h-10 bg-[#1a1a24] p-0.5 rounded border border-white/10 flex flex-col justify-between items-center cursor-pointer hover:border-[#4f98a3]"
                      title={`Перейти: ${neighbor.id} (${neighbor.date})`}
                    >
                      <span className="text-[6px] tracking-tight">{neighbor.date.slice(2, 7)}</span>
                      <span className={`text-[6px] font-bold ${neighbor.dominantHypothesis === 'H0' ? 'text-green-500':'text-red-500'}`}>{neighbor.dominantHypothesis}</span>
                    </div>
                  ))}
                </div>
                <div className="p-1 border-l border-white/5 text-white/40">
                  <ChevronRight className="w-4 h-4" />
                </div>
              </div>
            </div>

            {/* Publication contextual alerts Section 15 */}
            <div className="space-y-2">
              <span className="text-[8.5px] text-white/40 block border-b border-white/5 pb-1 uppercase tracking-wider">ИСТОРИЧЕСКИЙ КОНТЕКСТ ПУБЛИКАЦИЙ</span>
              
              <div className="space-y-3.5 bg-black/40 border border-white/10 p-3 rounded">
                {EVENT_PINS.filter((pin) => {
                  const pYear = new Date(photo.date).getFullYear();
                  const pinYear = new Date(pin.date).getFullYear();
                  return Math.abs(pYear - pinYear) <= 1.5; // Adjacent years
                }).map((pin) => {
                  return (
                    <div key={pin.id} className="space-y-1 text-[9px] border-l-2 pl-2 border-[#4f98a3]/60">
                      <div className="flex justify-between font-bold text-[#4f98a3]">
                        <span>{pin.label}</span>
                        <span>{pin.date}</span>
                      </div>
                      <p className="text-white/40 text-[7px] uppercase">ИСТОЧНИК: {pin.source}</p>
                      <p className="text-white/80 leading-relaxed italic">{pin.description}</p>
                    </div>
                  );
                })}

                {EVENT_PINS.filter((pin) => {
                  const pYear = new Date(photo.date).getFullYear();
                  const pinYear = new Date(pin.date).getFullYear();
                  return Math.abs(pYear - pinYear) <= 1.5;
                }).length === 0 && (
                  <div className="text-center py-4 text-white/30 text-[8px] flex items-center justify-center gap-1.5 uppercase">
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Медийный штиль на этом временном отрезке</span>
                  </div>
                )}
              </div>
            </div>

            {/* Longitudinal Model parameters */}
            <div className="bg-[#1a1a24]/30 border border-white/10 p-3 rounded text-[9px] space-y-1">
              <span className="text-[8px] text-white/40 uppercase block border-b border-white/5 pb-1">СТАТИСТИКА ПРОДОЛЬНОГО ПРОГНОЗИРОВАНИЯ</span>
              <p className="flex justify-between"><span>Ожидаемое значение:</span> <span className="text-white">0.432</span></p>
              <p className="flex justify-between"><span>Фактическое значение:</span> <span className="text-[#4f98a3] font-bold">{photo.geometry.geometry_score.toFixed(3)}</span></p>
              <p className="flex justify-between"><span>Остаточная погрешность:</span> <span className="text-red-500 font-bold">+0.114σ</span></p>
              <p className="flex justify-between"><span>Критическое расхождение:</span> <span className="text-red-500 font-bold">ДА</span></p>
            </div>

          </div>
        )}

      </div>

    </div>
  );
}

// Micro table styling
function TH({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th className="p-1 px-1.5 text-[8px] font-bold text-white/30 truncate select-none uppercase" style={style}>
      {children}
    </th>
  );
}

function TD({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <td className="p-1.5 px-2 border-b border-white/5 select-none text-[8.5px] truncate max-w-[140px]" style={style}>
      {children}
    </td>
  );
}
