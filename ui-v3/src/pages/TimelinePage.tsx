import { useMemo, useState } from "react";
import type { Photo, PoseBucket } from "../lib/types";
import { POSE_BUCKETS, POSE_LABELS } from "../lib/types";
import { fmt, fmtDate, isNum } from "../lib/format";
import PhotoArtifactImage from "../components/PhotoArtifactImage";
import { Banner, Chip, Empty, Select } from "../components/ui";
type MetricKey = "boneScore" | "quality" | "yaw" | "orbit" | "chin" | "jaw" | "cheek" | "symmetry";
const METRICS: Array<{ key: MetricKey; label: string; color: string }> = [
  { key: "boneScore", label: "bone / geometry", color: "#5b9fd4" },
  { key: "quality", label: "quality", color: "#5fad7e" },
  { key: "yaw", label: "yaw°", color: "#9aa3b5" },
  { key: "orbit", label: "orbit", color: "#6daa45" },
  { key: "chin", label: "chin", color: "#e8af34" },
  { key: "jaw", label: "jaw", color: "#fdab43" },
  { key: "cheek", label: "cheek", color: "#a86fdf" },
  { key: "symmetry", label: "symmetry", color: "#5591c7" },
];
function trackPath(photos: Photo[], key: MetricKey, w: number, h: number) {
  const vals = photos.map(p => p[key]).filter(isNum) as number[];
  if (!photos.length) return { d: "", pts: [] as Array<{x:number;y:number;i:number;v:number}>, minV: NaN, maxV: NaN };
  let minV = Math.min(...vals), maxV = Math.max(...vals);
  if (!Number.isFinite(minV)) { minV = 0; maxV = 1; }
  if (minV === maxV) { minV -= 1; maxV += 1; }
  const pad = (maxV - minV) * 0.12; minV -= pad; maxV += pad;
  const step = photos.length <= 1 ? 0 : (w - 24) / (photos.length - 1);
  const pts: Array<{x:number;y:number;i:number;v:number}> = [];
  const segs: string[] = []; let cur: string[] = []; let prevBucket: string | null = null;
  photos.forEach((p, i) => {
    const v = p[key];
    if (!isNum(v)) { if (cur.length) { segs.push(cur.join(" ")); cur = []; } prevBucket = p.bucket; return; }
    const x = 12 + i * step;
    const y = h - 10 - ((v - minV) / (maxV - minV)) * (h - 20);
    pts.push({ x, y, i, v });
    if (prevBucket != null && p.bucket !== prevBucket && cur.length) { segs.push(cur.join(" ")); cur = []; }
    cur.push(`${cur.length ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`);
    prevBucket = p.bucket;
  });
  if (cur.length) segs.push(cur.join(" "));
  return { d: segs.join(" "), pts, minV, maxV };
}
export default function TimelinePage({ photos, selectedId, onSelect, chronoAnomalies }: {
  photos: Photo[]; selectedId: string | null; onSelect: (id: string) => void;
  chronoAnomalies: Record<string, Record<string, unknown>>;
}) {
  const [bucket, setBucket] = useState<"all" | PoseBucket>("all");
  const view = useMemo(() => bucket === "all" ? photos : photos.filter(p => p.bucket === bucket), [photos, bucket]);
  const selected = view.find(p => p.id === selectedId) || view[0] || null;
  const small = photos.length > 0 && photos.length < 12;
  const width = Math.max(640, view.length * 72);
  if (!photos.length) return <div className="page"><Empty title="Хронология пуста">Нет фото в timeline.</Empty></div>;
  return (
    <div className="timeline-shell">
      <div className="timeline-toolbar">
        <strong>Хронология</strong>
        <Chip kind="info">{view.length} кадров</Chip>
        {small && <Chip kind="warn">TEST SUBSET</Chip>}
        <Select value={bucket} onChange={e => setBucket(e.target.value as "all" | PoseBucket)} style={{ maxWidth: 220 }}>
          <option value="all">все ракурсы (линии рвутся на bin)</option>
          {POSE_BUCKETS.map(b => <option key={b} value={b}>{POSE_LABELS[b]}</option>)}
        </Select>
        <div className="spacer" /><span className="muted">клик → инспектор</span>
      </div>
      {small && <div style={{ padding: "8px 16px" }}><Banner kind="warn" title="Малая выборка">Графики диагностические. Нужен полный датасет.</Banner></div>}
      <div className="timeline-body">
        <div className="timeline-list">
          {view.map(p => (
            <div key={p.id} className={`list-item ${selected?.id === p.id ? "active" : ""}`} onClick={() => onSelect(p.id)}>
              <div className="t"><PhotoArtifactImage photoId={p.id} kind="thumbnail" cover decorative /></div>
              <div>
                <div className="mono" style={{ fontSize: 11 }}>{p.id}</div>
                <div className="faint">{fmtDate(p.t)} · {p.bucket}</div>
                <div className="faint">q={fmt(p.quality,2)} · bone={fmt(p.boneScore,3)}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="timeline-chart">
          {Object.keys(chronoAnomalies || {}).length > 0 && (
            <Banner kind="info" title="Stage 2 chronology">{Object.keys(chronoAnomalies).join(", ")}</Banner>
          )}
          {METRICS.map(m => {
            const tr = trackPath(view, m.key, width, 72);
            return (
              <div key={m.key} className="track">
                <div className="track-hd"><span style={{ color: m.color }}>{m.label}</span><span className="mono faint">{fmt(tr.minV,3)} … {fmt(tr.maxV,3)}</span></div>
                <svg className="track-svg" viewBox={`0 0 ${width} 72`} preserveAspectRatio="none" style={{ width, minWidth: "100%" }}>
                  <path d={tr.d} fill="none" stroke={m.color} strokeWidth="1.6" strokeLinejoin="round" />
                  {tr.pts.map(pt => (
                    <circle key={pt.i} cx={pt.x} cy={pt.y} r={selected && view[pt.i]?.id === selected.id ? 3.4 : 2.2}
                      fill={m.color} stroke="#0b0c0f" strokeWidth="0.6" style={{ cursor: "pointer" }}
                      onClick={() => onSelect(view[pt.i].id)} />
                  ))}
                </svg>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
