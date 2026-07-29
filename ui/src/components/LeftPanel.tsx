import { useState, useMemo } from "react";
import { fmt } from "../format";

import { Photo, HYPOTHESIS_COLORS, FUZZY_COLORS, REF, EVENT_PINS } from "../data";
import Icon from "./Icon";
import { t, useLanguage } from "../i18n";
import SkinZonesPanel from "./SkinZonesPanel";
import PhotoKeysPanel from "./PhotoKeysPanel";
import ProvenancePopup from "./ProvenancePopup";


interface Props {
  photo: Photo | null;
  /** Полный текущий набор кадров — источник для «соседних кадров».
   *
   * 🔧 Раньше `ContextTab` брал соседей из встроенного демо-набора
   * `PHOTOS`, а не из показанных данных. В research-режиме это означало,
   * что рядом с реальным кадром выводились ВЫДУМАННЫЕ соседи с
   * синтетическими метриками — ровно та подмена, которую запрещает
   * `app6/AGENTS.md`. */
  photos: Photo[];
  onClose: () => void;
  onHide: (id: string) => void;
  onExpandMesh?: () => void;
}

type Tab = "PHOTO" | "FRAME" | "GEOMETRY" | "SKIN" | "VERDICT" | "CONTEXT";

/** 🔧 Строится внутри рендера, а не на уровне модуля: `t.xxx` — живой Proxy
 * (см. `i18n.ts`), и константа уровня модуля "заморозила" бы перевод на
 * момент первого импорта, не реагируя на переключение языка. */
function buildTabs(): { id: Tab; label: string; iconName: "image" | "triangle" | "circle-dot" | "scale" | "crosshair" | "layers" }[] {
  return [
    { id: "PHOTO", label: t.tabPhoto, iconName: "image" },
    // Категории C и H карты размещения ключей: Stage 1 сохраняет 156
    // значений на кадр, интерфейс использовал около восьми.
    { id: "FRAME", label: t.tabFrame, iconName: "layers" },
    { id: "GEOMETRY", label: t.tabGeometry, iconName: "triangle" },
    { id: "SKIN", label: t.tabSkin, iconName: "circle-dot" },
    { id: "VERDICT", label: t.tabVerdict, iconName: "scale" },
    { id: "CONTEXT", label: t.tabContext, iconName: "crosshair" },
  ];
}


const GEOM_ZONES = [
  "orbit_depth", "orbit_fossa", "chin_projection", "gonial_angle",
  "jaw_width", "bigonial_width", "mandibular_body", "ramus_height",
  "zygomatic_arch", "zygomatic_breadth", "nasal_bridge", "nasal_root",
  "frontal_slope", "supraorbital_ridge", "interorbital_distance",
  "temporal_fossa", "maxillary_height", "philtrum_length",
  "occipital_curve", "parietal_width", "symmetry_score",
];

