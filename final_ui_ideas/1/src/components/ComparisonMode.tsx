/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Photo } from '../types';
import { Sparkles, AlertTriangle, CheckCircle, RefreshCw, X, ArrowLeftRight } from 'lucide-react';

interface ComparisonModeProps {
  photoA: Photo | null;
  photoB: Photo | null;
  onClear: () => void;
}

export default function ComparisonMode({
  photoA,
  photoB,
  onClear
}: ComparisonModeProps) {
  if (!photoA || !photoB) return null;

  // Helper to translate status labels to Russian
  const translateFuzzy = (label: string) => {
    switch (label) {
      case 'STRONGLY_MATCHING': return 'ПОЛНОЕ СОВПАДЕНИЕ';
      case 'CONSISTENT': return 'СОГЛАСОВАНО';
      case 'INSUFFICIENT_DATA': return 'НЕДОСТАТОЧНО ДАННЫХ';
      case 'WEAK_EVIDENCE': return 'СЛАБЫЕ УЛИКИ';
      case 'SUSPICIOUS_TEXTURE': return 'ПОДОЗРИТЕЛЬНАЯ ТЕКСТУРА';
      case 'GEOMETRIC_MISMATCH': return 'КОСТНОЕ РАСХОЖДЕНИЕ';
      case 'IDENTITY_ANOMALY': return 'ЗАМЕНА ЛИЧНОСТИ';
      case 'TEMPORAL_IMPOSSIBILITY': return 'ТЕМПОРАЛЬНЫЙ СБОЙ';
      default: return label;
    }
  };

  // Threshold markers from policy.py mentioned in Section 11 & Appendix A
  const ALLOWED_GEOMETRY_DELTA = 0.018;
  const ALLOWED_TEXTURE_DELTA = 0.04;

  // Compute actual mathematical values
  const getGeometricDelta = (valA: number, valB: number) => {
    const diff = Math.abs(valA - valB);
    const exceeds = diff > ALLOWED_GEOMETRY_DELTA;
    return { diff, exceeds };
  };

  const getTextureDelta = (valA: number, valB: number) => {
    const diff = Math.abs(valA - valB);
    const exceeds = diff > ALLOWED_TEXTURE_DELTA;
    return { diff, exceeds };
  };

  // List of comparisons to draw
  const osteologyCompare = [
    { name: 'Orbit Depth (Глазницы)', valA: photoA.geometry.orbit_depth, valB: photoB.geometry.orbit_depth },
    { name: 'Orbit Fossa (Ямка)', valA: photoA.geometry.orbit_fossa, valB: photoB.geometry.orbit_fossa },
    { name: 'Chin Projection (Подбородок)', valA: photoA.geometry.chin_projection, valB: photoB.geometry.chin_projection },
    { name: 'Gonial Angle (Угол)', valA: photoA.geometry.gonial_angle, valB: photoB.geometry.gonial_angle },
    { name: 'Jaw Width (Челюсть)', valA: photoA.geometry.jaw_width, valB: photoB.geometry.jaw_width },
    { name: 'Ramus Height (Скулы)', valA: photoA.geometry.ramus_height, valB: photoB.geometry.ramus_height },
    { name: 'Symmetry Score (Симметрия)', valA: photoA.geometry.symmetry_score, valB: photoB.geometry.symmetry_score },
  ];

  const textureCompare = [
    { name: 'Silicone Prob (Силикон)', valA: photoA.texture.texture_silicone_prob, valB: photoB.texture.texture_silicone_prob },
    { name: 'Specular Gloss (Блеск)', valA: photoA.texture.texture_specular_gloss, valB: photoB.texture.texture_specular_gloss },
    { name: 'LBP Entropy (Сложность)', valA: photoA.texture.texture_lbp_complexity, valB: photoB.texture.texture_lbp_complexity },
    { name: 'Frangi Vessel (Капилляры)', valA: photoA.texture.texture_frangi_vessel, valB: photoB.texture.texture_frangi_vessel },
    { name: 'Subsurface scatter (Свечение)', valA: photoA.texture.texture_subsurface_scatter_proxy, valB: photoB.texture.texture_subsurface_scatter_proxy },
  ];

  return (
    <div className="fixed inset-x-0 bottom-0 bg-[#0d0d0f]/95 border-t border-white/20 z-50 p-4 font-mono select-none text-white shadow-2xl overflow-y-auto max-h-[50vh] flex flex-col">
      
      {/* Header controls Comparison */}
      <div className="flex justify-between items-center border-b border-white/10 pb-2 mb-3">
        <div className="flex items-center space-x-2">
          <ArrowLeftRight className="w-5 h-5 text-[#fdab43] animate-pulse" />
          <h3 className="font-display font-bold text-xs tracking-wider uppercase">БИОМЕТРИЧЕСКОЕ СРАВНЕНИЕ ДВУХ НАБЛЮДЕНИЙ (DIFF ANALYTICAL MATRIX)</h3>
        </div>
        <button
          onClick={onClear}
          className="flex items-center gap-1.5 p-1 px-2 border border-white/10 rounded text-[9.5px] text-white/50 hover:text-white hover:bg-white/5 cursor-pointer leading-none uppercase"
        >
          <X className="w-3.5 h-3.5" />
          <span>Закрыть диф-режим</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 overflow-y-auto">
        
        {/* LEFT CARD: Photo Point A metadata */}
        <div className="bg-[#13131a] border border-white/10 p-3 rounded flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center bg-white/5 p-1 px-2 rounded-sm border-l-2 border-[#4f98a3] mb-2">
              <span className="font-bold text-[#4f98a3]">ОТБОР (А): {photoA.id}</span>
              <span className="text-[8.5px] font-semibold text-white/50">{photoA.date}</span>
            </div>
            <div className="grid grid-cols-2 gap-y-1 text-[9px] text-white/70 mt-2">
              <p>ЭПОХА / ПЕРИОД:</p>
              <p className="text-right text-[#4f98a3]">{photoA.year < 2012 ? 'Эпоха 1 (Эталон)' : photoA.year < 2015 ? 'Эпоха 2' : photoA.year < 2021 ? 'Эпоха 3 (Удмурт)' : 'Эпоха 5 (Василич)'}</p>

              <p>КАЛЕНДАРНЫЙ ВОЗРАСТ:</p>
              <p className="text-right text-[#e8af34]">{photoA.calendarAge} лет</p>

              <p>БИО-ВНЕШНОСТЬ:</p>
              <p className="text-right text-[#fdab43]">{photoA.visualAge} лет</p>

              <p>СТАТ. ВЕРДИКТ:</p>
              <p className="text-right font-bold text-red-005">{translateFuzzy(photoA.fuzzyLabel)}</p>
            </div>
          </div>
          <div className="mt-4 p-2 bg-black/40 border border-white/5 rounded text-[8px] text-white/40 leading-relaxed uppercase">
            Оригинал взят в качестве аналитической опоры (а), значения отцентрированы.
          </div>
        </div>

        {/* CENTER CARD: Mathematical DELTAS table */}
        <div className="bg-[#1a1a24]/50 border border-white/10 p-3 rounded flex flex-col justify-between">
          <div>
            <p className="text-[8.5px] text-white/40 uppercase mb-2 block border-b border-white/10 pb-1 font-bold">ОТКЛОНЕНИЯ И СИГНАЛЫ (DELTA CALCULATOR)</p>
            
            <div className="space-y-1.5 overflow-y-auto max-h-[160px] pr-1">
              {/* Osteology */}
              <p className="text-[7.5px] text-white/30 font-bold uppercase mt-1">Остеология (Порог: {ALLOWED_GEOMETRY_DELTA}σ):</p>
              {osteologyCompare.map((metric) => {
                const { diff, exceeds } = getGeometricDelta(metric.valA, metric.valB);
                return (
                  <div key={metric.name} className="flex justify-between items-center text-[9px] border-b border-white/5 pb-0.5">
                    <span className="text-white/70">{metric.name}:</span>
                    <span className={`font-bold ${exceeds ? 'text-red-500 font-black animate-pulse bg-red-500/10 px-1 rounded-sm' : 'text-green-500'}`}>
                      {diff.toFixed(3)} {exceeds ? '⚠ AНОМАЛИЯ' : '✓ OK'}
                    </span>
                  </div>
                );
              })}

              {/* Textures */}
              <p className="text-[7.5px] text-white/30 font-bold uppercase mt-2.5">Текстуры кожи (Порог: {ALLOWED_TEXTURE_DELTA}):</p>
              {textureCompare.map((metric) => {
                const { diff, exceeds } = getTextureDelta(metric.valA, metric.valB);
                return (
                  <div key={metric.name} className="flex justify-between items-center text-[9px] border-b border-white/5 pb-0.5">
                    <span className="text-white/70">{metric.name}:</span>
                    <span className={`font-bold ${exceeds ? 'text-[#fdab43] font-black bg-amber-500/10 px-1 rounded-sm' : 'text-green-500'}`}>
                      {diff.toFixed(3)} {exceeds ? '⚠ SPIKE' : '✓ OK'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-2 text-[8px] text-white/40 leading-none flex items-center gap-1 border-t border-white/5 pt-2">
            <AlertTriangle className="w-3.5 h-3.5 text-red-500 shrink-0" />
            <span>КРАСНЫЙ ШТИФТ — Разрыв несовместим с естественным старением субъекта.</span>
          </div>
        </div>

        {/* RIGHT CARD: Photo Point B metadata */}
        <div className="bg-[#13131a] border border-white/10 p-3 rounded flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center bg-white/5 p-1 px-2 rounded-sm border-l-2 border-[#dd6974] mb-2">
              <span className="font-bold text-[#dd6974]">ОТБОР (B): {photoB.id}</span>
              <span className="text-[8.5px] font-semibold text-white/50">{photoB.date}</span>
            </div>
            <div className="grid grid-cols-2 gap-y-1 text-[9px] text-white/70 mt-2">
              <p>ЭПОХА / ПЕРИОД:</p>
              <p className="text-right text-[#dd6974]">{photoB.year < 2012 ? 'Эпоха 1 (Эталон)' : photoB.year < 2015 ? 'Эпоха 2' : photoB.year < 2021 ? 'Эпоха 3 (Удмурт)' : 'Эпоха 5 (Василич)'}</p>

              <p>КАЛЕНДАРНЫЙ ВОЗРАСТ:</p>
              <p className="text-right text-[#e8af34]">{photoB.calendarAge} лет</p>

              <p>БИО-ВНЕШНОСТЬ:</p>
              <p className="text-right text-[#fdab43]">{photoB.visualAge} лет</p>

              <p>СТАТ. ВЕРДИКТ:</p>
              <p className="text-right font-bold text-red-005">{translateFuzzy(photoB.fuzzyLabel)}</p>
            </div>
          </div>
          <div className="mt-4 p-2 bg-[#dd6974]/10 border border-[#dd6974]/20 rounded text-[8.5px] flex items-start gap-1.5 font-bold text-red-400 leading-tight">
            <span>АВТО-ВЕРДИКТ:</span>
            <span>МАТЕМАТИЧЕСКАЯ ВЕРОЯТНОСТЬ ОДНОГО И ТОГО ЖЕ ЛИЦА СТРЕМИТСЯ К НУЛЮ.</span>
          </div>
        </div>

      </div>

    </div>
  );
}
