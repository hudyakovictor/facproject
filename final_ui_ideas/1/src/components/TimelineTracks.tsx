/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useRef, useEffect, useState, useMemo } from 'react';
import { Photo, Era, EventPin, Hypothesis, PoseBucket } from '../types';
import { ERAS, EVENT_PINS } from '../data';
import { ChevronDown, ChevronUp, AlertTriangle, Eye, EyeOff, Info, Sparkles } from 'lucide-react';

// Render a stylized biometric head profile inline inside track row
export function VectorHead({ bucket, isUdmurt, isVasilich, size = 44 }: { bucket: PoseBucket, isUdmurt: boolean, isVasilich: boolean, size?: number }) {
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
      className="text-white/40 transition-all group-hover:text-white/60"
      style={{
        transform: `perspective(100px) rotateY(${rotateY}deg)`,
        transformStyle: 'preserve-3d'
      }}
    >
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
      <polyline
        points="50,15 50,92"
        fill="none"
        stroke="currentColor"
        strokeWidth="0.8"
        strokeOpacity="0.3"
      />
      <polyline
        points="18,45 82,45"
        fill="none"
        stroke="currentColor"
        strokeWidth="0.8"
        strokeOpacity="0.3"
      />
      <circle cx={bucket === 'profile_L' ? 42 : 36} cy={44} r={6} fill="none" stroke="currentColor" strokeWidth="1" strokeOpacity={bucket === 'profile_R' ? '0.1' : '0.6'} />
      <circle cx={bucket === 'profile_R' ? 58 : 64} cy={44} r={6} fill="none" stroke="currentColor" strokeWidth="1" strokeOpacity={bucket === 'profile_L' ? '0.1' : '0.6'} />
      <line x1={50} y1={40} x2={50} y2={60} stroke="currentColor" strokeWidth="1" />
      <line x1={44} y1={60} x2={56} y2={60} stroke="currentColor" strokeWidth="1" />
      <path d="M 40,73 Q 50,71 60,73" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <circle cx={50 + chinOffset} cy={92} r={2.5} fill="#4f98a3" />
      <circle cx={24} cy={66} r={2} fill="#e8af34" />
      <circle cx={76} cy={66} r={2} fill="#e8af34" />
    </svg>
  );
}

interface TimelineTracksProps {
  photos: Photo[];
  selectedPhoto: Photo | null;
  onSelectPhoto: (p: Photo) => void;
  playheadIndex: number;
  setPlayheadIndex: (idx: number) => void;
  zoomLevel: number;
  activeEventPin: EventPin | null;
  setActiveEventPin: (pin: EventPin | null) => void;
  onDoubleSelectPhoto?: (p: Photo) => void;
  selectedRange?: Photo[];
  setSelectedRange?: (range: Photo[]) => void;
}

interface MetricTrack {
  key: string;
  name: string;
  weight?: number;
  isTexture: boolean;
  color: string;
  minVal: number;
  maxVal: number;
  median: number;
  getValue: (p: Photo) => number;
  interpretation?: string;
}

// -------------------------------------------------------------
// HIGH-PERFORMANCE OUT-OF-SCOPE SUB-COMPONENTS & HELPERS
// Moved out of TimelineTracks to avoid garbage collection & unmount storms during rendering.
// -------------------------------------------------------------

const getXForIndexGrid = (idx: number, borderPadding: number, itemWidth: number): number => {
  return borderPadding + idx * itemWidth + itemWidth / 2;
};

const getXForDateGrid = (dateStr: string, photos: Photo[], borderPadding: number, itemWidth: number): number => {
  let closestIdx = 0;
  let minDiff = Infinity;
  const targetMs = new Date(dateStr).getTime();
  photos.forEach((photo, idx) => {
    const diff = Math.abs(new Date(photo.date).getTime() - targetMs);
    if (diff < minDiff) {
      minDiff = diff;
      closestIdx = idx;
    }
  });
  return borderPadding + closestIdx * itemWidth + itemWidth / 2;
};

interface TrackCanvasProps {
  track: MetricTrack;
  expandedTracks: string[];
  timelineWidth: number;
  borderPadding: number;
  itemWidth: number;
  photos: Photo[];
  playheadIndex: number;
  hoveredPhoto: Photo | null;
  selectedPhoto: Photo | null;
  scrollLeft: number;
  viewportWidth: number;
}

