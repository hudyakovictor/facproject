/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Photo, PoseBucket, Hypothesis } from '../types';
import { EyeOff, Eye, Image as ImageIcon, Sparkles, RefreshCw } from 'lucide-react';

interface FilmstripProps {
  photos: Photo[];
  selectedPhoto: Photo | null;
  onSelectPhoto: (p: Photo) => void;
  playheadIndex: number;
  setPlayheadIndex: (idx: number) => void;
  onDoubleSelectPhoto: (p: Photo) => void;
  selectedRange: Photo[];
  setSelectedRange: (range: Photo[]) => void;
}

export default function Filmstrip({
  photos,
  selectedPhoto,
  onSelectPhoto,
  playheadIndex,
  setPlayheadIndex,
  onDoubleSelectPhoto,
  selectedRange,
  setSelectedRange
}: FilmstripProps) {
  const [hoveredPhotoId, setHoveredPhotoId] = useState<string | null>(null);
  const [rangeStart, setRangeStart] = useState<Photo | null>(null);

  // Translate bucket to short code
  const getBucketCode = (b: PoseBucket): string => {
    switch (b) {
      case 'frontal_0': return 'F';
      case 'frontal_yaw15': return 'F15';
      case 'frontal_yaw30': return 'F30';
      case 'profile_L': return 'PL';
      case 'profile_R': return 'PR';
      default: return 'F';
    }
  };

  // Border color based on dominant schema
  const getBorderColor = (h: Hypothesis): string => {
    switch (h) {
      case 'H0': return 'border-[#6daa45]'; // green
      case 'H1': return 'border-[#fdab43]'; // orange
      case 'H2': return 'border-[#dd6974]'; // red-pink
      default: return 'border-[#797876]';
    }
  };

  const getHypLabelColor = (h: Hypothesis): string => {
    switch (h) {
      case 'H0': return 'text-[#6daa45]';
      case 'H1': return 'text-[#fdab43]';
      case 'H2': return 'text-[#dd6974]';
    }
  };

  // Multi-range selection via click and shift-click
  const handlePhotoClick = (photo: Photo, idx: number, e: React.MouseEvent) => {
    setPlayheadIndex(idx);
    onSelectPhoto(photo);

    if (e.shiftKey && rangeStart) {
      // Find start and end indices
      const startIdx = photos.indexOf(rangeStart);
      const endIdx = photos.indexOf(photo);
      
      const newRange = photos.slice(
        Math.min(startIdx, endIdx),
        Math.max(startIdx, endIdx) + 1
      );
      setSelectedRange(newRange);
    } else {
      setRangeStart(photo);
      setSelectedRange([photo]);
    }
  };

  const clearSelection = () => {
    setSelectedRange([]);
    setRangeStart(null);
  };

  // Render a stylized biometric head profile inline
  const VectorHead = ({ bucket, isUdmurt, isVasilich, size = 64 }: { bucket: PoseBucket, isUdmurt: boolean, isVasilich: boolean, size?: number }) => {
    // Generate a geometric human side / frontal wireframe silhouette based on the specific yaw angles
    let rotateY = 0;
    if (bucket === 'frontal_yaw15') rotateY = 15;
    if (bucket === 'frontal_yaw30') rotateY = 30;
    if (bucket === 'profile_L') rotateY = 70;
    if (bucket === 'profile_R') rotateY = -70;

    let chinOffset = isVasilich ? 4 : isUdmurt ? 2.5 : 0;
    let cheekbonesOffset = isVasilich ? 3.5 : isUdmurt ? 2.0 : 0;

    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        className="text-white/30 transition-all group-hover:text-white/50"
        style={{
          transform: `perspective(100px) rotateY(${rotateY}deg)`,
          transformStyle: 'preserve-3d'
        }}
      >
        {/* Silhouette Outline */}
        <path
          d={`M 50,15 
              C 72,15 82,25 82,45 
              C 82,53 ${80 + cheekbonesOffset},60 ${76 + cheekbonesOffset},66 
              C 70,74 64,84 ${50 + chinOffset},92 
              C 36,84 30,74 24,66 
              C 20,60 18,53 18,45 
              C 18,25 28,15 50,15 Z`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeDasharray="1,1"
        />

        {/* Biometric mesh lines */}
        <polyline
          points={`50,15 50,92`}
          fill="none"
          stroke="currentColor"
          strokeWidth="0.8"
          strokeOpacity="0.3"
        />
        <polyline
          points={`18,45 82,45`}
          fill="none"
          stroke="currentColor"
          strokeWidth="0.8"
          strokeOpacity="0.3"
        />
        <polyline
          points={`21,58 79,58`}
          fill="none"
          stroke="currentColor"
          strokeWidth="0.8"
          strokeOpacity="0.3"
        />

        {/* Eyes orbits */}
        <circle cx={bucket === 'profile_L' ? 42 : 36} cy={44} r={6} fill="none" stroke="currentColor" strokeWidth="1" strokeOpacity={bucket === 'profile_R' ? '0.1' : '0.6'} />
        <circle cx={bucket === 'profile_R' ? 58 : 64} cy={44} r={6} fill="none" stroke="currentColor" strokeWidth="1" strokeOpacity={bucket === 'profile_L' ? '0.1' : '0.6'} />

        {/* Nose bridge */}
        <line x1={50} y1={40} x2={50} y2={60} stroke="currentColor" strokeWidth="1" />
        <line x1={44} y1={60} x2={56} y2={60} stroke="currentColor" strokeWidth="1" />

        {/* Mouth */}
        <path d="M 40,73 Q 50,71 60,73" fill="none" stroke="currentColor" strokeWidth="1.2" />

        {/* Dynamic dots for landmarks */}
        <circle cx={50 + chinOffset} cy={92} r={2.5} fill="#4f98a3" />
        <circle cx={24} cy={66} r={2} fill="#e8af34" />
        <circle cx={76} cy={66} r={2} fill="#e8af34" />
      </svg>
    );
  };

  return (
    <div className="bg-[#101015] border-y border-white/10 py-1.5 relative select-none">
      
      {/* Filmstrip Header status / floating selection menu */}
      <div className="flex justify-between items-center px-4 mb-1">
        <div className="flex items-center space-x-2">
          <span className="text-[10px] font-mono text-white/50 tracking-wider">ГЛАВНАЯ ГОРИЗОНТАЛЬНАЯ КИНОЛЕНТА (ХРОНОЛОГИЯ СНИМКОВ)</span>
          <span className="text-[9px] font-mono text-white/30 hidden md:inline">• КЛИК ДЛЯ ВЫБОРА · SHIFT+КЛИК ДЛЯ ИНТЕРВАЛА · ДВОЙНОЙ КЛИК ДЛЯ 3D СЕТКИ</span>
        </div>

        {selectedRange.length > 1 && (
          <div className="flex items-center space-x-2 bg-[#13131a] border border-white/10 px-2.5 py-1 rounded text-[10px] font-mono shadow-xl shrink-0">
            <span className="text-[#fdab43] font-semibold">ВЫДЕЛЕНО: {selectedRange.length} КАДРОВ</span>
            <span className="text-white/30">|</span>
            <button
              onClick={() => {
                // Trigger comparing event
                const first = selectedRange[0];
                const last = selectedRange[selectedRange.length - 1];
                alert(`Аналитический диапазон активирован!\nСравнение серии снимков: ${first.date} — ${last.date}\nМедианные дельты рассчитаны.`);
              }}
              className="px-2 py-0.5 bg-[#4f98a3]/20 text-[#4f98a3] hover:bg-[#4f98a3]/30 border border-[#4f98a3]/40 rounded cursor-pointer text-[9px] transition"
            >
              СРАВНИТЬ ДИАПАЗОН
            </button>
            <button
              onClick={clearSelection}
              className="text-white/40 hover:text-white"
            >
              СБРОС
            </button>
          </div>
        )}
      </div>

      {/* Main photo row */}
      <div 
        className="w-full flex overflow-x-auto overflow-y-hidden px-4 gap-2 pb-1"
        style={{ height: '146px' }}
      >
        {photos.map((photo, index) => {
          const isSelected = selectedPhoto?.id === photo.id;
          const isPlayhead = playheadIndex === index;
          const isRangeSelected = selectedRange.some((p) => p.id === photo.id);
          const isUdmurt = photo.year >= 2015 && photo.year < 2021;
          const isVasilich = photo.year >= 2023;

          return (
            <div
              key={photo.id}
              onClick={(e) => handlePhotoClick(photo, index, e)}
              onDoubleClick={() => onDoubleSelectPhoto(photo)}
              onMouseEnter={() => setHoveredPhotoId(photo.id)}
              onMouseLeave={() => setHoveredPhotoId(null)}
              className={`w-[104px] min-w-[104px] h-[126px] bg-[#1a1a24] rounded border p-1 cursor-pointer transition-all duration-150 flex flex-col justify-between relative group select-none ${
                isPlayhead ? 'ring-2 ring-[#ff3b30] z-20' : ''
              } ${
                isRangeSelected ? 'bg-amber-500/10 border-amber-400' : isSelected ? 'bg-white/5 border-white' : getBorderColor(photo.dominantHypothesis)
              }`}
            >
              {/* Top Row: Date & hidden watermark */}
              <div className="flex justify-between items-center text-[9px] font-mono">
                <span className="text-white/70">{photo.date}</span>
                {photo.flags.includes('EXIF_DATE_ANOMALY') && (
                  <span className="text-[#dd6974] font-bold" title="EXIF ANOMALY detected">EXIF!</span>
                )}
              </div>

              {/* Mid Center: Vector biometrics representation */}
              <div className="flex-1 flex items-center justify-center relative overflow-hidden bg-black/30 rounded-sm my-0.5">
                {photo.isHidden ? (
                  <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center">
                    <EyeOff className="w-5 h-5 text-red-500/80" />
                    <span className="text-[7px] font-mono text-white/50 tracking-widest mt-1">СКРЫТ</span>
                  </div>
                ) : (
                  <>
                    <VectorHead 
                      bucket={photo.poseBucket} 
                      isUdmurt={isUdmurt}
                      isVasilich={isVasilich}
                      size={60} 
                    />
                    {/* Hover wireframe mesh accent overlays */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <div className="flex flex-col items-center space-y-1">
                        <Sparkles className="w-4 h-4 text-[#4f98a3] animate-pulse" />
                        <span className="text-[8px] font-mono text-white/90">ДВОЙНОЙ КЛИК</span>
                        <span className="text-[7px] font-mono text-white/50">ОТКРЫТЬ СЕТКУ</span>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Bottom Row: Score and Bucket labels */}
              <div className="flex justify-between items-end text-[8px] font-mono select-none">
                {/* Quality score indicator Section 7 */}
                <div 
                  className={`px-1 rounded-sm text-black font-semibold shrink-0 text-[8px] ${
                    photo.quality.overallScore > 0.60 
                      ? 'bg-[#6daa45]' // green
                      : photo.quality.overallScore > 0.35 
                        ? 'bg-[#e8af34]' // yellow
                        : 'bg-[#dd6974]' // red
                  }`}
                  title={`Face Quality overall score: ${photo.quality.overallScore}`}
                >
                  Q {(photo.quality.overallScore * 10).toFixed(0)}
                </div>

                <div className="flex items-center space-x-1">
                  <span className={`font-semibold ${getHypLabelColor(photo.dominantHypothesis)}`} title="Dominant hypothesis">
                    {photo.dominantHypothesis}
                  </span>
                  <span className="text-white/40 font-bold bg-white/5 px-1 py-0.2 rounded-sm" title="Angle/Pose Bucket">
                    {getBucketCode(photo.poseBucket)}
                  </span>
                </div>
              </div>

              {/* Critical flags pulse banner overlay */}
              {photo.flags.includes('TEMPORAL_IMPOSSIBILITY') && (
                <div className="absolute top-1/2 left-0 right-0 -translate-y-1/2 bg-[#ff3b30] text-[6.5px] font-bold text-center text-white p-0.5 leading-tight tracking-wider uppercase opacity-85 pointer-events-none text-blink">
                  ВРЕМЕННОЙ БЛОК!
                </div>
              )}

              {/* Hover quick metrics tooltip */}
              {hoveredPhotoId === photo.id && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 bg-black border border-white/20 p-2 rounded text-[8.5px] font-mono shadow-2xl w-[160px] z-50 pointer-events-none">
                  <div className="flex justify-between items-center text-white font-semibold pb-1 mb-1 border-b border-white/10">
                    <span>{photo.id}</span>
                    <span className="text-white/40">{photo.date}</span>
                  </div>
                  <div className="space-y-0.5 text-white/70">
                    <p className="flex justify-between"><span>Ракурс лица:</span> <span className="text-white font-semibold">{photo.poseBucket}</span></p>
                    <p className="flex justify-between"><span>Костный индекс:</span> <span className="text-[#4f98a3] font-semibold">{photo.geometry.geometry_score.toFixed(2)}</span></p>
                    <p className="text-[#dd6974] font-semibold">
                      {photo.fuzzyLabel === 'STRONGLY_MATCHING' ? 'ПОЛНОЕ СОВПАДЕНИЕ' :
                       photo.fuzzyLabel === 'CONSISTENT' ? 'СОГЛАСОВАНО' :
                       photo.fuzzyLabel === 'INSUFFICIENT_DATA' ? 'НЕДОСТАТОЧНО ДАННЫХ' :
                       photo.fuzzyLabel === 'WEAK_EVIDENCE' ? 'СЛАБЫЕ УЛИКИ' :
                       photo.fuzzyLabel === 'SUSPICIOUS_TEXTURE' ? 'ПОДОЗРИТЕЛЬНАЯ ТЕКСТУРА' :
                       photo.fuzzyLabel === 'GEOMETRIC_MISMATCH' ? 'КОСТНОЕ РАСХОЖДЕНИЕ' :
                       photo.fuzzyLabel === 'IDENTITY_ANOMALY' ? 'ЗАМЕНА ЛИЧНОСТИ' :
                       photo.fuzzyLabel === 'TEMPORAL_IMPOSSIBILITY' ? 'ТЕМПОРАЛЬНЫЙ СБОЙ' :
                       photo.fuzzyLabel}
                    </p>
                    <div className="flex space-x-1 border-t border-white/5 pt-1 mt-1 font-bold">
                      <span className="text-[#6daa45]">H0:{Math.round(photo.posteriors.H0*100)}%</span>
                      <span className="text-[#fdab43]">H1:{Math.round(photo.posteriors.H1*100)}%</span>
                      <span className="text-[#dd6974]">H2:{Math.round(photo.posteriors.H2*100)}%</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

    </div>
  );
}
