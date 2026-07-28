import React, { useMemo } from "react";
import { PhotoPoint, ERA_DEFS, HYP_COLORS, FUZZY_COLORS } from "../types";

// ------------------ ERA COMPARE VIEW ------------------
export const EraCompareView: React.FC<{
  photos: PhotoPoint[];
  onSelectPhoto: (id: string) => void;
  selectedId: string | null;
}> = ({ photos, onSelectPhoto, selectedId }) => {
  const eraBuckets = useMemo(() => {
    return ERA_DEFS.map((era) => ({
      era,
      photos: photos.filter((p) => p.era === era.id).sort((a, b) => a.timestamp - b.timestamp),
    }));
  }, [photos]);

  return (
    <div className="flex-1 flex overflow-hidden" style={{ background: "#0d0d0f" }}>
      {eraBuckets.map(({ era, photos: eraPhotos }) => {
        // Stats
        const h0Count = eraPhotos.filter((p) => p.dominant === "H0").length;
        const h1Count = eraPhotos.filter((p) => p.dominant === "H1").length;
        const h2Count = eraPhotos.filter((p) => p.dominant === "H2").length;
        return (
          <div
            key={era.id}
            className="flex-1 flex flex-col border-r border-white/8 overflow-hidden"
            style={{ minWidth: 0 }}
          >
            {/* Era header */}
            <div
              className="px-3 py-2 flex items-center justify-between"
              style={{ background: era.color + "22", borderBottom: `2px solid ${era.color}` }}
            >
              <div>
                <div className="font-display tracking-widest text-[11px]" style={{ color: era.color }}>
                  {era.label}
                </div>
                <div className="font-mono text-[9px] text-[#7a7a8a]">
                  {era.startYear}–{era.endYear} · {eraPhotos.length} photos
                </div>
              </div>
              <div className="flex gap-2 font-mono text-[9px]">
                <span style={{ color: HYP_COLORS.H0 }}>H0 {h0Count}</span>
                <span style={{ color: HYP_COLORS.H1 }}>H1 {h1Count}</span>
                <span style={{ color: HYP_COLORS.H2 }}>H2 {h2Count}</span>
              </div>
            </div>

            {/* Photos grid */}
            <div className="flex-1 overflow-y-auto p-2">
              <div className="grid grid-cols-3 gap-1">
                {eraPhotos.slice(0, 120).map((p) => (
                  <button
                    key={p.id}
                    onClick={() => onSelectPhoto(p.id)}
                    className="relative aspect-square rounded overflow-hidden hover:opacity-90"
                    style={{
                      border: `2px solid ${selectedId === p.id ? "#ff3b30" : HYP_COLORS[p.dominant]}`,
                      background: `linear-gradient(135deg, ${era.color}33, #0d0d0f)`,
                    }}
                  >
                    <SilhouetteSmall hue={eraHues[era.id]} />
                    <div
                      className="absolute top-0.5 left-0.5 font-mono rounded px-0.5"
                      style={{ fontSize: 7, background: "rgba(0,0,0,0.6)", color: "#e2e2e8" }}
                    >
                      {p.date.slice(2, 7)}
                    </div>
                    <div
                      className="absolute bottom-0 left-0 right-0 h-0.5"
                      style={{ background: FUZZY_COLORS[p.fuzzyLabel] }}
                    />
                  </button>
                ))}
              </div>
            </div>

            {/* Era footer: median metrics */}
            <div className="px-3 py-1.5 border-t border-white/8 font-mono text-[9px] text-[#7a7a8a]">
              <div className="flex justify-between">
                <span>bone</span>
                <span style={{ color: "#e2e2e8" }}>
                  μ={(eraPhotos.reduce((s, p) => s + p.geometry.boneScore, 0) / eraPhotos.length).toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>silicone</span>
                <span style={{ color: "#e2e2e8" }}>
                  μ={(eraPhotos.reduce((s, p) => s + p.texture.silicone, 0) / eraPhotos.length).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ------------------ CLUSTER VIEW (PCA-like scatter) ------------------
export const ClusterView: React.FC<{
  photos: PhotoPoint[];
  onSelectPhoto: (id: string) => void;
  selectedId: string | null;
  hoveredId: string | null;
  setHoveredId: (id: string | null) => void;
}> = ({ photos, onSelectPhoto, selectedId, hoveredId, setHoveredId }) => {
  const width = 800;
  const height = 600;
  const pad = 40;

  // PCA proxies: PC1 = geometry (bone score), PC2 = texture (silicone + subsurface)
  const points = useMemo(() => {
    return photos.map((p) => {
      const pc1 = p.geometry.boneScore;
      const pc2 = (p.texture.silicone + p.texture.subsurface) / 2;
      return {
        p,
        x: pad + pc1 * (width - 2 * pad),
        y: height - pad - pc2 * (height - 2 * pad),
      };
    });
  }, [photos]);

  const selectedPhoto = photos.find((p) => p.id === selectedId);

  return (
    <div className="flex-1 flex overflow-hidden" style={{ background: "#0d0d0f" }}>
      {/* Scatter */}
      <div className="flex-1 relative">
        <div className="absolute top-3 left-3 z-10 font-mono text-[10px]">
          <div className="font-display text-[11px] tracking-widest text-[#7a7a8a]">
            CLUSTER VIEW · PCA PROJECTION
          </div>
          <div className="text-[#7a7a8a] mt-0.5">
            PC1 = geometry · PC2 = texture · N = {photos.length}
          </div>
        </div>

        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-full"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Grid */}
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <React.Fragment key={t}>
              <line
                x1={pad + t * (width - 2 * pad)}
                y1={pad}
                x2={pad + t * (width - 2 * pad)}
                y2={height - pad}
                stroke="rgba(255,255,255,0.05)"
              />
              <line
                x1={pad}
                y1={pad + t * (height - 2 * pad)}
                x2={width - pad}
                y2={pad + t * (height - 2 * pad)}
                stroke="rgba(255,255,255,0.05)"
              />
            </React.Fragment>
          ))}

          {/* Axis labels */}
          <text x={width / 2} y={height - 8} textAnchor="middle" fontSize="10" fontFamily="JetBrains Mono" fill="#7a7a8a">
            PC1 · GEOMETRY (bone_score →)
          </text>
          <text
            x={12}
            y={height / 2}
            textAnchor="middle"
            fontSize="10"
            fontFamily="JetBrains Mono"
            fill="#7a7a8a"
            transform={`rotate(-90, 12, ${height / 2})`}
          >
            PC2 · TEXTURE (silicone →)
          </text>

          {/* Era clusters (convex hull approximation via circles) */}
          {ERA_DEFS.map((era) => {
            const eraPts = points.filter((pt) => pt.p.era === era.id);
            if (eraPts.length === 0) return null;
            const cx = eraPts.reduce((s, p) => s + p.x, 0) / eraPts.length;
            const cy = eraPts.reduce((s, p) => s + p.y, 0) / eraPts.length;
            const radius = Math.sqrt(eraPts.length) * 6;
            return (
              <g key={era.id}>
                <circle cx={cx} cy={cy} r={radius} fill={era.color} opacity={0.08} />
                <text
                  x={cx}
                  y={cy - radius - 4}
                  textAnchor="middle"
                  fontSize="9"
                  fontFamily="JetBrains Mono"
                  fill={era.color}
                >
                  {era.label} · {eraPts.length}
                </text>
              </g>
            );
          })}

          {/* Points */}
          {points.map((pt) => (
            <circle
              key={pt.p.id}
              cx={pt.x}
              cy={pt.y}
              r={selectedId === pt.p.id ? 6 : hoveredId === pt.p.id ? 4.5 : 2.5}
              fill={ERA_DEFS.find((e) => e.id === pt.p.era)!.color}
              stroke={
                selectedId === pt.p.id ? "#ff3b30" : hoveredId === pt.p.id ? "#e2e2e8" : "none"
              }
              strokeWidth={selectedId === pt.p.id ? 2 : 1}
              opacity={selectedId && selectedId !== pt.p.id ? 0.35 : 0.85}
              className="cursor-pointer"
              onClick={() => onSelectPhoto(pt.p.id)}
              onMouseEnter={() => setHoveredId(pt.p.id)}
              onMouseLeave={() => setHoveredId(null)}
            />
          ))}
        </svg>

        {/* Hover tooltip */}
        {hoveredId && (() => {
          const p = photos.find((x) => x.id === hoveredId);
          if (!p) return null;
          return (
            <div
              className="absolute top-14 right-4 z-10 rounded px-3 py-2 font-mono text-[10px]"
              style={{
                background: "#13131a",
                border: "1px solid rgba(255,255,255,0.12)",
                minWidth: 180,
              }}
            >
              <div className="text-[#e2e2e8]">{p.id}</div>
              <div className="text-[#7a7a8a]">{p.date} · {p.era}</div>
              <div className="mt-1 text-[#e2e2e8]">
                PC1 = {p.geometry.boneScore.toFixed(2)}
              </div>
              <div className="text-[#e2e2e8]">
                PC2 = {((p.texture.silicone + p.texture.subsurface) / 2).toFixed(2)}
              </div>
              <div className="mt-1" style={{ color: FUZZY_COLORS[p.fuzzyLabel] }}>
                {p.fuzzyLabel}
              </div>
            </div>
          );
        })()}
      </div>

      {/* Right sidebar: selected photo details */}
      <div
        className="border-l border-white/8 overflow-y-auto"
        style={{ width: 260, background: "#13131a" }}
      >
        {selectedPhoto ? (
          <div className="p-3">
            <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">
              SELECTED
            </div>
            <div
              className="rounded overflow-hidden mb-3"
              style={{
                height: 180,
                border: `2px solid ${HYP_COLORS[selectedPhoto.dominant]}`,
                background: `linear-gradient(135deg, ${ERA_DEFS.find((e) => e.id === selectedPhoto.era)!.color}33, #0d0d0f)`,
              }}
            >
              <SilhouetteSmall hue={eraHues[selectedPhoto.era]} />
            </div>
            <div className="font-mono text-[10px] space-y-1">
              <div className="flex justify-between">
                <span className="text-[#7a7a8a]">id</span>
                <span className="text-[#e2e2e8]">{selectedPhoto.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#7a7a8a]">date</span>
                <span className="text-[#e2e2e8]">{selectedPhoto.date}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#7a7a8a]">era</span>
                <span style={{ color: ERA_DEFS.find((e) => e.id === selectedPhoto.era)!.color }}>
                  {selectedPhoto.era}
                </span>
              </div>
              <div className="pt-2 border-t border-white/5 flex justify-between">
                <span style={{ color: HYP_COLORS.H0 }}>H0 {(selectedPhoto.p0 * 100).toFixed(0)}%</span>
                <span style={{ color: HYP_COLORS.H1 }}>H1 {(selectedPhoto.p1 * 100).toFixed(0)}%</span>
                <span style={{ color: HYP_COLORS.H2 }}>H2 {(selectedPhoto.p2 * 100).toFixed(0)}%</span>
              </div>
              {selectedPhoto.flags.length > 0 && (
                <div className="pt-2 mt-2 border-t border-white/5 text-[#e8af34]">
                  ⚠ {selectedPhoto.flags.join(", ")}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-3 font-mono text-[10px] text-[#4a4a5a]">
            Кликните на точку, чтобы увидеть детали фото.
          </div>
        )}
      </div>
    </div>
  );
};

const eraHues: Record<string, number> = {
  ERA_1: 190,
  ERA_2: 42,
  ERA_3: 355,
  ERA_4: 30,
  ERA_5: 280,
};

const SilhouetteSmall: React.FC<{ hue: number }> = ({ hue }) => (
  <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
    <defs>
      <linearGradient id={`sg-${hue}`} x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stopColor={`hsl(${hue}, 28%, 18%)`} />
        <stop offset="100%" stopColor={`hsl(${hue}, 28%, 8%)`} />
      </linearGradient>
    </defs>
    <rect width="100" height="100" fill={`url(#sg-${hue})`} />
    <ellipse cx="50" cy="42" rx="22" ry="26" fill={`hsl(${hue}, 22%, 32%)`} />
    <path d="M 15 100 Q 15 68 50 68 Q 85 68 85 100 Z" fill={`hsl(${hue}, 20%, 14%)`} />
  </svg>
);

// ------------------ COMPARISON VIEW (split A/B) ------------------
export const ComparisonView: React.FC<{
  photoA: PhotoPoint;
  photoB: PhotoPoint;
  onClose: () => void;
  onSelectPhoto: (id: string) => void;
}> = ({ photoA, photoB, onClose, onSelectPhoto }) => {
  // Delta computations
  const geoMetrics: { key: keyof PhotoPoint["geometry"]; label: string }[] = [
    { key: "boneScore", label: "bone_score" },
    { key: "orbits", label: "orbit_depth" },
    { key: "chin", label: "chin_projection" },
    { key: "jaw", label: "jaw_width" },
    { key: "cheekbones", label: "zygomatic_arch" },
    { key: "symmetry", label: "symmetry" },
  ];
  const texMetrics: { key: keyof PhotoPoint["texture"]; label: string }[] = [
    { key: "silicone", label: "silicone_prob" },
    { key: "gloss", label: "specular_gloss" },
    { key: "lbp", label: "lbp_entropy" },
    { key: "frangi", label: "frangi_vessel" },
    { key: "wrinkle", label: "wrinkle_index" },
    { key: "subsurface", label: "subsurface" },
  ];

  const allowedGeoDelta = 0.018;
  const allowedTexDelta = 0.04;

  const renderPhoto = (p: PhotoPoint, label: string) => (
    <div className="flex-1 flex flex-col overflow-hidden border-r border-white/8">
      <div
        className="px-3 py-2 flex items-center justify-between"
        style={{ background: "#13131a", borderBottom: `2px solid ${HYP_COLORS[p.dominant]}` }}
      >
        <div>
          <div className="font-display text-[11px] tracking-widest" style={{ color: HYP_COLORS[p.dominant] }}>
            {label}
          </div>
          <div className="font-mono text-[9px] text-[#7a7a8a]">{p.id}</div>
        </div>
        <button
          onClick={() => onSelectPhoto(p.id)}
          className="font-mono text-[9px] text-[#7a7a8a] hover:text-[#e2e2e8] px-2 py-1 rounded border border-white/8"
        >
          OPEN DETAILS
        </button>
      </div>

      {/* Photo */}
      <div
        className="relative"
        style={{
          height: 200,
          background: `linear-gradient(135deg, ${ERA_DEFS.find((e) => e.id === p.era)!.color}33, #0d0d0f)`,
        }}
      >
        <SilhouetteSmall hue={eraHues[p.era]} />
        <div className="absolute bottom-2 left-2 font-mono text-[10px] px-1.5 py-0.5 rounded"
          style={{ background: "rgba(0,0,0,0.7)", color: "#e2e2e8" }}>
          {p.date} · {p.era}
        </div>
      </div>

      {/* Posteriors */}
      <div className="px-3 py-2 border-b border-white/5 font-mono text-[10px]">
        <div className="flex justify-between gap-2">
          <span style={{ color: HYP_COLORS.H0 }}>H0 {(p.p0 * 100).toFixed(0)}%</span>
          <span style={{ color: HYP_COLORS.H1 }}>H1 {(p.p1 * 100).toFixed(0)}%</span>
          <span style={{ color: HYP_COLORS.H2 }}>H2 {(p.p2 * 100).toFixed(0)}%</span>
        </div>
        <div className="mt-1" style={{ color: FUZZY_COLORS[p.fuzzyLabel] }}>{p.fuzzyLabel}</div>
      </div>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ background: "#0d0d0f" }}>
      {/* Comparison header */}
      <div
        className="flex items-center justify-between px-4 border-b border-white/8"
        style={{ height: 40, background: "#13131a" }}
      >
        <div className="font-display text-[11px] tracking-widest text-[#e2e2e8]">
          COMPARISON MODE · SPLIT A/B
        </div>
        <button
          onClick={onClose}
          className="font-mono text-[10px] text-[#7a7a8a] hover:text-[#e2e2e8] px-3 py-1 rounded border border-white/8"
        >
          CLOSE (ESC)
        </button>
      </div>

      {/* Split A/B */}
      <div className="flex flex-1 overflow-hidden">
        {renderPhoto(photoA, "A · REFERENCE")}
        {renderPhoto(photoB, "B · COMPARE")}
      </div>

      {/* Diff table */}
      <div
        className="border-t border-white/8 overflow-y-auto"
        style={{ maxHeight: 200, background: "#13131a" }}
      >
        <div className="px-3 py-2 font-display text-[10px] tracking-widest text-[#7a7a8a] border-b border-white/5">
          DIFF · allowed_metric_delta: geometry {allowedGeoDelta} · texture {allowedTexDelta}
        </div>
        <table className="w-full font-mono text-[10px]">
          <thead>
            <tr className="text-[#7a7a8a]">
              <th className="text-left py-1 px-3 font-normal">METRIC</th>
              <th className="text-right py-1 px-3 font-normal">A</th>
              <th className="text-right py-1 px-3 font-normal">B</th>
              <th className="text-right py-1 px-3 font-normal">Δ</th>
              <th className="text-right py-1 px-3 font-normal">|Δ|</th>
              <th className="text-center py-1 px-3 font-normal">⚑</th>
            </tr>
          </thead>
          <tbody>
            {geoMetrics.map((m) => {
              const a = photoA.geometry[m.key] as number;
              const b = photoB.geometry[m.key] as number;
              const delta = b - a;
              const absDelta = Math.abs(delta);
              const exceeds = absDelta > allowedGeoDelta;
              return (
                <tr key={m.label} style={{ background: exceeds ? "rgba(161,53,68,0.1)" : "transparent" }}>
                  <td className="py-1 px-3 text-[#e2e2e8]">{m.label}</td>
                  <td className="py-1 px-3 text-right tabular-nums">{a.toFixed(3)}</td>
                  <td className="py-1 px-3 text-right tabular-nums">{b.toFixed(3)}</td>
                  <td className="py-1 px-3 text-right tabular-nums" style={{ color: delta > 0 ? "#dd6974" : delta < 0 ? "#4f98a3" : "#7a7a8a" }}>
                    {delta > 0 ? "+" : ""}{delta.toFixed(3)}
                  </td>
                  <td className="py-1 px-3 text-right tabular-nums" style={{ color: exceeds ? "#a13544" : "#7a7a8a" }}>
                    {absDelta.toFixed(3)}
                  </td>
                  <td className="py-1 px-3 text-center">{exceeds ? "🔴" : "✓"}</td>
                </tr>
              );
            })}
            {texMetrics.map((m) => {
              const a = photoA.texture[m.key] as number;
              const b = photoB.texture[m.key] as number;
              const delta = b - a;
              const absDelta = Math.abs(delta);
              const exceeds = absDelta > allowedTexDelta;
              return (
                <tr key={m.label} style={{ background: exceeds ? "rgba(161,53,68,0.1)" : "transparent" }}>
                  <td className="py-1 px-3 text-[#e2e2e8]">{m.label}</td>
                  <td className="py-1 px-3 text-right tabular-nums">{a.toFixed(3)}</td>
                  <td className="py-1 px-3 text-right tabular-nums">{b.toFixed(3)}</td>
                  <td className="py-1 px-3 text-right tabular-nums" style={{ color: delta > 0 ? "#dd6974" : delta < 0 ? "#4f98a3" : "#7a7a8a" }}>
                    {delta > 0 ? "+" : ""}{delta.toFixed(3)}
                  </td>
                  <td className="py-1 px-3 text-right tabular-nums" style={{ color: exceeds ? "#a13544" : "#7a7a8a" }}>
                    {absDelta.toFixed(3)}
                  </td>
                  <td className="py-1 px-3 text-center">{exceeds ? "🔴" : "✓"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
