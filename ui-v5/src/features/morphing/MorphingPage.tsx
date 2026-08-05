import React, { useState } from "react";
import { MOCK_FORENSIC_PHOTOS, type ForensicPhotoPoint } from "../../shared/mockData";
import { Play, Pause, ZoomIn, Layers, Activity, ShieldCheck, CheckCircle2 } from "lucide-react";
import { FaceMesh3D, type RenderMode } from "../../shared/ui/FaceMesh3D";

export const MorphingPage: React.FC = () => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentYearIndex, setCurrentYearIndex] = useState<number>(4); // 2008
  const [rangeStart, setRangeStart] = useState<number>(1999);
  const [rangeEnd, setRangeEnd] = useState<number>(2026);

  // Checkboxes for layer combinations
  const [showTexture, setShowTexture] = useState<boolean>(true);
  const [showHeatmap, setShowHeatmap] = useState<boolean>(true);
  const [showLandmarks, setShowLandmarks] = useState<boolean>(false);

  const activePhoto = MOCK_FORENSIC_PHOTOS[Math.min(currentYearIndex, MOCK_FORENSIC_PHOTOS.length - 1)];

  // Determine active render mode for 3D Mesh
  const renderMode: RenderMode =
    showHeatmap ? "heatmap" : showTexture ? "3d-solid" : "3d-wireframe";

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6 select-none">
      {/* HEADER: 3D CHRONOLOGY & RANGE ZOOM FOCUS */}
      <div className="flex items-center justify-between rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4">
        <div>
          <div className="font-mono text-sm font-bold text-cyan-300 uppercase">
            ИНТЕРАКТИВНЫЙ 3D-МОРФИНГ И ХРОНОЛОГИЯ (60 FPS INSTANCED MESH)
          </div>
          <div className="text-xs text-slate-400">
            Плавная деформация костной геометрии лица во времени с наложением UV-текстуры и тепловых карт отклонений
          </div>
        </div>

        {/* QUICK RANGE ZOOM PRESETS */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-400">Охват временного диапазона:</span>
          <button
            onClick={() => {
              setRangeStart(1999);
              setRangeEnd(2026);
            }}
            className={`rounded px-2.5 py-1 transition ${
              rangeStart === 1999 && rangeEnd === 2026
                ? "bg-cyan-950 text-cyan-300 border border-cyan-800"
                : "bg-[#141e27] text-slate-300 hover:bg-[#1f2d3d]"
            }`}
          >
            1999–2026 (Полный)
          </button>
          <button
            onClick={() => {
              setRangeStart(2009);
              setRangeEnd(2012);
            }}
            className={`rounded px-2.5 py-1 transition ${
              rangeStart === 2009 && rangeEnd === 2012
                ? "bg-amber-950 text-amber-300 border border-amber-800"
                : "bg-[#141e27] text-slate-300 hover:bg-[#1f2d3d]"
            }`}
          >
            2009–2012 (Зум аномалий)
          </button>
          <button
            onClick={() => {
              setRangeStart(2018);
              setRangeEnd(2026);
            }}
            className={`rounded px-2.5 py-1 transition ${
              rangeStart === 2018 && rangeEnd === 2026
                ? "bg-purple-950 text-purple-300 border border-purple-800"
                : "bg-[#141e27] text-slate-300 hover:bg-[#1f2d3d]"
            }`}
          >
            2018–2026 (Современный)
          </button>
        </div>
      </div>

      {/* CHECKBOXES FOR COMBINING ANY DISPLAY LAYERS */}
      <div className="flex items-center justify-between rounded-lg border border-cyan-800/60 bg-[#0b1117] px-5 py-3 text-xs font-mono">
        <div className="flex items-center gap-6">
          <span className="text-slate-400 uppercase font-bold">Комбинации отображения:</span>
          <label className="flex items-center gap-2 cursor-pointer text-slate-200">
            <input
              type="checkbox"
              checked={showTexture}
              onChange={(e) => setShowTexture(e.target.checked)}
              className="accent-cyan-500 h-4 w-4"
            />
            <span>3D модель + UV текстура</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-slate-200">
            <input
              type="checkbox"
              checked={showHeatmap}
              onChange={(e) => setShowHeatmap(e.target.checked)}
              className="accent-amber-500 h-4 w-4"
            />
            <span>Тепловая карта костных отклонений</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-slate-200">
            <input
              type="checkbox"
              checked={showLandmarks}
              onChange={(e) => setShowLandmarks(e.target.checked)}
              className="accent-emerald-500 h-4 w-4"
            />
            <span>Ключевые точки (Subset-91 / 106)</span>
          </label>
        </div>

        <div className="text-emerald-400">FOCUSED RANGE: {rangeStart} — {rangeEnd}</div>
      </div>

      {/* MAIN 3D MORPHING CANVAS & SIMULATED RENDER */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Main 3D Canvas */}
        <div className="md:col-span-2 h-[420px] rounded-lg border border-[#1f2d3d] bg-[#0b1117] relative overflow-hidden flex flex-col items-center justify-center p-4 shadow-2xl">
          {/* Top Info overlay inside canvas */}
          <div className="absolute top-4 left-4 z-10 font-mono text-xs space-y-1">
            <div className="rounded bg-[#080d12]/90 px-2.5 py-1 text-cyan-300 border border-[#1f2d3d]">
              КАДР МОРФИНГА: {activePhoto.year} ({activePhoto.timestamp})
            </div>
            <div className="rounded bg-[#080d12]/90 px-2.5 py-1 text-slate-300 border border-[#1f2d3d]">
              Режим:{" "}
              {showTexture && showHeatmap
                ? "3D + Текстура + Тепловая карта"
                : showTexture
                ? "3D + Текстура"
                : showHeatmap
                ? "3D + Тепловая карта без текстуры"
                : "Чистый полигональный 3D-меш"}
              {showLandmarks ? " + Ключевые точки" : ""}
            </div>
          </div>

          {/* REAL INTERACTIVE 3D MESH CANVAS */}
          <div className="w-full h-full flex items-center justify-center">
            <FaceMesh3D
              mode={renderMode}
              showKeypoints={showLandmarks}
              year={activePhoto.year}
              snrScore={activePhoto.snr}
              interactive={true}
              className="w-full h-full border-0"
            />
          </div>

          {/* Bottom attribution */}
          <div className="absolute bottom-4 right-4 z-10 font-mono text-[11px] text-slate-400 pointer-events-none">
            3DDFA_v3 Basel Face Model (BFM Topology SHA-256 Verified)
          </div>
        </div>

        {/* Right Info: Morphing Difference & Deviation Stats */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 flex flex-col justify-between">
          <div>
            <div className="border-b border-[#1f2d3d] pb-2 mb-4">
              <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
                ГЕОМЕТРИЧЕСКИЙ ДРЕЙФ И АНОМАЛИИ
              </span>
            </div>

            <div className="space-y-4 font-mono text-xs">
              <div className="rounded bg-[#101820] p-3 border border-[#1f2d3d]">
                <div className="text-slate-400 mb-1">Скуловые дуги (Zygomatic Span):</div>
                <div className="text-white font-bold text-sm">44.2 мм (Δ = +0.4 мм)</div>
              </div>

              <div className="rounded bg-[#101820] p-3 border border-[#1f2d3d]">
                <div className="text-slate-400 mb-1">Межглазничное расстояние:</div>
                <div className="text-white font-bold text-sm">31.8 мм (Δ = 0.0 мм)</div>
              </div>

              <div className="rounded bg-[#101820] p-3 border border-[#1f2d3d]">
                <div className="text-slate-400 mb-1">Угол челюсти:</div>
                <div className="text-white font-bold text-sm">122.1° (Стабильно)</div>
              </div>

              <div className="rounded bg-[#141e27] p-3 border border-cyan-900/60">
                <div className="text-cyan-300 font-bold mb-1">Статус интервала {rangeStart}–{rangeEnd}:</div>
                <div className="text-slate-300">
                  {rangeStart === 2009 && rangeEnd === 2012
                    ? "Внимание: Зафиксировано отклонение A->B->A и снижение SNR до 14.2."
                    : "Анатомическая структура соответствует монотонной кривой старения."}
                </div>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-[#1f2d3d] font-mono text-[11px] text-emerald-400">
            RAW OBJECT-NORMALIZED 3D COORD
          </div>
        </div>
      </div>

      {/* HORIZONTAL TEMPORAL SCRUBBER SLIDER ACROSS FULL WIDTH AT BOTTOM */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-3">
        <div className="flex items-center justify-between font-mono text-xs">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="flex items-center gap-1.5 rounded bg-cyan-600 px-3 py-1.5 font-bold text-white hover:bg-cyan-500 transition shadow-lg shadow-cyan-950"
            >
              {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              <span>{isPlaying ? "ПАУЗА" : "ВОСПРОИЗВЕСТЬ МОРФИНГ"}</span>
            </button>
            <span className="text-slate-400">
              Ручное управление ползунком: перемещайте для замедления на участках аномалий
            </span>
          </div>

          <div className="text-cyan-400 font-bold">
            КАДР {currentYearIndex + 1} / {MOCK_FORENSIC_PHOTOS.length}
          </div>
        </div>

        {/* Scrubber slider across full monitor width */}
        <input
          type="range"
          min={0}
          max={MOCK_FORENSIC_PHOTOS.length - 1}
          step={1}
          value={currentYearIndex}
          onChange={(e) => setCurrentYearIndex(Number(e.target.value))}
          className="w-full accent-cyan-500 h-2 cursor-pointer"
        />

        {/* Year ticks below scrubber */}
        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
          {MOCK_FORENSIC_PHOTOS.map((p, idx) => (
            <button
              key={p.id}
              onClick={() => setCurrentYearIndex(idx)}
              className={`transition hover:text-white ${
                idx === currentYearIndex ? "text-cyan-300 font-bold underline" : ""
              }`}
            >
              {p.year}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
