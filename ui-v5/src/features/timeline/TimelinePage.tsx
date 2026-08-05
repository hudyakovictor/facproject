import React, { useState } from "react";
import { MOCK_FORENSIC_PHOTOS, type ForensicPhotoPoint } from "../../shared/mockData";
import { Activity, Flag, Camera, ChevronRight, Play, Rewind, FastForward, CheckCircle2, ShieldCheck } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";

interface TimelinePageProps {
  activePose?: string;
  qualityThreshold?: number;
  mouthThreshold?: number;
}

export const TimelinePage: React.FC<TimelinePageProps> = ({
  activePose = "FRONTAL",
  qualityThreshold = 45,
  mouthThreshold = 0.35,
}) => {
  const [photoA, setPhotoA] = useState<string>("p2008_05"); // 2008
  const [photoB, setPhotoB] = useState<string>("p2012_05"); // 2012
  const [hoveredPhoto, setHoveredPhoto] = useState<ForensicPhotoPoint | null>(null);

  // Filter photos based on quality threshold
  const visiblePhotos = MOCK_FORENSIC_PHOTOS.map((p) => ({
    ...p,
    isHidden: p.qualityQ < qualityThreshold || p.mouthOpen > mouthThreshold,
  }));

  // Metric tracks labels corresponding to screen renders
  const metricRows = [
    { key: "qual", label: "кач", desc: "Качество снимка Q" },
    { key: "conf", label: "conf", desc: "Доверие разметки 3DDFA_v3" },
    { key: "bone", label: "bone", desc: "Костно-геометрический SNR" },
    { key: "orb", label: "орб", desc: "Межглазничное расстояние" },
    { key: "zyg", label: "скул", desc: "Ширина скуловых дуг" },
    { key: "sym", label: "сим", desc: "Краниометрическая симметрия" },
  ];

  // Helper to choose color dot tone
  const getDotTone = (rowKey: string, p: ForensicPhotoPoint) => {
    if (p.isHidden) return "border border-slate-700/50 bg-transparent"; // Hollow/hidden
    if (rowKey === "qual") return p.qualityQ >= 80 ? "bg-emerald-400" : "bg-amber-400";
    if (rowKey === "conf") return "bg-emerald-400";
    if (rowKey === "bone") return p.snr >= 17 ? "bg-emerald-400" : "bg-amber-400";
    if (rowKey === "orb") return p.snrDiff < 1.0 ? "bg-emerald-400" : "bg-rose-400";
    if (rowKey === "zyg") return p.boneRmse < 1.0 ? "bg-emerald-400" : "bg-amber-400";
    if (rowKey === "sym") return p.clusterId === 1 ? "bg-emerald-400" : "bg-amber-400";
    return "bg-slate-500";
  };

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-hidden select-none font-sans">
      {/* 100% Full Width Timeline Workstation - Matching Render 35-timeline-focus-v2.png */}
      <div className="flex-1 flex flex-col justify-between px-6 py-4 relative overflow-x-auto">
        
        {/* 1. TOP 6-ROW METRIC MATRIX (Above Photos) */}
        <div className="w-full flex flex-col justify-end border-b border-[#1f2d3d]/80 pb-3 relative">
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-2">
            <span className="flex items-center gap-1.5 text-cyan-400">
              <Activity className="h-3.5 w-3.5" />
              МЕТРИКИ 6/24 (RAW OBJECT-NORMALIZED) · FDR 0.05
            </span>
            <span className="text-slate-400">
              {visiblePhotos.filter((p) => !p.isHidden).length} фото активно ·{" "}
              {visiblePhotos.filter((p) => p.isHidden).length} колонки скрыто
            </span>
          </div>

          {/* 6 Grid Rows */}
          <div className="space-y-1.5 py-1">
            {metricRows.map((row) => (
              <div key={row.key} className="flex items-center justify-between text-xs font-mono">
                {/* Row label left */}
                <span className="w-12 text-right pr-3 font-bold text-slate-400 uppercase">
                  {row.label}
                </span>

                {/* Vertical aligned dots across photos */}
                <div className="flex-1 flex items-center justify-between px-4 relative">
                  {visiblePhotos.map((p, idx) => {
                    const dotClass = getDotTone(row.key, p);
                    const isSelected = p.id === photoA || p.id === photoB;

                    return (
                      <div key={p.id} className="relative flex flex-col items-center">
                        {/* Shaded background strip for hidden columns */}
                        {p.isHidden && row.key === "qual" && (
                          <div className="absolute -top-1 -bottom-24 w-8 bg-[#101820]/60 border-x border-dashed border-[#1f2d3d] pointer-events-none" />
                        )}

                        <button
                          onClick={() => {
                            if (p.id === photoA) return;
                            if (p.id !== photoB && photoA) setPhotoB(p.id);
                            else setPhotoA(p.id);
                          }}
                          onMouseEnter={() => setHoveredPhoto(p)}
                          onMouseLeave={() => setHoveredPhoto(null)}
                          className="p-1 focus:outline-none group"
                        >
                          <div
                            className={`h-2.5 w-2.5 rounded-full transition-transform ${dotClass} ${
                              isSelected ? "scale-150 ring-2 ring-cyan-400/50" : "group-hover:scale-125"
                            }`}
                          />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* BÉZIER COMPARISON BRACKET / BRIDGE BETWEEN PHOTO A & B */}
          <div className="relative h-7 w-full flex items-center justify-center font-mono text-[11px] mt-1">
            <div className="rounded bg-[#101820] px-3 py-1 border border-cyan-700 text-cyan-300 shadow-xl flex items-center gap-3">
              <span>Δ орбита +12%</span>
              <span className="text-slate-500">|</span>
              <span>пара A→B</span>
              <span className="text-slate-500">|</span>
              <span className="text-emerald-400">m ок</span>
            </div>
          </div>
        </div>

        {/* 2. MIDDLE LAYER: ARCHIVAL PUTIN PORTRAITS STRIP */}
        <div className="py-4 my-auto">
          <div className="flex items-center justify-between gap-3 px-4">
            {visiblePhotos.map((p) => {
              const isA = p.id === photoA;
              const isB = p.id === photoB;
              const isFlagged = Boolean(p.anomalyMarker);

              return (
                <div
                  key={p.id}
                  onClick={() => {
                    if (isA) return;
                    if (!photoA || (photoA && photoB)) setPhotoA(p.id);
                    else setPhotoB(p.id);
                  }}
                  className={`relative flex flex-col items-center group cursor-pointer transition-all duration-200 ${
                    p.isHidden ? "opacity-35 grayscale" : "opacity-100"
                  }`}
                >
                  {/* Portrait Card (Matching 35-timeline-focus-v2.png ratio) */}
                  <div
                    className={`h-24 w-20 rounded-md overflow-hidden border-2 bg-[#101820] flex flex-col items-center justify-between p-1 transition-all shadow-xl ${
                      isA
                        ? "border-cyan-400 ring-4 ring-cyan-500/30 z-20"
                        : isB
                        ? "border-amber-400 ring-4 ring-amber-500/30 z-20"
                        : isFlagged
                        ? "border-rose-500/80 hover:border-rose-400"
                        : "border-[#1f2d3d] hover:border-slate-400"
                    }`}
                  >
                    {/* Grayscale Putin Portrait Silhouette SVG */}
                    <div className="w-full flex-1 rounded-sm bg-gradient-to-b from-[#18232d] via-[#101820] to-[#080d12] flex flex-col items-center justify-center relative overflow-hidden">
                      {/* Stylized face contour matching real portraits */}
                      <svg viewBox="0 0 48 60" className="w-12 h-16 opacity-75 text-slate-300">
                        <ellipse cx="24" cy="24" rx="14" ry="18" fill="currentColor" opacity="0.3" />
                        <path
                          d="M 14 24 Q 24 30 34 24 Q 24 40 14 24"
                          fill="currentColor"
                          opacity="0.4"
                        />
                        <rect x="18" y="40" width="12" height="16" fill="currentColor" opacity="0.2" />
                      </svg>

                      {/* Quality Q badge top right */}
                      <span className="absolute top-1 right-1 font-mono text-[8px] text-slate-400">
                        Q:{p.qualityQ}
                      </span>
                    </div>

                    {/* Bottom Cluster strip */}
                    <div
                      className={`w-full h-1 mt-1 rounded-full ${
                        p.clusterId === 1
                          ? "bg-emerald-500"
                          : p.clusterId === 2
                          ? "bg-amber-500"
                          : "bg-cyan-500"
                      }`}
                    />
                  </div>

                  {/* Annotation Tag below photo */}
                  <span
                    className={`mt-1.5 font-mono text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                      isA
                        ? "bg-cyan-950 text-cyan-300 font-bold border border-cyan-700"
                        : isB
                        ? "bg-amber-950 text-amber-300 font-bold border border-amber-700"
                        : "text-slate-400 group-hover:text-white"
                    }`}
                  >
                    {isA
                      ? `A = ${p.timestamp}`
                      : isB
                      ? `B = ${p.timestamp}`
                      : p.year}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 3. BOTTOM LAYERS: ICONS, POSE BAR & MOUNTAIN MINIMAP */}
        <div className="w-full flex flex-col justify-end border-t border-[#1f2d3d]/80 pt-3 space-y-3">
          {/* Icons Row: Hexagons & Flags */}
          <div className="flex items-center justify-between px-4">
            <span className="w-16 font-mono text-[10px] text-slate-500 uppercase">флаги</span>
            <div className="flex-1 flex items-center justify-between px-4">
              {visiblePhotos.map((p) => (
                <div key={p.id} className="h-6 flex items-center justify-center min-w-[32px]">
                  {p.anomalyMarker === "A_B_A" && (
                    <span className="inline-flex items-center gap-1 rounded bg-rose-950/90 px-1.5 py-0.5 font-mono text-[10px] text-rose-300 border border-rose-700 animate-pulse">
                      ⚑ A-&gt;B-&gt;A
                    </span>
                  )}
                  {p.anomalyMarker === "STEP" && (
                    <span className="inline-flex items-center gap-1 rounded bg-amber-950/90 px-1.5 py-0.5 font-mono text-[10px] text-amber-300 border border-amber-700">
                      ⚑ STEP
                    </span>
                  )}
                  {p.anomalyMarker === "CLUSTER_TRANSITION" && (
                    <span className="inline-flex items-center gap-1 rounded bg-purple-950/90 px-1.5 py-0.5 font-mono text-[10px] text-purple-300 border border-purple-700">
                      ⚑ СМЕНА
                    </span>
                  )}
                  {p.anomalyMarker === "MASK_EVIDENCE" && (
                    <span className="inline-flex items-center gap-1 rounded bg-yellow-950/90 px-1.5 py-0.5 font-mono text-[10px] text-yellow-300 border border-yellow-700">
                      ⚑ MASK
                    </span>
                  )}
                  {!p.anomalyMarker && (
                    <span className="font-mono text-[10px] text-slate-700">⬡</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* POSE COVERAGE SEGMENTATION BAR (покрытие pose) */}
          <div className="flex items-center justify-between px-4 text-xs font-mono">
            <span className="w-16 text-[10px] text-slate-500 uppercase">покрытие</span>
            <div className="flex-1 flex h-2 rounded overflow-hidden bg-[#101820] mx-4 border border-[#1f2d3d]">
              <div className="w-[30%] bg-cyan-600/80" title="Yaw 0° ± 6°" />
              <div className="w-[20%] bg-slate-600/80" title="Left 15°" />
              <div className="w-[15%] bg-amber-600/80" title="Right 15°" />
              <div className="w-[20%] bg-purple-600/80" title="Left 30°" />
              <div className="w-[15%] bg-emerald-600/80" title="Right 30°" />
            </div>
          </div>

          {/* MINIMAP: ARCHIVAL DENSITY MOUNTAIN HISTOGRAM + RED FLAG PINS */}
          <div className="flex items-center justify-between px-4 text-xs font-mono">
            <span className="w-16 text-[10px] text-slate-500 uppercase">минимап</span>
            <div className="flex-1 h-12 relative mx-4 bg-[#0b1117] rounded border border-[#1f2d3d] overflow-hidden flex items-end px-2">
              {/* Simulated mountain histogram SVG */}
              <svg className="w-full h-8 overflow-visible" preserveAspectRatio="none">
                <polygon
                  fill="rgba(30, 41, 59, 0.6)"
                  stroke="#334155"
                  strokeWidth="1"
                  points="0,32 5,28 10,24 20,26 30,18 40,22 50,15 60,20 70,12 80,18 90,10 100,16 100,32 0,32"
                  transform="scale(10, 1)"
                />
              </svg>

              {/* Red anomaly flag pins on Minimap */}
              <div className="absolute inset-x-0 top-1 flex justify-between px-6 pointer-events-none">
                <span className="text-rose-500 text-xs font-bold" style={{ left: "28%" }}>
                  ⚑
                </span>
                <span className="text-amber-500 text-xs font-bold" style={{ left: "55%" }}>
                  ⚑
                </span>
                <span className="text-rose-500 text-xs font-bold" style={{ left: "82%" }}>
                  ⚑
                </span>
              </div>

              {/* White Viewport Brackets [   ] */}
              <div className="absolute inset-y-1 left-[25%] right-[25%] border-2 border-white/70 rounded-sm pointer-events-none bg-cyan-500/5" />
            </div>
          </div>

          {/* YEAR SCALE BAR AT BOTTOM (1999–2026) */}
          <div className="flex items-center justify-between px-4 py-1.5 bg-[#0b1117] rounded border border-[#1f2d3d] text-xs font-mono text-slate-400">
            <span>1999</span>
            <span>2001</span>
            <span>2003</span>
            <span>2005</span>
            <span>2008</span>
            <span>2010</span>
            <span>2012</span>
            <span>2014</span>
            <span>2018</span>
            <span>2021</span>
            <span>2024</span>
            <span className="text-cyan-400 font-bold">2026</span>
          </div>
        </div>
      </div>

      {/* FOOTER BAR: MATCHING SCREEN RENDER FOOTER */}
      <div className="h-10 w-full border-t border-[#1f2d3d] bg-[#0b1117] px-6 flex items-center justify-between text-xs font-mono text-slate-400">
        <div className="flex items-center gap-3">
          <button className="hover:text-white transition">⚙</button>
          <button className="hover:text-white transition">⇋</button>
          <button className="hover:text-white transition">⊞</button>
          <button className="hover:text-white transition">↓</button>
          <button className="hover:text-white transition">?</button>
        </div>

        <div className="text-slate-300 font-bold tracking-wider">
          ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ
        </div>

        <div className="text-slate-500">
          run #7 · build 5.2.1 · 1999–2026
        </div>
      </div>
    </div>
  );
};
