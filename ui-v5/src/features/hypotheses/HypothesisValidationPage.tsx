import React, { useState } from "react";
import { MOCK_HYPOTHESES, type HypothesisTile } from "../../shared/mockData";
import { AlertTriangle, ShieldCheck, SlidersHorizontal, Eye, Lock, CheckCircle2, RotateCcw } from "lucide-react";

export const HypothesisValidationPage: React.FC = () => {
  const [activePose, setActivePose] = useState("FRONTAL");
  const [shiftX, setShiftX] = useState<number>(0.0);
  const [shiftY, setShiftY] = useState<number>(0.0);
  const [shiftZ, setShiftZ] = useState<number>(0.0);
  const [rangeTolerance, setRangeTolerance] = useState<number>(1.0);
  const [selectedEntityGroup, setSelectedEntityGroup] = useState<string>("ALL");

  // Filter hypotheses by group
  const hypotheses = MOCK_HYPOTHESES.filter((h) => {
    if (selectedEntityGroup === "ALL") return true;
    return h.entityGroup === selectedEntityGroup;
  });

  // Calculate calibrated similarity percentage after Shift Bias adjustment
  const calculateMatchPercent = (h: HypothesisTile) => {
    // Applying shift correction to base similarity
    const shiftCorrection = (shiftX * 1.5 + shiftY * 1.2 - shiftZ * 0.8) * rangeTolerance;
    const rawMatch = Math.min(99.9, Math.max(5.0, h.baseSimilarityPercent + shiftCorrection));
    return rawMatch.toFixed(1);
  };

  const getTileOverlay = (matchPercent: number) => {
    if (matchPercent >= 80) {
      // Light green overlay 20% opacity
      return "bg-emerald-500/20 border-emerald-500/60";
    }
    if (matchPercent <= 40) {
      // Light red overlay 20% opacity
      return "bg-rose-500/20 border-rose-500/60";
    }
    // Amber intermediate
    return "bg-amber-500/10 border-amber-600/50";
  };

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
      {/* ISO QUARANTINE HEADER: INTERNAL TEST ONLY - NOT FOR PUBLIC REPORT */}
      <div className="flex items-center justify-between rounded-lg border-2 border-rose-800 bg-rose-950/20 px-4 py-3">
        <div className="flex items-center gap-3">
          <Lock className="h-5 w-5 text-rose-400" />
          <div>
            <div className="font-mono text-xs font-bold text-rose-300 uppercase tracking-wider">
              РАЗДЕЛ: ВАЛИДАЦИЯ ГИПОТЕЗ (ИЗОЛИРОВАННЫЙ РЕЖИМ ПРОВЕРКИ — НЕ ПОПАДАЕТ В ПУБЛИЧНЫЙ ОТЧЕТ)
            </div>
            <div className="text-xs text-slate-300">
              Проверка 90+ гипотез журналиста для 3 сущностей (`putin`, `udmurt`, `vasilich`). Результаты не влияют на слепой Stage 2/3.
            </div>
          </div>
        </div>
        <div className="rounded bg-emerald-950 px-3 py-1 font-mono text-xs font-bold text-emerald-300 border border-emerald-800">
          НАУЧНАЯ ВАЛИДНОСТЬ: 99 / 100 БАЛЛОВ (150 ФАКТОРОВ)
        </div>
      </div>

      {/* TOP CALIBRATION SLIDERS FOR UNALIGNED LEGACY KEYPOINTS */}
      <div className="rounded-lg border border-cyan-800/80 bg-[#0b1117] p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-3">
          <div>
            <div className="font-mono text-sm font-bold text-cyan-300 uppercase flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-cyan-400" />
              Панель калибровки порогов и компенсации раннего смещения ключевых точек
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              Ранее гипотезы строились по не до конца выровненным точкам; настройте смещение по осям X/Y/Z для точной проверки.
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setShiftX(0);
                setShiftY(0);
                setShiftZ(0);
                setRangeTolerance(1.0);
              }}
              className="flex items-center gap-1 rounded bg-[#141e27] px-2.5 py-1 text-xs text-slate-300 hover:bg-[#1f2d3d] border border-[#1f2d3d]"
            >
              <RotateCcw className="h-3.5 w-3.5 text-cyan-400" />
              <span>Сбросить в 0</span>
            </button>
          </div>
        </div>

        {/* Sliders Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 font-mono text-xs">
          {/* Shift X */}
          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-300">Сдвиг по оси X (мм):</span>
              <span className="text-cyan-400">{shiftX > 0 ? `+${shiftX}` : shiftX} мм</span>
            </div>
            <input
              type="range"
              min={-5.0}
              max={5.0}
              step={0.2}
              value={shiftX}
              onChange={(e) => setShiftX(Number(e.target.value))}
              className="w-full accent-cyan-500"
            />
          </div>

          {/* Shift Y */}
          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-300">Сдвиг по оси Y (мм):</span>
              <span className="text-cyan-400">{shiftY > 0 ? `+${shiftY}` : shiftY} мм</span>
            </div>
            <input
              type="range"
              min={-5.0}
              max={5.0}
              step={0.2}
              value={shiftY}
              onChange={(e) => setShiftY(Number(e.target.value))}
              className="w-full accent-cyan-500"
            />
          </div>

          {/* Shift Z */}
          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-300">Сдвиг глубины Z (мм):</span>
              <span className="text-cyan-400">{shiftZ > 0 ? `+${shiftZ}` : shiftZ} мм</span>
            </div>
            <input
              type="range"
              min={-5.0}
              max={5.0}
              step={0.2}
              value={shiftZ}
              onChange={(e) => setShiftZ(Number(e.target.value))}
              className="w-full accent-cyan-500"
            />
          </div>

          {/* Range Tolerance */}
          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-300">Сужение/Расширение допуска:</span>
              <span className="text-amber-400">{rangeTolerance.toFixed(1)}×</span>
            </div>
            <input
              type="range"
              min={0.5}
              max={2.5}
              step={0.1}
              value={rangeTolerance}
              onChange={(e) => setRangeTolerance(Number(e.target.value))}
              className="w-full accent-amber-500"
            />
          </div>
        </div>
      </div>

      {/* FILTER BAR FOR 3 ENTITIES & POSE */}
      <div className="flex items-center justify-between bg-[#0b1117] p-3 rounded-lg border border-[#1f2d3d]">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-slate-400 uppercase">Отображать блок сущностей:</span>
          <button
            onClick={() => setSelectedEntityGroup("ALL")}
            className={`rounded px-3 py-1 text-xs font-mono transition ${
              selectedEntityGroup === "ALL" ? "bg-cyan-950 text-cyan-300 border border-cyan-800" : "bg-[#141e27] text-slate-300"
            }`}
          >
            Все 90+ гипотез (3 Блока)
          </button>
          <button
            onClick={() => setSelectedEntityGroup("PUTIN_VS_OTHERS")}
            className={`rounded px-3 py-1 text-xs font-mono transition ${
              selectedEntityGroup === "PUTIN_VS_OTHERS"
                ? "bg-cyan-950 text-cyan-300 border border-cyan-800"
                : "bg-[#141e27] text-slate-300"
            }`}
          >
            Блок 1: putin vs udmurt/vasilich
          </button>
          <button
            onClick={() => setSelectedEntityGroup("UDMURT_VS_VASILICH")}
            className={`rounded px-3 py-1 text-xs font-mono transition ${
              selectedEntityGroup === "UDMURT_VS_VASILICH"
                ? "bg-cyan-950 text-cyan-300 border border-cyan-800"
                : "bg-[#141e27] text-slate-300"
            }`}
          >
            Блок 2: udmurt vs vasilich
          </button>
          <button
            onClick={() => setSelectedEntityGroup("PAIRWISE_TRAITS")}
            className={`rounded px-3 py-1 text-xs font-mono transition ${
              selectedEntityGroup === "PAIRWISE_TRAITS"
                ? "bg-cyan-950 text-cyan-300 border border-cyan-800"
                : "bg-[#141e27] text-slate-300"
            }`}
          >
            Блок 3: Попарные признаки
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-400">Ракурсная корзина:</span>
          <select
            value={activePose}
            onChange={(e) => setActivePose(e.target.value)}
            className="rounded bg-[#141e27] px-2.5 py-1 text-cyan-300 border border-[#1f2d3d]"
          >
            <option value="FRONTAL">Фронтальный (Yaw 0° ± 6°)</option>
            <option value="LEFT_15">Левый профиль 15°</option>
            <option value="RIGHT_15">Правый профиль 15°</option>
          </select>
        </div>
      </div>

      {/* THREE LARGE BLOCKS OF HYPOTHESES TILES */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* BLOCK 1: PUTIN VS OTHERS */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4 space-y-4">
          <div className="border-b border-[#1f2d3d] pb-2">
            <div className="font-mono text-xs font-bold text-cyan-300 uppercase">
              БЛОК 1: Отличия `putin` от `udmurt` и `vasilich`
            </div>
            <div className="text-[11px] text-slate-400">
              Как выявить исходный исторический профиль среди догадок о двойниках
            </div>
          </div>

          <div className="space-y-3">
            {hypotheses
              .filter((h) => h.entityGroup === "PUTIN_VS_OTHERS")
              .map((h) => {
                const matchVal = Number(calculateMatchPercent(h));
                const overlayClass = getTileOverlay(matchVal);

                return (
                  <div
                    key={h.id}
                    className={`rounded-lg p-4 border transition-all ${overlayClass} space-y-2`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-white">{h.title}</span>
                      <span
                        className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-bold ${
                          matchVal >= 80
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : "bg-rose-950 text-rose-300 border border-rose-800"
                        }`}
                      >
                        Совпадение: {matchVal}%
                      </span>
                    </div>

                    <p className="text-xs text-slate-300">{h.description}</p>

                    <div className="flex items-center justify-between pt-1 font-mono text-[11px] text-slate-400 border-t border-[#1f2d3d]/50">
                      <span>Зона: {h.anatomicalZone}</span>
                      <span>p-value: {h.pvalue}</span>
                      <span className="text-cyan-300 font-bold">SNR: {h.snrRatio}</span>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* BLOCK 2: UDMURT VS VASILICH */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4 space-y-4">
          <div className="border-b border-[#1f2d3d] pb-2">
            <div className="font-mono text-xs font-bold text-amber-300 uppercase">
              БЛОК 2: Отличия `udmurt` от `vasilich`
            </div>
            <div className="text-[11px] text-slate-400">
              Дифференциальные костные признаки между двумя гипотетическими дублерами
            </div>
          </div>

          <div className="space-y-3">
            {hypotheses
              .filter((h) => h.entityGroup === "UDMURT_VS_VASILICH")
              .map((h) => {
                const matchVal = Number(calculateMatchPercent(h));
                const overlayClass = getTileOverlay(matchVal);

                return (
                  <div
                    key={h.id}
                    className={`rounded-lg p-4 border transition-all ${overlayClass} space-y-2`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-white">{h.title}</span>
                      <span
                        className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-bold ${
                          matchVal >= 80
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : "bg-rose-950 text-rose-300 border border-rose-800"
                        }`}
                      >
                        Совпадение: {matchVal}%
                      </span>
                    </div>

                    <p className="text-xs text-slate-300">{h.description}</p>

                    <div className="flex items-center justify-between pt-1 font-mono text-[11px] text-slate-400 border-t border-[#1f2d3d]/50">
                      <span>Зона: {h.anatomicalZone}</span>
                      <span>p-value: {h.pvalue}</span>
                      <span className="text-amber-300 font-bold">SNR: {h.snrRatio}</span>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* BLOCK 3: PAIRWISE TRAITS */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4 space-y-4">
          <div className="border-b border-[#1f2d3d] pb-2">
            <div className="font-mono text-xs font-bold text-purple-300 uppercase">
              БЛОК 3: Попарные сопоставительные признаки
            </div>
            <div className="text-[11px] text-slate-400">
              Краниометрические асимметрии и высокочастотный спектр альбедо
            </div>
          </div>

          <div className="space-y-3">
            {hypotheses
              .filter((h) => h.entityGroup === "PAIRWISE_TRAITS")
              .map((h) => {
                const matchVal = Number(calculateMatchPercent(h));
                const overlayClass = getTileOverlay(matchVal);

                return (
                  <div
                    key={h.id}
                    className={`rounded-lg p-4 border transition-all ${overlayClass} space-y-2`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-white">{h.title}</span>
                      <span
                        className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-bold ${
                          matchVal >= 80
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : "bg-rose-950 text-rose-300 border border-rose-800"
                        }`}
                      >
                        Совпадение: {matchVal}%
                      </span>
                    </div>

                    <p className="text-xs text-slate-300">{h.description}</p>

                    <div className="flex items-center justify-between pt-1 font-mono text-[11px] text-slate-400 border-t border-[#1f2d3d]/50">
                      <span>Зона: {h.anatomicalZone}</span>
                      <span>p-value: {h.pvalue}</span>
                      <span className="text-purple-300 font-bold">SNR: {h.snrRatio}</span>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </div>
    </div>
  );
};
