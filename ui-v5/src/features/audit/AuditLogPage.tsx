import React from "react";
import { ShieldCheck, Lock, CheckCircle2, AlertTriangle, Clock, History, FileCheck } from "lucide-react";

export const AuditLogPage: React.FC = () => {
  const auditEntries = [
    { id: 1, timestamp: "2026-08-05 12:14:02", user: "Investigator #01", action: "OPEN_SESSION", target: "RUN 2026-08 #04", status: "SUCCESS", hash: "a1b2c3d4e5f6" },
    { id: 2, timestamp: "2026-08-05 12:15:30", user: "Investigator #01", action: "CHANGE_THRESHOLD_Q", target: "Q >= 45.0", status: "APPLIED", hash: "b2c3d4e5f6g7" },
    { id: 3, timestamp: "2026-08-05 12:18:12", user: "Investigator #01", action: "SELECT_PAIR_A_B", target: "A=2009-04-12, B=2012-05-07", status: "SUCCESS", hash: "c3d4e5f6g7h8" },
    { id: 4, timestamp: "2026-08-05 12:22:45", user: "Investigator #01", action: "HYPOTHESIS_SHIFT_BIAS", target: "Shift X = +0.4mm (putin vs udmurt)", status: "APPLIED", hash: "d4e5f6g7h8i9" },
    { id: 5, timestamp: "2026-08-05 12:25:00", user: "Investigator #01", action: "VERIFY_STAGE1_INTEGRITY", target: "1,900 info.json sidecars", status: "IMMUTABLE_OK", hash: "e5f6g7h8i9j0" },
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6 font-sans">
      {/* HEADER: AUDIT LOG & IMMUTABILITY LAYER */}
      <div className="flex items-center justify-between rounded-lg border border-cyan-800/80 bg-[#0b1117] p-5">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300 uppercase">
            <Lock className="h-5 w-5 text-cyan-400" />
            АУДИТ-ЖУРНАЛ СЕССИИ И ВЕРИФИКАЦИЯ НЕИЗМЕНЯЕМОСТИ STAGE 1
          </div>
          <div className="text-xs text-slate-300 mt-1">
            Слой первичных измерений Stage 1 доступен только для чтения; все настройки UI влияют только на Stage 2/3
          </div>
        </div>

        <div className="flex items-center gap-4 font-mono text-xs">
          <div className="rounded bg-emerald-950 px-3 py-1.5 border border-emerald-800 text-emerald-300 font-bold flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4" />
            <span>STAGE 1 INTEGRITY: 100% OK</span>
          </div>
          <button className="rounded bg-cyan-600 px-3 py-1.5 text-white font-bold hover:bg-cyan-500 transition shadow-lg shadow-cyan-950">
            [проверить хеши повторно]
          </button>
        </div>
      </div>

      {/* STAGE 1 IMMUTABILITY CERTIFICATE */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
        <div className="border-b border-[#1f2d3d] pb-2 flex items-center justify-between font-mono text-xs">
          <span className="font-bold text-cyan-300 uppercase">
            КРИПТОГРАФИЧЕСКИЙ РЕГИСТР ЦЕЛОСТНОСТИ ДАННЫХ
          </span>
          <span className="text-slate-400">SHA-256 CHECK PASSED</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono text-xs">
          <div className="rounded bg-[#101820] p-3 border border-[#1f2d3d]">
            <div className="text-slate-400 text-[10px]">RAW IMAGES (1999–2026)</div>
            <div className="text-emerald-400 font-bold mt-1">1,900 FILES MATCHED ✓</div>
            <div className="text-slate-500 text-[10px] truncate mt-1">e3b0...b855</div>
          </div>

          <div className="rounded bg-[#101820] p-3 border border-[#1f2d3d]">
            <div className="text-slate-400 text-[10px]">3DDFA_v3 BFM MESHES</div>
            <div className="text-emerald-400 font-bold mt-1">1,900 MESHES MATCHED ✓</div>
            <div className="text-slate-500 text-[10px] truncate mt-1">f4a1...b889</div>
          </div>

          <div className="rounded bg-[#101820] p-3 border border-[#1f2d3d]">
            <div className="text-slate-400 text-[10px]">UV ALBEDO TEXTURES</div>
            <div className="text-emerald-400 font-bold mt-1">1,900 TEXTURES MATCHED ✓</div>
            <div className="text-slate-500 text-[10px] truncate mt-1">a9c2...c001</div>
          </div>

          <div className="rounded bg-[#101820] p-3 border border-[#1f2d3d]">
            <div className="text-slate-400 text-[10px]">PROVENANCE SIDECARS</div>
            <div className="text-emerald-400 font-bold mt-1">1,900 SIDECARS MATCHED ✓</div>
            <div className="text-slate-500 text-[10px] truncate mt-1">b8d3...c112</div>
          </div>
        </div>
      </div>

      {/* USER AUDIT TRAIL TABLE */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
        <div className="border-b border-[#1f2d3d] pb-2 flex items-center justify-between font-mono text-xs">
          <span className="font-bold text-cyan-300 uppercase">
            ЖУРНАЛ ДЕЙСТВИЙ ИЗУЧАЮЩЕГО СПЕЦИАЛИСТА (APPEND-ONLY LEDGER)
          </span>
          <span className="text-slate-400">СЕССИЯ: ARENA/019FD1DA</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs border-collapse">
            <thead className="bg-[#101820] text-slate-400 uppercase text-[11px] border-b border-[#1f2d3d]">
              <tr>
                <th className="py-2.5 px-4">#</th>
                <th className="py-2.5 px-4">ВРЕМЯ (MSC)</th>
                <th className="py-2.5 px-4">РОЛЬ / ПОЛЬЗОВАТЕЛЬ</th>
                <th className="py-2.5 px-4">ДЕЙСТВИЕ</th>
                <th className="py-2.5 px-4">ОБЪЕКТ / ПАРАМЕТР</th>
                <th className="py-2.5 px-4">СТАТУС</th>
                <th className="py-2.5 px-4">SHA-256 ЗАПИСИ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1f2d3d]/60">
              {auditEntries.map((e) => (
                <tr key={e.id} className="hover:bg-[#101820] transition-colors">
                  <td className="py-3 px-4 text-slate-500">{e.id}</td>
                  <td className="py-3 px-4 text-slate-300">{e.timestamp}</td>
                  <td className="py-3 px-4 font-bold text-white">{e.user}</td>
                  <td className="py-3 px-4 text-cyan-300 font-bold">{e.action}</td>
                  <td className="py-3 px-4 text-slate-200">{e.target}</td>
                  <td className="py-3 px-4">
                    <span className="rounded bg-emerald-950 px-2 py-0.5 text-[10px] text-emerald-300 border border-emerald-800">
                      {e.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">{e.hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
