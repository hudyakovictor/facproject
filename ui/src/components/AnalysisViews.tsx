import { useEffect, useMemo, useState } from "react";
import PhotoPicker from "./PhotoPicker";
import { Spinner } from "./Loading";
import { ERA_META, FUZZY_COLORS, HYPOTHESIS_COLORS, POSE_BUCKETS, POSE_LABELS, type Era, type Photo } from "../data";
import { fetchPhotoDetail, fetchPhotoFullMesh, type FullMesh, type PhotoDetail } from "../api";
import MeshViewer from "./LazyMeshViewer";
import SkinZonesPanel from "./SkinZonesPanel";
import ChronologyAnomalies from "./ChronologyAnomalies";
import { t } from "../i18n";

type Kind = "MATRIX" | "COMPARE" | "INSPECTOR" | "DRIFT" | "METRICS" | "STATS";
interface Props { kind: Kind; photos: Photo[]; selected: Photo | null; onSelect: (id: string) => void; onInspect: (photo: Photo) => void; onCompare: () => void; chronoAnomalies?: Record<string, Record<string, unknown>>; }

const mean = (rows: Photo[], pick: (photo: Photo) => number) => rows.length ? rows.reduce((sum, row) => sum + pick(row), 0) / rows.length : 0;
/** Настоящая медиана. Карточки METRICS раньше были подписаны «медиана», но
 * считали среднее — для распределений с выбросами это разные числа, и в
 * forensic-отчёте такое расхождение подписи и вычисления недопустимо. */
const median = (rows: Photo[], pick: (photo: Photo) => number) => {
  if (!rows.length) return 0;
  const values = rows.map(pick).sort((a, b) => a - b);
  const mid = Math.floor(values.length / 2);
  return values.length % 2 === 0 ? (values[mid - 1] + values[mid]) / 2 : values[mid];
};
const anomaly = (p: Photo) => !["CONSISTENT", "STRONGLY_MATCHING"].includes(p.fuzzy);

function Shell({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return <section className="h-full overflow-auto bg-bg p-5 scanlines"><header className="mb-5"><h1 className="font-display text-xl tracking-forensic">{title}</h1><p className="font-mono text-[10px] text-text-muted mt-1">{sub}</p></header>{children}</section>;
}

function MetricCard({ label, value, note, color = "#5591c7" }: { label: string; value: string; note: string; color?: string }) {
  return <article className="bg-surface border border-border p-3 min-h-24"><div className="font-mono text-[9px] tracking-forensic text-text-muted">{label}</div><div className="font-display text-2xl mt-2" style={{ color }}>{value}</div><div className="font-mono text-[9px] text-text-faint mt-2">{note}</div></article>;
}

function Spark({ values, color = "#5591c7", height = 120 }: { values: number[]; color?: string; height?: number }) {
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const points = values.map((v, i) => `${(i / Math.max(1, values.length - 1)) * 100},${height - 8 - ((v - min) / span) * (height - 16)}`).join(" ");
  return <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }} aria-label={t.avChartLabel}><path d={`M0 ${height - 8} H100`} stroke="rgba(255,255,255,.08)" /><polyline points={points} fill="none" stroke={color} strokeWidth="1.2" vectorEffect="non-scaling-stroke" /></svg>;
}