const TrackCanvas = React.memo(({
  track,
  expandedTracks,
  timelineWidth,
  borderPadding,
  itemWidth,
  photos,
  playheadIndex,
  hoveredPhoto,
  selectedPhoto,
  scrollLeft,
  viewportWidth
}: TrackCanvasProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const isExpanded = expandedTracks.includes(track.key);
  const cvHeight = isExpanded ? 76 : 30;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle custom dpi devices
    const dpr = window.devicePixelRatio || 1;
    canvas.width = viewportWidth * dpr;
    canvas.height = cvHeight * dpr;
    ctx.scale(dpr, dpr);

    // Clear
    ctx.fillStyle = '#0d0d0f';
    ctx.fillRect(0, 0, viewportWidth, cvHeight);

    // Draw grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.03)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, cvHeight / 2);
    ctx.lineTo(viewportWidth, cvHeight / 2);
    ctx.stroke();

    // Confidence gray interval shading if expanded
    if (isExpanded) {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.015)';
      const startShadeX = borderPadding - scrollLeft;
      const endShadeX = (timelineWidth - borderPadding) - scrollLeft;
      ctx.fillRect(startShadeX, cvHeight * 0.15, endShadeX - startShadeX, cvHeight * 0.7);
    }

    // Precalculate coordinates relative to viewport
    const points: { x: number; y: number; val: number; p: Photo }[] = [];
    photos.forEach((photo, idx) => {
      const val = track.getValue(photo);
      const xFull = getXForIndexGrid(idx, borderPadding, itemWidth);
      const x = xFull - scrollLeft;
      
      // Map y value between top and down
      const valPct = (val - track.minVal) / (track.maxVal - track.minVal);
      const y = cvHeight - 4 - borderPadding * 0.1 - valPct * (cvHeight - 12);
      
      points.push({ x, y, val, p: photo });
    });

    // 1. Vertical spine connector line for *every visible photo* to correlate data points vertically
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.025)';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    points.forEach((pt) => {
      if (pt.x >= -itemWidth && pt.x <= viewportWidth + itemWidth) {
        ctx.moveTo(pt.x, 0);
        ctx.lineTo(pt.x, cvHeight);
      }
    });
    ctx.stroke();

    // 2. Playhead vertical guide line (red)
    const selectedPhotoObj = photos[playheadIndex];
    if (selectedPhotoObj) {
      const selX = getXForIndexGrid(playheadIndex, borderPadding, itemWidth) - scrollLeft;
      if (selX >= -2 && selX <= viewportWidth + 2) {
        ctx.strokeStyle = 'rgba(255, 59, 48, 0.35)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(selX, 0);
        ctx.lineTo(selX, cvHeight);
        ctx.stroke();
      }
    }

    // 3. Hover vertical guide line (cyan)
    if (hoveredPhoto) {
      const hoveredIdx = photos.findIndex(p => p.id === hoveredPhoto.id);
      if (hoveredIdx !== -1) {
        const hovX = getXForIndexGrid(hoveredIdx, borderPadding, itemWidth) - scrollLeft;
        if (hovX >= -2 && hovX <= viewportWidth + 2) {
          ctx.strokeStyle = 'rgba(79, 152, 163, 0.4)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(hovX, 0);
          ctx.lineTo(hovX, cvHeight);
          ctx.stroke();
        }
      }
    }

    // Render BONE SCORE filled area chart if it's that composite key
    if (track.key === 'BONE SCORE') {
      ERAS.forEach((era) => {
        const startX = getXForDateGrid(era.start, photos, borderPadding, itemWidth) - scrollLeft;
        const endX = getXForDateGrid(era.end, photos, borderPadding, itemWidth) - scrollLeft;
        const eraPoints = points.filter((pt) => pt.x >= startX && pt.x <= endX);

        if (eraPoints.length > 1) {
          ctx.beginPath();
          ctx.moveTo(eraPoints[0].x, cvHeight - 1);
          eraPoints.forEach((pt) => {
            ctx.lineTo(pt.x, pt.y);
          });
          ctx.lineTo(eraPoints[eraPoints.length - 1].x, cvHeight - 1);
          ctx.closePath();
          
          // Fill based on Era palette
          ctx.fillStyle = `${era.color}08`; // very light transparent
          ctx.fill();
        }
      });
    }

    // Draw horizontal line connect paths
    ctx.strokeStyle = track.color;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    points.forEach((pt, i) => {
      if (i === 0) ctx.moveTo(pt.x, pt.y);
      else ctx.lineTo(pt.x, pt.y);
    });
    ctx.stroke();

    // Draw scatter dots representing measurements
    points.forEach((pt) => {
      if (pt.x < -10 || pt.x > viewportWidth + 10) return; // FRUSTUM CULL OUT OF BOUND SHOTS

      const isAnomaly = Math.abs(pt.val - track.median) > (track.isTexture ? 0.3 : 1.8);
      const isCritical = pt.p.flags.includes('TEMPORAL_IMPOSSIBILITY') || pt.p.flags.includes('IDENTITY_ANOMALY');
      const isSelected = selectedPhoto?.id === pt.p.id;
      const isHovered = hoveredPhoto?.id === pt.p.id;

      // Draw scatter dot
      if (isCritical) {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, isSelected ? 4 : 3, 0, Math.PI * 2);
        ctx.fillStyle = '#ff3b30'; // critical red
        ctx.fill();
      } else if (isAnomaly) {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, isSelected ? 3.5 : 2, 0, Math.PI * 2);
        ctx.fillStyle = '#e8af34'; // warn gold
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, isSelected ? 2.5 : 1, 0, Math.PI * 2);
        ctx.fillStyle = track.color;
        ctx.fill();
      }

      // Draw tactical rings for alignment highlights
      if (isSelected) {
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 5.5, 0, Math.PI * 2);
        ctx.stroke();
      } else if (isHovered) {
        ctx.strokeStyle = 'rgba(79, 152, 163, 0.8)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 4.5, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Draw IMPOSSIBLE_SHORT red vertical indicators on specific coordinates
      if (pt.p.flags.includes('IMPOSSIBLE_SHORT') && !track.isTexture) {
        ctx.strokeStyle = 'rgba(255, 59, 48, 0.4)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pt.x, 0);
        ctx.lineTo(pt.x, cvHeight);
        ctx.stroke();
      }

      // Draw TEXTURE SPIKES warning indicator
      if (pt.p.flags.includes('TEXTURE_SPIKE') && track.isTexture) {
        ctx.strokeStyle = 'rgba(253, 171, 67, 0.3)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pt.x, 0);
        ctx.lineTo(pt.x, cvHeight);
        ctx.stroke();
      }
    });

  }, [cvHeight, viewportWidth, scrollLeft, borderPadding, itemWidth, expandedTracks, hoveredPhoto, playheadIndex, photos, selectedPhoto, track, timelineWidth]);

  return (
    <div 
      className="relative block w-full border-b border-white/5 bg-[#0d0d0f]"
      style={{ height: `${cvHeight}px` }}
    >
      <canvas 
        ref={canvasRef} 
        width={(viewportWidth || 1000) * (window.devicePixelRatio || 1)}
        height={cvHeight * (window.devicePixelRatio || 1)}
        className="absolute top-0 bottom-0 block cursor-col-resize" 
        style={{ 
          left: `${scrollLeft || 0}px`, 
          width: `${viewportWidth || 1000}px`, 
          height: `${cvHeight}px` 
        }}
      />
      
      {/* Quick info if expanded */}
      {isExpanded && (
        <div className="absolute right-3 bottom-1.5 bg-black/85 px-2 py-0.5 rounded text-[8px] font-mono text-white/50 border border-white/5 flex items-center gap-1 z-10 select-none">
          <Info className="w-2.5 h-2.5 text-[#4f98a3]" />
          <span>{track.interpretation}</span>
        </div>
      )}
    </div>
  );
});
TrackCanvas.displayName = 'TrackCanvas';

interface VisualAgeTrackProps {
  expandedTracks: string[];
  timelineWidth: number;
  borderPadding: number;
  itemWidth: number;
  photos: Photo[];
  playheadIndex: number;
  hoveredPhoto: Photo | null;
  scrollLeft: number;
  viewportWidth: number;
}

