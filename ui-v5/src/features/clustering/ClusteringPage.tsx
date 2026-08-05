import React, { useState } from "react";
import { MOCK_FORENSIC_PHOTOS, MOCK_CLUSTERING_BOUNDARIES, type ForensicPhotoPoint } from "../../shared/mockData";
import { Activity, Layers, ShieldCheck, AlertTriangle, CheckCircle2 } from "lucide-react";

export const ClusteringPage: React.FC = () => {
  const [includeAllPoses, setIncludeAllPoses] = useState<boolean>(true);
  const [selectedPose, setSelectedPose] = useState<string>("FRONTAL");
  const [sensitivity, setSensitivity] = useState<number>(0.82);

  // Filter photos by pose if not all poses included
  const photos = MOCK_FORENSIC_PHOTOS.filter((p) => {
    if (includeAllPoses) return true;
    return p.poseBin === selectedPose;
  });

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
      {/* HEADER CONTROLS */}
      <div className="flex items-center justify-between rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4">
        <div className="flex items-center gap-4">
          <div>
            <div className="font-mono text-sm font-bold text-cyan-300 uppercase">
              ХРОНОЛОГИЧЕСКОЕ РАСПРЕДЕЛЕНИЕ КЛАСТЕРОВ (1999–2026)
            </div>
            <div className="text-xs text-slate-400">
              Раскладка наблюдений по всей шкале времени для выявления параллельных или последовательных кластеров
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <label className="flex items-center gap-2 cursor-pointer text-slate-200">
            <input
              type="checkbox"
              checked={includeAllPoses}
              onChange={(e) => setIncludeAllPoses(e.target.checked)}
              className="accent-cyan-500 h-4 w-4"
            />
            <span>Включить все 9 ракурсов (Raw Object-Normalized)</span>
          </label>

          {!includeAllPoses && (
            <select
              value={selectedPose}
              onChange={(e) => setSelectedPose(e.target.value)}
              className="rounded bg-[#141e27] px-2.5 py-1 text-cyan-300 border border-[#1f2d3d]"
            >
              <option value="FRONTAL">Фронтальный (Yaw 0° ± 6°)</option>
              <option value="LEFT_15">Левый профиль 15°</option>
              <option value="RIGHT_15">Правый профиль 15°</option>
            </select>
          )}
        </div>
      </div>

      {/* PARAMETERS BAR */}
      <div className="flex items-center justify-between rounded-lg border border-cyan-800/60 bg-[#0b1117] px-4 py-3 text-xs font-mono">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Чувствительность границы смен:</span>
            <input
              type="range"
              min={0.5}
              max={1.0}
              step={0.05}
              value={sensitivity}
              onChange={(e) => setSensitivity(Number(e.target.value))}
              className="w-28 accent-cyan-500"
            />
            <span className="text-cyan-400">{sensitivity}</span>
          </div>
          <span className="text-slate-500">|</span>
          <span className="text-slate-300">Минимальная длительность кластера: 90 дней (FDR ≤ 0.05)</span>
        </div>
        <div className="text-emerald-400">ПОЛНОЕ КРОСС-РАКУРСНОЕ ОБЪЕДИНЕНИЕ: ВКЛЮЧЕНО</div>
      </div>

      {/* CHRONOLOGICAL CLUSTERING TRACKS ACROSS 1999-2026 */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-6 space-y-6 relative">
        <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 text-xs font-mono text-slate-400">
          <span>ОСЬ Х: ТОЧНЫЙ ДЕНЬ СЪЕМКИ (1999–2026)</span>
          <span>ОСЬ Y: АНАТОМИЧЕСКИЕ КЛАСТЕРЫ #1, #2, #3</span>
        </div>

        {/* TRACK 1: CLUSTER #1 */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="font-bold text-emerald-400">КЛАСТЕР #1: Основной исторический профиль (1999–2007, 2012–2014)</span>
            <span className="text-slate-400">
              {photos.filter((p) => p.clusterId === 1).length} фото
            </span>
          </div>
          <div className="relative h-12 w-full rounded bg-[#101820] border border-emerald-900/60 flex items-center px-4">
            {photos
              .filter((p) => p.clusterId === 1)
              .map((p) => {
                const leftPos = ((p.year - 1999) / 27) * 94 + 3;
                return (
                  <div
                    key={p.id}
                    className="absolute h-8 w-1.5 rounded bg-emerald-400 shadow-emerald-500/50 shadow-md transition hover:scale-125"
                    style={{ left: `${leftPos}%` }}
                    title={`${p.timestamp}: SNR ${p.snr}`}
                  />
                );
              })}
          </div>
        </div>

        {/* TRACK 2: CLUSTER #2 */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="font-bold text-amber-400">КЛАСТЕР #2: Аномальное отклонение скул (2008–2011, 2021)</span>
            <span className="text-slate-400">
              {photos.filter((p) => p.clusterId === 2).length} фото
            </span>
          </div>
          <div className="relative h-12 w-full rounded bg-[#101820] border border-amber-900/60 flex items-center px-4">
            {photos
              .filter((p) => p.clusterId === 2)
              .map((p) => {
                const leftPos = ((p.year - 1999) / 27) * 94 + 3;
                return (
                  <div
                    key={p.id}
                    className="absolute h-8 w-1.5 rounded bg-amber-400 shadow-amber-500/50 shadow-md transition hover:scale-125"
                    style={{ left: `${leftPos}%` }}
                    title={`${p.timestamp}: SNR ${p.snr}`}
                  />
                );
              })}
          </div>
        </div>

        {/* TRACK 3: CLUSTER #3 */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="font-bold text-cyan-400">КЛАСТЕР #3: Поздний морфологический сдвиг (2014–2026)</span>
            <span className="text-slate-400">
              {photos.filter((p) => p.clusterId === 3).length} фото
            </span>
          </div>
          <div className="relative h-12 w-full rounded bg-[#101820] border border-cyan-900/60 flex items-center px-4">
            {photos
              .filter((p) => p.clusterId === 3)
              .map((p) => {
                const leftPos = ((p.year - 1999) / 27) * 94 + 3;
                return (
                  <div
                    key={p.id}
                    className="absolute h-8 w-1.5 rounded bg-cyan-400 shadow-cyan-500/50 shadow-md transition hover:scale-125"
                    style={{ left: `${leftPos}%` }}
                    title={`${p.timestamp}: SNR ${p.snr}`}
                  />
                );
              })}
          </div>
        </div>

        {/* YEAR AXIS AT BOTTOM */}
        <div className="flex items-center justify-between px-4 py-2 bg-[#101820] rounded border border-[#1f2d3d] text-xs font-mono text-slate-400">
          <span>1999</span>
          <span>2003</span>
          <span>2007</span>
          <span>2011</span>
          <span>2015</span>
          <span>2019</span>
          <span>2023</span>
          <span className="text-cyan-400 font-bold">2026</span>
        </div>
      </div>

      {/* BOUNDARY DETECTOR SECTION */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
        <div className="border-b border-[#1f2d3d] pb-2 flex items-center justify-between">
          <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
            ВЫЯВЛЕННЫЕ ГРАНИЦЫ ХРОНОЛОГИЧЕСКИХ СМЕН (BOUNDARY DETECTOR)
          </span>
          <span className="font-mono text-xs text-emerald-400">
            СТАТИСТИЧЕСКАЯ ЗНАЧИМОСТЬ p &lt; 0.001
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {MOCK_CLUSTERING_BOUNDARIES.map((b, i) => (
            <div
              key={i}
              className="rounded-lg border border-[#1f2d3d] bg-[#101820] p-4 space-y-2 hover:border-cyan-500/50 transition"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-cyan-300">ПЕРЕХОД: {b.date}</span>
                <span className="rounded bg-cyan-950 px-2 py-0.5 font-mono text-[10px] text-cyan-300 border border-cyan-800">
                  Кластер #{b.fromCluster} -&gt; #{b.toCluster}
                </span>
              </div>
              <p className="text-xs text-slate-300">{b.description}</p>
              <div className="flex items-center justify-between font-mono text-[11px] text-slate-400 pt-1 border-t border-[#1f2d3d]">
                <span>ΔSNR: {b.deltaSnr}</span>
                <span className="text-emerald-400 font-bold">{b.confidence} CONFIDENCE</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