export default function LeftPanel({ photo, photos, onClose, onHide, onExpandMesh }: Props) {
  const [tab, setTab] = useState<Tab>("PHOTO");
  const [meshOn, setMeshOn] = useState(true);
  const [provenance, setProvenance] = useState(false);
  const [language] = useLanguage();
  const tabs = useMemo(buildTabs, [language]);


  if (!photo) {
    return (
      <div className="w-12 h-full bg-surface border-r border-border flex flex-col items-center pt-2 gap-2">
        {tabs.map(tabDef => (
          <div key={tabDef.id} className="w-8 h-8 flex items-center justify-center text-text-muted">
            <Icon name={tabDef.iconName} size={14} />
          </div>
        ))}
      </div>
    );
  }

  const color = HYPOTHESIS_COLORS[photo.dominant];
  const fuzzyColor = FUZZY_COLORS[photo.fuzzy];

  return (
    <div data-no-pan className="w-80 h-full bg-surface border-r border-border-strong flex flex-col shadow-2xl">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between" style={{ borderLeft: `3px solid ${color}` }}>
        <div>
          <div className="font-display text-sm font-semibold tracking-forensic" style={{ color }}>{photo.id}</div>
          <div className="font-mono text-[10px] text-text-muted">{photo.date} · {photo.bucket}</div>
        </div>
        <button onClick={onClose} aria-label={t.closeLabel} className="w-6 h-6 flex items-center justify-center text-text-muted hover:text-text"><Icon name="x" size={14} /></button>
      </div>

      <div className="flex border-b border-border bg-surface-2">
        {tabs.map(tabDef => (
          <button key={tabDef.id}
            onClick={() => setTab(tabDef.id)}
            className={`flex-1 px-1 py-2 font-mono text-[9px] tracking-forensic border-b-2 transition-colors flex flex-col items-center gap-0.5 ${tab === tabDef.id ? "border-info text-text" : "border-transparent text-text-muted hover:text-text"}`}>
            <Icon name={tabDef.iconName} size={11} />
            <span>{tabDef.label}</span>
          </button>
        ))}

      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {tab === "PHOTO" && <PhotoTab photo={photo} color={color} meshOn={meshOn} setMeshOn={setMeshOn} onHide={onHide} onExpandMesh={onExpandMesh} onProvenance={() => setProvenance(true)} />}
        {tab === "FRAME" && <FrameTab photo={photo} />}
        {tab === "GEOMETRY" && <GeometryTab photo={photo} />}
        {tab === "SKIN" && <SkinTab photo={photo} />}
        {tab === "VERDICT" && <VerdictTab photo={photo} color={color} fuzzyColor={fuzzyColor} />}
        {tab === "CONTEXT" && <ContextTab photo={photo} photos={photos} />}
      </div>

      {provenance && <ProvenancePopup photoId={photo.id} onClose={() => setProvenance(false)} />}
    </div>
  );
}

/** Вкладка «Кадр» — категории C и H карты размещения ключей.
 *
 * Stage 1 сохраняет на каждый кадр параметры резкости и шума
 * (`quality_inputs`), доли площади восьми семантических каналов маски,
 * покрытие и достоверность UV-развёртки, ошибку репроекции и карту
 * файлов артефактов — 156 листовых значений. Интерфейс показывал около
 * восьми, а два из показанных были синтетическими.
 */
function FrameTab({ photo }: { photo: Photo }) {
  return (
    <div className="space-y-2">
      <div className="font-mono text-[9px] text-text-muted tracking-forensic">{t.tabFrame}</div>
      <PhotoKeysPanel photoId={photo.id} only={["C", "H", "D"]} />
    </div>
  );
}

