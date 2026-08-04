import { useCallback, useEffect, useMemo, useRef, useState, type WheelEvent as ReactWheelEvent } from "react";
import {
  batchPairs, calibrationThresholds, fetchSettings, image, timeline,
  timelineFindings, type AppSettings, type BinFindings, type DenseZone, type PairFinding,
} from "../../shared/api";
import { displacementRamp } from "../../shared/landmarkRenderer";
import FilterPanel, { type FilterEvalResult } from "./FilterPanel";
import { LABEL, POSES, type Photo, type Pose, type TimelineData } from "../../shared/types";
import type { CompareRequest } from "../../app/App";

const EMPTY: TimelineData = { photos: [], mode: "loading", message: "Подключение к app6…", eras: {}, rejected: [] };
const MIN_THUMB = 30;
const MAX_THUMB = 150;
const MAX_ZOOM = 96;
const CONTROL_WIDTH = 220;
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

type MetricKey = "qualityStatus" | "quality" | "authenticityStatus" | "authenticityScore" | "expressionMagnitude" | "jawOpenDegree" | "jawOpenDetected" | "jawOpenRatio" | "smileDetected" | "landmarkShift" | "confidence" | "boneScore" | "yaw" | "pitch" | "roll" | "orbit" | "chin" | "jaw" | "cheek" | "symmetry" | "siliconeProb" | "specular" | "lbpEntropy" | "frangi" | "wrinkle";
type MetricKind = "line" | "status" | "boolean" | "landmark";
interface MetricDef { key: MetricKey; label: string; color: string; unit?: string; kind?: MetricKind; aliases?: string[] }
const METRICS: MetricDef[] = [
  { key: "qualityStatus", label: "Quality · status", color: "#68c3cf", kind: "status", aliases: ["quality_status", "qualityStatus"] },
  { key: "quality", label: "Quality · score", color: "#68c3cf", aliases: ["quality", "quality_score"] },
  { key: "authenticityStatus", label: "Authenticity · status", color: "#7ea8ff", kind: "status", aliases: ["authenticity_status", "authenticityStatus"] },
  { key: "authenticityScore", label: "Authenticity · score", color: "#7ea8ff", aliases: ["authenticity_score", "authenticityScore"] },
  { key: "expressionMagnitude", label: "Expression magnitude", color: "#d98fe7", aliases: ["expression_magnitude", "expressionMagnitude"] },
  { key: "jawOpenDegree", label: "Jaw-open degree", color: "#ff9a68", aliases: ["jaw_open_degree", "jawOpenDegree"] },
  { key: "jawOpenDetected", label: "Jaw-open detected", color: "#f37983", kind: "boolean", aliases: ["jaw_open_detected", "jawOpenDetected"] },
  { key: "jawOpenRatio", label: "Jaw-open ratio", color: "#efb84d", aliases: ["jaw_open_ratio", "jawOpenRatio"] },
  { key: "smileDetected", label: "Smile detected", color: "#e56ac5", kind: "boolean", aliases: ["smile_detected", "smileDetected"] },
  { key: "landmarkShift", label: "Aligned LDM 106 + 134", color: "#74d492", kind: "landmark" },
  { key: "confidence", label: "Confidence", color: "#74d492" }, { key: "boneScore", label: "Bone score", color: "#efb84d" },
  { key: "orbit", label: "Orbit", color: "#7ea8ff" }, { key: "chin", label: "Chin", color: "#ff9a68" }, { key: "jaw", label: "Jaw", color: "#f37983" },
  { key: "cheek", label: "Cheek", color: "#b585e7" }, { key: "symmetry", label: "Symmetry", color: "#76d0aa" },
  { key: "yaw", label: "Yaw", color: "#54b7ec", unit: "°" }, { key: "pitch", label: "Pitch", color: "#8d98ff", unit: "°" }, { key: "roll", label: "Roll", color: "#cb8cff", unit: "°" },
  { key: "siliconeProb", label: "Texture diagnostic", color: "#e56ac5" }, { key: "specular", label: "Specular", color: "#d9d56e" }, { key: "lbpEntropy", label: "LBP entropy", color: "#62ced5" },
  { key: "frangi", label: "Frangi", color: "#f38ca8" }, { key: "wrinkle", label: "Wrinkle", color: "#d28b69" },
];
interface PaneConfig { id: number; pose: Pose; metrics: MetricKey[]; anomalyOnly: boolean; minQuality: number }
interface PlacedPhoto { photo: Photo; x: number; row: number }

