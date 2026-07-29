import { useState, useMemo, useEffect, useRef } from "react";
import { Header, ViewMode } from "./components/Header";
import { EraCompareView, ClusterView, ComparisonView } from "./components/AlternativeViews";
import { ERA_DEFS } from "./types";
import { TimelineRuler } from "./components/TimelineRuler";
import { Filmstrip } from "./components/Filmstrip";
import { TrackPanel, TOP_LANES, BOTTOM_LANES } from "./components/TrackPanel";
import { EraVerdictStrip } from "./components/EraVerdictStrip";
import { LeftPanel } from "./components/LeftPanel";
import { HypothesisLegend } from "./components/HypothesisLegend";
import { PublicationsPanel } from "./components/PublicationsPanel";
import { generateDataset, EVENT_PINS } from "./data/mockData";

export default function App() {
  const allPhotos = useMemo(() => generateDataset(), []);

  const [dataset, setDataset] = useState<"main" | "calibration">("main");
  const [bucket, setBucket] = useState("all");
  const [zoom, setZoom] = useState(1.25);
  const [scrollRatio, setScrollRatio] = useState(0);
  const [playheadRatio, setPlayheadRatio] = useState(0.45);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);

  // Filters
  const [viewMode, setViewMode] = useState<ViewMode>("FULL");
  const [comparisonIds, setComparisonIds] = useState<[string, string] | null>(null);

  // Multi-select filters
  const [filterAnomaliesOnly, setFilterAnomaliesOnly] = useState(false);
  const [filterConfidence, setFilterConfidence] = useState(0);
  const [filterLowQuality, setFilterLowQuality] = useState(false);
  const [filterEras, setFilterEras] = useState<Set<string>>(new Set(["ERA_1", "ERA_2", "ERA_3", "ERA_4", "ERA_5"]));
  const [filterHyp, setFilterHyp] = useState<Set<string>>(new Set(["H0", "H1", "H2"]));
  const [filterFlags, setFilterFlags] = useState<Set<string>>(new Set());

  const containerRef = useRef<HTMLDivElement>(null);
  // viewportWidth больше не нужен — таймлайн сам определяет ширину по количеству фото
  void containerRef;

  // Keyboard shortcut
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return;
      if (e.key === "f" || e.key === "F") setFilterOpen((v) => !v);
      if (e.key === "Escape") {
        setSelectedId(null);
        setSourcesOpen(false);
        setFilterOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Apply filters
  const filteredPhotos = useMemo(() => {
    return allPhotos.filter((p) => {
      if (dataset === "calibration" && p.era !== "ERA_1") return false;
      if (bucket !== "all" && p.pose !== bucket) return false;
      if (search) {
        const s = search.toLowerCase();
        if (!p.id.toLowerCase().includes(s) && !p.date.includes(s)) return false;
      }
      if (!filterEras.has(p.era)) return false;
      if (!filterHyp.has(p.dominant)) return false;
      if (filterFlags.size > 0 && !p.flags.some((f) => filterFlags.has(f))) return false;
      if (filterAnomaliesOnly) {
        if (p.fuzzyLabel === "CONSISTENT" || p.fuzzyLabel === "STRONGLY_MATCHING") return false;
      }
      if (filterConfidence > 0 && p.confidence < filterConfidence) return false;
      if (filterLowQuality && p.quality < 0.35) return false;
      return true;
    });
  }, [allPhotos, dataset, bucket, search, filterAnomaliesOnly, filterConfidence, filterLowQuality, filterEras, filterHyp, filterFlags]);

  const selectedPhoto = useMemo(
    () => allPhotos.find((p) => p.id === selectedId) || null,
    [allPhotos, selectedId]
  );

  const leftPanelOpen = viewMode === "FULL" && selectedPhoto !== null;
  // mainWidth больше не нужен — все зоны используют index-based width
  void leftPanelOpen;

  return (
    <div ref={containerRef} className="w-screen h-screen flex flex-col overflow-hidden" style={{ background: "#0d0d0f" }}>
      {/* Header */}
      <Header
        dataset={dataset}
        setDataset={setDataset}
        bucket={bucket}
        setBucket={setBucket}
        zoom={zoom}
        setZoom={setZoom}
        search={search}
        setSearch={setSearch}
        totalPhotos={filteredPhotos.length}
        onOpenSources={() => setSourcesOpen(true)}
        onToggleFilter={() => setFilterOpen((v) => !v)}
        viewMode={viewMode}
        setViewMode={setViewMode}
      />

      {/* Filter bar (slides down) */}
      {filterOpen && (
        <div
          className="border-b border-white/8"
          style={{ background: "#13131a" }}
        >
          {/* Row 1: main filters */}
          <div className="flex items-center gap-4 px-4" style={{ height: 36 }}>
            <div className="font-display text-[10px] tracking-widest text-[#7a7a8a]">FILTERS</div>
            <label className="flex items-center gap-2 font-mono text-[10px] cursor-pointer">
              <input
                type="checkbox"
                checked={filterAnomaliesOnly}
                onChange={(e) => setFilterAnomaliesOnly(e.target.checked)}
                className="accent-[#e8af34]"
              />
              <span className="text-[#e2e2e8]">ANOMALIES ONLY</span>
            </label>
            <label className="flex items-center gap-2 font-mono text-[10px] cursor-pointer">
              <input
                type="checkbox"
                checked={filterLowQuality}
                onChange={(e) => setFilterLowQuality(e.target.checked)}
                className="accent-[#e8af34]"
              />
              <span className="text-[#e2e2e8]">HIDE LOW QUALITY</span>
            </label>
            <div className="flex items-center gap-2 font-mono text-[10px]">
              <span className="text-[#7a7a8a]">CONF ≥</span>
              <input
                type="range"
                min="0"
                max="0.9"
                step="0.05"
                value={filterConfidence}
                onChange={(e) => setFilterConfidence(parseFloat(e.target.value))}
                className="w-24 accent-[#4f98a3]"
              />
              <span className="text-[#e2e2e8] w-8">{filterConfidence.toFixed(2)}</span>
            </div>
            <div className="flex-1" />
            <div className="font-mono text-[10px] text-[#4a4a5a]">
              {filteredPhotos.length.toLocaleString()} / {allPhotos.length.toLocaleString()} visible
            </div>
          </div>

          {/* Row 2: multi-select filters */}
          <div className="flex items-center gap-4 px-4 pb-2 flex-wrap">
            {/* Era filter */}
            <div className="flex items-center gap-1">
              <span className="font-mono text-[9px] text-[#7a7a8a] mr-1">ERA:</span>
              {ERA_DEFS.map((era) => {
                const active = filterEras.has(era.id);
                return (
                  <button
                    key={era.id}
                    onClick={() => {
                      const next = new Set(filterEras);
                      if (active) next.delete(era.id);
                      else next.add(era.id);
                      setFilterEras(next);
                    }}
                    className="px-1.5 py-0.5 rounded font-mono text-[9px]"
                    style={{
                      background: active ? era.color + "33" : "transparent",
                      color: active ? era.color : "#4a4a5a",
                      border: `1px solid ${active ? era.color : "rgba(255,255,255,0.08)"}`,
                    }}
                  >
                    {era.label.slice(0, 4)}
                  </button>
                );
              })}
            </div>

            {/* Hypothesis filter */}
            <div className="flex items-center gap-1">
              <span className="font-mono text-[9px] text-[#7a7a8a] mr-1">HYP:</span>
              {[
                { id: "H0", color: "#6daa45" },
                { id: "H1", color: "#fdab43" },
                { id: "H2", color: "#a13544" },
              ].map((h) => {
                const active = filterHyp.has(h.id);
                return (
                  <button
                    key={h.id}
                    onClick={() => {
                      const next = new Set(filterHyp);
                      if (active) next.delete(h.id);
                      else next.add(h.id);
                      setFilterHyp(next);
                    }}
                    className="px-1.5 py-0.5 rounded font-mono text-[9px]"
                    style={{
                      background: active ? h.color + "33" : "transparent",
                      color: active ? h.color : "#4a4a5a",
                      border: `1px solid ${active ? h.color : "rgba(255,255,255,0.08)"}`,
                    }}
                  >
                    {h.id}
                  </button>
                );
              })}
            </div>

            {/* Flag filter */}
            <div className="flex items-center gap-1">
              <span className="font-mono text-[9px] text-[#7a7a8a] mr-1">FLAGS:</span>
              {["IMPOSSIBLE_SHORT", "TEXTURE_SPIKE", "RETURN_TO_BASELINE", "TRANSITION", "TEMPORAL_IMPOSSIBILITY"].map((f) => {
                const active = filterFlags.has(f);
                return (
                  <button
                    key={f}
                    onClick={() => {
                      const next = new Set(filterFlags);
                      if (active) next.delete(f);
                      else next.add(f);
                      setFilterFlags(next);
                    }}
                    className="px-1.5 py-0.5 rounded font-mono text-[8px]"
                    style={{
                      background: active ? "#e8af3433" : "transparent",
                      color: active ? "#e8af34" : "#4a4a5a",
                      border: `1px solid ${active ? "#e8af34" : "rgba(255,255,255,0.08)"}`,
                    }}
                  >
                    {f}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Main area: left panel + content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel (only in FULL mode) */}
        {viewMode === "FULL" && (
          <LeftPanel
            photo={selectedPhoto}
            onClose={() => setSelectedId(null)}
            contextPhotos={allPhotos}
          />
        )}

        {/* Main content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Comparison mode overlay */}
          {comparisonIds ? (
            <ComparisonView
              photoA={allPhotos.find((p) => p.id === comparisonIds[0])!}
              photoB={allPhotos.find((p) => p.id === comparisonIds[1])!}
              onClose={() => setComparisonIds(null)}
              onSelectPhoto={(id) => setSelectedId(id)}
            />
          ) : viewMode === "ERA_COMPARE" ? (
            <EraCompareView
              photos={filteredPhotos}
              onSelectPhoto={(id) => setSelectedId(id)}
              selectedId={selectedId}
            />
          ) : viewMode === "CLUSTER" ? (
            <ClusterView
              photos={filteredPhotos}
              onSelectPhoto={(id) => setSelectedId(id)}
              selectedId={selectedId}
              hoveredId={hoveredId}
              setHoveredId={setHoveredId}
            />
          ) : (
            <>
              {/* Top tracks (geometry) */}
              <div className="overflow-hidden" style={{ height: 196 + 18 }}>
                <TrackPanel
                  title="ГЕОМЕТРИЯ ЛИЦА · 7 МЕТРИК"
                  lanes={TOP_LANES}
                  photos={filteredPhotos}
                  zoom={zoom}
                  scrollRatio={scrollRatio}
                  setScrollRatio={setScrollRatio}
                  playheadRatio={playheadRatio}
                  setPlayheadRatio={setPlayheadRatio}
                  laneHeight={28}
                  areaLaneKey="bone"
                  hoveredId={hoveredId}
                  selectedId={selectedId}
                />
              </div>

              {/* Filmstrip */}
              <div className="flex-1 overflow-hidden relative">
                <Filmstrip
                  photos={filteredPhotos}
                  zoom={zoom}
                  scrollRatio={scrollRatio}
                  setScrollRatio={setScrollRatio}
                  playheadRatio={playheadRatio}
                  selectedId={selectedId}
                  setSelectedId={setSelectedId}
                  hoveredId={hoveredId}
                  setHoveredId={setHoveredId}
                  eventPins={EVENT_PINS}
                  onCompareWith={(id) => {
                    if (!selectedId) {
                      setSelectedId(id);
                    } else if (id !== selectedId) {
                      setComparisonIds([selectedId, id]);
                    }
                  }}
                />
                {selectedId && !comparisonIds && (
                  <div
                    className="absolute bottom-2 left-1/2 -translate-x-1/2 z-30 px-3 py-1 rounded-full font-mono text-[9px] pointer-events-none"
                    style={{
                      background: "rgba(19,19,26,0.95)",
                      border: "1px solid rgba(255,255,255,0.12)",
                      color: "#7a7a8a",
                    }}
                  >
                    SHIFT+CLICK другое фото для режима COMPARE
                  </div>
                )}
              </div>

              {/* Bottom tracks (texture + visual age) */}
              <div className="overflow-hidden" style={{ height: 196 + 28 + 18 }}>
                <TrackPanel
                  title="ТЕКСТУРА КОЖИ · 7 МЕТРИК + ВОЗРАСТ"
                  lanes={BOTTOM_LANES}
                  photos={filteredPhotos}
                  zoom={zoom}
                  scrollRatio={scrollRatio}
                  setScrollRatio={setScrollRatio}
                  playheadRatio={playheadRatio}
                  setPlayheadRatio={setPlayheadRatio}
                  laneHeight={28}
                  hoveredId={hoveredId}
                  selectedId={selectedId}
                  ageLane={{
                    getVisualAge: (p) => Math.max(40, Math.min(90, p.visualAge)) / 90,
                    getCalendarAge: (p) => Math.max(40, Math.min(90, p.calendarAge)) / 90,
                    minAge: 0,
                    maxAge: 1,
                  }}
                />
              </div>

          {/* ERA + Verdict strip */}
          <EraVerdictStrip
            photos={filteredPhotos}
            zoom={zoom}
            scrollRatio={scrollRatio}
            setScrollRatio={setScrollRatio}
            playheadRatio={playheadRatio}
          />

          {/* Timeline ruler */}
          <TimelineRuler
            photos={filteredPhotos}
            zoom={zoom}
            setZoom={setZoom}
            scrollRatio={scrollRatio}
            setScrollRatio={setScrollRatio}
            playheadRatio={playheadRatio}
            setPlayheadRatio={setPlayheadRatio}
          />
            </>
          )}
        </div>
      </div>

      {/* Hypothesis legend */}
      <HypothesisLegend />

      {/* Publications panel */}
      {sourcesOpen && <PublicationsPanel pins={EVENT_PINS} onClose={() => setSourcesOpen(false)} />}
    </div>
  );
}
