import { useState, useMemo } from "react";
import { fmt, fmtPercent } from "../format";

import { Photo, HYPOTHESIS_COLORS, FUZZY_COLORS } from "../data";
import { photoImageUrl } from "../api";
import Icon from "./Icon";
import { t, useLanguage } from "../i18n";
import SkinZonesPanel from "./SkinZonesPanel";
import PhotoKeysPanel from "./PhotoKeysPanel";
import ProvenancePopup from "./ProvenancePopup";
import { useSettings, isVisibleAt } from "../settings";


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


export default function LeftPanel({ photo, photos, onClose, onHide, onExpandMesh }: Props) {
  const [tab, setTab] = useState<Tab>("PHOTO");
  const [meshOn, setMeshOn] = useState(true);
  const [provenance, setProvenance] = useState(false);
  const [language] = useLanguage();
  const { detailLevel } = useSettings();
  
  const tabs = useMemo(() => {
    const all = buildTabs();
    if (!isVisibleAt("expert", detailLevel)) {
      return all.filter(t => t.id !== "FRAME");
    }
    return all;
  }, [language, detailLevel]);


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
        <img src={photoImageUrl(photo.id, "original")} alt={photo.id} className="absolute inset-0 w-full h-full object-contain" />
        {meshOn && <div className="absolute inset-0 border border-info/40 pointer-events-none"><span className="absolute left-1 bottom-1 bg-bg/80 px-1 font-mono text-[8px] text-info">3D — в полном просмотре</span></div>}
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
          <div>{t.exifAnomaly}{photo.exifDate && <div className="mt-1 opacity-80">EXIF: {photo.exifDate} · filename: {photo.date}{typeof photo.dateDeltaDays === "number" ? ` · Δ ${photo.dateDeltaDays} d` : ""}</div>}{photo.sourceClaimedDate && <div className="mt-1 opacity-80">Source claim: {photo.sourceClaimedDate}{typeof photo.sourceClaimedDeltaDays === "number" ? ` · Δ ${photo.sourceClaimedDeltaDays} d` : ""}</div>}</div>
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
  const stage2Available = photo.analysisStage !== "stage1_inventory" && photo.measurementStatus !== "not_compared";
  return (
    <div className="space-y-2">
      {!stage2Available && (
        <div role="status" className="bg-warning/10 border border-warning/40 p-3 font-mono text-[10px] text-warning">
          Сравнительная геометрия, зональные отклонения и z-оценки ещё не рассчитаны. Доступны реальные артефакты Stage 1 во вкладке «Кадр».
        </div>
      )}
      <div className="bg-surface-2 border border-border p-2 font-mono text-[10px] space-y-1">
        <div className="flex justify-between"><span className="text-text-muted">{t.geometryScore}</span><span>{fmt(photo.boneScore, 3)}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.evidenceMode}</span><span className={stage2Available ? "text-info" : "text-warning"}>{stage2Available ? "ИЗМЕРЕНО" : "НЕ РАССЧИТАНО"}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.reliability}</span><span>{fmt(photo.confidence, 2)}</span></div>
      </div>
      <PhotoKeysPanel photoId={photo.id} only={["D"]} defaultOpen />
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
    { k: "specular_gloss", v: photo.specular },
    { k: "lbp_entropy", v: photo.lbpEntropy },
    { k: "frangi_vesselness", v: photo.frangi },
    { k: "wrinkle", v: photo.wrinkle },
    { k: "silicone_prob", v: photo.siliconeProb },
    { k: "subsurface_scatter", v: photo.subsurface },
  ];

  // radar
  const cx = 110, cy = 100, R = 75;
  const points = metrics.map((m, i) => {
    const a = (i / metrics.length) * Math.PI * 2 - Math.PI / 2;
    const r = Math.max(0.1, Math.min(1, m.v)) * R;
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
        <polygon points={points.map(p => p.join(",")).join(" ")} fill="#fdab43" fillOpacity="0.25" stroke="#fdab43" strokeWidth="1.2" />
        {metrics.map((mm, i) => {
          const a = (i / metrics.length) * Math.PI * 2 - Math.PI / 2;
          return <text key={i} x={cx + Math.cos(a) * (R + 14)} y={cy + Math.sin(a) * (R + 14)} fontSize="6" fill="#7a7a8a" textAnchor="middle" fontFamily="JetBrains Mono">{mm.k.slice(0, 10)}</text>;
        })}
      </svg>

      <div className="font-mono text-[9px] text-text-muted tracking-forensic">{t.skinHeader}</div>
      <div className="space-y-1">
        {metrics.map(m => (
          <div key={m.k} className="font-mono text-[9px]">
            <div className="flex justify-between"><span className="text-text-muted">{m.k}</span><span>{Number.isFinite(m.v) ? m.v.toFixed(3) : "—"}</span></div>
            <div className="h-1 bg-surface-2 mt-0.5"><div className="h-full bg-info" style={{ width: `${Number.isFinite(m.v) ? Math.max(0, Math.min(100, m.v * 100)) : 0}%` }} /></div>
          </div>
        ))}
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
  const stage2Available = photo.analysisStage !== "stage1_inventory" && photo.measurementStatus !== "not_compared";
  const snrG = Number.isFinite(photo.boneScore) ? 1.4 + photo.boneScore * 1.6 : Number.NaN;
  const snrT = Number.isFinite(photo.confidence) ? 1.2 + photo.confidence * 1.4 : Number.NaN;

  if (!stage2Available) return (
    <div role="status" className="space-y-3">
      <div className="bg-warning/10 border border-warning/40 p-3 font-mono text-[10px] text-warning">
        Вердикты, вероятности гипотез, SNR и сравнительные аномалии недоступны до Stage 2. Интерфейс не подменяет их демонстрационными значениями.
      </div>
      <div className="bg-surface-2 border border-border p-2 font-mono text-[10px]">
        <div className="flex justify-between"><span className="text-text-muted">Статус измерений</span><span>НЕ СРАВНИВАЛОСЬ</span></div>
        <div className="flex justify-between"><span className="text-text-muted">Качество кадра</span><span>{fmt(photo.quality, 3)}</span></div>
      </div>
    </div>
  );

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
              <span style={{ color: r.c }}>{fmtPercent(r.v, 0)}</span>
            </div>
            <div className="h-2 bg-bg">
              <div className="h-full" style={{ width: `${Number.isFinite(r.v) ? r.v * 100 : 0}%`, background: r.c }} />
            </div>
          </div>
        ))}
      </div>

      <div className="font-mono text-[10px] space-y-1 bg-surface-2 p-2 border border-border">
        <div className="flex justify-between"><span className="text-text-muted">{t.confidence}</span><span>{fmt(photo.confidence, 2)}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.snrGeom}</span><span className={snrG > 2 ? "text-nominal" : "text-warning"}>{fmt(snrG, 2)} {Number.isFinite(snrG) ? (snrG > 2 ? t.snrSignal : t.snrUncertain) : ""}</span></div>
        <div className="flex justify-between"><span className="text-text-muted">{t.snrTex}</span><span className={snrT > 2 ? "text-nominal" : "text-warning"}>{fmt(snrT, 2)} {Number.isFinite(snrT) ? (snrT > 2 ? t.snrSignal : t.snrUncertain) : ""}</span></div>
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
              <div className="col-span-3 text-right">{fmt(r.actual, 3)}</div>
              <div className="col-span-2 text-right">z={fmt(r.z, 1)}</div>
              <div className="col-span-2 text-right">{Number.isFinite(r.z) ? (Math.abs(r.z) > 2.5 ? <span className="text-critical">{t.crit}</span> : <span className="text-warning">{t.warn}</span>) : <span className="text-text-faint">—</span>}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
