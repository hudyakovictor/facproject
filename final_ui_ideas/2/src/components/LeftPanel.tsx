import React, { useMemo } from "react";
import { PhotoPoint, ERA_DEFS, HYP_COLORS, FUZZY_COLORS } from "../types";

interface Props {
  photo: PhotoPoint | null;
  onClose: () => void;
  contextPhotos: PhotoPoint[];
}

type Tab = "photo" | "geometry" | "skin" | "verdict" | "context";

const POSE_LABEL: Record<string, string> = {
  frontal_0: "frontal_0",
  frontal_yaw15: "frontal_yaw15",
  frontal_yaw30: "frontal_yaw30",
  profile_L: "profile_L",
  profile_R: "profile_R",
};

const GEOMETRY_ZONES: { key: keyof PhotoPoint["geometry"]; label: string; ref: number }[] = [
  { key: "orbits", label: "orbit_depth", ref: 0.7 },
  { key: "chin", label: "chin_projection", ref: 0.72 },
  { key: "jaw", label: "jaw_width", ref: 0.7 },
  { key: "cheekbones", label: "zygomatic_arch", ref: 0.7 },
  { key: "symmetry", label: "symmetry_score", ref: 0.82 },
];

export const LeftPanel: React.FC<Props> = ({ photo, onClose, contextPhotos }) => {
  const [tab, setTab] = React.useState<Tab>("verdict");

  if (!photo) {
    // Collapsed state: icon tabs
    return (
      <div
        className="flex flex-col items-center pt-3 gap-2 border-r border-white/8"
        style={{ width: 48, background: "#13131a" }}
      >
        {(["photo", "geometry", "skin", "verdict", "context"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="w-8 h-8 flex items-center justify-center rounded text-[#7a7a8a] hover:bg-white/5"
            title={t.toUpperCase()}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {t === "photo" && (
                <>
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <circle cx="9" cy="9" r="2" />
                  <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
                </>
              )}
              {t === "geometry" && <path d="M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />}
              {t === "skin" && <circle cx="12" cy="12" r="10" />}
              {t === "verdict" && (
                <>
                  <path d="M9 11l3 3L22 4" />
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </>
              )}
              {t === "context" && (
                <>
                  <path d="M3 3v18h18" />
                  <path d="m7 14 4-4 4 4 5-5" />
                </>
              )}
            </svg>
          </button>
        ))}
      </div>
    );
  }

  const era = ERA_DEFS.find((e) => e.id === photo.era)!;

  // Geometry z-scores (rough, assuming std = 0.05 around ref)
  const geometryRows = GEOMETRY_ZONES.map((z) => {
    const val = photo.geometry[z.key] as number;
    const delta = val - z.ref;
    const zScore = delta / 0.05;
    return { ...z, val, delta, zScore };
  });

  return (
    <div
      className="flex flex-col border-r border-white/8 overflow-hidden"
      style={{ width: 340, background: "#13131a" }}
    >
      {/* Panel header */}
      <div
        className="flex items-center justify-between px-3 border-b border-white/8"
        style={{ height: 48, background: "#13131a" }}
      >
        <div className="font-mono text-[10px]">
          <div className="text-[#e2e2e8]">{photo.id}</div>
          <div className="text-[#7a7a8a]">{photo.date} · {POSE_LABEL[photo.pose]}</div>
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

      {/* Tabs */}
      <div className="flex border-b border-white/8">
        {(["photo", "geometry", "skin", "verdict", "context"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 font-mono text-[10px] tracking-wider uppercase ${
              tab === t ? "text-[#e2e2e8] border-b-2" : "text-[#7a7a8a]"
            }`}
            style={{ borderColor: tab === t ? era.color : "transparent" }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {tab === "photo" && <PhotoTab photo={photo} />}
        {tab === "geometry" && <GeometryTab photo={photo} rows={geometryRows} />}
        {tab === "skin" && <SkinTab photo={photo} />}
        {tab === "verdict" && <VerdictTab photo={photo} />}
        {tab === "context" && <ContextTab photo={photo} context={contextPhotos} />}
      </div>
    </div>
  );
};

// ---------------- PHOTO TAB ----------------
const PhotoTab: React.FC<{ photo: PhotoPoint }> = ({ photo }) => {
  const eraHues: Record<string, number> = {
    ERA_1: 190, ERA_2: 42, ERA_3: 355, ERA_4: 30, ERA_5: 280,
  };
  const hue = eraHues[photo.era];
  const era = ERA_DEFS.find((e) => e.id === photo.era)!;
  return (
    <div className="p-3">
      <div
        className="relative rounded overflow-hidden"
        style={{ height: 260, border: `2px solid ${HYP_COLORS[photo.dominant]}` }}
      >
        <svg viewBox="0 0 200 260" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
          <defs>
            <linearGradient id="p-bg" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={`hsl(${hue}, 30%, 18%)`} />
              <stop offset="100%" stopColor={`hsl(${hue}, 30%, 8%)`} />
            </linearGradient>
            <radialGradient id="p-face" cx="0.5" cy="0.35" r="0.4">
              <stop offset="0%" stopColor={`hsl(${hue}, 25%, 38%)`} />
              <stop offset="100%" stopColor={`hsl(${hue}, 20%, 18%)`} />
            </radialGradient>
          </defs>
          <rect width="200" height="260" fill="url(#p-bg)" />
          <ellipse cx="100" cy="95" rx="48" ry="58" fill="url(#p-face)" />
          <path d="M 30 260 Q 30 170 100 170 Q 170 170 170 260 Z" fill={`hsl(${hue}, 20%, 12%)`} />
          {/* Mesh overlay */}
          {LANDMARK_LINES.map((l, i) => (
            <path
              key={i}
              d={l}
              stroke={era.color}
              strokeWidth="0.5"
              fill="none"
              opacity="0.7"
            />
          ))}
        </svg>
        <div className="absolute top-2 left-2 font-mono text-[10px] px-1.5 py-0.5 rounded"
          style={{ background: "rgba(0,0,0,0.7)", color: "#e2e2e8" }}>
          MESH OVERLAY · 106 landmarks
        </div>
      </div>

      {/* Metadata table */}
      <div className="mt-3 font-mono text-[10px]">
        <MetaRow label="photo_id" value={photo.id} />
        <MetaRow label="source" value={`source_${photo.year}_${Math.floor(photo.quality * 100)}`} />
        <MetaRow label="date" value={photo.date} />
        <MetaRow label="bucket" value={POSE_LABEL[photo.pose]} />
        <MetaRow label="quality.overall" value={photo.quality.toFixed(3)} />
        <MetaRow label="quality.blur" value={(photo.quality * 0.9).toFixed(3)} />
        <MetaRow label="quality.noise" value={(0.1 + (1 - photo.quality) * 0.3).toFixed(3)} />
      </div>

      <div className="flex gap-2 mt-3">
        <button className="flex-1 py-1.5 font-mono text-[10px] uppercase tracking-wider rounded border border-white/10 hover:bg-white/5">
          HIDE / RESTORE
        </button>
      </div>

      {Math.abs(photo.year - 2015) > 12 && photo.year < 2010 && (
        <div className="mt-2 px-2 py-1.5 rounded font-mono text-[10px] pulse-critical"
          style={{ background: "rgba(255,59,48,0.12)", color: "#ff3b30", border: "1px solid rgba(255,59,48,0.3)" }}>
          ⚠ EXIF DATE ANOMALY
        </div>
      )}
    </div>
  );
};

const LANDMARK_LINES = [
  "M 100 60 L 80 90 L 100 110 L 120 90 Z",
  "M 70 75 L 90 80 L 85 95 L 65 92 Z",
  "M 130 75 L 110 80 L 115 95 L 135 92 Z",
  "M 85 110 L 100 120 L 115 110",
  "M 70 135 L 100 145 L 130 135",
  "M 60 70 L 80 65 L 100 68 L 120 65 L 140 70",
  "M 70 160 L 100 170 L 130 160",
  "M 55 100 L 70 95 L 85 100",
  "M 145 100 L 130 95 L 115 100",
];

const MetaRow: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
  <div className="flex justify-between py-1 border-b border-white/5">
    <span className="text-[#7a7a8a]">{label}</span>
    <span className="text-[#e2e2e8]">{value}</span>
  </div>
);

// ---------------- GEOMETRY TAB ----------------
const GeometryTab: React.FC<{
  photo: PhotoPoint;
  rows: { key: string; label: string; ref: number; val: number; delta: number; zScore: number }[];
}> = ({ photo, rows }) => {
  return (
    <div className="p-3">
      <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">21 ZONES · GEOMETRY</div>
      <table className="w-full font-mono text-[10px] tabular-nums">
        <thead>
          <tr className="text-[#7a7a8a]">
            <th className="text-left py-1 font-normal">ZONE</th>
            <th className="text-right py-1 font-normal">RAW</th>
            <th className="text-right py-1 font-normal">Δ</th>
            <th className="text-right py-1 font-normal">Z</th>
            <th className="text-center py-1 font-normal">⚑</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const bg = Math.abs(r.zScore) > 3 ? "rgba(161,53,68,0.2)" : Math.abs(r.zScore) > 2 ? "rgba(232,175,52,0.12)" : "transparent";
            return (
              <tr key={r.key} style={{ background: bg }}>
                <td className="py-1 text-[#e2e2e8]">{r.label}</td>
                <td className="py-1 text-right">{r.val.toFixed(3)}</td>
                <td className="py-1 text-right" style={{ color: r.delta > 0 ? "#dd6974" : r.delta < 0 ? "#4f98a3" : "#7a7a8a" }}>
                  {r.delta > 0 ? "+" : ""}{r.delta.toFixed(3)}
                </td>
                <td className="py-1 text-right" style={{ color: Math.abs(r.zScore) > 3 ? "#a13544" : Math.abs(r.zScore) > 2 ? "#e8af34" : "#7a7a8a" }}>
                  {r.zScore.toFixed(2)}
                </td>
                <td className="py-1 text-center">
                  {Math.abs(r.zScore) > 3 ? "●" : Math.abs(r.zScore) > 2 ? "▲" : ""}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="mt-4 p-2 rounded tabular-nums" style={{ background: "#1a1a24", border: "1px solid rgba(255,255,255,0.08)" }}>
        <div className="flex justify-between font-mono text-[10px]">
          <span className="text-[#7a7a8a]">geometry_score</span>
          <span className="text-[#e2e2e8]">{photo.geometry.boneScore.toFixed(3)}</span>
        </div>
        <div className="flex justify-between font-mono text-[10px]">
          <span className="text-[#7a7a8a]">evidence_mode</span>
          <span className="text-[#e2e2e8]">CALIBRATED</span>
        </div>
        <div className="flex justify-between font-mono text-[10px]">
          <span className="text-[#7a7a8a]">reliability</span>
          <span className="text-[#e2e2e8]">{(photo.quality * 0.95).toFixed(3)}</span>
        </div>
      </div>
    </div>
  );
};

// ---------------- SKIN TAB ----------------
const SkinTab: React.FC<{ photo: PhotoPoint }> = ({ photo }) => {
  const metrics = [
    { label: "gloss", value: photo.texture.gloss, ref: 0.55 },
    { label: "lbp", value: photo.texture.lbp, ref: 0.4 },
    { label: "glcm_contrast", value: 0.5 + photo.texture.lbp * 0.3, ref: 0.55 },
    { label: "frangi", value: photo.texture.frangi, ref: 0.7 },
    { label: "wrinkle_fh", value: photo.texture.wrinkle, ref: 0.3 },
    { label: "wrinkle_nl", value: photo.texture.wrinkle * 0.9, ref: 0.28 },
    { label: "silicone", value: photo.texture.silicone, ref: 0.05 },
    { label: "subsurface", value: photo.texture.subsurface, ref: 0.6 },
  ];

  // Radar chart
  const n = metrics.length;
  const cx = 100, cy = 100, R = 80;
  const pts = metrics.map((m, i) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    const r = R * Math.max(0, Math.min(1, m.value));
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r, label: m.label };
  });
  const refPts = metrics.map((m, i) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    const r = R * Math.max(0, Math.min(1, m.ref));
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r };
  });
  const polyPath = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ") + " Z";
  const refPath = refPts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ") + " Z";

  const era = ERA_DEFS.find((e) => e.id === photo.era)!;

  return (
    <div className="p-3">
      <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">RADAR · 8 KEY METRICS</div>
      <svg viewBox="0 0 200 200" className="w-full">
        {/* Concentric rings */}
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <circle key={f} cx={cx} cy={cy} r={R * f} fill="none" stroke="rgba(255,255,255,0.06)" />
        ))}
        {/* Spokes */}
        {pts.map((_p, i) => (
          <line key={i} x1={cx} y1={cy} x2={cx + Math.cos((Math.PI * 2 * i) / n - Math.PI / 2) * R} y2={cy + Math.sin((Math.PI * 2 * i) / n - Math.PI / 2) * R} stroke="rgba(255,255,255,0.06)" />
        ))}
        {/* Reference (ERA_1 median) */}
        <path d={refPath} fill="rgba(79,152,163,0.1)" stroke="#4f98a3" strokeWidth="1" strokeDasharray="3,3" />
        {/* Actual */}
        <path d={polyPath} fill={era.color + "33"} stroke={era.color} strokeWidth="1.5" />
        {/* Labels */}
        {pts.map((_pt, i) => {
          const a = (Math.PI * 2 * i) / n - Math.PI / 2;
          const lx = cx + Math.cos(a) * (R + 12);
          const ly = cy + Math.sin(a) * (R + 12);
          return (
            <text key={i} x={lx} y={ly} textAnchor="middle" fontSize="8" fontFamily="JetBrains Mono" fill="#7a7a8a">
              {metrics[i].label}
            </text>
          );
        })}
      </svg>

      <div className="mt-3">
        <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">EXTENDED · 19 METRICS</div>
        {metrics.map((m) => {
          const deviation = m.value - m.ref;
          const color = Math.abs(deviation) > 0.3 ? "#dd6974" : Math.abs(deviation) > 0.15 ? "#e8af34" : "#6daa45";
          return (
            <div key={m.label} className="mb-1.5">
              <div className="flex justify-between font-mono text-[10px]">
                <span className="text-[#e2e2e8]">{m.label}</span>
                <span style={{ color }}>{m.value.toFixed(2)}</span>
              </div>
              <div className="relative h-1 bg-[#1a1a24] rounded-full mt-0.5">
                <div
                  className="absolute top-0 h-full rounded-full"
                  style={{ left: 0, width: `${m.value * 100}%`, background: color }}
                />
                <div
                  className="absolute top-0 h-full w-0.5"
                  style={{ left: `${m.ref * 100}%`, background: "rgba(255,255,255,0.4)" }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ---------------- VERDICT TAB ----------------
const VerdictTab: React.FC<{ photo: PhotoPoint }> = ({ photo }) => {
  const bgByLabel: Record<string, string> = {
    STRONGLY_MATCHING: "rgba(109,170,69,0.12)",
    CONSISTENT: "rgba(79,152,163,0.12)",
    INSUFFICIENT_DATA: "rgba(121,120,118,0.12)",
    WEAK_EVIDENCE: "rgba(232,175,52,0.12)",
    SUSPICIOUS_TEXTURE: "rgba(253,171,67,0.12)",
    GEOMETRIC_MISMATCH: "rgba(221,105,116,0.12)",
    IDENTITY_ANOMALY: "rgba(161,53,68,0.15)",
    TEMPORAL_IMPOSSIBILITY: "rgba(255,59,48,0.2)",
  };
  const borderByLabel: Record<string, string> = {
    STRONGLY_MATCHING: "#6daa45",
    CONSISTENT: "#4f98a3",
    INSUFFICIENT_DATA: "#797876",
    WEAK_EVIDENCE: "#e8af34",
    SUSPICIOUS_TEXTURE: "#fdab43",
    GEOMETRIC_MISMATCH: "#dd6974",
    IDENTITY_ANOMALY: "#a13544",
    TEMPORAL_IMPOSSIBILITY: "#ff3b30",
  };
  return (
    <div className="p-3">
      <div
        className="p-3 rounded"
        style={{
          background: bgByLabel[photo.fuzzyLabel],
          border: `1px solid ${borderByLabel[photo.fuzzyLabel]}`,
          boxShadow: `0 0 24px ${borderByLabel[photo.fuzzyLabel]}22`,
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="font-display text-[10px] tracking-widest text-[#7a7a8a]">BAYESIAN VERDICT</div>
          <div
            className="font-mono text-[9px] px-1.5 py-0.5 rounded"
            style={{ background: borderByLabel[photo.fuzzyLabel] + "33", color: borderByLabel[photo.fuzzyLabel] }}
          >
            v2.1.0
          </div>
        </div>
        <div className="font-mono text-[12px] mb-1 font-bold" style={{ color: FUZZY_COLORS[photo.fuzzyLabel] }}>
          {photo.fuzzyLabel}
        </div>
        <div className="font-mono text-[9px] text-[#7a7a8a] mb-3">
          DOMINANT: {photo.dominant} · CONFIDENCE {(photo.confidence * 100).toFixed(0)}%
        </div>

        <div className="mt-3 space-y-1.5">
          <ProbBar label="H0 · same_person" prob={photo.p0} color={HYP_COLORS.H0} />
          <ProbBar label="H1 · mask/surgery" prob={photo.p1} color={HYP_COLORS.H1} />
          <ProbBar label="H2 · identity_swap" prob={photo.p2} color={HYP_COLORS.H2} />
        </div>

        <div className="mt-3 pt-3 border-t border-white/8 space-y-1 font-mono text-[10px]">
          <div className="flex justify-between">
            <span className="text-[#7a7a8a]">CONFIDENCE</span>
            <span className="text-[#e2e2e8]">{photo.confidence.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#7a7a8a]">SNR geometry</span>
            <span className="text-[#e2e2e8]">{(photo.geometry.boneScore * 3.2).toFixed(2)} ({photo.geometry.boneScore > 0.65 ? "SIGNAL" : "UNCERTAIN"})</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#7a7a8a]">SNR texture</span>
            <span className="text-[#e2e2e8]">{(photo.texture.lbp * 3.5).toFixed(2)} ({photo.texture.lbp > 0.55 ? "SIGNAL" : "UNCERTAIN"})</span>
          </div>
        </div>

        {photo.flags.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/8">
            <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">ACTIVE FLAGS</div>
            <div className="space-y-1">
              {photo.flags.map((f) => {
                const severity =
                  f === "TEMPORAL_IMPOSSIBILITY" ? { color: "#ff3b30", icon: "🔴" } :
                  f === "IMPOSSIBLE_SHORT" || f === "TEXTURE_SPIKE" ? { color: "#fdab43", icon: "🟠" } :
                  { color: "#e8af34", icon: "🟡" };
                return (
                  <div key={f} className="font-mono text-[10px] flex items-center gap-2" style={{ color: severity.color }}>
                    <span>{severity.icon}</span>
                    <span>{f}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="mt-3 pt-3 border-t border-white/8">
          <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">REASONING</div>
          <ul className="font-mono text-[10px] text-[#e2e2e8] space-y-1 list-none">
            <li>· orbit_depth deviation {(Math.abs(photo.geometry.orbits - 0.7) * 20).toFixed(1)}σ from baseline</li>
            <li>· texture channels drift +{(photo.texture.lbp - 0.4).toFixed(2)} from ERA_1 median</li>
            <li>· silicone_prob at {(photo.texture.silicone * 100).toFixed(0)}% (threshold 35%)</li>
            {photo.flags.includes("IMPOSSIBLE_SHORT") && <li>· gap &lt; 90 days, geometry shift &gt; 1.75σ</li>}
          </ul>
        </div>
      </div>
    </div>
  );
};

const ProbBar: React.FC<{ label: string; prob: number; color: string }> = ({ label, prob, color }) => (
  <div>
    <div className="flex justify-between font-mono text-[10px]">
      <span style={{ color }}>{label}</span>
      <span className="text-[#e2e2e8]">{(prob * 100).toFixed(0)}%</span>
    </div>
    <div className="h-2 bg-[#1a1a24] rounded overflow-hidden mt-0.5">
      <div className="h-full" style={{ width: `${prob * 100}%`, background: color }} />
    </div>
  </div>
);

// ---------------- CONTEXT TAB ----------------
const ContextTab: React.FC<{ photo: PhotoPoint; context: PhotoPoint[] }> = ({ photo, context }) => {
  const idx = useMemo(() => context.findIndex((p) => p.id === photo.id), [context, photo]);
  const neighbors = useMemo(() => {
    if (idx < 0) return [];
    return context.slice(Math.max(0, idx - 5), idx + 6);
  }, [context, idx]);

  return (
    <div className="p-3">
      <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">SPARKLINE · ±5 NEIGHBORS</div>
      <div className="flex items-end gap-1 justify-center py-2" style={{ height: 80 }}>
        {neighbors.map((n) => {
          const isCurrent = n.id === photo.id;
          const h = 20 + n.confidence * 60;
          return (
            <div key={n.id} className="flex flex-col items-center gap-1">
              <div
                className="w-3 rounded-t"
                style={{
                  height: h,
                  background: HYP_COLORS[n.dominant],
                  opacity: isCurrent ? 1 : 0.5,
                  border: isCurrent ? "2px solid #ff3b30" : "none",
                }}
              />
              <div className="font-mono text-[8px] text-[#7a7a8a]">{n.date.slice(5)}</div>
            </div>
          );
        })}
      </div>

      <div className="mt-4">
        <div className="font-display text-[10px] tracking-widest text-[#7a7a8a] mb-2">LONGITUDINAL MODEL</div>
        <div className="space-y-1.5 font-mono text-[10px]">
          {[
            { m: "orbit_depth", predicted: 0.7, actual: photo.geometry.orbits },
            { m: "silicone_prob", predicted: 0.05, actual: photo.texture.silicone },
            { m: "wrinkle_index", predicted: 0.4, actual: photo.texture.wrinkle },
          ].map((row) => {
            const z = (row.actual - row.predicted) / 0.05;
            const critical = Math.abs(z) > 3;
            return (
              <div key={row.m} className="flex justify-between items-center p-1.5 rounded" style={{ background: critical ? "rgba(161,53,68,0.1)" : "#1a1a24" }}>
                <span className="text-[#7a7a8a]">{row.m}</span>
                <div className="flex gap-3">
                  <span>pred <span className="text-[#e2e2e8]">{row.predicted.toFixed(2)}</span></span>
                  <span>act <span className="text-[#e2e2e8]">{row.actual.toFixed(2)}</span></span>
                  <span style={{ color: critical ? "#a13544" : "#7a7a8a" }}>z={z.toFixed(1)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
