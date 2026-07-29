import React from "react";
import { HYP_COLORS } from "../types";

export const HypothesisLegend: React.FC = () => {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="fixed z-40" style={{ right: 12, bottom: 48 }}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="rounded-lg px-3 py-2 shadow-2xl font-mono text-[10px]"
        style={{
          background: "#13131a",
          border: "1px solid rgba(255,255,255,0.12)",
          width: 200,
        }}
      >
        <div className="font-display text-[9px] tracking-widest text-[#7a7a8a] mb-1.5">ГИПОТЕЗЫ</div>
        <div className="flex items-center gap-2 py-0.5">
          <div className="w-3 h-3 rounded-sm" style={{ background: HYP_COLORS.H0 }} />
          <span className="text-[#e2e2e8]">Н0</span>
          <span className="text-[#7a7a8a]">тот же человек</span>
        </div>
        <div className="flex items-center gap-2 py-0.5">
          <div className="w-3 h-3 rounded-sm" style={{ background: HYP_COLORS.H1 }} />
          <span className="text-[#e2e2e8]">Н1</span>
          <span className="text-[#7a7a8a]">маска / пластика</span>
        </div>
        <div className="flex items-center gap-2 py-0.5">
          <div className="w-3 h-3 rounded-sm" style={{ background: HYP_COLORS.H2 }} />
          <span className="text-[#e2e2e8]">Н2</span>
          <span className="text-[#7a7a8a]">замена личности</span>
        </div>
        <div className="mt-1.5 pt-1.5 border-t border-white/5 flex justify-between text-[9px]">
          <span className="text-[#4a4a5a]">БАЗОВЫЕ</span>
          <span className="text-[#7a7a8a]">Н0 65% · Н1 33% · Н2 2%</span>
        </div>
      </button>
      {open && (
        <div
          className="absolute rounded-lg p-3 shadow-2xl mb-2 font-mono text-[10px]"
          style={{
            bottom: "100%",
            right: 0,
            width: 300,
            background: "#13131a",
            border: "1px solid rgba(255,255,255,0.12)",
          }}
        >
          <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">МЕТОДИКА</div>
          <p className="text-[#e2e2e8] leading-relaxed">
            Байесовская модель пересчитывает базовые вероятности трёх гипотез на основе 21 зоны геометрии лица (106 ключевых точек) и 34 метрик текстуры кожи.
          </p>
          <div className="mt-2 pt-2 border-t border-white/5 text-[#7a7a8a] space-y-0.5">
            <div>· отклонение больше 2σ — аномалия</div>
            <div>· отклонение больше 3σ — критическое</div>
            <div>· невозможно короткий срок: менее 90 дней, отклонение &gt; 1.75σ</div>
            <div>· эталонный период: до 31.12.2002</div>
          </div>
        </div>
      )}
    </div>
  );
};
