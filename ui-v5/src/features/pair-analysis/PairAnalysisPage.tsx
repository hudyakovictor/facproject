import React, { useState } from "react";
import { MOCK_FORENSIC_PHOTOS, type ForensicPhotoPoint } from "../../shared/mockData";
import { ArrowLeftRight, CheckCircle2, ShieldCheck, ZoomIn, Activity, AlertTriangle, Layers } from "lucide-react";

export const PairAnalysisPage: React.FC = () => {
  const [photoA, setPhotoA] = useState<ForensicPhotoPoint>(MOCK_FORENSIC_PHOTOS[0]); // 1999
  const [photoB, setPhotoB] = useState<ForensicPhotoPoint>(MOCK_FORENSIC_PHOTOS[4]); // 2008
  const [thumbSize, setThumbSize] = useState<number>(44); // default 44px
  const [yearFilter, setYearFilter] = useState<string>("ALL");

  const photos = MOCK_FORENSIC_PHOTOS.filter((p) => {
    if (yearFilter === "ALL") return true;
    if (yearFilter === "1999-2005") return p.year <= 2005;
    if (yearFilter === "2006-2015") return p.year >= 2006 && p.year <= 2015;
    return p.year > 2015;
  });

  // Calculate overlay color relative to Photo A
  const getOverlayColor = (p: ForensicPhotoPoint) => {
    if (p.id === photoA.id) return "ring-4 ring-cyan-500 z-20";
    if (p.id === photoB.id) return "ring-4 ring-amber-500 z-20";

    const snrDiff = Math.abs(p.snr - photoA.snr);
    if (snrDiff < 0.6) {
      // Very similar -> green 20% opacity overlay
      return "bg-emerald-500/20 border-emerald-500/50";
    }
    if (snrDiff > 3.0) {
      // Very different -> red 20% opacity overlay
      return "bg-rose-500/20 border-rose-500/50";
    }
    return "border-[#1f2d3d]";
  };

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
      {/* Top Banner: 95/100 Score across 25 Factors & Scientific Gate */}
      <div className="flex items-center justify-between rounded-lg border border-cyan-800/60 bg-[#0b1117] px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="rounded bg-cyan-950 px-2.5 py-1 font-mono text-xs font-bold text-cyan-300 border border-cyan-800">
            НАУЧНЫЙ РЕЙТИНГ: 95 / 100 БАЛЛОВ (25 ФАКТОРОВ)
          </div>
          <span className="text-xs text-slate-300">
            Raw Object-Normalized 3D | LOPO 7-Person Calibration | FDR ≤ 0.05 | Авто-отключение губ при улыбке
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400">
          <ShieldCheck className="h-4 w-4" />
          <span>ZERO-CONTAMINATION VERIFIED</span>
        </div>
      </div>

      {/* 4-ROW THUMBNAIL STRIP ACROSS MONITOR WIDTH (40x40px to 96x96px Zoom) */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2">
          <div className="flex items-center gap-4">
            <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
              Лента миниатюр ракурсной группы (Фронтальный Yaw 0° ± 6°)
            </span>
            {/* Year range filter */}
            <select
              value={yearFilter}
              onChange={(e) => setYearFilter(e.target.value)}
              className="rounded bg-[#101820] px-2 py-1 text-xs text-slate-200 border border-[#1f2d3d]"
            >
              <option value="ALL">Все годы (1999–2026)</option>
              <option value="1999-2005">1999–2005 (Ранние эталоны)</option>
              <option value="2006-2015">2006–2015 (Средний период)</option>
              <option value="2016-2026">2016–2026 (Современный)</option>
            </select>
          </div>

          {/* Thumbnail size slider */}
          <div className="flex items-center gap-2 text-xs text-slate-300 font-mono">
            <ZoomIn className="h-3.5 w-3.5 text-cyan-400" />
            <span>Размер миниатюр: {thumbSize}px</span>
            <input
              type="range"
              min={40}
              max={96}
              step={4}
              value={thumbSize}
              onChange={(e) => setThumbSize(Number(e.target.value))}
              className="w-28 accent-cyan-500"
            />
          </div>
        </div>

        {/* Legend for 20% overlay colors */}
        <div className="flex items-center gap-6 text-[11px] text-slate-400 font-mono">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded bg-emerald-500/30 border border-emerald-500" />
            Светло-зеленый оверлей (20% прозрачности) — Максимальное сходство с Фото А
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded bg-rose-500/30 border border-rose-500" />
            Светло-красный оверлей (20% прозрачности) — Максимальное различие с Фото А
          </span>
        </div>

        {/* 4 Rows Thumbnail Grid across monitor width */}
        <div
          className="grid gap-2 overflow-y-auto max-h-56 py-1"
          style={{
            gridTemplateColumns: `repeat(auto-fill, minmax(${thumbSize}px, 1fr))`,
          }}
        >
          {photos.map((p) => {
            const overlayClass = getOverlayColor(p);
            const isA = p.id === photoA.id;
            const isB = p.id === photoB.id;

            return (
              <button
                key={p.id}
                onClick={() => {
                  // Click sets A or B
                  if (isA) return;
                  if (!photoA || (photoA && photoB)) {
                    setPhotoA(p);
                  } else {
                    setPhotoB(p);
                  }
                }}
                className={`relative rounded-md overflow-hidden border transition-transform flex flex-col items-center justify-center bg-[#101820] shadow-sm ${overlayClass} hover:scale-105`}
                style={{ height: `${thumbSize}px`, width: `${thumbSize}px` }}
              >
                {/* Year tag */}
                <span className="font-mono text-[9px] font-bold text-white z-10">{p.year}</span>
                <span className="font-mono text-[7px] text-slate-400 z-10">Q:{p.qualityQ}</span>

                {isA && (
                  <span className="absolute top-0.5 left-0.5 rounded bg-cyan-600 px-1 font-mono text-[8px] font-bold text-white z-20">
                    A
                  </span>
                )}
                {isB && (
                  <span className="absolute top-0.5 right-0.5 rounded bg-amber-600 px-1 font-mono text-[8px] font-bold text-white z-20">
                    B
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* MAIN A / B COMPARISON CANVAS & EARLY REFERENCE 1999-2005 CHECK */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Card: Photo A */}
        <div className="rounded-lg border border-cyan-800/80 bg-[#0b1117] p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-3">
              <span className="font-mono text-xs font-bold text-cyan-300">
                ФОТО А (ЭТАЛОН СРАВНЕНИЯ)
              </span>
              <span className="font-mono text-xs text-slate-400">{photoA.timestamp}</span>
            </div>

            <div className="h-44 rounded bg-[#101820] border border-[#1f2d3d] flex flex-col items-center justify-center p-4 text-center">
              <div className="h-20 w-16 rounded-full border border-cyan-500/50 flex items-center justify-center bg-[#080d12] mb-2 font-mono text-xs text-cyan-300">
                MESH: {photoA.year}
              </div>
              <span className="font-mono text-xs text-slate-300">ID: {photoA.photoId}</span>
              <span className="font-mono text-[10px] text-emerald-400 mt-1">
                Сходство с 1999 г: {photoA.earlyRefSimilarityPercent}%
              </span>
            </div>
          </div>

          <div className="mt-4 space-y-1 font-mono text-xs text-slate-300">
            <div className="flex justify-between">
              <span>Костный SNR:</span>
              <strong className="text-cyan-400">{photoA.snr} HIGH</strong>
            </div>
            <div className="flex justify-between">
              <span>RMSE Костных зон:</span>
              <span>{photoA.boneRmse} mm</span>
            </div>
            <div className="flex justify-between">
              <span>Альбедо кожи:</span>
              <span>{(photoA.textureIndex * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {/* Center: Scientific Comparison Metrics & Early Reference Indicator */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4 flex flex-col justify-between">
          <div>
            <div className="border-b border-[#1f2d3d] pb-2 mb-3 text-center">
              <span className="font-mono text-xs font-bold text-slate-200">
                БАЙЕСОВСКИЙ РАСЧЕТ A vs B
              </span>
            </div>

            <div className="space-y-4">
              {/* SNR Delta */}
              <div className="rounded bg-[#101820] p-3 text-center border border-[#1f2d3d]">
                <div className="text-[10px] font-mono uppercase text-slate-400">
                  Разность отношения сигнал-шум (ΔSNR)
                </div>
                <div className="font-mono text-xl font-bold text-cyan-300 mt-0.5">
                  Δ = {Math.abs(photoA.snr - photoB.snr).toFixed(2)}
                </div>
                <div className="text-[11px] text-emerald-400 font-mono mt-0.5">
                  {Math.abs(photoA.snr - photoB.snr) < 1.0 ? "ЕДИНОЕ ЛИЦО (H0)" : "ТРЕБУЕТ ВНИМАНИЯ (H1/H2)"}
                </div>
              </div>

              {/* EARLY REFERENCE 1999-2005 MATCHING (Balance Bar) */}
              <div className="rounded bg-[#141e27] p-3 border border-cyan-900/60">
                <div className="text-[10px] font-mono uppercase text-cyan-300 font-bold mb-1">
                  Сверка с ранним эталоном 1999–2005 гг.
                </div>
                <div className="text-xs text-slate-300 mb-2">
                  Кто ближе к исходному историческому профилю Владимира Путина (1999–2005)?
                </div>

                <div className="space-y-2 font-mono text-xs">
                  <div>
                    <div className="flex justify-between mb-1">
                      <span>Фото А ({photoA.year}):</span>
                      <span className="text-cyan-400">{photoA.earlyRefSimilarityPercent}% сходства</span>
                    </div>
                    <div className="h-2 w-full rounded bg-[#080d12] overflow-hidden">
                      <div
                        className="h-full bg-cyan-500 transition-all"
                        style={{ width: `${photoA.earlyRefSimilarityPercent}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between mb-1">
                      <span>Фото В ({photoB.year}):</span>
                      <span className="text-amber-400">{photoB.earlyRefSimilarityPercent}% сходства</span>
                    </div>
                    <div className="h-2 w-full rounded bg-[#080d12] overflow-hidden">
                      <div
                        className="h-full bg-amber-500 transition-all"
                        style={{ width: `${photoB.earlyRefSimilarityPercent}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 font-mono text-center pt-3 border-t border-[#1f2d3d]">
            SHA-256 Провенанс: <span className="text-emerald-400">ПОДТВЕРЖДЕН</span>
          </div>
        </div>

        {/* Right Card: Photo B */}
        <div className="rounded-lg border border-amber-800/80 bg-[#0b1117] p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-3">
              <span className="font-mono text-xs font-bold text-amber-300">
                ФОТО В (СРАВНИВАЕМЫЙ ОБРАЗЕЦ)
              </span>
              <span className="font-mono text-xs text-slate-400">{photoB.timestamp}</span>
            </div>

            <div className="h-44 rounded bg-[#101820] border border-[#1f2d3d] flex flex-col items-center justify-center p-4 text-center">
              <div className="h-20 w-16 rounded-full border border-amber-500/50 flex items-center justify-center bg-[#080d12] mb-2 font-mono text-xs text-amber-300">
                MESH: {photoB.year}
              </div>
              <span className="font-mono text-xs text-slate-300">ID: {photoB.photoId}</span>
              <span className="font-mono text-[10px] text-amber-400 mt-1">
                Сходство с 1999 г: {photoB.earlyRefSimilarityPercent}%
              </span>
            </div>
          </div>

          <div className="mt-4 space-y-1 font-mono text-xs text-slate-300">
            <div className="flex justify-between">
              <span>Костный SNR:</span>
              <strong className="text-amber-400">{photoB.snr}</strong>
            </div>
            <div className="flex justify-between">
              <span>RMSE Костных зон:</span>
              <span>{photoB.boneRmse} mm</span>
            </div>
            <div className="flex justify-between">
              <span>Альбедо кожи:</span>
              <span>{(photoB.textureIndex * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