const VisualAgeTrack = React.memo(({
  expandedTracks,
  timelineWidth,
  borderPadding,
  itemWidth,
  photos,
  playheadIndex,
  hoveredPhoto,
  scrollLeft,
  viewportWidth
}: VisualAgeTrackProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const isExpanded = expandedTracks.includes('VISUAL AGE');
  const cvHeight = isExpanded ? 76 : 30;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = viewportWidth * dpr;
    canvas.height = cvHeight * dpr;
    ctx.scale(dpr, dpr);

    ctx.fillStyle = '#0d0d0f';
    ctx.fillRect(0, 0, viewportWidth, cvHeight);

    const minAge = 40;
    const maxAge = 80;

    // 1. Vertical spine connector line for *every single photo* to correlate data points vertically
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.025)';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    photos.forEach((_, idx) => {
      const x = getXForIndexGrid(idx, borderPadding, itemWidth) - scrollLeft;
      if (x >= -itemWidth && x <= viewportWidth + itemWidth) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, cvHeight);
      }
    });
    ctx.stroke();

    // 2. Playhead vertical guide line (red)
    const selectedPhoto = photos[playheadIndex];
    if (selectedPhoto) {
      const selX = getXForIndexGrid(playheadIndex, borderPadding, itemWidth) - scrollLeft;
      if (selX >= -2 && selX <= viewportWidth + 2) {
        ctx.strokeStyle = 'rgba(255, 59, 48, 0.35)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(selX, 0);
        ctx.lineTo(selX, cvHeight);
        ctx.stroke();
      }
    }

    // 3. Hover vertical guide line (cyan)
    if (hoveredPhoto) {
      const hoveredIdx = photos.findIndex(p => p.id === hoveredPhoto.id);
      if (hoveredIdx !== -1) {
        const hovX = getXForIndexGrid(hoveredIdx, borderPadding, itemWidth) - scrollLeft;
        if (hovX >= -2 && hovX <= viewportWidth + 2) {
          ctx.strokeStyle = 'rgba(79, 152, 163, 0.4)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(hovX, 0);
          ctx.lineTo(hovX, cvHeight);
          ctx.stroke();
        }
      }
    }

    // Precalculate all line points for line drawings (using translation)
    const pts: {x: number, cy: number, vy: number}[] = [];
    photos.forEach((photo, i) => {
      const x = getXForIndexGrid(i, borderPadding, itemWidth) - scrollLeft;
      const cyPct = (photo.calendarAge - minAge) / (maxAge - minAge);
      const cy = cvHeight - 4 - cyPct * (cvHeight - 10);
      const vyPct = (photo.visualAge - minAge) / (maxAge - minAge);
      const vy = cvHeight - 4 - vyPct * (cvHeight - 10);
      pts.push({ x, cy, vy });
    });

    // Draw calendar age dotted line (starts around 46, ends at 73.6)
    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    ctx.setLineDash([2, 4]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    pts.forEach((pt, i) => {
      if (i === 0) ctx.moveTo(pt.x, pt.cy);
      else ctx.lineTo(pt.x, pt.cy);
    });
    ctx.stroke();
    ctx.setLineDash([]); // Reset

    // Draw visual age stepped area chart
    ctx.fillStyle = 'rgba(253, 171, 67, 0.08)';
    ctx.strokeStyle = '#fdab43';
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    pts.forEach((pt, i) => {
      if (i === 0) {
        ctx.moveTo(pt.x, cvHeight);
        ctx.lineTo(pt.x, pt.vy);
      } else {
        ctx.lineTo(pt.x, pt.vy);
      }
    });
    ctx.stroke();

    // Draw divergence warning indicators where visual_age - calendar_age > 10 years
    photos.forEach((photo, idx) => {
      const diff = photo.calendarAge - photo.visualAge;
      if (diff > 10) { // looks way younger (Vasilich effect)
        const x = getXForIndexGrid(idx, borderPadding, itemWidth) - scrollLeft;
        if (x >= -2 && x <= viewportWidth + 2) {
          ctx.fillStyle = 'rgba(168, 111, 223, 0.2)';
          ctx.fillRect(x - 1, 0, 2, cvHeight);
        }
      }
    });

  }, [cvHeight, viewportWidth, scrollLeft, borderPadding, itemWidth, expandedTracks, playheadIndex, hoveredPhoto, photos]);

  return (
    <div 
      className="relative block w-full border-b border-white/5 bg-[#0d0d0f]"
      style={{ height: `${cvHeight}px` }}
    >
      <canvas 
        ref={canvasRef} 
        width={(viewportWidth || 1000) * (window.devicePixelRatio || 1)}
        height={cvHeight * (window.devicePixelRatio || 1)}
        className="absolute top-0 bottom-0 block cursor-col-resize" 
        style={{ 
          left: `${scrollLeft || 0}px`, 
          width: `${viewportWidth || 1000}px`, 
          height: `${cvHeight}px` 
        }}
      />
      
      <div className="absolute right-3 top-2 flex items-center space-x-3 text-[8px] font-mono text-white/45 bg-black/80 px-2 py-0.5 rounded border border-white/5 z-10 select-none pointer-events-none">
        <div className="flex items-center gap-1">
          <div className="w-2.5 h-0.5 bg-[#fdab43]" />
          <span>Расчетный био-возраст</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2.5 h-0.5 border-t border-dotted border-white/60" />
          <span>Хронологический</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5 bg-[#a86fdf]/30" />
          <span>Омоложение &gt;10 лет</span>
        </div>
      </div>
    </div>
  );
});
VisualAgeTrack.displayName = 'VisualAgeTrack';