export default function AnalysisViews({ kind, photos, selected, onSelect, onInspect, onCompare, chronoAnomalies = {} }: Props) {
  // Подвыборка для спарклайнов: 120 точек достаточно для формы тренда.
  // Факт подвыборки подписывается на графике — иначе читатель решит, что
  // видит весь набор.
  const sampled = useMemo(() => photos.filter((_, i) => i % Math.max(1, Math.floor(photos.length / 120)) === 0).slice(0, 120), [photos]);
  const isSampled = photos.length > sampled.length;
  // Строки матрицы — сегменты, фактически присутствующие в выборке,
  // а не жёсткий список ERA_*, которого нет в данных backend.
  const eras = useMemo(
    () => Array.from(new Set(photos.map(p => p.era)))
      .sort((a, b) => (photos.find(p => p.era === a)?.t ?? 0) - (photos.find(p => p.era === b)?.t ?? 0)) as Era[],
    [photos]);

  if (kind === "MATRIX") return <Shell title={t.avMatrixTitle} sub={t.avMatrixSub}><div className="overflow-auto border border-border"><table className="w-full min-w-[980px] border-collapse font-mono text-[10px]"><thead><tr><th className="sticky left-0 bg-surface p-2 text-left">{t.avColEra}</th>{POSE_BUCKETS.map(p => <th key={p} className="bg-surface p-2 text-text-muted">{POSE_LABELS[p]}</th>)}</tr></thead><tbody>{eras.map(era => <tr key={era}><th className="sticky left-0 bg-surface p-2 text-left" style={{ color: ERA_META[era].color }}>{ERA_META[era].label}</th>{POSE_BUCKETS.map(pose => { const rows = photos.filter(p => p.era === era && p.bucket === pose); const score = mean(rows, p => p.boneScore); return <td key={pose} className="border border-border p-2 text-center" title={t.avPhotoCount(rows.length)}><div className="text-base">{rows.length ? score.toFixed(3) : "—"}</div><div className="text-text-faint">n={rows.length}</div></td>; })}</tr>)}</tbody></table></div></Shell>;

  if (kind === "COMPARE") return <Shell title={t.avCompareTitle} sub={t.avCompareSub}><div className="grid grid-cols-3 gap-3"><MetricCard label={t.avSelectedA} value="SHIFT+DRAG" note={t.avRangeFirst} /><MetricCard label={t.avSelectedB} value="SHIFT+DRAG" note={t.avRangeSecond} /><button onClick={onCompare} className="bg-info/20 border border-info/50 p-4 text-left hover:bg-info/30"><div className="font-mono text-[9px]">{t.avOpenPanel}</div><div className="font-display text-xl mt-2">COMPARE</div></button></div><div className="mt-5 bg-surface border border-border p-4"><Spark values={sampled.map(p => p.boneScore)} /><div className="font-mono text-[9px] text-text-muted">{t.avBoneNote}</div>{isSampled && <div className="font-mono text-[8px] text-text-faint mt-0.5">{t.sampledNotice(sampled.length, photos.length)}</div>}</div></Shell>;

  if (kind === "INSPECTOR") return <InspectorView photos={photos} selected={selected} onSelect={onSelect} onInspect={onInspect} />;

  if (kind === "DRIFT") return <Shell title={t.avDriftTitle} sub={t.avDriftSub}><div className="grid grid-cols-3 gap-3 mb-4"><MetricCard label="ORBIT DRIFT" value={mean(photos, p => Math.abs(p.zOrbitDepth)).toFixed(2)} note="mean |z|" /><MetricCard label="CHIN DRIFT" value={mean(photos, p => Math.abs(p.zChinProj)).toFixed(2)} note="mean |z|" color="#e8af34" /><MetricCard label="JAW DRIFT" value={mean(photos, p => Math.abs(p.zJawWidth)).toFixed(2)} note="mean |z|" color="#dd6974" /></div><div className="bg-surface border border-border p-4"><Spark values={sampled.map(p => p.zChinProj)} color="#dd6974" height={280} /></div></Shell>;

  if (kind === "METRICS") return <Shell title={t.avMetricsTitle} sub={t.avMetricsSub}><div className="grid grid-cols-4 gap-3">{([["BONE",(r:Photo[])=>median(r,p=>p.boneScore)],["ORBITS",(r:Photo[])=>median(r,p=>p.orbit)],["CHIN",(r:Photo[])=>median(r,p=>p.chin)],["JAW",(r:Photo[])=>median(r,p=>p.jaw)],["CHEEK",(r:Photo[])=>median(r,p=>p.cheek)],["SYMMETRY",(r:Photo[])=>median(r,p=>p.symmetry)],["LBP",(r:Photo[])=>median(r,p=>p.lbpEntropy)],["FRANGI",(r:Photo[])=>median(r,p=>p.frangi)],["WRINKLE",(r:Photo[])=>median(r,p=>p.wrinkle)],["SUBSURFACE",(r:Photo[])=>median(r,p=>p.subsurface)],["P(H0)",(r:Photo[])=>median(r,p=>p.p0)],["QUALITY",(r:Photo[])=>median(r,p=>p.quality)]] as [string,(r:Photo[])=>number][]).map(([label,fn]) => <MetricCard key={label} label={label} value={fn(photos).toFixed(3)} note={t.statMedian} />)}</div></Shell>;

  const anomalies = photos.filter(anomaly).length;
  const chronoPanel = <ChronologyAnomalies summaries={chronoAnomalies} />;
  return <Shell title={t.avStatsTitle} sub={t.avStatsSub}><div className="grid grid-cols-4 gap-3"><MetricCard label={t.avCardPhotos} value={String(photos.length)} note={t.avCurrentSelection} /><MetricCard label={t.avCardAnomalies} value={String(anomalies)} note={`${((anomalies / Math.max(1, photos.length)) * 100).toFixed(1)}%`} color="#dd6974" /><MetricCard label={t.avCardQuality} value={mean(photos,p=>p.quality).toFixed(3)} note={t.avQualityGate} color="#6daa45" /><MetricCard label={t.avCardPoseBins} value="9" note={t.avNormativeScheme} /></div><div className="mt-4">{chronoPanel}</div><div className="grid grid-cols-3 gap-4 mt-4"><div className="bg-surface border border-border p-4"><h2 className="font-mono text-[10px] mb-3">{t.avHypotheses}</h2>{(["H0","H1","H2"] as const).map(h => { const n=photos.filter(p=>p.dominant===h).length; return <div key={h} className="flex justify-between py-2 border-b border-border"><span style={{color:HYPOTHESIS_COLORS[h]}}>{h}</span><span>{n}</span></div>;})}</div><div className="col-span-2 bg-surface border border-border p-4"><h2 className="font-mono text-[10px] mb-3">{t.avEvidenceStates}</h2>{Object.entries(FUZZY_COLORS).map(([label,color])=>{const n=photos.filter(p=>p.fuzzy===label).length;return <div key={label} className="grid grid-cols-[180px_1fr_50px] gap-2 items-center py-1"><span className="font-mono text-[9px]">{label}</span><div className="h-2 bg-surface-3"><div className="h-full" style={{width:`${n/Math.max(1,photos.length)*100}%`,background:color}}/></div><span className="font-mono text-[9px] text-right">{n}</span></div>})}</div></div></Shell>;
}

