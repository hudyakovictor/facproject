import React from "react";

export type ViewMode = "FULL" | "ERA_COMPARE" | "CLUSTER";

interface Props {
  dataset: "main" | "calibration";
  setDataset: (v: "main" | "calibration") => void;
  bucket: string;
  setBucket: (v: string) => void;
  zoom: number;
  setZoom: (v: number) => void;
  search: string;
  setSearch: (v: string) => void;
  totalPhotos: number;
  onOpenSources: () => void;
  onToggleFilter: () => void;
  viewMode: ViewMode;
  setViewMode: (v: ViewMode) => void;
}

export const Header: React.FC<Props> = ({
  dataset,
  setDataset,
  bucket,
  setBucket,
  zoom,
  setZoom,
  search,
  setSearch,
  totalPhotos,
  onOpenSources,
  onToggleFilter,
  viewMode,
  setViewMode,
}) => {
  return (
    <div
      className="flex items-center justify-between px-4 border-b border-white/8"
      style={{ height: 48, background: "#13131a" }}
    >
      {/* Left block */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div
            className="font-display font-bold tracking-widest text-sm"
            style={{ color: "#e2e2e8", letterSpacing: "0.22em" }}
          >
            DEEPUTIN
          </div>
          <div
            className="font-mono text-[10px] px-1.5 py-0.5 rounded"
            style={{ background: "#1a1a24", color: "#7a7a8a", border: "1px solid rgba(255,255,255,0.08)" }}
          >
            ХРОНОФОRENЗИКА
          </div>
        </div>
        <div className="h-4 w-px bg-white/10" />
        <div className="flex items-center gap-3 font-mono text-[11px] text-[#7a7a8a]">
          <span>
            АРТЕФАКТ <span className="text-[#e2e2e8]">v2.1.0</span>
          </span>
          <span className="text-[#4a4a5a]">·</span>
          <span>
            <span className="text-[#e2e2e8]">{totalPhotos.toLocaleString("ru-RU")}</span> фото
          </span>
          <span className="text-[#4a4a5a]">·</span>
          <span>
            прогон <span className="text-[#e2e2e8]">04.06.2026</span>
          </span>
        </div>
        <button
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-white/5"
          title="Dataset locked"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </button>
      </div>

      {/* Center block */}
      <div className="flex items-center gap-3">
        <div className="flex items-center rounded" style={{ background: "#1a1a24", border: "1px solid rgba(255,255,255,0.08)" }}>
          <span className="font-mono text-[10px] px-2 text-[#7a7a8a]">ДАТАСЕТ</span>
          {(["main", "calibration"] as const).map((d) => (
            <button
              key={d}
              onClick={() => setDataset(d)}
              className={`px-3 py-1 font-mono text-[11px] uppercase tracking-wider transition ${
                dataset === d ? "bg-white/8 text-[#e2e2e8]" : "text-[#7a7a8a] hover:text-[#e2e2e8]"
              }`}
            >
              {d === "main" ? "ОСНОВНОЙ" : "КАЛИБРОВКА"}
            </button>
          ))}
        </div>

        <div className="flex items-center rounded" style={{ background: "#1a1a24", border: "1px solid rgba(255,255,255,0.08)" }}>
          <span className="font-mono text-[10px] px-2 text-[#7a7a8a]">РЕЖИМ</span>
          <div className="flex">
            {(["FULL", "ERA_COMPARE", "CLUSTER"] as ViewMode[]).map((v) => (
              <button
                key={v}
                onClick={() => setViewMode(v)}
                className={`px-2 py-1 font-mono text-[10px] uppercase tracking-wider transition ${
                  viewMode === v ? "bg-white/8 text-[#e2e2e8]" : "text-[#7a7a8a] hover:text-[#e2e2e8]"
                }`}
              >
                {v === "FULL" ? "ХРОНОЛОГИЯ" : v === "ERA_COMPARE" ? "ЭПОХИ" : "ГРУППЫ"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center rounded" style={{ background: "#1a1a24", border: "1px solid rgba(255,255,255,0.08)" }}>
          <span className="font-mono text-[10px] px-2 text-[#7a7a8a]">РАКУРС</span>
          <select
            value={bucket}
            onChange={(e) => setBucket(e.target.value)}
            className="bg-transparent px-2 py-1 font-mono text-[11px] text-[#e2e2e8] outline-none"
          >
            <option value="all">все</option>
            <option value="frontal_0">фронт</option>
            <option value="frontal_yaw15">фронт 15°</option>
            <option value="frontal_yaw30">фронт 30°</option>
            <option value="profile_L">профиль Л</option>
            <option value="profile_R">профиль П</option>
          </select>
        </div>

        <div className="flex items-center gap-2 rounded px-2" style={{ background: "#1a1a24", border: "1px solid rgba(255,255,255,0.08)" }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#7a7a8a" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="id фото / дата"
            className="bg-transparent py-1 font-mono text-[11px] text-[#e2e2e8] outline-none w-40 placeholder:text-[#4a4a5a]"
          />
        </div>
      </div>

      {/* Right block */}
      <div className="flex items-center gap-2">
        <div className="flex items-center rounded" style={{ background: "#1a1a24", border: "1px solid rgba(255,255,255,0.08)" }}>
          <button
            onClick={() => setZoom(Math.max(0.25, zoom - 0.25))}
            className="w-7 h-7 flex items-center justify-center text-[#7a7a8a] hover:text-[#e2e2e8]"
          >
            −
          </button>
          <div className="px-2 font-mono text-[11px] text-[#e2e2e8] w-14 text-center">
            {Math.round(zoom * 100)}%
          </div>
          <button
            onClick={() => setZoom(Math.min(4, zoom + 0.25))}
            className="w-7 h-7 flex items-center justify-center text-[#7a7a8a] hover:text-[#e2e2e8]"
          >
            +
          </button>
          <button
            onClick={() => setZoom(1)}
            className="px-2 h-7 font-mono text-[10px] text-[#7a7a8a] hover:text-[#e2e2e8] border-l border-white/8"
            title="Показать всё"
          >
            ВСЁ
          </button>
        </div>
        <button
          onClick={onToggleFilter}
          className="flex items-center gap-1.5 px-3 h-8 font-mono text-[11px] tracking-wider rounded hover:bg-white/5 text-[#7a7a8a]"
          style={{ border: "1px solid rgba(255,255,255,0.08)" }}
          title="Фильтры (F)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
          </svg>
          ФИЛЬТР
        </button>
        <button
          onClick={onOpenSources}
          className="flex items-center gap-1.5 px-3 h-8 font-mono text-[11px] tracking-wider rounded hover:bg-white/5 text-[#7a7a8a]"
          style={{ border: "1px solid rgba(255,255,255,0.08)" }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
          </svg>
          ИСТОЧНИКИ
        </button>
        <button className="flex items-center gap-1.5 px-3 h-8 font-mono text-[11px] tracking-wider rounded hover:bg-white/5"
          style={{ border: "1px solid rgba(255,255,255,0.08)", color: "#e2e2e8" }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 3v12m0 0 4-4m-4 4-4-4" />
            <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
          </svg>
          ЭКСПОРТ
        </button>
        <button className="flex items-center gap-1.5 px-3 h-8 font-mono text-[11px] tracking-wider rounded hover:bg-white/5 text-[#7a7a8a]"
          style={{ border: "1px solid rgba(255,255,255,0.08)" }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
            <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
            <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
            <line x1="2" x2="22" y1="2" y2="22" />
          </svg>
          СКРЫТЬ
        </button>
        <button
          className="w-8 h-8 flex items-center justify-center rounded hover:bg-white/5 text-[#7a7a8a]"
          title="Toggle theme"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
          </svg>
        </button>
      </div>
    </div>
  );
};
