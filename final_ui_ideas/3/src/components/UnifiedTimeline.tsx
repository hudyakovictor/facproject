// Единый блок таймлайна в стиле Adobe Premiere:
// — по вертикальной линии каждого фото расположены точки всех метрик
// — между точками рисуются соединительные линии (line chart по реальным данным)
// — при hover на фото подсвечивается "связка" через все дорожки
// — фото 50×50 идут вплотную друг к другу

import { useMemo, useRef, useEffect, useState, useCallback } from "react";
import { Photo, HYPOTHESIS_COLORS, EVENT_PINS, EventPin, FUZZY_COLORS, ERA_META, REF } from "../data";
import Icon from "./Icon";
import { t } from "../i18n";

export interface TrackDef {
  id: string;
  label: string;
  color: string;
  weight: string;
  metric: (p: Photo) => number;
  ref: { median: number; std: number };
  filled?: boolean;
  dashed?: boolean;
}

const GEOM_TRACKS: TrackDef[] = [
  { id: "BONE", label: t.trackBone, weight: "—", color: "#4f98a3", metric: p => p.boneScore, ref: REF.boneScore, filled: true },
  { id: "ORBIT", label: t.trackOrbits, weight: "1.0", color: "#6daa45", metric: p => p.orbit, ref: REF.orbit },
  { id: "CHIN", label: t.trackChin, weight: "1.0", color: "#e8af34", metric: p => p.chin, ref: REF.chin },
  { id: "JAW", label: t.trackJaw, weight: "0.8", color: "#fdab43", metric: p => p.jaw, ref: REF.jaw },
  { id: "CHEEK", label: t.trackCheek, weight: "0.7", color: "#a86fdf", metric: p => p.cheek, ref: REF.cheek },
  { id: "SYM", label: t.trackSymmetry, weight: "0.6", color: "#5591c7", metric: p => p.symmetry, ref: REF.symmetry },
  { id: "YAW", label: t.trackYaw, weight: "—", color: "#797876", metric: p => p.yaw, ref: REF.yaw, dashed: true },
];
const TEX_TRACKS: TrackDef[] = [
  { id: "SIL", label: t.trackSilicone, weight: "—", color: "#a13544", metric: p => p.siliconeProb, ref: REF.siliconeProb },
  { id: "SPEC", label: t.trackSpecular, weight: "—", color: "#4f98a3", metric: p => p.specular, ref: REF.specular },
  { id: "LBP", label: t.trackLBP, weight: "—", color: "#6daa45", metric: p => p.lbpEntropy, ref: REF.lbpEntropy },
  { id: "FRA", label: t.trackFrangi, weight: "—", color: "#5591c7", metric: p => p.frangi, ref: REF.frangi },
  { id: "WRI", label: t.trackWrinkle, weight: "—", color: "#e8af34", metric: p => p.wrinkle, ref: REF.wrinkle },
  { id: "SUB", label: t.trackSubsurface, weight: "—", color: "#a86fdf", metric: p => p.subsurface, ref: REF.subsurface },
];
const AGE_TRACK: TrackDef = { id: "AGE", label: t.trackVisualAge, weight: "Δкал", color: "#fdab43", metric: p => p.visualAge, ref: REF.visualAge, filled: true };

interface Props {
  photos: Photo[];
  filmstripOffset: number;
  setFilmstripOffset: (n: number) => void;
  thumbSize: number;
  playheadT: number;
  onSelectPhoto: (id: string) => void;
  selectedId: string | null;
  onScrubTo: (t: number) => void;
  onPinClick: (pin: EventPin) => void;
  onDoubleClickPhoto: (p: Photo) => void;
  onRangeSelected: (range: { t0: number; t1: number; photos: Photo[] } | null) => void;
  rangeSelection: { t0: number; t1: number } | null;
  highlightIds?: Set<string>;
}

const LABEL_W = 184;        // ширина левой колонки с подписями дорожек
const PINS_H = 30;          // полоса пинов событий сверху
const FILMSTRIP_H = 64;     // высота полосы фото (фото 50 + поля)
const VERDICT_H = 14;       // полоса fuzzy-вердикта над фото
const ERA_H = 8;            // полоса эпохи под фото
const RULER_H = 20;         // линейка дат
const TRACK_H_GEOM = 38;    // высота каждой геометрической дорожки
const TRACK_H_TEX = 36;     // высота каждой текстурной дорожки
const TRACK_H_AGE = 56;     // высота дорожки возраста (заполненная)
const GROUP_HEADER_H = 18;  // заголовок группы (ГЕОМЕТРИЯ / ТЕКСТУРА)
const PHOTO_PAD = 7;        // отступ карточки фото от верха/низа полосы

