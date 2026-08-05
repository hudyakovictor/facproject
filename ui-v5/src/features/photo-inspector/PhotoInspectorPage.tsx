import React, { useState } from "react";
import { MOCK_FORENSIC_PHOTOS, type ForensicPhotoPoint } from "../../shared/mockData";
import { ShieldCheck, Layers, Eye, CheckCircle2, Activity, ExternalLink, SlidersHorizontal } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import { FaceMesh3D, type RenderMode } from "../../shared/ui/FaceMesh3D";

export const PhotoInspectorPage: React.FC = () => {
  const [selectedPhoto, setSelectedPhoto] = useState<ForensicPhotoPoint>(MOCK_FORENSIC_PHOTOS[4]); // 2008
  const [showKeypoints, setShowKeypoints] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<RenderMode>("3d-wireframe");

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
      {/* HEADER: PHOTO ID & PROVENANCE METADATA */}
      <div className="flex items-center justify-between rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4">
        <div className="flex items-center gap-4">
          <div>
            <div className="font-mono text-sm font-bold text-cyan-300 uppercase">
              ИНСПЕКТОР ФОТОГРАФИИ: {selectedPhoto.photoId} ({selectedPhoto.timestamp})
            </div>
            <div className="text-xs text-slate-400">
              Полноформатный Split-View: исходное изображение и интерактивная 3D-реконструкция 3DDFA_v3
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <span className="rounded bg-[#101820] px-2.5 py-1 text-slate-300 border border-[#1f2d3d]">
            Ракурс: {selectedPhoto.poseBin}
          </span>
          <span className="rounded bg-cyan-950 px-2.5 py-1 text-cyan-300 border border-cyan-800">
            Качество Q: {selectedPhoto.qualityQ} / 100
          </span>
          <span className="rounded bg-emerald-950 px-2.5 py-1 text-emerald-300 border border-emerald-800 flex items-center gap-1">
            <ShieldCheck className="h-3.5 w-3.5" />
            SHA-256 Verified
          </span>
        </div>
      </div>

      {/* MAIN SPLIT VIEW: PHOTO LEFT + 3D MESH RIGHT */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT AREA: ORIGINAL HIGH-RES PHOTO & ANATOMICAL ZONES */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 flex flex-col justify-between h-[440px]">
          <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-3">
            <span className="font-mono text-xs font-bold text-slate-200 uppercase">
              1. ИСХОДНЫЙ АРХИВНЫЙ КАДР С НАЛОЖЕНИЕМ 21 КОСТНОЙ ЗОНЫ
            </span>
            <span className="font-mono text-[11px] text-slate-400 truncate max-w-xs">
              {selectedPhoto.sourceUrl}
            </span>
          </div>

          <div className="flex-1 rounded-md bg-[#101820] border border-[#1f2d3d] flex flex-col items-center justify-center relative overflow-hidden shadow-inner">
            {/* High-Res Archive Portrait Silhouette with anatomical guidelines */}
            <div className="h-72 w-52 rounded-md border border-cyan-500/40 bg-gradient-to-b from-[#18232d] via-[#101820] to-[#080d12] flex flex-col items-center justify-center relative shadow-2xl">
              <div className="w-24 h-32 rounded-full border border-slate-500/50 bg-[#0b1117]/80 flex flex-col items-center justify-center mb-2">
                <span className="font-mono text-xl font-bold text-cyan-300">ПОРТРЕТ</span>
                <span className="font-mono text-xs text-slate-400">{selectedPhoto.year} г.</span>
              </div>

              {/* Anatomical zone lines simulation */}
              <div className="absolute inset-5 border border-dashed border-cyan-400/50 rounded-sm pointer-events-none" />
              <div className="absolute top-16 left-6 right-6 h-12 border-b border-cyan-500/60 pointer-events-none" />
            </div>

            <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between font-mono text-[11px] text-slate-400 bg-[#080d12]/90 px-3 py-1 rounded border border-[#1f2d3d]">
              <span>EXIF: 85mm f/2.8</span>
              <span>De-lighted Albedo: ОК</span>
            </div>
          </div>
        </div>

        {/* RIGHT AREA: 3D BFM MESH WITH TABS & KEYPOINTS CHECKBOX */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 flex flex-col justify-between h-[440px]">
          <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-3">
            <div className="flex items-center gap-1 font-mono text-xs">
              <button
                onClick={() => setActiveTab("3d-wireframe")}
                className={`rounded px-3 py-1 transition ${
                  activeTab === "3d-wireframe"
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                3D-каркас (Wireframe)
              </button>
              <button
                onClick={() => setActiveTab("uv-texture")}
                className={`rounded px-3 py-1 transition ${
                  activeTab === "uv-texture"
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Только UV-текстура
              </button>
              <button
                onClick={() => setActiveTab("3d-solid")}
                className={`rounded px-3 py-1 transition ${
                  activeTab === "3d-solid"
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                3D модель + текстура
              </button>
            </div>

            <label className="flex items-center gap-1.5 cursor-pointer font-mono text-xs text-slate-300">
              <input
                type="checkbox"
                checked={showKeypoints}
                onChange={(e) => setShowKeypoints(e.target.checked)}
                className="accent-cyan-500 h-3.5 w-3.5"
              />
              <span>Ключевые точки (91/106)</span>
            </label>
          </div>

          {/* 3D INTERACTIVE CANVAS VIEW */}
          <div className="flex-1 flex flex-col items-center justify-center overflow-hidden">
            <FaceMesh3D
              mode={activeTab}
              showKeypoints={showKeypoints}
              year={selectedPhoto.year}
              snrScore={selectedPhoto.snr}
              interactive={true}
              className="w-full h-[320px] shadow-2xl"
            />
          </div>

          <div className="pt-2 border-t border-[#1f2d3d] flex items-center justify-between font-mono text-[11px] text-slate-400">
            <span>Интерактивное вращение 360° мышью</span>
            <span className="text-cyan-400">Raw Object-Normalized 3DDFA_v3</span>
          </div>
        </div>
      </div>

      {/* COMPACT FACTS PANEL (6 STRUCTURED CARDS INSTEAD OF MASSIVE JSON TABLES) */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
        <div className="border-b border-[#1f2d3d] pb-2 flex items-center justify-between">
          <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
            3. КОМПАКТНАЯ ПАНЕЛЬ ФАКТОВ (INFO.JSON &amp; TEXTURE.JSON БЕЗ ГРОМОЗДКИХ ТАБЛИЦ)
          </span>
          <span className="font-mono text-[11px] text-slate-400">
            Отображаются только верифицированные измерения и флаги
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 font-mono text-xs">
          {/* CARD 1 */}
          <div className="rounded-lg bg-[#101820] p-3 border border-[#1f2d3d] flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 uppercase">Костно-геометрический SNR</div>
            <div className="text-xl font-bold text-cyan-300 my-1">{selectedPhoto.snr}</div>
            <div className="text-[10px] text-emerald-400 font-bold">HIGH CONFIDENCE</div>
          </div>

          {/* CARD 2 */}
          <div className="rounded-lg bg-[#101820] p-3 border border-[#1f2d3d] flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 uppercase">Индекс микрорельефа</div>
            <div className="text-xl font-bold text-white my-1">
              {(selectedPhoto.textureIndex * 100).toFixed(0)}%
            </div>
            <div className="text-[10px] text-slate-400">H_detail = 0.88</div>
          </div>

          {/* CARD 3 */}
          <div className="rounded-lg bg-[#101820] p-3 border border-[#1f2d3d] flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 uppercase">Ориентация (Yaw/Pitch/Roll)</div>
            <div className="text-sm font-bold text-cyan-300 my-1">
              +{selectedPhoto.yaw}° / {selectedPhoto.pitch}° / {selectedPhoto.roll}°
            </div>
            <div className="text-[10px] text-emerald-400">Внутри допуска ≤6°</div>
          </div>

          {/* CARD 4 */}
          <div className="rounded-lg bg-[#101820] p-3 border border-[#1f2d3d] flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 uppercase">Мимическая нагрузка</div>
            <div className="text-sm font-bold text-amber-300 my-1">
              Mouth: {selectedPhoto.mouthOpen} | Smile: {selectedPhoto.smileScore}
            </div>
            <div className="text-[10px] text-slate-400">Зона губ: Включена</div>
          </div>

          {/* CARD 5 */}
          <div className="rounded-lg bg-[#101820] p-3 border border-[#1f2d3d] flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 uppercase">Фокус и камера</div>
            <div className="text-sm font-bold text-white my-1">
              {selectedPhoto.focalLengthMm} мм (f/2.8)
            </div>
            <div className="text-[10px] text-slate-400">Ortho-error &lt; 1.2%</div>
          </div>

          {/* CARD 6 */}
          <div className="rounded-lg bg-[#141e27] p-3 border border-emerald-800/80 flex flex-col justify-between">
            <div className="text-[10px] text-emerald-300 uppercase font-bold">Провенанс SHA-256</div>
            <div className="text-xs font-mono text-white my-1 truncate">
              {selectedPhoto.sha256.slice(0, 12)}...
            </div>
            <div className="text-[10px] text-emerald-400">IPFS CID Verified</div>
          </div>
        </div>
      </div>
    </div>
  );
};