/** 3D / BFM Inspector — НАСТОЯЩАЯ геометрия, а не декоративный SVG.
 *
 * Раньше этот режим рисовал набор концентрических эллипсов и выводил список
 * галочек «✓ Mesh 35 709 vertices / ✓ Landmarks 106/134 / ✓ Heatmap z-score /
 * ✓ Morph A→B», хотя ни один из этих пунктов не был реализован: `MeshViewer`
 * здесь даже не импортировался. Это ровно тот случай, который запрещает
 * `app6/AGENTS.md` — интерфейс заявлял возможности, которых нет.
 *
 * Теперь используется тот же `MeshViewer` (three.js), что и в полноэкранном
 * оверлее, с подлинной BFM-топологией из `/api/v1/photos/{id}/mesh`. Если
 * backend меш не отдал — показывается явная причина и режим деградирует до
 * 106/134 landmarks; если нет и их — честное сообщение вместо картинки.
 */
function InspectorView({ photos, selected, onSelect, onInspect }: {
  photos: Photo[]; selected: Photo | null; onSelect: (id: string) => void; onInspect: (photo: Photo) => void;
}) {
  const photo = selected ?? photos[0] ?? null;
  const [detail, setDetail] = useState<PhotoDetail | null>(null);
  const [fullMesh, setFullMesh] = useState<FullMesh | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const [wireframe, setWireframe] = useState(true);
  const [showPoints, setShowPoints] = useState(true);

  useEffect(() => {
    if (!photo) { setStatus("unavailable"); return undefined; }
    let cancelled = false;
    setStatus("loading");
    setDetail(null);
    setFullMesh(null);
    fetchPhotoDetail(photo.id)
      .then(d => {
        if (cancelled) return;
        setDetail(d);
        setStatus("ready");
        if (d.full_mesh_available) {
          fetchPhotoFullMesh(photo.id)
            .then(m => { if (!cancelled) setFullMesh(m); })
            .catch(() => undefined);  // деградируем до landmarks, состояние видно в шапке
        }
      })
      .catch(() => { if (!cancelled) setStatus("unavailable"); });
    return () => { cancelled = true; };
  }, [photo?.id]);

  const sourceLabel = fullMesh
    ? `${t.inspectorRealMesh} · ${fullMesh.vertices.length.toLocaleString("ru-RU")} vertices / ${fullMesh.triangles.length.toLocaleString("ru-RU")} triangles`
    : detail
      ? `${t.inspectorLandmarks} · ${detail.landmarks_134.length} pts`
      : status === "loading" ? t.inspectorLoading : t.inspectorNoGeometry;

  return (
    <Shell title={t.avInspectorTitle} sub={t.avInspectorSub}>
      <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-4">
        <div className="flex flex-col gap-2">
          <div className="min-h-[520px] h-[520px] bg-surface border border-border relative">
            {status === "ready" && (fullMesh || detail) ? (
              <MeshViewer
                fullMesh={fullMesh ? { vertices: fullMesh.vertices, triangles: fullMesh.triangles } : undefined}
                points134={fullMesh ? undefined : detail?.landmarks_134}
                wireframe={wireframe}
                showPoints={showPoints}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center p-6 text-center">
                {status === "loading"
                  ? <Spinner label={t.inspectorLoading} />
                  : <span className="font-mono text-[11px] text-text-muted">{t.inspectorNoGeometry}</span>}
              </div>
            )}
            <div className="absolute left-3 top-3 font-mono text-[10px] bg-bg/70 px-2 py-1 pointer-events-none">
              {photo?.id ?? "—"} · {photo?.bucket ?? "—"}
            </div>
          </div>

          <div className="flex items-center gap-3 bg-surface border border-border p-2">
            <label className="flex items-center gap-1.5 font-mono text-[10px] text-text-muted cursor-pointer">
              <input type="checkbox" checked={wireframe} onChange={e => setWireframe(e.target.checked)}
                aria-label={t.inspectorWireframe} />
              {t.inspectorWireframe}
            </label>
            <label className="flex items-center gap-1.5 font-mono text-[10px] text-text-muted cursor-pointer">
              <input type="checkbox" checked={showPoints} onChange={e => setShowPoints(e.target.checked)}
                aria-label={t.inspectorPoints} />
              {t.inspectorPoints}
            </label>
            <span className="ml-auto font-mono text-[9px] text-text-faint">{sourceLabel}</span>
          </div>

          {photo && (
            <div className="flex gap-2">
              <div className="flex-1">
                <PhotoPicker photos={photos} value={photo.id} onChange={onSelect}
                  label={t.inspectorSelectPhoto} />
              </div>
              <button onClick={() => onInspect(photo)}
                className="px-3 bg-info/20 border border-info/50 font-mono text-[10px] hover:bg-info/30">
                OVERLAY
              </button>
            </div>
          )}
        </div>

        <aside className="overflow-auto max-h-[640px]" data-scroll>
          <div className="font-display text-xs tracking-forensic mb-2">{t.skinZonesTitle}</div>
          {photo ? <SkinZonesPanel photoId={photo.id} /> : null}
        </aside>
      </div>
    </Shell>
  );
}