export default function TimelineTracks({
  photos,
  selectedPhoto,
  onSelectPhoto,
  playheadIndex,
  setPlayheadIndex,
  zoomLevel,
  activeEventPin,
  setActiveEventPin,
  onDoubleSelectPhoto,
  selectedRange,
  setSelectedRange
}: TimelineTracksProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rulerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const [hoveredPhoto, setHoveredPhoto] = useState<Photo | null>(null);
  const [hoverX, setHoverX] = useState<number>(0);
  const [hoverY, setHoverY] = useState<number>(0);
  const [expandedTracks, setExpandedTracks] = useState<string[]>(['BONE SCORE', 'SILICONE PROB', 'WRINKLE INDEX']);
  const [isDraggingPlayhead, setIsDraggingPlayhead] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const startX = useRef(0);
  const startScrollLeft = useRef(0);
  const hasMoved = useRef(false);
  const [rangeStart, setRangeStart] = useState<Photo | null>(null);

  // Track scroll details for virtualized, lightweight canvas rendering
  const [currentScrollLeft, setCurrentScrollLeft] = useState(0);
  const [viewportWidth, setViewportWidth] = useState(1000);

  // Define total coordinate width stretching with zoom
  const borderPadding = 30;
  const itemWidth = 50 * (zoomLevel / 100);
  const timelineWidth = borderPadding * 2 + photos.length * itemWidth;

  // Determine chronological limits (kept for compatibility in dataset limits checks)
  const minTime = new Date('1999-01-01').getTime();
  const maxTime = new Date('2026-06-06').getTime();
  const totalMs = maxTime - minTime;

  // Track definitions
  const GEOMETRIC_TRACKS: MetricTrack[] = [
    {
      key: 'BONE SCORE',
      name: 'ИНДЕКС КОСТНОЙ СТРУКТУРЫ',
      isTexture: false,
      color: '#4f98a3', // teal
      minVal: 0.0,
      maxVal: 4.5,
      median: 0.3,
      getValue: (p) => p.geometry.geometry_score,
      interpretation: 'Интегральный индекс изменения костной геометрии. Норма до 1.5.'
    },
    {
      key: 'ORBITS',
      name: 'ГЛУБИНА ГЛАЗНИЦ',
      weight: 1.0,
      isTexture: false,
      color: '#6daa45', // green
      minVal: -2.0,
      maxVal: 6.0,
      median: 0.0,
      getValue: (p) => p.geometry.orbit_depth,
      interpretation: 'Глубина глазниц и орбитальная ямка. Изменяется с трудом. Смена >3.0σ аномальна.'
    },
    {
      key: 'CHIN',
      name: 'ПРОЕКЦИЯ ПОДБОРОДКА',
      weight: 1.0,
      isTexture: false,
      color: '#e8af34', // gold
      minVal: -1.0,
      maxVal: 6.0,
      median: 0.0,
      getValue: (p) => p.geometry.chin_projection,
      interpretation: 'Выступание подбородка и угол челюсти. Аномально растет в ERA 5.'
    },
    {
      key: 'JAW',
      name: 'ШИРИНА ЧЕЛЮСТИ',
      weight: 0.8,
      isTexture: false,
      color: '#fdab43', // orange
      minVal: -1.0,
      maxVal: 5.0,
      median: 0.0,
      getValue: (p) => p.geometry.jaw_width,
      interpretation: 'Ширина нижней челюсти. Высокие показатели в эпохе Василича.'
    },
    {
      key: 'CHEEKBONES',
      name: 'ВЫСОТА СКУЛ',
      weight: 0.7,
      isTexture: false,
      color: '#a86fdf', // purple
      minVal: -1.0,
      maxVal: 6.0,
      median: 0.0,
      getValue: (p) => p.geometry.ramus_height,
      interpretation: 'Высота скуловой дуги и ветви. Рост сигнализирует филлеры/протезы.'
    },
    {
      key: 'SYMMETRY',
      name: 'СИММЕТРИЯ ЛИЦА',
      weight: 0.6,
      isTexture: false,
      color: '#5591c7', // blue
      minVal: 0.5,
      maxVal: 1.0,
      median: 0.96,
      getValue: (p) => p.geometry.symmetry_score,
      interpretation: 'Билатеральная симметрия лица. Снижение говорит об асимметричном старении.'
    },
    {
      key: 'POSE YAW',
      name: 'ПОВОРОТ ГОЛОВЫ',
      isTexture: false,
      color: '#797876', // gray
      minVal: -10,
      maxVal: 80,
      median: 5.0,
      getValue: (p) => p.geometry.pose_yaw_deg,
      interpretation: 'Угол поворота лица в градусах. Меньше 15 — наивысшая надежность.'
    }
  ];

  const TEXTURE_TRACKS: MetricTrack[] = [
    {
      key: 'SILICONE PROB',
      name: 'ВЕРОЯТНОСТЬ СИЛИКОНА / ГРИМА',
      isTexture: true,
      color: '#a13544', // maroon
      minVal: 0.0,
      maxVal: 1.0,
      median: 0.02,
      getValue: (p) => p.texture.texture_silicone_prob,
      interpretation: 'Вероятность наличия силиконовой маски / пластического грима.'
    },
    {
      key: 'SPECULAR GLOSS',
      name: 'ЗЕРКАЛЬНЫЙ БЛЕСК КОЖИ',
      isTexture: true,
      color: '#4f98a3', // teal
      minVal: 0.1,
      maxVal: 1.0,
      median: 0.45,
      getValue: (p) => p.texture.texture_specular_gloss,
      interpretation: 'Зеркальный блеск кожи. Падает со старением, аномально прыгает при вмешательствах.'
    },
    {
      key: 'LBP ENTROPY',
      name: 'ТЕКСТУРНАЯ СЛОЖНОСТЬ LBP',
      isTexture: true,
      color: '#6daa45', // green
      minVal: 0.2,
      maxVal: 1.0,
      median: 0.42,
      getValue: (p) => p.texture.texture_lbp_complexity,
      interpretation: 'Текстурная сложность распределения LBP. Всплеск говорит об изменении микроструктуры.'
    },
    {
      key: 'FRANGI VESSEL',
      name: 'СУДИСТЫЙ РИСУНОК (ФРАНДЖИ)',
      isTexture: true,
      color: '#5591c7', // blue
      minVal: 0.2,
      maxVal: 1.0,
      median: 0.85,
      getValue: (p) => p.texture.texture_frangi_vessel,
      interpretation: 'Плотность сосудистого русла по фильтру Франджи. Снижается у масок.'
    },
    {
      key: 'WRINKLE INDEX',
      name: 'СУММАРНЫЙ ИНДЕКС МОРЩИН',
      isTexture: true,
      color: '#e8af34', // gold
      minVal: 0.0,
      maxVal: 0.7,
      median: 0.1,
      getValue: (p) => (p.texture.texture_wrinkle_forehead + p.texture.texture_wrinkle_nasolabial) / 2,
      interpretation: 'Суммарный индекс морщин лба/носогубок. Естественно возрастает с ходом лет.'
    },
    {
      key: 'SUBSURFACE',
      name: 'СВЕТОРАССЕЯНИЕ КОЖИ',
      isTexture: true,
      color: '#a86fdf', // purple
      minVal: 0.0,
      maxVal: 1.0,
      median: 0.15,
      getValue: (p) => p.texture.texture_subsurface_scatter_proxy,
      interpretation: 'Рассеяние света под кожей. Рост означает полимерные маски или филлеры.'
    }
  ];

  // Map index to visual coordinate
  const getXForIndex = (idx: number): number => {
    return borderPadding + idx * itemWidth + itemWidth / 2;
  };

  // Helper: map a date to the closest index visual coordinate
  const getXForDate = (dateStr: string): number => {
    let closestIdx = 0;
    let minDiff = Infinity;
    const targetMs = new Date(dateStr).getTime();
    photos.forEach((photo, idx) => {
      const diff = Math.abs(new Date(photo.date).getTime() - targetMs);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = idx;
      }
    });
    return getXForIndex(closestIdx);
  };

  // Helper: find closest photo by coordinate or date index
  const getPhotoForX = (clientX: number): { photo: Photo; idx: number } | null => {
    if (!containerRef.current) return null;
    const rect = containerRef.current.getBoundingClientRect();
    const scrollLeft = containerRef.current.scrollLeft;
    const absoluteX = clientX - rect.left + scrollLeft;

    let idx = Math.floor((absoluteX - borderPadding) / itemWidth);
    idx = Math.max(0, Math.min(photos.length - 1, idx));
    return { photo: photos[idx], idx };
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!containerRef.current) return;
    
    // Check if click was inside the Ruler top part or PREVIEWS track (Y < 115)
    const rect = containerRef.current.getBoundingClientRect();
    const clickY = e.clientY - rect.top;

    if (clickY < 115) {
      setIsDraggingPlayhead(true);
      const result = getPhotoForX(e.clientX);
      if (result) {
        setPlayheadIndex(result.idx);
        onSelectPhoto(result.photo);
      }
    } else {
      // Clicked on standard tracks canvas region: initiate drag panning!
      setIsPanning(true);
      startX.current = e.clientX;
      startScrollLeft.current = containerRef.current.scrollLeft;
      hasMoved.current = false;
    }
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      // 1. Scrubbing slider
      if (isDraggingPlayhead) {
        const result = getPhotoForX(e.clientX);
        if (result) {
          setPlayheadIndex(result.idx);
          onSelectPhoto(result.photo);
        }
      }

      // 2. Click-to-drag panning
      if (isPanning && containerRef.current) {
        const dx = e.clientX - startX.current;
        if (Math.abs(dx) > 4) {
          hasMoved.current = true;
        }
        containerRef.current.scrollLeft = startScrollLeft.current - dx;
      }

      // 3. Sync hover positioning
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const scrollLeft = containerRef.current.scrollLeft;
        const result = getPhotoForX(e.clientX);
        
        if (result && e.clientY > rect.top && e.clientY < rect.bottom) {
          setHoveredPhoto(result.photo);
          setHoverX(getXForIndex(result.idx) - scrollLeft + 4);
          setHoverY(e.clientY - rect.top - 80);
        } else {
          setHoveredPhoto(null);
        }
      }
    };

    const handleMouseUp = (e: MouseEvent) => {
      if (isPanning && !hasMoved.current) {
        // If it was just a quick static click (no movement), select that photo
        const result = getPhotoForX(e.clientX);
        if (result) {
          setPlayheadIndex(result.idx);
          onSelectPhoto(result.photo);
        }
      }
      setIsDraggingPlayhead(false);
      setIsPanning(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingPlayhead, isPanning, photos, zoomLevel]);

  // Sync scroll positioning to the selected photo's index
  useEffect(() => {
    if (photos[playheadIndex] && containerRef.current && !isDraggingPlayhead && !isPanning) {
      const pX = getXForIndex(playheadIndex);
      const container = containerRef.current;
      const targetScroll = pX - container.clientWidth / 2;
      container.scrollTo({
        left: targetScroll,
        behavior: 'smooth'
      });
    }
  }, [playheadIndex, zoomLevel]);

  // Handle wheel horizontal scrolling
  useEffect(() => {
    const handleWheel = (e: WheelEvent) => {
      if (containerRef.current) {
        // Convert vertical mouse coordinates (deltaY) into horizontal scrolling if deltaX is zero
        if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
          e.preventDefault();
          containerRef.current.scrollLeft += e.deltaY;
        } else if (Math.abs(e.deltaX) > 0) {
          e.preventDefault();
          containerRef.current.scrollLeft += e.deltaX;
        }
      }
    };

    const container = containerRef.current;
    if (container) {
      container.addEventListener('wheel', handleWheel, { passive: false });
    }
    return () => {
      if (container) {
        container.removeEventListener('wheel', handleWheel);
      }
    };
  }, [timelineWidth]);

  // Keep scrollLeft and viewportWidth in state to drive high-performance canvas frustum culling
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScrollAndResize = () => {
      setCurrentScrollLeft(container.scrollLeft);
      setViewportWidth(container.clientWidth || 1000);
    };

    // Initialize immediately
    handleScrollAndResize();

    container.addEventListener('scroll', handleScrollAndResize, { passive: true });
    window.addEventListener('resize', handleScrollAndResize);

    // Monitor resize of container dynamically
    const ro = new ResizeObserver(() => {
      handleScrollAndResize();
    });
    ro.observe(container);

    return () => {
      container.removeEventListener('scroll', handleScrollAndResize);
      window.removeEventListener('resize', handleScrollAndResize);
      ro.disconnect();
    };
  }, []);

  const toggleTrack = (key: string) => {
    if (expandedTracks.includes(key)) {
      setExpandedTracks(expandedTracks.filter((t) => t !== key));
    } else {
      setExpandedTracks([...expandedTracks, key]);
    }
  };

  // Removed old nested helper components TrackCanvas and VisualAgeTrack to boost execution speed and eliminate unmounting loops.

  // Generate ruler ticks based on years present in the current photo collection
  const rulerTicks = useMemo(() => {
    const ticks: { year: number; idx: number }[] = [];
    let currentYear = -1;
    photos.forEach((photo, idx) => {
      if (photo.year !== currentYear) {
        ticks.push({ year: photo.year, idx });
        currentYear = photo.year;
      }
    });
    return ticks;
  }, [photos]);

  return (
    <div className="flex text-white select-none bg-[#09090b]" ref={rulerRef}>
      
      {/* FIXED LEFT SIDEBAR: Static labels with expand triggers */}
      <div className="w-[180px] min-w-[180px] flex flex-col bg-[#0c0c0e] border-r border-[#ffffff]/10 z-20 shrink-0 select-none">
        {/* Spacer for ruler top */}
        <div className="h-[48px] border-b border-[#ffffff]/10 px-3 flex items-center bg-[#09090b] text-[#4f98a3] font-display font-semibold text-[9px] tracking-widest shrink-0 uppercase">
          Timeline Index
        </div>

        {/* PHOTO PREVIEWS SPOOLER HEADER */}
        <div className="h-[60px] border-b border-[#ffffff]/10 px-3 flex flex-col justify-center bg-[#070709] shrink-0">
          <span className="font-display font-medium text-[9px] tracking-wider text-white/90 uppercase flex items-center gap-1.5 text-glow-teal">
            <Sparkles className="w-3 h-3 text-[#4f98a3]" />
            ЛЕНТА КАДРОВ
          </span>
          <span className="text-[7.5px] font-mono text-white/35 uppercase">
            {photos.length} ФОТО • 50PX FLUSH
          </span>
        </div>

        {/* GEOM HEADER ROW */}
        <div className="h-[22px] bg-[#09090c] border-b border-white/5 px-3 flex items-center text-[7.5px] font-mono text-white/40 tracking-wider">
          GEOMETRY TRACKS
        </div>

        {GEOMETRIC_TRACKS.map((track) => {
          const isExpanded = expandedTracks.includes(track.key);
          const cvHeight = isExpanded ? 76 : 30;
          return (
            <div 
              key={track.key}
              onClick={() => toggleTrack(track.key)}
              className="px-3 flex items-center justify-between cursor-pointer border-b border-white/5 bg-[#0d0d11]/80 hover:bg-white/5 transition duration-150"
              style={{ height: cvHeight }}
            >
              <div className="flex flex-col">
                <span className="font-display font-medium text-[9px] tracking-wider text-white/90 uppercase">{track.name}</span>
                {track.weight && <span className="text-[7.5px] font-mono text-white/35">WT: {track.weight.toFixed(1)}</span>}
              </div>
              <div className="text-white/30 hover:text-white transition">
                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </div>
            </div>
          );
        })}

        {/* TEXTURE HEADER ROW */}
        <div className="h-[22px] bg-[#09090c] border-b border-white/5 px-3 flex items-center text-[7.5px] font-mono text-white/40 tracking-wider">
          SKIN TEXTURES
        </div>

        {TEXTURE_TRACKS.map((track) => {
          const isExpanded = expandedTracks.includes(track.key);
          const cvHeight = isExpanded ? 76 : 30;
          return (
            <div 
              key={track.key}
              onClick={() => toggleTrack(track.key)}
              className="px-3 flex items-center justify-between cursor-pointer border-b border-white/5 bg-[#0d0d11]/80 hover:bg-white/5 transition duration-150"
              style={{ height: cvHeight }}
            >
              <div className="flex flex-col">
                <span className="font-display font-medium text-[9px] tracking-wider text-white/90 uppercase">{track.name}</span>
              </div>
              <div className="text-white/30 hover:text-white transition">
                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </div>
            </div>
          );
        })}

        {/* VISUAL AGE DOCK ROW */}
        <div 
          onClick={() => toggleTrack('VISUAL AGE')}
          className="px-3 flex items-center justify-between cursor-pointer border-b border-white/10 bg-[#0d0d11]/80 hover:bg-white/5 transition duration-150"
          style={{ height: expandedTracks.includes('VISUAL AGE') ? 76 : 30 }}
        >
          <div className="flex flex-col">
            <span className="font-display font-medium text-[9px] tracking-wider text-[#fdab43] uppercase">ВИЗУАЛЬНЫЙ ВОЗРАСТ</span>
            <span className="text-[7.5px] font-mono text-white/35">ПРОТИВ КАЛЕНДАРНОГО</span>
          </div>
          <div className="text-[#fdab43]/60 hover:text-[#fdab43] transition">
            {expandedTracks.includes('VISUAL AGE') ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </div>
        </div>
      </div>

      {/* HORIZONTALLY SCROLLABLE WORKSPACE TIMELINE REGION */}
      <div 
        ref={containerRef}
        onMouseDown={handleMouseDown}
        className={`flex-1 overflow-x-auto overflow-y-hidden select-none relative bg-[#09090c] border-l border-white/5 ${
          isPanning ? 'cursor-grabbing' : 'cursor-grab'
        }`}
      >
        <div style={{ width: timelineWidth }} className="flex flex-col relative select-none">
          
          {/* A. TIMELINE RULER TOP BAR */}
          <div className="bg-[#0b0b0d] border-b border-white/10 relative h-[48px] select-none shrink-0 cursor-col-resize">
            {/* Timeline ticks */}
            <div className="absolute inset-x-0 top-0 h-[22px] border-b border-white/5 flex items-end">
              {rulerTicks.map((tick) => {
                const x = getXForIndex(tick.idx);
                return (
                  <div key={tick.year} className="absolute pointer-events-none" style={{ left: x }}>
                    {/* Big ticks with labels */}
                    <div className="h-4 border-l border-white/20" />
                    <span className="absolute bottom-4 left-1.5 font-mono text-[9px] font-medium text-white/45 select-none text-glow-teal">
                      {tick.year}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* ERA markers stripe */}
            <div className="absolute inset-x-0 bottom-0 h-[10px] flex">
              {ERAS.map((era) => {
                const startX = getXForDate(era.start);
                const endX = getXForDate(era.end);
                return (
                  <div
                    key={era.id}
                    title={`${era.name}\n${era.description}`}
                    className="absolute bottom-0 h-[6px] transition-all hover:h-[10px] cursor-help"
                    style={{
                      left: startX,
                      width: Math.max(2, endX - startX),
                      backgroundColor: era.color
                    }}
                  />
                );
              })}
            </div>

            {/* HISTORICAL EVENT PINS */}
            {EVENT_PINS.map((pin) => {
              const x = getXForDate(pin.date);
              const isActive = activeEventPin?.id === pin.id;
              
              return (
                <button
                  key={pin.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveEventPin(isActive ? null : pin);
                  }}
                  className={`absolute -top-1 w-[16px] h-[24px] z-20 cursor-pointer flex flex-col items-center transition-all ${
                    isActive ? 'scale-125' : 'hover:scale-110'
                  }`}
                  style={{ left: x - 8 }}
                >
                  <div 
                    className="w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold border leading-none"
                    style={{
                      backgroundColor: pin.color,
                      borderColor: isActive ? '#ffffff' : 'rgba(0,0,0,0.4)',
                      color: pin.color === '#ffffff' ? '#111' : '#fff'
                    }}
                    title={`${pin.label} (Клик для источника)`}
                  >
                    !
                  </div>
                  <div className="w-0.5 h-4" style={{ backgroundColor: pin.color }} />
                </button>
              );
            })}

            {/* DYNAMIC TIMELINE ANOMALY & INCIDENT MARKERS */}
            {photos.filter(p => p.flags.length > 0).map((p) => {
              const pIdx = photos.findIndex(item => item.id === p.id);
              if (pIdx === -1) return null;
              const x = getXForIndex(pIdx);
              const isSelected = selectedPhoto?.id === p.id;
              
              const isTemporal = p.flags.includes('TEMPORAL_IMPOSSIBILITY');
              const isIdentity = p.flags.includes('IDENTITY_ANOMALY');
              const isExif = p.flags.includes('EXIF_DATE_ANOMALY');
              const isShort = p.flags.includes('IMPOSSIBLE_SHORT');
              
              let markerColor = '#fdab43'; // default warm orange
              let symbol = '⚠️';
              let badgeTitle = `Обнаружен инцидент: ${p.flags.join(', ')}`;
              
              if (isTemporal || isIdentity) {
                markerColor = '#ff3b30'; // vivid red
                symbol = '🚨';
                badgeTitle = `КРИТИЧЕСКАЯ АНОМАЛИЯ: ${p.flags.join(', ')}`;
              } else if (isExif) {
                markerColor = '#dd6974'; // red-pink
                symbol = '📅';
                badgeTitle = `КОНФЛИКТ ВРЕМЕНИ / EXIF: ${p.flags.join(', ')}`;
              } else if (isShort) {
                markerColor = '#e8af34'; // gold
                symbol = '⚡';
                badgeTitle = `СКАЧОК ИЗМЕНЕНИЙ: ${p.flags.join(', ')}`;
              }

              return (
                <button
                  key={`anomaly-badge-${p.id}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectPhoto(p);
                  }}
                  className={`absolute top-[22px] w-[14px] h-[16px] z-25 cursor-pointer flex flex-col items-center transition-all group ${
                    isSelected ? 'scale-125' : 'hover:scale-115'
                  }`}
                  style={{ left: x - 7 }}
                  title={`${badgeTitle}\nКадр: ${p.id} (${p.date})\nНажмите для фокусировки`}
                >
                  <div 
                    className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-[7.5px] font-bold border leading-none shadow-lg transition"
                    style={{
                      backgroundColor: markerColor,
                      borderColor: isSelected ? '#ffffff' : 'rgba(0,0,0,0.5)',
                      color: '#ffffff'
                    }}
                  >
                    {symbol}
                  </div>
                  <div className="w-[1px] h-3 bg-white/20 group-hover:bg-white/50" />
                </button>
              );
            })}
          </div>

          {/* A2. PHOTO PREVIEWS TRACK (Adobe Premiere style) */}
          <div className="h-[60px] bg-[#0c0c0e]/95 border-b border-[#ffffff]/10 relative flex items-center select-none shrink-0 overflow-hidden">
            {photos.map((photo, idx) => {
              const xCenter = getXForIndex(idx);
              const isSelected = selectedPhoto?.id === photo.id;
              const isPlayhead = playheadIndex === idx;
              const isRangeSelected = selectedRange?.some((p) => p.id === photo.id) || false;
              const isUdmurt = photo.year >= 2015 && photo.year < 2021;
              const isVasilich = photo.year >= 2023;
              const isCrit = photo.flags.includes('TEMPORAL_IMPOSSIBILITY') || photo.flags.includes('IDENTITY_ANOMALY');

              return (
                <div
                  key={photo.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    setPlayheadIndex(idx);
                    onSelectPhoto(photo);
                    if (e.shiftKey && rangeStart && setSelectedRange) {
                      const startIdx = photos.indexOf(rangeStart);
                      const endIdx = idx;
                      const newRange = photos.slice(
                        Math.min(startIdx, endIdx),
                        Math.max(startIdx, endIdx) + 1
                      );
                      setSelectedRange(newRange);
                    } else {
                      setRangeStart(photo);
                      if (setSelectedRange) setSelectedRange([photo]);
                    }
                  }}
                  onDoubleClick={() => onDoubleSelectPhoto?.(photo)}
                  onMouseEnter={() => setHoveredPhoto(photo)}
                  onMouseLeave={() => setHoveredPhoto(null)}
                  className={`absolute top-[5px] h-[50px] cursor-pointer transition-all border flex items-center justify-center select-none overflow-hidden rounded-[2px] ${
                    isPlayhead ? 'ring-2 ring-red-500 scale-102 z-30 border-red-500/85 shadow-md shadow-red-500/10' : ''
                  } ${
                    isRangeSelected ? 'bg-amber-500/20 border-amber-500/80 z-10' :
                    isSelected ? 'bg-white/5 border-white z-10' : 'border-white/5 hover:border-white/30 bg-[#08080a]'
                  }`}
                  style={{
                    left: xCenter - itemWidth / 2,
                    width: itemWidth,
                  }}
                >
                  <div className="w-full h-full relative flex items-center justify-center">
                    {photo.isHidden ? (
                      <div className="absolute inset-0 bg-black/80 flex items-center justify-center">
                        <EyeOff className="w-3.5 h-3.5 text-red-500/60" />
                      </div>
                    ) : (
                      <>
                        <VectorHead
                          bucket={photo.poseBucket}
                          isUdmurt={isUdmurt}
                          isVasilich={isVasilich}
                          size={Math.min(42, itemWidth - 2)}
                        />
                        {isCrit && (
                          <div className="absolute top-1 right-1 w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
                        )}
                        {/* Compact index/year label on bottom */}
                        <div className="absolute bottom-0 inset-x-0 bg-black/75 text-[7px] py-0.5 text-center font-mono opacity-85 select-none text-white/95">
                          {photo.year}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* B. GEOMETRIC SEGMENT */}
          <div className="bg-[#0e0e12] border-b border-[#ffffff]/10">
            <div className="h-[22px] bg-[#ffffff]/[0.02]/30 px-3 flex items-center justify-between border-b border-[#ffffff]/5 select-none pointer-events-none">
              <span className="text-[9px] font-mono text-white/50 tracking-wider">ВЕРХНИЕ ДОРОЖКИ — ОСТЕОЛОГИЯ ЛИЦА (7 ЛИНИЙ)</span>
              <span className="text-[8px] font-mono text-white/30 font-semibold text-glow-teal">ЭТАЛОННАЯ БАЗА: МЕДИАНЫ ЭПОХИ 1</span>
            </div>
            {GEOMETRIC_TRACKS.map((track) => (
              <TrackCanvas
                key={track.key}
                track={track}
                expandedTracks={expandedTracks}
                timelineWidth={timelineWidth}
                borderPadding={borderPadding}
                itemWidth={itemWidth}
                photos={photos}
                playheadIndex={playheadIndex}
                hoveredPhoto={hoveredPhoto}
                selectedPhoto={selectedPhoto}
                scrollLeft={currentScrollLeft}
                viewportWidth={viewportWidth}
              />
            ))}
          </div>

          {/* C. TEXTURE SEGMENT */}
          <div className="bg-[#0e0e12]">
            <div className="h-[22px] bg-[#ffffff]/[0.02]/30 px-3 flex items-center justify-between border-b border-[#ffffff]/5 select-none pointer-events-none">
              <span className="text-[9px] font-mono text-white/50 tracking-wider">НИЖНИЕ ДОРОЖКИ — ТЕКСТУРА КОЖИ И СТРУКТУРА (7 ЛИНИЙ)</span>
              <span className="text-[8px] font-mono text-white/30">ПОРОГ ВСПЛЕСКА ТЕКСТУРЫ: 0.15</span>
            </div>
            {TEXTURE_TRACKS.map((track) => (
              <TrackCanvas
                key={track.key}
                track={track}
                expandedTracks={expandedTracks}
                timelineWidth={timelineWidth}
                borderPadding={borderPadding}
                itemWidth={itemWidth}
                photos={photos}
                playheadIndex={playheadIndex}
                hoveredPhoto={hoveredPhoto}
                selectedPhoto={selectedPhoto}
                scrollLeft={currentScrollLeft}
                viewportWidth={viewportWidth}
              />
            ))}
            <VisualAgeTrack
              expandedTracks={expandedTracks}
              timelineWidth={timelineWidth}
              borderPadding={borderPadding}
              itemWidth={itemWidth}
              photos={photos}
              playheadIndex={playheadIndex}
              hoveredPhoto={hoveredPhoto}
              scrollLeft={currentScrollLeft}
              viewportWidth={viewportWidth}
            />
          </div>

          {/* D. SYNCHRONOUS RED PLAYHEAD SLIDER */}
          <div 
            className="absolute top-0 bottom-0 w-[2px] bg-[#ff3b30]/80 z-20 pointer-events-none"
            style={{ left: getXForIndex(playheadIndex) }}
          >
            <div className="w-2.5 h-2.5 bg-[#ff3b30] rounded-full -ml-[4px] -mt-[4px]" />
            <div className="bg-[#ff3b30] text-[8px] font-mono text-white px-1 py-0.5 rounded absolute -top-4 left-2.5 leading-none shadow-lg animate-fade-in">
              {photos[playheadIndex]?.date}
            </div>
          </div>

        </div>

        {/* Dynamic Hover Tooltip synchronized on coordinates */}
        {hoveredPhoto && (
          <div 
            ref={tooltipRef}
            className="absolute z-40 bg-black/95 border border-white/15 rounded p-2 text-[10px] font-mono shadow-2xl pointer-events-none w-[200px]"
            style={{
              left: Math.min(hoverX + 10, timelineWidth - 220),
              top: Math.max(20, hoverY)
            }}
          >
            <div className="flex justify-between text-white border-b border-white/10 pb-1 mb-1">
              <span className="font-semibold text-[#4f98a3]">{hoveredPhoto.id}</span>
              <span className="text-white/40">{hoveredPhoto.date}</span>
            </div>
            <div className="space-y-0.5">
              <div className="flex justify-between">
                <span>Ракурс:</span>
                <span className="text-white/80">{hoveredPhoto.poseBucket}</span>
              </div>
              <div className="flex justify-between">
                <span>Костный индекс:</span>
                <span className="text-[#4f98a3]">{hoveredPhoto.geometry.geometry_score.toFixed(2)}σ</span>
              </div>
              <div className="flex justify-between">
                <span>Маска/Грим:</span>
                <span className="text-[#a13544]">{(hoveredPhoto.texture.texture_silicone_prob * 100).toFixed(0)}%</span>
              </div>
              <div className="flex justify-between">
                <span>Стат. вердикт:</span>
                <span className="text-white font-semibold" style={{ color: 
                  hoveredPhoto.fuzzyLabel === 'IDENTITY_ANOMALY' ? '#ff3b30' :
                  hoveredPhoto.fuzzyLabel === 'GEOMETRIC_MISMATCH' ? '#dd6974' :
                  hoveredPhoto.fuzzyLabel === 'SUSPICIOUS_TEXTURE' ? '#fdab43' : '#6daa45'
                }}>
                  {hoveredPhoto.fuzzyLabel === 'STRONGLY_MATCHING' ? 'ПООЛНОЕ СОВПАДЕНИЕ' :
                   hoveredPhoto.fuzzyLabel === 'CONSISTENT' ? 'СОГЛАСОВАНО' :
                   hoveredPhoto.fuzzyLabel === 'INSUFFICIENT_DATA' ? 'НЕДОСТАТОЧНО ДАННЫХ' :
                   hoveredPhoto.fuzzyLabel === 'WEAK_EVIDENCE' ? 'СЛАБЫЕ УЛИКИ' :
                   hoveredPhoto.fuzzyLabel === 'SUSPICIOUS_TEXTURE' ? 'ПОДОЗРИТЕЛЬНАЯ ТЕКСТУРА' :
                   hoveredPhoto.fuzzyLabel === 'GEOMETRIC_MISMATCH' ? 'КОСТНОЕ РАСХОЖДЕНИЕ' :
                   hoveredPhoto.fuzzyLabel === 'IDENTITY_ANOMALY' ? 'ЗАМЕНА ЛИЧНОСТИ' :
                   hoveredPhoto.fuzzyLabel === 'TEMPORAL_IMPOSSIBILITY' ? 'ТЕМПОРАЛЬНЫЙ СБОЙ' :
                   hoveredPhoto.fuzzyLabel}
                </span>
              </div>
            </div>
          </div>
        )}

      </div>

    </div>
  );
};
