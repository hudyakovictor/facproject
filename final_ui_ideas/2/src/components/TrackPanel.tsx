import React, { useMemo, useRef, useState } from "react";
import { PhotoPoint, ERA_DEFS } from "../types";
import { ZONE_COLORS } from "../utils/timeline";
import { useTimelineScroll } from "../hooks/useTimelineScroll";
import { TILE_STEP, TILE_CENTER, tileCenterX, timelineWidth } from "./unifiedTimeline";

export interface LaneDef {
  key: string;
  label: string;
  color: string;
  getValue: (p: PhotoPoint) => number;
  dashed?: boolean;
}

export const TOP_LANES: LaneDef[] = [
  { key: "bone", label: "КОСТНАЯ СТРУКТУРА", color: ZONE_COLORS.bone, getValue: (p) => p.geometry.boneScore },
  { key: "orbits", label: "ГЛАЗНИЦЫ", color: ZONE_COLORS.orbits, getValue: (p) => p.geometry.orbits },
  { key: "chin", label: "ПОДБОРОДОК", color: ZONE_COLORS.chin, getValue: (p) => p.geometry.chin },
  { key: "jaw", label: "НИЖНЯЯ ЧЕЛЮСТЬ", color: ZONE_COLORS.jaw, getValue: (p) => p.geometry.jaw },
  { key: "cheekbones", label: "СКУЛЫ", color: ZONE_COLORS.cheekbones, getValue: (p) => p.geometry.cheekbones },
  { key: "symmetry", label: "СИММЕТРИЯ", color: ZONE_COLORS.symmetry, getValue: (p) => p.geometry.symmetry },
  { key: "pose", label: "ПОВОРОТ ГОЛОВЫ", color: ZONE_COLORS.pose, getValue: (p) => (p.geometry.poseYaw + 40) / 80, dashed: true },
];

export const BOTTOM_LANES: LaneDef[] = [
  { key: "silicone", label: "ВЕРОЯТН. СИЛИКОНА", color: ZONE_COLORS.silicone, getValue: (p) => p.texture.silicone },
  { key: "gloss", label: "БЛЕСК КОЖИ", color: ZONE_COLORS.gloss, getValue: (p) => p.texture.gloss },
  { key: "lbp", label: "МИКРОТЕКСТУРА", color: ZONE_COLORS.lbp, getValue: (p) => p.texture.lbp },
  { key: "frangi", label: "СОСУДИСТЫЙ РИСУНОК", color: ZONE_COLORS.frangi, getValue: (p) => p.texture.frangi },
  { key: "wrinkle", label: "МОРЩИНЫ", color: ZONE_COLORS.wrinkle, getValue: (p) => p.texture.wrinkle },
  { key: "subsurface", label: "ПОДКОЖНЫЙ СЛОЙ", color: ZONE_COLORS.subsurface, getValue: (p) => p.texture.subsurface },
];

interface TrackPanelProps {
  title: string;
  lanes: LaneDef[];
  photos: PhotoPoint[];
  zoom: number;
  scrollRatio: number;
  setScrollRatio: (v: number) => void;
  playheadRatio: number;
  setPlayheadRatio: (v: number) => void;
  laneHeight: number;
  areaLaneKey?: string;
  hoveredId?: string | null;
  selectedId?: string | null;
  ageLane?: {
    getVisualAge: (p: PhotoPoint) => number;
    getCalendarAge: (p: PhotoPoint) => number;
    minAge: number;
    maxAge: number;
  };
}

