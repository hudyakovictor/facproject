import React, { useMemo, useRef, useEffect } from "react";
import { PhotoPoint, ERA_DEFS, FUZZY_COLORS } from "../types";
import { useTimelineScroll } from "../hooks/useTimelineScroll";
import { TILE_STEP, tileCenterX, timelineWidth } from "./unifiedTimeline";

interface Props {
  photos: PhotoPoint[];
  zoom: number;
  scrollRatio: number;
  setScrollRatio: (v: number) => void;
  playheadRatio: number;
}

// Русская inline-легенда fuzzy labels
const FUZZY_LEGEND: { label: string; color: string; short: string }[] = [
  { label: "полное совпадение", color: "#6daa45", short: "СОВП" },
  { label: "соответствует", color: "#4f98a3", short: "СООТВ" },
  { label: "слабые данные", color: "#e8af34", short: "СЛАБ" },
  { label: "подозрит. текстура", color: "#fdab43", short: "ПОДОЗР" },
  { label: "несоответствие геометрии", color: "#dd6974", short: "НЕСООТВ" },
  { label: "аномалия личности", color: "#a13544", short: "АНОМАЛ" },
  { label: "невозможно по времени", color: "#ff3b30", short: "НЕВОЗМ" },
];

export const EraVerdictStrip: React.FC<Props> = ({
  photos,
  zoom,
  scrollRatio,
  setScrollRatio,
  playheadRatio,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const labelW = 140;
  const totalW = timelineWidth(photos.length);

  useTimelineScroll(scrollRef, {
    zoom,
    scrollRatio,
    setScrollRatio,
    viewportWidth: totalW,
  });

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    if (maxScroll > 0) {
      const target = scrollRatio * maxScroll;
      if (Math.abs(el.scrollLeft - target) > 1) el.scrollLeft = target;
    }
  }, [scrollRatio]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    if (maxScroll > 0) setScrollRatio(el.scrollLeft / maxScroll);
  };

  // Era bands — по индексам
  const eraSegments = useMemo(() => {
    const segments: { era: string; left: number; width: number; color: string }[] = [];
    let i = 0;
    while (i < photos.length) {
      const era = photos[i].era;
      let j = i;
      while (j < photos.length && photos[j].era === era) j++;
      const eraDef = ERA_DEFS.find((e) => e.id === era);
      if (eraDef) {
        segments.push({
          era,
          left: i * TILE_STEP,
          width: (j - i) * TILE_STEP,
          color: eraDef.color,
        });
      }
      i = j;
    }
    return segments;
  }, [photos]);

  // Verdict точки — по индексам
  const verdictPts = useMemo(() => {
    return photos.map((p, i) => ({
      x: tileCenterX(i),
      color: FUZZY_COLORS[p.fuzzyLabel],
      label: p.fuzzyLabel,
    }));
  }, [photos]);

  const criticalPts = useMemo(() => {
    return photos
      .map((p, i) => ({ p, x: tileCenterX(i) }))
      .filter((x) => x.p.fuzzyLabel === "TEMPORAL_IMPOSSIBILITY");
  }, [photos]);

  const playheadIdx = Math.round(playheadRatio * (photos.length - 1));
  const playheadX = tileCenterX(playheadIdx);

  return (
    <div className="flex" style={{ background: "#0d0d0f" }}>
      {/* Labels */}
      <div
        className="flex-shrink-0"
        style={{
          width: labelW,
          background: "#13131a",
          borderRight: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div
          className="px-2 flex items-center font-display tracking-widest"
          style={{ color: "#7a7a8a", height: 12, borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: 9 }}
        >
          ЭПОХА
        </div>
        <div
          className="px-2 flex items-center font-display tracking-widest"
          style={{ color: "#7a7a8a", height: 16, fontSize: 9 }}
        >
          ВЕРДИКТ
        </div>
        {/* Inline fuzzy legend */}
        <div className="px-2 py-1 flex flex-wrap gap-x-2 gap-y-0.5 border-t border-white/5">
          {FUZZY_LEGEND.map((f) => (
            <div key={f.label} className="flex items-center gap-1" title={f.label}>
              <div className="w-1.5 h-1.5 rounded-sm" style={{ background: f.color }} />
              <span className="font-mono text-[8px] text-[#7a7a8a]">{f.short}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Plots */}
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 relative overflow-x-auto overflow-y-hidden"
      >
        <div className="relative" style={{ width: totalW }}>
          {/* ERA strip */}
          <div className="relative" style={{ height: 12, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
            {eraSegments.map((seg, i) => (
              <div
                key={`${seg.era}-${i}`}
                className="absolute top-0 h-full"
                style={{ left: seg.left, width: seg.width, background: seg.color, opacity: 0.9 }}
              />
            ))}
          </div>

          {/* Verdict bar */}
          <div className="relative" style={{ height: 16 }}>
            <svg width={totalW} height={16} style={{ display: "block" }}>
              {verdictPts.map((pt, i) => {
                const isCritical = pt.label === "TEMPORAL_IMPOSSIBILITY";
                return (
                  <rect
                    key={i}
                    x={pt.x - 1}
                    y={isCritical ? 0 : 4}
                    width={Math.max(2, isCritical ? 3 : 2)}
                    height={isCritical ? 16 : 8}
                    fill={pt.color}
                    opacity={isCritical ? 1 : 0.85}
                    className={isCritical ? "blink-critical" : undefined}
                  />
                );
              })}
              {criticalPts.map((x, i) => (
                <rect
                  key={`glow-${i}`}
                  x={x.x - 3}
                  y={0}
                  width={6}
                  height={16}
                  fill="#ff3b30"
                  opacity={0.25}
                  className="blink-critical"
                />
              ))}
            </svg>
          </div>

          {/* Playhead */}
          <div
            className="absolute top-0 bottom-0 pointer-events-none"
            style={{ left: playheadX, width: 1, background: "#ff3b30", zIndex: 10 }}
          />
        </div>
      </div>
    </div>
  );
};
