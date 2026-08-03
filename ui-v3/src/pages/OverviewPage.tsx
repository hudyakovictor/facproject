import type { Photo, TimelineResult } from "../lib/types";
import { POSE_BUCKETS, POSE_LABELS } from "../lib/types";
import { fmt, fmtDate } from "../lib/format";
import { Banner, Button, Panel, Stat } from "../components/ui";
import PhotoArtifactImage from "../components/PhotoArtifactImage";

export default function OverviewPage({ timeline, onOpenGallery, onOpenControl, onOpenPhoto }: {
  timeline: TimelineResult; onOpenGallery: () => void; onOpenControl: () => void; onOpenPhoto: (id: string) => void;
}) {
  const photos = timeline.photos;
  const bins = Object.fromEntries(POSE_BUCKETS.map(b => [b, photos.filter(p => p.bucket === b).length]));
  const flagged = photos.filter(p => (p.flags?.length || 0) > 0 || p.exifAnomaly);
  const recent = [...photos].slice(-8).reverse();
  const q = photos.map(p => p.quality).filter(Number.isFinite);
  const meanQ = q.length ? q.reduce((a, b) => a + b, 0) / q.length : NaN;
  return (
    <div className="page">
      <div className="page-hd">
        <div><h1>Обзор рабочей станции</h1><p>Тёмная forensic-станция для хронологического 3D-анализа. Автоматический score не является вердиктом о личности.</p></div>
        <div className="row"><Button onClick={onOpenGallery}>галерея</Button><Button variant="primary" onClick={onOpenControl}>управление анализом</Button></div>
      </div>
      {timeline.mode === "error" && <Banner kind="bad" title="Timeline не загружен">{timeline.message}</Banner>}
      {timeline.mode === "empty" && <Banner kind="warn" title="Нет извлечённых фото">Запустите Stage 1 extract в «Управление анализом».</Banner>}
      {photos.length > 0 && photos.length < 12 && <Banner kind="warn" title={`TEST SUBSET · ${photos.length} фото`}>Малая выборка. Для полноценной хронологии нужен dense dataset.</Banner>}
      {timeline.rejected.length > 0 && <Banner kind="bad" title={`Отклонено строк: ${timeline.rejected.length}`}>{timeline.rejected.slice(0, 3).map(r => `${r.id}: ${r.reason}`).join(" · ")}</Banner>}
      <div className="grid-4">
        <Stat k="фото" v={photos.length} h={timeline.message} />
        <Stat k="с флагами" v={flagged.length} h="anomaly / provenance" />
        <Stat k="pose bins" v={`${Object.values(bins).filter(Boolean).length}/9`} h="покрытие ракурсов" />
        <Stat k="качество (mean)" v={Number.isFinite(meanQ) ? fmt(meanQ, 3) : "—"} h="measurement quality" />
      </div>
      <div className="grid-2">
        <Panel title="Покрытие 9 ракурсов">
          <div className="table-wrap"><table className="data"><thead><tr><th>ракурс</th><th>n</th></tr></thead><tbody>
            {POSE_BUCKETS.map(b => (<tr key={b}><td>{POSE_LABELS[b]} <span className="faint mono">· {b}</span></td><td className="mono">{bins[b]}</td></tr>))}
          </tbody></table></div>
        </Panel>
        <Panel title="Последние кадры" right={<Button size="sm" onClick={onOpenGallery}>все</Button>}>
          {recent.length === 0 ? <div className="muted">Нет данных</div> : (
            <div className="photo-grid">{recent.map((p: Photo) => (
              <button key={p.id} type="button" className="photo-card" onClick={() => onOpenPhoto(p.id)}>
                <div className="thumb"><PhotoArtifactImage photoId={p.id} kind="thumbnail" cover decorative /></div>
                <div className="meta"><div className="id">{p.id}</div><div className="sub">{fmtDate(p.t)} · {p.bucket}</div></div>
              </button>
            ))}</div>
          )}
        </Panel>
      </div>
    </div>
  );
}
