import React, { useRef, useEffect, useMemo } from "react";
import { PhotoPoint, ERA_DEFS, HYP_COLORS, FUZZY_COLORS, EventPinDef } from "../types";
import { useTimelineScroll } from "../hooks/useTimelineScroll";

interface Props {
  photos: PhotoPoint[];
  zoom: number;
  scrollRatio: number;
  setScrollRatio: (v: number) => void;
  playheadRatio: number;
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  hoveredId: string | null;
  setHoveredId: (id: string | null) => void;
  eventPins: EventPinDef[];
  onCompareWith?: (id: string) => void;
}

import { TILE_SIZE, TILE_STEP } from "./unifiedTimeline";

// Силуэт лица в заданной палитре эпохи
const eraHues: Record<string, number> = {
  ERA_1: 190,
  ERA_2: 42,
  ERA_3: 355,
  ERA_4: 30,
  ERA_5: 280,
};

const POSE_SHORT: Record<string, string> = {
  frontal_0: "F",
  frontal_yaw15: "F15",
  frontal_yaw30: "F30",
  profile_L: "ПЛ",
  profile_R: "ПП",
};

const Silhouette: React.FC<{ era: string; seed: number }> = ({ era, seed }) => {
  const hue = eraHues[era] || 200;
  const variant = seed % 4;
  return (
    <svg viewBox="0 0 50 50" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id={`fs-${era}-${seed}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={`hsl(${hue + variant * 3}, 32%, 22%)`} />
          <stop offset="100%" stopColor={`hsl(${hue + variant * 3}, 32%, 10%)`} />
        </linearGradient>
      </defs>
      <rect width="50" height="50" fill={`url(#fs-${era}-${seed})`} />
      <ellipse
        cx={25 + (variant - 1.5) * 0.5}
        cy={21}
        rx={11 - variant * 0.3}
        ry={13}
        fill={`hsl(${hue}, 22%, 34%)`}
      />
      <path
        d={`M 8 50 Q 8 36 25 36 Q 42 36 42 50 Z`}
        fill={`hsl(${hue}, 20%, 16%)`}
      />
    </svg>
  );
};

export const Filmstrip: React.FC<Props> = ({
  photos,
  zoom,
  scrollRatio,
  setScrollRatio,
  playheadRatio,
  selectedId,
  setSelectedId,
  hoveredId,
  setHoveredId,
  onCompareWith,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Единая ширина для всего таймлайна (tracks/filmstrip/verdict используют её же)
  const totalW = photos.length * TILE_STEP;

  useTimelineScroll(scrollRef, {
    zoom,
    scrollRatio,
    setScrollRatio,
    viewportWidth: totalW,
  });

  // Синхронизация scrollLeft со scrollRatio
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    if (maxScroll > 0) {
      const target = scrollRatio * maxScroll;
      if (Math.abs(el.scrollLeft - target) > 1) {
        el.scrollLeft = target;
      }
    }
  }, [scrollRatio]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    if (maxScroll > 0) {
      setScrollRatio(el.scrollLeft / maxScroll);
    }
  };

  // Виртуализация: рендерим только видимые плитки
  const scrollLeft = scrollRatio * Math.max(0, totalW - window.innerWidth);
  const startIdx = Math.max(0, Math.floor(scrollLeft / TILE_STEP) - 2);
  const viewportW = window.innerWidth;
  const visibleCount = Math.ceil(viewportW / TILE_STEP) + 6;
  const endIdx = Math.min(photos.length, startIdx + visibleCount);

  const visibleTiles = useMemo(() => {
    const tiles = [];
    for (let i = startIdx; i < endIdx; i++) {
      tiles.push({ photo: photos[i], idx: i, x: i * TILE_STEP });
    }
    return tiles;
  }, [photos, startIdx, endIdx]);

  // Playhead: ближайшее фото к позиции playheadRatio * totalPhotos
  const playheadIdx = Math.round(playheadRatio * (photos.length - 1));
  const playheadX = playheadIdx * TILE_STEP + TILE_SIZE / 2;
  const localPlayheadX = playheadX - scrollLeft;

  // Hover preview card
  const hoveredTile = hoveredId ? visibleTiles.find((t) => t.photo.id === hoveredId) : null;

  return (
    <div
      className="relative w-full h-full overflow-hidden"
      style={{ minHeight: 80, background: "#0d0d0f", borderBottom: "1px solid rgba(255,255,255,0.08)" }}
    >
      {/* Скроллируемая лента */}
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="absolute inset-0 overflow-x-auto overflow-y-hidden"
      >
        <div
          className="relative"
          style={{ width: totalW, height: "100%", display: "flex", alignItems: "center", padding: "0 8px" }}
        >
          {visibleTiles.map(({ photo, idx, x }) => {
            const era = ERA_DEFS.find((e) => e.id === photo.era)!;
            const isSelected = selectedId === photo.id;
            const isHovered = hoveredId === photo.id;
            const isPlayhead = idx === playheadIdx;
            const qualityColor =
              photo.quality > 0.6 ? "#6daa45" : photo.quality > 0.35 ? "#e8af34" : "#dd6974";
            return (
              <div
                key={photo.id}
                onClick={(e) => {
                  e.stopPropagation();
                  if (e.shiftKey && onCompareWith) {
                    onCompareWith(photo.id);
                  } else {
                    setSelectedId(photo.id);
                  }
                }}
                onMouseEnter={() => setHoveredId(photo.id)}
                onMouseLeave={() => setHoveredId(null)}
                className="absolute cursor-pointer flex-shrink-0"
                style={{
                  left: x + 8,
                  width: TILE_SIZE,
                  height: TILE_SIZE,
                  top: "50%",
                  transform: "translateY(-50%)",
                  border: `2px solid ${
                    isSelected ? "#ff3b30" : isHovered ? "#e2e2e8" : HYP_COLORS[photo.dominant]
                  }`,
                  borderRadius: 3,
                  overflow: "hidden",
                  background: "#13131a",
                  filter: photo.hidden ? "blur(2px) brightness(0.5)" : "none",
                  boxShadow: isSelected
                    ? `0 0 0 1px #ff3b30, 0 4px 12px rgba(255,59,48,0.3)`
                    : isHovered
                      ? `0 4px 10px rgba(0,0,0,0.5)`
                      : isPlayhead
                        ? `0 0 0 1px #ff3b30`
                        : `0 1px 3px rgba(0,0,0,0.3)`,
                  transition: "box-shadow 100ms ease, border-color 100ms ease",
                }}
              >
                <Silhouette era={photo.era} seed={idx} />

                {/* Полоска эпохи сверху */}
                <div
                  className="absolute top-0 left-0 w-full"
                  style={{ height: 2, background: era.color }}
                />

                {/* Дата (очень мелко) */}
                <div
                  className="absolute top-0.5 left-0.5 font-mono rounded"
                  style={{
                    fontSize: 7,
                    padding: "0 2px",
                    background: "rgba(0,0,0,0.6)",
                    color: "#e2e2e8",
                    lineHeight: "10px",
                  }}
                >
                  {photo.date.slice(2, 7)}
                </div>

                {/* Pose */}
                <div
                  className="absolute bottom-0.5 right-0.5 font-mono rounded"
                  style={{
                    fontSize: 7,
                    padding: "0 2px",
                    background: "rgba(0,0,0,0.6)",
                    color: "#7a7a8a",
                    lineHeight: "10px",
                  }}
                >
                  {POSE_SHORT[photo.pose]}
                </div>

                {/* Quality */}
                <div
                  className="absolute bottom-0.5 left-0.5 font-mono rounded"
                  style={{
                    fontSize: 7,
                    padding: "0 2px",
                    background: qualityColor,
                    color: "#0d0d0f",
                    fontWeight: 700,
                    lineHeight: "10px",
                  }}
                >
                  {photo.quality.toFixed(1).slice(2)}
                </div>

                {photo.hidden && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#e2e2e8" strokeWidth="2">
                      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
                      <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
                      <line x1="2" x2="22" y1="2" y2="22" />
                    </svg>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Playhead */}
      {localPlayheadX >= 0 && localPlayheadX <= viewportW && (
        <div
          className="absolute top-0 bottom-0 pointer-events-none"
          style={{ left: localPlayheadX + 8, width: 1, background: "#ff3b30", zIndex: 30 }}
        >
          <div
            className="absolute -top-0.5"
            style={{
              left: -5,
              width: 11,
              height: 8,
              background: "#ff3b30",
              clipPath: "polygon(0 0, 100% 0, 50% 100%)",
            }}
          />
        </div>
      )}

      {/* Hover preview */}
      {hoveredTile && (() => {
        const { photo, x } = hoveredTile;
        const cardX = Math.max(8, Math.min(viewportW - 220, x - scrollLeft + 8 - 80));
        return (
          <div
            className="absolute z-40 pointer-events-none rounded shadow-2xl"
            style={{
              left: cardX,
              top: -128,
              width: 220,
              background: "#13131a",
              border: "1px solid rgba(255,255,255,0.12)",
              padding: 8,
            }}
          >
            <div className="flex gap-2">
              <div
                className="rounded overflow-hidden flex-shrink-0"
                style={{ width: 56, height: 56, border: `2px solid ${HYP_COLORS[photo.dominant]}` }}
              >
                <Silhouette era={photo.era} seed={hoveredTile.idx} />
              </div>
              <div className="flex-1 font-mono text-[10px] min-w-0">
                <div className="text-[#e2e2e8] truncate">{photo.id}</div>
                <div className="text-[#7a7a8a]">{photo.date}</div>
                <div className="text-[#7a7a8a]">
                  {POSE_SHORT[photo.pose]} · качество {photo.quality.toFixed(2)}
                </div>
                <div className="mt-1" style={{ color: FUZZY_COLORS[photo.fuzzyLabel] }}>
                  {photo.fuzzyLabel}
                </div>
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-white/5 flex justify-between font-mono text-[10px]">
              <span style={{ color: HYP_COLORS.H0 }}>Н0 {(photo.p0 * 100).toFixed(0)}%</span>
              <span style={{ color: HYP_COLORS.H1 }}>Н1 {(photo.p1 * 100).toFixed(0)}%</span>
              <span style={{ color: HYP_COLORS.H2 }}>Н2 {(photo.p2 * 100).toFixed(0)}%</span>
            </div>
            {photo.flags.length > 0 && (
              <div className="mt-1 font-mono text-[9px] text-[#e8af34] truncate">
                ⚠ {photo.flags.slice(0, 2).join(", ")}
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
};
