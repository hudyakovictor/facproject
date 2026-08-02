import { useMemo } from "react";
import { Photo, ERA_META, Era, HYPOTHESIS_COLORS, FUZZY_COLORS } from "../data";
import Icon from "./Icon";
import { t } from "../i18n";

// === ERA COMPARE: 5 columns, one per era, photos chronologically ===
export function EraCompareView({ photos, onSelectPhoto, onDoubleClick, selectedId }: {
  photos: Photo[];
  onSelectPhoto: (id: string) => void;
  onDoubleClick: (p: Photo) => void;
  selectedId: string | null;
}) {
  // Сегменты берутся из фактических данных: жёсткий список ERA_* не совпадает
  // с идентификаторами backend (`DEMO_SEGMENT_*` / `STAGE2_RESEARCH`).
  const byEra = useMemo(() => {
    const out: Record<string, Photo[]> = {};
    for (const p of photos) (out[p.era] ??= []).push(p);
    return out;
  }, [photos]);

  const eras: Era[] = useMemo(
    () => Object.keys(byEra).sort((a, b) => (byEra[a][0]?.t ?? 0) - (byEra[b][0]?.t ?? 0)),
    [byEra]);

  return (
    <div className="w-full h-full flex bg-bg/40 overflow-hidden">
      {eras.map(era => {
        const meta = ERA_META[era] ?? { label: era, short: era, color: "#797876", start: "", end: "" };
        const list = byEra[era] ?? [];
        const anomalies = list.filter(p => p.fuzzy === "IDENTITY_ANOMALY" || p.fuzzy === "GEOMETRIC_MISMATCH" || p.fuzzy === "TEMPORAL_IMPOSSIBILITY").length;
        const h0 = list.filter(p => p.dominant === "H0").length;
        const h1 = list.filter(p => p.dominant === "H1").length;
        const h2 = list.filter(p => p.dominant === "H2").length;
        const total = list.length || 1;
        return (
          <div key={era} className="flex-1 flex flex-col border-r border-border last:border-r-0 min-w-0">
            <div className="p-3 border-b border-border bg-surface-2" style={{ borderTopColor: meta.color, borderTopWidth: 3 }}>
              <div className="font-display tracking-forensic text-sm" style={{ color: meta.color }}>{t.eraNames[era] ?? meta.label}</div>
              <div className="font-mono text-[10px] text-text-muted mt-0.5">{meta.start ? new Date(meta.start).toLocaleDateString("ru-RU") : "—"} → {meta.end ? new Date(meta.end).toLocaleDateString("ru-RU") : "—"}</div>
              <div className="font-mono text-[11px] mt-1.5"><span className="text-text">{list.length}</span> <span className="text-text-muted">{t.eraColumn}</span> · <span className="text-critical">{anomalies}</span> <span className="text-text-muted">{t.anomCount}</span></div>
              {/* hypothesis distribution bar */}
              <div className="flex h-1.5 mt-2 bg-bg">
                <div style={{ width: `${(h0 / total) * 100}%`, background: HYPOTHESIS_COLORS.H0 }} />
                <div style={{ width: `${(h1 / total) * 100}%`, background: HYPOTHESIS_COLORS.H1 }} />
                <div style={{ width: `${(h2 / total) * 100}%`, background: HYPOTHESIS_COLORS.H2 }} />
              </div>
              <div className="flex justify-between font-mono text-[8px] text-text-muted mt-0.5">
                <span style={{ color: HYPOTHESIS_COLORS.H0 }}>H0 {Math.round((h0 / total) * 100)}%</span>
                <span style={{ color: HYPOTHESIS_COLORS.H1 }}>H1 {Math.round((h1 / total) * 100)}%</span>
                <span style={{ color: HYPOTHESIS_COLORS.H2 }}>H2 {Math.round((h2 / total) * 100)}%</span>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-1.5" data-scroll>
              <div className="grid grid-cols-4 gap-1">
                {list.map(p => {
                  const color = HYPOTHESIS_COLORS[p.dominant];
                  const sel = selectedId === p.id;
                  return (
                    <div key={p.id}
                      className={`relative aspect-[3/4] cursor-pointer ${sel ? "ring-2 ring-white" : ""}`}
                      style={{ border: `1.5px solid ${color}`, background: `linear-gradient(160deg, ${color}33, #0d0d0f)` }}
                      onClick={() => onSelectPhoto(p.id)}
                      onDoubleClick={() => onDoubleClick(p)}
                      title={`${p.id} · ${p.date}`}
                    >
                      <div className="absolute top-0 left-0 right-0 h-0.5" style={{ background: FUZZY_COLORS[p.fuzzy] }} />
                      <svg viewBox="0 0 60 80" className="absolute inset-0 w-full h-full opacity-50">
                        <ellipse cx="30" cy="35" rx={16 + p.cheek * 4} ry={22 + p.chin * 3} fill={color} fillOpacity="0.2" stroke={color} strokeWidth="0.4" />
                        <ellipse cx="22" cy="32" rx="2" ry={1 + p.orbit * 1.2} fill={color} />
                        <ellipse cx="38" cy="32" rx="2" ry={1 + p.orbit * 1.2} fill={color} />
                      </svg>
                      {p.flags.includes("TEMPORAL_IMPOSSIBILITY") && (
                        <div className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-critical blink-critical" />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// === CLUSTER VIEW: scatter on 2 PCA components of identity vector ===
export function ClusterView({ photos, onSelectPhoto, onDoubleClick, selectedId }: {
  photos: Photo[];
  onSelectPhoto: (id: string) => void;
  onDoubleClick: (p: Photo) => void;
  selectedId: string | null;
}) {
  // Synthetic PCA: PC1 ≈ geometric drift, PC2 ≈ texture drift
  const pts = useMemo(() => photos.map(p => {
    const pc1 = (p.chin - 0.46) * 4 + (p.orbit - 0.34) * 2 + (p.cheek - 0.48) * 1.5;
    const pc2 = (p.lbpEntropy - 0.62) * 3 + (p.siliconeProb - 0.15) * 2 - (p.specular - 0.55) * 1.5;
    return { p, pc1, pc2 };
  }), [photos]);

  const minX = Math.min(...pts.map(p => p.pc1));
  const maxX = Math.max(...pts.map(p => p.pc1));
  const minY = Math.min(...pts.map(p => p.pc2));
  const maxY = Math.max(...pts.map(p => p.pc2));

  const W = 1000, H = 600;
  const padX = 60, padY = 50;

  const xFor = (v: number) => padX + ((v - minX) / (maxX - minX || 1)) * (W - 2 * padX);
  const yFor = (v: number) => H - padY - ((v - minY) / (maxY - minY || 1)) * (H - 2 * padY);

  // cluster centroids per era
  const centroids = useMemo(() => {
    // Partial<> вместо `{} as any` (DEV_FIX_TZ P2.1): не все эпохи обязаны
    // присутствовать — отсутствие центроида это валидное «нет точек в эпохе».
    const out: Partial<Record<Era, { x: number; y: number; n: number; color: string; label: string }>> = {};
    // Центроиды строятся по сегментам, реально присутствующим в выборке.
    for (const era of Array.from(new Set(pts.map(d => d.p.era)))) {
      const sub = pts.filter(d => d.p.era === era);
      if (!sub.length) continue;
      const meta = ERA_META[era] ?? { color: "#797876", short: era };
      const x = sub.reduce((s, d) => s + d.pc1, 0) / sub.length;
      const y = sub.reduce((s, d) => s + d.pc2, 0) / sub.length;
      out[era] = { x, y, n: sub.length, color: meta.color, label: meta.short };
    }
    return out;
  }, [pts]);

  return (
    <div className="w-full h-full bg-bg/40 flex">
      <div className="flex-1 relative overflow-hidden">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full" preserveAspectRatio="xMidYMid meet">
          {/* axes */}
          <line x1={padX} y1={H - padY} x2={W - padX} y2={H - padY} stroke="rgba(255,255,255,0.15)" />
          <line x1={padX} y1={padY} x2={padX} y2={H - padY} stroke="rgba(255,255,255,0.15)" />
          <text x={W / 2} y={H - 15} textAnchor="middle" fill="#7a7a8a" fontSize="11" fontFamily="JetBrains Mono">{t.pcaXLabel}</text>
          <text x={20} y={H / 2} textAnchor="middle" fill="#7a7a8a" fontSize="11" fontFamily="JetBrains Mono" transform={`rotate(-90 20 ${H / 2})`}>{t.pcaYLabel}</text>
          {/* grid */}
          {Array.from({ length: 8 }).map((_, i) => (
            <line key={`gx${i}`} x1={padX + ((W - 2 * padX) / 8) * i} y1={padY} x2={padX + ((W - 2 * padX) / 8) * i} y2={H - padY} stroke="rgba(255,255,255,0.04)" />
          ))}
          {Array.from({ length: 6 }).map((_, i) => (
            <line key={`gy${i}`} x1={padX} y1={padY + ((H - 2 * padY) / 6) * i} x2={W - padX} y2={padY + ((H - 2 * padY) / 6) * i} stroke="rgba(255,255,255,0.04)" />
          ))}

          {/* zero crosshair */}
          <line x1={xFor(0)} y1={padY} x2={xFor(0)} y2={H - padY} stroke="rgba(85,145,199,0.25)" strokeDasharray="3 3" />
          <line x1={padX} y1={yFor(0)} x2={W - padX} y2={yFor(0)} stroke="rgba(85,145,199,0.25)" strokeDasharray="3 3" />
          <text x={xFor(0) + 6} y={padY + 12} fill="#5591c7" fontSize="9" fontFamily="JetBrains Mono">центр ERA_1 (норма)</text>

          {/* convex hulls per era (approximated as ellipses around centroid) */}
          {(Object.keys(centroids) as Era[]).map(era => {
            const c = centroids[era];
            if (!c) return null;
            const sub = pts.filter(d => d.p.era === era);
            const vx = sub.reduce((s, d) => s + (d.pc1 - c.x) ** 2, 0) / sub.length;
            const vy = sub.reduce((s, d) => s + (d.pc2 - c.y) ** 2, 0) / sub.length;
            const rx = Math.sqrt(vx) * (W - 2 * padX) / (maxX - minX || 1) * 1.5;
            const ry = Math.sqrt(vy) * (H - 2 * padY) / (maxY - minY || 1) * 1.5;
            return (
              <g key={era}>
                <ellipse cx={xFor(c.x)} cy={yFor(c.y)} rx={rx} ry={ry} fill={c.color} fillOpacity="0.07" stroke={c.color} strokeWidth="0.8" strokeDasharray="3 3" />
                <text x={xFor(c.x)} y={yFor(c.y) - ry - 6} textAnchor="middle" fill={c.color} fontSize="10" fontFamily="Space Grotesk" fontWeight="600">{t.eraShort[era] ?? c.label}</text>
                <circle cx={xFor(c.x)} cy={yFor(c.y)} r="3" fill={c.color} stroke="#000" strokeWidth="1" />
              </g>
            );
          })}

          {/* points */}
          {pts.map(d => {
            const sel = selectedId === d.p.id;
            const color = HYPOTHESIS_COLORS[d.p.dominant];
            return (
              <g key={d.p.id}>
                <circle
                  cx={xFor(d.pc1)} cy={yFor(d.pc2)} r={sel ? 5 : 2.5}
                  fill={color} fillOpacity={sel ? 1 : 0.6}
                  stroke={sel ? "#fff" : "none"} strokeWidth="1"
                  className="cursor-pointer hover:opacity-100"
                  onClick={() => onSelectPhoto(d.p.id)}
                  onDoubleClick={() => onDoubleClick(d.p)}
                >
                  <title>{d.p.id} · {d.p.date} · {d.p.fuzzy}</title>
                </circle>
              </g>
            );
          })}
        </svg>

        <div className="absolute top-3 left-3 bg-surface/90 border border-border p-2 font-mono text-[10px]">
          <div className="text-text-muted tracking-forensic mb-1">{t.clusterView}</div>
          <div>{t.clusterSub}</div>
          <div className="text-text-faint mt-0.5">{photos.length} точек · 5 центроидов эпох</div>
        </div>
      </div>

      <div className="w-64 border-l border-border bg-surface p-3 overflow-y-auto" data-scroll>
        <div className="font-display tracking-forensic text-xs mb-2">{t.centroidsTitle}</div>
        {(Object.keys(centroids) as Era[]).map(era => {
          const c = centroids[era];
          if (!c) return null;
          return (
            <div key={era} className="mb-2 p-2 bg-surface-2 border-l-2" style={{ borderLeftColor: c.color }}>
              <div className="font-mono text-[10px] flex justify-between">
                <span style={{ color: c.color }}>{t.eraShort[era] ?? c.label}</span>
                <span className="text-text-muted">{c.n}</span>
              </div>
              <div className="font-mono text-[9px] text-text-muted">PC1 {c.x.toFixed(2)} · PC2 {c.y.toFixed(2)}</div>
            </div>
          );
        })}
        <div className="mt-3 pt-3 border-t border-border">
          <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1">{t.legend}</div>
          <div className="space-y-1 font-mono text-[10px]">
            <div className="flex items-start gap-2"><Icon name="circle-dot" size={10} color={HYPOTHESIS_COLORS.H0} /><span>{t.legendPoint}</span></div>
            <div className="flex items-start gap-2"><Icon name="circle-dot" size={10} color="#797876" /><span>{t.legendEllipse}</span></div>
            <div className="flex items-start gap-2"><Icon name="info" size={10} /><span>{t.legendDblClick}</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}