function rawMetric(photo: Photo, metric: MetricDef): unknown {
  for (const key of metric.aliases || [metric.key]) if (key in photo) return photo[key];
  return undefined;
}
function numeric(photo: Photo, metric: MetricDef): number | null {
  const value = rawMetric(photo, metric);
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function categoricalTone(value: unknown, kind: MetricKind | undefined): "good" | "warning" | "bad" | "missing" {
  if (value === undefined || value === null || value === "") return "missing";
  if (kind === "boolean") return value === true || String(value).toLowerCase() === "true" ? "bad" : "good";
  const text = String(value).toLowerCase();
  if (/complete|pass|good|high|verified|available|authentic/.test(text)) return "good";
  if (/limited|medium|warn|review|pending/.test(text)) return "warning";
  if (/fail|invalid|low|reject|conflict|missing|unavailable/.test(text)) return "bad";
  return "warning";
}
function findNumber(value: unknown, aliases: string[]): number | null {
  const wanted = new Set(aliases.map(item => item.toLowerCase())); const stack: unknown[] = [value]; const seen = new Set<object>();
  while (stack.length) { const current = stack.pop(); if (!current || typeof current !== "object" || seen.has(current)) continue; seen.add(current); for (const [key, child] of Object.entries(current as Record<string, unknown>)) { if (wanted.has(key.toLowerCase()) && typeof child === "number" && Number.isFinite(child)) return child; if (child && typeof child === "object") stack.push(child); } }
  return null;
}
function anomalyIcon(flag: string): string {
  const value = flag.toUpperCase();
  if (value.includes("RETURN")) return "↩";
  if (value.includes("TEXTURE") || value.includes("SKIN")) return "◈";
  if (value.includes("SMILE") || value.includes("JAW") || value.includes("EXPRESSION")) return "◉";
  if (value.includes("TEMPORAL") || value.includes("IMPOSSIBLE")) return "⚠";
  if (value.includes("QUALITY") || value.includes("VISIBILITY")) return "!";
  return "◆";
}
function anomalyTone(flag: string): string {
  const value = flag.toUpperCase();
  if (value.includes("IMPOSSIBLE") || value.includes("CRITICAL")) return "critical";
  if (value.includes("RETURN") || value.includes("QUALITY") || value.includes("EXPRESSION")) return "warning";
  return "info";
}
function placeSingleRow(photos: Photo[], xOf: (time: number) => number, size: number): PlacedPhoto[] {
  let nextCenter = size / 2;
  return photos.map(photo => {
    const x = Math.max(xOf(photo.t), nextCenter);
    nextCenter = x + size + 4;
    return { photo, x, row: 0 };
  });
}

function MetricTrack({ metric, photos, positionOf, width }: { metric: MetricDef; photos: Photo[]; positionOf: (photo: Photo) => number; width: number }) {
  if (metric.kind === "status" || metric.kind === "boolean") return <div className="metric-track categorical-track"><div className="metric-scale"><b style={{ color: metric.color }}>{metric.label}</b><span>source</span><span>status</span></div>{photos.map(photo => { const value = rawMetric(photo, metric); const tone = categoricalTone(value, metric.kind); return <button key={photo.id} className={`status-cube ${tone}`} style={{ left: positionOf(photo) - 6 }} title={`${photo.id}: ${value == null ? "нет данных" : String(value)}`}><span>{metric.kind === "boolean" ? value === true ? "1" : value === false ? "0" : "—" : ""}</span></button>; })}</div>;
  const values = photos.map(photo => ({ photo, value: numeric(photo, metric) })).filter((row): row is { photo: Photo; value: number } => row.value !== null);
  const min = values.length ? Math.min(...values.map(row => row.value)) : 0, max = values.length ? Math.max(...values.map(row => row.value)) : 1, span = max === min ? 1 : max - min;
  const points = values.map(row => `${positionOf(row.photo)},${48 - ((row.value - min) / span) * 34}`).join(" ");
  return <div className="metric-track"><div className="metric-scale"><b style={{ color: metric.color }}>{metric.label}</b><span>{max.toFixed(3)}{metric.unit}</span><span>{min.toFixed(3)}{metric.unit}</span></div><svg width={width} height="56"><line x1="0" y1="48" x2={width} y2="48" stroke="#ffffff12"/><polyline points={points} fill="none" stroke={metric.color} strokeWidth="1.6"/>{values.map(row => <circle key={row.photo.id} cx={positionOf(row.photo)} cy={48 - ((row.value - min) / span) * 34} r="2.2" fill={metric.color}><title>{row.photo.id}: {row.value}</title></circle>)}</svg></div>;
}
interface ShiftPair { a: Photo; b: Photo; ldm106: number | null; ldm134: number | null; cal106: boolean; cal134: boolean }
const BATCH_CACHE = new Map<string, ShiftPair>();
function cachedBatchPair(a: Photo, b: Photo, key: string): Promise<ShiftPair | null> {
  const cached = BATCH_CACHE.get(key);
  if (cached) return Promise.resolve(cached);
  return batchPairs([[a.id, b.id]], 106)
    .then(result => {
      const row106 = result.results[0];
      if (!row106) return null;
      return batchPairs([[a.id, b.id]], 134).then(result134 => {
        const row134 = result134.results[0];
        const pair: ShiftPair = {
          a, b,
          ldm106: row106.rms,
          ldm134: row134?.rms ?? null,
          cal106: row106.calibrated,
          cal134: Boolean(row134?.calibrated),
        };
        BATCH_CACHE.set(key, pair);
        return pair;
      });
    })
    .catch(() => null);
}
function LandmarkShiftTrack({ photos, positionOf, thresholds }: { photos: Photo[]; positionOf: (photo: Photo) => number; thresholds: { tolerance: number; suspect: number; calibrated: boolean } | null }) {
  const [rows, setRows] = useState<ShiftPair[]>([]); const [loading, setLoading] = useState(false);
  const [cal106Ref, setCal106Ref] = useState<{ tolerance: number; suspect: number } | null>(null);
  const [cal134Ref, setCal134Ref] = useState<{ tolerance: number; suspect: number } | null>(null);
  useEffect(() => { void calibrationThresholds().then(data => {
    if (!data.calibrated) return;
    const byKey = new Map(data.references.map(ref => [`${ref.pose_bin}:${ref.count}`, ref]));
    const pick = (pose: string, count: 106 | 134) => {
      const ref = byKey.get(`${pose}:${count}`);
      if (!ref?.scalar.p95) return null;
      return { tolerance: ref.scalar.p95 ?? 0, suspect: (ref.scalar.p95 ?? 0) * 1.6 };
    };
    const pose = photos[0]?.bucket ?? "frontal";
    const ref106 = pick(pose, 106);
    const ref134 = pick(pose, 134);
    setCal106Ref(ref106); setCal134Ref(ref134);
  }).catch(() => undefined); }, [photos]);
  useEffect(() => { let dead = false; if (photos.length < 2) { setRows([]); return; } setLoading(true);
    const keys = photos.slice(1).map((b, index) => `${photos[index].id}|${b.id}`);
    Promise.all(photos.slice(1).map((b, index) => cachedBatchPair(photos[index], b, keys[index]))).then(values => {
      if (!dead) setRows(values.filter((value): value is ShiftPair => value !== null));
    }).finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [photos]);
  const tone = (value: number | null, ref: { tolerance: number; suspect: number } | null, calibrated: boolean) => {
    if (value === null) return "missing";
    if (ref && calibrated) return value <= ref.tolerance ? "good" : value <= ref.suspect ? "warning" : "bad";
    if (!thresholds) return "missing";
    return value <= thresholds.tolerance ? "good" : value <= thresholds.suspect ? "warning" : "bad";
  };
  return <div className="landmark-shift-track"><div className="metric-scale"><b>Aligned LDM shift</b><span>106</span><span>134</span></div>{loading && <em className="pair-loading">pairs…</em>}{rows.map(row => { const x = (positionOf(row.a) + positionOf(row.b)) / 2; return <div className="shift-pair" key={`${row.a.id}-${row.b.id}`} style={{ left: x - 15 }} title={`${row.a.id} → ${row.b.id}\nLDM106: ${row.ldm106 ?? "—"}\nLDM134: ${row.ldm134 ?? "—"}`}><i className={tone(row.ldm106, cal106Ref, row.cal106)}>106</i><i className={tone(row.ldm134, cal134Ref, row.cal134)}>134</i></div>; })}<div className="shift-legend"><span className="good"/>≤ {thresholds?.tolerance ?? "—"}<span className="warning"/>≤ {thresholds?.suspect ?? "—"}<span className="bad"/>аномально{cal106Ref ? <b>calibrated</b> : <b>diagnostic</b>}</div></div>;
}

function PaneControls({ pane, index, count, update, remove, add }: { pane: PaneConfig; index: number; count: number; update: (patch: Partial<PaneConfig>) => void; remove: () => void; add: () => void }) {
  const [metricsOpen, setMetricsOpen] = useState(false);
  const toggleMetric = (key: MetricKey) => update({ metrics: pane.metrics.includes(key) ? pane.metrics.filter(item => item !== key) : [...pane.metrics, key] });
  return <div className="pane-controls">
    <div className="pane-number">VIEW {index + 1}</div>
    <select value={pane.pose} onChange={event => update({ pose: event.target.value as Pose })}>{POSES.map(pose => <option value={pose} key={pose}>{LABEL[pose]}</option>)}</select>
    <div className="pane-actions"><button onClick={() => setMetricsOpen(value => !value)} className={metricsOpen ? "active" : ""}>≋ Метрики <em>{pane.metrics.length}</em></button>{count < POSES.length && <button onClick={add}>＋ Ракурс</button>}{count > 1 && <button className="remove" onClick={remove}>×</button>}</div>
    {metricsOpen && <div className="metric-menu">{METRICS.map(metric => <label key={metric.key}><input type="checkbox" checked={pane.metrics.includes(metric.key)} onChange={() => toggleMetric(metric.key)} /><i style={{ background: metric.color }} /><span>{metric.label}</span></label>)}</div>}
    <label className="pane-filter"><input type="checkbox" checked={pane.anomalyOnly} onChange={event => update({ anomalyOnly: event.target.checked })}/><span>Только с аномалиями</span></label>
    <label className="pane-quality"><span>Quality ≥</span><input type="range" min="0" max="1" step=".05" value={pane.minQuality} onChange={event => update({ minQuality: Number(event.target.value) })}/><b>{pane.minQuality.toFixed(2)}</b></label>
  </div>;
}

interface FindingsLayers { anomalies: boolean; shape: boolean; texture: boolean; density: boolean }

function shapeColor(rmse: number | null, maxRmse: number): string {
  if (rmse === null || !Number.isFinite(rmse)) return "#3a4654";
  const t = Math.min(1, Math.max(0, rmse / Math.max(maxRmse, 1e-6)));
  const [r, g, b] = displacementRamp(t);
  return `rgb(${r},${g},${b})`;
}

function FindingsStrip({ bin, xOf, width, layers, positionMap }: {
  bin: BinFindings | null;
  xOf: (time: number) => number;
  width: number;
  layers: FindingsLayers;
  positionMap: Map<string, number>;
}) {
  if (!bin) return null;
  const xOfPhoto = (id: string | null | undefined) => {
    if (!id) return null;
    const fromMap = positionMap.get(id);
    if (fromMap !== undefined) return fromMap;
    return null;
  };
  const xOfDate = (date: string | null | undefined) => {
    if (!date) return null;
    const ms = new Date(date).getTime();
    return Number.isFinite(ms) ? xOf(ms) : null;
  };
  const shapeMax = Math.max(1e-6, ...bin.pairs.map(p => p.shape.rmse ?? 0));
  const textureMax = Math.max(1e-6, ...bin.pairs.map(p => p.texture.delta ?? 0));

  const showShape = layers.shape && bin.pairs.length > 0;
  const showTexture = layers.texture && bin.pairs.some(p => p.texture.delta !== null || p.texture.status);
  const showAnomalies = layers.anomalies && (bin.change_points.length > 0 || bin.returns.length > 0);
  if (!showShape && !showTexture && !showAnomalies) return null;

  const height = (showShape || showTexture ? 44 : 0) + (showAnomalies ? 22 : 0);
  return <div className="findings-strip" style={{ height }}>
    {showAnomalies && (
      <div className="findings-flags">
        {bin.change_points.map((cp, index) => {
          const x = xOfDate(cp.date) ?? xOfPhoto(cp.pair?.split(" → ")[1]) ?? 0;
          const tone = String(cp.status || "").includes("persistent") || String(cp.status || "").includes("improbable") ? "bad" : "warn";
          return <button key={`cp-${index}`} className={`finding-flag cp ${tone}`} style={{ left: x - 8, top: 0 }}
            title={`Change point ${cp.date}\n${cp.status}\n${cp.pair}\np95_z: ${cp.p95_z?.toFixed(2) ?? "—"}`}>⚑</button>;
        })}
        {bin.returns.map((ret, index) => {
          const x = xOfPhoto(ret.photo_id) ?? xOfDate(ret.date) ?? 0;
          const bx = xOfPhoto(ret.baseline_photo_id);
          return <button key={`rt-${index}`} className="finding-flag ret" style={{ left: x - 8, top: 22 }}
            title={`Возврат к предыдущему состоянию\n${ret.kind}\nфото: ${ret.photo_id}\nбазовая линия: ${ret.baseline_photo_id ?? "—"}\nсила: ${ret.strength?.toFixed(3) ?? "—"}`}>↩</button>;
        })}
      </div>
    )}
    {(showShape || showTexture) && (
      <svg className="findings-bridges" width={width} height={44}>
        {showTexture && bin.pairs.map((pair, index) => {
          const x1 = xOfPhoto(pair.a), x2 = xOfPhoto(pair.b);
          if (x1 === null || x2 === null) return null;
          const mid = (x1 + x2) / 2;
          const delta = pair.texture.delta;
          const color = delta !== null ? shapeColor(delta, textureMax) : "#4a5564";
          const hollow = pair.texture.status === "unavailable" || pair.texture.status === null;
          return <g key={`tx-${index}`}>
            <path d={`M ${x1} 34 Q ${mid} 44 ${x2} 34`} fill="none" stroke={hollow ? "#556070" : color}
              strokeWidth={delta !== null ? 1 + delta / textureMax * 3 : 1} strokeDasharray={hollow ? "3 3" : undefined} opacity={hollow ? 0.45 : 0.9}>
              <title>{`Текстура кожи ${pair.a} → ${pair.b}\nстатус: ${pair.texture.status ?? "—"}\ndelta: ${delta?.toFixed(4) ?? "—"}`}</title>
            </path>
          </g>;
        })}
        {showShape && bin.pairs.map((pair, index) => {
          const x1 = xOfPhoto(pair.a), x2 = xOfPhoto(pair.b);
          if (x1 === null || x2 === null) return null;
          const mid = (x1 + x2) / 2;
          const rmse = pair.shape.rmse;
          const color = shapeColor(rmse, shapeMax);
          const width2 = 1 + Math.min(4, (pair.shape.p95_z ?? 0) * 0.5);
          const alert = pair.shape.alert;
          return <g key={`sh-${index}`}>
            <path d={`M ${x1} 20 Q ${mid} 4 ${x2} 20`} fill="none" stroke={color} strokeWidth={width2} opacity={alert ? 0.95 : 0.45}>
              <title>{`Форма ${pair.a} → ${pair.b}\nrmse: ${rmse?.toFixed(5) ?? "—"}\np95_z: ${pair.shape.p95_z?.toFixed(2) ?? "—"}\nстатус: ${pair.shape.status}\nзначимых: ${(pair.shape.significant_fraction ?? 0 * 100).toFixed(1)}%\n${pair.shape.rate_status ?? ""}`}</title>
            </path>
          </g>;
        })}
      </svg>
    )}
  </div>;
}

function PosePane({ pane, index, count, photos, width, thumbSize, xOf, selected, onSelect, openPhoto, update, remove, add, shiftThresholds, photoA, photoB, findingsBin, layers, onZoneClick, viewportLeft, viewportRight }: { pane: PaneConfig; index: number; count: number; photos: Photo[]; width: number; thumbSize: number; xOf: (time: number) => number; selected: string | null; onSelect: (id: string) => void; openPhoto: (id: string) => void; update: (patch: Partial<PaneConfig>) => void; remove: () => void; add: () => void; shiftThresholds: { tolerance: number; suspect: number; calibrated: boolean } | null; photoA: string | null; photoB: string | null; findingsBin: BinFindings | null; layers: FindingsLayers; onZoneClick: (zone: DenseZone) => void; viewportLeft: number; viewportRight: number }) {
  const panePhotos = useMemo(() => photos.filter(photo => photo.bucket === pane.pose && (!pane.anomalyOnly || photo.flags.length > 0) && (!Number.isFinite(photo.quality) || photo.quality >= pane.minQuality)), [photos, pane]);
  const layout = useMemo(() => placeSingleRow(panePhotos, xOf, thumbSize), [panePhotos, xOf, thumbSize]);
  const overscan = thumbSize * 4;
  const visibleLayout = useMemo(() => layout.filter(item => item.x >= viewportLeft - overscan && item.x <= viewportRight + overscan), [layout, viewportLeft, viewportRight, overscan]);
  const visiblePhotos = useMemo(() => visibleLayout.map(item => item.photo), [visibleLayout]);
  const positionMap = useMemo(() => new Map(layout.map(item => [item.photo.id, item.x])), [layout]);
  const positionOf = (photo: Photo) => positionMap.get(photo.id) ?? xOf(photo.t);
  const photoArea = thumbSize + 14;
  const anomalyHeight = panePhotos.some(photo => photo.flags.length) ? 34 : 0;
  const landmarkEnabled = pane.metrics.includes("landmarkShift");
  const metricDefs = pane.metrics.map(key => METRICS.find(item => item.key === key)).filter((item): item is MetricDef => Boolean(item) && item?.kind !== "landmark");
  const suggested = useMemo(() => {
    const set = new Set<string>();
    (findingsBin?.zones ?? []).forEach(zone => zone.remove.forEach(entry => set.add(entry.id)));
    return set;
  }, [findingsBin]);
  const findingsActive = layers.shape || layers.texture || layers.anomalies || layers.density;
  return <section className="pose-pane" style={{ minHeight: photoArea + anomalyHeight + (findingsActive ? 44 : 0) + metricDefs.length * 56 + (landmarkEnabled ? 72 : 0) + 42 }}>
    <PaneControls pane={pane} index={index} count={count} update={update} remove={remove} add={add}/>
    <div className="pose-pane-canvas" style={{ width }}>
      {layers.density && (findingsBin?.zones ?? []).map((zone, index) => {
        const x1 = zone.start ? xOf(new Date(zone.start).getTime()) : 0;
        const x2 = zone.end ? xOf(new Date(zone.end).getTime()) : x1 + thumbSize;
        return <button key={`zone-${index}`} className="dense-zone" style={{ left: Math.min(x1, x2) - 4, width: Math.abs(x2 - x1) + 8 }}
          onClick={() => onZoneClick(zone)} title={`${zone.count} фото за ${zone.days} дн — предложено удалить ${zone.remove.length}`}>
          <span>▦ ×{zone.count} · {zone.days}д · −{zone.remove.length}</span>
        </button>;
      })}
      <div className="photo-strip" style={{ height: photoArea }}>
        {visibleLayout.map(({ photo, x, row }) => <button className={`pure-thumb ${selected === photo.id ? "selected" : ""} ${photoA === photo.id ? "is-a" : ""} ${photoB === photo.id ? "is-b" : ""} ${suggested.has(photo.id) ? "suggest-remove" : ""}`} key={photo.id} style={{ width: thumbSize, height: thumbSize, left: x - thumbSize / 2, top: 6 + row * (thumbSize + 5) }} onClick={() => onSelect(photo.id)} onDoubleClick={() => openPhoto(photo.id)} title={photo.id}><img src={image(photo.id, "thumbnail")} alt="" loading="lazy" />{suggested.has(photo.id) && <i className="rm-badge" title="предложено исключить (лишний шум)">−</i>}</button>)}
        {panePhotos.length === 0 && <div className="empty-pose">Нет кадров для выбранного ракурса и фильтров</div>}
      </div>
      {findingsActive && <FindingsStrip bin={findingsBin} xOf={xOf} width={width} layers={layers} positionMap={positionMap} />}
      {anomalyHeight > 0 && <div className="anomaly-strip" style={{ height: anomalyHeight }}>{visiblePhotos.flatMap(photo => photo.flags.map((flag, flagIndex) => <button key={`${photo.id}-${flag}-${flagIndex}`} className={`anomaly-icon ${anomalyTone(flag)}`} style={{ left: positionOf(photo) - 11, top: flagIndex % 2 ? 13 : 2 }} title={`${photo.id}\n${flag}`} onClick={() => onSelect(photo.id)}>{anomalyIcon(flag)}</button>))}</div>}
      {landmarkEnabled && <LandmarkShiftTrack photos={visiblePhotos} positionOf={positionOf} thresholds={shiftThresholds}/>}
      {metricDefs.map(metric => <MetricTrack key={metric.key} metric={metric} photos={visiblePhotos} positionOf={positionOf} width={width}/>) }
    </div>
  </section>;
}

const PRESET_KEY = "deeputin.timeline.pose_preset";
function loadPresetPanes(): PaneConfig[] {
  try {
    const raw = localStorage.getItem(PRESET_KEY);
    if (!raw) return [{ id: 1, pose: "frontal", metrics: ["quality"], anomalyOnly: false, minQuality: 0 }];
    const poses = JSON.parse(raw) as Pose[];
    if (!Array.isArray(poses) || !poses.length) throw new Error("empty");
    return poses.filter((pose): pose is Pose => (POSES as readonly string[]).includes(pose)).map((pose, index) => ({
      id: index + 1, pose, metrics: ["quality"] as MetricKey[], anomalyOnly: false, minQuality: 0,
    }));
  } catch {
    return [{ id: 1, pose: "frontal", metrics: ["quality"], anomalyOnly: false, minQuality: 0 }];
  }
}

export default function TimelineView({ openPhoto, openCompare }: { openPhoto: (id: string) => void; openCompare: (request: CompareRequest) => void }) {
  const [data, setData] = useState<TimelineData>(EMPTY);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());
  const [selectionNote, setSelectionNote] = useState("");
  const [abMode, setAbMode] = useState(false);
  const [photoA, setPhotoA] = useState<string | null>(null);
  const [photoB, setPhotoB] = useState<string | null>(null);
  const [jumpInput, setJumpInput] = useState("");
  const jumpRef = useRef<HTMLInputElement>(null);
  const [findings, setFindings] = useState<Awaited<ReturnType<typeof timelineFindings>> | null>(null);
  const [findLayers, setFindLayers] = useState<FindingsLayers>({ anomalies: true, shape: true, texture: true, density: true });
  const [zonePanel, setZonePanel] = useState<{ pose: string; zone: DenseZone } | null>(null);
  const [panes, setPanes] = useState<PaneConfig[]>(loadPresetPanes);
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [viewportWidth, setViewportWidth] = useState(900);
  const [playhead, setPlayhead] = useState<number | null>(null);
  const [drag, setDrag] = useState<{ x: number; scroll: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(Math.max(2, loadPresetPanes().length + 1));
  const load = useCallback(() => { setData(value => ({ ...value, mode: "loading" })); void timeline().then(setData); }, []);
  useEffect(load, [load]);
  useEffect(() => { void fetchSettings().then(setSettings).catch(() => setSettings(null)); }, []);
  useEffect(() => { const element = scrollRef.current; if (!element) return; const observer = new ResizeObserver(() => setViewportWidth(Math.max(1, element.clientWidth))); observer.observe(element); setViewportWidth(element.clientWidth); return () => observer.disconnect(); }, []);
  useEffect(() => { localStorage.setItem(PRESET_KEY, JSON.stringify(panes.map(pane => pane.pose))); }, [panes]);
  const sortedPhotos = useMemo(() => [...data.photos].sort((a, b) => a.t - b.t || a.id.localeCompare(b.id)), [data.photos]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      if (!data.photos.length) return;
      const index = sortedPhotos.findIndex(photo => photo.id === selected);
      const next = (delta: number) => sortedPhotos[Math.max(0, Math.min(sortedPhotos.length - 1, index + delta))];
      if (event.key === "ArrowRight") { event.preventDefault(); const photo = next(1); setSelected(photo.id); setPlayhead(photo.t); }
      if (event.key === "ArrowLeft") { event.preventDefault(); const photo = next(-1); setSelected(photo.id); setPlayhead(photo.t); }
      if (event.key === "a" || event.key === "A") { event.preventDefault(); if (selected) { setAbMode(true); setPhotoA(selected); } }
      if (event.key === "b" || event.key === "B") { event.preventDefault(); if (selected) { setAbMode(true); setPhotoB(selected); } }
      if (event.key === "Enter" && selected) {
        event.preventDefault();
        const photo = data.photos.find(item => item.id === selected);
        if (photo) openCompare({ kind: "landmarks", pose: photo.bucket, photoA: photoA ?? photo.id, photoB: photoB ?? photo.id });
      }
      if (event.key === "Escape") { setAbMode(false); setPhotoA(null); setPhotoB(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [data.photos, sortedPhotos, selected, photoA, photoB, openCompare]);

  useEffect(() => {
    if (!findLayers.anomalies && !findLayers.shape && !findLayers.texture && !findLayers.density) {
      setFindings(null);
      return;
    }
    let dead = false;
    timelineFindings()
      .then(data => { if (!dead) setFindings(data); })
      .catch(() => { if (!dead) setFindings(null); });
    return () => { dead = true; };
  }, [findLayers]);

  const excludeZone = (zone: DenseZone) => {
    setExcludedIds(current => {
      const next = new Set(current);
      zone.remove.forEach(entry => next.add(entry.id));
      return next;
    });
    setSelectionNote(`Плотный участок ${zone.start}—${zone.end}: исключено ${zone.remove.length} шумных фото`);
    setZonePanel(null);
  };

  const jumpToDate = () => {
    const parsed = new Date(jumpInput);
    if (Number.isNaN(parsed.getTime())) return;
    const target = parsed.getTime();
    const photo = [...data.photos].sort((a, b) => Math.abs(a.t - target) - Math.abs(b.t - target))[0];
    if (photo) { setSelected(photo.id); setPlayhead(photo.t); }
  };
  const bounds = useMemo(() => { const times = data.photos.map(photo => photo.t); const min = times.length ? Math.min(...times) : Date.now(); const max = times.length ? Math.max(...times) : min + 86_400_000; return { min, max: max === min ? min + 86_400_000 : max }; }, [data.photos]);
  const thumbSize = Math.round(MIN_THUMB + Math.pow((zoom - 1) / (MAX_ZOOM - 1), .46) * (MAX_THUMB - MIN_THUMB));
  const baseTimeWidth = Math.max(viewportWidth, viewportWidth * zoom);
  const filteredPhotos = useMemo(() => excludedIds.size ? data.photos.filter(photo => !excludedIds.has(photo.id)) : data.photos, [data.photos, excludedIds]);
  const densestPane = Math.max(1, ...panes.map(pane => filteredPhotos.filter(photo => photo.bucket === pane.pose).length));
  const contentWidth = Math.max(baseTimeWidth + thumbSize, densestPane * (thumbSize + 4) + thumbSize);
  const xOf = useCallback((time: number) => thumbSize / 2 + ((time - bounds.min) / (bounds.max - bounds.min)) * Math.max(1, baseTimeWidth - thumbSize), [bounds, baseTimeWidth, thumbSize]);
  const ticks = Array.from({ length: 11 }, (_, index) => bounds.min + (bounds.max - bounds.min) * index / 10);
  const viewportLeft = Math.max(0, scrollLeft - CONTROL_WIDTH);
  const viewportRight = viewportLeft + viewportWidth;
  const updatePane = (id: number, patch: Partial<PaneConfig>) => setPanes(items => items.map(item => item.id === id ? { ...item, ...patch } : item));
  const addPane = () => setPanes(items => { const used = new Set(items.map(item => item.pose)); const pose = POSES.find(item => !used.has(item)) || "frontal"; return [...items, { id: nextId.current++, pose, metrics: ["quality"], anomalyOnly: false, minQuality: 0 }]; });
  const applyPreset = (poses: readonly Pose[]) => { nextId.current = poses.length + 1; setPanes(poses.map((pose, index) => ({ id: index + 1, pose, metrics: ["quality"], anomalyOnly: false, minQuality: 0 }))); };
  const onWheel = (event: ReactWheelEvent) => { const element = scrollRef.current; if (!element) return; event.preventDefault(); if (event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) { element.scrollLeft += event.deltaX + event.deltaY; return; } const rect = element.getBoundingClientRect(); const localX = event.clientX - rect.left; const pointer = element.scrollLeft + localX - CONTROL_WIDTH; const ratio = clamp(pointer / contentWidth, 0, 1); const next = clamp(zoom * Math.exp(-event.deltaY * .0022), 1, MAX_ZOOM); setZoom(next); requestAnimationFrame(() => { element.scrollLeft = CONTROL_WIDTH + ratio * Math.max(viewportWidth, viewportWidth * next) - localX; }); };
  return <main className="multi-timeline-page">
    <header className="multi-top"><div className="brand"><i>D</i><div><b>DEEPUTIN</b><small>MULTI-POSE FORENSIC TIMELINE</small></div></div><span className={`live ${data.mode}`}>● APP6 · {data.mode.toUpperCase()}</span><button className={filterOpen ? "active" : ""} onClick={() => setFilterOpen(value => !value)}> cop Фильтры</button><div className="pose-presets" aria-label="Пресеты ракурсов"><button className={panes.length === 1 ? "active" : ""} onClick={() => applyPreset(["frontal"])}>1</button><button className={panes.length === 3 ? "active" : ""} onClick={() => applyPreset(["left_mid", "frontal", "right_mid"])}>3</button><button className={panes.length === 9 ? "active" : ""} onClick={() => applyPreset(POSES)}>9</button></div><button onClick={addPane} disabled={panes.length >= POSES.length}>＋ Добавить ракурс</button>
      <div className={`ab-mode ${abMode ? "active" : ""}`}>
        <button className={abMode ? "active" : ""} onClick={() => { setAbMode(v => !v); if (abMode) { setPhotoA(null); setPhotoB(null); } }} title="A/B выбор (клавиши A, B)">
          A/B {abMode ? "on" : "off"}
        </button>
        {abMode && <span className="ab-chips"><i className={photoA ? "set" : ""}>A:{photoA ? photoA.slice(-12) : "—"}</i><i className={photoB ? "set" : ""}>B:{photoB ? photoB.slice(-12) : "—"}</i></span>}
        {abMode && photoA && photoB && <>
          <button onClick={() => openCompare({ kind: "landmarks", pose: data.photos.find(p => p.id === photoA)?.bucket ?? null, photoA, photoB })} title="Enter">⌖ Точки</button>
          <button onClick={() => openCompare({ kind: "morphing", pose: data.photos.find(p => p.id === photoA)?.bucket ?? null, photoA, photoB })}>◈ Morphing</button>
        </>}
        {abMode && <button className="ghost" onClick={() => { setPhotoA(null); setPhotoB(null); }}>✕</button>}
      </div>
      <label className="jump-date"><input ref={jumpRef} value={jumpInput} onChange={event => setJumpInput(event.target.value)} onKeyDown={event => { if (event.key === "Enter") jumpToDate(); }} placeholder="ГГГГ-ММ-ДД" /><button onClick={jumpToDate}>⌖</button></label>
      <div className="findings-toggles" title={`Слой находок · run ${findings?.run_id ?? "нет"}`}>
        {([["anomalies", "⚑ Аномалии"], ["shape", "⌁ Форма"], ["texture", "◈ Текстура"], ["density", "▦ Плотность"]] as const).map(([key, label]) => (
          <label key={key} className={findings?.has_stage2 === false && key !== "density" ? "disabled" : ""}>
            <input type="checkbox" checked={findLayers[key]} onChange={event => setFindLayers(layers => ({ ...layers, [key]: event.target.checked }))} />
            {label}
          </label>
        ))}
        {findings?.has_stage2 === false && <em className="no-stage2">нет Stage 2</em>}
      </div><button onClick={() => { setZoom(1); if (scrollRef.current) scrollRef.current.scrollLeft = 0; }}>↔ Fit</button><button onClick={load}>↻</button></header>
    {data.mode !== "research" ? <div className={`state ${data.mode}`}><span>{data.mode === "loading" ? "◌" : "!"}</span><b>{data.mode === "loading" ? "Чтение timeline" : "Timeline недоступен"}</b><p>{data.message}</p>{data.mode !== "loading" && <button onClick={load}>Повторить</button>}</div> : <div className="multi-body">
      <div className="shared-ruler-left"><small>SHARED TIME</small><b>{new Date(bounds.min).getFullYear()}—{new Date(bounds.max).getFullYear()}</b></div>
      <div ref={scrollRef} className={`multi-scroll ${drag ? "dragging" : ""}`} onScroll={event => setScrollLeft(event.currentTarget.scrollLeft)} onWheel={onWheel} onPointerDown={event => { if (event.button === 1 || event.shiftKey) { event.preventDefault(); setDrag({ x: event.clientX, scroll: scrollRef.current?.scrollLeft || 0 }); event.currentTarget.setPointerCapture(event.pointerId); } }} onPointerMove={event => { if (drag && scrollRef.current) scrollRef.current.scrollLeft = drag.scroll - (event.clientX - drag.x); }} onPointerUp={() => setDrag(null)}>
        <div className="multi-canvas" style={{ width: contentWidth + CONTROL_WIDTH }}>
          <div className="shared-ruler" style={{ marginLeft: CONTROL_WIDTH, width: contentWidth }} onClick={event => { const rect = event.currentTarget.getBoundingClientRect(); setPlayhead(bounds.min + clamp((event.clientX - rect.left) / contentWidth, 0, 1) * (bounds.max - bounds.min)); }}>{ticks.map(time => <div key={time} className="shared-tick" style={{ left: xOf(time) }}><span>{new Date(time).toLocaleDateString("ru-RU", { year: "numeric", month: zoom > 8 ? "short" : undefined })}</span><i /></div>)}</div>
          <div className="pane-stack">{panes.map((pane, index) => <PosePane key={pane.id} pane={pane} index={index} count={panes.length} photos={filteredPhotos} width={contentWidth} thumbSize={thumbSize} xOf={xOf} selected={selected} onSelect={id => {
        setSelected(id);
        const photo = data.photos.find(item => item.id === id);
        if (photo) setPlayhead(photo.t);
        if (abMode) {
          if (!photoA || (photoA && photoB)) { setPhotoA(id); setPhotoB(null); }
          else setPhotoB(id);
        }
      }} openPhoto={openPhoto} update={patch => updatePane(pane.id, patch)} remove={() => setPanes(items => items.filter(item => item.id !== pane.id))} add={addPane} shiftThresholds={settings?.landmark_shift ?? null} photoA={photoA} photoB={photoB}
          findingsBin={findings?.bins?.[pane.pose] ?? null} layers={findLayers}
          onZoneClick={zone => setZonePanel({ pose: pane.pose, zone })}
          viewportLeft={viewportLeft} viewportRight={viewportRight}/>)}</div>
          {playhead !== null && <div className="multi-playhead" style={{ left: CONTROL_WIDTH + xOf(playhead) }}/>} 
        </div>
      </div>
    </div>}
    {filterOpen && <FilterPanel open={filterOpen} onClose={() => setFilterOpen(false)} onApplied={(result: FilterEvalResult) => { setExcludedIds(new Set(result.excluded_ids || [])); setSelectionNote(`${result.included_count} in · ${result.excluded_count} out`); }} />}
    {zonePanel && (
      <aside className="findings-zone-panel">
        <header>
          <div>
            <small>DENSE ZONE · {zonePanel.pose}</small>
            <b>{zonePanel.zone.count} фото за {zonePanel.zone.days} дней</b>
            <span>{zonePanel.zone.start} — {zonePanel.zone.end}</span>
          </div>
          <button onClick={() => setZonePanel(null)}>×</button>
        </header>
        <div className="zone-panel-body">
          <p>В этом участке избыточное количество копий за короткий срок. Предлагается исключить фото, дающие лишний шум (плохое качество, крайние позы, дубликаты):</p>
          <div className="zone-remove-list">
            {zonePanel.zone.remove.map(entry => (
              <div key={entry.id} className="zone-remove-row">
                <code>{entry.id}</code>
                <span>{entry.reasons.join(" · ")}</span>
                <b>{entry.noise_score.toFixed(2)}</b>
              </div>
            ))}
          </div>
          <div className="zone-keep">Останется: {zonePanel.zone.keep.length} фото</div>
        </div>
        <footer>
          <button className="ghost" onClick={() => setZonePanel(null)}>Отмена</button>
          <button className="primary" onClick={() => excludeZone(zonePanel.zone)}>Исключить {zonePanel.zone.remove.length}</button>
        </footer>
      </aside>
    )}
    <footer><span>● APP6 DATA CONTRACT</span><em>{data.message}</em><strong>{filteredPhotos.length}/{data.photos.length} фото{selectionNote ? ` · ${selectionNote}` : ""} · scroll {Math.round(scrollLeft)}px</strong><small>Double click → Photo Lab · A/B mode: клик = A, ещё клик = B · Enter = сравнение точек · ←→ = навигация</small></footer>
  </main>;
}
