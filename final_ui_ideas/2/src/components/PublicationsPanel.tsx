import React from "react";
import { EventPinDef } from "../types";

interface Props {
  pins: EventPinDef[];
  onClose: () => void;
}

const KIND_LABEL: Record<string, { label: string; color: string }> = {
  disappearance: { label: "Media", color: "#e8af34" },
  statement: { label: "Political", color: "#5591c7" },
  study: { label: "AI Research", color: "#4f98a3" },
  report: { label: "Political", color: "#797876" },
  era: { label: "Forensic", color: "#a86fdf" },
  return: { label: "Forensic", color: "#6daa45" },
};

export const PublicationsPanel: React.FC<Props> = ({ pins, onClose }) => {
  const [filter, setFilter] = React.useState<string>("all");
  const kinds = ["all", "Media", "Political", "AI Research", "Forensic"];

  const filtered = pins.filter((p) => {
    if (filter === "all") return true;
    return KIND_LABEL[p.kind].label === filter;
  });

  return (
    <div
      className="fixed right-0 top-12 bottom-0 z-40 flex flex-col"
      style={{
        width: 360,
        background: "#13131a",
        borderLeft: "1px solid rgba(255,255,255,0.12)",
        boxShadow: "-8px 0 24px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/8">
        <div>
          <div className="font-display text-[11px] tracking-widest">SOURCES</div>
          <div className="font-mono text-[9px] text-[#7a7a8a] mt-0.5">
            {pins.length} events · _archive/misc/all_publications
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-white/5 text-[#7a7a8a]"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-1 px-3 py-2 border-b border-white/8 flex-wrap">
        {kinds.map((k) => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`px-2 py-0.5 rounded font-mono text-[9px] uppercase tracking-wider ${
              filter === k ? "bg-white/8 text-[#e2e2e8]" : "text-[#7a7a8a] hover:text-[#e2e2e8]"
            }`}
          >
            {k}
          </button>
        ))}
      </div>

      {/* Mini timeline */}
      <div className="px-3 py-2 border-b border-white/8">
        <div className="font-mono text-[9px] text-[#7a7a8a] mb-1">TIMELINE</div>
        <div className="relative h-6" style={{ background: "#0d0d0f" }}>
          {pins.map((p) => {
            const t = new Date(p.date).getTime();
            const start = new Date("1999-01-01").getTime();
            const end = new Date("2027-01-01").getTime();
            const left = ((t - start) / (end - start)) * 100;
            return (
              <div
                key={p.label}
                className="absolute top-1 w-1 h-4"
                style={{ left: `${left}%`, background: p.color }}
              />
            );
          })}
          <div className="absolute bottom-0 left-0 right-0 flex justify-between font-mono text-[8px] text-[#4a4a5a] px-1">
            <span>1999</span>
            <span>2010</span>
            <span>2026</span>
          </div>
        </div>
      </div>

      {/* Sources list */}
      <div className="flex-1 overflow-y-auto">
        {filtered.map((pin) => {
          const kind = KIND_LABEL[pin.kind];
          return (
            <div
              key={pin.label}
              className="px-3 py-3 border-b border-white/5 hover:bg-white/2"
            >
              <div className="flex items-start gap-2">
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ background: pin.color + "22", color: pin.color, fontSize: 10, fontWeight: 700 }}
                >
                  {pin.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-mono text-[10px] text-[#e2e2e8]">{pin.label}</span>
                    <span
                      className="font-mono text-[8px] px-1 py-0.5 rounded"
                      style={{ background: kind.color + "22", color: kind.color }}
                    >
                      {kind.label}
                    </span>
                  </div>
                  <div className="font-mono text-[10px] text-[#7a7a8a] mb-1">{pin.date}</div>
                  <div className="font-mono text-[10px] text-[#e2e2e8] leading-relaxed">{pin.excerpt}</div>
                  <div className="font-mono text-[9px] text-[#4a4a5a] mt-1">— {pin.source}</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
