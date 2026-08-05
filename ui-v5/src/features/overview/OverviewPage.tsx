import React from "react";
import { MOCK_FORENSIC_PHOTOS } from "../../shared/mockData";
import { ShieldCheck, Activity, Database, AlertTriangle, Eye, CheckCircle2, Lock } from "lucide-react";
import { Link } from "@tanstack/react-router";

export const OverviewPage: React.FC = () => {
  const poses = [
    { id: "FRONTAL", label: "Фронтальный (Yaw 0° ± 6°)", count: 1420, calibrated: true },
    { id: "LEFT_15", label: "Левый профиль 15°", count: 210, calibrated: true },
    { id: "RIGHT_15", label: "Правый профиль 15°", count: 195, calibrated: true },
    { id: "LEFT_30", label: "Левый боковой 30°", count: 88, calibrated: true },
    { id: "RIGHT_30", label: "Правый боковой 30°", count: 92, calibrated: true },
    { id: "LEFT_45", label: "Левый боковой 45°", count: 32, calibrated: false },
    { id: "RIGHT_45", label: "Правый боковой 45°", count: 38, calibrated: false },
    { id: "LEFT_60", label: "Крайний левый профиль 60°", count: 12, calibrated: false },
    { id: "RIGHT_60", label: "Крайний правый профиль 60°", count: 14, calibrated: false },
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
      {/* READINESS HEADER */}
      <div className="flex items-center justify-between rounded-lg border border-cyan-800/60 bg-[#0b1117] p-5">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300 uppercase">
            <ShieldCheck className="h-5 w-5 text-cyan-400" />
            ОБЗОР ГОТОВНОСТИ ПАЙПЛАЙНА (DEEPUTIN FORENSIC WORKSTATION v5.0)
          </div>
          <div className="text-xs text-slate-300 mt-1">
            Исследование 1900 архивных фотографий Владимира Путина с 1999 по 2026 год в 9 ракурсных корзинах
          </div>
        </div>

        <div className="flex items-center gap-4 font-mono text-xs">
          <div className="rounded bg-[#101820] px-3 py-1.5 border border-[#1f2d3d] text-center">
            <div className="text-[10px] text-slate-400">ВСЕГО ФОТО</div>
            <div className="text-lg font-bold text-white">1,900</div>
          </div>
          <div className="rounded bg-[#101820] px-3 py-1.5 border border-[#1f2d3d] text-center">
            <div className="text-[10px] text-slate-400">LOPO КАЛИБРОВКА</div>
            <div className="text-lg font-bold text-emerald-400">7 / 7 HIGH</div>
          </div>
          <div className="rounded bg-cyan-950 px-3 py-1.5 border border-cyan-800 text-center">
            <div className="text-[10px] text-cyan-300">СТАТУС ИЗВЛЕЧЕНИЯ</div>
            <div className="text-lg font-bold text-white">100% ГОТОВО</div>
          </div>
        </div>
      </div>

      {/* MATRIX OF 9 POSES */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
        <div className="border-b border-[#1f2d3d] pb-2 flex items-center justify-between">
          <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
            МАТРИЦА ПОКРЫТИЯ 9 РАКУРСНЫХ КОРЗИН (POSE COVERAGE MATRIX)
          </span>
          <span className="font-mono text-[11px] text-slate-400">
            Для корзин с числом кадров &lt; 10 применяется ApplicabilityBanner
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-3 gap-4 font-mono text-xs">
          {poses.map((p) => (
            <div
              key={p.id}
              className={`rounded-lg p-4 border transition flex flex-col justify-between ${
                p.calibrated
                  ? "bg-[#101820] border-[#1f2d3d] hover:border-cyan-500/50"
                  : "bg-[#101820]/50 border-amber-900/50"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-white truncate">{p.label}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                    p.calibrated
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                      : "bg-amber-950 text-amber-300 border border-amber-800"
                  }`}
                >
                  {p.calibrated ? "CALIBRATED" : "LIMITED"}
                </span>
              </div>

              <div className="mt-3 flex items-center justify-between text-slate-300">
                <span>Количество кадров:</span>
                <span className="text-cyan-400 font-bold text-sm">{p.count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ANOMALY COUNTERS & CRYPTOGRAPHIC PROVENANCE MANIFEST CARD */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Anomaly Counters */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
          <div className="border-b border-[#1f2d3d] pb-2">
            <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
              СВОДКА ВЫЯВЛЕННЫХ АНОМАЛИЙ НА ТАЙМЛАЙНЕ
            </span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between rounded bg-[#101820] p-3 border border-[#1f2d3d]">
              <span className="flex items-center gap-2 text-rose-300">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500 animate-pulse" />
                Парадоксальные возвраты (A-&gt;B-&gt;A)
              </span>
              <span className="font-bold text-rose-400">1 случай (2012–2014)</span>
            </div>

            <div className="flex items-center justify-between rounded bg-[#101820] p-3 border border-[#1f2d3d]">
              <span className="flex items-center gap-2 text-amber-300">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                Резкие хронологические скачки (Step-Change)
              </span>
              <span className="font-bold text-amber-400">2 случая</span>
            </div>

            <div className="flex items-center justify-between rounded bg-[#101820] p-3 border border-[#1f2d3d]">
              <span className="flex items-center gap-2 text-purple-300">
                <span className="h-2.5 w-2.5 rounded-full bg-purple-500" />
                Переходы между кластерами (#1 -&gt; #2 -&gt; #3)
              </span>
              <span className="font-bold text-purple-400">2 ключевые границы</span>
            </div>
          </div>
        </div>

        {/* SHA-256 Provenance & LOPO Health */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
          <div className="border-b border-[#1f2d3d] pb-2">
            <span className="font-mono text-xs font-bold text-emerald-400 uppercase flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              ЧЕТЫРЕХКОМПОНЕНТНЫЙ ХЕШ-КОНТРАКТ И LOPO 7/7
            </span>
          </div>

          <div className="space-y-2 font-mono text-xs text-slate-300">
            <div className="flex justify-between rounded bg-[#101820] p-2 border border-[#1f2d3d]">
              <span className="text-slate-400">DATASET SHA-256:</span>
              <span className="text-emerald-300">e3b0c442...91b785</span>
            </div>
            <div className="flex justify-between rounded bg-[#101820] p-2 border border-[#1f2d3d]">
              <span className="text-slate-400">CODE COMPILATION:</span>
              <span className="text-cyan-300">GIT ARENA/019FD1DA</span>
            </div>
            <div className="flex justify-between rounded bg-[#101820] p-2 border border-[#1f2d3d]">
              <span className="text-slate-400">BFM MODEL SHA-256:</span>
              <span className="text-white">VERIFIED (3DDFA_v3)</span>
            </div>
            <div className="flex justify-between rounded bg-[#101820] p-2 border border-[#1f2d3d]">
              <span className="text-slate-400">CONFIG SETTINGS:</span>
              <span className="text-amber-300">FDR 0.05 | AXIS GATE ON</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