export default function UnifiedTimeline({
  photos, filmstripOffset, setFilmstripOffset, thumbSize,
  playheadT, onSelectPhoto, selectedId, onScrubTo, onPinClick,
  onDoubleClickPhoto, onRangeSelected, rangeSelection, highlightIds,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1200);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [hoverPos, setHoverPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [dragSel, setDragSel] = useState<{ i0: number; i1: number } | null>(null);

  useEffect(() => {
    const ro = new ResizeObserver(entries => {
      for (const e of entries) { setWidth(e.contentRect.width); }
    });
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // Compute layout
  const trackAreaW = Math.max(200, width - LABEL_W);
  const visibleCount = Math.max(1, Math.floor(trackAreaW / thumbSize));
  const totalPhotos = photos.length;
  const maxOffset = Math.max(0, totalPhotos - visibleCount);
  const offset = Math.max(0, Math.min(maxOffset, filmstripOffset));

  const xForIdxLocal = (gi: number) => (gi - offset) * thumbSize;
  const xForIdx = (gi: number) => LABEL_W + xForIdxLocal(gi) + thumbSize / 2;
  const idxForX = (x: number) => Math.floor((x - LABEL_W) / thumbSize) + offset;

  // Vertical layout: pins, filmstrip+verdict+era, then geom group, then tex group
  const filmstripBlockH = VERDICT_H + FILMSTRIP_H + ERA_H;

  const yPins = 0;
  const yFilmstripBlock = yPins + PINS_H;
  const yVerdict = yFilmstripBlock;
  const yFilm = yVerdict + VERDICT_H;
  const yEra = yFilm + FILMSTRIP_H;
  const yGeomHeader = yEra + ERA_H;
  const yGeomTracks = yGeomHeader + GROUP_HEADER_H;
  const yTexHeader = yGeomTracks + GEOM_TRACKS.length * TRACK_H_GEOM;
  const yTexTracks = yTexHeader + GROUP_HEADER_H;
  const yAgeTrack = yTexTracks + TEX_TRACKS.length * TRACK_H_TEX;
  const yRuler = yAgeTrack + TRACK_H_AGE;
  const totalContentH = yRuler + RULER_H;

  // Compute Y for a specific track
  const yForGeomTrack = (i: number) => yGeomTracks + i * TRACK_H_GEOM;
  const yForTexTrack = (i: number) => yTexTracks + i * TRACK_H_TEX;

  // Visible photos (slightly extended on both sides)
  const margin = 2;
  const firstVisible = Math.max(0, offset - margin);
  const lastVisible = Math.min(totalPhotos, offset + visibleCount + margin);
  const visiblePhotos = photos.slice(firstVisible, lastVisible);

  // Playhead index = closest photo to playheadT
  const playheadIdx = useMemo(() => {
    if (!photos.length) return 0;
    let bi = 0; let bd = Infinity;
    for (let i = 0; i < photos.length; i++) {
      const d = Math.abs(photos[i].t - playheadT);
      if (d < bd) { bd = d; bi = i; }
    }
    return bi;
  }, [photos, playheadT]);

  // Auto-scroll filmstrip when playhead leaves visible window
  useEffect(() => {
    if (playheadIdx < offset) setFilmstripOffset(playheadIdx);
    else if (playheadIdx >= offset + visibleCount) setFilmstripOffset(Math.max(0, playheadIdx - visibleCount + 1));
  }, [playheadIdx]); // eslint-disable-line

  // Wheel: pan filmstrip by index
  useEffect(() => {
    const el = wrapRef.current; if (!el) return;
    const onWheel = (ev: WheelEvent) => {
      if (ev.ctrlKey || ev.metaKey) return;
      const dom = Math.abs(ev.deltaX) > Math.abs(ev.deltaY) ? ev.deltaX : ev.deltaY;
      if (Math.abs(dom) < 0.1) return;
      ev.preventDefault();
      const step = Math.sign(dom) * Math.max(1, Math.round(Math.abs(dom) / 60));
      setFilmstripOffset(Math.max(0, Math.min(maxOffset, offset + step)));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [offset, maxOffset, setFilmstripOffset]);

  // Render one track as SVG paths using real per-photo values
  const renderTrackPath = useCallback((tr: TrackDef, yTop: number, h: number, withFill: boolean) => {
    // Compute y range from ALL photos (so the same scale persists when scrolling)
    let minV = Infinity, maxV = -Infinity;
    for (const p of photos) {
      const v = tr.metric(p);
      if (v < minV) minV = v;
      if (v > maxV) maxV = v;
    }
    if (!isFinite(minV)) { minV = 0; maxV = 1; }
    const pad = (maxV - minV) * 0.18 || 0.05;
    const lo = minV - pad, hi = maxV + pad;

    const yVal = (v: number) => yTop + h - ((v - lo) / (hi - lo)) * h;

    // baseline (reference median)
    const yRef = yVal(tr.ref.median);

    // Build path. Include 1 extra point on each side for line continuity.
    const i0 = Math.max(0, offset - 1);
    const i1 = Math.min(photos.length, offset + visibleCount + 1);

    let pathD = "";
    let fillD = "";
    const pts: { x: number; y: number; gi: number; v: number; z: number }[] = [];

    for (let i = i0; i < i1; i++) {
      const p = photos[i];
      const x = xForIdx(i);
      const v = tr.metric(p);
      const y = yVal(v);
      const z = (v - tr.ref.median) / tr.ref.std;
      pts.push({ x, y, gi: i, v, z });
      pathD += (pathD ? " L " : "M ") + x.toFixed(1) + " " + y.toFixed(1);
    }

    if (withFill && pts.length) {
      fillD = `M ${pts[0].x.toFixed(1)} ${(yTop + h).toFixed(1)} `
        + pts.map(p => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ")
        + ` L ${pts[pts.length - 1].x.toFixed(1)} ${(yTop + h).toFixed(1)} Z`;
    }

    return { pathD, fillD, pts, yRef, lo, hi };
  }, [photos, offset, visibleCount, xForIdx]);

  // Date labels: every Nth photo
  const labelEvery = Math.max(1, Math.ceil(80 / thumbSize));

  // Mouse handlers
  const onMouseDown = (e: React.MouseEvent) => {
    const rect = wrapRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x < LABEL_W) return;
    const idx = Math.max(0, Math.min(totalPhotos - 1, idxForX(x)));
    if (e.shiftKey) {
      setDragSel({ i0: idx, i1: idx });
      const onMove = (ev: MouseEvent) => {
        const xx = ev.clientX - rect.left;
        const ii = Math.max(0, Math.min(totalPhotos - 1, idxForX(xx)));
        setDragSel(prev => prev ? { ...prev, i1: ii } : null);
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        setDragSel(prev => {
          if (!prev) return null;
          const a = Math.min(prev.i0, prev.i1), b = Math.max(prev.i0, prev.i1);
          if (b - a >= 1) {
            const selPhotos = photos.slice(a, b + 1);
            onRangeSelected({ t0: photos[a].t, t1: photos[b].t, photos: selPhotos });
          }
          return null;
        });
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    } else if (photos[idx]) {
      onScrubTo(photos[idx].t);
    }
  };

  const onMouseMove = (e: React.MouseEvent) => {
    const rect = wrapRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    setHoverPos({ x: e.clientX, y: e.clientY });
    if (x < LABEL_W) { setHoverIdx(null); return; }
    const idx = idxForX(x);
    if (idx >= 0 && idx < totalPhotos) setHoverIdx(idx);
    else setHoverIdx(null);
  };

  const onMouseLeave = () => setHoverIdx(null);

  // Pin index = closest photo to pin's date
  const pinIdx = (pinT: number) => {
    let bi = 0; let bd = Infinity;
    for (let i = 0; i < photos.length; i++) {
      const d = Math.abs(photos[i].t - pinT);
      if (d < bd) { bd = d; bi = i; }
    }
    return bi;
  };

  if (!photos.length) {
    return <div ref={wrapRef} className="w-full h-full flex items-center justify-center text-text-muted font-mono text-xs bg-bg/40">Нет фото, удовлетворяющих фильтрам</div>;
  }

  // Era stripe by photo
  const eraColorFor = (gi: number) => {
    const p = photos[gi]; return p ? ERA_META[p.era].color : "#000";
  };

  // Determine if photo is part of an active drag selection
  const inDragRange = (gi: number) => dragSel ? gi >= Math.min(dragSel.i0, dragSel.i1) && gi <= Math.max(dragSel.i0, dragSel.i1) : false;

  return (
    <div ref={wrapRef}
      className="relative w-full h-full overflow-hidden bg-bg select-none"
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
    >
      {/* === LEFT COLUMN: track labels === */}
      <div className="absolute top-0 left-0 bg-surface border-r border-border-strong" style={{ width: LABEL_W, height: totalContentH }}>
        {/* pins band label */}
        <div className="px-2 flex items-center font-mono text-[9px] text-text-faint tracking-forensic border-b border-border bg-surface-2"
          style={{ height: PINS_H }}>
          <Icon name="alert-triangle" size={11} className="mr-1.5" /> СОБЫТИЯ
        </div>

        {/* film block label */}
        <div className="border-b border-border bg-surface-2 px-2 flex flex-col justify-center font-mono text-[10px]"
          style={{ height: filmstripBlockH }}>
          <div className="text-text tracking-forensic font-semibold">ФОТО · {totalPhotos}</div>
          <div className="text-text-muted text-[9px] mt-0.5">видно {Math.min(visibleCount, totalPhotos)} из {totalPhotos}</div>
          <div className="text-text-faint text-[9px] mt-0.5">↑ цвет — вердикт<br />↓ цвет — эпоха</div>
        </div>

        {/* geometry group */}
        <div className="px-2 flex items-center justify-between bg-surface-2 border-b border-border font-mono text-[9px] text-text-muted tracking-forensic"
          style={{ height: GROUP_HEADER_H }}>
          <span>{t.geometry7Lanes}</span>
        </div>
        {GEOM_TRACKS.map(tr => (
          <div key={tr.id}
            className="flex items-center gap-2 px-2 border-b border-border/60 font-mono text-[10px] hover:bg-surface-2"
            style={{ height: TRACK_H_GEOM }}>
            <div className="w-1 h-4" style={{ background: tr.color }} />
            <div className="flex-1 min-w-0">
              <div className="truncate" style={{ color: tr.color }}>{tr.label}</div>
              <div className="text-text-faint text-[8px]">норма {tr.ref.median.toFixed(2)} · w={tr.weight}</div>
            </div>
          </div>
        ))}

        {/* texture group */}
        <div className="px-2 flex items-center bg-surface-2 border-y border-border font-mono text-[9px] text-text-muted tracking-forensic"
          style={{ height: GROUP_HEADER_H }}>
          {t.texture7Lanes}
        </div>
        {TEX_TRACKS.map(tr => (
          <div key={tr.id}
            className="flex items-center gap-2 px-2 border-b border-border/60 font-mono text-[10px] hover:bg-surface-2"
            style={{ height: TRACK_H_TEX }}>
            <div className="w-1 h-4" style={{ background: tr.color }} />
            <div className="flex-1 min-w-0">
              <div className="truncate" style={{ color: tr.color }}>{tr.label}</div>
              <div className="text-text-faint text-[8px]">норма {tr.ref.median.toFixed(2)}</div>
            </div>
          </div>
        ))}
        <div className="flex items-center gap-2 px-2 border-b border-border/60 font-mono text-[10px] hover:bg-surface-2"
          style={{ height: TRACK_H_AGE }}>
          <div className="w-1 h-7" style={{ background: AGE_TRACK.color }} />
          <div className="flex-1 min-w-0">
            <div className="truncate" style={{ color: AGE_TRACK.color }}>{AGE_TRACK.label}</div>
            <div className="text-text-faint text-[8px]">vs <span className="text-info">календарный</span> · пунктир</div>
          </div>
        </div>

        {/* ruler label */}
        <div className="bg-surface-2 px-2 flex items-center font-mono text-[9px] text-text-faint tracking-forensic border-t border-border"
          style={{ height: RULER_H }}>
          <Icon name="calendar" size={10} className="mr-1.5" /> ДАТЫ
        </div>
      </div>

      {/* === RIGHT COLUMN: timeline tracks (SVG) === */}
      <svg
        className="absolute top-0 pointer-events-none"
        style={{ left: LABEL_W, width: trackAreaW, height: totalContentH }}
        viewBox={`${LABEL_W} 0 ${trackAreaW} ${totalContentH}`}
        preserveAspectRatio="none"
      >
        {/* row background bands (alternating subtle) for tracks */}
        {GEOM_TRACKS.map((_, i) => (
          <rect key={`bg-g${i}`} x={LABEL_W} y={yForGeomTrack(i)} width={trackAreaW} height={TRACK_H_GEOM}
            fill={i % 2 === 0 ? "rgba(255,255,255,0.012)" : "transparent"} />
        ))}
        {TEX_TRACKS.map((_, i) => (
          <rect key={`bg-t${i}`} x={LABEL_W} y={yForTexTrack(i)} width={trackAreaW} height={TRACK_H_TEX}
            fill={i % 2 === 0 ? "rgba(255,255,255,0.012)" : "transparent"} />
        ))}

        {/* Vertical guides — one for each visible photo. Subtle dashed lines that connect filmstrip → all tracks. */}
        {visiblePhotos.map((p, i) => {
          const gi = firstVisible + i;
          const x = xForIdx(gi);
          const isHovered = hoverIdx === gi;
          const isSelected = selectedId === p.id;
          const isPlayhead = gi === playheadIdx;
          const isInDrag = inDragRange(gi);
          const isInRange = rangeSelection && p.t >= rangeSelection.t0 && p.t <= rangeSelection.t1;

          if (isHovered || isSelected || isPlayhead || isInDrag) {
            return (
              <line key={`g-${gi}`}
                x1={x} y1={yGeomHeader} x2={x} y2={yRuler}
                stroke={isPlayhead ? "#ff3b30" : isSelected ? "#fff" : isHovered ? "#5591c7" : "#5591c7"}
                strokeWidth={isPlayhead ? 1.2 : isSelected ? 1 : 0.7}
                strokeDasharray={isPlayhead ? undefined : "2 2"}
                strokeOpacity={isPlayhead ? 0.95 : isSelected ? 0.8 : 0.5}
              />
            );
          }
          if (isInRange) {
            return <line key={`g-${gi}`} x1={x} y1={yGeomHeader} x2={x} y2={yRuler}
              stroke="#5591c7" strokeWidth={0.4} strokeOpacity={0.18} />;
          }
          return null;
        })}

        {/* === GEOMETRY tracks === */}
        {GEOM_TRACKS.map((tr, i) => {
          const yTop = yForGeomTrack(i);
          const { pathD, fillD, pts, yRef } = renderTrackPath(tr, yTop + 3, TRACK_H_GEOM - 6, !!tr.filled);
          return (
            <g key={tr.id}>
              {/* baseline reference line (ref median) */}
              <line x1={LABEL_W} y1={yRef} x2={LABEL_W + trackAreaW} y2={yRef} stroke={tr.color} strokeOpacity="0.18" strokeDasharray="2 4" />
              {tr.filled && fillD && (
                <path d={fillD} fill={tr.color} fillOpacity="0.18" />
              )}
              <path d={pathD} fill="none" stroke={tr.color} strokeWidth={1.4}
                strokeDasharray={tr.dashed ? "3 3" : undefined}
                strokeLinejoin="round" strokeLinecap="round" />
              {/* keyframe dots aligned with each photo column */}
              {pts.map(p => {
                const abs = Math.abs(p.z);
                const fill = abs > 3 ? "#ff3b30" : abs > 2 ? "#fdab43" : abs > 1 ? "#e8af34" : tr.color;
                const r = abs > 3 ? 2.6 : abs > 2 ? 2.2 : 1.8;
                return (
                  <g key={p.gi}>
                    {abs > 2 && (
                      <circle cx={p.x} cy={p.y} r={r + 2.5} fill={fill} fillOpacity="0.25">
                        <animate attributeName="r" values={`${r + 2.5};${r + 5};${r + 2.5}`} dur="2s" repeatCount="indefinite" />
                        <animate attributeName="fill-opacity" values="0.25;0;0.25" dur="2s" repeatCount="indefinite" />
                      </circle>
                    )}
                    <circle cx={p.x} cy={p.y} r={r} fill={fill} stroke="#0d0d0f" strokeWidth="0.5" />
                  </g>
                );
              })}
              {/* hovered keyframe — exact value label */}
              {hoverIdx !== null && pts.find(p => p.gi === hoverIdx) && (() => {
                const p = pts.find(p => p.gi === hoverIdx)!;
                const txtX = p.x + 5 + (p.x > LABEL_W + trackAreaW - 60 ? -50 : 0);
                return <g>
                  <rect x={txtX - 1} y={p.y - 8} width={48} height={11} fill="#0d0d0f" fillOpacity="0.85" />
                  <text x={txtX} y={p.y + 1} fontSize="9" fontFamily="JetBrains Mono" fill={tr.color}>{p.v.toFixed(3)}</text>
                </g>;
              })()}
            </g>
          );
        })}

        {/* === TEXTURE tracks === */}
        {TEX_TRACKS.map((tr, i) => {
          const yTop = yForTexTrack(i);
          const { pathD, fillD, pts, yRef } = renderTrackPath(tr, yTop + 3, TRACK_H_TEX - 6, !!tr.filled);
          return (
            <g key={tr.id}>
              <line x1={LABEL_W} y1={yRef} x2={LABEL_W + trackAreaW} y2={yRef} stroke={tr.color} strokeOpacity="0.18" strokeDasharray="2 4" />
              {fillD && <path d={fillD} fill={tr.color} fillOpacity="0.18" />}
              <path d={pathD} fill="none" stroke={tr.color} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" />
              {pts.map(p => {
                const abs = Math.abs(p.z);
                const fill = abs > 3 ? "#ff3b30" : abs > 2 ? "#fdab43" : abs > 1 ? "#e8af34" : tr.color;
                const r = abs > 3 ? 2.6 : abs > 2 ? 2.2 : 1.8;
                return (
                  <g key={p.gi}>
                    {abs > 2 && (
                      <circle cx={p.x} cy={p.y} r={r + 2.5} fill={fill} fillOpacity="0.25">
                        <animate attributeName="r" values={`${r + 2.5};${r + 5};${r + 2.5}`} dur="2s" repeatCount="indefinite" />
                        <animate attributeName="fill-opacity" values="0.25;0;0.25" dur="2s" repeatCount="indefinite" />
                      </circle>
                    )}
                    <circle cx={p.x} cy={p.y} r={r} fill={fill} stroke="#0d0d0f" strokeWidth="0.5" />
                  </g>
                );
              })}
              {hoverIdx !== null && pts.find(p => p.gi === hoverIdx) && (() => {
                const p = pts.find(p => p.gi === hoverIdx)!;
                const txtX = p.x + 5 + (p.x > LABEL_W + trackAreaW - 60 ? -50 : 0);
                return <g>
                  <rect x={txtX - 1} y={p.y - 8} width={48} height={11} fill="#0d0d0f" fillOpacity="0.85" />
                  <text x={txtX} y={p.y + 1} fontSize="9" fontFamily="JetBrains Mono" fill={tr.color}>{p.v.toFixed(3)}</text>
                </g>;
              })()}
            </g>
          );
        })}

        {/* === AGE TRACK (filled area + calendar overlay) === */}
        {(() => {
          const yTop = yAgeTrack + 3;
          const h = TRACK_H_AGE - 6;
          const lo = 40, hi = 90;
          const yVal = (v: number) => yTop + h - ((v - lo) / (hi - lo)) * h;
          const i0 = Math.max(0, offset - 1);
          const i1 = Math.min(photos.length, offset + visibleCount + 1);
          let visualD = "", calD = "", visualFill = "";
          const ptsV: { x: number; y: number; gi: number; v: number; cal: number; diff: number }[] = [];
          for (let i = i0; i < i1; i++) {
            const p = photos[i];
            const x = xForIdx(i);
            const yV = yVal(p.visualAge);
            const yC = yVal(p.calendarAge);
            ptsV.push({ x, y: yV, gi: i, v: p.visualAge, cal: p.calendarAge, diff: p.visualAge - p.calendarAge });
            visualD += (visualD ? " L " : "M ") + x.toFixed(1) + " " + yV.toFixed(1);
            calD += (calD ? " L " : "M ") + x.toFixed(1) + " " + yC.toFixed(1);
          }
          if (ptsV.length) {
            visualFill = `M ${ptsV[0].x.toFixed(1)} ${(yTop + h).toFixed(1)} `
              + ptsV.map(p => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ")
              + ` L ${ptsV[ptsV.length - 1].x.toFixed(1)} ${(yTop + h).toFixed(1)} Z`;
          }
          return (
            <g>
              <path d={visualFill} fill="#fdab43" fillOpacity="0.2" />
              <path d={visualD} fill="none" stroke="#fdab43" strokeWidth={1.4} />
              <path d={calD} fill="none" stroke="#5591c7" strokeWidth={1.1} strokeDasharray="4 3" />
              {ptsV.map(p => (
                <g key={p.gi}>
                  <circle cx={p.x} cy={p.y} r={1.8} fill={Math.abs(p.diff) > 5 ? "#ff3b30" : "#fdab43"} stroke="#0d0d0f" strokeWidth="0.5" />
                </g>
              ))}
              {hoverIdx !== null && ptsV.find(p => p.gi === hoverIdx) && (() => {
                const p = ptsV.find(p => p.gi === hoverIdx)!;
                const txtX = p.x + 5 + (p.x > LABEL_W + trackAreaW - 90 ? -70 : 0);
                return <g>
                  <rect x={txtX - 1} y={p.y - 17} width={84} height={22} fill="#0d0d0f" fillOpacity="0.9" />
                  <text x={txtX} y={p.y - 7} fontSize="9" fontFamily="JetBrains Mono" fill="#fdab43">визуал {p.v.toFixed(1)}</text>
                  <text x={txtX} y={p.y + 3} fontSize="9" fontFamily="JetBrains Mono" fill="#5591c7">календ {p.cal.toFixed(1)}</text>
                </g>;
              })()}
            </g>
          );
        })()}

        {/* === PLAYHEAD line through all tracks (always rendered last for top layer) === */}
        {(() => {
          if (playheadIdx < offset - 1 || playheadIdx > offset + visibleCount + 1) return null;
          const x = xForIdx(playheadIdx);
          return (
            <g>
              <line x1={x} y1={yPins} x2={x} y2={totalContentH}
                stroke="#ff3b30" strokeWidth={1} strokeOpacity={0.9} />
            </g>
          );
        })()}
      </svg>

      {/* === ABSOLUTE OVERLAY ELEMENTS in right column === */}
      <div className="absolute" style={{ left: LABEL_W, top: 0, width: trackAreaW, height: totalContentH, pointerEvents: "none" }}>
        {/* Event pins */}
        <div className="absolute left-0 right-0 z-30 pointer-events-none" style={{ top: yPins, height: PINS_H }}>
          {EVENT_PINS.map(pin => {
            const idx = pinIdx(pin.t);
            if (idx < offset - 1 || idx > offset + visibleCount + 1) return null;
            const xLocal = xForIdxLocal(idx) + thumbSize / 2;
            return (
              <div key={pin.id} className="absolute pointer-events-auto cursor-pointer group"
                style={{ left: xLocal - 9, top: 4 }}
                onClick={e => { e.stopPropagation(); onPinClick(pin); }}>
                <div className="w-[18px] h-[18px] rounded-sm border border-black/40 flex items-center justify-center shadow-md hover:scale-110 transition-transform" style={{ background: pin.color }}>
                  <Icon name={pin.iconName} size={11} color="#0d0d0f" strokeWidth={2.2} />
                </div>
                <div className="w-px h-2 mx-auto" style={{ background: pin.color, opacity: 0.6 }} />
                <div className="absolute left-5 top-0 hidden group-hover:block bg-bg border border-border-strong rounded p-2 w-72 text-[10px] z-50 shadow-2xl"
                  style={{ borderLeftWidth: 3, borderLeftColor: pin.color }}>
                  <div className="font-display font-semibold text-[11px] mb-0.5" style={{ color: pin.color }}>{pin.title}</div>
                  <div className="text-text-muted font-mono text-[9px] mb-1.5">{new Date(pin.t).toLocaleDateString("ru-RU")} · {pin.source}</div>
                  <div className="text-text leading-snug mb-1">«{pin.tooltip}»</div>
                  {pin.folkTag && <div className="text-text-faint italic text-[9px] pt-1 border-t border-border mt-1">↳ {pin.folkTag}</div>}
                </div>
              </div>
            );
          })}
        </div>

        {/* Verdict (fuzzy-label) strip above thumbnails */}
        <div className="absolute left-0 right-0 pointer-events-none flex" style={{ top: yVerdict, height: VERDICT_H }}>
          {visiblePhotos.map((p, i) => {
            const gi = firstVisible + i;
            const xLocal = xForIdxLocal(gi);
            const isImpossible = p.fuzzy === "TEMPORAL_IMPOSSIBILITY";
            return (
              <div key={p.id} className={`absolute ${isImpossible ? "blink-critical" : ""}`}
                style={{ left: xLocal, width: thumbSize, top: 0, height: VERDICT_H, background: FUZZY_COLORS[p.fuzzy] }}>
                {isImpossible && <div className="absolute inset-1 bg-white/80" />}
              </div>
            );
          })}
        </div>

        {/* Filmstrip */}
        <div className="absolute left-0 right-0 pointer-events-none" style={{ top: yFilm, height: FILMSTRIP_H }}>
          {visiblePhotos.map((p, i) => {
            const gi = firstVisible + i;
            const xLocal = xForIdxLocal(gi);
            const color = HYPOTHESIS_COLORS[p.dominant];
            const isSelected = selectedId === p.id;
            const isHovered = hoverIdx === gi;
            const isHighlighted = highlightIds?.has(p.id);
            const qColor = p.quality > 0.6 ? "#6daa45" : p.quality > 0.35 ? "#e8af34" : "#a13544";

            return (
              <div key={p.id}
                className={`absolute pointer-events-auto cursor-pointer transition-all duration-150 ${isSelected ? "z-30" : isHovered ? "z-20" : "z-10"}`}
                style={{
                  left: xLocal, top: PHOTO_PAD,
                  width: thumbSize, height: thumbSize,
                  transform: isSelected ? "scale(1.15)" : isHovered ? "scale(1.06)" : "scale(1)",
                  transformOrigin: "center bottom",
                }}
                onClick={e => { e.stopPropagation(); onSelectPhoto(p.id); onScrubTo(p.t); }}
                onDoubleClick={e => { e.stopPropagation(); onDoubleClickPhoto(p); }}
              >
                <div className="w-full h-full relative overflow-hidden"
                  style={{
                    border: `1.5px solid ${color}`,
                    background: `linear-gradient(160deg, ${color}33 0%, #1a1a24 55%, #0d0d0f 100%)`,
                    filter: p.hidden ? "blur(3px) brightness(0.4)" : "none",
                    boxShadow: isSelected ? `0 0 0 1px #fff, 0 4px 18px ${color}` : isHovered ? `0 0 0 1px #5591c7` : isHighlighted ? `inset 0 0 0 1px #5591c7` : "none",
                    opacity: highlightIds && !isHighlighted ? 0.35 : 1,
                  }}>
                  <svg viewBox="0 0 60 80" className="absolute inset-0 w-full h-full opacity-60" preserveAspectRatio="xMidYMid meet">
                    <defs>
                      <radialGradient id={`rg-${p.id}`} cx="50%" cy="40%" r="60%">
                        <stop offset="0%" stopColor={color} stopOpacity="0.5" />
                        <stop offset="100%" stopColor={color} stopOpacity="0.05" />
                      </radialGradient>
                    </defs>
                    <ellipse cx="30" cy="36" rx={15 + p.cheek * 4} ry={22 + p.chin * 4} fill={`url(#rg-${p.id})`} stroke={color} strokeWidth="0.4" />
                    <ellipse cx="22" cy="33" rx="2" ry={1 + p.orbit * 1.5} fill={color} fillOpacity="0.85" />
                    <ellipse cx="38" cy="33" rx="2" ry={1 + p.orbit * 1.5} fill={color} fillOpacity="0.85" />
                    <path d={`M 22 ${46 + p.jaw * 4} Q 30 ${50 + p.chin * 10} 38 ${46 + p.jaw * 4}`} stroke={color} strokeWidth="0.6" fill="none" />
                  </svg>
                  <div className="absolute top-0.5 left-0.5 w-1.5 h-1.5 rounded-full" style={{ background: qColor }} />
                  {p.hidden && <div className="absolute inset-0 flex items-center justify-center"><Icon name="eye-off" size={20} color="#fff" /></div>}
                  {p.flags.includes("TEMPORAL_IMPOSSIBILITY") && <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-critical blink-critical border border-bg" />}
                </div>
              </div>
            );
          })}
        </div>

        {/* Era stripe under photos */}
        <div className="absolute left-0 right-0 pointer-events-none flex" style={{ top: yEra, height: ERA_H }}>
          {visiblePhotos.map((p, i) => {
            const gi = firstVisible + i;
            const xLocal = xForIdxLocal(gi);
            return <div key={p.id} className="absolute" style={{ left: xLocal, width: thumbSize, top: 0, height: ERA_H, background: eraColorFor(gi), opacity: 0.75 }} />;
          })}
        </div>

        {/* Range selection (persistent) */}
        {rangeSelection && (() => {
          let i0 = -1, i1 = -1;
          for (let i = 0; i < photos.length; i++) {
            if (photos[i].t >= rangeSelection.t0 && i0 < 0) i0 = i;
            if (photos[i].t <= rangeSelection.t1) i1 = i;
          }
          if (i0 < 0) return null;
          const x0 = xForIdxLocal(i0);
          const x1 = xForIdxLocal(i1 + 1);
          if (x1 < 0 || x0 > trackAreaW) return null;
          return (
            <div className="absolute pointer-events-none border-l-2 border-r-2 border-info/60 bg-info/10"
              style={{ left: Math.max(0, x0), width: Math.min(trackAreaW, x1) - Math.max(0, x0), top: yFilmstripBlock, height: totalContentH - yFilmstripBlock - RULER_H }}>
              <div className="absolute top-1 left-1 font-mono text-[9px] text-info bg-bg/80 px-1.5 py-0.5 tracking-forensic">
                {t.rangeLabel} · {new Date(rangeSelection.t0).toLocaleDateString("ru-RU")} → {new Date(rangeSelection.t1).toLocaleDateString("ru-RU")}
              </div>
            </div>
          );
        })()}

        {/* Drag selection (live) */}
        {dragSel && (() => {
          const i0 = Math.min(dragSel.i0, dragSel.i1);
          const i1 = Math.max(dragSel.i0, dragSel.i1);
          const x0 = xForIdxLocal(i0);
          const x1 = xForIdxLocal(i1 + 1);
          return (
            <div className="absolute pointer-events-none border-l-2 border-r-2 border-info bg-info/20"
              style={{ left: x0, width: x1 - x0, top: yFilmstripBlock, height: totalContentH - yFilmstripBlock - RULER_H }}>
              <div className="absolute top-1 left-1 font-mono text-[9px] text-info bg-bg/80 px-1.5 py-0.5 tracking-forensic">
                {t.selecting} {i1 - i0 + 1}
              </div>
            </div>
          );
        })()}

        {/* Date ruler at the bottom */}
        <div className="absolute left-0 right-0 pointer-events-none flex border-t border-border" style={{ top: yRuler, height: RULER_H }}>
          {visiblePhotos.map((p, i) => {
            const gi = firstVisible + i;
            if (gi % labelEvery !== 0 && i !== 0 && i !== visiblePhotos.length - 1) return null;
            const xLocal = xForIdxLocal(gi);
            return (
              <div key={p.id} className="absolute text-center font-mono text-[8px] text-text-muted"
                style={{ left: xLocal + thumbSize / 2 - 28, top: 4, width: 56 }}>
                {new Date(p.t).toLocaleDateString("ru-RU", { year: "2-digit", month: "2-digit", day: "2-digit" })}
              </div>
            );
          })}
        </div>

        {/* Scroll indicator at very bottom */}
        {totalPhotos > visibleCount && (
          <div className="absolute left-1 right-1 bottom-0.5 h-0.5 bg-surface-3 pointer-events-none">
            <div className="h-full bg-info/60" style={{
              left: `${(offset / totalPhotos) * 100}%`,
              width: `${(visibleCount / totalPhotos) * 100}%`,
              position: "absolute",
            }} />
          </div>
        )}
      </div>

      {/* Hover floating card with full info */}
      {hoverIdx !== null && photos[hoverIdx] && (() => {
        const p = photos[hoverIdx];
        return (
          <div className="fixed z-50 bg-bg border border-border-strong rounded p-2 pointer-events-none shadow-2xl"
            style={{ left: Math.min(hoverPos.x + 14, window.innerWidth - 280), top: Math.min(hoverPos.y + 14, window.innerHeight - 280), width: 260 }}>
            <div className="w-full h-32 mb-2 relative overflow-hidden"
              style={{ background: `linear-gradient(160deg, ${HYPOTHESIS_COLORS[p.dominant]}44, #13131a)`, border: `1px solid ${HYPOTHESIS_COLORS[p.dominant]}` }}>
              <svg viewBox="0 0 60 80" className="absolute inset-0 w-full h-full opacity-70" preserveAspectRatio="xMidYMid meet">
                <ellipse cx="30" cy="36" rx={15 + p.cheek * 4} ry={22 + p.chin * 4} fill={HYPOTHESIS_COLORS[p.dominant]} fillOpacity="0.22" stroke={HYPOTHESIS_COLORS[p.dominant]} strokeWidth="0.6" />
                <ellipse cx="22" cy="33" rx="2.5" ry="2" fill={HYPOTHESIS_COLORS[p.dominant]} />
                <ellipse cx="38" cy="33" rx="2.5" ry="2" fill={HYPOTHESIS_COLORS[p.dominant]} />
                <path d={`M 22 ${46 + p.jaw * 4} Q 30 ${50 + p.chin * 10} 38 ${46 + p.jaw * 4}`} stroke={HYPOTHESIS_COLORS[p.dominant]} strokeWidth="0.7" fill="none" />
              </svg>
              <div className="absolute top-0 left-0 right-0 h-1" style={{ background: FUZZY_COLORS[p.fuzzy] }} />
            </div>
            <div className="font-mono text-[10px] space-y-0.5">
              <div className="flex justify-between"><span className="text-text-muted">{t.hoverId}</span><span>{p.id}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.hoverDate}</span><span>{new Date(p.t).toLocaleDateString("ru-RU")}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.hoverBucket}</span><span>{p.bucket}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.hoverQuality}</span><span>{p.quality.toFixed(2)}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.hoverDominant}</span><span style={{ color: HYPOTHESIS_COLORS[p.dominant] }}>{p.dominant} · {t.hypothesisShort[p.dominant]}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.hoverFuzzy}</span><span style={{ color: FUZZY_COLORS[p.fuzzy] }}>{t.fuzzy[p.fuzzy]}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.era.toLowerCase()}</span><span style={{ color: ERA_META[p.era].color }}>{t.eraShort[p.era]}</span></div>
            </div>
            {p.flags.length > 0 && (
              <div className="mt-1.5 pt-1.5 border-t border-border flex flex-wrap gap-1">
                {p.flags.slice(0, 3).map(f => (
                  <span key={f} className="font-mono text-[8px] px-1 py-0.5 bg-surface-3 text-warning">{f}</span>
                ))}
              </div>
            )}
            <div className="mt-1.5 pt-1.5 border-t border-border font-mono text-[8px] text-text-faint leading-tight">
              {t.hintClick}<br />{t.hintDbl}<br />{t.hintShift}<br />{t.hintWheel}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