export const TrackPanel: React.FC<TrackPanelProps> = ({
  title,
  lanes,
  photos,
  zoom,
  scrollRatio,
  setScrollRatio,
  playheadRatio,
  setPlayheadRatio,
  laneHeight,
  areaLaneKey,
  hoveredId,
  selectedId,
  ageLane,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expandedLane, setExpandedLane] = useState<string | null>(null);

  // Единая ширина = N фото * TILE_STEP
  const totalW = timelineWidth(photos.length);
  const labelW = 140;

  useTimelineScroll(scrollRef, {
    zoom,
    scrollRatio,
    setScrollRatio,
    viewportWidth: totalW,
  });

  React.useEffect(() => {
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

  const totalHeight =
    lanes.reduce((sum, l) => sum + (expandedLane === l.key ? 120 : laneHeight), 0) +
    (ageLane ? laneHeight : 0);

  // Точки для каждой дорожки: по индексу фото (не по timestamp!)
  const laneData = useMemo(() => {
    return lanes.map((lane) => {
      const points = photos.map((p, i) => ({
        x: tileCenterX(i),
        val: Math.max(0, Math.min(1, lane.getValue(p))),
        p,
        i,
      }));

      // Baseline = медиана ERA_1
      const baseline = photos.filter((p) => p.era === "ERA_1");
      const vals = baseline.map(lane.getValue).sort((a, b) => a - b);
      const median = vals[Math.floor(vals.length / 2)] || 0.7;
      const std =
        Math.sqrt(vals.reduce((s, v) => s + (v - median) ** 2, 0) / Math.max(1, vals.length)) || 0.05;
      return { lane, points, median, std };
    });
  }, [lanes, photos]);

  const playheadIdx = Math.round(playheadRatio * (photos.length - 1));
  const playheadX = tileCenterX(playheadIdx);

  // Highlight photo
  const highlightIdx = useMemo(() => {
    const id = selectedId || hoveredId;
    if (!id) return -1;
    return photos.findIndex((p) => p.id === id);
  }, [photos, selectedId, hoveredId]);

  const handlePlotClick = (e: React.MouseEvent) => {
    if (!scrollRef.current) return;
    const rect = scrollRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left + scrollRef.current.scrollLeft;
    const idx = Math.round((x - TILE_CENTER) / TILE_STEP);
    const clamped = Math.max(0, Math.min(photos.length - 1, idx));
    setPlayheadRatio(clamped / Math.max(1, photos.length - 1));
  };

  let yOffset = 0;

  return (
    <div className="flex h-full" style={{ background: "#0d0d0f" }}>
      {/* Label column */}
      <div
        className="flex-shrink-0 overflow-hidden"
        style={{
          width: labelW,
          background: "#13131a",
          borderRight: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div
          className="px-2 font-display tracking-widest flex items-center justify-between"
          style={{
            color: "#7a7a8a",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
            height: 18,
            fontSize: 9,
          }}
        >
          <span>{title}</span>
          <span className="font-mono text-[8px] text-[#4a4a5a]">
            {photos.length.toLocaleString("ru-RU")} фото
          </span>
        </div>
        {lanes.map((lane) => {
          const h = expandedLane === lane.key ? 120 : laneHeight;
          return (
            <div
              key={lane.key}
              onClick={() => setExpandedLane(expandedLane === lane.key ? null : lane.key)}
              className="flex items-center justify-between px-2 cursor-pointer hover:bg-white/3"
              style={{ height: h, borderBottom: "1px solid rgba(255,255,255,0.04)" }}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: lane.color }} />
                <span className="font-mono tracking-wider text-[10px] text-[#e2e2e8] truncate">
                  {lane.label}
                </span>
              </div>
              <span className="font-mono text-[9px] text-[#4a4a5a]">
                {expandedLane === lane.key ? "▾" : "▸"}
              </span>
            </div>
          );
        })}
        {ageLane && (
          <div
            className="flex items-center justify-between px-2"
            style={{ height: laneHeight, borderBottom: "1px solid rgba(255,255,255,0.04)" }}
          >
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: ZONE_COLORS.visualAge }} />
              <span className="font-mono text-[10px] tracking-wider text-[#e2e2e8]">
                ВИЗУАЛЬНЫЙ ВОЗРАСТ
              </span>
            </div>
            <span className="font-mono text-[9px] text-[#4a4a5a]">оценка</span>
          </div>
        )}
      </div>

      {/* Plot area */}
      <div
        ref={scrollRef}
        onScroll={onScroll}
        onClick={handlePlotClick}
        className="flex-1 overflow-x-auto overflow-y-hidden relative"
        style={{ cursor: "crosshair" }}
      >
        <svg width={totalW} height={totalHeight} style={{ display: "block" }}>
          {/* Era background bands (по индексам фото) */}
          {(() => {
            const bands: React.ReactElement[] = [];
            let i = 0;
            while (i < photos.length) {
              const era = photos[i].era;
              let j = i;
              while (j < photos.length && photos[j].era === era) j++;
              const eraDef = ERA_DEFS.find((e) => e.id === era);
              if (eraDef) {
                const l = i * TILE_STEP;
                const r = j * TILE_STEP;
                bands.push(
                  <rect
                    key={`${era}-${i}`}
                    x={l}
                    y={0}
                    width={r - l}
                    height={totalHeight}
                    fill={eraDef.color}
                    opacity={0.05}
                  />
                );
              }
              i = j;
            }
            return bands;
          })()}

          {/* Vertical guides every 50 photos */}
          {photos.length > 0 &&
            Array.from({ length: Math.ceil(photos.length / 50) }).map((_, k) => (
              <line
                key={`guide-${k}`}
                x1={k * 50 * TILE_STEP}
                y1={0}
                x2={k * 50 * TILE_STEP}
                y2={totalHeight}
                stroke="rgba(255,255,255,0.03)"
              />
            ))}

          {/* Lanes */}
          {(() => {
            yOffset = 0;
            return null;
          })()}

          {laneData.map(({ lane, points, median, std }) => {
            const isExpanded = expandedLane === lane.key;
            const h = isExpanded ? 120 : laneHeight;
            const y = yOffset;
            yOffset += h;

            const scaleY = (val: number) => (1 - val) * (h - 6) + 3;
            const pathD = points
              .map((pt, i) => `${i === 0 ? "M" : "L"} ${pt.x.toFixed(1)} ${scaleY(pt.val).toFixed(1)}`)
              .join(" ");
            const isAreaLane = lane.key === areaLaneKey;

            // Anomaly dots (z-score > 2)
            const anomalies = points
              .map((pt) => ({ ...pt, zScore: Math.abs(pt.val - median) / std }))
              .filter((d) => d.zScore > 2 && lane.key !== "bone");

            return (
              <g key={lane.key} transform={`translate(0, ${y})`}>
                <line x1={0} y1={0} x2={totalW} y2={0} stroke="rgba(255,255,255,0.05)" />
                {/* Baseline */}
                <line
                  x1={0}
                  y1={scaleY(median)}
                  x2={totalW}
                  y2={scaleY(median)}
                  stroke="rgba(255,255,255,0.1)"
                  strokeDasharray="2,4"
                />
                {/* Confidence band */}
                {isExpanded && (
                  <>
                    <rect
                      x={0}
                      y={scaleY(Math.min(1, median + std))}
                      width={totalW}
                      height={scaleY(Math.max(0, median - std)) - scaleY(Math.min(1, median + std))}
                      fill="rgba(255,255,255,0.04)"
                    />
                    <text x={4} y={12} fontSize="9" fontFamily="JetBrains Mono" fill="#7a7a8a">
                      ±1σ = {std.toFixed(3)} · медиана = {median.toFixed(3)}
                    </text>
                  </>
                )}

                {/* Impossible flags */}
                {lane.key === lanes[0].key &&
                  photos
                    .map((p, i) => ({ p, x: tileCenterX(i) }))
                    .filter((x) => x.p.flags.includes("IMPOSSIBLE_SHORT"))
                    .map((x, k) => (
                      <rect
                        key={`imp-${k}`}
                        x={x.x - 1}
                        y={0}
                        width={2}
                        height={totalHeight}
                        fill="#dd6974"
                        opacity={0.3}
                      />
                    ))}

                {/* Texture spikes */}
                {lane.key === lanes[0].key &&
                  ageLane &&
                  photos
                    .map((p, i) => ({ p, x: tileCenterX(i) }))
                    .filter((x) => x.p.flags.includes("TEXTURE_SPIKE"))
                    .map((x, k) => (
                      <rect
                        key={`tsp-${k}`}
                        x={x.x - 1}
                        y={0}
                        width={2}
                        height={totalHeight}
                        fill="#fdab43"
                        opacity={0.3}
                      />
                    ))}

                {/* Area fill for BONE SCORE per era */}
                {isAreaLane &&
                  (() => {
                    const segments: React.ReactElement[] = [];
                    let i = 0;
                    while (i < points.length) {
                      const era = points[i].p.era;
                      let j = i;
                      while (j < points.length && points[j].p.era === era) j++;
                      const eraDef = ERA_DEFS.find((e) => e.id === era);
                      if (eraDef && j - i >= 2) {
                        const segPts = points.slice(i, j);
                        const areaD =
                          `M ${segPts[0].x.toFixed(1)} ${h - 3} ` +
                          segPts.map((pt) => `L ${pt.x.toFixed(1)} ${scaleY(pt.val).toFixed(1)}`).join(" ") +
                          ` L ${segPts[segPts.length - 1].x.toFixed(1)} ${h - 3} Z`;
                        segments.push(
                          <path key={era} d={areaD} fill={eraDef.color} opacity={0.22} />
                        );
                      }
                      i = j;
                    }
                    return segments;
                  })()}

                {/* Main line */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={lane.color}
                  strokeWidth={isAreaLane ? 1.5 : 1}
                  strokeDasharray={lane.dashed ? "3,3" : undefined}
                  opacity={0.9}
                />

                {/* Точки метрик — маленькие кружки на каждом фото */}
                {points.map((pt, i) => {
                  // Рендерим только каждые N точек для производительности
                  if (i % 4 !== 0 && !isExpanded) return null;
                  return (
                    <circle
                      key={i}
                      cx={pt.x}
                      cy={scaleY(pt.val)}
                      r={1.2}
                      fill={lane.color}
                      opacity={0.6}
                    />
                  );
                })}

                {/* Anomaly dots */}
                {anomalies.map((d, k) => (
                  <circle
                    key={k}
                    cx={d.x}
                    cy={scaleY(d.val)}
                    r={d.zScore > 3 ? 3.5 : 2.5}
                    fill={d.zScore > 3 ? "#dd6974" : "#e8af34"}
                    className={d.zScore > 3 ? "pulse-critical" : undefined}
                  />
                ))}
              </g>
            );
          })}

          {/* Age lane */}
          {ageLane &&
            (() => {
              const y = yOffset;
              const { getVisualAge, getCalendarAge, minAge, maxAge } = ageLane;
              const ageRange = maxAge - minAge;
              const scaleYAge = (val: number) => (1 - (val - minAge) / ageRange) * (laneHeight - 6) + 3;

              // Точки расхождения > порога
              const gaps = photos
                .map((p, i) => ({
                  p,
                  i,
                  x: tileCenterX(i),
                  gap: Math.abs(getVisualAge(p) - getCalendarAge(p)),
                }))
                .filter((g) => g.gap > 0.06);

              const visualPath = photos
                .map((p, i) => {
                  const x = tileCenterX(i);
                  const yy = scaleYAge(getVisualAge(p));
                  return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${yy.toFixed(1)}`;
                })
                .join(" ");
              const calendarPath = photos
                .map((p, i) => {
                  const x = tileCenterX(i);
                  const yy = scaleYAge(getCalendarAge(p));
                  return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${yy.toFixed(1)}`;
                })
                .join(" ");

              return (
                <g transform={`translate(0, ${y})`}>
                  <line x1={0} y1={0} x2={totalW} y2={0} stroke="rgba(255,255,255,0.05)" />
                  {gaps.map((g, i) => (
                    <rect
                      key={i}
                      x={g.x - 2}
                      y={0}
                      width={4}
                      height={laneHeight}
                      fill="#dd6974"
                      opacity={0.15}
                    />
                  ))}
                  <path d={visualPath} stroke={ZONE_COLORS.visualAge} strokeWidth={1.5} fill="none" />
                  <path d={calendarPath} stroke="#7a7a8a" strokeWidth={1} fill="none" strokeDasharray="4,3" />
                  {gaps.map((g, i) => (
                    <circle
                      key={`gap-${i}`}
                      cx={g.x}
                      cy={scaleYAge(getVisualAge(g.p))}
                      r={3}
                      fill="#dd6974"
                      opacity={0.9}
                    />
                  ))}
                </g>
              );
            })()}

          {/* Linked highlight — вертикальная связь с превью */}
          {highlightIdx >= 0 &&
            (() => {
              const x = tileCenterX(highlightIdx);
              return (
                <g>
                  {/* Вертикальная линия через все дорожки */}
                  <line
                    x1={x}
                    y1={0}
                    x2={x}
                    y2={totalHeight}
                    stroke={selectedId ? "#ff3b30" : "#e2e2e8"}
                    strokeWidth={selectedId ? 1.5 : 1}
                    strokeDasharray={selectedId ? undefined : "2,3"}
                    opacity={selectedId ? 0.9 : 0.5}
                  />
                  {/* Подсветка точек на всех дорожках */}
                  {laneData.map(({ lane, median, std }, idx) => {
                    const h = expandedLane === lane.key ? 120 : laneHeight;
                    let yTop = 0;
                    for (let k = 0; k < idx; k++) {
                      yTop += expandedLane === lanes[k].key ? 120 : laneHeight;
                    }
                    const val = lane.getValue(photos[highlightIdx]);
                    const y = yTop + (1 - val) * (h - 6) + 3;
                    const zScore = Math.abs(val - median) / std;
                    const color = zScore > 3 ? "#dd6974" : zScore > 2 ? "#e8af34" : lane.color;
                    return (
                      <circle
                        key={lane.key}
                        cx={x}
                        cy={y}
                        r={5}
                        fill={color}
                        stroke="#0d0d0f"
                        strokeWidth={2}
                      />
                    );
                  })}
                </g>
              );
            })()}

          {/* Playhead */}
          <line
            x1={playheadX}
            y1={0}
            x2={playheadX}
            y2={totalHeight}
            stroke="#ff3b30"
            strokeWidth={1.5}
          />
        </svg>
      </div>
    </div>
  );
};