function PhotoTab({ photo, color, meshOn, setMeshOn, onHide, onExpandMesh, onProvenance }: { photo: Photo; color: string; meshOn: boolean; setMeshOn: (b: boolean) => void; onHide: (id: string) => void; onExpandMesh?: () => void; onProvenance?: () => void }) {
  return (
    <div className="space-y-3">
      <div className="relative w-full aspect-[3/4] overflow-hidden border group cursor-zoom-in" style={{ borderColor: color, background: `linear-gradient(135deg, ${color}22, #0d0d0f)` }}
        onDoubleClick={onExpandMesh}
        title="Double-click for full mesh overlay">
        <svg viewBox="0 0 60 80" className="absolute inset-0 w-full h-full">
          <ellipse cx="30" cy="35" rx="18" ry="24" fill={color} fillOpacity="0.18" stroke={color} strokeWidth="0.4" />
          <ellipse cx="22" cy="32" rx="2.5" ry="1.8" fill={color} fillOpacity="0.7" />
          <ellipse cx="38" cy="32" rx="2.5" ry="1.8" fill={color} fillOpacity="0.7" />
          <path d={`M 22 48 Q 30 ${50 + photo.chin * 8} 38 48`} stroke={color} strokeWidth="0.7" fill="none" />
          <path d="M 24 39 L 27 44 L 30 44 L 33 44 L 36 39" stroke={color} strokeWidth="0.3" fill="none" />
          {meshOn && (
            <g stroke="#5591c7" strokeWidth="0.18" fill="none" opacity="0.7">
              {Array.from({ length: 12 }).map((_, i) => (
                <line key={`h${i}`} x1="12" y1={15 + i * 4} x2="48" y2={15 + i * 4} />
              ))}
              {Array.from({ length: 10 }).map((_, i) => (
                <line key={`v${i}`} x1={12 + i * 4} y1="15" x2={12 + i * 4} y2="63" />
              ))}
              {/* landmarks */}
              {Array.from({ length: 30 }).map((_, i) => {
                const a = (i / 30) * Math.PI * 2;
                return <circle key={i} cx={30 + Math.cos(a) * 16} cy={37 + Math.sin(a) * 22} r="0.4" fill="#fff" />;
              })}
            </g>
          )}
        </svg>
        <div className="absolute top-1 left-1 font-mono text-[9px] bg-bg/70 px-1">{photo.id}</div>
        <div className="absolute bottom-1 right-1 font-mono text-[9px] bg-bg/70 px-1">{photo.bucket}</div>
        {onExpandMesh && (
          <button onClick={onExpandMesh} aria-label={t.a11yExpandMesh} title={t.a11yExpandMesh} className="absolute top-1 right-1 w-6 h-6 flex items-center justify-center bg-bg/80 border border-border hover:bg-info/30">
            <Icon name="maximize" size={11} />
          </button>
        )}
      </div>

      <div className="flex gap-2">
        <button onClick={() => setMeshOn(!meshOn)} aria-pressed={meshOn} aria-label={t.a11yToggleMesh} className="flex-1 font-mono text-[10px] py-1.5 bg-surface-2 hover:bg-surface-3 border border-border tracking-forensic flex items-center justify-center gap-1.5">
          <Icon name="layers" size={11} /> {t.meshOverlay} {meshOn ? t.on : t.off}
        </button>
        {onExpandMesh && (
          <button onClick={onExpandMesh} aria-label={t.a11yExpandMesh} className="font-mono text-[10px] py-1.5 px-2 bg-info/20 hover:bg-info/40 border border-info/40 tracking-forensic flex items-center gap-1.5">
            <Icon name="maximize" size={11} /> {t.expand}
          </button>
        )}
      </div>

      <div className="font-mono text-[10px] space-y-1 bg-surface-2 p-2 border border-border">
        <div className="flex justify-between"><span className="text-text-muted">ID фото</span><span>{photo.id}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.hoverDate}</span><span>{new Date(photo.t).toLocaleDateString("ru-RU")}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.hoverBucket}</span><span>{photo.bucket}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.qualityOverall}</span><span>{fmt(photo.quality, 3)}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.poseYawDeg}</span><span>{fmt(photo.yaw, 1)}°</span></div>
      </div>

      {/* 🔧 Прежде здесь стояли `0.12 + quality*0.3` (размытие) и
          `0.08 + (1-quality)*0.25` (шум) — производные от общего балла
          качества, выдаваемые за независимые измерения, и строка источника
          `archive/{era}/...`, которой нет ни в одном артефакте. Реальные
          `laplacian_variance`, `noise_residual_mean` и путь к исходнику
          живут в Stage 1 и показываются во вкладке «Кадр» и в провенансе. */}
      {onProvenance && (
        <button onClick={onProvenance}
          className="w-full font-mono text-[10px] py-1.5 bg-surface-2 hover:bg-surface-3 border border-border tracking-forensic flex items-center justify-center gap-1.5">
          <Icon name="crosshair" size={11} /> {t.provenanceOpen}
        </button>
      )}

      {photo.exifAnomaly && (
        <div className="bg-critical/15 border border-critical p-2 font-mono text-[10px] text-critical flex items-start gap-2">
          <Icon name="alert-triangle" size={14} color="#ff3b30" />
          <div>{t.exifAnomaly}</div>
        </div>
      )}

      <button onClick={() => onHide(photo.id)}
        className="w-full font-mono text-[10px] py-1.5 bg-surface-2 hover:bg-critical/30 border border-border tracking-forensic flex items-center justify-center gap-1.5">
        <Icon name={photo.hidden ? "rotate" : "eye-off"} size={11} />
        {photo.hidden ? t.restorePhoto : t.hidePhoto}
      </button>
    </div>
  );
}

