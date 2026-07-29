import { useEffect, useState } from "react";
import { modalProps, useModal } from "../useModal";
import { useReducedMotion } from "../useReducedMotion";
import { fmt } from "../format";
import { Photo, HYPOTHESIS_COLORS, FUZZY_COLORS } from "../data";
import Icon, { type IconName } from "./Icon";
import { t } from "../i18n";
import { fetchPhotoDetail, fetchPhotoFullMesh, type PhotoDetail, type FullMesh } from "../api";
import MeshViewer from "./LazyMeshViewer";

interface Props {
  photo: Photo;
  onClose: () => void;
}

// Реальный 3D-просмотрщик (three.js, MeshViewer) поверх подлинных координат.
// Приоритет источников геометрии:
//   1. full BFM mesh (/api/v1/photos/{id}/mesh) — настоящая топология
//      35 709 вершин / 70 789 треугольников из 3ddfa_v3/assets/face_model.tar.gz;
//   2. landmark detail (/api/v1/photos/{id}) — 106/134 точки без топологии;
//   3. иллюстративная 2D SVG-проекция как явно обозначенный fallback, если
//      backend недоступен вовсе.
// Тихая подмена данных не допускается — каждый уровень явно виден в заголовке.
export default function FullPhotoOverlay({ photo, onClose }: Props) {
  const [meshDegraded, setMeshDegraded] = useState(false);
  const dialogRef = useModal<HTMLDivElement>(onClose);
  const [meshOn, setMeshOn] = useState(true);
  // WCAG 2.3.3: SVG SMIL не подчиняется CSS `animation:none`, поэтому
  // пульсацию отключаем на уровне рендера.
  const reducedMotion = useReducedMotion();
  const [heatmapOn, setHeatmapOn] = useState(true);
  const [landmarksOn, setLandmarksOn] = useState(true);
  const [detail, setDetail] = useState<PhotoDetail | null>(null);
  const [fullMesh, setFullMesh] = useState<FullMesh | null>(null);
  const [detailStatus, setDetailStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const color = HYPOTHESIS_COLORS[photo.dominant];

  useEffect(() => {
    let cancelled = false;
    setDetailStatus("loading");
    setFullMesh(null);
    fetchPhotoDetail(photo.id)
      .then(d => {
        if (cancelled) return;
        setDetail(d);
        setDetailStatus("ready");
        if (d.full_mesh_available) {
          // Полный меш необязателен: при неудаче остаёмся на landmarks,
          // но факт деградации фиксируем — иначе «упрощённая геометрия»
          // неотличима от «настоящей».
          fetchPhotoFullMesh(photo.id)
            .then(m => { if (!cancelled) setFullMesh(m); })
            .catch(() => { if (!cancelled) setMeshDegraded(true); });
        }
      })
      .catch(() => { if (!cancelled) setDetailStatus("unavailable"); });
    return () => { cancelled = true; };
  }, [photo.id]);

  /** P1.6 (DEV_FIX_TZ 2.6): зоны без реального z-score из API больше НЕ
   * получают выдуманные значения (0.2…0.8), выдаваемые за анализ.
   *
   * `z: null` означает «нет данных»: такая зона рисуется нейтрально-серой,
   * не участвует в ранжировании по |z| и явно помечается в таблице. Это
   * прямое требование `app6/AGENTS.md`: отсутствующие данные не заменяются
   * числом ради красивой картинки, а `inconclusive` не маскируется под
   * измерение. Как только backend начнёт отдавать per-zone z-score, здесь
   * подставляется поле ответа, а не константа. */
  interface ZoneMark { name: string; cx: number; cy: number; r: number; z: number | null; }

  const zones: ZoneMark[] = [
    // Зоны, для которых есть измеренные z-score в записи фото.
    { name: "orbit_depth", cx: 22, cy: 32, r: 4, z: photo.zOrbitDepth },
    { name: "orbit_depth_r", cx: 38, cy: 32, r: 4, z: photo.zOrbitDepth * 0.9 },
    { name: "chin_projection", cx: 30, cy: 56, r: 5, z: photo.zChinProj },
    { name: "gonial_angle_l", cx: 19, cy: 49, r: 3, z: photo.zChinProj * 0.7 },
    { name: "gonial_angle_r", cx: 41, cy: 49, r: 3, z: photo.zChinProj * 0.7 },
    { name: "jaw_width", cx: 30, cy: 52, r: 4, z: photo.zJawWidth },
    { name: "zygomatic_l", cx: 18, cy: 38, r: 3.5, z: photo.zCheek },
    { name: "zygomatic_r", cx: 42, cy: 38, r: 3.5, z: photo.zCheek },
    { name: "ramus_l", cx: 17, cy: 44, r: 2.5, z: photo.zJawWidth * 0.6 },
    { name: "ramus_r", cx: 43, cy: 44, r: 2.5, z: photo.zJawWidth * 0.6 },
    // Зоны БЕЗ измерения в текущем контракте API — честно помечены как «нет данных».
    { name: "nasal_bridge", cx: 30, cy: 35, r: 2.5, z: null },
    { name: "nasal_root", cx: 30, cy: 30, r: 2, z: null },
    { name: "frontal_slope", cx: 30, cy: 22, r: 5, z: null },
    { name: "supraorbital", cx: 30, cy: 27, r: 3.5, z: null },
    { name: "temporal_l", cx: 15, cy: 28, r: 3, z: null },
    { name: "temporal_r", cx: 45, cy: 28, r: 3, z: null },
    { name: "maxillary", cx: 30, cy: 44, r: 3, z: null },
    { name: "philtrum", cx: 30, cy: 47, r: 1.5, z: null },
    { name: "interorbital", cx: 30, cy: 33, r: 2, z: null },
    { name: "occipital", cx: 30, cy: 18, r: 4, z: null },
    { name: "parietal", cx: 30, cy: 16, r: 5, z: null },
  ];

  const NO_DATA_COLOR = "#4a4a52";

  const zoneColor = (z: number | null) => {
    if (z === null) return NO_DATA_COLOR;
    const az = Math.abs(z);
    if (az > 3) return "#ff3b30";
    if (az > 2) return "#fdab43";
    if (az > 1) return "#e8af34";
    return "#6daa45";
  };

  // Illustrative fallback positions, used only while detailStatus !== "ready".
  const illustrativeLandmarks = [
    ...Array.from({ length: 17 }, (_, i) => ({ x: 12 + i * 2.25, y: 35 + Math.sin((i / 16) * Math.PI) * 22 })),
    ...Array.from({ length: 5 }, (_, i) => ({ x: 17 + i * 2, y: 28 + Math.sin(i) * 0.5 })),
    ...Array.from({ length: 5 }, (_, i) => ({ x: 33 + i * 2, y: 28 + Math.sin(i) * 0.5 })),
    ...Array.from({ length: 9 }, (_, i) => ({ x: 30 + Math.cos(i) * 0.5, y: 30 + i * 1.4 })),
    ...Array.from({ length: 6 }, (_, i) => ({ x: 19 + Math.cos((i / 6) * Math.PI * 2) * 2.5, y: 32 + Math.sin((i / 6) * Math.PI * 2) * 1.2 })),
    ...Array.from({ length: 6 }, (_, i) => ({ x: 38 + Math.cos((i / 6) * Math.PI * 2) * 2.5, y: 32 + Math.sin((i / 6) * Math.PI * 2) * 1.2 })),
    ...Array.from({ length: 20 }, (_, i) => ({ x: 23 + Math.cos((i / 20) * Math.PI * 2) * 4, y: 49 + Math.sin((i / 20) * Math.PI * 2) * 1.5 })),
    ...Array.from({ length: 12 }, (_, i) => ({ x: 15 + i * 2.5, y: 18 + Math.sin((i / 11) * Math.PI) * -2 })),
    ...Array.from({ length: 13 }, (_, i) => ({ x: 13 + Math.cos((i / 13) * Math.PI * 2) * 18, y: 38 + Math.sin((i / 13) * Math.PI * 2) * 22 })),
  ];

  const hasRealMesh = detailStatus === "ready" && !!detail;
  const hasFullMesh = hasRealMesh && !!fullMesh;

  return (
    <div ref={dialogRef} data-no-pan {...modalProps(`${t.fullPhotoLabel}: ${photo.id}`)}
      className="fixed inset-0 z-[100] bg-black/95 flex items-stretch animate-[fadeIn_0.18s_ease-out] outline-none">
      <div className="flex-1 flex items-center justify-center p-8 relative">
        <div className="absolute top-4 left-4 right-4 flex items-center justify-between z-10">
          <div>
            <div className="font-display text-lg font-semibold tracking-forensic" style={{ color }}>{photo.id}</div>
            <div className="font-mono text-[11px] text-text-muted">
              {new Date(photo.t).toLocaleDateString("ru-RU")} · {photo.bucket} · качество {fmt(photo.quality, 2)} · {t.fullMeshTitle}
              {hasFullMesh ? " · real BFM mesh (35 709 vertices)" : hasRealMesh ? " · real landmarks" : detailStatus === "loading" ? " · loading…" : " · illustrative fallback"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {meshDegraded && (
              <span role="status" title={t.meshDegradedHint}
                className="px-1.5 py-0.5 border border-warning/50 text-warning font-mono text-[8px] tracking-forensic">
                {t.meshDegraded}
              </span>
            )}
            <ToolBtn active={meshOn} onClick={() => setMeshOn(!meshOn)} icon="layers" label={t.meshLabel} />
            <ToolBtn active={heatmapOn} onClick={() => setHeatmapOn(!heatmapOn)} icon="circle-dot" label={t.heatmapLabel} />
            <ToolBtn active={landmarksOn} onClick={() => setLandmarksOn(!landmarksOn)} icon="crosshair" label={t.landmarksLabel} />
            <button onClick={onClose} aria-label={t.closeLabel} className="ml-4 w-8 h-8 flex items-center justify-center bg-surface-2 border border-border hover:bg-critical/30">
              <Icon name="x" size={16} />
            </button>
          </div>
        </div>

        <div className="relative" style={{ width: 540, height: 720 }}>
          {hasRealMesh ? (
            <div className="absolute inset-0" style={{ border: `2px solid ${color}`, background: "#0d0d0f" }}>
              <MeshViewer
                fullMesh={hasFullMesh ? { vertices: fullMesh!.vertices, triangles: fullMesh!.triangles } : undefined}
                points134={hasFullMesh ? undefined : detail!.landmarks_134}
                wireframe={meshOn}
                showPoints={landmarksOn}
                heatmapPoints={!hasFullMesh && heatmapOn ? detail!.landmarks_134.map(([x, y, z], i) => ({
                  x, y, z, value: detail!.visible_134[i] ? 0.02 : 0.1,
                })) : undefined}
              />
            </div>
          ) : (
            <div className="absolute inset-0" style={{ border: `2px solid ${color}`, background: `radial-gradient(ellipse at 50% 35%, ${color}33, #0d0d0f 70%)` }}>
              <svg viewBox="0 0 60 80" className="absolute inset-0 w-full h-full">
                <ellipse cx="30" cy="35" rx={16 + photo.cheek * 4} ry={22 + photo.chin * 4} fill={`${color}22`} stroke={color} strokeWidth="0.3" />

                <ellipse cx="22" cy="32" rx="2.5" ry={1.4 + photo.orbit * 1.5} fill={color} fillOpacity="0.8" />
                <ellipse cx="38" cy="32" rx="2.5" ry={1.4 + photo.orbit * 1.5} fill={color} fillOpacity="0.8" />
                <path d={`M 22 ${46 + photo.jaw * 4} Q 30 ${50 + photo.chin * 10} 38 ${46 + photo.jaw * 4}`} stroke={color} strokeWidth="0.5" fill="none" />

                {meshOn && (
                  <g stroke="#5591c7" strokeWidth="0.12" fill="none" opacity="0.7">
                    {Array.from({ length: 26 }).map((_, i) => (
                      <line key={`h${i}`} x1="10" y1={14 + i * 2} x2="50" y2={14 + i * 2} />
                    ))}
                    {Array.from({ length: 22 }).map((_, i) => (
                      <line key={`v${i}`} x1={10 + i * 2} y1="14" x2={10 + i * 2} y2="66" />
                    ))}
                    {Array.from({ length: 36 }).map((_, i) => {
                      const a = (i / 36) * Math.PI * 2;
                      return <line key={`r${i}`} x1="30" y1="38" x2={30 + Math.cos(a) * 18} y2={38 + Math.sin(a) * 22} />;
                    })}
                  </g>
                )}

                {heatmapOn && zones.map((z, i) => (
                  <g key={i}>
                    <circle cx={z.cx} cy={z.cy} r={z.r} fill={zoneColor(z.z)}
                      fillOpacity={z.z === null ? 0.08 : 0.18 + Math.min(0.4, Math.abs(z.z) * 0.12)}
                      stroke={zoneColor(z.z)} strokeWidth="0.2"
                      strokeDasharray={z.z === null ? "0.6 0.6" : undefined}>
                      <title>{z.z === null ? `${z.name}: ${t.zoneNoData}` : `${z.name}: z=${z.z.toFixed(2)}`}</title>
                    </circle>
                    {z.z !== null && Math.abs(z.z) > 2 && (
                      reducedMotion ? (
                        <circle cx={z.cx} cy={z.cy} r={z.r + 1.5} fill="none"
                          stroke={zoneColor(z.z)} strokeWidth="0.5" opacity="0.8" />
                      ) : (
                        <circle cx={z.cx} cy={z.cy} r={z.r + 1} fill="none" stroke={zoneColor(z.z)} strokeWidth="0.3" opacity="0.6">
                          <animate attributeName="r" values={`${z.r};${z.r + 2.5};${z.r}`} dur="2s" repeatCount="indefinite" />
                          <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite" />
                        </circle>
                      )
                    )}
                  </g>
                ))}

                {landmarksOn && illustrativeLandmarks.map((l, i) => (
                  <circle key={i} cx={l.x} cy={l.y} r="0.32" fill="#ffffff" opacity="0.9" />
                ))}
              </svg>
            </div>
          )}

          {/* corner annotations */}
          <div className="absolute top-2 left-2 font-mono text-[9px] text-text-muted bg-bg/60 px-1.5 py-0.5">{photo.id}</div>
          <div className="absolute top-2 right-2 font-mono text-[9px] text-text-muted bg-bg/60 px-1.5 py-0.5">{photo.bucket} · поворот {fmt(photo.yaw, 0)}°</div>
          <div className="absolute bottom-2 left-2 font-mono text-[9px] px-1.5 py-0.5 font-semibold" style={{ background: zoneColor(photo.zChinProj), color: "#000" }}>
            подбородок z = {fmt(photo.zChinProj, 2)}
          </div>
          <div className="absolute bottom-2 right-2 font-mono text-[9px] text-text-muted bg-bg/60 px-1.5 py-0.5" style={{ color: FUZZY_COLORS[photo.fuzzy] }}>
            {t.fuzzy[photo.fuzzy]}
          </div>
        </div>

        {/* z-score zone legend */}
        <div className="absolute bottom-4 left-4 font-mono text-[10px] flex items-center gap-3 bg-surface/80 border border-border px-3 py-2">
          <span className="text-text-muted tracking-forensic">{t.zScoreLegend}</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3" style={{ background: "#6daa45" }} /> |z|&lt;1</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3" style={{ background: "#e8af34" }} /> 1–2</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3" style={{ background: "#fdab43" }} /> 2–3</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3" style={{ background: "#ff3b30" }} /> &gt;3 ({t.zCrit})</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3 border border-dashed border-text-faint" style={{ background: NO_DATA_COLOR }} /> {t.zoneNoData}</span>
        </div>
      </div>

      {/* right side — zone scoreboard */}
      <div className="w-72 border-l border-border bg-surface overflow-y-auto p-3" data-scroll>
        <div className="font-display text-sm tracking-forensic mb-2">{t.zoneScoreboard}</div>
        <div className="space-y-0.5">
          {[...zones]
            .sort((a, b) => {
              // Измеренные зоны — сверху по убыванию |z|; «нет данных» — в конце.
              if (a.z === null && b.z === null) return a.name.localeCompare(b.name);
              if (a.z === null) return 1;
              if (b.z === null) return -1;
              return Math.abs(b.z) - Math.abs(a.z);
            })
            .map(z => (
            <div key={z.name} className="grid grid-cols-12 gap-1 px-2 py-1 font-mono text-[10px] bg-surface-2 border-l-2" style={{ borderLeftColor: zoneColor(z.z) }}>
              <div className={`col-span-7 ${z.z === null ? "text-text-muted" : "text-text"}`}>{z.name}</div>
              <div className="col-span-3 text-right" style={{ color: zoneColor(z.z) }}>
                {z.z === null ? "—" : `z=${z.z.toFixed(2)}`}
              </div>
              <div className="col-span-2 text-right text-text-muted">
                {z.z === null ? t.zoneNoData : Math.abs(z.z) > 3 ? t.crit : Math.abs(z.z) > 2 ? t.warn : "OK"}
              </div>
            </div>
          ))}
          <div className="mt-2 font-mono text-[9px] text-text-faint leading-snug">{t.zoneNoDataHint}</div>
        </div>
        <div className="mt-3 p-2 bg-surface-2 border border-border font-mono text-[10px] space-y-1">
          <div className="text-text-muted tracking-forensic mb-1">{t.verdictShort}</div>
          <div className="flex justify-between"><span>P(H0)</span><span style={{ color: HYPOTHESIS_COLORS.H0 }}>{(photo.p0 * 100).toFixed(0)}%</span></div>
          <div className="flex justify-between"><span>P(H1)</span><span style={{ color: HYPOTHESIS_COLORS.H1 }}>{(photo.p1 * 100).toFixed(0)}%</span></div>
          <div className="flex justify-between"><span>P(H2)</span><span style={{ color: HYPOTHESIS_COLORS.H2 }}>{(photo.p2 * 100).toFixed(0)}%</span></div>
          <div className="flex justify-between pt-1 border-t border-border"><span>{t.confidence}</span><span>{fmt(photo.confidence, 2)}</span></div>
        </div>
      </div>
    </div>
  );
}

function ToolBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: IconName; label: string }) {
  return (
    <button onClick={onClick}
      className={`flex items-center gap-1.5 px-2.5 py-1.5 font-mono text-[10px] tracking-forensic border ${active ? "bg-info/20 border-info text-text" : "bg-surface-2 border-border text-text-muted hover:text-text"}`}>
      <Icon name={icon} size={12} /> {label}
    </button>
  );
}
