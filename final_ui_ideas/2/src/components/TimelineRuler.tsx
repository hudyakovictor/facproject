import React, { useRef, useState, useEffect, useMemo } from "react";
import { ERA_DEFS } from "../types";
import { useTimelineScroll } from "../hooks/useTimelineScroll";
import { TILE_STEP, tileCenterX, timelineWidth } from "./unifiedTimeline";

interface Props {
  photos: any[];
  zoom: number;
  setZoom: (v: number) => void;
  scrollRatio: number;
  setScrollRatio: (v: number) => void;
  playheadRatio: number;
  setPlayheadRatio: (v: number) => void;
}

export const TimelineRuler: React.FC<Props> = ({
  photos,
  zoom,
  setZoom,
  scrollRatio,
  setScrollRatio,
  playheadRatio,
  setPlayheadRatio,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [hoveredEra, setHoveredEra] = useState<string | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  const totalW = timelineWidth(photos.length);

  useTimelineScroll(scrollRef, {
    zoom,
    scrollRatio,
    setScrollRatio,
    viewportWidth: totalW,
    onZoom: (delta) => setZoom(Math.max(0.25, Math.min(4, zoom + delta))),
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

  // Годы как маркеры: для каждого года — позиция первого фото этого года
  const yearMarkers = useMemo(() => {
    const markers: { year: number; x: number; idx: number; isMajor: boolean }[] = [];
    let lastYear = -1;
    for (let i = 0; i < photos.length; i++) {
      const year = photos[i].year;
      if (year !== lastYear) {
        markers.push({
          year,
          x: tileCenterX(i),
          idx: i,
          isMajor: year % 5 === 0,
        });
        lastYear = year;
      }
    }
    return markers;
  }, [photos]);

  // Era segments по индексам
  const eraSegments = useMemo(() => {
    const segments: { era: typeof ERA_DEFS[0]; left: number; width: number; count: number }[] = [];
    let i = 0;
    while (i < photos.length) {
      const era = photos[i].era;
      let j = i;
      while (j < photos.length && photos[j].era === era) j++;
      const eraDef = ERA_DEFS.find((e) => e.id === era);
      if (eraDef) {
        segments.push({
          era: eraDef,
          left: i * TILE_STEP,
          width: (j - i) * TILE_STEP,
          count: j - i,
        });
      }
      i = j;
    }
    return segments;
  }, [photos]);

  const handleRulerClick = (e: React.MouseEvent) => {
    if (!scrollRef.current) return;
    const rect = scrollRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left + scrollRef.current.scrollLeft;
    const idx = Math.round((x - 25) / TILE_STEP);
    const clamped = Math.max(0, Math.min(photos.length - 1, idx));
    setPlayheadRatio(clamped / Math.max(1, photos.length - 1));
  };

  const playheadIdx = Math.round(playheadRatio * (photos.length - 1));
  const playheadX = tileCenterX(playheadIdx);

  // Mini-scrubber (обзор всего таймлайна)
  const miniW = 220;
  const maxScroll = Math.max(1, totalW - (scrollRef.current?.clientWidth || 0));
  const currentOffset = scrollRatio * maxScroll;
  const thumbWidth = Math.max(10, ((scrollRef.current?.clientWidth || 0) / totalW) * miniW);
  const thumbLeft = (currentOffset / Math.max(1, maxScroll)) * (miniW - thumbWidth);

  return (
    <div
      className="relative select-none"
      style={{ height: 44, background: "#0d0d0f", borderTop: "1px solid rgba(255,255,255,0.08)" }}
    >
      {/* Mini-scrubber */}
      <div
        className="absolute top-1 z-10"
        style={{ right: 12, width: miniW, height: 6, background: "#1a1a24", borderRadius: 3 }}
      >
        {eraSegments.map((seg) => {
          const l = (seg.left / totalW) * miniW;
          const w = (seg.width / totalW) * miniW;
          return (
            <div
              key={seg.era.id}
              className="absolute top-0 h-full"
              style={{ left: l, width: w, background: seg.era.color, opacity: 0.7 }}
            />
          );
        })}
        <div
          className="absolute top-0 h-full"
          style={{
            left: thumbLeft,
            width: thumbWidth,
            background: "rgba(255,255,255,0.12)",
            border: "1px solid rgba(255,255,255,0.25)",
            borderRadius: 3,
          }}
        />
      </div>

      {/* Scrollable ruler */}
      <div
        ref={scrollRef}
        onScroll={onScroll}
        onClick={handleRulerClick}
        className="absolute inset-0 overflow-x-auto overflow-y-hidden"
        style={{ cursor: "crosshair" }}
      >
        <div className="relative" style={{ width: totalW, height: "100%" }}>
          {/* Year markers */}
          {yearMarkers.map((m) => (
            <React.Fragment key={m.year}>
              <div
                className="absolute bottom-0"
                style={{
                  left: m.x,
                  width: 1,
                  height: m.isMajor ? 14 : 8,
                  background: m.isMajor ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.12)",
                }}
              />
              <div
                className="absolute font-mono"
                style={{
                  left: m.x + 4,
                  top: 10,
                  fontSize: 9,
                  color: m.isMajor ? "#e2e2e8" : "#7a7a8a",
                }}
              >
                {m.year}
              </div>
            </React.Fragment>
          ))}

          {/* Era color bands */}
          <div className="absolute left-0 right-0" style={{ bottom: 0, height: 6 }}>
            {eraSegments.map((seg) => (
              <div
                key={seg.era.id}
                onMouseEnter={(e) => {
                  setHoveredEra(seg.era.id);
                  setMousePos({ x: e.clientX, y: e.clientY });
                }}
                onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setHoveredEra(null)}
                className="absolute h-full"
                style={{
                  left: seg.left,
                  width: seg.width,
                  background: seg.era.color,
                  opacity: hoveredEra === seg.era.id ? 1 : 0.85,
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Playhead */}
      <div
        className="absolute top-0 h-full pointer-events-none"
        style={{ left: playheadX - (scrollRef.current?.scrollLeft || 0), width: 1, background: "#ff3b30", zIndex: 20 }}
      >
        <div
          className="absolute -top-0.5"
          style={{
            left: -5,
            width: 11,
            height: 10,
            background: "#ff3b30",
            clipPath: "polygon(0 0, 100% 0, 50% 100%)",
          }}
        />
      </div>

      {/* ERA tooltip */}
      {hoveredEra && mousePos && (
        <div
          className="fixed z-50 pointer-events-none px-2 py-1.5 rounded font-mono"
          style={{
            left: mousePos.x + 10,
            top: mousePos.y - 40,
            background: "#13131a",
            border: "1px solid rgba(255,255,255,0.12)",
            color: "#e2e2e8",
            fontSize: 10,
          }}
        >
          {(() => {
            const e = eraSegments.find((s) => s.era.id === hoveredEra)?.era;
            if (!e) return null;
            const count = eraSegments.find((s) => s.era.id === hoveredEra)?.count || 0;
            return (
              <span>
                <span style={{ color: e.color }}>●</span>{" "}
                <span className="text-[#e2e2e8]">{e.label}</span>{" "}
                <span className="text-[#7a7a8a]">
                  · {e.startYear}–{e.endYear} · {count.toLocaleString("ru-RU")} фото
                </span>
              </span>
            );
          })()}
        </div>
      )}
    </div>
  );
};