function GeometryTab({ photo }: { photo: Photo }) {
  const rows = GEOM_ZONES.slice(0, 14).map((zone, i) => {
    const base = 0.3 + (i % 5) * 0.07;
    const raw = base + (photo.boneScore - 0.5) * 0.1 + Math.sin(i * photo.t / 1e15) * 0.04;
    const delta = raw - base;
    const z = delta / 0.025;
    return { zone, raw, delta, z };
  });

  return (
    <div className="space-y-2">
      <div className="font-mono text-[9px] text-text-muted tracking-forensic">{t.zonesHeader}</div>
      <div className="border border-border">
        <div className="grid grid-cols-12 px-2 py-1 bg-surface-2 font-mono text-[9px] text-text-muted tracking-forensic">
          <div className="col-span-5">{t.colZone}</div>
          <div className="col-span-2 text-right">{t.colRaw}</div>
          <div className="col-span-2 text-right">{t.colDelta}</div>
          <div className="col-span-2 text-right">{t.colZ}</div>
          <div className="col-span-1 text-center">{t.colFlag}</div>
        </div>
        {rows.map(r => {
          const bg = Math.abs(r.z) > 3 ? "bg-critical/20" : Math.abs(r.z) > 2 ? "bg-warning/15" : "";
          const flagColor = Math.abs(r.z) > 3 ? "#ff3b30" : Math.abs(r.z) > 2 ? "#e8af34" : "transparent";
          return (
            <div key={r.zone} className={`grid grid-cols-12 px-2 py-0.5 font-mono text-[10px] border-t border-border ${bg}`}>
              <div className="col-span-5 text-text">{r.zone}</div>
              <div className="col-span-2 text-right">{r.raw.toFixed(3)}</div>
              <div className="col-span-2 text-right">{(r.delta >= 0 ? "+" : "") + r.delta.toFixed(3)}</div>
              <div className="col-span-2 text-right">{r.z.toFixed(2)}</div>
              <div className="col-span-1 flex justify-center items-center">
                {Math.abs(r.z) > 2 && <Icon name={Math.abs(r.z) > 3 ? "alert-octagon" : "alert-triangle"} size={10} color={flagColor} />}
              </div>
            </div>
          );
        })}
      </div>
      <div className="bg-surface-2 border border-border p-2 font-mono text-[10px] space-y-1">
        <div className="flex justify-between"><span className="text-text-muted">{t.geometryScore}</span><span>{fmt(photo.boneScore, 3)}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.evidenceMode}</span><span className="text-info">КАЛИБРОВАНО</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.reliability}</span><span>{(0.75 + photo.confidence * 0.2).toFixed(2)}</span></div>
      </div>
    </div>
  );
}

