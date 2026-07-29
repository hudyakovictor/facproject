/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Hypothesis } from '../types';
import { Info, HelpCircle, X, CheckCircle, ShieldAlert } from 'lucide-react';

export default function HypothesisLegend() {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <>
      {/* Mini floating container (lower right) */}
      <div 
        onClick={() => setIsExpanded(true)}
        className="fixed bottom-12 right-6 bg-[#0d0d0f]/95 border border-white/10 rounded p-2.5 shadow-2xl z-40 select-none cursor-pointer hover:bg-[#1a1a24]/90 transition duration-150 w-[160px]"
      >
        <div className="flex items-center justify-between border-b border-white/10 pb-1 mb-1.5">
          <span className="font-display font-bold text-[8.5px] tracking-widest text-[#4f98a3] uppercase flex items-center gap-1">
            <HelpCircle className="w-3 h-3 text-[#4f98a3]" />
            <span>ГИПОТЕЗЫ</span>
          </span>
          <span className="text-[7.5px] font-mono text-white/40">АПРИОРНЫЕ</span>
        </div>

        <div className="space-y-1.5 font-mono text-[9px]">
          <div className="flex items-center justify-between text-white">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 bg-[#6daa45] rounded-sm" />
              <span>H0: Тот же</span>
            </div>
            <span className="text-white/50 text-[8.5px] font-bold">0.65</span>
          </div>

          <div className="flex items-center justify-between text-white">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 bg-[#fdab43] rounded-sm" />
              <span>H1: Маска</span>
            </div>
            <span className="text-white/50 text-[8.5px] font-bold">0.33</span>
          </div>

          <div className="flex items-center justify-between text-white">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 bg-[#dd6974] rounded-sm" />
              <span>H2: Смена</span>
            </div>
            <span className="text-white/50 text-[8.5px] font-bold">0.02</span>
          </div>
        </div>

        <p className="text-[7px] font-mono text-white/30 text-center uppercase tracking-wider mt-2 hover:text-white transition">🔍 Инфотолкование</p>
      </div>

      {/* Expanded methodology Modal */}
      {isExpanded && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#13131a] border border-white/15 rounded-md p-5 w-full max-w-[480px] font-mono select-none shadow-2xl">
            <div className="flex justify-between items-start border-b border-white/10 pb-2 mb-3">
              <div className="flex items-center gap-2">
                <Info className="w-5 h-5 text-[#4f98a3]" />
                <h3 className="font-display font-semibold text-sm text-white tracking-wider">МЕТОДОЛОГИЯ БАЙЕСОВСКОГО ВЕРДИКТА</h3>
              </div>
              <button 
                onClick={() => setIsExpanded(false)}
                className="text-white/40 hover:text-white p-1 hover:bg-white/5 rounded cursor-pointer transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-[10px] text-white/80 space-y-3.5 leading-relaxed">
              <p>
                Байесовский ИИ-классификатор производит апостериорный расчет вероятностей (posteriors) по трем исключающим друг друга гипотезам (H0, H1, H2), взвешивая геометрические и текстурные дельты относительно эталонного профиля.
              </p>

              <div className="space-y-2.5">
                <div className="p-2 bg-[#6daa45]/10 rounded border border-[#6daa45]/20 flex gap-2.5 items-start">
                  <CheckCircle className="w-4 h-4 text-[#6daa45] shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-white">H0: SAME_PERSON (Один и тот же человек)</h4>
                    <p className="text-white/60 text-[9.5px] mt-0.5">Естественное старение. Внутренние колебания остеологии лица не выходят за рамки 1.5σ отклонений. Физиология симметрична.</p>
                  </div>
                </div>

                <div className="p-2 bg-[#fdab43]/10 rounded border border-[#fdab43]/20 flex gap-2.5 items-start">
                  <ShieldAlert className="w-4 h-4 text-[#fdab43] shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-white">H1: MASK_SURGERY (Маска / Инвазивная косметология)</h4>
                    <p className="text-white/60 text-[9.5px] mt-0.5">Маскировка, филлеры или силиконовые накладки. Текстурный анализ кожи выдает сильный рост specular_gloss, LBP асинхронию и неестественное омоложение.</p>
                  </div>
                </div>

                <div className="p-2 bg-[#dd6974]/10 rounded border border-[#dd6974]/20 flex gap-2.5 items-start">
                  <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-white">H2: IDENTITY_SWAP (Замена личности / Подмена)</h4>
                    <p className="text-white/60 text-[9.5px] mt-0.5">Кардинальное различие. Костные структуры орбитальных впадин ушей, подбородка и ширины скул выходят за критические 3σ. Различие регистрируется на кратких интервалах времени.</p>
                  </div>
                </div>
              </div>

              <div className="bg-black/40 border border-white/5 p-3 rounded text-[9.5px] space-y-1 text-white/55">
                <p className="font-semibold text-white/80 mb-1">ФОРМУЛИРОВКА ПРИОРОB СКОРИНГА (Constants.py):</p>
                <p>• Prior H0 (Same Person) = 65% — презумпция тождественности</p>
                <p>• Prior H1 (Cosmetology) = 33% — вероятность хирургических масок</p>
                <p>• Prior H2 (Identity Swap) = 2% — априорное допущение смены персон</p>
              </div>
            </div>

            <div className="mt-4 border-t border-white/15 pt-3 text-right">
              <button
                onClick={() => setIsExpanded(false)}
                className="px-3 py-1 bg-[#4f98a3] hover:bg-[#4f98a3]/85 text-black font-semibold rounded text-[10.5px] transition cursor-pointer"
              >
                ПРИНЯТЬ СВЕДЕНИЯ
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