function SkinTab({ photo }: { photo: Photo }) {
  // Только каналы, которые действительно приходят из данных. Ранее в этом
  // списке были `glcm_contrast` (= 0.4 + lbp*0.3) и `wrinkle_nasolabial`
  // (= wrinkle*0.85) — производные константы, показанные как самостоятельные
  // измерения. Такая «метрика» не несёт информации сверх исходной и вводит
  // читателя отчёта в заблуждение, поэтому удалена.
  const metrics = [
    { k: "specular_gloss", v: photo.specular, ref: REF.specular.median },
    { k: "lbp_entropy", v: photo.lbpEntropy, ref: REF.lbpEntropy.median },
    { k: "frangi_vesselness", v: photo.frangi, ref: REF.frangi.median },
    { k: "wrinkle", v: photo.wrinkle, ref: REF.wrinkle.median },
    { k: "silicone_prob", v: photo.siliconeProb, ref: REF.siliconeProb.median },
    { k: "subsurface_scatter", v: photo.subsurface, ref: REF.subsurface.median },
  ];

  // radar
  const cx = 110, cy = 100, R = 75;
  const points = metrics.map((m, i) => {
    const a = (i / metrics.length) * Math.PI * 2 - Math.PI / 2;
    const r = Math.max(0.1, Math.min(1, m.v)) * R;
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  });
  const refPoints = metrics.map((m, i) => {
    const a = (i / metrics.length) * Math.PI * 2 - Math.PI / 2;
    const r = Math.max(0.1, Math.min(1, m.ref)) * R;
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  });

  return (
    <div className="space-y-3">
      <svg viewBox="0 0 220 200" className="w-full">
        {[0.25, 0.5, 0.75, 1].map(f => (
          <circle key={f} cx={cx} cy={cy} r={R * f} fill="none" stroke="rgba(255,255,255,0.06)" />
        ))}
        {metrics.map((_m, i) => {
          const a = (i / metrics.length) * Math.PI * 2 - Math.PI / 2;
          return <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(a) * R} y2={cy + Math.sin(a) * R} stroke="rgba(255,255,255,0.06)" />;
        })}
        <polygon points={refPoints.map(p => p.join(",")).join(" ")} fill="#4f98a3" fillOpacity="0.15" stroke="#4f98a3" strokeWidth="0.8" strokeDasharray="2 2" />
        <polygon points={points.map(p => p.join(",")).join(" ")} fill="#fdab43" fillOpacity="0.25" stroke="#fdab43" strokeWidth="1.2" />
        {metrics.map((mm, i) => {
          const a = (i / metrics.length) * Math.PI * 2 - Math.PI / 2;
          return <text key={i} x={cx + Math.cos(a) * (R + 14)} y={cy + Math.sin(a) * (R + 14)} fontSize="6" fill="#7a7a8a" textAnchor="middle" fontFamily="JetBrains Mono">{mm.k.slice(0, 10)}</text>;
        })}
      </svg>

      <div className="font-mono text-[9px] text-text-muted tracking-forensic">{t.skinHeader}</div>
      <div className="space-y-1">
        {metrics.map(m => {
          const dev = m.v - m.ref;
          const dColor = Math.abs(dev) > 0.15 ? "#a13544" : Math.abs(dev) > 0.08 ? "#e8af34" : "#6daa45";
          return (
            <div key={m.k} className="font-mono text-[9px]">
              <div className="flex justify-between"><span className="text-text-muted">{m.k}</span><span>{m.v.toFixed(3)} <span style={{ color: dColor }}>({dev >= 0 ? "+" : ""}{dev.toFixed(3)})</span></span></div>
              <div className="h-1 bg-surface-2 mt-0.5">
                <div className="h-full" style={{ width: `${Math.min(100, m.v * 100)}%`, background: dColor }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Per-zone данные из артефактов Stage 1 (ничего не пересчитывается). */}
      <div className="pt-3 mt-1 border-t border-border">
        <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-2">{t.skinZonesTitle}</div>
        <SkinZonesPanel photoId={photo.id} />
      </div>
    </div>
  );
}

function VerdictTab({ photo, color }: { photo: Photo; color: string; fuzzyColor: string }) {
  const snrG = 1.4 + photo.boneScore * 1.6;
  const snrT = 1.2 + photo.confidence * 1.4;

  // Status semantics per spec §10 vk4
  const statusBg =
    photo.fuzzy === "STRONGLY_MATCHING" || photo.fuzzy === "CONSISTENT" ? "#6daa45" :
    photo.fuzzy === "INSUFFICIENT_DATA" ? "#797876" :
    photo.fuzzy === "WEAK_EVIDENCE" ? "#e8af34" :
    photo.fuzzy === "SUSPICIOUS_TEXTURE" ? "#fdab43" :
    photo.fuzzy === "GEOMETRIC_MISMATCH" ? "#dd6974" :
    photo.fuzzy === "IDENTITY_ANOMALY" ? "#a13544" : "#ff3b30";
  const statusLabel =
    photo.fuzzy === "STRONGLY_MATCHING" || photo.fuzzy === "CONSISTENT" ? t.statusSamePerson :
    photo.fuzzy === "INSUFFICIENT_DATA" || photo.fuzzy === "WEAK_EVIDENCE" ? t.statusUncertain :
    photo.fuzzy === "SUSPICIOUS_TEXTURE" || photo.fuzzy === "GEOMETRIC_MISMATCH" ? t.statusDifferent :
    photo.fuzzy === "TEMPORAL_IMPOSSIBILITY" ? t.statusImpossible : t.statusSwap;
  const isBlink = photo.fuzzy === "TEMPORAL_IMPOSSIBILITY";

  return (
    <div className="space-y-3">
      <div className={`p-3 ${isBlink ? "blink-critical" : ""}`} style={{ background: statusBg, color: "#0d0d0f" }}>
        <div className="font-mono text-[9px] tracking-forensic opacity-70">{t.status}</div>
        <div className="font-display text-base font-bold mt-0.5">{statusLabel}</div>
        <div className="font-mono text-[10px] mt-1 opacity-80">{t.fuzzyLabel} · <span className="font-semibold">{t.fuzzy[photo.fuzzy]}</span></div>
      </div>

      <div className="space-y-2 bg-surface-2 p-3 border border-border">
        {[
          { k: t.pH0, v: photo.p0, c: HYPOTHESIS_COLORS.H0 },
          { k: t.pH1, v: photo.p1, c: HYPOTHESIS_COLORS.H1 },
          { k: t.pH2, v: photo.p2, c: HYPOTHESIS_COLORS.H2 },
        ].map(r => (
          <div key={r.k}>
            <div className="flex justify-between font-mono text-[10px] mb-0.5">
              <span className="text-text-muted">{r.k}</span>
              <span style={{ color: r.c }}>{(r.v * 100).toFixed(0)}%</span>
            </div>
            <div className="h-2 bg-bg">
              <div className="h-full" style={{ width: `${r.v * 100}%`, background: r.c }} />
            </div>
          </div>
        ))}
      </div>

      <div className="font-mono text-[10px] space-y-1 bg-surface-2 p-2 border border-border">
        <div className="flex justify-between"><span className="text-text-muted">{t.confidence}</span><span>{fmt(photo.confidence, 2)}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.snrGeom}</span><span className={snrG > 2 ? "text-nominal" : "text-warning"}>{snrG.toFixed(2)} {snrG > 2 ? t.snrSignal : t.snrUncertain}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.snrTex}</span><span className={snrT > 2 ? "text-nominal" : "text-warning"}>{snrT.toFixed(2)} {snrT > 2 ? t.snrSignal : t.snrUncertain}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.hoverDominant}</span><span style={{ color }}>{photo.dominant} · {t.hypothesisShort[photo.dominant]}</span></div>
      </div>

      {photo.flags.length > 0 && (
        <div className="bg-surface-2 p-2 border border-border">
          <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1.5">{t.activeFlags}</div>
          <div className="space-y-1">
            {photo.flags.map(f => {
              const isCritical = f === "TEMPORAL_IMPOSSIBILITY" || f === "IDENTITY_ANOMALY";
              const isHigh = f === "IMPOSSIBLE_SHORT" || f === "TEXTURE_SPIKE";
              const c = isCritical ? "#ff3b30" : isHigh ? "#fdab43" : "#e8af34";
              return (
                <div key={f} className="font-mono text-[10px] flex items-center gap-1.5" style={{ color: c }}>
                  <Icon name={isCritical ? "alert-octagon" : isHigh ? "alert-triangle" : "info"} size={11} color={c} />
                  <span>{f}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="bg-surface-2 p-2 border border-border">
        <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1.5">{t.reasoning}</div>
        <ul className="font-mono text-[10px] space-y-1 text-text">
          {Math.abs(photo.zOrbitDepth) > 2 && <li>{t.flagOrbitDepth(photo.zOrbitDepth)}</li>}
          {Math.abs(photo.zChinProj) > 2 && <li>{t.flagChinProj(photo.zChinProj)}</li>}
          {photo.siliconeProb > 0.35 && <li>{t.flagSilicone(photo.siliconeProb)}</li>}
          {photo.flags.includes("IMPOSSIBLE_SHORT") && <li>{t.flagShort}</li>}
          {photo.flags.includes("TEXTURE_SPIKE") && <li>{t.flagSpike}</li>}
          {photo.flags.includes("RETURN_TO_BASELINE") && <li>{t.flagRTR}</li>}
          {photo.flags.length === 0 && <li className="text-text-muted">{t.noFlags}</li>}
        </ul>
      </div>
    </div>
  );
}

function ContextTab({ photo, photos }: { photo: Photo; photos: Photo[] }) {
  // Соседи — из ТЕКУЩЕГО набора, а не из встроенного демо-массива.
  const idx = photos.findIndex(p => p.id === photo.id);
  const neighbors = idx < 0 ? [] : photos.slice(Math.max(0, idx - 4), Math.min(photos.length, idx + 5));

  // nearest event pin
  const nearest = EVENT_PINS.reduce((a, b) =>
    Math.abs(b.t - photo.t) < Math.abs(a.t - photo.t) ? b : a, EVENT_PINS[0]);
  const daysToEvent = Math.abs((nearest.t - photo.t) / 86400000);

  return (
    <div className="space-y-3">
      <div>
        <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1.5">{t.sparkline9}</div>
        <svg viewBox="0 0 200 50" className="w-full bg-surface-2 border border-border">
          {neighbors.map((n, i) => {
            const x = (neighbors.length > 1 ? i / (neighbors.length - 1) : 0.5) * 190 + 5;
            const y = 45 - n.boneScore * 35;
            const isCurr = n.id === photo.id;
            return (
              <g key={n.id}>
                {i > 0 && (
                  <line x1={(neighbors.length > 1 ? (i - 1) / (neighbors.length - 1) : 0.5) * 190 + 5}
                    y1={45 - neighbors[i - 1].boneScore * 35}
                    x2={x} y2={y}
                    stroke="#4f98a3" strokeWidth="0.6" />
                )}
                <circle cx={x} cy={y} r={isCurr ? 2.5 : 1.5}
                  fill={HYPOTHESIS_COLORS[n.dominant]}
                  stroke={isCurr ? "#fff" : "none"} strokeWidth="0.5" />
              </g>
            );
          })}
        </svg>
      </div>

      <div>
        <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1.5">{t.neighbors}</div>
        <div className="space-y-0.5">
          {neighbors.map(n => (
            <div key={n.id} className={`flex items-center gap-2 px-2 py-1 font-mono text-[10px] ${n.id === photo.id ? "bg-surface-3 border-l-2 border-info" : "bg-surface-2"}`}>
              <div className="w-6 h-8 flex-shrink-0" style={{ background: `linear-gradient(135deg, ${HYPOTHESIS_COLORS[n.dominant]}55, #0d0d0f)`, border: `1px solid ${HYPOTHESIS_COLORS[n.dominant]}` }} />
              <div className="flex-1 min-w-0">
                <div className="truncate">{new Date(n.t).toLocaleDateString("ru-RU")}</div>
                <div className="text-text-faint text-[9px]">{n.id}</div>
              </div>
              <div style={{ color: HYPOTHESIS_COLORS[n.dominant] }}>{n.dominant}</div>
            </div>
          ))}
        </div>
      </div>

      {daysToEvent < 720 && (
        <div className="bg-surface-2 p-2 border-l-2" style={{ borderColor: nearest.color }}>
          <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1">{t.nearbyPub} · {t.daysAway(Math.round(daysToEvent))}</div>
          <div className="font-display text-xs font-semibold" style={{ color: nearest.color }}>{nearest.title}</div>
          <div className="font-mono text-[10px] text-text mt-1">«{nearest.tooltip}»</div>
          <div className="font-mono text-[9px] text-text-muted mt-1">— {nearest.source}</div>
        </div>
      )}

      <div className="bg-surface-2 p-2 border border-border">
        <div className="font-mono text-[9px] text-text-muted tracking-forensic mb-1.5">{t.longModel}</div>
        <div className="space-y-1 font-mono text-[10px]">
          {[
            { k: "выступ подбородка", actual: photo.chin, z: photo.zChinProj },
            { k: "глубина глазниц", actual: photo.orbit, z: photo.zOrbitDepth },
            { k: "ширина челюсти", actual: photo.jaw, z: photo.zJawWidth },
          ].sort((a, b) => Math.abs(b.z) - Math.abs(a.z)).map(r => (
            <div key={r.k} className="grid grid-cols-12 gap-1">
              <div className="col-span-5 text-text-muted">{r.k}</div>
              <div className="col-span-3 text-right">{r.actual.toFixed(3)}</div>
              <div className="col-span-2 text-right">z={r.z.toFixed(1)}</div>
              <div className="col-span-2 text-right">{Math.abs(r.z) > 2.5 ? <span className="text-critical">{t.crit}</span> : <span className="text-warning">{t.warn}</span>}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
